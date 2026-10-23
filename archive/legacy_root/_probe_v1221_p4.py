#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P4] 探针：三态多票 ON/OFF 开关 + 「stability 只在多票路径写」。

★ 这一条是本档的核心实测：`stability` 只在多票路径被赋值 —— 所以
  任务书指定的 md 口径在 OFF 臂**不可用**（缺键 → 引擎按 (0+0)/n 印 0%）。

用法：python _probe_v1221_p4.py <src.py>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else ""
NL = chr(10)
TXT = Path(SRC).read_text(encoding="utf-8").replace(chr(13) + chr(10), NL)


def _body(name: str) -> str:
    """★ 必须带开括号 —— `def _adjudicate_sub_tristate` 是 `..._multi` 的
    **前缀**，不带括号会两条都命中 multi（探针第一版就这么误读成
    「单票路径也写了 stability」）。"""
    i = TXT.find("def " + name + "(")
    if i < 0:
        return ""
    j = TXT.find(NL + "    def ", i + 10)
    return TXT[i:j] if j > i else TXT[i:]


MULTI = _body("_adjudicate_sub_tristate_multi")
SINGLE = _body("_adjudicate_sub_tristate")

out = {}
out["A1_开关在DEFAULT_CONFIG"] = 'tri_multi_vote' in TXT
out["A2_调用点_action_on"] = '_action_on(self.config, "tri_multi_vote")' in TXT
out["B1_stability_写入处"] = {
    "multi 路径": MULTI.count('"stability"'),
    "single 路径": SINGLE.count('"stability"'),
}
out["B2_multi_写_stability"] = MULTI.count('"stability"') > 0
out["B3_single_写_stability"] = SINGLE.count('"stability"') > 0
# 头部渲染读它
out["C1_头部读_stability"] = 's.get("stability") == "high"' in TXT
out["C2_头部按零渲染"] = "_rate = (_hi + _me) / max(1, len(_sq1))" in TXT
out["D1_consistency_json"] = (
    Path(".").resolve() / "_v1221_p4_consistency.json").is_file()
try:
    spec = importlib.util.spec_from_file_location("dgtf_p4", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p4"] = m
    spec.loader.exec_module(m)
    out["E1_DEFAULT_tri_multi_vote"] = (
        (m.DEFAULT_CONFIG.get("actions") or {}).get("tri_multi_vote", "<缺>"))
except Exception as e:
    out["E1_DEFAULT_tri_multi_vote"] = "ERR " + type(e).__name__
_js = json.dumps(out, ensure_ascii=False, indent=2)
if OUT:
    from pathlib import Path as _P2
    _P2(OUT).write_bytes(_js.encode("utf-8"))
print(_js)
