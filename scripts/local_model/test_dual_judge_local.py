# -*- coding: utf-8 -*-
"""dual_judge local 离线判据（Round 96，worktree 分支）。

T1：CLI 接受 local（argparse choices）
T2：本地成功 ⇒ 使用本地判定（不走 llm）
T3：本地失败（None）⇒ 确定性回退 llm
T4：本地 HTTP 协议（stub 服务，stage=dual_judge、messages/text/timeout 字段）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parent.parent
ENGINE = (WT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.3.py")

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


class _Stub(BaseHTTPRequestHandler):
    body = {"ok": True, "confidence": 0.9,
            "text": json.dumps({"judgments": [
                {"idx": 1, "position": "1", "why_position": "stub"},
                {"idx": 2, "position": "0", "why_position": "stub"}]})}
    last = {}

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace")
        try:
            _Stub.last = json.loads(raw)
        except Exception:  # noqa: BLE001
            _Stub.last = {}
        out = json.dumps(_Stub.body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D401
        return


def _load_engine():
    spec = importlib.util.spec_from_file_location("dgtf_engine_mod", str(ENGINE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_engine_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    # T1：CLI choices 含 local
    r = subprocess.run([sys.executable, str(ENGINE), "--help"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(WT))
    out = (r.stdout or "") + (r.stderr or "")
    ck("T1 CLI 接受 --dual-judge-mode local",
       "llm,cache,auto,local" in out.replace(" ", ""), out[-300:])

    srv = HTTPServer(("127.0.0.1", 8799), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        mod = _load_engine()
        cls = None
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and "_dual_judge_local" in getattr(
                    obj, "__dict__", {}):
                cls = obj
                break
        ck("T2 引擎含 _dual_judge_local 方法", cls is not None)
        if cls is None:
            return 1

        eng = object.__new__(cls)
        eng.local_llm_cfg = {"url": "http://127.0.0.1:8799/generate",
                            "min_confidence": 0.6,
                            "judge_timeout": 10,
                            "judge_max_new_tokens": 100}
        eng.llm = types.SimpleNamespace(parse_json=lambda s: json.loads(s))
        eng._carry_block_text = lambda *a: ""
        eng._self_block = lambda: ""
        eng._dual_judge_spec = lambda: ""
        eng._decidability_block = lambda i: ""
        eng._judge_context = lambda i, a: "ctx"
        eng._stable_first = lambda: True
        eng._move_var_to_user = lambda s, v, u: (s, u)
        eng.show_dual = False
        eng.vp = lambda *a: None
        eng.config = {}
        eng.sp = {}
        eng.entry = "1"
        eng._local_llm_fail = lambda e: None
        eng._dual_apply_judgments = lambda *a: "APPLIED"
        eng._dual_judge_llm = lambda *a, **k: "LLM"
        eng._extract_judgments = lambda data: {
            int(j["idx"]): j for j in data.get("judgments", [])}
        cands = [types.SimpleNamespace(kind="c", desc="a"),
                 types.SimpleNamespace(kind="c", desc="b")]
        inp = types.SimpleNamespace()

        got = eng._dual_judge_local(cands, inp, "anchor")
        ck("T3 本地成功路径返回本地判定", got == "APPLIED", got)
        ck("T4 本地请求协议（stage/messages/text/timeout）",
           _Stub.last.get("stage") == "dual_judge"
           and isinstance(_Stub.last.get("messages"), list)
           and _Stub.last.get("text")
           and "timeout" in _Stub.last,
           {k: _Stub.last.get(k) for k in ("stage", "timeout")})

        # T7：长候选被截断（单条描述 >120 字不进 prompt）
        long_c = types.SimpleNamespace(kind="c", desc="长" * 3000)
        eng._dual_judge_local([long_c], inp, "anchor")
        ck("T7 长候选描述被截断（≤120字/条）",
           "长" * 200 not in str(_Stub.last.get("text") or ""))

        # T8：失败计数（ok=false ⇒ 回退并 +1）
        eng.dual_judge_local_fallbacks = 0
        _Stub.body = {"ok": False, "text": ""}
        got_fail = eng._dual_judge_local(cands, inp, "anchor")
        ck("T8 失败回退计数 +1",
           got_fail is None
           and int(getattr(eng, "dual_judge_local_fallbacks", 0)) == 1,
           (got_fail, getattr(eng, "dual_judge_local_fallbacks", None)))
        _Stub.body = {"ok": True, "confidence": 0.9,
                      "text": json.dumps({"judgments": [
                          {"idx": 1, "position": "1", "why_position": "stub"},
                          {"idx": 2, "position": "0",
                           "why_position": "stub"}]})}

        # T5：分发器 local 成功用本地；local 失败回退 llm
        # ★ [Round 137] 模块级调用预算/熔断需在测试间复位（每 run 一进程语义）
        try:
            mod._DJ_LOCAL_BREAKER.update({"fail": 0, "until": 0.0,
                                         "calls": 0, "logged": False})
        except Exception:  # noqa: BLE001
            pass
        eng.dual_judge_mode = "local"
        ck("T5 分发器 local ⇒ 本地结果", eng._dual_judge(cands, inp, "anchor") == "APPLIED")
        eng._dual_judge_local = lambda *a, **k: None
        ck("T6 分发器 local 失败 ⇒ 回退 llm",
           eng._dual_judge(cands, inp, "anchor") == "LLM")
    finally:
        srv.shutdown()

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
