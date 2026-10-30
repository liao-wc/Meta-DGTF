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


TOK = ("reasoning", "choice", "fact", "project")


def _static_scan() -> list:
    """静态扫描证据写手：文件名 token 与同文件 schema 的方向词不能矛盾。"""
    import glob
    import re
    bad = []
    for f in glob.glob(str(ROOT / "scripts" / "local_model" / "*.py")) + \
            glob.glob(str(ROOT / "scripts" / "*.py")):
        try:
            t = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'docs["/\\\\]+([A-Za-z0-9_\-]+\.json)', t):
            name = m.group(1).lower()
            exp = next((x for x in TOK if x in name), "")
            if not exp:
                continue
            seg = t[max(0, m.start() - 6000):m.end() + 6000]
            actual = ""
            for s in re.findall(r'"schema"\s*:\s*"([^"]+)"', seg):
                slow = s.lower()
                for x in TOK:
                    if x in slow:
                        actual = x
                        break
                if actual:
                    break
            if actual and actual != exp:
                bad.append("%s 写 %s 但 schema 方向是 %s"
                           % (Path(f).name, name, actual))
    return bad


def _date_scan() -> list:
    """日期证据：文件名前缀日期与 JSON ts/iso/generated_at 必须同日。"""
    import glob
    import re
    bad = []
    for f in glob.glob(str(DOCS / "*.json")):
        name = Path(f).name
        m = re.match(r"^(\d{8})_", name)
        if not m:
            continue
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        ts = str(d.get("ts") or d.get("iso") or d.get("generated_at") or "")
        dm = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", ts)
        if not dm:
            continue
        tdate = dm.group(1) + dm.group(2) + dm.group(3)
        if m.group(1) != tdate:
            bad.append("%s 文件名日期 %s ≠ 内容日期 %s"
                       % (name, m.group(1), tdate))
    return bad


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
    static_bad = _static_scan()
    date_bad = _date_scan()
    bad = bad + static_bad + date_bad
    out = {"schema": "metadgtf.evidence_naming.v1", "rows": rows,
           "static_violations": static_bad, "date_violations": date_bad,
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
