# -*- coding: utf-8 -*-
"""[V2.2.27] App 路径成本开销校准：1 臂有界云端实测（route=0/rounds=0:1/web off）。

目的：引擎 CLI 校准的 route 子集模型（31,620 tokens）在 App 全流程（自省/质量门/归档）
下会有额外 token 开销；本臂测 App 实际 tokens，得到 app_path_overhead 系数。
成本有界：max_tokens=150000，预计 <= ¥0.15。
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
SAVE = ROOT / "outputs" / "_e2e_local" / "app_cost_calib"
SAVE.mkdir(parents=True, exist_ok=True)
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
QUESTION = "成年人正常心率是多少次每分钟？"


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


def _free_port(prefer=8813):
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
    token = "appcal_%d" % os.getpid()
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token,
                "DGTF_DAOSHENG_BALANCE_CNY": "3.0"})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    proc = None
    try:
        with (AUD / "appcal.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "appcal.err.log").open("w", encoding="utf-8") as fe:
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
        before = set(glob.glob(str(SAVE / "*.packed.json")))
        body = {"question": QUESTION, "mode": "auto",
                "opts": {"mock": False, "timeout_s": 600,
                         "route": "0", "rounds": "0:1", "web": "off",
                         "max_tokens": 150000,
                         "overrides": {
                             "output.save_dir": "outputs/_e2e_local/app_cost_calib",
                             "web_search.enabled": False}}}
        t0 = time.time()
        s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
        tid = str((r1 or {}).get("id") or "")
        status, last = "", {}
        deadline = time.time() + 600
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
        mode = (last.get("mode") or {})
        plan = mode.get("plan") or {}
        model_tok = 31620.0  # _route_round_tokens("0","0:1","fast","off","fact")
        actual = int(d.get("llm_tokens") or 0)
        ratio = round(actual / model_tok, 3) if model_tok else None
        out = {"schema": "metadgtf.app_path_cost_calibration.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "question": QUESTION,
               "fixed": {"route": "0", "rounds": "0:1", "web": "off",
                         "mode": "auto", "balance_assumed": 3.0,
                         "max_tokens": 150000},
               "status": status, "wall_s": wall,
               "mode": {k: mode.get(k) for k in
                        ("id", "tier", "engine_mode", "rounds", "rounds_locked")},
               "dynamic_opt": plan.get("dynamic_opt") or {},
               "engine_model_tokens": model_tok,
               "actual": {"llm_calls": d.get("llm_calls"), "tokens": actual,
                          "est_cost_cny": round(actual / 1e6 * 2.0, 3),
                          "answer_quality": (d.get("quality") or {}).get("answer_quality")},
               "app_path_overhead": ratio,
               "packed": Path(new[0]).name if new else ""}
        (ROOT / "docs" / "app_path_cost_calibration_20261029.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False)[:1200])
        print("evidence -> docs/app_path_cost_calibration_20261029.json")
        if status != "done" or not actual:
            raise SystemExit(1)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
