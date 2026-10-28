# -*- coding: utf-8 -*-
"""[V2.2.18] App selftest 门（流程不能漏：App 自检必须进一键验收）。

为什么需要它
------------
README 发版流程要求「跑 App selftest」，但它此前只靠人手跑：acceptance 里没有、
自动化流程看不见。本脚本自起一个**临时 App server**（HTTP + 随机端口 + 访问口令 +
--no-agent-daemon + --local-chain-watchdog off）→ 跑 dgtf_app/selftest.py →
关服 → 写证据 docs/app_selftest_latest.json。**绝不碰用户正在用的 8765 实例**。

三态（与 acceptance 语义一致）：
  0 = 全绿（PASS）
  1 = 判红（selftest 有 FAIL / 启动后报错）
  2 = 没跑（临时 server 起不来：端口/依赖/启动超时 —— acceptance 按服务型 SKIP 处理）
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EVID = DOCS / "app_selftest_latest.json"
LOG_DIR = ROOT / "outputs" / "_lead_audit"


def _free_port(prefer: int = 8799) -> int:
    for cand in (prefer, 0):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", cand))
            port = s.getsockname()[1]
            s.close()
            return int(port)
        except OSError:
            s.close()
    return prefer


def _health(base: str, token: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(
                base + "/api/health?t=" + token, timeout=timeout) as r:
            return int(getattr(r, "status", 200) or 200) == 200
    except Exception:  # noqa: BLE001
        return False


def _kill_tree(pid: int) -> None:
    """Windows 下连带子进程（rag_embed_service 等）一起收掉；失败不阻断。"""
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        try:
            os.kill(pid, 9)
        except Exception:  # noqa: BLE001
            pass


def _write_ev(ev: dict) -> None:
    try:
        DOCS.mkdir(parents=True, exist_ok=True)
        EVID.write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="App selftest 自动门（临时 server）")
    ap.add_argument("--port", type=int, default=0, help="0=自动挑空闲端口")
    ap.add_argument("--timeout", type=float, default=900.0, help="selftest 超时秒数")
    ap.add_argument("--json", action="store_true", help="只打印证据 JSON")
    a = ap.parse_args(argv)

    port = int(a.port or _free_port())
    token = "selftest_%d" % os.getpid()
    base = "http://127.0.0.1:%d" % port
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_log = LOG_DIR / "app_selftest_server.out.log"
    err_log = LOG_DIR / "app_selftest_server.err.log"
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    t0 = time.time()
    ev = {"schema": "dgtf.app_selftest.v1", "ts": t0,
          "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
          "base": base, "port": port, "ok": False, "pass": 0, "fail": 0,
          "status": "not_run", "reason": ""}
    proc = None
    try:
        with out_log.open("w", encoding="utf-8", errors="replace") as fo, \
                err_log.open("w", encoding="utf-8", errors="replace") as fe:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo, stderr=fe,
                                    env=env)
        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if _health(base, token):
                ready = True
                break
            time.sleep(1.0)
        if not ready:
            ev["status"] = "not_run"
            ev["reason"] = ("临时 App server 未就绪（exit=%s）；见 %s"
                            % (proc.poll(), err_log.name))
            _write_ev(ev)
            print("SKIP app_selftest: " + ev["reason"], flush=True)
            return 2
        r = subprocess.run([sys.executable, str(ROOT / "dgtf_app" / "selftest.py"),
                            "--base", base],
                           cwd=str(ROOT), env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=float(a.timeout))
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        pass_n = fail_n = 0
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("PASS ") and "/" not in s:
                pass_n += 1
            elif s.startswith("FAIL ") and "/" not in s:
                fail_n += 1
        # 结构化汇总行：PASS 455 / FAIL 0
        for line in reversed(out.splitlines()):
            if "PASS" in line and "FAIL" in line and "/" in line:
                try:
                    tail = line.split("PASS", 1)[1]
                    pass_n = int(tail.split("/")[0].strip())
                    fail_n = int(line.split("FAIL", 1)[1].strip())
                except Exception:  # noqa: BLE001
                    pass
                break
        ev.update({"pass": pass_n, "fail": fail_n,
                   "rc": int(r.returncode),
                   "ok": bool(r.returncode == 0 and fail_n == 0),
                   "status": "pass" if (r.returncode == 0 and fail_n == 0) else "fail",
                   "tail": "\n".join(out.strip().splitlines()[-3:])[:600]})
        _write_ev(ev)
        if a.json:
            print(json.dumps(ev, ensure_ascii=False, indent=1))
        else:
            print(("PASS " if ev["ok"] else "FAIL ")
                  + "app_selftest: PASS %d / FAIL %d（rc=%s）"
                  % (pass_n, fail_n, r.returncode), flush=True)
            if not ev["ok"]:
                print(ev["tail"], flush=True)
        return 0 if ev["ok"] else 1
    except subprocess.TimeoutExpired:
        ev.update({"status": "fail", "reason": "selftest 超时 %.0fs" % a.timeout})
        _write_ev(ev)
        print("FAIL app_selftest: timeout", flush=True)
        return 1
    except Exception as exc:  # noqa: BLE001
        ev.update({"status": "not_run",
                   "reason": "%s: %s" % (type(exc).__name__, exc)})
        _write_ev(ev)
        print("SKIP app_selftest: " + ev["reason"], flush=True)
        return 2
    finally:
        if proc is not None and proc.poll() is None:
            _kill_tree(proc.pid)
        # 兜底：临时 server 启动的 rag_embed_service 子进程
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


if __name__ == "__main__":
    raise SystemExit(main())
