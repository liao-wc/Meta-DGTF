# -*- coding: utf-8 -*-
"""v1.23.18 前置探针：外部锚点「默认打开」前后的读数对表。

量五类：
  A 出厂值：DEFAULT_CONFIG.external_anchor.enabled / path
  B 行为：enabled=True 且 path 空时 `_load_anchors` 记了什么（error？）
  C 渲染：`_anchor_lane_lines` 在四种状态下的**文本通道**那一行
      （缺失 / 未挂文件 / 已接入 / 接入失败）
  D 产物：无锚点时「锚点明细」块写了几行（改前应是 5 行零）
  E 留痕：事实题 + 联网关时，产物里「未接入外部校验」那段的话术
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.17.py")
spec = importlib.util.spec_from_file_location("m", str(TARGET))
mod = importlib.util.module_from_spec(spec)
sys.modules["m"] = mod
spec.loader.exec_module(mod)

out = {}
_ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
out["A_def_enabled"] = _ea.get("enabled")
out["A_def_path"] = repr(_ea.get("path"))

# ── B 行为：enabled=True 但没给 path ────────────────────────
cfg = mod.load_config(str(HERE / "__nope__.yaml"))
cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
cfg["external_anchor"].update({"enabled": True, "path": ""})
o = object.__new__(mod.MetaDGTF)
o.config = cfg
o.vp = lambda *a, **k: None
try:
    o._load_anchors()
    out["B_err"] = repr(getattr(o, "_anchor_err", None))
    out["B_unconfigured"] = getattr(o, "_anchor_unconfigured", "<无此属性>")
    out["B_anchors"] = len(getattr(o, "_anchors", []) or [])
except Exception as exc:  # noqa: BLE001
    out["B_异常"] = "%s: %s" % (type(exc).__name__, exc)

# ── B2 报告 dict（pack 挂的那个）────────────────────────────
try:
    o._anchor_report = None
    o._anchor_calls = 0
    o._call_budget = 0
    o.decidability_result = None
    o._anchor_source = {}
    o._anchor_answers_warning = ""
    o._anchor_answers_filtered = ""
    o._anchor_tier_warning = ""
    o._anchors = list(getattr(o, "_anchors", []) or [])
    o.pools = {}
    o._call_budget = 0
    rep = o._anchor_crosscheck({"1": {"amps": [], "threads": []}})
    out["B2_enabled"] = rep.get("enabled")
    out["B2_error"] = repr(rep.get("error"))
    out["B2_unconfigured"] = rep.get("unconfigured", "<无此键>")
except Exception as exc:  # noqa: BLE001
    out["B2_异常"] = "%s: %s" % (type(exc).__name__, exc)


def _txt(st):
    r = {"question": "q", "route": ["1"], "keep": {"1": "all"},
         "rounds": {"1": 1},
         "dispatch": {"_parallel_mode": "serial", "order": ["1"]},
         "views": {"1": {}}, "pools": {"1": {}}, "llm_calls": 1, "llm_tokens": 1,
         "decidability": {"decidability": "decidable"},
         "channels": ["content"], "tri_state": [0, 0], "_config": {},
         "_runtime": {"web_enabled": False}}
    r.update(st)
    for l in mod._anchor_lane_lines(r):
        if "文本" in l:
            return l
    return "<没有文本通道那一行>"


# ── C 四种状态 ─────────────────────────────────────────────
out["C_缺失"] = _txt({})
out["C_未挂文件"] = _txt({"external_anchor": {
    "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}})
out["C_已接入"] = _txt({"external_anchor": {
    "enabled": True, "anchors": 3, "source_file": "a.json",
    "retrieved_at": "t0", "error": ""}})
out["C_失败"] = _txt({"external_anchor": {
    "enabled": True, "anchors": 0, "error": "FileNotFoundError: x"}})


# ── D/E 产物 ───────────────────────────────────────────────
def _res(**kw):
    d = {"question": "新中国的成立时间是什么时候", "route": ["1"],
         "keep": {"1": "all"}, "rounds": {"1": 1},
         "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                      "requested": ["1"], "skipped": []},
         "views": {"1": {}}, "pools": {"1": {
             "amps": [], "threads": [], "probes": [], "suspensions": [],
             "meta": [], "sub_questions": [], "deferrals": [],
             "escalations": [], "decidability_log": [], "duel_suspensions": [],
             "duel_alignment": [], "engagements": [], "refinements": [],
             "decidable_channel": [], "undecidable_channel": []}},
         "llm_calls": 1, "llm_tokens": 1,
         "decidability": {"decidability": "decidable"},
         "channels": ["content"], "tri_state": [0, 0], "_config": {}}
    d.update(kw)
    return d


for tag, st in (("D_无锚点", {"external_anchor": {
        "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}}),):
    with tempfile.TemporaryDirectory() as td:
        p = Path(mod.save_result(_res(**st), save_dir=td))
        t = p.read_text(encoding="utf-8")
    for key in ("**锚点对照**", "**锚点分级**", "**triage 降级**",
                "**冲突**", "**锚点入池**", "**锚点异常**"):
        out["%s_%s" % (tag, key.strip("*"))] = key in t

# E 事实题 + 联网关：留痕段
with tempfile.TemporaryDirectory() as td:
    p = Path(mod.save_result(_res(), save_dir=td))
    t = p.read_text(encoding="utf-8")
out["E_有未接入留痕"] = "未接入外部校验" in t
seg = [l for l in t.split("\n") if "未接入外部校验" in l]
out["E_留痕原文"] = (seg[0][:90] if seg else "<无>")

# E2 真跑形态：锚点键在、未挂文件 → 留痕该说「开着但未挂文件」
with tempfile.TemporaryDirectory() as td:
    p2 = Path(mod.save_result(_res(**{"external_anchor": {
        "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}}),
        save_dir=td))
    t2 = p2.read_text(encoding="utf-8")
seg2 = [l for l in t2.split("\n") if "未接入外部校验" in l]
out["E2_留痕原文"] = (seg2[0][:100] if seg2 else "<无>")

for k in sorted(out):
    print("%-24s %s" % (k, out[k]))
