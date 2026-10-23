#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 F.4] 生成 P3/P4/P5/P6 四个探针（补齐交付物清单）。

四个探针都是 `python _probe_v1221_pN.py <src.py>` → stdout 打 JSON，用于
before/after 对照。不写反斜杠（换行用 chr(10)，引号用 chr(34)）。
"""
from __future__ import annotations

import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)

P3 = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P3] 探针：仅源码机制负对照（before/after）。

用法：python _probe_v1221_p3.py <src.py>
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
HERE = Path(".").resolve()

MECHS = ("escalate_starve_rounds", "no_push_when_idle", "_reopen_closed_debt",
         "both_tighten_ratio", "_all_settle_streak")

out = {}
out["A1_src_五机制全在"] = {m: (m in TXT) for m in MECHS}
out["A2_negctl_json"] = (HERE / "_negctl_v1221_p3.json").is_file()
out["A3_negctl_doc"] = (HERE / "docs" / "机制负对照-v1221.md").is_file()
out["A4_audit_doc"] = (HERE / "audit_v122_dead_mechanisms.md").is_file()
_j = HERE / "_negctl_v1221_p3.json"
out["B1_negctl_条数"] = None
out["B2_判定分布"] = None
if _j.is_file():
    try:
        d = json.loads(_j.read_text(encoding="utf-8"))
        out["B1_negctl_条数"] = len(d)
        _c = {}
        for v in d.values():
            _c[v.get("verdict")] = _c.get(v.get("verdict"), 0) + 1
        out["B2_判定分布"] = _c
    except Exception as e:
        out["B2_判定分布"] = "ERR " + type(e).__name__
try:
    spec = importlib.util.spec_from_file_location("dgtf_p3", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p3"] = m
    spec.loader.exec_module(m)
    out["C1_模块可加载"] = True
    out["C2_AUDIT122_常量"] = [
        getattr(m, "_AUDIT122_PENDING_FIX", None),
        getattr(m, "_AUDIT122_DUAL_IMPL", None)]
except Exception as e:
    out["C1_模块可加载"] = "ERR " + type(e).__name__ + ": " + str(e)[:80]
import difflib
out["E1_src_名"] = Path(SRC).name


def _pure_del(a_path, b_path):
    """纯删除块（difflib opcode == delete）——红线口径。"""
    try:
        A2 = Path(a_path).read_bytes().decode("utf-8").replace(
            chr(13) + chr(10), NL).split(NL)
        B2 = Path(b_path).read_bytes().decode("utf-8").replace(
            chr(13) + chr(10), NL).split(NL)
    except Exception:
        return None
    sm = difflib.SequenceMatcher(None, A2, B2)
    return sum(i2 - i1 for tag, i1, i2, j1, j2 in sm.get_opcodes()
               if tag == "delete")


out["E2_纯删除(对_v1220)"] = _pure_del("_baseline_v1220.py", SRC)
out["E3_纯删除(对_v12177)"] = _pure_del("_baseline_v12177.py", SRC)
out["D1_不删机制"] = {
    "说明": "见 _v122_verify --phase p3 的 P3.5/P3.6（纯删除 == 0 且符号消失 == 0）"}
_js = json.dumps(out, ensure_ascii=False, indent=2)
if OUT:
    from pathlib import Path as _P2
    _P2(OUT).write_bytes(_js.encode("utf-8"))
print(_js)
'''

P4 = '''#!/usr/bin/env python3
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
'''

P5 = '''#!/usr/bin/env python3
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
'''

P6 = '''#!/usr/bin/env python3
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
'''


def main() -> int:
    for name, body in (("_probe_v1221_p3.py", P3), ("_probe_v1221_p4.py", P4),
                       ("_probe_v1221_p5.py", P5), ("_probe_v1221_p6.py", P6)):
        p = Path(name)
        p.write_bytes(body.encode("utf-8"))
        import ast
        ast.parse(body)
        print("  ✓ " + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
