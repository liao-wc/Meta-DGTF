#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P3] 探针：仅源码机制负对照（before/after）。

用法：python _probe_v1221_p3.py <src.py>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else ""
NL = chr(10)
TXT = Path(SRC).read_text(encoding="utf-8").replace(chr(13) + chr(10), NL)
HERE = Path(".").resolve()

MECHS = ("escalate_starve_rounds", "no_push_when_idle", "_reopen_closed_debt",
         "both_tighten_ratio", "_all_settle_streak")

out = {}
out["A1_src_五机制全在"] = {m: (m in TXT) for m in MECHS}
out["A2_negctl_json"] = (HERE / "_negctl_v1221_p3.json").is_file()
out["A3_negctl_doc"] = (HERE / "docs" / "机制负对照-v1221.md").is_file()
out["A4_audit_doc"] = (HERE / "audit_v122_dead_mechanisms.md").is_file()
_j = HERE / "_negctl_v1221_p3.json"
out["B1_negctl_条数"] = None
out["B2_判定分布"] = None
if _j.is_file():
    try:
        d = json.loads(_j.read_text(encoding="utf-8"))
        out["B1_negctl_条数"] = len(d)
        _c = {}
        for v in d.values():
            _c[v.get("verdict")] = _c.get(v.get("verdict"), 0) + 1
        out["B2_判定分布"] = _c
    except Exception as e:
        out["B2_判定分布"] = "ERR " + type(e).__name__
try:
    spec = importlib.util.spec_from_file_location("dgtf_p3", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p3"] = m
    spec.loader.exec_module(m)
    out["C1_模块可加载"] = True
    out["C2_AUDIT122_常量"] = [
        getattr(m, "_AUDIT122_PENDING_FIX", None),
        getattr(m, "_AUDIT122_DUAL_IMPL", None)]
except Exception as e:
    out["C1_模块可加载"] = "ERR " + type(e).__name__ + ": " + str(e)[:80]
import difflib
out["E1_src_名"] = Path(SRC).name


def _pure_del(a_path, b_path):
    """纯删除块（difflib opcode == delete）——红线口径。"""
    try:
        A2 = Path(a_path).read_bytes().decode("utf-8").replace(
            chr(13) + chr(10), NL).split(NL)
        B2 = Path(b_path).read_bytes().decode("utf-8").replace(
            chr(13) + chr(10), NL).split(NL)
    except Exception:
        return None
    sm = difflib.SequenceMatcher(None, A2, B2)
    return sum(i2 - i1 for tag, i1, i2, j1, j2 in sm.get_opcodes()
               if tag == "delete")


out["E2_纯删除(对_v1220)"] = _pure_del("_baseline_v1220.py", SRC)
out["E3_纯删除(对_v12177)"] = _pure_del("_baseline_v12177.py", SRC)
out["D1_不删机制"] = {
    "说明": "见 _v122_verify --phase p3 的 P3.5/P3.6（纯删除 == 0 且符号消失 == 0）"}
_js = json.dumps(out, ensure_ascii=False, indent=2)
if OUT:
    from pathlib import Path as _P2
    _P2(OUT).write_bytes(_js.encode("utf-8"))
print(_js)
