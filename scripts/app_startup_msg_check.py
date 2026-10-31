#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App 启动文案检查（V2.2.113）。

起一个临时 App 实例（随机端口/no-agent/关闭 watchdog），抓启动日志里的
「V2 自动策略：…」行，要求显示「冻结（原因）」而非「无样本，跳过」。
证据 → docs/app_startup_msg_latest.json；退出码 0=符合预期。
用法：python scripts/app_startup_msg_check.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "_lead_audit" / "app_startup_msg.out.txt"
EVID = ROOT / "docs" / "app_startup_msg_latest.json"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return int(p)


def _app_version() -> str:
    for ln in (ROOT / "dgtf_app" / "server.py").read_text(encoding="utf-8").splitlines():
        if "APP_VERSION" in ln and "=" in ln:
            return ln.split("=", 1)[1].strip().strip(chr(34))
    return ""


def main() -> int:
    port = _free_port()
    token = "startupmsg_check"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               DGTF_ACCESS_TOKEN=token)
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    line = ""
    proc = None
    try:
        with OUT.open("w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fh,
                                    stderr=subprocess.STDOUT, env=env)
            deadline = time.time() + 90
            while time.time() < deadline:
                time.sleep(1.0)
                txt = OUT.read_text(encoding="utf-8", errors="replace")
                for ln in txt.splitlines():
                    if "V2 自动策略" in ln:
                        line = ln.strip()
                        break
                if line:
                    break
                if proc.poll() is not None:
                    break
    finally:
        if proc is not None and proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
    ev = {"schema": "dgtf.app_startup_msg.v1",
          "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
          "app_version": _app_version(), "matched": line,
          "expect_contains": "冻结", "ok": ("冻结" in line)}
    EVID.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    return 0 if ev["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
