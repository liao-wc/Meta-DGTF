# -*- coding: utf-8 -*-
"""[_gate_core_app] 应用端到端门禁的外壳：起 server → 跑 selftest → kill server。

用法：python _gate_core_app_gate.py [端口，默认 8765]
为什么用脚本而不是手工三条命令：server 是**子进程**，必须由同一个父进程在
finally 里 kill —— 否则「跑完 kill」全靠人记得，漏一次就留下 8765 端口孤儿
（本项目的 app 门禁此前多次踩到端口占用）。
产物：_gate_core_app.log（selftest 的 stdout+stderr）、_gate_core_server.log（server 日志）。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
PY = sys.executable
LOG = HERE / "_gate_core_app.log"
SRV_LOG = HERE / "_gate_core_server.log"

env = dict(os.environ)
env.setdefault("PYTHONUTF8", "1")
env.setdefault("PYTHONIOENCODING", "utf-8")

srv_out = open(SRV_LOG, "wb")
srv = subprocess.Popen(
    [PY, "dgtf_app/server.py", "--port", str(PORT)],
    cwd=str(HERE), env=env, stdout=srv_out, stderr=subprocess.STDOUT)
rc = 2
try:
    up = False
    for _ in range(120):
        if srv.poll() is not None:
            print("✗ server 启动即退出（exit=%r），见 %s" % (srv.returncode, SRV_LOG.name))
            break
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/config" % PORT, timeout=2) as r:
                if r.status == 200:
                    up = True
                    break
        except Exception:
            pass
        time.sleep(0.5)
    if not up:
        print("✗ server 未就绪（127.0.0.1:%d）" % PORT)
    else:
        print("· server 已就绪（127.0.0.1:%d）" % PORT)
        r = subprocess.run([PY, "dgtf_app/selftest.py"],
                           cwd=str(HERE), env=env, capture_output=True)
        txt = (r.stdout or b"") + (r.stderr or b"")
        LOG.write_bytes(txt)
        rc = r.returncode
        print("EXIT=%d  日志 %s（%d 字节）" % (rc, LOG.name, len(txt)))
        tail = txt.decode("utf-8", "replace").splitlines()[-15:]
        print("\n".join(tail))
finally:
    srv.terminate()
    try:
        srv.wait(timeout=10)
    except Exception:
        srv.kill()
        try:
            srv.wait(timeout=5)
        except Exception:
            pass
    srv_out.close()
    print("· server 已 kill（port %d）" % PORT)
sys.exit(rc)
