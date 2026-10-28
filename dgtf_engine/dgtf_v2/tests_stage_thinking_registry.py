# -*- coding: utf-8 -*-
"""[V2.2.15] thinking stage 登记闭环判据（审计 K4 的单测版）。

为什么需要它
------------
`audit70`（_probe_v1232_audit.py）的 K4 是「代码里传的字面 stage 都必须在
DEFAULT_CONFIG.api.thinking.stages 里声明」。它一直由 fast_gate 的 audit 任务
承担，但 audit 依赖「导入整个引擎模块 + 解析全文」，跑一次要几分钟；而且它
不区分「登记值是否等于 thinking.default」——登记成 enabled 就等于悄悄改了行为。

本文件是 K4 的**单测版**：零执行引擎（只 AST 解析源码）、毫秒级、且加两条
audit 没有的判据：
  · 新增登记的六个 stage 值必须 == thinking.default（登记不得改行为）；
  · 已声明但永远选不中的 stage（K1 死键）必须为空。
每条判据都有变异体（喂坏源码给同一个检查函数 ⇒ 必须判红）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

V2 = Path(__file__).resolve().parent
ENG_DIR = V2 / "engine"
P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name +
          (" :: " + str(info) if info and not cond else ""))


def _highest_engine() -> Path:
    cands = list(ENG_DIR.glob("Meta-DGTF-V*.py"))
    def ver(p):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    cands.sort(key=ver)
    return cands[-1]


def _dict_of(node):
    """AST Dict 节点 → {str key: value node}（只取 Constant 键）。"""
    out = {}
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out[k.value] = v
    return out


def extract_stage_literals(src: str):
    """代码里所有 `stage="字面量"` 的字面量（K4 口径）。"""
    tree = ast.parse(src)
    lit = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if (kw.arg == "stage" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)):
                    lit.add(kw.value.value)
    return lit


def extract_wired_stages(src: str):
    """`_thinking_stage(cfg, "字面量")` 的接线名（K1/K3 口径）。"""
    tree = ast.parse(src)
    wired = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_thinking_stage" and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant)
                and isinstance(n.args[1].value, str)):
            wired.add(n.args[1].value)
    return wired


def extract_thinking_cfg(src: str):
    """从 DEFAULT_CONFIG 的 AST 里抠出 api.thinking.default 与 stages 表。"""
    tree = ast.parse(src)
    dc = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG":
                dc = n.value
                break
    if dc is None:
        return None, {}
    api = _dict_of(_dict_of(dc).get("api"))
    th = _dict_of(api.get("thinking")) if api else {}
    default = None
    dv = th.get("default")
    if isinstance(dv, ast.Constant):
        default = dv.value
    stages = {}
    sv = th.get("stages")
    if isinstance(sv, ast.Dict):
        for k, v in _dict_of(sv).items():
            if isinstance(v, ast.Constant):
                stages[k] = v.value
    return default, stages


def check_registry(src: str) -> dict:
    """同一套检查：返回 {ok, missing, bad_value, dead_keys, n_lit, default}。"""
    default, stages = extract_thinking_cfg(src)
    lit = extract_stage_literals(src)
    wired = extract_wired_stages(src)
    missing = sorted(lit - set(stages))
    bad_value = sorted(k for k, v in stages.items()
                       if default is not None and v != default
                       and k in ("expand_pair", "expand_pair_merged",
                                 "expand_pair_merged_fixup", "ing",
                                 "he_amps", "manifest"))
    dead = sorted(set(stages) - lit - wired)
    return {"ok": bool(lit) and not missing and not bad_value and not dead,
            "missing": missing, "bad_value": bad_value, "dead_keys": dead,
            "n_lit": len(lit), "default": default, "n_declared": len(stages)}


def main() -> int:
    eng = _highest_engine()
    src = eng.read_text(encoding="utf-8")
    print("引擎：", eng.name)
    print("── A 静态登记 ──")

    default, stages = extract_thinking_cfg(src)
    lit = extract_stage_literals(src)
    ck("A1 ★ thinking.default 可抠出", bool(default), default)
    ck("A2 ★ stage 字面量抽样非空（>=15；防解析器坏掉后恒绿）",
       len(lit) >= 15, len(lit))
    ck("A3 ★ stages 表非空（>=25）", len(stages) >= 25, len(stages))
    r = check_registry(src)
    ck("A4 ★ 所有 stage 字面量都已登记（K4 单测版）",
       not r["missing"], "未登记：" + repr(r["missing"]))
    ck("A5 ★ V2.2.15 新增 6 个登记的取值 == thinking.default（登记不改行为）",
       not r["bad_value"], "值不等于 default：" + repr(r["bad_value"]))
    ck("A6 ★ 没有「声明了但永远选不中」的死键（K1 单测版）",
       not r["dead_keys"], "死键：" + repr(r["dead_keys"]))

    print("── B 变异体（有牙证明）──")
    # B1: 删掉一个登记 ⇒ A4 必须判红
    _line = '                "he_amps": "disabled",\n'
    assert _line in src
    bad1 = src.replace(_line, "", 1)
    ck("B1 ★ 变异体：删掉 he_amps 登记 ⇒ A4 判红",
       "he_amps" in check_registry(bad1)["missing"])
    # B2: 把登记值改成 enabled ⇒ A5 必须判红
    bad2 = src.replace('                "ing": "disabled",\n',
                       '                "ing": "enabled",\n', 1)
    ck("B2 ★ 变异体：把 ing 登记成 enabled（会改行为）⇒ A5 判红",
       "ing" in check_registry(bad2)["bad_value"])
    # B3: 加一个无调用的死键 ⇒ A6 必须判红
    bad3 = src.replace('                "tool_preflight": "disabled",\n',
                       '                "tool_preflight": "disabled",\n'
                       '                "never_used_stage": "disabled",\n', 1)
    ck("B3 ★ 变异体：加一个永远选不中的死键 ⇒ A6 判红",
       "never_used_stage" in check_registry(bad3)["dead_keys"])
    # B4: 解析器被掏空（没有 stage 字面量）⇒ A2/A4 必须判红（防恒绿）
    bad4 = "DEFAULT_CONFIG = {\"api\": {\"thinking\": {\"default\": \"disabled\", \"stages\": {}}}}\n"
    ck("B4 ★ 变异体：源码里没有 stage 字面量 ⇒ 检查函数 ok=False（防恒绿）",
       check_registry(bad4)["ok"] is False)

    print("")
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
