# -*- coding: utf-8 -*-
"""[dry-run] 验证 check_v12338_relax_targets：
  ① 施加到内存副本后 AST OK；
  ② 真跑一次（对主文件）应判绿；
  ③ 变异（塞不存在的环节名）应判红；
  ④ 变异（删成员）应判红。

★ 不写任何真实文件。mk 脚本有 __main__ 护栏 ⇒ 可安全 import。
"""
import ast
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mk = _load(HERE / "_mk_v12338_relaxjudge.py", "mk_relaxjudge")

SM = HERE / "smoke_test.py"
raw = SM.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
s = raw.decode("utf-8").replace("\r\n", "\n")

# ① 施加到内存副本 + AST
s2 = mk.apply(s)
ast.parse(s2)
print("[ok] ① 施加后 AST OK")

# 把施加后的内容写成**项目目录下的临时 smoke_test 副本**（同名目录 ⇒ HERE 解析正确）
_tmp_sm = HERE / "_dry_smoke_tmp.py"
_tmp_sm.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
print("[ok] 临时 smoke_test：", _tmp_sm)

# ②③④ 子进程里跑
code = r'''
import sys, importlib.util, tempfile
from pathlib import Path
HERE = Path(r"%s")
TMP = Path(r"%s")
sys.path.insert(0, str(HERE))          # 让临时 smoke_test 能找到依赖

spec = importlib.util.spec_from_file_location("smoke_test", TMP)
st = importlib.util.module_from_spec(spec); sys.modules["smoke_test"] = st
spec.loader.exec_module(st)

print("=== ② 真跑（对主文件）应判绿 ===")
print("RESULT:", st.check_v12338_relax_targets())

_src = (HERE / "元DGTF-V1.23.38.py").read_bytes().decode("utf-8").replace("\r\n", "\n")

print("=== ③ 变异：塞不存在的环节名 ⇒ 应判红 ===")
_bad = _src.replace('"expand_pair_merged_once")',
                    '"expand_pair_merged_once", "__no_such_stage__")', 1)
_t = Path(tempfile.gettempdir()) / "_dry_relax_bad.py"
_t.write_bytes(_bad.encode("utf-8"))
st.SRC = _t
print("RESULT:", st.check_v12338_relax_targets(), "(期望 False)")

print("=== ④ 变异：砍到只剩 2 个成员 ⇒ 应判红 ===")
_bad2 = _src.replace(
    '("ing", "probe_research", "probe_duel", "probe_meta",\n'
    '                       "he", "phase_probe",\n'
    '                       "expand_pair", "expand_pair_merged_once")',
    '("ing", "probe_research")', 1)
_t2 = Path(tempfile.gettempdir()) / "_dry_relax_bad2.py"
_t2.write_bytes(_bad2.encode("utf-8"))
st.SRC = _t2
print("RESULT:", st.check_v12338_relax_targets(), "(期望 False)")
''' % (str(HERE), str(_tmp_sm))

r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                   cwd=str(HERE))
print(r.stdout)
if r.stderr:
    print("[stderr]", r.stderr[-1200:])
