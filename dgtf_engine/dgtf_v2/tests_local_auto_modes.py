# -*- coding: utf-8 -*-
"""[V2.2.16] 本地端点「自省/双判默认档自动切 local」判据。

背景
----
0.5B 本地链路上，output.self_check_mode / dual_judge_mode 的默认档是 "llm"：
引擎会把**自然语言 prompt** 经 shim 发给 LoRA 适配器，而适配器训练契约是
结构化 payload（服务端只在 text 是 JSON 形状时才转）—— 实测经 shim 的
dual_judge 74/74 条输出都不是 JSON。V2.2.16 在 main() 里把「本地端点 + 默认
llm + 无显式 CLI」的两项自动切到 local（直连服务、按契约发结构化 payload）。

本判据测纯函数 _auto_local_modes(cfg, explicit)（从 main() 里提出来，可测），
以及「接线真的在 main 里」与「显式/非默认值一律尊重」。
"""
from __future__ import annotations

import importlib.util
import re
import sys
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
_spec = importlib.util.spec_from_file_location("dgtf_v2216_auto_modes", ENGINE)
ENG = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_v2216_auto_modes"] = ENG
_spec.loader.exec_module(ENG)
SRC = ENGINE.read_text(encoding="utf-8-sig")

print("引擎：", ENGINE.name)
print("── A 端点判定（_is_local_llm_endpoint）──")
_ep = ENG._is_local_llm_endpoint
ck("A1 127.0.0.1 ⇒ 本地", _ep({"api": {"base_url": "http://127.0.0.1:8773/v1"}}) is True)
ck("A2 localhost ⇒ 本地", _ep({"api": {"base_url": "http://localhost:8000/v1"}}) is True)
ck("A3 [::1] ⇒ 本地", _ep({"api": {"base_url": "http://[::1]:8773/v1"}}) is True)
ck("A4 云端 ⇒ 非本地", _ep({"api": {"base_url": "https://api.deepseek.com/v1"}}) is False)
ck("A5 空配置 ⇒ 非本地（不抛异常）", _ep({}) is False and _ep(None) is False)


print("── B 自动切档纯函数 ──")
_fn = getattr(ENG, "_auto_local_modes", None)
ck("B0 引擎有 _auto_local_modes（否则 main 的自动切档不可测）", _fn is not None)
if _fn is not None:
    def mk(base):
        return {"api": {"base_url": base},
                "output": {"self_check_mode": "llm", "dual_judge_mode": "llm"}}

    c1 = mk("http://127.0.0.1:8773/v1")
    ch = _fn(c1, ())
    ck("B1 本地端点 + 默认 llm + 无显式 ⇒ 两项都切 local",
       sorted(ch) == ["dual_judge_mode", "self_check_mode"]
       and c1["output"]["self_check_mode"] == "local"
       and c1["output"]["dual_judge_mode"] == "local", (ch, c1["output"]))
    c2 = mk("https://api.deepseek.com/v1")
    ck("B2 云端端点 ⇒ 一项都不动", _fn(c2, ()) == []
       and c2["output"]["self_check_mode"] == "llm")
    c3 = mk("http://127.0.0.1:8773/v1")
    ch3 = _fn(c3, ("self_check_mode",))
    ck("B3 显式 self_check_mode ⇒ 只切另一项、显式项不动",
       ch3 == ["dual_judge_mode"]
       and c3["output"]["self_check_mode"] == "llm", (ch3, c3["output"]))
    c4 = mk("http://127.0.0.1:8773/v1")
    c4["output"]["dual_judge_mode"] = "cache"
    ch4 = _fn(c4, ())
    ck("B4 配置非默认值（cache）⇒ 不动它，只切仍是 llm 的项",
       ch4 == ["self_check_mode"]
       and c4["output"]["dual_judge_mode"] == "cache", (ch4, c4["output"]))
    c5 = mk("http://127.0.0.1:8773/v1")
    c5["output"]["self_check_mode"] = "auto_narr"
    ch5 = _fn(c5, ())
    ck("B5 配置 auto_narr ⇒ 不动（只切 llm 默认项）",
       ch5 == ["dual_judge_mode"] and c5["output"]["self_check_mode"] == "auto_narr",
       (ch5, c5["output"]))
    c6 = {"api": {"base_url": "http://127.0.0.1:8773/v1"}}
    ck("B6 output 段缺失 ⇒ 不抛异常、返回空", _fn(c6, ()) == [])
    c7 = mk("http://127.0.0.1:8773/v1")
    c7["output"] = []
    ck("B7 output 形状非法（list）⇒ 返回空、不抛", _fn(c7, ()) == [])


print("── C main() 真接线 ──")
ck("C1 main 里调用了 _auto_local_modes（不是又抄一份判断）",
   re.search(r"_auto_local_modes\(cfg,", SRC) is not None)
ck("C2 自动切档只在本地端点分支内（避免云端被切）",
   re.search(r"if _is_local_llm_endpoint\(cfg\):(?:.|\n){0,400}?_auto_local_modes\(",
             SRC) is not None)


print("── D 变异体（有牙证明）──")


def _auto_impl_wrong(cfg, explicit):
    """变异体：忽略 explicit（显式 CLI 会被覆盖）⇒ B3 必须判红。"""
    oc = (cfg or {}).get("output") or {}
    changed = []
    for k in ("self_check_mode", "dual_judge_mode"):
        if str(oc.get(k) or "llm") == "llm":
            oc[k] = "local"
            changed.append(k)
    return changed


_b = {"api": {"base_url": "http://127.0.0.1:8773/v1"},
      "output": {"self_check_mode": "llm", "dual_judge_mode": "llm"}}
_wrong = _auto_impl_wrong(_b, ("self_check_mode",))
ck("D1 ★ 变异体：忽略显式 CLI 的实现 ⇒ 会切两项（B3 期望只切一项）",
   _wrong == ["self_check_mode", "dual_judge_mode"])

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
