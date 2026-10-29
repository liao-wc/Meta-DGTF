# -*- coding: utf-8 -*-
"""[V2.2.28] 有界 A/B：dual_judge cache vs llm（同题同 route/rounds/预算）。

两臂均 balance=3（warn 档、阶段路由会选 dual_judge=cache）；A 臂显式 dual_judge_mode=llm
作为对照。比较 tokens/calls/quality；max_tokens=150000 硬上限，总成本 <= ¥0.2。
证据：docs/dynamic_dual_judge_ab_20261029.json
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
SAVE = ROOT / "outputs" / "_e2e_local" / "dual_judge_ab"
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


def _free_port(prefer=8815):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def run_arm(tag, extra_opts):
    port = _free_port()
    assert port
    token = "djab_%s_%d" % (tag, os.getpid())
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
        with (AUD / ("djab_%s.out.log" % tag)).open("w", encoding="utf-8") as fo, \
                (AUD / ("djab_%s.err.log" % tag)).open("w", encoding="utf-8") as fe:
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
        opts = {"mock": False, "timeout_s": 600, "route": "0",
                "rounds": "0:1", "web": "off", "max_tokens": 150000,
                "overrides": {"output.save_dir": "outputs/_e2e_local/dual_judge_ab",
                              "web_search.enabled": False}}
        opts.update(extra_opts)
        body = {"question": QUESTION, "mode": "auto", "opts": opts}
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
        return {"arm": tag, "status": status, "wall_s": wall,
                "opts_extra": extra_opts,
                "mode": {k: mode.get(k) for k in
                         ("id", "tier", "engine_mode", "dual_judge_mode")},
                "plan_djm": plan.get("dual_judge_mode"),
                "dynamic_apply": ((plan.get("dynamic_opt") or {}).get("applied") or {}),
                "actual": {"calls": d.get("llm_calls"),
                           "tokens": d.get("llm_tokens"),
                           "cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
                           "quality": (d.get("quality") or {}).get("answer_quality")},
                "packed": Path(new[0]).name if new else ""}
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


def main():
    rows = [run_arm("A-cache", {}),
            run_arm("B-llm", {"dual_judge_mode": "llm"})]
    cache = rows[0].get("actual") or {}
    llm = rows[1].get("actual") or {}
    out = {"schema": "metadgtf.dual_judge_ab.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": QUESTION,
           "fixed": {"route": "0", "rounds": "0:1", "web": "off",
                     "balance_assumed": 3.0, "max_tokens": 150000},
           "arms": rows,
           "delta": {"tokens": (cache.get("tokens") or 0) - (llm.get("tokens") or 0),
                     "calls": (cache.get("calls") or 0) - (llm.get("calls") or 0),
                     "cost_cny": round((cache.get("cost_cny") or 0)
                                       - (llm.get("cost_cny") or 0), 3)},
           "note": "负值= cache 臂更省；单题单次，仅供动态依赖方向校准"}
    (ROOT / "docs" / "dynamic_dual_judge_ab_20261029.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(json.dumps({k: r.get(k) for k in ("arm", "status", "mode",
                                                "plan_djm", "actual")},
                         ensure_ascii=False)[:700])
    print("delta:", json.dumps(out["delta"], ensure_ascii=False))
    print("evidence -> docs/dynamic_dual_judge_ab_20261029.json")
    bad = [r for r in rows if r.get("error") or r.get("status") != "done"]
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
