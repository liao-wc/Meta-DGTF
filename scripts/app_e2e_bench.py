# -*- coding: utf-8 -*-
"""App 端到端编排时延基线：mock 任务从 POST 到首条日志 / 完成的墙钟。"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _req(url, token, data=None, timeout=15):
    h = {"Content-Type": "application/json; charset=utf-8",
         "X-DGTF-Token": token}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=h)
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://127.0.0.1:8765")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    tok = (ROOT / "dgtf_memory/.access_token").read_text(encoding="utf-8").strip()
    t0 = time.perf_counter()
    resp = _req(args.base + "/api/tasks?t=" + tok, tok,
                {"question": "App端到端编排时延基线（mock）",
                 "opts": {"mock": True, "auto_fused": False}})
    t_post = (time.perf_counter() - t0) * 1000
    tid = resp.get("id")
    first_log_ms = None
    done_ms = None
    for _ in range(300):
        time.sleep(0.1)
        try:
            tasks = _req(args.base + "/api/tasks?t=" + tok, tok)
            row = next((x for x in (tasks.get("tasks") or [])
                        if str(x.get("id")) == str(tid)), None)
            if first_log_ms is None:
                try:
                    lg = _req(args.base + "/api/tasks/%s/log?offset=0&mode=filtered&t=%s"
                               % (tid, tok), tok)
                    if (lg.get("text") or lg.get("lines") or lg.get("log")):
                        first_log_ms = (time.perf_counter() - t0) * 1000
                except Exception:
                    pass
            if row and str(row.get("status")) in ("done", "error", "cancelled"):
                done_ms = (time.perf_counter() - t0) * 1000
                break
        except Exception:
            continue
    out = {"ok": bool(tid), "id": tid,
           "post_ms": round(t_post, 1),
           "first_log_ms": round(first_log_ms, 1) if first_log_ms else None,
           "done_ms": round(done_ms, 1) if done_ms else None}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
