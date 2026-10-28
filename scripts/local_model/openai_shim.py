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
from dgtf_local_llm.gates import (  # noqa: E402
    cap_max_new, sanitize_stage, finish_reason_for,
    LORA_STAGES, BASE_STAGE_REP_PEN)
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

#: ★ [V2.2.13] stage 通道对账计数（/health 暴露；线程安全）。
import threading as _threading  # noqa: E402
_STATS_LOCK = _threading.Lock()
_STATS: dict = {}

_DEFAULT_STAGE = "self_check"


def pick_stage(model: str, system: str, user: str, explicit: str = "") -> str:
    """决定转发给本地服务的 stage。可被单测直接调用（纯函数）。

    优先级（V2.2.13 起）：
      1. **显式 stage**（引擎经 extra_body 摊到请求体顶层的 `stage` 字段）——
         清洗后直接采用。★ 此前没有这条通道：引擎请求既不带 stage、文本也
         不含关键词 ⇒ 兜底 self_check ⇒ 主生成/清单/重锚定全被路由到
         **自省 LoRA** + 64 token（题不对文，JSON 截断靠修复硬扛）。
      2. `model` 写成 `local:<stage>`。
      3. 文本特征关键词。
      4. 兜底 `self_check`。
    """
    _ex = _sanitize_stage(explicit)
    if _ex:
        return _ex
    m = str(model or "")
    if ":" in m:
        tail = m.rsplit(":", 1)[-1].strip()
        if tail:
            return _sanitize_stage(tail) or _DEFAULT_STAGE
    blob = (system or "") + "\n" + (user or "")
    for needle, stage in _STAGE_HINTS:
        if needle in blob:
            return stage
    return _DEFAULT_STAGE


#: ★ [V2.2.13] 单一定义迁到 `dgtf_local_llm/gates.py`（service 也从那里取）。
#:   此处留别名兼容旧引用（单测直接调 `_sanitize_stage`）。
_sanitize_stage = sanitize_stage


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
                  temperature: float, timeout: float,
                  rep_pen: float = 0.0) -> Dict[str, Any]:
    body = json.dumps({
        "stage": stage,
        "text": text,
        "max_new_tokens": max(1, int(max_new_tokens)),
        "temperature": float(temperature),
        "timeout": float(timeout),
        # ★ [V2.2.14] 重复惩罚透传（0 = 关，服务端默认也是关）。
        "repetition_penalty": float(rep_pen),
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
            with _STATS_LOCK:
                stats = dict(_STATS)
            self._send(200, {"ok": True, "shim": "up", "upstream": UPSTREAM,
                             # ★ [V2.2.13] stage 通道对账读数：
                             #   explicit_stage = 显式 stage 被采用的请求数；
                             #   mismatch_avoided = 其中若无此通道会被错路由
                             #   （文本猜出别的 stage）的请求数。两者为 0
                             #   说明通道断了（引擎没带 stage 字段）。
                             "stage_channel": stats})
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
        # ★ [V2.2.13] 显式 stage 通道：引擎经 extra_body 摊到顶层。
        #   同时对账「若无此通道会路由到哪」—— 错路由避免数进 /health，
        #   不然这条通道哪天断了也没人知道（通道断了 ≠ 行为变了）。
        _explicit = str(payload.get("stage") or "")
        _guess = pick_stage(model, system, user)
        stage = pick_stage(model, system, user, _explicit)
        if _sanitize_stage(_explicit):
            with _STATS_LOCK:
                _STATS["explicit_stage"] = _STATS.get("explicit_stage", 0) + 1
                if stage != _guess:
                    _STATS["mismatch_avoided"] = \
                        _STATS.get("mismatch_avoided", 0) + 1
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

        # ★ [V2.2.14] base-model stage 默认带重复惩罚：0.5B 底座在结构化
        #   JSON 任务上确定性复读（同一短语 ×N 撞上限 ⇒ JSON 必截断），
        #   实测见 gates.BASE_STAGE_REP_PEN 注释。LoRA stage 不带
        #   （训练分布内不复读；且多走 temp=0 graph 快路径，惩罚不适用）。
        _rep_pen = 0.0 if stage in LORA_STAGES else BASE_STAGE_REP_PEN
        t0 = time.monotonic()
        try:
            up = call_upstream(stage, system + "\n\n" + user, max_new, temp,
                               timeout, rep_pen=_rep_pen)
            # ★ [诊断 · env 门控] DGTF_SHIM_DUMP=<path> 时把每条请求+上游
            #   原文落盘（JSONL 追加）。默认完全不写。用于「引擎实际发的
            #   prompt 长什么样」这类只能看真流量的诊断。
            _dump = os.environ.get("DGTF_SHIM_DUMP") or ""
            if _dump:
                try:
                    with open(_dump, "a", encoding="utf-8") as _f:
                        _f.write(json.dumps({
                            "ts": time.time(), "stage": stage,
                            "temp": temp, "max_new": max_new,
                            "rep_pen": _rep_pen,
                            "system": (system or "")[:4000],
                            "user": (user or "")[:6000],
                            "upstream_text": str(up.get("text") or "")[:3000],
                            "gen_tokens": up.get("gen_tokens"),
                        }, ensure_ascii=False) + "\n")
                except Exception:  # noqa: BLE001
                    pass
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
                # ★ 诚实的 finish_reason：被 max_new 掐断要报 "length"，
            #   否则引擎的续跑机制（last_finish=="length"）在本地是死的，
            #   截断 JSON 全靠修复硬扛。此前这里硬编码 "stop"。
            "finish_reason": finish_reason_for(ct, max_new),
            }],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct,
                      "total_tokens": pt + ct},
            # 非标准字段：留痕用，openai SDK 会忽略未知键
            "dgtf_local": {"stage": stage, "confidence": up.get("confidence"),
                           "cached": up.get("cached"), "ms": up.get("ms"),
                           # ★ 排队与生成分开报：「慢」是哪一种，下一步动作完全不同
                           "queue_ms": up.get("queue_ms"),
                           "max_new": max_new,
                           "truncated": finish_reason_for(ct, max_new) == "length",
                           # ★ [V2.2.13] 请求的 stage（清洗前）与是否走了显式通道
                           "requested_stage": _explicit or None,
                           "explicit": bool(_sanitize_stage(_explicit))},
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
