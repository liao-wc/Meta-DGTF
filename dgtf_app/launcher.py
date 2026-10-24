# -*- coding: utf-8 -*-
"""Meta-DGTF 个人工作台后台启动器（完全无 PowerShell）。

用法：
  pythonw dgtf_app/launcher.py --open       启动/复用 App 并打开浏览器
  pythonw dgtf_app/launcher.py --start      只启动/复用，不打开浏览器
  python dgtf_app/launcher.py --check       只检查健康（前台调试）

特点：
- 用 pythonw.exe 启动 server.py，DETACHED_PROCESS + CREATE_NO_WINDOW；
- 不调用 PowerShell / cmd，不产生控制台窗口；
- 健康检查走 127.0.0.1 + token，失败只写日志，不弹窗；
- 已有实例健康时直接复用。
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "dgtf_memory" / ".access_token"
SSL_CTX = ssl._create_unverified_context()


def read_token() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def health(port: int, timeout: float = 6.0) -> dict:
    token = read_token()
    url = f"https://127.0.0.1:{port}/api/health?t={token}"
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def is_ready(port: int) -> bool:
    return bool(health(port, timeout=6.0).get("ok"))


def open_url(port: int) -> None:
    token = read_token()
    if not token:
        return
    url = f"https://127.0.0.1:{port}/?t={token}"
    try:
        os.startfile(url)  # noqa: S606 - Windows 默认浏览器
    except Exception:
        import webbrowser
        webbrowser.open(url)


def pythonw_binary() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        cand = exe.with_name("pythonw.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def start(port: int, no_browser: bool) -> int:
    if is_ready(port):
        if not no_browser:
            open_url(port)
        return 0

    token = read_token()
    if not token:
        return 2

    env = dict(os.environ)
    env["DGTF_ACCESS_TOKEN"] = token
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    out = open(ROOT / f"_app_out_{port}.log", "ab", buffering=0)
    err = open(ROOT / f"_app_err_{port}.log", "ab", buffering=0)
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    cmd = [pythonw_binary(), "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port)]
    try:
        subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=out, stderr=err, close_fds=True, creationflags=flags,
        )
    except Exception as exc:  # noqa: BLE001
        with open(ROOT / "_launcher.err.log", "a", encoding="utf-8") as f:
            f.write(f"start failed: {type(exc).__name__}: {exc}\n")
        return 3

    deadline = time.time() + 120
    while time.time() < deadline:
        if is_ready(port):
            if not no_browser:
                open_url(port)
            return 0
        time.sleep(1.0)
    with open(ROOT / "_launcher.err.log", "a", encoding="utf-8") as f:
        f.write("health timeout after 120s\n")
    return 4


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="启动并打开浏览器")
    ap.add_argument("--start", action="store_true", help="只启动/复用")
    ap.add_argument("--check", action="store_true", help="只打印 health")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        print(json.dumps(health(args.port), ensure_ascii=False))
        return 0 if is_ready(args.port) else 1
    return start(args.port, bool(args.no_browser or args.start))


if __name__ == "__main__":
    raise SystemExit(main())
