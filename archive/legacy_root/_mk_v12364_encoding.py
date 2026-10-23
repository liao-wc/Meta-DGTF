# -*- coding: utf-8 -*-
"""v1.23.64 编码面修复：所有会打印非 ASCII 的入口都做 UTF-8 兜底。

★ 为什么必须修：Windows 下 stdout 被重定向到管道/文件时，Python 用 locale
  （cp936）编码；本项目第一条 print 就带 ✓/✗/emoji ⇒ UnicodeEncodeError
  ⇒ 进程在**真正干活之前或之后**崩掉。_run_gate 曾经因此在命令成功后仍
  打印失败（退出码 1），把「成功」读成「失败」。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

BOOT = (
    "# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──\n"
    "import sys as _sys_utf8\n"
    "for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):\n"
    "    try:\n"
    "        _s_utf8.reconfigure(encoding=\"utf-8\", errors=\"replace\")\n"
    "    except Exception:\n"
    "        pass\n"
)

FILES = [
    "bench/bench_calibrate.py", "bench/bench_diff.py", "bench/bench_report.py",
    "bench/bench_run.py", "bench/bench_score.py",
    "_v122_verify.py", "_probe_v1232_audit.py", "_mut_v12332.py",
    "_git_save.py", "dgtf_app/server.py", "dgtf_app/selftest.py",
    "_probe_gain_dist.py", "_probe_gain_live.py",
    "_run_matrix_v12333.py", "_run_full_v12333.py", "_run_gate.py",
]


def patch_boot(p: Path) -> bool:
    t = p.read_text(encoding="utf-8")
    if "reconfigure(encoding=" in t and "_sys_utf8" in t:
        return False
    nl = "\r\n" if "\r\n" in t else "\n"
    tree = ast.parse(t)
    ins_line = 0
    if tree.body and isinstance(tree.body[0], ast.Expr) \
            and isinstance(getattr(tree.body[0], "value", None), ast.Constant) \
            and isinstance(tree.body[0].value.value, str):
        ins_line = tree.body[0].end_lineno
    if len(tree.body) > 1 and isinstance(tree.body[1], ast.ImportFrom) \
            and tree.body[1].module == "__future__":
        ins_line = tree.body[1].end_lineno
    lines = t.split(nl)
    boot = BOOT.replace("\n", nl).rstrip(nl).split(nl)
    out = lines[:ins_line] + [""] + boot + lines[ins_line:]
    p.write_text(nl.join(out), encoding="utf-8")
    return True


for fn in FILES:
    p = HERE / fn
    if p.is_file():
        changed = patch_boot(p)
        print(("patched  " if changed else "skip     ") + fn)

# ── _run_gate.py：给子进程注入 UTF-8 环境（否则子进程照样按 GBK 崩）──
p = HERE / "_run_gate.py"
t = p.read_text(encoding="utf-8")
if "PYTHONUTF8" not in t:
    t = t.replace("import pathlib\n", "import os\nimport pathlib\n", 1)
    old = "r = subprocess.run(cmd, cwd=str(HERE), capture_output=True)"
    assert old in t, "_run_gate 的 subprocess 行找不到"
    t = t.replace(
        old,
        "_env = dict(os.environ)\n"
        "_env.setdefault(\"PYTHONUTF8\", \"1\")\n"
        "_env.setdefault(\"PYTHONIOENCODING\", \"utf-8\")\n"
        "r = subprocess.run(cmd, cwd=str(HERE), capture_output=True, env=_env)",
        1,
    )
    p.write_text(t, encoding="utf-8")
    print("patched  _run_gate.py (env)")
else:
    print("skip     _run_gate.py (env)")
