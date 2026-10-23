# -*- coding: utf-8 -*-
"""[v1.23.3] AST 登记表两向对账（未登记判红 / 过期登记判红）。"""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
regf = HERE / "_v122_ast_registry.json"
d = json.loads(regf.read_text(encoding="utf-8"))


def syms(p):
    t = ast.parse(Path(p).read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(t)
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


a = syms(HERE / d["baseline"])
b = syms(HERE / "元DGTF-V1.23.3.py")
added = sorted(b - a)

NEW = {
    "_normalize_judgment_ids":
        ("v1233",
         "★ 把一票的 {id: label} 归一到 1..n（1 起原样 / 0 起整体 +1 / 越界判 None）"
         " —— 修「模型给 0 起 id ⇒ 整票错位一格且无声」（受控实验抓到）"),
    "_canonical_sub_ids":
        ("v1233",
         "★ 子问题 id 按位置重编号成 1..n —— 原实现直接用模型给的 id（0 起/带洞/重复），"
         "而下游一律按 1..n 用"),
}
for k, (ph, why) in NEW.items():
    d["registry"][k] = {"phase": ph, "reason": why}

unreg = [x for x in added if x not in d["registry"]]
stale = [k for k in d["registry"] if k not in added]
d["added"] = len(added)
d["n_symbols_baseline"] = len(a)
d["n_symbols_current"] = len(b)
d["current"] = "元DGTF-V1.23.3.py"
regf.write_bytes(json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8"))
print("符号 %d -> %d；added=%d；未登记=%s；过期=%s；消失=%d"
      % (len(a), len(b), len(added), unreg, stale, len(a - b)))
