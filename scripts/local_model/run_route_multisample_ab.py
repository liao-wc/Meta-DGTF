# -*- coding: utf-8 -*-
"""[V2.2.31] 层子集质量多样本 A/B：route0 / route0,1 / full，各 2 次（同题）。

目的：单题单次方差大（上轮 A verified、B needs_evidence）；用 2 reps ×3 arms 看
verified/answer_ready/tokens 分布，为"是否可安全省层"提供更稳证据。
成本：约 ¥0.8（每臂 max_tokens=150000）；证据 docs/route_subset_multisample_20261029.json
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
SAVE = ROOT / "outputs" / "_e2e_local" / "route_multi"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
QUESTION = "成年人正常心率是多少次每分钟？"
ARMS = [
    ("A-route0", "0", "0:1"),
    ("B-route01", "0,1", "0:1,1:1"),
    ("C-full", "0,1,both,all", "0:1,1:1,both:1,all:1"),
]
REPS = 2


def _req(url, token, data=None, timeout=60):
    h = {"Content-Type": "application/json; charset=utf-8",
         "Cookie": "dgtf_token=" + str(token)}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
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


def _free_port(prefer=8819):
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
    assert port
    token = "rm_%d" % os.getpid()
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
        with (AUD / "rm.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "rm.err.log").open("w", encoding="utf-8") as fe:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo, stderr=fe, env=env)
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
        for rep in range(1, REPS + 1):
            for tag, route, rounds in ARMS:
                before = set(glob.glob(str(SAVE / "*.packed.json")))
                body = {"question": QUESTION, "mode": "auto",
                        "opts": {"mock": False, "timeout_s": 900,
                                 "route": route, "rounds": rounds,
                                 "max_tokens": 150000,
                                 "overrides": {"output.save_dir": "outputs/_e2e_local/route_multi"}}}
                t0 = time.time()
                s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
                tid = str((r1 or {}).get("id") or "")
                status, last = "", {}
                deadline = time.time() + 900
                while time.time() < deadline:
                    try:
                        _s, last = _req(base + "/api/tasks/" + tid, token, timeout=30)
                        status = str((last or {}).get("status") or "")
                    except Exception:  # noqa: BLE001
                        pass
                    if status in ("done", "error", "cancelled"):
                        break
                    time.sleep(2.0)
                wall = round(time.time() - t0, 1)
                new = [p for p in glob.glob(str(SAVE / "*.packed.json")) if p not in before]
                d = {}
                if new:
                    d = json.loads(Path(sorted(new, key=os.path.getmtime)[-1])
                                   .read_text(encoding="utf-8", errors="replace"))
                q = d.get("quality") or {}
                rows.append({"arm": tag, "rep": rep, "route": route,
                             "rounds": rounds, "status": status, "wall_s": wall,
                             "calls": d.get("llm_calls"),
                             "tokens": d.get("llm_tokens"),
                             "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
                             "answer_quality": q.get("answer_quality"),
                             "answer_ready": q.get("answer_ready"),
                             "packed": Path(new[0]).name if new else ""})
                print("[multi]", json.dumps(rows[-1], ensure_ascii=False)[:400], flush=True)
        summary = {}
        for tag, _, _ in ARMS:
            rs = [x for x in rows if x["arm"] == tag]
            summary[tag] = {
                "n": len(rs),
                "verified": sum(1 for x in rs if x.get("answer_quality") == "verified"),
                "ready": sum(1 for x in rs if x.get("answer_ready") is True),
                "tokens_med": sorted([x.get("tokens") or 0 for x in rs])[len(rs)//2]
                              if rs else 0,
                "cost_total": round(sum(x.get("cost_cny") or 0 for x in rs), 3),
            }
        out = {"schema": "metadgtf.route_subset_multisample.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "question": QUESTION,
               "fixed": {"rounds": "1", "web": "on(事实题强制)", "balance_assumed": 50.0,
                         "max_tokens": 150000, "reps": REPS},
               "rows": rows, "summary": summary,
               "note": "同一问题重复采样；verified/ready 计数 + tokens 中位；成本约 ¥0.8"}
        (ROOT / "docs" / "route_subset_multisample_20261029.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("summary:", json.dumps(summary, ensure_ascii=False))
        print("evidence -> docs/route_subset_multisample_20261029.json")
        bad = [x for x in rows if x.get("status") != "done"]
        raise SystemExit(1 if bad else 0)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
