# -*- coding: utf-8 -*-
"""`max_new` 按 stage 压缩的判据（纯函数 + 构造性证明）。

为什么要这套判据
----------------
「适配层把 max_new 从 2048 压到 64」是一个**纯省钱**的改动，按项目规矩
（「省钱」分支必配「省钱真发生」的成本判据），光有纯函数全绿不够，
必须证明**真实入口真的只向上游请求了压过的长度**。

三类判据
--------
A. 纯函数两向：该压的压、不该压的不抬（含退化输入）
B. 单一定义：服务与适配层读的是同一张表（不是各抄一份）
C. 构造性证明：起一个假上游，真跑 shim 的 Handler，断言上游收到的
   `max_new_tokens` == 压过的值
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAILS: list[str] = []
N = [0]


def check(name: str, cond: bool, detail: str = "") -> None:
    N[0] += 1
    if not cond:
        FAILS.append(f"✗ {name}" + (f" — {detail}" if detail else ""))
        print(f"✗ {name}" + (f" — {detail}" if detail else ""))
    else:
        print(f"✓ {name}")


# ─────────────────────────── A. 纯函数两向 ───────────────────────────
from dgtf_local_llm.gates import (  # noqa: E402
    cap_max_new, DEFAULT_MAX_NEW, DEFAULT_MAX_NEW_FALLBACK)

check("A1 self_check 请求 2048 被压到 64（该 stage 训练长度）",
      cap_max_new("self_check", 2048) == 64, str(cap_max_new("self_check", 2048)))
check("A2 dual_judge 请求 600 被压到 224",
      cap_max_new("dual_judge", 600) == 224)
check("A3 route 请求 4096 被压到 96",
      cap_max_new("route", 4096) == 96)
check("A4 未登记 stage 落兜底上限（引擎多数调用走这条路）",
      cap_max_new("expand_pair", 1500) == DEFAULT_MAX_NEW_FALLBACK)
check("A5 ★ 只压不抬：调用方要得更少时原样返回",
      cap_max_new("self_check", 12) == 12)
check("A6 ★ 只压不抬：等于上限时原样返回",
      cap_max_new("dual_judge", 224) == 224)
check("A7 退化输入不炸（None / 空串 / 非数字）",
      all(cap_max_new("self_check", x) > 0
          for x in (None, "", "abc", [], {}, 3.7)))
check("A8 负数/0 被抬到至少 1（不生成 0 token 的空响应）",
      cap_max_new("self_check", 0) == 1 and cap_max_new("self_check", -5) == 1)

# ★ 负对照：光看「压了」不够，要看「压得对不对」。一条「全部压成 1」的实现
#   也能让 A1~A4 全绿，却会把输出砍成空壳。
check("A9 ★ 负对照：不是无脑压到 1（各 stage 各有各的上限）",
      len({cap_max_new(s, 9999) for s in
           ("self_check", "dual_judge", "route", "unknown")}) >= 2)
check("A10 上限表非空且值都 > 0（空表会让所有请求变成兜底）",
      bool(DEFAULT_MAX_NEW) and all(v > 0 for v in DEFAULT_MAX_NEW.values()))

# ───────────────────── B. 单一定义（不是各抄一份）─────────────────────
svc = os.path.join(ROOT, "dgtf_local_llm", "service.py")
shim = os.path.join(ROOT, "scripts", "local_model", "openai_shim.py")
svc_src = open(svc, encoding="utf-8-sig", errors="replace").read()
shim_src = open(shim, encoding="utf-8-sig", errors="replace").read()

check("B1 服务侧不再自带 DEFAULT_MAX_NEW 字面定义（改为从 gates 取）",
      "DEFAULT_MAX_NEW = {" not in svc_src,
      "服务里仍有一份字面定义 ⇒ 两处会漂移")
check("B2 服务侧从 gates 导入该表",
      "from dgtf_local_llm.gates import" in svc_src
      and "DEFAULT_MAX_NEW" in svc_src)
check("B3 适配层也从 gates 导入（不是自己抄一份）",
      "from dgtf_local_llm.gates import cap_max_new" in shim_src)
check("B4 适配层不再写死 2048 上限",
      "min(int(payload.get(\"max_tokens\") or 600), 2048)" not in shim_src)

# ─────────────────── C. 构造性证明：真打一遍 shim ───────────────────
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location("_shim_under_test", shim)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_seen: list[dict] = []


class _Up(BaseHTTPRequestHandler):
    """假上游：记录收到的 body，回一个固定形状的成功响应。"""

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        _seen.append(body)
        raw = json.dumps({"ok": True, "text": "{}", "gen_tokens": 8,
                          "prompt_tokens": 100, "ms": 12.3,
                          "queue_ms": 1.2}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        return


_up = ThreadingHTTPServer(("127.0.0.1", 0), _Up)
threading.Thread(target=_up.serve_forever, daemon=True).start()
_mod.UPSTREAM = "http://127.0.0.1:%d" % _up.server_address[1]

_orig = _mod.Handler
_seen.clear()
_client = ThreadingHTTPServer(("127.0.0.1", 0), _orig)
threading.Thread(target=_client.serve_forever, daemon=True).start()
_port = _client.server_address[1]


def _ask(model: str, max_tokens: int) -> dict:
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "条目：心率。"}],
                       "max_tokens": max_tokens,
                       "temperature": 0.9}).encode()
    import urllib.request as _u
    r = _u.urlopen(_u.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % _port, data=body,
        headers={"Content-Type": "application/json"}), timeout=30)
    return json.loads(r.read().decode())


_seen.clear()
_r1 = _ask("local:self_check", 2048)
check("C1 适配层向真上游请求的长度 == 压过的值（不是 2048）",
      _seen and _seen[0].get("max_new_tokens") == 64,
      "上游收到 %s" % (_seen[0].get("max_new_tokens") if _seen else "nothing"))
check("C2 stage 也正确传到上游（本地服务按 stage 选适配器）",
      _seen and _seen[0].get("stage") == "self_check")

_seen.clear()
_ask("local:dual_judge", 1500)
check("C3 换 stage 后上限随之变化（不是写死一个数）",
      _seen and _seen[0].get("max_new_tokens") == 224,
      "上游收到 %s" % (_seen[0].get("max_new_tokens") if _seen else "nothing"))

_seen.clear()
_ask("local", 1500)
check("C4 model 不带 stage 后缀 ⇒ 走兜底 stage + 兜底上限",
      _seen and _seen[0].get("max_new_tokens") == DEFAULT_MAX_NEW_FALLBACK,
      "上游收到 %s / stage=%s" % (
          _seen[0].get("max_new_tokens") if _seen else None,
          _seen[0].get("stage") if _seen else None))

check("C5 ★ 压过的长度要能被下游看到（响应里回显 max_new，便于事后审计）",
      (_r1.get("dgtf_local") or {}).get("max_new") == 64)
check("C6 ★ 排队耗时与生成耗时分开回显（否则分不清「排队」与「生成慢」）",
      (_r1.get("dgtf_local") or {}).get("queue_ms") is not None)

# ★ 变异体：如果有人把 cap_max_new 换成「原样返回」，C1~C4 必须判红。
_mod.MAX_NEW_CAP = 32
_seen.clear()
_ask("local:self_check", 2048)
check("C7 变异体：全局硬上限生效（说明压缩发生在这条代码路径上，不是别处）",
      _seen and _seen[0].get("max_new_tokens") == 32,
      "上游收到 %s" % (_seen[0].get("max_new_tokens") if _seen else "nothing"))
_mod.MAX_NEW_CAP = 0

_up.shutdown()
_client.shutdown()

print("─" * 60)
print(f"{N[0] - len(FAILS)}/{N[0]} 通过" + (f"，{len(FAILS)} 项判红" if FAILS else ""))
sys.exit(1 if FAILS else 0)
