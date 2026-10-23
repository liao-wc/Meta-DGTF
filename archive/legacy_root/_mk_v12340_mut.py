# -*- coding: utf-8 -*-
"""[v1.23.40 补丁] _mut_v12332.py：SRC 切 V1.23.40 + 追加 M85/M86。

★ 纪律（本轮又踩两次）：
  ① 变异体锚点含换行 ⇒ 用**相邻字面量隐式拼接**（`'a\n'` `'b'`），
     换行写成转义序列 `\n`；**绝不能**把真换行拼进字面量（M84 栽过）。
  ② 锚点以**反斜杠结尾** ⇒ 文件里必须写 `\\`（转义反斜杠），
     否则会把闭合引号转义掉（SyntaxError）。
  ③ 改完必须验「变异后 AST 是否还 OK」——语法崩了的变异体是**无效变异体**
     （它只是让判据报错，不是打中机制）。
"""
import ast
from pathlib import Path

BS = chr(92)
NL = chr(10)
HERE = Path(__file__).resolve().parent
P = HERE / "_mut_v12332.py"
MAIN = HERE / "元DGTF-V1.23.40.py"

raw = P.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "_mut 不是纯 CRLF"
s = raw.decode("utf-8").replace("\r\n", "\n")

# ── ① SRC 切 v1.23.40（幂等：已是 40 则跳过）──
a = 'SRC = HERE / "元DGTF-V1.23.39.py"'
b = 'SRC = HERE / "元DGTF-V1.23.40.py"'
if b in s:
    print("[info] SRC 已是 v1.23.40，跳过")
elif s.count(a) == 1:
    s = s.replace(a, b)
    print("[ok] SRC -> v1.23.40")
else:
    raise AssertionError("SRC 锚点 %d（既非 39 也非 40）" % s.count(a))

# ── ② 构造 M85/M86（文件里的字面行，用隐式拼接）──
# M85：stage 兜底不做（锚点无反斜杠，简单）
l85_old = "     '        _st = str(stage or \"\").strip()',"
l85_new = "     '        _st = str(stage or \"\").strip()  # M85 故意不兜底'," + "),"

# M86：跳过元组去掉 _web_need_report（锚点跨行 + 以反斜杠结尾）
Q = chr(34)
tup_old_1 = ('            if _n not in ("call", "_call_long", "_web_augment",')
tup_old_2 = ('                          "_web_need_report", "<module>") ')
tup_new_1 = tup_old_1
tup_new_2 = ('                          "<module>") ')


def _lit(txt):
    """生成一行「单引号字面量」：txt 里的真换行写成 \\n，反斜杠写成 \\\\。"""
    out = txt.replace(BS, BS + BS).replace(NL, BS + "n")
    return "     '" + out + "'"


l86_old1 = _lit(tup_old_1 + NL)
l86_old2 = _lit(tup_old_2 + BS + NL) + ","   # ★ 逗号：分隔 old 与 new
l86_new1 = _lit(tup_new_1 + NL)
l86_new2 = _lit(tup_new_2 + BS + NL) + "),"

block = [
    '    #   ★ M85 打在**stage 兜底**上：不再用 `_infer_stage_from_stack()`',
    '    #     取真实环节名 ⇒ record 的 stage 为空 ⇒ 回喂永远匹配不上',
    '    #     （= v1.23.39 真跑前的状态；判据「stage 兜底失败」必判红）。',
    '    ("M85 回喂 stage 不兜底（记录无名 ⇒ 回喂匹配不上）",',
    l85_old,
    l85_new,
    '    #   ★ M86 打在**跳过元组**上：`_web_need_report` 不被跳过 ⇒',
    '    #     从它内部调 `_infer_stage_from_stack()` 会把**它自己**当成',
    '    #     环节名 ⇒ 入库 stage = "web_need_report"（判据必判红）。',
    '    ("M86 跳过元组漏本函数（把自己当环节名）",',
    l86_old1,
    l86_old2,
    l86_new1,
    l86_new2,
]

lines = s.split("\n")
iend = next(i for i, l in enumerate(lines) if l.strip() == "]")
s = NL.join(lines[:iend] + block + lines[iend:])

# ── ③ 判据清单接入 ──
c = '             "st.check_v12339_ondemand() and "'
assert s.count(c) == 1, "判据清单锚点 %d" % s.count(c)
s = s.replace(c, '             "st.check_v12340_backfeed_stage() and "' + NL + c)

out = s.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out
P.write_bytes(out)

# ── 回读自检 ──
t = P.read_bytes().decode("utf-8")
ast.parse(t)
print("[ok] _mut AST OK | 纯 CRLF =",
      P.read_bytes().count(b"\n") == P.read_bytes().count(b"\r\n"))

# ── ★ 有效变异体自检：每条锚点命中 1 次 **且变异后 AST 仍 OK** ──
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("mm", P)
mm = importlib.util.module_from_spec(spec)
sys.modules["mm"] = mm
spec.loader.exec_module(mm)
src = MAIN.read_bytes().decode("utf-8").replace("\r\n", "\n")
bad = 0
for i, (name, old, new) in enumerate(mm.MUTS, 1):
    if not ("M85" in name or "M86" in name):
        continue
    n = src.count(old)
    try:
        ast.parse(src.replace(old, new, 1))
        ok = "AST OK"
    except SyntaxError as e:
        ok = "SyntaxError(%s) ⇒ **无效变异体**" % e.msg
        bad += 1
    print("  [%d] %-28s 命中 %d | %s" % (i, name[:28], n, ok))
    if n != 1:
        bad += 1
print("[%s] M85/M86 有效变异体自检" % ("ok" if bad == 0 else "!! 有问题"))
print("[ok] 总条目:", len(mm.MUTS))