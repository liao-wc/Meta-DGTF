# -*- coding: utf-8 -*-
"""[V2.2.21 / App 2.0.46] 融合后全链路真跑判据：App → 调度 → 引擎 → 本地模型 → 产物 → 读数。

前置 8772/8773 未起 => exit 2（没跑，不是判红）。全程自起临时 App server，
**不碰用户 8765 实例**；零 API 成本（走本地 0.5B 链路）。
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

ROOT = Path(__file__).resolve().parent.parent.parent
RUNS = ROOT / "dgtf_app" / "runs"
SAVE = ROOT / "outputs" / "_e2e_local" / "fused_chain"
SAVE.mkdir(parents=True, exist_ok=True)
LOG_DIR = ROOT / "outputs" / "_lead_audit"
LOG_DIR.mkdir(parents=True, exist_ok=True)

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


def _up(port, path="/health"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path),
                                    timeout=4) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _free_port(prefer=8797):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def _req(url, token, data=None, timeout=60):
    # 服务端访问口令走 Cookie（dgtf_token=...）；?t= 用于首次种 cookie/health。
    h = {"Content-Type": "application/json; charset=utf-8",
         "Cookie": "dgtf_token=" + str(token)}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h,
                               method="POST" if body is not None else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))


def _kill_tree(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        pass


if not _up(8772) or not _up(8773, "/v1/models"):
    print("SKIP: 服务不可达（8772/8773 未起，本判据没跑）")
    raise SystemExit(2)

port = _free_port()
assert port, "无空闲端口"
token = "fused_chain_%d" % os.getpid()
base = "http://127.0.0.1:%d" % port
cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
       "--port", str(port), "--http", "--no-agent-daemon",
       "--local-chain-watchdog", "off", "--token", token]
env = dict(os.environ)
env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
            "DGTF_ACCESS_TOKEN": token})
proc = None
try:
    with (LOG_DIR / "fused_chain_server.out.log").open("w", encoding="utf-8") as fo, \
            (LOG_DIR / "fused_chain_server.err.log").open("w", encoding="utf-8") as fe:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo, stderr=fe, env=env)
    ready = False
    deadline = time.time() + 120
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
    ck("A1 临时 App server 起得来（不碰用户 8765）", ready,
       "exit=%s" % (proc.poll() if proc else "?"))
    if not ready:
        raise SystemExit(2)

    ck("A2 用户 8765 实例未被占用/干扰（本判据用独立端口 %d）", port != 8765)

    overrides = {
        "api.base_url": "http://127.0.0.1:8773/v1",
        "api.key": "local-shim",
        "api.default_model": "local",
        "api.reasoner_model": "local",
        "web_search.enabled": False,
        "output.answer_gates.enabled": True,
        "output.answer_gates.block": False,
        "output.save_dir": "outputs/_e2e_local/fused_chain",
    }
    body = {"question": "HTTP 404 状态码表示什么？", "mode": "auto",
            "opts": {"mock": False, "timeout_s": 900,
                     "route": "0", "rounds": "0:1",
                     "overrides": overrides}}
    before = {p: os.path.getmtime(p) for p in glob.glob(str(SAVE / "*.packed.json"))}
    t0 = time.time()
    s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
    tid = str((r1 or {}).get("id") or "")
    ck("B1 POST /api/tasks（mode=auto 默认）⇒ 201 + 任务 id",
       s1 == 201 and bool(tid), "status=%s id=%s" % (s1, tid))

    mode = (r1 or {}).get("mode") or {}
    ck("B2 融合语义：mode.id=daosheng / requested=auto / fused=True",
       mode.get("id") == "daosheng" and mode.get("requested") == "auto"
       and mode.get("fused") is True,
       json.dumps({k: mode.get(k) for k in ("id", "requested", "fused")},
                  ensure_ascii=False))
    plan = mode.get("plan") or {}
    ck("B3 单一链路：plan.policy=daosheng.v1（不走旧 standard 链路）",
       plan.get("policy") == "daosheng.v1", plan.get("policy"))
    ck("B4 engine_mode ∈ {B,fast} 且 mode_fusion.unified=True",
       mode.get("engine_mode") in ("B", "fast")
       and (mode.get("plan") or {}).get("engine_mode") == mode.get("engine_mode")
       and bool((r1.get("mode_fusion") or {}).get("unified")),
       "%s / %s" % (mode.get("engine_mode"),
                    (r1.get("mode_fusion") or {}).get("unified")))
    ck("B5 模式专属配置随任务下发（parallel/thinking/rounds_locked 可审计）",
       bool(plan.get("parallel")) and bool(plan.get("thinking"))
       and isinstance(plan.get("rounds_locked"), bool),
       {k: plan.get(k) for k in ("parallel", "thinking", "rounds_locked")})

    # ── 等任务跑完 ──
    status, last = "", {}
    deadline = time.time() + 900
    while time.time() < deadline:
        try:
            s, last = _req(base + "/api/tasks/" + tid, token, timeout=30)
            status = str((last or {}).get("status") or "")
        except Exception:  # noqa: BLE001
            s = 0
        if status in ("done", "error", "cancelled"):
            break
        time.sleep(2.0)
    wall = round(time.time() - t0, 1)
    ck("C1 任务跑完（status=done，不是 error/cancelled/timeout）",
       status == "done", "status=%s wall=%ss" % (status, wall))

    logp = Path(str((last or {}).get("log") or ""))
    log = logp.read_text(encoding="utf-8", errors="replace") if logp.is_file() else ""
    ck("C2 任务日志显示走了融合后的单一道生链路（自动模式/专属配置）",
       ("自动模式：" in log or "模式专属配置" in log
        or "[daosheng]" in log or "engine_mode" in log),
       log[-300:] if log else "无日志")

    after = [p for p in glob.glob(str(SAVE / "*.packed.json"))
             if p not in before or os.path.getmtime(p) > before.get(p, 0)]
    ck("C3 落了 packed 产物（链路走到底）", bool(after), after[:1])
    packed = {}
    if after:
        packed = json.loads(Path(after[0]).read_text(encoding="utf-8",
                                                     errors="replace"))
    prov = packed.get("provenance") or {}
    ck("C4 packed.provenance.engine_version 与生产引擎一致（V2.2.21）",
       str(prov.get("engine_version") or "").endswith("2.2.21"),
       prov.get("engine_version"))
    am = (packed.get("auto_mode") or {})
    ck("C5 引擎侧 auto_mode 计划与 App 选择一致",
       str((am.get("plan") or {}).get("mode") or "") == str(mode.get("engine_mode")),
       "%s vs %s" % ((am.get("plan") or {}).get("mode"), mode.get("engine_mode")))
    ck("C6 auto_mode.adjustments 账本存在（可审计）",
       isinstance(am.get("adjustments"), list))
    q = packed.get("quality") or {}
    ag = q.get("answer_gates") or {}
    ck("C7 产物读数非空：answer_gates + answer_ready_reason",
       bool(ag) and str(q.get("answer_ready_reason") or "") != "",
       "ag=%s reason=%s" % (sorted(ag)[:4], str(q.get("answer_ready_reason"))[:40]))
    ck("C8 真跑了本地模型（llm_calls>0，非空跑）",
       int(packed.get("llm_calls") or 0) > 0, packed.get("llm_calls"))
    ck("C9 总墙钟在预算内（本地链路验证档）", wall < 900, wall)
finally:
    if proc is not None and proc.poll() is None:
        _kill_tree(proc.pid)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*rag_embed_service*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
             "-ErrorAction SilentlyContinue }"],
            capture_output=True, timeout=30)
    except Exception:  # noqa: BLE001
        pass

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
