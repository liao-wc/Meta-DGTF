# -*- coding: utf-8 -*-
"""[V2.2.88] 证据文件命名 ↔ 内容一致性审计（纯函数，零 API）。

背景：run_route_choice_ab.py 曾把 choice 结果写到
route_subset_reasoning_ab_20261029.json（文件名与内容不符，污染证据）。
本审计按文件名 token 与 JSON 内 kind/schema 比对，防止同类错位再次发生。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"
TOKENS = ("reasoning", "choice", "fact", "project")
# schema 里出现的方向词
SCHEMA_TOKENS = {"reasoning": "reasoning", "choice": "choice",
                 "fact": "fact", "project": "project"}


def _actual(d: dict) -> str:
    k = str(d.get("kind") or "").strip().lower()
    if k in SCHEMA_TOKENS:
        return k
    sch = str(d.get("schema") or "").lower()
    for tok, name in SCHEMA_TOKENS.items():
        if tok in sch:
            return name
    return ""


def main() -> int:
    bad, rows = [], []
    for f in sorted(DOCS.glob("*.json")):
        name = f.name.lower()
        expected = next((t for t in TOKENS if t in name), "")
        if not expected:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        actual = _actual(d)
        if not actual:
            continue
        ok = actual == expected
        rows.append({"file": f.name, "expected": expected, "actual": actual,
                     "ok": ok})
        if not ok:
            bad.append("%s：文件名暗示 %s，内容 kind/schema=%s"
                       % (f.name, expected, actual))
    out = {"schema": "metadgtf.evidence_naming.v1", "rows": rows,
           "violations": bad, "n": len(rows), "n_bad": len(bad)}
    ev = ROOT / "docs" / "evidence_naming_20261030.json"
    ev.write_text(json.dumps(out, ensure_ascii=False, indent=1) + chr(10),
                  encoding="utf-8")
    print("evidence files checked:", len(rows), "| violations:", len(bad))
    for b in bad[:10]:
        print("BAD", b)
    print("evidence ->", ev.relative_to(ROOT))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
