#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前置量化探针 · v1.21.70（F/K/G/H/I/J 六项）

用法：
    python _probe_v70_six.py 元DGTF-V1.21.69.py > _probe_v70_before.txt
    python _probe_v70_six.py 元DGTF-V1.21.70.py > _probe_v70_after.txt

★ 每项都走**生产入口**（Pool.add_undecidable / DGTF._re_anchor /
  DGTF.dump_round / MetaDGTF._merge_decidability /
  MetaDGTF._finalize_layer_common / save_result），不手造中间结构。
★ 全部离线：LLM 一律换成桩，绝不联网。
"""
import contextlib
import importlib.util
import inspect
import io
import json
import re
import sys
import tempfile
from pathlib import Path

TARGET = Path(sys.argv[1]).resolve()
HERE = TARGET.parent

spec = importlib.util.spec_from_file_location("dgtf_probe", str(TARGET))
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe"] = mod
spec.loader.exec_module(mod)

CFG = mod.load_config(str(HERE / "__nonexistent__.yaml"))
CFG["api"]["key"] = "sk-probe"
CFG["output"]["verbose"] = False

REPORT = {}


def _sec(name):
    print("\n" + "=" * 62)
    print(f"## {name}")
    print("=" * 62)


# ======================================================================
# [F] struct_trace / aspect_first_hit 与 B 口径对齐
# ======================================================================
_sec("[F] 轨迹是否拆成两条（structural / aligned）")
_p = mod.Pool()
# ★ 方面必须够长：`_kw("A")` 是空集（单字被 jieba 过滤）⇒ 单字方面永远撞不上，
#   用它做样例会把"闸门没坏"误读成"闸门坏了"。
_ASPECTS = ["时间尺度结论相反且无仲裁规则",
            "档案与记忆两份留痕之差不可对撞消掉"]
_PROD = {"structural_amps": ["毫不相干的一段"],
         "aligned_amps": [_ASPECTS[0]],
         "clarity": 0.5}
for _ly in (1, 2):
    _p.add_undecidable(dict(_PROD), list(_ASPECTS), layer=_ly)
_ch = _p.undecidable_channel
F = {
    "trace_keys": sorted(k for k in _ch if "trace" in k),
    "first_hit_keys": sorted(k for k in _ch if "first_hit" in k),
    "struct_trace_len": len(_ch.get("struct_trace") or []),
    "aligned_trace_len": len(_ch.get("aligned_trace") or []),
    "aspect_first_hit": _ch.get("aspect_first_hit"),
    "aligned_first_hit": _ch.get("aligned_first_hit"),
    "last_struct_coverage": _ch.get("last_struct_coverage"),
    "last_aligned_coverage": _ch.get("last_aligned_coverage"),
}
REPORT["F"] = F
for k, v in F.items():
    print(f"   {k} = {v!r}")

# 渲染出口
_fake = {
    "question": "轨迹渲染探针",
    "route": ["0", "1"], "keep": {"1": "all"}, "rounds": {"1": 2},
    "dispatch": {"_parallel_mode": "serial", "order": ["0", "1"],
                 "requested": ["0", "1"], "skipped": []},
    "views": {},
    "pools": {"1": {"amps": [], "threads": [], "probes": [],
                    "suspensions": [], "meta": [],
                    "sub_questions": [], "deferrals": [],
                    "escalations": [], "decidability_log": [],
                    "duel_suspensions": [],
                    "undecidable_channel": _ch}},
    "llm_calls": 1, "llm_tokens": 1,
    "decidability": {"decidability": "decidable"},
    "channels": ["content"], "cost_profile": "balanced",
    "orientation": "auto", "tri_state": [0, 0],
}
with tempfile.TemporaryDirectory() as _td:
    _md = mod.save_result(_fake, save_dir=_td)
    _txt = _md.read_text(encoding="utf-8").replace("\r\n", "\n")
_lines = [ln.strip() for ln in _txt.split("\n") if "覆盖轨迹" in ln]
F["render_lines"] = _lines
print(f"   渲染出的覆盖轨迹行（{len(_lines)} 行）：")
for _ln in _lines:
    print(f"      {_ln}")

# ======================================================================
# [K] 覆盖率段的触发时机
# ======================================================================
_sec("[K] _coverage_segment 在哪些 entry 收尾时被调")
_SENT = "SENTINEL_COVERAGE"
for _e in ("1", "all"):
    _m = mod.MetaDGTF(CFG)
    _m._coverage_segment = lambda: ("\n\n## 七、原始问题覆盖率\n" + _SENT)
    _orig_qc = mod.DGTF._quality_check
    mod.DGTF._quality_check = lambda self, *a, **k: []
    try:
        _v = mod.View(entry=_e)
        _st = {"roles_hist": ["摊开", "转向"], "total_rounds": 2,
               "round_log": [], "all_rehashed": [], "all_candidates": [],
               "all_amps": [], "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 2, "rounds_n": 2, "sp": mod._spiral_for(CFG, _e)}
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _m._finalize_layer_common(_e, _v, _st)
        _hit = _SENT in (_v.manifest or "")
    finally:
        mod.DGTF._quality_check = _orig_qc
    REPORT.setdefault("K", {})[f"entry={_e}"] = _hit
    print(f"   entry={_e:5s} 收尾后 manifest 含覆盖率段：{_hit}")

# ======================================================================
# [G] _re_anchor 的占位符闸门
# ======================================================================
_sec("[G] 锚点重述的 touched/untouched 是否挡占位符")


class _StubLLM:
    def __init__(self, payload):
        self.payload = payload

    def call(self, *a, **k):
        return json.dumps(self.payload, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def _run_anchor(payload):
    _dg = mod.DGTF("0", mod.LLM(CFG), CFG)
    _dg.verbose = False
    _dg.llm = _StubLLM(payload)
    _inp = mod.Input(question="原始问题", round_role="摊开", round_no=1)
    _inp.pool = mod.Pool()
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        _a, _t, _u = _dg._re_anchor(_inp)
    return _t, _u


_t1, _u1 = _run_anchor({"anchor": "x",
                        "touched": ["此处未生", "正常方面"],
                        "untouched": ["（无）", "另一个方面"]})
_t2, _u2 = _run_anchor({"anchor": "x",
                        "touched": ["此处未生", "（无）"],
                        "untouched": ["(此处未生)", "无", "N/A"]})
G = {"case1_touched": _t1, "case1_untouched": _u1,
     "case2_touched": _t2, "case2_untouched": _u2}
REPORT["G"] = G
for k, v in G.items():
    print(f"   {k} = {v!r}")

# ======================================================================
# [H] dump_view_fields 对超大覆盖型字段的处理
# ======================================================================
_sec("[H] rendered / manifest 是否只打长度")
_dg = mod.DGTF("0", mod.LLM(CFG), CFG)
_dg.verbose = True
_v = mod.View(entry="0")
_v.rendered = "a" * 5000
_v.manifest = "m" * 3000
_v.candidates = [{"desc": "候选甲", "attribute": "0", "position": "0"}]
_inp = mod.Input(question="q", round_role="摊开", round_no=1)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _dg.dump_round(_v, _inp)
_out = _buf.getvalue()
H = {
    "out_chars": len(_out),
    "has_rendered_lenline": bool(re.search(r"rendered：str 5000 字", _out)),
    "has_manifest_lenline": bool(re.search(r"manifest：str 3000 字", _out)),
    "leaks_rendered_body": ("a" * 50) in _out,
    "leaks_manifest_body": ("m" * 50) in _out,
    "field_line_count": _out.count("   \u251c "),
}
REPORT["H"] = H
for k, v in H.items():
    print(f"   {k} = {v!r}")

# 负对照：非超大字段的正文仍必须在
_v2 = mod.View(entry="0")
_v2.collision = "ing 正文" * 30
_buf2 = io.StringIO()
with contextlib.redirect_stdout(_buf2):
    _dg.dump_round(_v2, _inp)
_out2 = _buf2.getvalue()
H["collision_body_kept"] = ("ing 正文" * 30) in _out2.replace("\n", "").replace(
    "   \u2502 ", "")
print(f"   负对照 · collision 正文仍在留痕里：{H['collision_body_kept']}")

# ======================================================================
# [I] dump_round 顶部的「本圈留痕」说明
# ======================================================================
_sec("[I] dump_round 是否有本圈留痕说明")
I = {"note_in_output": "本段是**本圈**留痕" in _out,
     "note_in_source": "本段是**本圈**留痕" in inspect.getsource(
         mod.DGTF.dump_round)}
REPORT["I"] = I
for k, v in I.items():
    print(f"   {k} = {v!r}")

# ======================================================================
# [J] _merge_decidability 复用 _und_untraced
# ======================================================================
_sec("[J] 合并时是否复用池评估算好的 _und_untraced")
_mt = mod.MetaDGTF(CFG)
_SRC_MERGE = inspect.getsource(mod.MetaDGTF._merge_decidability)
_pool_ok = {"decidability": "undecidable",
            "undecidable_aspects": ["凭空说的一条"],
            "evidence": [{"aspect": "完全不相干的另一条"}],
            "_und_untraced": ["CACHED_SENTINEL"]}
_ext = {"decidability": "undecidable", "decidable_aspects": [],
        "undecidable_aspects": [], "reason": "", "features": []}
_r1 = _mt._merge_decidability(dict(_pool_ok), dict(_ext))
_pool_nocache = {"decidability": "undecidable",
                 "undecidable_aspects": ["凭空说的一条"],
                 "evidence": [{"aspect": "完全不相干的另一条"}]}
try:
    _r2 = _mt._merge_decidability(dict(_pool_nocache), dict(_ext))
    _r2_ut = _r2.get("_und_untraced")
except Exception as _e:      # 不许崩
    _r2_ut = f"EXC:{type(_e).__name__}:{_e}"
J = {
    "cached_used": _r1.get("_und_untraced") == ["CACHED_SENTINEL"],
    "merged_und_untraced": _r1.get("_und_untraced"),
    "fallback_without_cache": _r2_ut,
    "source_reads_cache": 'pool_res.get("_und_untraced")' in _SRC_MERGE,
}
REPORT["J"] = J
for k, v in J.items():
    print(f"   {k} = {v!r}")

# 池评估侧确实产出这个键（J 依赖的前提）
_assess_src = inspect.getsource(mod.MetaDGTF._assess_decidability_from_pool_view)
J["pool_assess_emits_key"] = '"_und_untraced"' in _assess_src
print(f"   前提 · 池评估返回值里带 _und_untraced："
      f"{J['pool_assess_emits_key']}")

print("\n" + "=" * 62)
print("## 摘要（机器可读）")
print("=" * 62)
print(json.dumps(REPORT, ensure_ascii=False, indent=1, default=str))
