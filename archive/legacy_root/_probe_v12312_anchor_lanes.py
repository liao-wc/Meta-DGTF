# -*- coding: utf-8 -*-
"""v1.23.12 探针：外部锚点两条通道（文本 `/` 联网）是否**分别写明**。

驱动方式（零 LLM）：直接把 result 喂 `save_result` / `render_landing` /
`render_manifestation`，读回产物 md。真实数据用 v1.23.11 真跑的
`*.packed.json`（联网收了 6 条、锚点文件没有）—— 这正是「读者看不到」的原始场景。

用法：python _probe_v12312_anchor_lanes.py <主文件.py>
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.12.py")
if not SRC.is_absolute():
    SRC = HERE / SRC


def load(p):
    spec = importlib.util.spec_from_file_location("m_v12312", p)
    assert spec is not None and spec.loader is not None, "spec 为 None（路径要以 .py 结尾）"
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_v12312"] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC)
HAS = hasattr(mod, "_anchor_lane_lines")
out = {}
out["HAS_函数"] = HAS


def lanes(txt):
    """从一段文本里取出两条通道行（新实现有；旧实现只有一条）。"""
    got = {"文本": "**外部锚点 · 文本**" in txt,
           "联网": "**外部锚点 · 联网**" in txt,
           "旧单通道": "**外部锚点**：无（本产物不含外部事实校验" in txt
                       or "**外部锚点**：已接入" in txt
                       or "**外部锚点**：本次没有接入" in txt}
    return got


def render_all(res):
    """返回 (产物 md, 头部片段, 显化说明片段, 落地层片段)。"""
    with tempfile.TemporaryDirectory() as td:
        p = mod.save_result(res, save_dir=td)
        t = Path(p).read_text(encoding="utf-8")
    man = mod.render_manifestation(res)
    land = mod.render_landing(res)
    head = "\n".join(t.split("\n")[:90])
    return t, head, man, land


# ── A · 真实真跑快照（联网 6 条、锚点文件无）────────────────────
PK = sorted(HERE.glob("outputs/*.packed.json"),
            key=lambda q: q.stat().st_mtime)
if PK:
    real = json.loads(PK[-1].read_text(encoding="utf-8"))
    out["A_真实快照"] = PK[-1].name
    out["A_真实联网条数"] = sum(
        len((pp or {}).get("web_results") or [])
        for pp in (real.get("pools") or {}).values())
    t, head, man, land = render_all(real)
    for _k, _v in lanes(t).items():
        out["A_产物_%s" % _k] = _v
    for _k, _v in lanes(man).items():
        out["A_显化_%s" % _k] = _v
    for _k, _v in lanes(land).items():
        out["A_落地_%s" % _k] = _v
    out["A_落地有七节"] = "### 七、外部锚点（两条通道分开记账）" in land
    out["A_头部含收6条"] = "收 6 条" in head
    out["A_头部含W1"] = "W1" in head
else:
    out["A_真实快照"] = "（无 packed 快照）"


def pool(**x):
    p = {"amps": [], "threads": [], "probes": [], "suspensions": [], "meta": [],
         "sub_questions": [], "deferrals": [], "escalations": [],
         "decidability_log": [], "duel_suspensions": [], "duel_alignment": [],
         "engagements": [], "refinements": [], "decidable_channel": [],
         "undecidable_channel": []}
    p.update(x)
    return p


def fake(q, **kw):
    d = {"question": q, "route": ["1"], "keep": {"1": "all"},
         "rounds": {"1": 1},
         "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                      "requested": ["1"], "skipped": []},
         "views": {"1": {}},
         "pools": {"1": pool()},
         "llm_calls": 1, "llm_tokens": 1,
         "decidability": {"decidability": "decidable"},
         "channels": ["content"], "tri_state": [0, 0],
         "_config": {}}
    d.update(kw)
    return d


FACT = "新中国的成立时间是什么时候"
DEC = "这份方案怎么落地"

# ── B · 无 _runtime（未记录）+ 无锚点 ─────────────────────────
_b = fake(FACT)
_tb, _hb, _mb, _lb = render_all(_b)
out["B_未记录_联网行"] = "**外部锚点 · 联网**" in _tb
out["B_未记录_含未记录"] = "未记录" in _tb
out["B_无锚点_含无"] = "**外部锚点 · 文本**（锚点文件 `external_anchor`）：无" in _tb
out["B_事实题留痕"] = "未接入外部校验" in _tb and "--web on" in _tb

# ── C · 联网开 + 6 条 + 锚点文件 3 条 ─────────────────────────
_c = fake(FACT, **{
    "_runtime": {"web_enabled": True},
    "pools": {"1": pool(web_results=[
        {"id": "W%d" % i, "stage": ("research_decompose" if i <= 3
                                    else "research_evidence"),
         "tier": 3} for i in range(1, 7)], web_errors=[])},
    "external_anchor": {
        "anchors": 3, "source_file": "anchor.json", "retrieved_at": "t0",
        "as_evidence": "partial",
        "summary": {"claims": 2, "supported": 1, "conflicted": 0,
                    "unmatched": 1}},
})
_tc, _hc, _mc, _lc = render_all(_c)
out["C_文本_已接入3"] = "已接入 3 条" in _tc
out["C_锚点对照明细"] = "**锚点对照**：结论 2 条" in _tc
out["C_锚点分级"] = "**锚点分级**：partial" in _tc
out["C_triage降级"] = "**triage 降级**：0 条" in _tc
out["C_锚点入池"] = "**锚点入池**" in _tc
out["C_联网_开"] = "**外部锚点 · 联网**（`web_search`）：**开**" in _tc
out["C_联网_收6条"] = "收 6 条" in _tc
out["C_联网_环节2"] = "2 个环节" in _tc
out["C_联网_失败0"] = "失败 0 条" in _tc
out["C_联网开_不提示未接入"] = "未接入外部校验" not in _tc

# ── D · 联网关（含失败留痕）──────────────────────────────────
_d = fake(FACT, **{
    "_runtime": {"web_enabled": False},
    "pools": {"1": pool(web_errors=[{"kind": "rate", "stage": "x"}])},
})
_td, _hd, _md, _ld = render_all(_d)
out["D_联网_关"] = "**外部锚点 · 联网**（`web_search`）：**关**" in _td
out["D_事实题_指路"] = "未接入外部校验" in _td and "--web on" in _td
out["D_联网关_不报已接入"] = "已接入 3 条" not in _td

# ── E · 决策题 + 联网关 → 不提示 ─────────────────────────────
_e = fake(DEC, **{"_runtime": {"web_enabled": False}})
_te, _he, _me, _le = render_all(_e)
out["E_决策题_不提示"] = "未接入外部校验" not in _te
out["E_决策题_仍有两条"] = ("**外部锚点 · 文本**" in _te
                            and "**外部锚点 · 联网**" in _te)

# ── F · 锚点文件异常 ────────────────────────────────────────
_f = fake(FACT, **{
    "_runtime": {"web_enabled": True},
    "external_anchor": {"anchors": 0, "error": "FileNotFoundError: x"},
})
_tf, _hf, _mf, _lf = render_all(_f)
out["F_锚点异常"] = "**锚点异常**：" in _tf
out["F_异常仍写联网"] = "**外部锚点 · 联网**" in _tf

# ── G · 联网开 + 收 0 条（空结果）──────────────────────────
_g = fake(FACT, **{"_runtime": {"web_enabled": True},
                   "pools": {"1": pool(web_results=[], web_errors=[])}})
_tg, _hg, _mg, _lg = render_all(_g)
out["G_联网开_收0条"] = "**开** —— 收 0 条" in _tg

# ── H · 4 处调用点都出现两条通道 ─────────────────────────────
for _k, _v in lanes(_hc).items():
    out["H_头部_%s" % _k] = _v
for _k, _v in lanes(_mc).items():
    out["H_显化_%s" % _k] = _v
for _k, _v in lanes(_lc).items():
    out["H_落地_%s" % _k] = _v
out["H_落地_有七节"] = "### 七、外部锚点（两条通道分开记账）" in _lc
out["H_落地_两模板都有"] = (
    ("### 七、外部锚点（两条通道分开记账）" in mod.render_landing(_c))
    and ("### 七、外部锚点（两条通道分开记账）"
         in mod.render_landing(dict(_c, orientation="boundary"))))

# ── 统计函数（旧版没有 → 记 NA）────────────────────────────
if HAS:
    _s = mod._web_lane_stats(_c)
    out["S_stats_ok"] = _s["ok"]
    out["S_stats_ids"] = "、".join(_s["ids"])
    out["S_stats_环节"] = len(_s["stages"])
    out["S_stats_tier"] = "/".join("%s×%d" % (k, v)
                                   for k, v in _s["tiers"].items())
    out["S_stats_errs"] = len(_s["errs"])
    out["S_stats_enabled"] = _s["enabled"]

for _k in sorted(out):
    print("%-24s = %s" % (_k, out[_k]))
