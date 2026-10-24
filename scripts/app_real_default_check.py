# -*- coding: utf-8 -*-
"""App 真实默认链路验证：POST /api/tasks（不传 mock，M4 默认 auto）→ 轮询到完成。"""
from __future__ import annotations
import json, ssl, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOK = (ROOT / "dgtf_memory/.access_token").read_text(encoding="utf-8").strip()
CTX = ssl._create_unverified_context()
BASE = "https://127.0.0.1:8765"

def req(path, data=None, timeout=30):
    url = BASE + path + ("?t=" + TOK if "?" not in path else "&t=" + TOK)
    h = {"Content-Type": "application/json; charset=utf-8", "X-DGTF-Token": TOK}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))

t0 = time.perf_counter()
created = req("/api/tasks", {"question": "1+1等于几？",
                             "opts": {"timeout_s": 3600}})
tid = created.get("id")
print("CREATED", json.dumps(created, ensure_ascii=False), flush=True)
last = None
for i in range(240):
    time.sleep(5)
    try:
        tasks = req("/api/tasks")
        row = next((x for x in (tasks.get("tasks") or [])
                    if str(x.get("id")) == str(tid)), None)
        last = row
        st = str((row or {}).get("status") or "")
        print("POLL", i, st, round(time.perf_counter() - t0, 1), flush=True)
        if st in ("done", "error", "cancelled"):
            break
    except Exception as e:
        print("POLL_ERR", e, flush=True)
out = {"created": created, "task": last,
       "elapsed_s": round(time.perf_counter() - t0, 1)}
try:
    detail = req("/api/tasks/" + str(tid))
    out["detail_keys"] = sorted(detail.keys())
    log = req("/api/tasks/%s/log?offset=0&mode=filtered" % tid)
    out["log_head"] = (log.get("text") or "")[:600]
except Exception as e:
    out["detail_err"] = str(e)
print("RESULT", json.dumps(out, ensure_ascii=False, indent=1), flush=True)
