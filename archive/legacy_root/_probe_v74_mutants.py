# -*- coding: utf-8 -*-
"""[v1.21.74 变异测试] 证明 check_v74_anchor_refs 有判别力。

★ 为什么必须做：结构不变式在**现版**必然通过，「通过」本身不构成证据。
  真正的判据要能在畸形体上报错。本脚本造 3 个畸形体，要求**每个都被抓到**。

做法：把 v1.21.74 复制成畸形体，重进 smoke_test 的 `mod` / `SRC` 两个全局，
再调 `check_v74_anchor_refs()` —— 它每次调用都现读这两个全局，所以能换被测对象。

畸形体：
  M1 删掉携带块          → 应当 [形态] / [B] 报错（等于退回 v1.21.73 的丢引用）
  M2 无条件携带 if True  → 应当 [A] 报错（关闭态泄漏键，加性红线破了）
  M3 只看 refs 不看 given → 应当 [C] 报错（「给了 12 条却 0 引用」被抹掉）

跑法：python _probe_v74_mutants.py
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC74 = HERE / "元DGTF-V1.21.74.py"
SMOKE = HERE / "smoke_test.py"

# 携带块原文（v1.21.74 里的写法，逐字）
CARRY_IF = "        if _ext_refs or _ext_given:\n"
SET_REFS = '            merged["anchor_refs"] = _ext_refs\n'
SET_GIVEN = '            merged["_anchors_given"] = _ext_given\n'

MUTANTS = [
    ("M1 删掉携带块（退回丢引用）", "delete"),
    ("M2 无条件携带（关闭态泄漏）", "always"),
    ("M3 只看 refs、丢掉 given 条件", "refs_only"),
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_mutant(text: str, kind: str) -> str:
    n_carry = text.count(CARRY_IF)
    assert n_carry == 1, f"携带块 IF 出现 {n_carry} 次（期望 1）"
    n_refs = text.count(SET_REFS)
    n_given = text.count(SET_GIVEN)
    assert n_refs == 1 and n_given == 1, "赋值语句计数异常"

    if kind == "delete":
        lines = text.split("\n")
        out = [l for l in lines
               if l != CARRY_IF.rstrip("\n")
               and l != SET_REFS.rstrip("\n")
               and l != SET_GIVEN.rstrip("\n")]
        assert len(lines) - len(out) == 3, "M1 没删干净"
        return "\n".join(out)
    if kind == "always":
        return text.replace(CARRY_IF, "        if True:\n", 1)
    if kind == "refs_only":
        return text.replace(CARRY_IF, "        if _ext_refs:\n", 1)
    raise AssertionError(kind)


def run_check(mut_path: Path) -> tuple[bool, str]:
    """把 smoke_test 的 mod / SRC 换成畸形体再跑判据，返回 (通过?, 输出)。"""
    smoke = load_module("smoke_mut", SMOKE)
    smoke.SRC = mut_path
    m = load_module("dgtf_mut", mut_path)
    smoke.mod = m
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = smoke.check_v74_anchor_refs()
    return bool(ok), buf.getvalue()


def main() -> int:
    base = SRC74.read_bytes().decode("utf-8")
    assert base.count("\n") == base.count("\r\n"), "v1.21.74 不是纯 CRLF"
    text = base.replace("\r\n", "\n")

    tmp = Path(tempfile.mkdtemp(prefix="dgtf74mut_"))
    print(f"畸形体目录：{tmp}\n")

    all_ok = True
    for name, kind in MUTANTS:
        mt_text = make_mutant(text, kind)
        p = tmp / f"mut_{kind}.py"
        p.write_bytes(mt_text.replace("\n", "\r\n").encode("utf-8"))
        ok, out = run_check(p)
        tail = " | ".join(
            l.strip() for l in out.splitlines()
            if l.strip().startswith(("✗", "-", "✓")))[:180]
        if ok:
            print(f"❌ {name}\n    畸形体仍然全绿 —— 判据 **没有判别力**\n")
            all_ok = False
        else:
            first = next((l.strip() for l in out.splitlines()
                          if l.strip().startswith(("✗", "  ✗", "    -"))), "")
            print(f"✅ {name}\n    被抓到：{first[:110]}\n")

    # 正对照：未改动的 v1.21.74 必须全绿（否则判据本身写错了）
    ok0, out0 = run_check(SRC74)
    if ok0:
        print("✅ 正对照：未改动的 v1.21.74 全绿（判据本身没写错）")
    else:
        print("❌ 正对照失败：原版都过不了，判据写错了")
        print(out0[-800:])
        all_ok = False

    print("\n" + "=" * 60)
    print("结论：3 个畸形体全部被抓到" if all_ok
          else "结论：存在没被抓到的畸形体 —— 判据需加强")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
