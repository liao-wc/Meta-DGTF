# -*- coding: utf-8 -*-
"""M4 真实任务参数落盘检查：创建 → 读 cmd → 立即取消。"""
from __future__ import annotations
import json, ssl, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOK = (ROOT / "dgtf_memory/.access_token").read_text(encoding="utf-8").strip()
CTX = ssl._create_unverified_context()
BASE = "https://127.0.0.1:8765"

def req(path, data=None, method=None, timeout=30):
    url = BASE + path + ("?t=" + TOK if "?" not in path else "&t=" + TOK)
    h = {"Content-Type": "application/json; charset=utf-8", "X-DGTF-Token": TOK}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))

created = req("/api/tasks", {"question": "1+1等于几？", "opts": {}})
tid = created.get("id")
print("CREATED", json.dumps({k: created.get(k) for k in ("id", "mode_fusion")},
                            ensure_ascii=False), flush=True)
time.sleep(1.5)
detail = req("/api/tasks/" + str(tid))
cmd = detail.get("cmd") or []
print("CMD", json.dumps(cmd, ensure_ascii=False, indent=1), flush=True)
out = {"id": tid, "mode_fusion": created.get("mode_fusion"), "cmd": cmd,
       "cmd_flags": {str(cmd[i]): cmd[i+1] for i in range(len(cmd)-1)
                     if str(cmd[i]).startswith("--")}}
try:
    req("/api/tasks/" + str(tid) + "/cancel", {}, method="POST")
    print("CANCELLED", flush=True)
except Exception as e:
    print("CANCEL_ERR", e, flush=True)
print("RESULT", json.dumps(out, ensure_ascii=False, indent=1), flush=True)
