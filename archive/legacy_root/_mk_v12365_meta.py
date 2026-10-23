# -*- coding: utf-8 -*-
"""同步 v1.23.65 的 SRC、符号注册表与配置头（幂等）。"""
from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD, NEW = "元DGTF-V1.23.64.py", "元DGTF-V1.23.65.py"

for fn in ("smoke_test.py", "_mut_v12332.py"):
    p = HERE / fn
    t = p.read_text(encoding="utf-8")
    old = 'SRC = HERE / "%s"' % OLD
    new = 'SRC = HERE / "%s"' % NEW
    if old in t:
        p.write_text(t.replace(old, new), encoding="utf-8")
        print("SRC updated:", fn)
    elif new not in t:
        raise SystemExit("%s 里没有旧/新 SRC" % fn)

raw = subprocess.check_output(["git", "show", "HEAD:_v122_ast_registry.json"])
crlf = b"\r\n" in raw
d = json.loads(raw.decode("utf-8"), object_pairs_hook=collections.OrderedDict)
d["added"] = 348
d["current"] = NEW
d["n_symbols_current"] = 637
d["registry"]["_token_budget_over"] = collections.OrderedDict([
    ("phase", "F"),
    ("reason", "总 token 软预算判定（层/圈边界优雅停；与 max_calls 互补）"),
])
# 保留当前已追加的 22 个 F 符号（HEAD 里还没有）
cur = json.loads((HERE / "_v122_ast_registry.json").read_text(encoding="utf-8"),
                 object_pairs_hook=collections.OrderedDict)
for k, v in cur.get("registry", {}).items():
    if k not in d["registry"]:
        d["registry"][k] = v
out = json.dumps(d, ensure_ascii=False, indent=1)
if crlf:
    out = out.replace("\n", "\r\n")
(HERE / "_v122_ast_registry.json").write_bytes(
    (out + ("\r\n" if crlf else "\n")).encode("utf-8"))
print("registry entries:", len(d["registry"]))

p = HERE / "dgtf_config.yaml"
t = p.read_text(encoding="utf-8")
if "# 元 DGTF · v1.23.64 配置文件" in t:
    p.write_text(t.replace("# 元 DGTF · v1.23.64 配置文件",
                           "# 元 DGTF · v1.23.65 配置文件"), encoding="utf-8")
    print("yaml header updated")
