#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2b] 探针：answers 匹配路径 + 双路径 + 阈值完整性。

用法：python _probe_v1221_p2b.py <src.py>
任务书 Step P2b.5 原文实现（未增删判据）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("dgtf", sys.argv[1])
dgtf = importlib.util.module_from_spec(spec)
# ★ 任务书给的骨架漏了这一行：主文件里有 `@dataclass`，dataclasses 解析时
#   要 `sys.modules[cls.__module__]`，未注册 → AttributeError('NoneType' ...)。
sys.modules["dgtf"] = dgtf
spec.loader.exec_module(dgtf)

out = {}

# A. 两个函数在不在
out["A1_hit_by_answers"] = hasattr(dgtf, "_hit_by_answers")
out["A2_hit_by_claim"] = hasattr(dgtf, "_hit_by_claim")

# B. 匹配行为
if hasattr(dgtf, "_hit_by_answers"):
    out["B1_exact"] = dgtf._hit_by_answers(
        "老城区现有排水管网的设计标准是多少年一遇",
        ["管网设计重现期", "老城区现有排水管网的设计标准"])
    out["B2_overlap"] = dgtf._hit_by_answers(
        "老城区地下管线密集程度", ["老城区地下管线密集程度"])
    out["B3_neg_no_answers"] = dgtf._hit_by_answers("任意", [])
    out["B4_neg_unrelated"] = dgtf._hit_by_answers(
        "本地微观数据", ["管网设计重现期"])
    out["B5_neg_none"] = dgtf._hit_by_answers("X", None)
else:
    # ★ 任务书「期望」写的是 before 侧 `B*` 全 AttributeError，但它给的骨架
    #   用 `hasattr` 守住了 → 键会**直接缺席**（diff 里看不出「为什么缺席」）。
    #   这里显式记一条，免得把「没测」误读成「测了是 False」。
    out["B_absent_before"] = "AttributeError: module has no _hit_by_answers"

# C. claim 路径阈值未动
src = Path(sys.argv[1]).read_text(encoding="utf-8")
out["C1_claim_0.6_intact"] = (
    "_similar(aspect, claim, 0.6)" in src
    or "_similar(s, claim, 0.6)" in src
    or ("_hit_by_claim" in src and "0.6" in src)
)
out["C2_answers_uses_UNTRACED"] = "_UNTRACED_OVERLAP" in src

# D. _anchor_crosscheck 里两条路都在
out["D1_answers_in_crosscheck"] = (
    "_hit_by_answers(str(a)" in src or "_hit_by_answers(" in src)
out["D2_claim_in_crosscheck"] = (
    "_hit_by_claim(str(a)" in src or "_hit_by_claim(" in src)

# E. _load_anchors 读 answers
out["E1_answers_key"] = '"answers"' in src

print(json.dumps(out, ensure_ascii=False, indent=2))
