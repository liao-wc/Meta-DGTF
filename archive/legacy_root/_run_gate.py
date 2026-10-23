# -*- coding: utf-8 -*-
"""通用验收 runner：跑一条命令，stdout+stderr 一次性 write_bytes 落盘。

★ 为什么不用 shell 的 `>`：本机重定向偶发写空/写旧（本项目实测多次），
  写出来的日志会「只有前半段」⇒ 把「没跑完」读成「跑到这儿失败了」。
用法：python _run_gate.py <日志名> -- <命令...>
"""

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
argv = sys.argv[1:]
assert "--" in argv, "用法：python _run_gate.py <日志名> -- <命令...>"
_i = argv.index("--")
logname = argv[:_i][0]
cmd = argv[_i + 1:]

_env = dict(os.environ)
_env.setdefault("PYTHONUTF8", "1")
_env.setdefault("PYTHONIOENCODING", "utf-8")
r = subprocess.run(cmd, cwd=str(HERE), capture_output=True, env=_env)
txt = (r.stdout or b"") + (r.stderr or b"")
p = HERE / logname
p.write_bytes(txt)
print("EXIT=%d  日志 %s（%d 字节）" % (r.returncode, logname, len(txt)))
tail = txt.decode("utf-8", "replace").splitlines()[-25:]
print("\n".join(tail))
sys.exit(r.returncode)
