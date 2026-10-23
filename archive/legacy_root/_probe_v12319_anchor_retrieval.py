# -*- coding: utf-8 -*-
"""v1.23.19 前置探针：锚点「真检索」这条路到底够不够得到。

背景：`_retrieve_anchors` 全篇只有 `_anchor_round` 里一处调用，而它在
      `not self._anchors` 这道早退**之后** —— 所以「真检索」只有在**先挂了
      快照文件**时才可能发生。本探针量这件事 + 负对照。

量：
  A 出厂 retriever
  B 行为（桩替换 AnchorRetriever.search 记调用）：tavily / snapshot / web_search
      各跑一次 `_anchor_round`（`_anchors` 空），看：检索被调用几次 / 池里投了几条 /
      `_anchor_err` / 有没有抛异常
  C `_load_anchors` 在 tavily 模式 + 无 path 时会不会被误置「未挂文件」
  D 渲染：未挂文件那句 / 明细「未做」那句，各自给没给**两条**接入方式
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.18.py")
spec = importlib.util.spec_from_file_location("m", str(TARGET))
mod = importlib.util.module_from_spec(spec)
sys.modules["m"] = mod
spec.loader.exec_module(mod)

out = {}
out["A_def_retriever"] = (mod.DEFAULT_CONFIG.get("external_anchor") or {}).get("retriever")

# ── B 行为：桩掉检索实现 ───────────────────────────────────
_rec = {"n": 0, "q": None}
_orig = mod.AnchorRetriever.search


def _stub(self, queries, max_n=12):
    _rec["n"] += 1
    _rec["q"] = list(queries or [])
    return [{"id": "R1", "claim": "真检索条目 1", "tier": 3},
            {"id": "R2", "claim": "真检索条目 2", "tier": 3}]


mod.AnchorRetriever.search = _stub
try:
    for mode in ("tavily", "snapshot", "web_search"):
        _rec.update(n=0, q=None)
        o = object.__new__(mod.MetaDGTF)
        o.config = {"external_anchor": {
            "enabled": True, "path": "", "per_round": 2, "retriever": mode,
            "api_key_env": "TAVILY_API_KEY", "cache_ttl_hours": 24,
            "max_items": 12, "as_evidence": "off", "triage": False}}
        o._anchors = []
        o._anchor_err = ""
        o._anchor_unconfigured = False
        o.vp = lambda *a, **k: None
        o.pools = {"0": mod.Pool()}
        try:
            o._anchor_round("0", o.pools["0"], 0)
            out["B_%s_异常" % mode] = "无"
        except Exception as exc:  # noqa: BLE001
            out["B_%s_异常" % mode] = "%s: %s" % (type(exc).__name__, exc)
        out["B_%s_检索调用" % mode] = _rec["n"]
        out["B_%s_检索后anchors" % mode] = len(o._anchors)
        out["B_%s_池里条数" % mode] = len(o.pools["0"].anchors)
        out["B_%s_err" % mode] = (o._anchor_err or "")[:44]
finally:
    mod.AnchorRetriever.search = _orig

# ── B2 负对照（**不桩**）：未实现后端必须真抛错留痕、不崩、不投池 ──
for mode in ("web_search", "snapshot"):
    _o2 = object.__new__(mod.MetaDGTF)
    _o2.config = {"external_anchor": {
        "enabled": True, "path": "", "per_round": 2, "retriever": mode,
        "api_key_env": "TAVILY_API_KEY", "cache_ttl_hours": 24,
        "max_items": 12, "as_evidence": "off", "triage": False}}
    _o2._anchors = []
    _o2._anchor_err = ""
    _o2._anchor_unconfigured = False
    _o2.vp = lambda *a, **k: None
    _o2.pools = {"0": mod.Pool()}
    try:
        _o2._anchor_round("0", _o2.pools["0"], 0)
        out["B2_%s_异常" % mode] = "无"
    except Exception as exc:  # noqa: BLE001
        out["B2_%s_异常" % mode] = "%s: %s" % (type(exc).__name__, exc)
    out["B2_%s_含尚未实现" % mode] = "尚未实现" in (_o2._anchor_err or "")
    out["B2_%s_池里条数" % mode] = len(_o2.pools["0"].anchors)

# ── C unconfigured：snapshot vs tavily ─────────────────────
for mode in ("snapshot", "tavily"):
    _c = mod.load_config(str(HERE / "__nope__.yaml"))
    _c["external_anchor"] = dict(_c.get("external_anchor") or {})
    _c["external_anchor"].update({"enabled": True, "path": "", "retriever": mode})
    _o = object.__new__(mod.MetaDGTF)
    _o.config = _c
    _o.vp = lambda *a, **k: None
    _o._load_anchors()
    out["C_%s_unconfigured" % mode] = getattr(_o, "_anchor_unconfigured", "<无>")
    out["C_%s_err" % mode] = repr(getattr(_o, "_anchor_err", None))[:40]

# ── D 渲染 ────────────────────────────────────────────────
_oneline = [l for l in mod._anchor_lane_lines({"external_anchor": {
    "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}})
    if "文本" in l]
out["D_未挂文件_给两条路"] = bool(_oneline) and ("path" in _oneline[0]
                                          and "tavily" in _oneline[0])
out["D_未挂文件_原文"] = (_oneline[0] if _oneline else "<无>")[:150]

out["D2_明细_给两条路"] = ("tavily" in (mod.__doc__ or "") or True)  # 占位，见下
try:
    import tempfile
    _res = {"question": "新中国的成立时间是什么时候", "route": ["1"],
            "keep": {"1": "all"}, "rounds": {"1": 1},
            "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                         "requested": ["1"], "skipped": []},
            "views": {"1": {}}, "pools": {"1": {
                "amps": [], "threads": [], "probes": [], "suspensions": [],
                "meta": [], "sub_questions": [], "deferrals": [],
                "escalations": [], "decidability_log": [],
                "duel_suspensions": [], "duel_alignment": [],
                "engagements": [], "refinements": [],
                "decidable_channel": [], "undecidable_channel": []}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "tri_state": [0, 0], "_config": {},
            "external_anchor": {"enabled": True, "unconfigured": True,
                                "anchors": 0, "error": ""}}
    with tempfile.TemporaryDirectory() as td:
        _t = Path(mod.save_result(_res, save_dir=td)).read_text(encoding="utf-8")
    _seg = [l for l in _t.split("\n") if "锚点对照" in l]
    out["D2_明细_给两条路"] = bool(_seg) and ("tavily" in _seg[0])
    out["D2_明细_原文"] = (_seg[0] if _seg else "<无>")[:150]
except Exception as exc:  # noqa: BLE001
    out["D2_异常"] = "%s: %s" % (type(exc).__name__, exc)

for k in sorted(out):
    print("%-26s %s" % (k, out[k]))
