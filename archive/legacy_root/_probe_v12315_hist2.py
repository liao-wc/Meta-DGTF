# -*- coding: utf-8 -*-
"""v1.23.15 探针：分层抽样 + 时间衰减 + 三条规则的实测校准（零 LLM）。

用法：python _probe_v12315_hist2.py <主文件.py>
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.15.py")
if not SRC.is_absolute():
    SRC = HERE / SRC


def load(p):
    spec = importlib.util.spec_from_file_location("m_v12315", p)
    assert spec is not None and spec.loader is not None, "路径要以 .py 结尾"
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_v12315"] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC)
out = {}
HAS = all(hasattr(mod, x) for x in
          ("_hist_wquant", "_hist_weight", "_hist_decay"))
out["HAS_加权分位"] = HAS

FACT = "新中国的成立时间是什么时候"
DEC = "这份方案怎么落地"

if HAS:
    cfg0 = mod.load_config("")

    # ── A · 分层：每题型上限 ────────────────────────────────
    h = mod._auto_history("outputs", 20, cfg=cfg0)
    out["A_每桶上限"] = h.get("_limit_per_type")
    out["A_事实桶n"] = (h["by_type"]["fact"] or {}).get("n")
    out["A_决策桶n"] = (h["by_type"]["nonfact"] or {}).get("n")
    out["A_两桶都≤上限"] = ((h["by_type"]["fact"] or {}).get("n", 0) <= 20
                          and (h["by_type"]["nonfact"] or {}).get("n", 0) <= 20)
    _h200 = mod._auto_history("outputs", 300, cfg=cfg0)
    out["A_大上限样本更多"] = _h200["n"] > h["n"]
    out["A_半衰期"] = h.get("_half_life_days")

    # ── B · 时间衰减 ────────────────────────────────────────
    import time as _t
    _now = _t.time()
    out["B_权重_同刻"] = mod._hist_weight(_now, 14, _now)
    out["B_权重_一个半衰期"] = mod._hist_weight(_now - 14 * 86400, 14, _now)
    out["B_权重_两个半衰期"] = mod._hist_weight(_now - 28 * 86400, 14, _now)
    out["B_权重_无mtime"] = mod._hist_weight(None, 14, _now)
    out["B_权重_半衰期为0"] = mod._hist_weight(_now - 100 * 86400, 0, _now)
    # 加权分位偏向新样本：两条旧值 100（28 天前）+ 一条新值 10（今天）
    #   ★ 两点分不出来（p50 都落在那一点上），要用**三条**才看得出偏向。
    _old = [(100, mod._hist_weight(_now - 28 * 86400, 14, _now)),
            (100, mod._hist_weight(_now - 28 * 86400, 14, _now))]
    _pairs = _old + [(10, mod._hist_weight(_now, 14, _now))]
    out["B_加权中位"] = mod._hist_wquant(_pairs, .5)
    out["B_等权中位"] = mod._hist_quant([100, 100, 10], .5)
    out["B_衰减后更靠新值"] = mod._hist_wquant(_pairs, .5) < mod._hist_quant(
        [100, 100, 10], .5)
    out["B_半衰期0等于等权"] = mod._hist_wquant(
        [(100, mod._hist_weight(_now - 28 * 86400, 0, _now)),
         (100, mod._hist_weight(_now - 28 * 86400, 0, _now)),
         (10, mod._hist_weight(_now, 0, _now))], .5) == mod._hist_quant(
        [100, 100, 10], .5)

    # ── C · 三态一致率抽取 ──────────────────────────────────
    H2 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
          "**三态判决一致率**：2/6（33%）　其中 4 条分歧已按 partial 计入\n")
    r = mod._hist_from_md(H2)
    out["C_tri"] = r.get("tri")
    H2b = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
           "**三态判决一致率**：0/0（—）\n")
    out["C_分母0不写键"] = "tri" not in mod._hist_from_md(H2b)

    # ── D · 联网行抽取 ──────────────────────────────────────
    H3 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
          "**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条"
          "（W1、W2；2 个环节；tier 3×6）；失败 1 条\n")
    r3 = mod._hist_from_md(H3)
    out["D_web_hit"] = r3.get("web_hit")
    out["D_web_fail"] = r3.get("web_fail")
    H4 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n")
    r4 = mod._hist_from_md(H4)
    out["D_无联网行不写键"] = ("web_hit" not in r4) and ("web_fail" not in r4)

    # ── E · 真实语料读数 ────────────────────────────────────
    out["E_样本数"] = _h200["n"]
    out["E_tri_n"] = _h200["tri_n"]
    out["E_tri_p10"] = _h200["tri_p10"]
    out["E_tri_med"] = _h200["tri_rate"]
    out["E_两桶都非空"] = all((_h200["by_type"][k] or {}).get("n", 0) > 0
                            for k in ("fact", "nonfact"))
    out["E_cut_rate"] = _h200["cut_rate"]
    out["E_stop_n"] = _h200["stop_n"]

    # ── F · 成本档：用实测 p10（不是 0.5），且要够样本 ───────
    _d = mod._auto_features(DEC)
    # ★ 夹具要让「降档」本身**会发生**（类内成本中位 ≥ 全语料 p75），
    #   否则一致率门槛根本观察不到（降不降都是 balanced）。
    _base = {"n": 99, "tokens_p75": 1000, "calls_p75": 999999}
    _expensive = {"n": 30, "tokens_med": 900000, "calls_med": 1}
    _lo = dict(_base, by_type={"nonfact": dict(
        _expensive, tri_n=40, tri_rate=0.10, tri_p10=0.167)})
    out["F_远低于p10则不降"] = mod._auto_pick_cost_profile(_d, _lo, cfg0)[0]
    _ok = dict(_base, by_type={"nonfact": dict(
        _expensive, tri_n=40, tri_rate=0.30, tri_p10=0.167)})
    out["F_0.3高于p10则照降"] = mod._auto_pick_cost_profile(_d, _ok, cfg0)[0]
    _few = dict(_base, by_type={"nonfact": dict(
        _expensive, tri_n=5, tri_rate=0.10, tri_p10=0.167)})
    out["F_样本不足不表态"] = mod._auto_pick_cost_profile(_d, _few, cfg0)[0]

    # ── G · 截断率样本门槛 ──────────────────────────────────
    f = mod._auto_features(FACT)
    _fewstop = {"n": 50, "cut_rate": 0.9, "stop_n": 6}
    # ★ 门槛以下 ⇒ 不用 cut_rate 阻止砍层，落到题型分支（事实短题 ⇒ 0/1/both）
    out["G_门槛以下走题型分支"] = mod._auto_pick_route(f, _fewstop, cfg0)[0]
    _manystop = {"n": 50, "cut_rate": 0.9, "stop_n": 40}
    out["G_层样本足够则不砍"] = mod._auto_pick_route(f, _manystop, cfg0)[1]

for _k in sorted(out):
    print("%-26s = %s" % (_k, out[_k]))
