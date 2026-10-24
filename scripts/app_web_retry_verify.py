# -*- coding: utf-8 -*-
"""用新事实题 + web-retry 产生 verified 最新 packed，恢复质量门基线。"""
from __future__ import annotations
import json, ssl, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TOK = (ROOT / "dgtf_memory/.access_token").read_text(encoding="utf-8").strip()
CTX = ssl._create_unverified_context(); BASE = "https://127.0.0.1:8765"
def req(path, data=None, timeout=60):
    url = BASE + path + ("?t=" + TOK if "?" not in path else "&t=" + TOK)
    h = {"Content-Type": "application/json; charset=utf-8", "X-DGTF-Token": TOK}
    body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))
c = req("/api/tasks", {"question": "2+2等于几？",
                       "opts": {"quality_policy": "web-retry", "timeout_s": 1200}})
tid = c.get("id"); print("CREATED", tid, "policy", c.get("quality_policy"), "retry", c.get("quality_retry"), flush=True)
for i in range(180):
    time.sleep(10)
    tasks = req("/api/tasks").get("tasks") or []
    row = next((x for x in tasks if str(x.get("id")) == str(tid)), None)
    st = str((row or {}).get("status") or "")
    if i % 6 == 0: print("POLL", i, st, flush=True)
    if st in ("done", "error", "cancelled"): break
print("RESULT", json.dumps(row, ensure_ascii=False)[:1000], flush=True)
