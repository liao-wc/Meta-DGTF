# -*- coding: utf-8 -*-
"""DSH Agent 写入热门话题：仅落盘，不调用模型；App /api/dsh/hot-topics 只读该文件。

用法：
  python scripts/write_hot_topics.py --input draft.json
  python scripts/write_hot_topics.py --stdin < draft.json
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dgtf_memory" / "hot_topics.json"
DEFAULT_DOMAINS = ["AI / 科技", "宇宙", "生命 / 健康", "心理", "历史",
                   "经济", "环境", "哲学", "未来 / 社会"]


def normalize(raw: dict) -> dict:
    questions = []
    for it in raw.get("questions") or []:
        if not isinstance(it, dict):
            continue
        q = str(it.get("q") or "").strip()
        dom = str(it.get("domain") or "").strip()
        if not q or not dom:
            continue
        item = {"domain": dom,
                "kind": str(it.get("kind") or "interest"),
                "q": q[:240],
                "query": str(it.get("query") or "")[:300],
                "content": str(it.get("content") or "")[:2000],
                "fetched": bool(it.get("fetched"))}
        if it.get("source"):
            item["source"] = str(it.get("source"))[:300]
        if it.get("url"):
            item["url"] = str(it.get("url"))[:500]
        if it.get("confidence") is not None:
            try:
                item["confidence"] = max(0.0, min(1.0, float(it.get("confidence"))))
            except Exception:
                item["confidence"] = 0.6
        questions.append(item)
    domains = [str(d).strip() for d in (raw.get("domains") or [])
               if str(d).strip()]
    if not domains:
        for it in questions:
            if it["domain"] not in domains:
                domains.append(it["domain"])
    for d in DEFAULT_DOMAINS:
        if d not in domains:
            domains.append(d)
    return {"updated_at": str(raw.get("updated_at") or datetime.now(
                timezone(timedelta(hours=8))).isoformat(timespec="seconds")),
            "source": str(raw.get("source") or "dsh-agent"),
            "ttl_seconds": int(raw.get("ttl_seconds") or 21600),
            "domains": domains,
            "questions": questions,
            "note": str(raw.get("note") or "由 DSH Agent 分析后定期写入；接口只读，不调用模型。")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="输入 JSON 文件；省略则读 stdin")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--history", default=str(ROOT / "dgtf_memory" / "hot_topics_crawl.jsonl"))
    args = ap.parse_args()
    try:
        text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError("根节点必须是对象")
        data = normalize(raw)
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="hot_topics.", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, out)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    # 追加检索/爬取历史，供 Agent 面板「热门话题库」展示
    try:
        hp = Path(args.history)
        hp.parent.mkdir(parents=True, exist_ok=True)
        now = data.get("updated_at") or data.get("source") or ""
        _seen = set()
        if hp.is_file():
            for _ln in hp.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    _r = json.loads(_ln)
                    _seen.add((str(_r.get("domain") or ""), str(_r.get("q") or "")))
                except Exception:
                    pass
        with hp.open("a", encoding="utf-8") as hf:
            for it in data["questions"]:
                if (str(it.get("domain") or ""), str(it.get("q") or "")) in _seen:
                    continue
                hf.write(json.dumps({
                    "ts": now, "run": str(data.get("source") or "dsh-agent"),
                    "domain": it.get("domain"), "kind": it.get("kind"),
                    "q": it.get("q"), "source": it.get("source") or "",
                    "url": it.get("url") or "",
                    "query": it.get("query") or "",
                    "content": it.get("content") or "",
                    "fetched": bool(it.get("fetched")),
                    "confidence": it.get("confidence"),
                }, ensure_ascii=False) + "\n")
    except Exception as exc:
        print("WARN history: %s" % exc, file=sys.stderr)
    print(json.dumps({"ok": True, "out": str(out),
                      "questions": len(data["questions"]),
                      "domains": len(data["domains"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
