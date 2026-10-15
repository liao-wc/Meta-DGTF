# -*- coding: utf-8 -*-
"""[v1.23.40 补丁4] _mut_v12332.py：追加 M87/M88（强制放宽两条）。

★ 纪律（本轮已固化）：
  ① 锚点含换行 ⇒ 隐式拼接 + 转义序列，绝不写真换行；
  ② 锚点以反斜杠结尾 ⇒ 写 `\\`；
  ③ 改完验「锚点命中 1 + 变异后 AST OK」（有效变异体）。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_mut_v12332.py"
MAIN = HERE / "元DGTF-V1.23.40.py"

raw = P.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
s = raw.decode("utf-8").replace("\r\n", "\n")

if "M87 " in s or "M88 " in s:
    raise SystemExit("[skip] M87/M88 已在列（幂等）")

l87_old = "     '                if _force or _grew <= 0:',"
l87_new = "     '                if _grew <= 0:'" + "),"       # 注意：')' + ','
l88_old = "     '                       \"decompose_koan\", \"decompose_from_pool\")',"
l88_new = "     '                       \"decompose_koan\")'" + "),"

block = [
    '    #   ★ M87 打在**强制放宽判据**上：`_force` 被忽略 ⇒ `relax_force=true`',
    '    #     在有增量时不再放宽（开关成了摆设）；判据「force=true 也放宽」必判红。',
    '    ("M87 强制放宽开关被忽略（force 成摆设）",',
    l87_old,
    l87_new,
    '    #   ★ M88 打在**放宽表扩项**上：去掉 `decompose_from_pool` ⇒',
    '    #     用户口径「要扩」被回退；判据「放宽表缺 decompose_*」必判红。',
    '    ("M88 放宽表扩项被回退（少一个 decompose_*）",',
    l88_old,
    l88_new,
]

lines = s.split("\n")
iend = next(i for i, l in enumerate(lines) if l.strip() == "]")
s = "\n".join(lines[:iend] + block + lines[iend:])

out = s.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out
P.write_bytes(out)

# ── 自检 ──
t = P.read_bytes().decode("utf-8")
ast.parse(t)
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("mm2", P)
mm = importlib.util.module_from_spec(spec)
sys.modules["mm2"] = mm
spec.loader.exec_module(mm)
src = MAIN.read_bytes().decode("utf-8").replace("\r\n", "\n")
bad = 0
for i, (name, old, new) in enumerate(mm.MUTS, 1):
    if not ("M87" in name or "M88" in name):
        continue
    n = src.count(old)
    try:
        ast.parse(src.replace(old, new, 1))
        ok = "AST OK"
    except SyntaxError as e:
        ok = "SyntaxError(%s)" % e.msg
        bad += 1
    print("  [%d] %-30s 命中 %d | %s" % (i, name[:30], n, ok))
    if n != 1:
        bad += 1
print("[%s] M87/M88 有效变异体自检 | 总条目 %d" % ("ok" if bad == 0 else "!!", len(mm.MUTS)))