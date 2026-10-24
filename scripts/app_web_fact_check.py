# -*- coding: utf-8 -*-
"""通用事实任务 + 官方联网：验证是否能以可接受墙钟拿到 verified。"""
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
t0=time.perf_counter()
created=req("/api/tasks", {"question":"1+1等于几？",
                           "opts":{"timeout_s":1200,"web":"on"}})
tid=created.get("id"); print("CREATED", json.dumps({k:created.get(k) for k in ("id","mode_fusion")},ensure_ascii=False),flush=True)
last=None
for i in range(150):
    time.sleep(10)
    try:
        tasks=req("/api/tasks"); row=next((x for x in (tasks.get("tasks") or []) if str(x.get("id"))==str(tid)),None); last=row
        st=str((row or {}).get("status") or "")
        if i%3==0: print("POLL",i,st,round(time.perf_counter()-t0,1),flush=True)
        if st in ("done","error","cancelled"): break
    except Exception as e: print("POLL_ERR",e,flush=True)
print("RESULT", json.dumps({"created":created.get("mode_fusion"),"task":last,"elapsed_s":round(time.perf_counter()-t0,1)},ensure_ascii=False,indent=1),flush=True)
