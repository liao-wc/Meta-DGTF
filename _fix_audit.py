# -*- coding: utf-8 -*-
"""[v1.23.3] 给整体审计探针加一类：**模型返回的 id 必须过归一化**。

为什么加这一类：受控投票实验抓到「某票返回 0 起 id ⇒ 整票错位一格且无声」。
这是**一类** bug（凡「读模型返回的 id 再按本地 1..N 对齐」都可能有），
所以要做成机械判据，而不是修完这一处就算了。

判据：
  L1 存在纯函数 `_normalize_judgment_ids`
  L2 ★ 源码里**所有**「读模型返回的 id」的调用点，其所在函数体内必须出现
     `_normalize_judgment_ids(`（未归一化 = 可能静默错位）
  L3 自检：把 L2 的扫描逻辑跑在**合成源码**上（含一处未归一化）⇒ 必须报出
     （否则 L2「全绿」只说明扫描没工作）
"""
from pathlib import Path
import ast

P = Path("_probe_v1232_audit.py")
s = P.read_text(encoding="utf-8")

O = "# ============================================================ I 自检"
N = '''# ============================================================ L 模型 id
# ★ 一类 bug，不是一个点：凡「读模型返回的 id、再按本地 1..N 对齐」的地方，
#   都可能因为模型给 0 起而**整票错位一格、且完全无声**（v1.23.3 实测）。
#   做成机械判据：这些调用点所在函数体里必须出现 `_normalize_judgment_ids(`。
print("── L 模型返回的 id 归一化 ──")


def _unnormalized_id_sites(txtx):
    """返回 [(函数名, 行号)]：读了模型返回的 id 但**没有**归一化的位置。"""
    _bad = []
    _tr = ast.parse(txtx)
    _L = txtx.split(chr(10))
    for _fn in ast.walk(_tr):
        if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        _body = chr(10).join(_L[_fn.lineno - 1:_fn.end_lineno])
        if "_normalize_judgment_ids(" in _body:
            continue
        for _n in ast.walk(_fn):
            # 形状：int(<expr>.get("id" ...))
            if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                    and _n.func.id == "int" and _n.args):
                continue
            _a = _n.args[0]
            if (isinstance(_a, ast.Call) and isinstance(_a.func, ast.Attribute)
                    and _a.func.attr == "get" and _a.args
                    and isinstance(_a.args[0], ast.Constant)
                    and _a.args[0].value == "id"):
                _bad.append((_fn.name, _n.lineno))
    return _bad


ck("L1 ★ 存在纯函数 `_normalize_judgment_ids`",
   hasattr(mod, "_normalize_judgment_ids"), "改前版本没有这个符号")
_bad_sites = _unnormalized_id_sites(txt)
ck("L2 ★ 所有「读模型返回的 id」的调用点都过了归一化", not _bad_sites,
   "未归一化：" + repr(_bad_sites))
_N = [i for i, l in enumerate(LINES, 1) if "int(it.get(" in l
      and chr(34) + "id" + chr(34) in l]
ck("L2.b 抽样非空（防空过）", len(_N) >= 2,
   "命中 %d 处（应 ≥2：多票 + 单票）" % len(_N))
_SYN = ("def f(it):" + chr(10) + "    sid = int(it.get(" + chr(34) + "id"
        + chr(34) + ", 0))" + chr(10) + "    return sid" + chr(10))
ckt = _unnormalized_id_sites(_SYN)
ck("L3 自检：合成源码（一处未归一化）必须被报出", len(ckt) == 1, repr(ckt))
_SYN2 = ("def g(it):" + chr(10) + "    sid = int(it.get(" + chr(34) + "id"
         + chr(34) + ", 0))" + chr(10)
         + "    return _normalize_judgment_ids(sid, 3)" + chr(10))
ck("L3.b 自检（负）：归一化过的合成源码**不**报出",
   not _unnormalized_id_sites(_SYN2), "")

# ============================================================ I 自检'''
assert s.count(O) == 1
s = s.replace(O, N)
P.write_text(s, encoding="utf-8")
ast.parse(s)
print("审计探针 +L 类（含 1 条合成自检）")
