# -*- coding: utf-8 -*-
"""给产物库审计提案补充详细说明（只改 pending 的 audit 提案）。"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "docs" / "outputs_audit_latest.json"
PDIR = ROOT / "dgtf_memory" / "dsh_proposals"
NL = chr(10)


def main() -> int:
    try:
        d = json.loads(AUDIT.read_text(encoding="utf-8"))
    except Exception:
        print("no audit")
        return 1
    c = d.get("counts") or {}
    base = [
        "【详细说明】",
        "证据：docs/outputs_audit_latest.json；packed=%d，md=%d，run_json=%d。"
        % (int(c.get("packed") or 0), int(c.get("md") or 0), int(c.get("run_json") or 0)),
        "质量：verified=%d，needs_evidence=%d，unverified=%d，answer_ready_false=%d，missing_quality=%d。"
        % (int(c.get("verified") or 0), int(c.get("needs_evidence") or 0),
           int(c.get("unverified") or 0), int(c.get("answer_ready_false") or 0),
           int(c.get("missing_quality") or 0)),
        "主要 flags：%s。" % "；".join("%s=%s" % (a, b) for a, b in (d.get("top_flags") or [])[:6]),
        "影响：可能增加无效真跑成本、降低用户对答案门禁的信任，或让历史产物无法追溯。",
        "建议：先抽样核对 packed 与 md，再按类别修复；不删除历史产物，不把 needs_evidence 改成 verified。",
        "验证：python scripts/outputs_library_audit.py；python fast_gate.py；python dgtf_app/selftest.py；python scripts/run_v2_tests.py。",
        "风险：回放/重建可能覆盖历史文件；追加真跑会消耗预算；缓存收紧可能误复用答案。",
        "需人工决策：是否允许追加真跑/回放/归档，以及可接受的预算与质量门。",
    ]
    text = NL.join(base)
    changed = 0
    for p in PDIR.glob("prop-audit-*.json"):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(rec.get("status")) != "pending":
            continue
        if rec.get("task", {}).get("source_run") != "outputs_library_audit":
            continue
        plan = str(rec.get("plan") or "")
        if "【详细说明】" in plan:
            continue
        rec["plan"] = plan + (NL if plan else "") + text
        rec["plan_gap"] = False
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        changed += 1
        print("enriched", rec.get("id"))
    print("CHANGED", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
