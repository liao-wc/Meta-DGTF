# -*- coding: utf-8 -*-
"""[v1.23.38 补丁] _v122_ast_registry.json：current 指向 V1.23.38。

★ 本版**无新增/消失 AST 符号**（回喂是 `_web_augment` 体内改动）
   ⇒ registry 条目数不变（308），只改 current / n_symbols_current。
★ 保持原文件换行格式（先探测）。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_v122_ast_registry.json"
SRC = HERE / "元DGTF-V1.23.38.py"

raw = P.read_bytes()
is_crlf = raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\n") > 0
print("[info] registry 换行：%s" % ("CRLF" if is_crlf else "LF"))

d = json.loads(raw.decode("utf-8"))
print("[before] current =", d.get("current"), "| n_symbols_current =",
      d.get("n_symbols_current"), "| registry =", len(d.get("registry") or {}))

import ast


def top_syms(p):
    t = ast.parse(Path(p).read_text(encoding="utf-8"))
    out = {}
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = 1
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out[n.name + "." + m.name] = 1
    return out


cur = top_syms(SRC)
d["current"] = SRC.name
d["n_symbols_current"] = len(cur)

txt = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
out = txt.replace("\n", "\r\n").encode("utf-8") if is_crlf else txt.encode("utf-8")
P.write_bytes(out)

# 回读校验
d2 = json.loads(P.read_bytes().decode("utf-8"))
assert d2["current"] == SRC.name, "current 未更新"
assert d2["n_symbols_current"] == len(cur), "n_symbols_current 未更新"
assert len(d2.get("registry") or {}) == len(d.get("registry") or {}), "条目数变了"
print("[after ] current =", d2["current"], "| n_symbols_current =",
      d2["n_symbols_current"], "| registry =", len(d2["registry"]))
print("[ok] AST 登记表已同步（无新增/消失符号）")
