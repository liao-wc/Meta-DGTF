# -*- coding: utf-8 -*-
"""[dry-run] 验证 check_v12338_relax_targets 落盘后的**行为**：
  用子进程把新判据函数**注入内存副本**（不写真文件），跑一次看它是否判绿。
★ 为什么要子进程：`_mk_*.py` 的执行在模块级，直接 import 会真的改文件。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

code = r'''
import re, sys, importlib.util
from pathlib import Path
HERE = Path(r"%s")
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("smoke_test", HERE / "smoke_test.py")
st = importlib.util.module_from_spec(spec); sys.modules["smoke_test"] = st
spec.loader.exec_module(st)

# ── 把新判据注入到内存中的 smoke_test 模块 ──
mk_src = (HERE / "_mk_v12338_relaxjudge.py").read_text(encoding="utf-8")
_qq = chr(39) * 3
m = re.search("NEW_FN = " + _qq + "(.*?)" + _qq, mk_src, re.S)
fn_src = m.group(1)
# NEW_FN 尾部带着插入锚点行（`def check_v12338_backfeed():`）—— 真实补丁需要它，
# 但这里 exec 不需要 ⇒ 截到锚点行之前。
fn_src = fn_src.split("def check_v12338_backfeed():")[0]
# 落盘等价：把 \\r\\n 还原成 \r\n 等（模拟写进 py 文件后 Python 解析的结果）
fn_src = fn_src.replace("\\\\r\\\\n", "\\\\r\\\\n")   # 保持原样（已是源文本）
ns = dict(st.__dict__)
exec(compile(fn_src, "<newfn>", "exec"), ns)
st.check_v12338_relax_targets = ns["check_v12338_relax_targets"]

print("=== 单跑 check_v12338_relax_targets ===")
ok = st.check_v12338_relax_targets()
print("RESULT:", ok)

# ── 变异体试验：把放宽表塞一个不存在的环节名 ⇒ 必须判红 ──
import tempfile
_src = (HERE / "元DGTF-V1.23.38.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
_bad = _src.replace('"expand_pair_merged_once")',
                    '"expand_pair_merged_once", "__no_such_stage__")', 1)
_tmp = Path(tempfile.gettempdir()) / "_dry_relax_bad.py"
_tmp.write_bytes(_bad.encode("utf-8"))
st.SRC = _tmp
print("=== 变异（塞不存在的环节名）应判红 ===")
ok2 = st.check_v12338_relax_targets()
print("RESULT:", ok2, "(期望 False)")
''' % str(HERE).replace("\\", "\\\\")

r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                   cwd=str(HERE))
print(r.stdout)
if r.stderr:
    print("[stderr]", r.stderr[-800:])
