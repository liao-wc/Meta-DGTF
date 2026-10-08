#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P5] 探针：auto 取向回填（单调用路径要带出 orientation）。

★ 本档的核心实测：`auto_plan` 的**单调用**分支原来不带 orientation ——
  而 `run()` 走的就是它，所以 `_auto_plan_used` 永远拿不到取向。

用法：python _probe_v1221_p5.py <src.py>
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
Q = chr(34)

out = {}
out["A1_src_auto_plan_used"] = "_auto_plan_used" in TXT
out["A2_src_头部两行"] = ("取向判定（plan_orientation）" in TXT
                          and "取向错配" in TXT)
out["A3_src_pack_字段"] = Q + "_auto_plan_used" + Q in TXT

_i = TXT.find("def auto_plan(")
_j = TXT.find(NL + "def ", _i + 10) if _i >= 0 else -1
BODY = TXT[_i:_j] if _i >= 0 and _j > _i else TXT[_i:]
_b1 = ("data.get(" + Q + "orientation" + Q) in BODY
out["B1_单调用_解析orient"] = bool(
    _b1 and BODY.count(Q + "orientation" + Q + ": _ori") >= 2)
out["B2_单调用_prompt要了orient"] = "【取向】" in BODY

# 行为：打桩跑一次
class _Stub:
    def __init__(self):
        self.calls = []

    def call(self, system, user, *a, **kw):
        self.calls.append((system, user))
        import json as _j2
        return _j2.dumps({"mode": "serial", "orientation": "boundary",
                          "rounds": {"0": 4, "1": 4, "both": 4, "all": 5},
                          "reason": "桩", "confidence": 0.9})

    def parse_json(self, raw):
        import json as _j2
        return _j2.loads(raw)


try:
    spec = importlib.util.spec_from_file_location("dgtf_p5", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p5"] = m
    spec.loader.exec_module(m)
    out["C1_模块可加载"] = True
    _s = _Stub()
    _p = m.auto_plan("地铁运营效率该怎么衡量？", dict(m.DEFAULT_CONFIG), llm=_s)
    out["C2_桩_带出orientation"] = _p.get("orientation")
    out["C3_桩_调用次数"] = len(_s.calls)
except Exception as e:
    out["C1_模块可加载"] = "ERR " + type(e).__name__ + ": " + str(e)[:80]
out["D1_真跑产物"] = {
    "p5_auto": (Path("outputs") / "p5_auto" / "meta.json").is_file(),
    "p5_boundary": (Path("outputs") / "p5_boundary" / "meta.json").is_file()}
_js = json.dumps(out, ensure_ascii=False, indent=2)
if OUT:
    from pathlib import Path as _P2
    _P2(OUT).write_bytes(_js.encode("utf-8"))
print(_js)
