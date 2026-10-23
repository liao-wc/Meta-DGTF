# -*- coding: utf-8 -*-
"""盘点现有产物的完成度/成本/可评分性，供优化决策用（只读）。"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "bench"))
_spec = importlib.util.spec_from_file_location("bs", HERE / "bench" / "bench_score.py")
BS = importlib.util.module_from_spec(_spec)
sys.modules["bs"] = BS
_spec.loader.exec_module(BS)

rows = []
for p in sorted((HERE / "outputs").glob("*.packed.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    stem = p.name.replace(".packed.json", "")
    md_p = HERE / "outputs" / (stem + ".md")
    md = md_p.read_text(encoding="utf-8", errors="replace") if md_p.is_file() else ""
    views = d.get("views") or {}
    layers = sorted(views.keys())
    complete = set(layers) >= {"0", "1", "both", "all"}
    errs = md.count("调用失败")
    manual = ("手动" in md[:1200]) or ("manual" in md[:1200].lower())
    status = ""
    m = re.search(r"\*\*状态\*\*：(.+)", md[:2000])
    if m:
        status = m.group(1).strip()
    tri = d.get("tri_state") or [0, 0]
    score = {
        "practice": BS.score_practice(md),
        "research": BS.score_research(md),
        "decision": BS.score_decision_rubric(md),
        "boundary": BS.score_boundary(md),
    }
    cov = None
    mc = re.search(r"可判定覆盖率\s*([\d.]+)%", md)
    if mc:
        cov = float(mc.group(1))
    rows.append({
        "stem": stem, "question": (d.get("question") or "")[:60],
        "layers": layers, "complete": complete, "errs": errs,
        "manual": manual, "status": status,
        "calls": int(d.get("llm_calls") or 0),
        "tokens": int(d.get("llm_tokens") or 0),
        "route": d.get("route") or [],
        "rounds": d.get("rounds") or {},
        "tri": tri,
        "coverage": cov,
        "md_chars": len(md),
        "practice": score["practice"].get("score"),
        "research": score["research"].get("score"),
        "decision": score["decision"].get("score"),
        "n_actions": score["decision"].get("actions"),
        "boundary": score["boundary"].get("score"),
    })

out = HERE / "audits" / "opt_inventory_v12365.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

comp = [r for r in rows if r["complete"] and r["errs"] == 0 and not r["manual"]]
bad = [r for r in rows if r not in comp]
print("total", len(rows), "complete/clean", len(comp), "excluded", len(bad))
print("excluded reasons:", {
    "incomplete": sum(1 for r in bad if not r["complete"]),
    "has_errs": sum(1 for r in bad if r["errs"]),
    "manual": sum(1 for r in bad if r["manual"]),
})
if comp:
    import statistics
    for k in ("calls", "tokens", "md_chars", "decision", "n_actions", "coverage"):
        vals = [r[k] for r in comp if r[k] is not None]
        print(k, "n", len(vals), "median", statistics.median(vals),
              "min", min(vals), "max", max(vals))
    print("practice pass", sum(1 for r in comp if r["practice"] == 1.0), "/", len(comp))
    print("research pass", sum(1 for r in comp if r["research"] == 1.0), "/", len(comp))
    print("boundary pass", sum(1 for r in comp if r["boundary"] == 1.0), "/", len(comp))
    from collections import Counter
    print("decision rubric dist", Counter(r["decision"] for r in comp))
