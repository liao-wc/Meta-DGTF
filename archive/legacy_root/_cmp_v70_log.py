#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真跑前的日志体量对照：同一支 mock 作业分别跑 v69 码与 v70 码，比 stdout。

[E] 用差分压掉了"累积型"字段；[H] 说大头其实是**覆盖型**的
rendered / manifest。这条对照把"大头在哪、压掉了多少"算成数 ——
不靠感觉。段内切分，不用整串 re.search。
"""
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st          # noqa: E402

Q = "老城区暴雨内涝，重建还是局部改造加海绵，怎么权衡？"


def _load(fn, name):
    spec = importlib.util.spec_from_file_location(name, str(HERE / fn))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mod69 = _load("元DGTF-V1.21.69.py", "dgtf69")
mod70 = _load("元DGTF-V1.21.70.py", "dgtf70")
for m in (mod69, mod70):
    m.LLM.call = st.fake_call


def _run(m):
    st.mod = m
    st.CALLS["n"] = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        st.run_mode("serial", Q, verbose=True)
    return buf.getvalue()


def _stats(txt, tag):
    segs = re.split(r"(?=圈全量留痕 · entry=)", txt)
    dump_segs = [s for s in segs[1:]]
    dump_chars = sum(len(s) for s in dump_segs)
    # 每个留痕段里 rendered/manifest 各占多少行
    n_rm_body = len(re.findall(r"   │ .*(?:\n(?!   ├ ).*)*", ""))
    n_len_line = len(re.findall(
        r"├ (rendered|manifest)：str \d+ 字（超大覆盖字段", txt))
    n_rm_lines = 0
    for m in re.finditer(
            r"├ (rendered|manifest)：[^\n]*\n((?:   │ [^\n]*\n)*)", txt):
        n_rm_lines += len(m.group(2).splitlines())
    out = {
        "tag": tag,
        "stdout_chars": len(txt),
        "dump_segs": len(dump_segs),
        "dump_chars": dump_chars,
        "rm_len_lines": n_len_line,
        "rm_body_lines": n_rm_lines,
        "yi_lines": txt.count("   │ "),
    }
    return out


a = _stats(_run(mod69), "v1.21.69")
b = _stats(_run(mod70), "v1.21.70")
keys = ["stdout_chars", "dump_segs", "dump_chars", "rm_len_lines",
        "rm_body_lines", "yi_lines"]
print(f"{'指标':<16}{'v69':>12}{'v70':>12}{'变化':>16}")
for k in keys:
    d = b[k] - a[k]
    pct = f"{d / a[k] * 100:+.1f}%" if a[k] else "-"
    print(f"{k:<16}{a[k]:>12}{b[k]:>12}{d:>10} {pct:>6}")
