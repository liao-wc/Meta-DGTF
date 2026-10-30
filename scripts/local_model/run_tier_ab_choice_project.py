# -*- coding: utf-8 -*-
"""[V2.2.77] choice/project tier A/B（真 API，约 ¥0.5）：quality vs fast 同题。

补 tier_advice 证据空白：reasoning 已有 A/B，choice/project 的 verified=0 题型
是否也能用 fast 省成本且质量不劣。证据 docs/tier_advice_choice_project_ab_20261030.json
"""
from __future__ import annotations

import glob
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVE = ROOT / "outputs" / "_e2e_local" / "tier_cp"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)

CASES = [
    ("choice", "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气",
     {"web": "on", "route": "0,1,both,all", "rounds": "0:1,1:1,both:1,all:1"}),
    ("project", "Meta-DGTF 道生三阶模型的项目当前状态如何？",
     {"web": "off", "route": "0,1,both,all", "rounds": "0:1,1:1,both:1,all:1"}),
]
ARMS = [("A-quality", "daosheng"), ("B-fast", "daosheng_fast")]


def _req(url, token, data=None, timeout=60):
    h = {"Content-Type": "application/json; charset=utf-8",
         "Cookie": "dgtf_token=" + str(token)}
    body = (json.dumps(data, ensure_ascii=False).encode("utf-8")
            if data is not None else None)
    r = urllib.request.Request(url, data=body, headers=h,
                               method="POST" if body is not None else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))


def _kill(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        pass


def _free_port(prefer=8839):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def main():
    port = _free_port()
    token = "tcp_%d" % os.getpid()
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token,
                "DGTF_DAOSHENG_BALANCE_CNY": "50.0"})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    proc = None
    rows = []
    try:
        with (AUD / "tcp.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "tcp.err.log").open("w", encoding="utf-8") as fe:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo,
                                    stderr=fe, env=env)
        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                s, _ = _req(base + "/api/health?t=" + token, token, timeout=3)
                if s == 200:
                    ready = True
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1.0)
        if not ready:
            raise SystemExit("server not ready")
        for kind, question, fixed in CASES:
            for tag, mode in ARMS:
                before = set(glob.glob(str(SAVE / "*.packed.json")))
                body = {"question": question, "mode": mode,
                        "opts": {"mock": False, "timeout_s": 1200,
                                 "route": fixed["route"],
                                 "rounds": fixed["rounds"],
                                 "web": fixed["web"], "max_tokens": 150000,
                                 "no_cache": True, "use_cache": False,
                                 "use_semantic_cache": False,
                                 "overrides": {
                                     "output.save_dir":
                                         "outputs/_e2e_local/tier_cp"}}}
                t0 = time.time()
                s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
                tid = str((r1 or {}).get("id") or "")
                status, last = "", {}
                deadline = time.time() + 1200
                while time.time() < deadline:
                    try:
                        _s, last = _req(base + "/api/tasks/" + tid, token,
                                        timeout=30)
                        status = str((last or {}).get("status") or "")
                    except Exception:  # noqa: BLE001
                        pass
                    if status in ("done", "error", "cancelled"):
                        break
                    time.sleep(2.0)
                wall = round(time.time() - t0, 1)
                new = [p for p in glob.glob(str(SAVE / "*.packed.json"))
                       if p not in before]
                d = {}
                if new:
                    d = json.loads(Path(sorted(new,
                                               key=os.path.getmtime)[-1])
                                   .read_text(encoding="utf-8",
                                              errors="replace"))
                q = d.get("quality") or {}
                plan = ((last.get("mode") or {}).get("plan") or {})
                rows.append({
                    "kind": kind, "arm": tag, "mode": mode,
                    "status": status,
                    "tier": (last.get("mode") or {}).get("tier"),
                    "engine_mode": (last.get("mode") or {}).get("engine_mode"),
                    "wall_s": wall, "calls": d.get("llm_calls"),
                    "tokens": d.get("llm_tokens"),
                    "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0,
                                      3),
                    "answer_quality": q.get("answer_quality"),
                    "answer_ready": q.get("answer_ready"),
                    "reason": str(q.get("answer_ready_reason") or "")[:160],
                    "tier_advice": (plan.get("quality_retry") or {}
                                    ).get("tier_advice"),
                    "packed": Path(new[0]).name if new else "",
                })
                print("[tcp]", json.dumps(rows[-1], ensure_ascii=False)[:520],
                      flush=True)
        out = {"schema": "metadgtf.tier_advice_choice_project_ab.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "fixed": {"balance_assumed": 50.0, "max_tokens": 150000,
                         "route": "full", "rounds": "1/层"},
               "rows": rows,
               "note": "choice/project tier A/B：quality vs fast 同题"}
        (ROOT / "docs" / "tier_advice_choice_project_ab_20261030.json"
         ).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                      encoding="utf-8")
        print("evidence -> docs/tier_advice_choice_project_ab_20261030.json")
        bad = [x for x in rows if x.get("status") != "done"]
        raise SystemExit(1 if bad else 0)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
