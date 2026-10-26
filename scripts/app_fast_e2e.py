# -*- coding: utf-8 -*-
"""App 端到端验证：道生 fast 成本档真实任务（Round 7，真跑一次）。

流程：起 App server（8768，真实非 mock）→ POST /api/tasks(mode=daosheng_fast)
→ 轮询任务 → 汇总 mode.plan / 引擎参数 / packed 指标 → 关 server → 写 JSON。
零额外依赖；结果落 outputs/_lead_audit/app_fast_e2e.json，供证据引用。
"""
from __future__ import annotations

import json
import os
import signal
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "_lead_audit" / (
    "app_fact_e2e.json" if len(sys.argv) > 2 and sys.argv[2] == "daosheng"
    else "app_fast_e2e.json")
TOKEN = "lead-e2e-token-7"
def _pick_port(explicit: str = "") -> str:
    import socket
    if explicit:
        return explicit
    for _p in range(8800, 8860):
        _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            _s.bind(("127.0.0.1", _p))
            _s.close()
            return str(_p)
        except OSError:
            _s.close()
    return "8768"


PORT = _pick_port(os.environ.get("DGTF_E2E_PORT") or "")
BASE = "http://127.0.0.1:" + PORT
QUESTION = (sys.argv[1] if len(sys.argv) > 1
            else "为什么城市热岛效应在夜间比白天更明显？")


def req(path, obj=None, timeout=15):
    url = BASE + path + ("&" if "?" in path else "?") + "t=" + TOKEN
    data = None if obj is None else json.dumps(obj).encode("utf-8")
    r = urllib.request.Request(url, data=data,
                               headers={"Content-Type": "application/json",
                                        "Cookie": "dgtf_token=" + TOKEN})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read().decode("utf-8", "replace"))


def main() -> int:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    log = open(ROOT / "outputs" / "_lead_audit" / "app_fast_e2e_server.log",
               "w", encoding="utf-8", errors="replace")
    srv = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
         "--port", PORT, "--http", "--token", TOKEN, "--no-agent-daemon"],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env)
    result = {"ok": False, "server_pid": srv.pid,
          "requested_mode": (sys.argv[2] if len(sys.argv) > 2
                             else "daosheng_fast")}
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                h = req("/api/health", timeout=3)
                if h:
                    result["health"] = h
                    break
            except Exception:  # noqa: BLE001
                time.sleep(2)
        else:
            result["error"] = "server 未 ready"
            return 1
        t0 = time.time()
        _mode = (sys.argv[2] if len(sys.argv) > 2 else "daosheng_fast")
        r = req("/api/tasks", {"question": QUESTION,
                               "mode": _mode, "opts": {}}, timeout=60)
        result["task_post_status"] = 201
        result["task_id"] = r.get("id") or r.get("task", {}).get("id")
        mode = r.get("mode") or (r.get("task") or {}).get("mode") or {}
        result["mode"] = mode
        plan = mode.get("plan") or {}
        result["plan_summary"] = {
            "tier": plan.get("tier"), "engine_mode": plan.get("engine_mode"),
            "parallel": plan.get("parallel"), "thinking": plan.get("thinking"),
            "web": plan.get("web"), "rounds": plan.get("rounds"),
            "scenario": (plan.get("scenario") or {}).get("kind"),
            "scenario_rec": (plan.get("scenario") or {}).get("mode"),
            "budget_decision": (plan.get("budget_guard") or {}).get("decision"),
            "reason": str(mode.get("reason") or plan.get("reason") or "")[:400],
        }
        tid = result["task_id"]
        last = {}
        deadline = time.time() + 1500
        while time.time() < deadline:
            time.sleep(10)
            try:
                t = req("/api/tasks/" + str(tid), timeout=20)
            except Exception as e:  # noqa: BLE001
                last = {"error": str(e)}
                continue
            task = t.get("task") or t
            last = task
            st = str(task.get("status") or "")
            if st in ("done", "failed", "error", "cancelled"):
                break
        _fields = ("id", "status", "tokens", "calls", "elapsed",
                   "quality", "answer_quality", "answer_ready", "error",
                   "packed", "output", "tok_tokens", "tok_calls",
                   "llm_tokens", "llm_calls", "answer_ready", "quality_score",
                   "elapsed_seconds", "run_id")
        result["task"] = {k: last.get(k) for k in _fields if k in last}
        result["elapsed_task_s"] = round(time.time() - t0, 1)
        # 从最新 packed 读质量/成本（先补 sys.path 再 import，否则 V2 模块找不到）
        try:
            sys.path.insert(0, str(ROOT / "dgtf_engine"))
            from dgtf_v2.pareto_flow import extract_flow_metrics as efm
            packs = sorted((ROOT / "outputs").glob("*.packed.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            if packs:
                d = json.loads(packs[0].read_text(encoding="utf-8",
                                                  errors="replace"))
                m = efm(d)
                result["packed"] = {"file": packs[0].name,
                                    "id": m.get("id"),
                                    "quality": m.get("quality"),
                                    "tokens": m.get("tokens"),
                                    "calls": m.get("calls"),
                                    "answer_quality": m.get("answer_quality"),
                                    "answer_ready": m.get("answer_ready"),
                                    "rounds": m.get("rounds")}
            result["ok"] = last.get("status") == "done"
        except Exception as e:  # noqa: BLE001
            result["packed_error"] = str(e)
    finally:
        try:
            srv.terminate()
            time.sleep(2)
            if srv.poll() is None:
                srv.kill()
        except Exception:  # noqa: BLE001
            pass
        log.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False)[:1200])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
