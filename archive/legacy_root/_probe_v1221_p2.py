#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2] 探针：triage 触发条件改挂结构标签。

用法：python _probe_v1221_p2.py <src.py> > _probe_v1221_p2_before.txt
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.1-rc1.py")
if not SRC.is_absolute():
    SRC = HERE / SRC


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:110]}"


def main() -> int:
    txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("dgtf_p2_probe", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p2_probe"] = m
    spec.loader.exec_module(m)
    out = {}

    # ---- 源码侧 ----
    out["A1_旧词表 _TRIAGE_KEYS 仍在"] = "_TRIAGE_KEYS = (" in txt
    out["A1b_旧词表值"] = list(getattr(m, "_TRIAGE_KEYS", ()) or ())
    out["A2_结构标签前缀常量"] = "_TRIAGE_STRUCTURAL_PREFIXES" in txt
    out["A3_语义关键词常量"] = "_TRIAGE_SEMANTIC_KEYS" in txt
    out["A4__is_triage_candidate"] = "def _is_triage_candidate" in txt
    out["A5_never 常量"] = "_TRIAGE_NEVER_DOWNGRADE" in txt
    out["A6__is_never_downgrade"] = "def _is_never_downgrade" in txt
    _xc = _region(txt, "def _anchor_crosscheck", "def _anchor_pooled_total")
    out["C1_crosscheck 仍用旧词表"] = "for k in _TRIAGE_KEYS)" in _xc
    out["C2_crosscheck 调 _is_triage_candidate"] = "_is_triage_candidate(" in _xc
    out["C3_crosscheck 调 _is_never_downgrade"] = "_is_never_downgrade(" in _xc
    out["C4_产物侧渲染点仍在"] = "triage_downgrades" in txt
    out["A7_动词白名单条数（旁证没动别的）"] = len(
        getattr(m, "_ACTION_VERB_WHITELIST", ()) or ())

    # ---- 功能侧 ----
    out["B1_结构标签命中"] = _try(lambda: m._is_triage_candidate(
        "[外] 具体某老城区的最优方案"))
    out["B2_语义关键词命中"] = _try(lambda: m._is_triage_candidate(
        "信息不足，无法判断"))
    out["B2b_旧四类之一"] = _try(lambda: m._is_triage_candidate("需外部动作"))
    out["B3_负对照_无标签无语义词"] = _try(lambda: m._is_triage_candidate(
        "现场取证难度大"))
    out["B3b_负对照_空串"] = _try(lambda: m._is_triage_candidate(""))
    out["B4_自指判定"] = _try(lambda: m._is_never_downgrade(
        "该判定自指，无共同参照系"))
    out["B4b_本体论判定"] = _try(lambda: m._is_never_downgrade("本体论判断"))
    out["B5_负对照_结构标签不是自指"] = _try(
        lambda: m._is_never_downgrade("[外] 具体某老城区的最优方案"))

    # ---- 产物侧（3 题真跑后才有） ----
    got = []
    for i in (1, 2, 3):
        d = HERE / "outputs" / f"p2_run{i}"
        f = sorted(d.glob("*.md")) if d.is_dir() else []
        if f:
            t = f[0].read_text(encoding="utf-8")
            got.append(_triage_line(t))
    out["D_三题产物 triage 读数"] = got or "（尚未真跑）"

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _region(txt: str, a: str, b: str) -> str:
    i = txt.find(a)
    j = txt.find(b, i + 1) if i >= 0 else -1
    return txt[i:j] if i >= 0 and j > i else (txt[i:] if i >= 0 else "")


def _triage_line(t: str):
    import re as _re
    m = _re.search(r"\*\*triage 降级\*\*：(\d+) 条", t)
    n = int(m.group(1)) if m else None
    items = _re.findall(r"triage ([^\n]{0,60})", t)[:3]
    return {"triage_downgrades": n, "sample": items}


if __name__ == "__main__":
    sys.exit(main())
