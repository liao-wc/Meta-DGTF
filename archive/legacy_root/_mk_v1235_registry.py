# -*- coding: utf-8 -*-
"""v1.23.5：把新增的三个模块级函数登记进 AST 登记表（phase 6.6 两向对账）。

未登记判红 + 过期登记判红 —— 这条判据存在的意义就是逼着每个新符号都要写清
「为什么加」。三个函数都是 pending_fix #1 收口抽出来的唯一实现。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE / "_v122_ast_registry.json"
BAK = HERE / "_bak_v122_ast_registry.pre_v1235"

if not BAK.exists():
    BAK.write_bytes(REG.read_bytes())

d = json.loads(REG.read_text(encoding="utf-8"))

NEW = {
    "_plan_conf": {
        "phase": "v1235",
        "reason": "pending_fix #1 收口：confidence 归一化的唯一实现（不可解析记 0.0，保守退 serial）。原在三处各写一份。",
    },
    "_normalize_plan_mode": {
        "phase": "v1235",
        "reason": "pending_fix #1 收口：调度 mode 白名单归一化的唯一实现（A~H 或 serial）。原在三处各写一份。",
    },
    "_normalize_plan_rounds": {
        "phase": "v1235",
        "reason": "pending_fix #1 收口：逐层圈数归一化的唯一实现（解析 + 中位数补漏 + 钳制 + 可选按 route 裁）。原在两处各写一份。",
    },
}

added = 0
for k, v in NEW.items():
    if k not in d["registry"]:
        d["registry"][k] = v
        added += 1

d["current"] = "元DGTF-V1.23.5.py"
if isinstance(d.get("added"), int):
    d["added"] = len(d["registry"])

REG.write_bytes(json.dumps(d, ensure_ascii=False, indent=1,
                           sort_keys=True).encode("utf-8"))
print("登记表已更新：新增 %d 条，registry 共 %d 条，current -> %s"
      % (added, len(d["registry"]), d["current"]))
