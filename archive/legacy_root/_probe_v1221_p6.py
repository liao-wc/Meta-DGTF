#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P6] 探针：tier 全缺省时的显式提示。

★ 本档的核心实测：任务书骨架在**已补过缺省 tier** 的容器上数「谁没声明」
  → 计数恒满 → 警告永不触发。正解在补默认值之前判（`_n_explicit_tier`）。

用法：python _probe_v1221_p6.py <src.py>
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
out["A1_src_字段"] = "_anchor_tier_warning" in TXT
out["A2_src_头部行"] = "锚点 tier 警告" in TXT
out["A3_src_pack_字段"] = Q + "_anchor_tier_warning" + Q in TXT
out["A4_src_原始条目计数"] = "_n_explicit_tier" in TXT

_i = TXT.find("def _load_anchors")
_j = TXT.find(NL + "    def ", _i + 10) if _i >= 0 else -1
LB = TXT[_i:_j] if _i >= 0 and _j > _i else TXT[_i:]
out["B1_计数在_load_anchors 内"] = "_n_explicit_tier" in LB
out["B2_在原始条目上判"] = ('a.get(' + Q + 'tier' + Q + ')') in LB

# 行为：全缺省 / 有一条显式
def _write(name, anchors):
    p = Path(name)
    p.write_bytes(json.dumps({"anchors": anchors}, ensure_ascii=False)
                  .encode("utf-8"))
    return p


_notier = _write("_probe_p6_notier.json",
                 [{"id": "a1", "claim": "x"}, {"id": "a2", "claim": "y"}])
_onetier = _write("_probe_p6_onetier.json",
                  [{"id": "a1", "claim": "x"},
                   {"id": "a2", "claim": "y", "tier": 1}])
try:
    spec = importlib.util.spec_from_file_location("dgtf_p6", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p6"] = m
    spec.loader.exec_module(m)
    out["C1_模块可加载"] = True

    def _load(path):
        cfg = json.loads(json.dumps(m.DEFAULT_CONFIG, default=str))
        cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
        cfg["external_anchor"].update({"enabled": True, "path": str(path)})
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["verbose"] = False
        mm = m.MetaDGTF(cfg)
        mm._load_anchors()
        # ★ 属性不存在时回 None（不是非空哨兵串 —— 否则「没这个字段」会被
        #   读成「有警告」，before 侧两格都会假真）。
        return getattr(mm, "_anchor_tier_warning", None)

    _w_all = _load(_notier)
    _w_one = _load(_onetier)
    out["C0_属性存在"] = _w_all is not None
    out["C2_全缺省_警告"] = bool(_w_all)
    out["C3_有tier_警告"] = bool(_w_one)
    _p1 = m.Pool()
    _p1.anchors = [{"id": "a1", "claim": "X"}]
    _p1.anchor_as_evidence = True
    out["C4_无tier_进表"] = any(
        c.startswith("X") for c, _ in m._citation_table(None, _p1))
except Exception as e:
    out["C1_模块可加载"] = "ERR " + type(e).__name__ + ": " + str(e)[:80]
out["D1_真跑产物"] = {
    "p6_notier": (Path("outputs") / "p6_notier" / "meta.json").is_file(),
    "p6_tier": (Path("outputs") / "p6_tier" / "meta.json").is_file()}
for _f in (_notier, _onetier):
    try:
        _f.unlink()
    except OSError:
        pass
_js = json.dumps(out, ensure_ascii=False, indent=2)
if OUT:
    from pathlib import Path as _P2
    _P2(OUT).write_bytes(_js.encode("utf-8"))
print(_js)
