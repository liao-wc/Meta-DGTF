# -*- coding: utf-8 -*-
"""OpenAI 兼容适配层：把引擎的 `/v1/chat/completions` 转给本地推理服务 `/generate`。

为什么需要
----------
引擎通过 openai SDK 说话（`base_url` + `chat.completions.create`），而本地服务
只提供 `/generate`（stage 化 + LoRA 路由）。两者协议不通，于是「引擎 + 本地模型」
这条链路**从来没有被端到端跑通过** —— 只能在有 API 预算时用云模型验证。

本适配层把这条链路补上：零 API 成本即可端到端跑引擎，用于
  · 成本归因/结构/调度的**回归验证**（不是质量评估）
  · 预算耗尽时仍能继续迭代

它**不是**质量替代品：本地 0.5B 模型的输出质量远低于云模型，跑出来的读数
只能看「链路是否通、读数是否非空、结构是否完整」，不能当质量指标。

设计要点
--------
1. **不改引擎**：只提供 base_url 指向本服务的配置写法（见 `--print-hint`）。
2. **stage 分流**：本地服务按 stage 选 LoRA 适配器。请求里的 `model` 若写成
   `local:<stage>` 则直接指定；否则按 system 文本特征推断，兜底 `self_check`。
3. **超时可控**：转发超时 < 引擎 client timeout，保证失败是「本地超时」
   而不是「引擎整跑被拖死」。
4. **失败显式**：上游不可达/超时 → 返回 OpenAI 形状的 5xx 且 body 带原因，
   引擎侧会走它自己的失败留痕，不会静默拿到空内容。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple

UPSTREAM = "http://127.0.0.1:8772"

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
#: ★ stage 长度上限只有**一处**定义（`dgtf_local_llm/gates.py`），本地服务也用同一份。
#:   适配层自己再抄一份必然漂移：服务按 64 训练、适配层按 2048 请求，
#:   于是每次调用都要多付 ~2000 个 token 的慢路径解码钱。
from dgtf_local_llm.gates import cap_max_new  # noqa: E402
#: prompt 特征 → 本地 stage。顺序即优先级。
_STAGE_HINTS: List[Tuple[str, str]] = [
    ("双判", "dual_judge"),
    ("dual_judge", "dual_judge"),
    ("自省", "self_check"),
    ("self_check", "self_check"),
    ("回看", "self_check"),
    ("复述", "self_check"),
]
#: 全局长度硬上限（0 = 不额外限制，只按 stage 压）。做对照实验时用。
MAX_NEW_CAP = int(os.environ.get("DGTF_SHIM_MAX_NEW_CAP") or 0)

_DEFAULT_STAGE = "self_check"


def pick_stage(model: str, system: str, user: str) -> str:
    """决定转发给本地服务的 stage。可被单测直接调用（纯函数）。"""
    m = str(model or "")
    if ":" in m:
        tail = m.rsplit(":", 1)[-1].strip()
        if tail:
            return tail
    blob = (system or "") + "\n" + (user or "")
    for needle, stage in _STAGE_HINTS:
        if needle in blob:
            return stage
    return _DEFAULT_STAGE


def flatten_messages(messages: Any) -> Tuple[str, str]:
    """把 OpenAI messages 摊成 (system, user)。多条 system/user 按序拼接。

    ★ content 可能是字符串，也可能是 [{"type":"text","text":...}] 数组
      （引擎发图时用后者）—— 数组情况下只取 text 段，图丢弃并留痕，
      不静默当成空串。
    """
    if not isinstance(messages, list):
        return "", str(messages or "")

    def _text(c: Any) -> str:
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts = []
            for seg in c:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    parts.append(str(seg.get("text") or ""))
            return "\n".join(parts)
        return str(c or "")

    sys_parts, user_parts = [], []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user")
        txt = _text(m.get("content"))
        if role == "system":
            sys_parts.append(txt)
        else:
            user_parts.append(txt)
    return "\n\n".join(sys_parts), "\n\n".join(user_parts)


def call_upstream(stage: str, text: str, max_new_tokens: int,
                  temperature: float, timeout: float) -> Dict[str, Any]:
    body = json.dumps({
        "stage": stage,
        "text": text,
        "max_new_tokens": max(1, int(max_new_tokens)),
        "temperature": float(temperature),
        "timeout": float(timeout),
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        UPSTREAM.rstrip("/") + "/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "dgtf-local-shim/1.0"

    def log_message(self, fmt, *args):  # 静音：判定在引擎侧日志里
        return

    def _send(self, code: int, obj: Dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._send(200, {"object": "list", "data": [{
                "id": "local", "object": "model", "owned_by": "dgtf"}]})
            return
        if self.path.rstrip("/") in ("/health", ""):
            self._send(200, {"ok": True, "shim": "up", "upstream": UPSTREAM})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "unsupported path"}})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8", "replace"))
        except Exception as e:
            self._send(400, {"error": {"message": "bad json: %s" % e}})
            return

        model = str(payload.get("model") or "local")
        system, user = flatten_messages(payload.get("messages"))
        stage = pick_stage(model, system, user)
        # ★★ 长度不是「越大越好」，是**纯成本**：
        #   本地服务在 `prompt + max_new + 2 > 3072` 时会丢掉 CUDA graph 快路径，
        #   而引擎调用普遍 temp>0（graph 本来就不可用）⇒ 慢路径约 150ms/token。
        #   实测同一条 2048-token prompt：要 2048 ⇒ 110s 撞超时并触发引擎重试；
        #   要 64 ⇒ 11s。而模型在该 stage 只吐 22~27 个 token 就 EOS。
        #   ⇒ 按 stage 压到训练长度，一个有效 token 都不损失，省掉 10 倍墙钟。
        max_new = cap_max_new(stage, int(payload.get("max_tokens") or 600))
        if MAX_NEW_CAP:
            max_new = min(max_new, int(MAX_NEW_CAP))
        temp = payload.get("temperature")
        temp = 0.0 if temp is None else float(temp)
        # 本地服务 timeout 上限 120；留出余量防引擎侧先超时
        timeout = 110.0

        t0 = time.monotonic()
        try:
            up = call_upstream(stage, system + "\n\n" + user, max_new, temp, timeout)
        except urllib.error.HTTPError as e:
            # ★ 上游的 503 body 里带着「队列超时 vs 生成超时」的区分，
            #   必须透传 —— 丢掉它，引擎侧就只剩一个「503」，没法判断该压
            #   并发还是压长度。
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
            except Exception:  # noqa: BLE001
                detail = ""
            self._send(503, {"error": {
                "message": "local upstream %s: %s" % (e.code, detail),
                "type": "upstream_error",
                "upstream_status": int(e.code), "upstream_body": detail}})
            return
        except Exception as e:
            self._send(503, {"error": {
                "message": "local upstream failed: %s: %s" % (type(e).__name__, e),
                "type": "upstream_error"}})
            return

        if up.get("ok") is False:
            self._send(503, {"error": {
                "message": "local upstream ok=false: %s" % (up.get("error"),),
                "type": "upstream_error"}})
            return

        text = str(up.get("text") or "")
        pt = int(up.get("prompt_tokens") or 0)
        ct = int(up.get("gen_tokens") or 0)
        self._send(200, {
            "id": "chatcmpl-local-%d" % int(t0 * 1000),
            "object": "chat.completion",
            "created": int(time.time()),
            # ★ 回显请求里原样的 model 名：引擎会比对「请求 model vs 实际服务 model」
            #   并在不一致时告警「模型别名漂移」。适配层不是路由漂移，回显可避免
            #   把一条假告警塞进每跑的日志（告警泛滥会淹掉真漂移）。
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct,
                      "total_tokens": pt + ct},
            # 非标准字段：留痕用，openai SDK 会忽略未知键
            "dgtf_local": {"stage": stage, "confidence": up.get("confidence"),
                           "cached": up.get("cached"), "ms": up.get("ms"),
                           # ★ 排队与生成分开报：「慢」是哪一种，下一步动作完全不同
                           "queue_ms": up.get("queue_ms"),
                           "max_new": max_new},
        })


def serve(port: int, upstream: str) -> None:
    global UPSTREAM
    UPSTREAM = upstream
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    print("[shim] listening 127.0.0.1:%d -> %s" % (port, upstream), flush=True)
    srv.serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenAI 兼容适配层（引擎 ↔ 本地推理服务）")
    ap.add_argument("--port", type=int, default=8773)
    ap.add_argument("--upstream", default="http://127.0.0.1:8772")
    ap.add_argument("--max-new-cap", type=int, default=0,
                    help="全局生成长度硬上限（0=只按 stage 压）。对照实验用。")
    ap.add_argument("--print-hint", action="store_true",
                    help="打印引擎侧需要配置的写法后退出")
    a = ap.parse_args()
    global MAX_NEW_CAP
    MAX_NEW_CAP = int(a.max_new_cap or 0)
    if a.print_hint:
        print(json.dumps({
            "api": {
                "base_url": "http://127.0.0.1:%d/v1" % a.port,
                "key": "local-shim",
                "default_model": "local",
                "reasoner_model": "local",
                "timeout": 180,
            }
        }, ensure_ascii=False, indent=2))
        return 0
    try:
        serve(a.port, a.upstream)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
