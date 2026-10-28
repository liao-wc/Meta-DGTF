# -*- coding: utf-8 -*-
"""DSH 技术知识库写入器：追加检索/评估结果到 dgtf_memory/tech_knowledge/library.jsonl。"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dgtf_memory" / "tech_knowledge" / "library.jsonl"
FIELDS = ("ts", "query", "title", "url", "summary", "applicability", "action", "applied", "source")


def norm(it: dict) -> dict:
    rec = {k: it.get(k) for k in FIELDS}
    rec["ts"] = str(rec.get("ts") or datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"))
    rec["query"] = str(rec.get("query") or "")
    rec["title"] = str(rec.get("title") or "")
    rec["url"] = str(rec.get("url") or "")
    rec["summary"] = str(rec.get("summary") or "")[:4000]
    rec["applicability"] = str(rec.get("applicability") or "unknown")[:200]
    rec["action"] = str(rec.get("action") or "record")[:200]
    rec["applied"] = bool(rec.get("applied"))
    rec["source"] = str(rec.get("source") or "dsh-guard")[:200]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="输入 JSON 文件（对象或数组）；省略则读 stdin")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    try:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        raw = json.loads(text)
        items = raw if isinstance(raw, list) else [raw]
        records = [norm(x) for x in items if isinstance(x, dict)]
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if out.is_file():
        lines = [ln for ln in out.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    lines.extend(json.dumps(r, ensure_ascii=False) for r in records)
    fd, tmp = tempfile.mkstemp(prefix="techlib.", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, out)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    print(json.dumps({"ok": True, "out": str(out), "added": len(records), "total": len(lines)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
