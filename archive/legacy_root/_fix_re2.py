# -*- coding: utf-8 -*-
"""[v1.23.2] 同步注入器 `_mk_v1232_verify.py` 里的 `_wired` 正则。

注入器里的字面量是**双层转义**（它在 `'''` 里，生成的是带单层转义的源码），
所以锚点要用 `\\\\(` 这种写法才能命中（我第一版按生成后源码的写法去找，
当然找不到）。生成后的目标正则（raw 串，容忍嵌套括号）：

    r\"\"\"stage=_thinking_stage\\([^\\n]*?,\\s*[\"'](\\w+)[\"']\\)\"\"\"
"""
import ast
from pathlib import Path

P = Path("_mk_v1232_verify.py")
s = P.read_text(encoding="utf-8")

OLD = """    _wired = set(_re.findall(r'stage=_thinking_stage\\\\([^,]+,\\\\s*"(\\\\w+)"', _txt))"""
NEW = ('''    # ★ 注入的字面量是**单引号**（%r 生成），且 `_check_input_sanity` 那处
    #   参数里有**逗号**（`getattr(d, 'config', None)`）⇒ 正则要容忍嵌套括号。
    _wired = set(_re.findall(
        r\\"\\"\\"stage=_thinking_stage\\\\([^\\\\n]*?,\\\\s*["'](\\\\w+)["']\\\\)\\"\\"\\", _txt))''')

n = s.count(OLD)
assert n == 1, "锚点命中 %d 次" % n
s = s.replace(OLD, NEW)
ast.parse(s)
P.write_text(s, encoding="utf-8")
print("注入器正则已同步")
# 自证：重新注入一次，生成的正则应能被 ast.parse 且能抠到 15 个
