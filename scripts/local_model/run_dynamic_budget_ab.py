# -*- coding: utf-8 -*-
"""[V2.2.25] 剩余预算有界 A/B：同一任务在两条预算下的动态配置决策 + 真实成本校准。

A 臂：余额假设 ¥50（ok 档）→ 期望 quality 档（B 引擎模式）
B 臂：余额假设 ¥3（warn 档）→ 期望 fast 档 + 低圈
两臂同题、同 route=0/rounds=0:1（显式，锁定圈数），只观察动态配置决策差异与真实 tokens。
成本有界：两臂合计 token 上限 150k/臂，预计 <= ¥0.5。
证据：docs/dynamic_budget_ab_20261029.json（不写入生产质量统计）。
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
SAVE = ROOT / "outputs" / "_e2e_local" / "dynamic_ab"
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


def _free_port(prefer=8811):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def run_arm(balance, tag):
    port = _free_port()
    assert port, "no free port"
    token = "dynab_%s_%d" % (tag, os.getpid())
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token,
                "DGTF_DAOSHENG_BALANCE_CNY": str(balance)})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    proc = None
    try:
        with (AUD / ("dynab_%s.out.log" % tag)).open("w", encoding="utf-8") as fo, \
                (AUD / ("dynab_%s.err.log" % tag)).open("w", encoding="utf-8") as fe:
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
            return {"tag": tag, "error": "server not ready", "exit": proc.poll()}

        before = set(glob.glob(str(SAVE / "*.packed.json")))
        body = {"question": QUESTION, "mode": "auto",
                "opts": {"mock": False, "timeout_s": 600,
                         "route": "0", "rounds": "0:1", "max_tokens": 150000,
                         "overrides": {
                             "output.save_dir": "outputs/_e2e_local/dynamic_ab",
                             "web_search.enabled": False}}}
        t0 = time.time()
        s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
        tid = str((r1 or {}).get("id") or "")
        if s1 != 201 or not tid:
            return {"tag": tag, "error": "POST failed", "status": s1, "body": r1}
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
        mode = (last.get("mode") or {})
        plan = mode.get("plan") or {}
        dyn = plan.get("dynamic_opt") or {}
        new = [p for p in glob.glob(str(SAVE / "*.packed.json")) if p not in before]
        packed = {}
        if new:
            packed = json.loads(Path(sorted(new, key=os.path.getmtime)[-1])
                                .read_text(encoding="utf-8", errors="replace"))
        tokens = int(packed.get("llm_tokens") or 0)
        return {"tag": tag, "balance_assumed": balance, "task_id": tid,
                "status": status, "wall_s": wall,
                "mode": {k: mode.get(k) for k in ("id", "requested", "tier",
                                                  "engine_mode", "rounds",
                                                  "rounds_locked")},
                "budget": plan.get("budget_guard") or {},
                "dynamic_opt": {k: dyn.get(k) for k in
                                ("budget_level", "balance_cny", "route",
                                 "cache_hit", "chosen", "applied", "fallback", "why")},
                "actual": {"llm_calls": packed.get("llm_calls"), "tokens": tokens,
                           "est_cost_cny": round(tokens / 1e6 * 2.0, 3),
                           "answer_quality": (packed.get("quality") or {}).get("answer_quality")},
                "packed": Path(new[0]).name if new else ""}
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


def main():
    results = []
    for balance, tag in ((50.0, "A-ok"), (3.0, "B-warn")):
        print("[AB] arm", tag, "balance", balance, flush=True)
        results.append(run_arm(balance, tag))
    out = {"schema": "metadgtf.dynamic_budget_ab.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": QUESTION,
           "fixed_opts": {"route": "0", "rounds": "0:1", "max_tokens": 150000,
                          "web_search.enabled": False},
           "arms": results,
           "note": "两臂同题同 route/rounds，仅预算不同；实际成本按 tokens×2.0/M 估"}
    (ROOT / "docs" / "dynamic_budget_ab_20261029.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in results:
        print(json.dumps({k: r.get(k) for k in
                          ("tag", "status", "mode", "dynamic_opt", "actual")},
                         ensure_ascii=False)[:900])
    print("evidence -> docs/dynamic_budget_ab_20261029.json")
    bad = [r for r in results if r.get("error") or r.get("status") != "done"]
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
