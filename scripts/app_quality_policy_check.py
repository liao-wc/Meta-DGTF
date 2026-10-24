
# -*- coding: utf-8 -*-
"""质量策略 cmd 检查：stable/web/verified 创建后立即读 cmd 并取消。"""
from __future__ import annotations
import json, ssl, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TOK = (ROOT / "dgtf_memory/.access_token").read_text(encoding="utf-8").strip()
CTX = ssl._create_unverified_context(); BASE = "https://127.0.0.1:8765"
def req(path, data=None, method=None):
    url = BASE + path + ("?t=" + TOK if "?" not in path else "&t=" + TOK)
    h = {"Content-Type": "application/json; charset=utf-8", "X-DGTF-Token": TOK}
    body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=30, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))
for policy in ("stable", "web", "verified"):
    try:
        c = req("/api/tasks", {"question": "1+1等于几？",
                               "opts": {"quality_policy": policy, "timeout_s": 1800}})
        tid = c.get("id")
        time.sleep(1.2)
        d = req("/api/tasks/" + str(tid))
        cmd = d.get("cmd") or []
        flags = {str(cmd[i]): cmd[i + 1] for i in range(len(cmd) - 1)
                 if str(cmd[i]).startswith("--")}
        has_ctx = any("项目权威背景" in str(x) for x in cmd)
        print(policy, "id", tid, "web", flags.get("--web"), "parallel", flags.get("--parallel"),
              "behavior_fusion", flags.get("--behavior-fusion"),
              "rounds", flags.get("--rounds"), "ctx", has_ctx,
              "fused", (c.get("mode_fusion") or {}).get("grounding_web"))
        req("/api/tasks/" + str(tid) + "/cancel", {}, method="POST")
    except Exception as e:
        print(policy, "ERR", e)
