# -*- coding: utf-8 -*-
"""v1.23.9：AST 登记表同步（按主文件实算符号数，两向对账）。"""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.9.py"
BASE = HERE / "_baseline_v12177.py"
REG = HERE / "_v122_ast_registry.json"


def syms(p):
    t = ast.parse(Path(p).read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(t)
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


a, b = syms(BASE), syms(MAIN)
added = sorted(b - a)
d = json.loads(REG.read_text(encoding="utf-8"))
print("baseline %d → 本版 %d；added %d" % (len(a), len(b), len(added)))

t = REG.read_text(encoding="utf-8")
for old, new in (
    ('"added": %d,' % d["added"], '"added": %d,' % len(added)),
    ('"n_symbols_current": %d,' % d["n_symbols_current"],
     '"n_symbols_current": %d,' % len(b)),
    ('"current": "%s",' % d["current"], '"current": "元DGTF-V1.23.9.py",'),
):
    assert t.count(old) == 1, f"{old!r} 命中 {t.count(old)} 次"
    t = t.replace(old, new, 1)

anchor = ' "registry": {\n'
assert t.count(anchor) == 1, "registry 锚点不唯一"
INS = ('  "_has_decision_context": {\n'
       '   "phase": "9",\n'
       '   "reason": "取向分流守卫：题面有无决策语境（决定 decision 模板适不适用）"\n'
       '  },\n')
if '"_has_decision_context"' in t:
    print("[skip] 已登记")
else:
    t = t.replace(anchor, anchor + INS, 1)
    print("已登记 _has_decision_context")
REG.write_text(t, encoding="utf-8")

d2 = json.loads(REG.read_text(encoding="utf-8"))
unreg = [x for x in added if x not in d2["registry"]]
stale = [k for k in d2["registry"] if k not in added]
print("registry %d | 未登记 %s | 过期登记 %s"
      % (len(d2["registry"]), unreg or "无", stale or "无"))
assert not unreg and not stale, "两向对账失败"
