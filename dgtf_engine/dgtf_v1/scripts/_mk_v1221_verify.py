#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1] 给 `_v122_verify.py` 加 `--phase p1..p7`。

- phase_p1：P1 全部判据（源码区域取样 + `_extract_actions` 三态 + 负对照 +
  3 题产物的 action 数 / rubric）。
- phase_p2..p7：**先注册成「未实现即判红」的占位**。
  ★ 为什么不用空函数：`main()` 里 `if not fn: continue` —— 没注册的 phase
    会以 `PASS 0 / FAIL 0` 退出（假绿）。占位判红才拦得住「跨档验收」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "_v122_verify.py"

P1_FIELDS_DEF = '''_P1_FIELDS = ("verb", "object", "owner_role", "deadline_hint",
               "acceptance", "fallback")


def _region(txt: str, a: str, b: str) -> str:
    """按源码字面串取区间。整文件 grep 会在 before 也命中，判据就没判别力了。"""
    i = txt.find(a)
    j = txt.find(b)
    return txt[i:j] if i >= 0 and j > i else ""


def _p1_actions_from_md(p) -> dict:
    """从产物 md 的「### 二、行动清单」段数 action 与 rubric。

    rubric（三项各 1 分，上限 3）：
      ① action 条数 ≥ 3；② 每条回退非「（未指定）」；③ 「不做什么」非空。
    """
    import re as _re
    t = p.read_text(encoding="utf-8") if hasattr(p, "read_text") else str(p)
    m = _re.search(r"### 二、行动清单(.*?)### 三、", t, _re.S)
    if not m:
        return {"n": 0, "rubric": 0, "note": "无行动清单段"}
    seg = m.group(1)
    ids = _re.findall(r"- \\*\\*(A\\d+)\\*\\*", seg)
    fallbacks = _re.findall(r"- 回退：(.+)", seg)
    nd = _re.search(r"### 五、不做什么\\n(.*?)(?:\\n### |\\Z)", t, _re.S)
    nd_n = len([l for l in (nd.group(1).splitlines() if nd else [])
                if l.strip().startswith("- ")]) if nd else 0
    ok_fb = bool(fallbacks) and all("未指定" not in f for f in fallbacks)
    r = (1 if len(ids) >= 3 else 0) + (1 if ok_fb else 0) + (1 if nd_n else 0)
    return {"n": len(ids), "ids": ids[:6], "n_not_do": nd_n,
            "rubric": r, "fallbacks_all": ok_fb}


def phase_p1(src, mod):
    """[v1.22.1 P1] 研究层直接产出结构化 actions 段。"""
    txt = Path(src).read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    sk = _region(txt, '  "decidable_product": {', '  "undecidable_product": {')
    rq = _region(txt, "【A. decidable_product 要求】",
                 "【B. undecidable_product 要求】")
    _miss = [f for f in _P1_FIELDS if f'"{f}"' not in sk]
    check("P1.1.a", '"actions"' in sk, "decidable_product 骨架里有 actions 键")
    check("P1.1.b", not _miss, f"骨架里六字段齐（缺 {_miss}）")
    check("P1.1.c", "decision 取向必须产出" in rq, "prompt 约束段在")

    def _mk(dp):
        v = mod.View(entry="1")
        v.decidable_product = dp
        return v

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return f"ERR {type(e).__name__}: {e}"

    _full = [{"id": f"A{i}", "verb": "指派", "object": f"对象{i}",
              "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
              "acceptance": "出具签字人清单", "fallback": "向上级申请"}
             for i in (1, 2, 3)]
    a1 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": _full})))
    check("P1.2.a",
          isinstance(a1, list) and len(a1) == 3
          and all(x.get("_source") == "schema" for x in a1),
          f"schema 有 actions → 三条且 _source=schema（实测 "
          f"{a1 if not isinstance(a1, list) else [x.get('_source') for x in a1]}）")
    a2 = _try(lambda: mod._extract_actions(
        _mk({"answer": "先指派区防汛办核查。否则回退上级。"})))
    check("P1.2.b",
          isinstance(a2, list) and a2
          and all(x.get("_source") == "lexical" for x in a2),
          f"schema 无 actions → 走词法并带 _source=lexical（实测 "
          f"{a2 if not isinstance(a2, list) else [x.get('_source') for x in a2]}）")
    a3 = _try(lambda: mod._extract_actions(_mk({"answer": ""})))
    check("P1.2.c", a3 == [], f"负对照 空 answer → []（实测 {a3!r}）")
    a4 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": [{"id": "A1", "verb": "指派",
                                        "object": "核查"}]})))
    check("P1.2.d",
          isinstance(a4, list) and a4 and a4[0].get("_missing"),
          f"负对照 schema 缺字段 → _missing 标出（实测 "
          f"{a4 if not isinstance(a4, list) else a4[0].get('_missing')}）")

    check("P1.3.a", "模型没按 schema 产出 actions" in txt,
          "action_incomplete 语义注释已改写")
    check("P1.3.b", "action_fields_missing" in txt, "action_fields_missing 字面串在")
    _n_schema = len([x for x in a1 if x.get("_source") == "schema"]) \\
        if isinstance(a1, list) else 0
    _any_miss = any(x.get("_missing") for x in a1) if isinstance(a1, list) else True
    check("P1.3.c", _n_schema >= 3 and not _any_miss,
          f"负对照 三条全字段齐全 → 不满足 action_incomplete 触发条件"
          f"（schema {_n_schema} 条 / 有缺字段 {_any_miss}）")
    a5 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": _full[:2]})))
    _n5 = len([x for x in a5 if x.get("_source") == "schema"]) \\
        if isinstance(a5, list) else 0
    check("P1.3.d", _n5 == 2, f"正对照 只给 2 条 → 满足触发条件（实测 {_n5}）")
    check("P1.3.e",
          "action_fields_missing" in (getattr(mod, "_V122_HARD_FLAGS", ()) or ()),
          "新 flag 在 _V122_HARD_FLAGS 里（否则被 quality_flags 重算冲掉）")

    # ---- P1.4 三题真跑产物 ----
    tgt = [HERE / "outputs" / f"p1_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        got = sorted(d.glob("*.md")) if d.is_dir() else []
        mds.append(got[0] if got else None)
    if not all(mds):
        check("P1.4.a", False,
              f"三题产物未齐（{sum(1 for x in mds if x)}/3）—— 先跑 _run_v1221_p1.sh")
    else:
        info = [_p1_actions_from_md(x) for x in mds]
        check("P1.4.a", all(i["n"] >= 3 for i in info),
              f"三题 action 均 ≥ 3（实测 {[i['n'] for i in info]}）")
        avg = sum(i["rubric"] for i in info) / 3.0
        check("P1.4.b", avg >= 2.0,
              f"三题 rubric 平均 ≥ 2/3（实测 {avg:.2f}；各项 "
              f"{[i['rubric'] for i in info]}）")
        _inc = []
        for x in mds:
            t = x.read_text(encoding="utf-8")
            _inc.append("actions 段不足" in t or "action_incomplete" in t)
        check("P1.4.c", not any(_inc),
              f"三题 action_incomplete 均为 0（实测 {_inc}）")
        print(f"  ℹ️  P1.4 详情：" + "；".join(
            f"{p.parent.name} n={i['n']} rubric={i['rubric']} 不做={i['n_not_do']}"
            for p, i in zip(mds, info)))


def _phase_todo(name: str):
    """未实现档的占位：**判红**，不许以 PASS 0 / FAIL 0 假绿。"""
    def _f(src, mod):
        check(f"{name}.todo", False,
              f"{name} 尚未实现（本档未开；不许跨档验收）")
    return _f


phase_p2 = _phase_todo("p2")
phase_p3 = _phase_todo("p3")
phase_p4 = _phase_todo("p4")
phase_p5 = _phase_todo("p5")
phase_p6 = _phase_todo("p6")
phase_p7 = _phase_todo("p7")


'''

OLD_PHASES = '''PHASES = {"1": phase1, "2": phase2, "3": phase3, "4": phase4,
          "5": phase5, "6": phase6}
'''
NEW_PHASES = '''PHASES = {"1": phase1, "2": phase2, "3": phase3, "4": phase4,
          "5": phase5, "6": phase6,
          "p1": phase_p1, "p2": phase_p2, "p3": phase_p3,
          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6, "p7": phase_p7}
'''


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "TARGET 不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    if "def phase_p1(" in s:
        print("· 已接过 p1..p7（幂等跳过）")
    else:
        assert s.count(OLD_PHASES) == 1, "PHASES 锚点不唯一"
        s = s.replace(OLD_PHASES, P1_FIELDS_DEF + NEW_PHASES, 1)
        s = s.replace('ap = argparse.ArgumentParser(description="元 DGTF v1.22.0 六阶段验收")',
                      'ap = argparse.ArgumentParser(\n'
                      '        description="元 DGTF v1.22 六阶段 + v1.22.1 三档验收")', 1)
        s = s.replace('print(f"═══ v1.22.0 验收 · phase={args.phase} · src={Path(src).name} ═══")',
                      'print(f"═══ v1.22 验收 · phase={args.phase} · '
                      'src={Path(src).name} ═══")', 1)
        print("  ✓ phase_p1 已接；p2..p7 注册为「未实现即判红」占位")

    ast.parse(s)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    for must in ("def phase_p1(", "phase_p7 = _phase_todo",
                 '"p1": phase_p1', "_p1_actions_from_md"):
        assert must in TARGET.read_text(encoding="utf-8"), f"自检缺 {must}"
    print("✓ _v122_verify.py 已加 p1..p7；ast OK；纯 CRLF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
