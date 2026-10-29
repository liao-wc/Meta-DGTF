# -*- coding: utf-8 -*-
"""[V2.2.43] 质量门未验证 -> 加圈重试是否有用：fact 题 rounds=1 vs rounds=2（真 API）。

目的：回答"unverified 能否通过加圈/重试改善"（决定是否实现动态 quality retry）。
两臂各 1 次；max_tokens=150000；证据 docs/quality_retry_ab_20261029.json
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
SAVE = ROOT / "outputs" / "_e2e_local" / "quality_retry"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
QUESTION = "HTTP 404 状态码表示什么？"
ARMS = [
    ("A-rounds1", "0:1,1:1,both:1,all:1"),
    ("B-rounds2", "0:2,1:2,both:2,all:2"),
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


def _free_port(prefer=8831):
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
    token = "qrt_%d" % os.getpid()
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
        with (AUD / "qrt.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "qrt.err.log").open("w", encoding="utf-8") as fe:
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
        for tag, rounds in ARMS:
            before = set(glob.glob(str(SAVE / "*.packed.json")))
            body = {"question": QUESTION, "mode": "auto",
                    "opts": {"mock": False, "timeout_s": 1200,
                             "route": "0,1,both,all", "rounds": rounds,
                             "web": "on", "max_tokens": 150000,
                             "overrides": {
                                 "output.save_dir": "outputs/_e2e_local/quality_retry"}}}
            t0 = time.time()
            s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
            tid = str((r1 or {}).get("id") or "")
            status, last = "", {}
            deadline = time.time() + 1200
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
            rows.append({"arm": tag, "rounds": rounds, "status": status,
                         "wall_s": wall, "calls": d.get("llm_calls"),
                         "tokens": d.get("llm_tokens"),
                         "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
                         "answer_quality": q.get("answer_quality"),
                         "answer_ready": q.get("answer_ready"),
                         "coverage": q.get("coverage"),
                         "packed": Path(new[0]).name if new else ""})
            print("[qrt]", json.dumps(rows[-1], ensure_ascii=False)[:450], flush=True)
        out = {"schema": "metadgtf.quality_retry_ab.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "question": QUESTION, "kind": "fact",
               "fixed": {"route": "full", "web": "on", "balance_assumed": 50.0,
                         "max_tokens": 150000},
               "rows": rows,
               "note": "验证 unverified 是否能靠加圈/重试改善；决定是否实现动态 quality retry"}
        (ROOT / "docs" / "quality_retry_ab_20261029.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("evidence -> docs/quality_retry_ab_20261029.json")
        bad = [x for x in rows if x.get("status") != "done"]
        raise SystemExit(1 if bad else 0)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
