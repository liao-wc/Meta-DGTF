#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2] 把 `_v122_verify.py` 里的 `phase_p2` 占位换成真判据。"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "_v122_verify.py"

NEW = '''def _p2_triage_from_md(p) -> dict:
    """从产物 md 取 triage 条数 + 漂移读数（undecidable → partial）。

    md 末尾有 ```json 围栏的 packed 快照，里面有 `pools.*.decidability_log`。
    """
    import re as _re
    t = p.read_text(encoding="utf-8")
    m = _re.search(r"\\*\\*triage 降级\\*\\*：(\\d+) 条", t)
    n = int(m.group(1)) if m else None
    und = tot = 0
    for blk in _re.findall(r"```json\\s*(.*?)```", t, _re.S):
        try:
            d = json.loads(blk)
        except Exception:
            continue
        pools = (d.get("pools") or {}) if isinstance(d, dict) else {}
        for pool in pools.values():
            for ent in ((pool or {}).get("decidability_log") or []):
                tot += 1
                if (str((ent or {}).get("from")) == "undecidable"
                        and str((ent or {}).get("to")) == "partial"):
                    und += 1
    return {"triage": n, "und_from": und, "log_total": tot}


def phase_p2(src, mod):
    """[v1.22.1 P2] triage 触发条件改挂结构标签。"""
    txt = Path(src).read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    xc = _region(txt, "def _anchor_crosscheck", "def _anchor_pooled_total")
    check("P2.1.a", "for k in _TRIAGE_KEYS)" not in xc,
          "旧词表判据已从 crosscheck 换掉")
    check("P2.1.b", "_is_triage_candidate(" in xc,
          "crosscheck 改调 _is_triage_candidate")
    check("P2.1.c", "_is_never_downgrade(" in xc,
          "crosscheck 先过 _is_never_downgrade")
    check("P2.1.d",
          '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in txt,
          "加性：旧词表一字未删")
    check("P2.2.a", "def _is_triage_candidate" in txt
          and "def _is_never_downgrade" in txt,
          "两个判据函数都在")

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return f"ERR {type(e).__name__}: {e}"

    c1 = _try(lambda: mod._is_triage_candidate("[外] 具体某老城区的最优方案"))
    c2 = _try(lambda: mod._is_triage_candidate("信息不足，无法判断"))
    c3 = _try(lambda: mod._is_triage_candidate("现场取证难度大"))
    c4 = _try(lambda: mod._is_triage_candidate(""))
    c5 = _try(lambda: mod._is_never_downgrade("该判定自指，无共同参照系"))
    c6 = _try(lambda: mod._is_never_downgrade("[外] 具体某老城区的最优方案"))
    check("P2.3.a", c1 is True, f"结构标签 [外] 命中（实测 {c1!r}）")
    check("P2.3.b", c2 is True, f"语义关键词命中（实测 {c2!r}）")
    check("P2.3.c", c3 is False and c4 is False,
          f"负对照：无标签无语义词 → False（实测 {c3!r} / {c4!r}）")
    check("P2.3.d", c5 is True, f"真·自指判为不许降级（实测 {c5!r}）")
    check("P2.3.e", c6 is False,
          f"负对照：[外] 不是自指（实测 {c6!r}）")

    tgt = [HERE / "outputs" / f"p2_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        got = sorted(d.glob("*.md")) if d.is_dir() else []
        mds.append(got[0] if got else None)
    if not all(mds):
        check("P2.4.a", False,
              f"三题产物未齐（{sum(1 for x in mds if x)}/3）—— 先跑 _run_v1221_p2.py")
    else:
        info = [_p2_triage_from_md(x) for x in mds]
        ns = [i["triage"] for i in info]
        check("P2.4.a", any(isinstance(n, int) and n >= 1 for n in ns),
              f"≥1 题 triage ≥ 1 条（实测 {ns}）")
        _drift = []
        for i in info:
            if i["log_total"] == 0:
                _drift.append(None)
            else:
                _drift.append(i["und_from"] / i["log_total"])
        _ok_drift = all((d is None) or (d <= 0.5) for d in _drift)
        check("P2.4.b", _ok_drift,
              f"无题出现「全是 partial」漂移（und→partial 占比 ≤50%："
              f"{[None if d is None else round(d, 2) for d in _drift]}）")
        print("  ℹ️  P2.4 详情：" + "；".join(
            f"{p.parent.name} triage={i['triage']} 漂移 {i['und_from']}/"
            f"{i['log_total']}" for p, i in zip(mds, info)))
        for p, i in zip(mds, info):
            if i["triage"]:
                _t = p.read_text(encoding="utf-8")
                _ln = [l for l in _t.splitlines()
                       if "triage" in l and "降级" in l][:2]
                print(f"  ℹ️  {p.parent.name} 降级行：{_ln}")


'''

OLD = 'phase_p2 = _phase_todo("p2")\n'
NEWLINE = 'phase_p2 = _phase_todo("p2")\n'


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    if "def phase_p2(" in s:
        print("· phase_p2 已换过（幂等跳过）")
    else:
        assert s.count(OLD) == 1, f"占位锚点 {s.count(OLD)} 次"
        s = s.replace(OLD, NEW + NEWLINE, 1)
        print("  ✓ phase_p2 占位 → 真判据")
    ast.parse(s)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    assert "def phase_p2(" in TARGET.read_text(encoding="utf-8")
    print("✓ _v122_verify.py phase_p2 已接；ast OK；纯 CRLF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
