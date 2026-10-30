# -*- coding: utf-8 -*-
"""[V2.2.58] 四层 probe 读数方差统计（从审计文档历史 § 抽取，零 API）。

用途：量化「层0 单次方差」等说法——同一 case 在多次复跑中的读数分布。
输入：docs/四层目标读数审计_20261028.md 中各「## N. V2.2.x 复跑」表格。
输出：docs/probe_variance_20261030.json + 控制台摘要。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "docs" / "四层目标读数审计_20261028.md"
OUT = ROOT / "docs" / "probe_variance_20261030.json"

_CASE_RE = re.compile(
    r"^\|\s*(?P<case>0|1|both|all)\s*\|.*?"
    r"(?P<metric>excavate|settle|fuse|crystallize)="
    r"(?P<val>-?\d+(?:\.\d+)?)", re.M)


def _collect() -> dict:
    text = AUDIT.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"^## ", text, flags=re.M)
    data: dict = {}
    for sec in sections:
        m = re.match(r"(\d+)\.\s*V(2\.2\.\d+)(?:\s*/\s*App[^\n]*)?\s*复跑", sec)
        if not m:
            continue
        ver = m.group(2)
        for cm in _CASE_RE.finditer(sec):
            case = cm.group("case")
            key = ver + "/" + case
            data.setdefault(key, []).append({
                "version": ver, "case": case,
                "metric": cm.group("metric"),
                "value": float(cm.group("val")),
            })
    return data


def _stats(vals: list) -> dict:
    if not vals:
        return {"n": 0}
    v = sorted(vals)
    mean = sum(v) / len(v)
    return {"n": len(v), "mean": round(mean, 3), "min": v[0], "max": v[-1],
            "values": v}


def main() -> int:
    data = _collect()
    out: dict = {"schema": "dgtf.probe_variance.v1",
                 "source": str(AUDIT.relative_to(ROOT)).replace("\\", "/"),
                 "cases": {}}
    for case in ("0", "1", "both", "all"):
        vals = []
        for key, rows in data.items():
            if not key.endswith("/" + case):
                continue
            for r in rows:
                if r["case"] == case:
                    vals.append(r["value"])
        out["cases"][case] = _stats(vals)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    for case in ("0", "1", "both", "all"):
        s = out["cases"][case]
        print("case %-4s n=%-2d mean=%-6s min=%-5s max=%-5s values=%s"
              % (case, s.get("n", 0), s.get("mean"), s.get("min"),
                 s.get("max"), s.get("values")))
    print("evidence ->", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
