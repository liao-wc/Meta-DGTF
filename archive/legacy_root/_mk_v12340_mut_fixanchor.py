# -*- coding: utf-8 -*-
"""★ 作废（勿运行）：本脚本的 `ast.unparse` 整文件重写方案**未被采用** ——
   M79/M82 锚点最终用「直接编辑」修复（多行上下文 + 元组新末行）。

   保留此文作**过程证据**：记录「先想用 unparse 重排，评估后放弃（会重排
   整个 _mut 文件、有破坏风险）」这一步探索。若运行本脚本，它会用
   `ast.unparse` 重写 `_mut_v12332.py` —— **可能损坏变异体清单，请勿运行。**

原始的锚点失配分析与修法思路（历史记录）：
修 v1.23.40 relax 改动引发的 M79/M82 锚点失配。

根因：relax 改动把
  M79 的 `if _grew <= 0:` 改成 `if _force or _grew <= 0:`（_before_round）
  M82 的 `"expand_pair", "expand_pair_merged_once")` 拆行 + 扩项（_TICK_WEB_RELAX）
⇒ 两条老变异体锚点命中 0（失效），v1.23.39 时是 82/82 全红。

修法：
· M79：old 改用「多行上下文」唯一锚定新行 `if _force or _grew <= 0:\n    _why = (`
        （不可只用单行，否则与 M87 的 old 串撞，count=2）
        new = `if True:\n                    _why = (`（忽略增量+force，恒放宽）
        仍被 judge 臂①（force=false 有增量 ⇒ 期望不放宽）逮到 ⇒ 判红。
· M82：old 改用元组新末行 `"decompose_koan", "decompose_from_pool)"`
        new 追加死配置 `__no_such_stage__`。
"""
import sys

# ★★ 硬护栏（无条件）：本脚本作废，**直跑与 import 都拒绝执行** ——
#    它后面的模块级代码会用 ast.unparse 重写 _mut_v12332.py（项目踩过
#    「_mk_* 模块级逻辑 ⇒ import 即真改文件」的坑，故此处不做 __main__ 判断）。
#    要看历史思路读文件头 docstring 即可。
raise SystemExit("[作废] 本脚本未被采用（方案：ast.unparse 重排，评估后放弃）。"
                 " M79/M82 锚点已用直接编辑修复，勿运行本脚本。")

from pathlib import Path

P = Path("_mut_v12332.py")
raw = P.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw, "非纯 CRLF"
s = raw.decode("utf-8").replace("\r\n", "\n")

# ── M79：多行上下文唯一锚点（注意 _why = ( 前是 20 空格）──
M79_OLD = ('                if _grew <= 0:',)
m79_old = '                if _grew <= 0:'
m79_new = '                if _force or _grew <= 0:\n                    _why = ('

# 当前 M79 的 old 是单行 `if _grew <= 0:` —— 在代码里已不存在（代码是
# `if _force or _grew <= 0:`），所以这里改 _mut 文件里 M79 那条的 old/new。
# 用 AST 定位 M79 条目最稳。
import ast
t = ast.parse(s)
for n in ast.walk(t):
    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "MUTS":
        for e in n.value.elts:
            nm = ast.literal_eval(e.elts[0])
            if nm.startswith("M79"):
                # 改 old（第2元素）与 new（第3元素）
                e.elts[1] = ast.Constant(m79_new.split("\n")[0] + "\n" +
                                         "                    _why = (")
                e.elts[2] = ast.Constant("                if True:\n" +
                                         "                    _why = (")
                print("[ok] M79 锚点改为多行唯一：", repr(ast.literal_eval(e.elts[1]))[:60])
            if nm.startswith("M82"):
                old_now = ast.literal_eval(e.elts[1])
                assert old_now == '                       "expand_pair", "expand_pair_merged_once")', \
                    "M82 old 已变？%r" % old_now
                e.elts[1] = ast.Constant('                       "decompose_koan", "decompose_from_pool")')
                e.elts[2] = ast.Constant('                       "decompose_koan", "decompose_from_pool",\n                       "__no_such_stage__")')
                print("[ok] M82 锚点改为元组新末行")

# 重新序列化：用原生 ast 不可行（会丢注释/格式），改为在文本上按 name 替换
# —— 但 AST 已改了对象，最稳是重新 parse 整文件并 unparse（Python3.9+ 支持）。
new_src = ast.unparse(t)
out = new_src.replace("\n", "\r\n").encode("utf-8")
P.write_bytes(out)
print("[ok] 已写回（unparse ⇒ 纯 LF 转 CRLF）| 字节含 CRLF:",
      out.count(b"\r\n") > 0, "| CRCRLF:", out.count(b"\r\r\n"))

# ── 自检：在引擎里验证新锚点命中 1 ──
eng = Path("元DGTF-V1.23.40.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
import importlib.util, sys
spec = importlib.util.spec_from_file_location("mfix", "_mut_v12332.py")
m = importlib.util.module_from_spec(spec); sys.modules["mfix"] = m
spec.loader.exec_module(m)
ok = 0
for nm, old, new in m.MUTS:
    if nm.startswith("M79"):
        print("M79 old 命中引擎:", eng.count(old), "| 变异后 AST:",
              end=" ")
        mut = eng.replace(old, new, 1)
        try:
            ast.parse(mut); print("OK"); ok += 1
        except SyntaxError as ex:
            print("ERR", ex); 
    if nm.startswith("M82"):
        print("M82 old 命中引擎:", eng.count(old), "| 变异后 AST:",
              end=" ")
        mut = eng.replace(old, new, 1)
        try:
            ast.parse(mut); print("OK"); ok += 1
        except SyntaxError as ex:
            print("ERR", ex)
print("[ok] 两锚点自检通过数:", ok, "/ 2")
