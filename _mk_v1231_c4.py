# -*- coding: utf-8 -*-
"""[v1.23.1 遗留] 把 C4（停止与清算分开）的判据锚从**兜底实现**扩到**主路径**。

起因（真跑产物读出）：最终 `decidability` 与判决时刻的 `_tri_final` 不一致
（子问题 2/6 是 `_tri_final=partial` → 产物 `undecidable`），追到
`_settle_research` 的「升级 → undecidable」写点（14175-14178）。
再查 C4 判据：它的锚是 `settle_deferrals` —— 而那个函数只是
**LLM 清算失败时的兜底**（14157 `return settle_deferrals(pool, layer)`），
真正跑主路径的是 `_settle_research`。

★ 所以旧判据是「锚错了对象」：往主路径里塞联网，旧的 C4 判据**不判红**。
本补丁：① 覆盖全部 4 个结算相关函数；② 加主路径变异体；
③ 把「旧锚对主路径变异体不判红」本身做成一条**负对照**证据。
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_probe_v123_w34.py"
s = P.read_bytes().decode("utf-8")
if "\n" in s and "\r\n" in s:
    s = s.replace("\r\n", "\n")

if "C4.e" in s:
    print("已加，跳过")
    sys.exit(0)

ADD = '''
# ---- [v1.23.1 遗留] C4 的锚必须覆盖**主路径**，不能只锚兜底 ----
_SETTLE_FNS = ("settle_deferrals", "_settle_research", "_settle_meta",
               "_refresh_settlement")
for _nm in _SETTLE_FNS:
    _b = body_of(_nm)
    ck("C4.e ★ 结算函数 %s 体内无任何 web 符号" % _nm,
       bool(_b) and not any(_k in _b for _k in _ING_FORBID)
       and "web_" not in _b,
       ("空体（符号不存在？）" if not _b
        else repr([_k for _k in _ING_FORBID if _k in _b])))
_b_main = body_of("_settle_research")
ck("C4.f ★ 主路径 `_settle_research` 确含「升级 → undecidable」写点"
   "（否则它就不是主路径，上面的锚白扩）",
   'sq["decidability"] = "undecidable"' in _b_main
   and 'escalated' in _b_main, "")
'''
A = "\n# ============================================================ D 变异测试"
assert s.count(A) == 1, s.count(A)
s = s.replace(A, ADD + A)

# ---- 变异体：AST 定位后按行插入（避开锚点唯一性）----
HELP = '''

def _inject_after_def(text, fn_name, stmt_line):
    """在函数体**第一条语句之前**插入一行（缩进取该语句的 col_offset）。

    ★ 不用字面锚点 —— 主路径里的行很多都不唯一；AST 定位天然唯一，
      且插入点缩进正确。
    """
    tree = ast.parse(text)
    for x in ast.walk(tree):
        if isinstance(x, ast.FunctionDef) and x.name == fn_name:
            _ind = " " * (x.body[0].col_offset if x.body else
                          (x.col_offset + 4))
            lines = text.split("\\n")
            lines.insert(x.body[0].lineno - 1, _ind + stmt_line)
            return "\\n".join(lines)
    return ""


_MUT2 = {
    "N3 往清算**主路径** `_settle_research` 掺 W#（C4.e 必须判红）":
        ("_settle_research",
         'pool.web_results.append({"id": "WX", "claim": "清算时偷跑检索"})'),
    "N4 往 `_settle_meta` 掺 W#（C4.e 必须判红）":
        ("_settle_meta",
         'pool.web_clean_check.append({"id": "WX", "claim": "元层清算偷跑"})'),
}
for _nm, (_fn, _stmt) in _MUT2.items():
    _mt = _inject_after_def(txt, _fn, _stmt)
    if not _mt or _mt == txt:
        ck("D.%s 变异体可构造" % _nm[:2], False, "AST 定位失败：" + _fn)
        continue
    _mb = body_of_in(_mt, _fn)
    _red = any(_k in _mb for _k in _ING_FORBID) or "web_" in _mb
    ck("D.%s → 判据判红" % _nm[:2], _red, "")
    if _nm.startswith("N3"):
        # ★★ 负对照：**旧判据**（只读 settle_deferrals）对主路径变异体
        #    **不判红** —— 这就是「锚错对象」的直接证据。
        _old = body_of_in(_mt, "settle_deferrals")
        _old_red = any(_k in _old for _k in _ING_FORBID) or "web_" in _old
        ck("D.N3 负对照：旧锚（只读 settle_deferrals）对主路径变异体**不判红**",
           _old_red is False,
           "旧锚也判红了 —— 说明它本来就覆盖主路径，本补丁是多余的")
'''

A2 = "\nprint(\"═══ probe v123 W3+W4 ═══\")"
assert s.count(A2) == 1, s.count(A2)
s = s.replace(A2, HELP + A2)

# 需要 body_of_in(text, name) —— 拿任意文本抠函数体
H2 = '''

def body_of_in(text, name):
    """在**任意文本**里抠函数体（变异体文本要用它，不能用全局 txt）。"""
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return "\\n".join(text.split("\\n")[n.lineno - 1:n.end_lineno])
    return ""
'''
A3 = "\n# ============================================================ A 结构"
assert s.count(A3) == 1, s.count(A3)
s = s.replace(A3, H2 + A3)

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
ast.parse(s)
print("C4 判据已扩到主路径（+2 变异体 +1 负对照）")
