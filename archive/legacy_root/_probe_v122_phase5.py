#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段5 探针] 机制审计的可探测量（脚本/报告/文档/登记对账）。

用法：
    python _probe_v122_phase5.py <src.py> > _probe_v122_phase5_after.txt

基线里这些文件与常量都不存在，所以每格都是「取值 / 具名异常 / 不存在」。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
HERE = SRC.parent
spec = importlib.util.spec_from_file_location("dgtf_probe5", SRC)
dgtf = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe5"] = dgtf
spec.loader.exec_module(dgtf)
TXT = SRC.read_text(encoding="utf-8")


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def _run_audit():
    py = HERE / "_audit_v122_dead_mechanisms.py"
    if not py.is_file():
        return "脚本不存在"
    r = subprocess.run([sys.executable, str(py), "--src", SRC.name],
                       cwd=str(HERE), capture_output=True, text=True,
                       timeout=300)
    md = HERE / "audit_v122_dead_mechanisms.md"
    nj = HERE / "_audit_v122_result.json"
    d = json.loads(nj.read_text(encoding="utf-8")) if nj.is_file() else {}
    return {"rc": r.returncode, "md_exists": md.is_file(),
            "n_logs": d.get("n_logs"), "n_prods": d.get("n_prods"),
            "n_reach": d.get("n_reach"), "n_src_only": d.get("n_src_only"),
            "n_check": d.get("n_check"),
            "mechs": [x["mechanism"] for x in (d.get("rows") or [])]}


def _doc():
    p = HERE / "docs" / "机制审计-v122.md"
    if not p.is_file():
        return "文档不存在"
    t = p.read_text(encoding="utf-8")
    return {"has_pending_fix": "## pending_fix" in t,
            "has_dual": "## 双实现清单" in t,
            "has_resolved": "## resolved" in t,
            "mentions_auto_plan": "auto_plan" in t and "_auto_plan" in t}


out = {
    "src": SRC.name,
    "version": getattr(dgtf, "__version__", "?"),
    "A_audit_script": (HERE / "_audit_v122_dead_mechanisms.py").is_file(),
    "B_audit_run": _try(_run_audit),
    "C_doc": _try(_doc),
    "D_const_pending_fix": _try(
        lambda: getattr(dgtf, "_AUDIT122_PENDING_FIX", None)),
    "D2_const_dual": _try(lambda: getattr(dgtf, "_AUDIT122_DUAL_IMPL", None)),
    "E_src_注释条数": TXT.count("# [AUDIT-122] 标 pending_fix："),
    "F_src_机制审计行": "机制审计" in TXT,
    "G_src_pending_fix_串": "pending_fix" in TXT,
    "H_del_lines": _try(lambda: __import__("_v122_verify", fromlist=["x"])
                        .count_del_lines(str(HERE / "_baseline_v12177.py"),
                                         str(SRC))),
    "H2_mechanism_removed": _try(
        lambda: __import__("_v122_verify", fromlist=["x"]).mechanism_removed(
            str(HERE / "_baseline_v12177.py"), str(SRC))),
}
sys.path.insert(0, str(HERE))
print(json.dumps(out, ensure_ascii=False, indent=2))
