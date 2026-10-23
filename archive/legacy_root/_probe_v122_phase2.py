#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段2 探针] 三态多票 / 冻结 / 校准队列的可探测量。

用法：
    python _probe_v122_phase2.py <src.py> > _probe_v122_phase2_after.txt

基线里这些符号都不存在，所以每格都是「取值 / 具名异常」二选一。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = sys.argv[1]
HERE = Path(SRC).resolve().parent
spec = importlib.util.spec_from_file_location("dgtf_probe2", SRC)
dgtf = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe2"] = dgtf
spec.loader.exec_module(dgtf)
TXT = Path(SRC).read_text(encoding="utf-8")


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def _pool(labs):
    p = dgtf.Pool()
    p.sub_questions = [{"id": f"s{i}", "decidability": l, "question": f"Q{i}"}
                       for i, l in enumerate(labs, 1)]
    p.deferrals = []
    return p


def _freeze_probe():
    p = _pool(["decidable", "undecidable"])
    fz = dgtf.DecidabilityFreeze()
    sig = fz.freeze(p, layer=1)
    tamper = {}
    for name, mut in (
            ("decidable→partial", lambda qq: qq.sub_questions[0].__setitem__(
                "decidability", "partial")),
            ("decidable→undecidable", lambda qq: qq.sub_questions[0].__setitem__(
                "decidability", "undecidable")),
            ("signature 手改", None)):
        q = _pool(["decidable", "undecidable"])
        fz2 = dgtf.DecidabilityFreeze()
        fz2.freeze(q, layer=1)
        if mut is None:
            q.sub_questions[0]["_frozen_answerable"] = not \
                q.sub_questions[0]["_frozen_answerable"]
        else:
            mut(q)
        try:
            fz2.verify(q)
            tamper[name] = "未判红（漏洞）"
        except RuntimeError:
            tamper[name] = "RuntimeError"
    return {"sig_len": len(sig),
            "has_frozen_keys": all("_frozen_answerable" in s
                                   for s in p.sub_questions),
            "clean_verify": _try(lambda: fz.verify(p)),
            "tamper": tamper}


def _cov_frozen_probe():
    p = _pool(["decidable", "undecidable"])
    fz = dgtf.DecidabilityFreeze()
    fz.freeze(p, layer=1)
    d1 = dgtf.coverage_parts(p, {}, entry="1")[1]
    p.sub_questions[0]["decidability"] = "undecidable"
    d2 = dgtf.coverage_parts(p, {}, entry="1")[1]
    q = _pool(["decidable", "undecidable"])
    e1 = dgtf.coverage_parts(q, {}, entry="1")[1]
    q.sub_questions[0]["decidability"] = "undecidable"
    e2 = dgtf.coverage_parts(q, {}, entry="1")[1]
    return {"frozen_denominator": [d1, d2],
            "unfrozen_denominator": [e1, e2]}


def _calib_probe():
    td = Path(tempfile.mkdtemp())
    (td / "packed.json").write_text(json.dumps({
        "calibration_queue": [{"sub_id": "s1", "final": "partial",
                               "votes": [{"voter": 0, "label": "decidable"},
                                         {"voter": 1, "label": "partial"},
                                         {"voter": 2, "label": "decidable"}]}],
        "freeze": {"signature": "z" * 64},
        "pools": {"1": {"sub_questions": [{"id": "s1", "question": "甲"}]}},
    }, ensure_ascii=False), encoding="utf-8")
    cal = HERE / "bench" / "bench_calibrate.py"
    r1 = subprocess.run([sys.executable, str(cal), "export", str(td),
                         str(td / "b.md")], capture_output=True, text=True)
    tbl = (td / "b.md").read_text(encoding="utf-8") if r1.returncode == 0 else ""
    (td / "b.md").write_text(
        tbl.replace("|  |  |", "| partial | 人工核过 |"), encoding="utf-8")
    r2 = subprocess.run([sys.executable, str(cal), "import", str(td / "b.md"),
                         str(td)], capture_output=True, text=True)
    n = None
    if (td / "verdicts.json").exists():
        n = json.loads((td / "verdicts.json").read_text(
            encoding="utf-8")).get("n")
    return {"export_rc": r1.returncode, "rows": tbl.count("| ") if tbl else 0,
            "import_rc": r2.returncode, "verdicts_n": n}


out = {
    "src": SRC,
    "version": getattr(dgtf, "__version__", "?"),
    "A_tri_vote_prompts": _try(lambda: len(dgtf._TRI_VOTE_PROMPTS)),
    "A2_tri_vote_prompts_distinct": _try(
        lambda: len(set(dgtf._TRI_VOTE_PROMPTS))),
    "B_multi_method": _try(
        lambda: hasattr(dgtf.MetaDGTF, "_adjudicate_sub_tristate_multi")),
    "B2_single_method_still_there": _try(
        lambda: hasattr(dgtf.MetaDGTF, "_adjudicate_sub_tristate")),
    "C_freeze": _try(_freeze_probe),
    "D_cov_frozen": _try(_cov_frozen_probe),
    "E_calib_roundtrip": _try(_calib_probe),
    "F_header_src_三态多票": "三态多票" in TXT,
    "F2_header_src_冻结": "**冻结**" in TXT,
    "G_action_switch": _try(
        lambda: (dgtf.DEFAULT_CONFIG.get("actions") or {}).get(
            "tri_multi_vote")),
    "G2_pack_keys": _try(lambda: sorted(
        k for k in ("freeze", "calibration_queue")
        if k in inspect.getsource(dgtf.MetaDGTF._pack_result))),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
