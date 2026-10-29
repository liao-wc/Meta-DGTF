# -*- coding: utf-8 -*-
"""[V2.2.30] 层子集质量 A/B：route=0 vs route=0,1（事实题/web on/quality 档）。

目的：为"动态层子集"提供质量证据——省掉研究层是否影响 verified/质量。
两臂同题、同 rounds=1、web on、预算 50（ok 档）；max_tokens=150000 硬上限。
证据：docs/route_subset_quality_ab_20261029.json
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
SAVE = ROOT / "outputs" / "_e2e_local" / "route_quality_ab"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
QUESTION = "成年人正常心率是多少次每分钟？"
ARMS = [
    ("A-route0", "0", "0:1"),
    ("B-route01", "0,1", "0:1,1:1"),
]


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


def _free_port(prefer=8817):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def run_arm(tag, route, rounds):
    port = _free_port()
    assert port
    token = "rq_%s_%d" % (tag, os.getpid())
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token,
                "DGTF_DAOSHENG_BALANCE_CNY": "50.0"})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    proc = None
    try:
        with (AUD / ("rq_%s.out.log" % tag)).open("w", encoding="utf-8") as fo, \
                (AUD / ("rq_%s.err.log" % tag)).open("w", encoding="utf-8") as fe:
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
            return {"arm": tag, "error": "server not ready"}
        before = set(glob.glob(str(SAVE / "*.packed.json")))
        body = {"question": QUESTION, "mode": "auto",
                "opts": {"mock": False, "timeout_s": 900,
                         "route": route, "rounds": rounds,
                         "max_tokens": 150000,
                         "overrides": {"output.save_dir": "outputs/_e2e_local/route_quality_ab"}}}
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
        mode = (last.get("mode") or {})
        plan = mode.get("plan") or {}
        return {"arm": tag, "route": route, "rounds": rounds, "status": status,
                "wall_s": wall,
                "actual": {"calls": d.get("llm_calls"), "tokens": d.get("llm_tokens"),
                           "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
                           "answer_quality": q.get("answer_quality"),
                           "quality": d.get("answer_quality"),
                           "quality_flags": q.get("quality_flags"),
                           "answer_ready": q.get("answer_ready")},
                "plan": {"engine_mode": mode.get("engine_mode"),
                         "route": plan.get("route"),
                         "web": plan.get("web"),
                         "djm": plan.get("dual_judge_mode"),
                         "dynamic_route": (plan.get("dynamic_opt") or {}).get("route")},
                "packed": Path(new[0]).name if new else ""}
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


def main():
    rows = [run_arm(*a) for a in ARMS]
    out = {"schema": "metadgtf.route_subset_quality_ab.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": QUESTION,
           "fixed": {"rounds": "1", "web": "on(事实题强制)", "balance_assumed": 50.0,
                     "max_tokens": 150000},
           "arms": rows,
           "note": "比较省层（route=0）与多一层（0,1）对 verified/质量/tokens 的影响"}
    (ROOT / "docs" / "route_subset_quality_ab_20261029.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False)[:800])
    print("evidence -> docs/route_subset_quality_ab_20261029.json")
    bad = [r for r in rows if r.get("error") or r.get("status") != "done"]
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
