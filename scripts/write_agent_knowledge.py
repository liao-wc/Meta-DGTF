# -*- coding: utf-8 -*-
"""DSH 技术知识库写入器：追加到 App 技术知识库 dgtf_memory/agent_knowledge.jsonl。"""
from __future__ import annotations
import argparse, json, os, sys, tempfile, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dgtf_memory" / "agent_knowledge.jsonl"


def norm(it: dict) -> dict:
    now = time.time()
    cv = it.get("confidence")
    if isinstance(cv, str):
        m = {"high": 0.9, "medium": 0.7, "low": 0.4,
             "verified": 0.95, "unknown": 0.5}
        cv = m.get(cv.strip().lower(), 0.6)
    else:
        try:
            cv = float(cv)
            if cv > 1:
                cv = cv / 100.0
        except Exception:
            cv = 0.6
    cv = max(0.0, min(1.0, float(cv)))
    return {
        "run": str(it.get("run") or "dsh_guard_patrol"),
        "query": str(it.get("query") or ""),
        "title": str(it.get("title") or ""),
        "url": str(it.get("url") or ""),
        "claim": str(it.get("claim") or it.get("summary") or "")[:2000],
        "content": str(it.get("content") or it.get("summary") or "")[:8000],
        "fetched": bool(it.get("fetched")),
        "retrieved_at": float(it.get("retrieved_at") or now),
        "fetched_at": it.get("fetched_at"),
        "source_type": str(it.get("source_type") or "web_search"),
        "published": str(it.get("published") or ""),
        "pdf_url": str(it.get("pdf_url") or ""),
        "confidence": round(cv, 3),
        "zh_note": str(it.get("zh_note") or "")[:1000],
        "applicability": str(it.get("applicability") or ""),
        "action": str(it.get("action") or ""),
        "applied": bool(it.get("applied")),
        "triage": str(it.get("triage") or ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="输入 JSON（对象或数组）；省略读 stdin")
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
    fd, tmp = tempfile.mkstemp(prefix="agent_kn.", suffix=".tmp", dir=str(out.parent))
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
