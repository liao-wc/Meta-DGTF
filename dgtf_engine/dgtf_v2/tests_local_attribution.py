# -*- coding: utf-8 -*-
"""[V2.2.16] 本地直连调用的成本归因判据（记账无暗路）。

背景：本地端点自动切 self_check/dual_judge=local 后，引擎直连本地服务（不经
OpenAI 客户端）⇒ LLM.call 的记账点看不到这两类调用。若不补，llm_calls /
llm_by_stage 会把它们整段漏掉（V2.2.9/V2.2.10 反复修的那类盲区）。
本判据：纯函数式记账单测 + 三处接线静态判据 + 变异体，零 GPU。
"""
from __future__ import annotations

import importlib.util
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENG_DIR = HERE / "engine"
P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


def _highest():
    cands = list(ENG_DIR.glob("Meta-DGTF-V*.py"))

    def ver(p):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver)
    return cands[-1]


ENGINE = _highest()
_spec = importlib.util.spec_from_file_location("dgtf_v2216_attr", ENGINE)
ENG = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_v2216_attr"] = ENG
_spec.loader.exec_module(ENG)
SRC = ENGINE.read_text(encoding="utf-8-sig")


def _mk_llm():
    llm = object.__new__(ENG.LLM)
    llm.total_calls = 0
    llm.total_tokens = 0
    llm.ops_calls = 0
    llm.ops_tokens = 0
    llm.eval_calls = 0
    llm.eval_tokens = 0
    llm.stage_calls = {}
    llm.stage_tokens = {}
    llm.stage_ms = {}
    llm._lock = threading.Lock()
    return llm


print("引擎：", ENGINE.name)
print("── A record_local_call 纯记账 ──")
ck("A1 版本 >= 2.2.16", tuple(int(x) for x in
   re.search(r"V(\d+)\.(\d+)\.(\d+)", ENGINE.name).groups()) >= (2, 2, 16))
ck("A2 LLM 有 record_local_call 方法",
   callable(getattr(ENG.LLM, "record_local_call", None)))
_llm = _mk_llm()
_llm.record_local_call("dual_judge", calls=2, tokens=120, ms=50)
ck("A3 调用数/总 token 累加", (_llm.total_calls, _llm.total_tokens) == (2, 120),
   (_llm.total_calls, _llm.total_tokens))
ck("A4 stage 桶累加", _llm.stage_calls.get("dual_judge") == 2
   and _llm.stage_tokens.get("dual_judge") == 120
   and _llm.stage_ms.get("dual_judge") == 50, (_llm.stage_calls, _llm.stage_tokens))
_llm.record_local_call("dual_judge", calls=1, tokens=30, ms=10)
ck("A5 二次调用继续累加（不是覆盖）",
   _llm.stage_calls.get("dual_judge") == 3
   and _llm.stage_tokens.get("dual_judge") == 150)
_llm.record_local_call("self_check", calls=1, tokens=40, ms=5)
# ★ 分组口径必须与 cost_bucket 一致（dual_judge / self_check 都可能是 eval 档，
#   不钉死具体值，按引擎自己的分桶函数算期望）
_b1 = ENG.cost_bucket("dual_judge")
_b2 = ENG.cost_bucket("self_check")
_exp_eval = (3 if _b1 == "eval" else 0) + (1 if _b2 == "eval" else 0)
ck("A6 分桶与 cost_bucket 同口径（eval=%d/ops=%d）"
   % (_exp_eval, 4 - _exp_eval),
   _llm.eval_calls == _exp_eval and _llm.ops_calls == 4 - _exp_eval,
   (_llm.eval_calls, _llm.ops_calls, _b1, _b2))
_llm.record_local_call(None, calls=1)
ck("A7 stage 缺失 ⇒ unknown 桶（不静默丢）", "unknown" in _llm.stage_calls)
_llm.record_local_call("dual_judge", calls="bad", tokens="bad")
ck("A8 非法参数不炸且不记账", _llm.stage_calls.get("dual_judge") == 3)


print("── B 三处接线 ──")
_gg = re.search(r"def _self_check_local\(.*?\n    def ", SRC, re.S)
ck("B1 _self_check_local 成功路径记账",
   _gg is not None and "record_local_call" in _gg.group(0)
   and 'record_local_call(\n                    "self_check"' in _gg.group(0))
_dj = re.search(r"def _dual_judge_local\(.*?\n    def ", SRC, re.S)
ck("B2 _dual_judge_local 成功路径记账",
   _dj is not None and 'self.llm.record_local_call(\n                    "dual_judge"' in _dj.group(0))
ck("B3 dual_judge 回退路径保留 token 读数（记账才有数）",
   _dj is not None and '"prompt_tokens": _d.get("prompt_tokens")' in _dj.group(0)
   and '"gen_tokens": _d.get("gen_tokens")' in _dj.group(0))


print("── C 变异体（有牙证明）──")


def _wired(src) -> dict:
    a = re.search(r"def _self_check_local\(.*?\n    def ", src, re.S)
    b = re.search(r"def _dual_judge_local\(.*?\n    def ", src, re.S)
    return {
        "self_check": a is not None and "record_local_call" in a.group(0),
        "dual_judge": b is not None and "record_local_call" in b.group(0),
        "tokens": b is not None and '"prompt_tokens": _d.get("prompt_tokens")' in b.group(0),
    }


_ok = _wired(SRC)
ck("C0 真实源码三项全过（否则 C1–C3 没有对照）", all(_ok.values()), _ok)
_sc_i = SRC.find("def _self_check_local")
_sc_j = SRC.find("self.llm.record_local_call(", _sc_i)
_bad_sc = SRC[:_sc_j] + "self.llm_noop(" + SRC[_sc_j + len("self.llm.record_local_call("):]
ck("C1 变异体：删掉 self_check 记账 ⇒ 判红",
   _wired(_bad_sc)["self_check"] is False)
_i = SRC.find("self.llm.record_local_call(")
_bad = SRC[:_i] + "self.llm_noop(" + SRC[_i + len("self.llm.record_local_call("):]
ck("C2 变异体：全部记账调用换成空实现 ⇒ 判红",
   not all(_wired(_bad).values()))
ck("C3 变异体：删掉回退路径 token 字段 ⇒ 判红",
   _wired(SRC.replace('"prompt_tokens": _d.get("prompt_tokens"),', ""))["tokens"] is False)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
