# -*- coding: utf-8 -*-
"""[V2.2.35] reasoning 高圈省层 A/B：route0 vs full，rounds=2/层（总 8 圈）。

目的：短跑锚点只覆盖总圈数<=4；高圈 reasoning 的成本估算仍走可加模型（可能偏差大）。
本 A/B 给高圈锚点：route0 2 圈 vs full 2 圈各 1 次。
成本：约 ¥0.45（max_tokens=150000/跑）；证据 docs/route_reasoning_rounds2_ab_20261029.json
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
SAVE = ROOT / "outputs" / "_e2e_local" / "reasoning_r2"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
QUESTION = "为什么城市热岛效应在夜间比白天更明显？"
ARMS = [
    ("A-route0-r2", "0", "0:2"),
    ("B-full-r2", "0,1,both,all", "0:2,1:2,both:2,all:2"),
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


def _free_port(prefer=8823):
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
    token = "rr2_%d" % os.getpid()
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
        with (AUD / "rr2.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "rr2.err.log").open("w", encoding="utf-8") as fe:
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
        for tag, route, rounds in ARMS:
            before = set(glob.glob(str(SAVE / "*.packed.json")))
            body = {"question": QUESTION, "mode": "auto",
                    "opts": {"mock": False, "timeout_s": 900,
                             "route": route, "rounds": rounds,
                             "max_tokens": 150000,
                             "overrides": {"output.save_dir": "outputs/_e2e_local/reasoning_r2"}}}
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
            rows.append({"arm": tag, "route": route, "rounds": rounds,
                         "status": status, "wall_s": wall,
                         "calls": d.get("llm_calls"), "tokens": d.get("llm_tokens"),
                         "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
                         "answer_quality": q.get("answer_quality"),
                         "answer_ready": q.get("answer_ready"),
                         "packed": Path(new[0]).name if new else ""})
            print("[r2]", json.dumps(rows[-1], ensure_ascii=False)[:400], flush=True)
        out = {"schema": "metadgtf.route_reasoning_rounds2_ab.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "question": QUESTION, "kind": "reasoning",
               "fixed": {"rounds": "2/层（总 8 圈）", "web": "auto(off)",
                         "balance_assumed": 50.0, "max_tokens": 150000},
               "rows": rows,
               "note": "高圈 reasoning 省层/成本锚点（route0 vs full）；单次采样"}
        (ROOT / "docs" / "route_reasoning_rounds2_ab_20261029.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("evidence -> docs/route_reasoning_rounds2_ab_20261029.json")
        bad = [x for x in rows if x.get("status") != "done"]
        raise SystemExit(1 if bad else 0)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
