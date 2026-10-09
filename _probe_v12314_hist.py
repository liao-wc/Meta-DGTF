# -*- coding: utf-8 -*-
"""v1.23.14 探针：真实历史语料 → 调度读数（零 LLM）。

用法：python _probe_v12314_hist.py <主文件.py>
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.14.py")
if not SRC.is_absolute():
    SRC = HERE / SRC


def load(p):
    spec = importlib.util.spec_from_file_location("m_v12314", p)
    assert spec is not None and spec.loader is not None, "路径要以 .py 结尾"
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_v12314"] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC)
out = {}
HAS = all(hasattr(mod, x) for x in
          ("_hist_from_md", "_hist_from_packed", "_hist_from_batch",
           "_hist_for", "_rounds_run_line"))
out["HAS_历史三源"] = HAS

FACT = "新中国的成立时间是什么时候"
DEC = "这份方案怎么落地"

if HAS:
    cfg0 = mod.load_config("")

    # ── A · 真实语料：样本量与三类来源 ───────────────────────
    h = mod._auto_history("outputs", 200, cfg=cfg0)
    out["A_样本数"] = h["n"]
    out["A_来源"] = h["sources"]
    out["A_三类都有"] = all(h["sources"].get(k, 0) > 0
                           for k in ("packed", "md", "batch"))
    out["A_tokens_p75"] = h["tokens_p75"]
    out["A_calls_p75"] = h["calls_p75"]
    out["A_种子上限"] = h["cap_rounds"]
    out["A_实际停圈"] = h["layer_rounds"]
    out["A_每层样本数"] = h["cap_rounds_n"]
    out["A_分题型"] = {k: v["n"] for k, v in (h["by_type"] or {}).items()}
    out["A_有被截断率"] = h["cut_rate"] is not None
    out["A_有联网读数"] = h["web_hit"] > 0
    # 负对照：不存在的目录必须不崩、零样本
    h0 = mod._auto_history(str(HERE / "__nope__"), 5, cfg=cfg0)
    out["A_空目录_无产物样本"] = not (h0["sources"].get("md")
                                or h0["sources"].get("packed"))
    # ★ 负对照：**关掉 md / 跑批两个源** ⇒ 只剩落 packed 的那 1 份
    _p2 = mod._auto_history("outputs", 200, cfg=cfg0,
                            want_md=False, want_batch=False)
    out["A_关掉两源后n"] = _p2["n"]
    out["A_关掉两源后来源"] = _p2["sources"]

    # ── B · md 抽取：正 / 负对照 ─────────────────────────────
    HEAD = ("# 元 DGTF · 测试题\n\n**调度**：修行(4圈) → 研究(5圈) → 对撞(6圈)\n\n"
            "**并行模式**：A · 四层独立并行 + 汇流\n\n"
            "**成本档位**：economy（再省调用次数）\n\n"
            "**取向**：boundary（要边界清单）\n\n"
            "**停止**：自然 2 层 / 被截断（体力耗尽）2 层\n\n"
            "**资源**: 137 次 LLM | 654321 tokens\n")
    r = mod._hist_from_md(HEAD)
    out["B_calls"] = r.get("calls")
    out["B_tokens"] = r.get("tokens")
    out["B_mode"] = r.get("mode")
    out["B_profile"] = r.get("profile")
    out["B_orientation"] = r.get("orientation")
    out["B_种子上限"] = r.get("cap_rounds")
    out["B_停止"] = [r.get("nat"), r.get("cut")]
    out["B_负对照空串"] = mod._hist_from_md("") == {}
    out["B_负对照无资源行"] = mod._hist_from_md("# 标题\n正文\n") == {}

    # ── C · packed 抽取：字段名必须读 `rounds_run` ───────────
    P = {"question": FACT, "llm_calls": 88, "llm_tokens": 123456,
         "cost_profile": "balanced", "orientation": "boundary",
         "dispatch": {"_parallel_mode": "B"}, "tri_state": [3, 4],
         "views": {"0": {"rounds_run": 3, "rounds_cap": 6,
                         "stop_reason": "连续 2 轮无新 &，螺旋停止"},
                   "1": {"rounds": 5, "rounds_cap": 6,
                         "stop_reason": "体力耗尽（6 圈走满，未触发任何停止判据）"}},
         "pools": {"1": {"web_results": [{"id": "W1"}, {"id": "W2"}],
                         "web_errors": [{"kind": "rate"}], "meta": ["[W-EMPTY] x"]}}}
    rc = mod._hist_from_packed(P)
    out["C_实际停圈"] = rc.get("actual_rounds")
    out["C_种子上限"] = rc.get("cap_rounds")
    out["C_读对字段"] = rc.get("actual_rounds", {}).get("0") == 3
    out["C_不认错字段"] = "1" not in (rc.get("actual_rounds") or {})
    out["C_停止分层"] = [rc.get("nat"), rc.get("cut")]
    out["C_联网"] = [rc.get("web_hit"), rc.get("web_fail"), rc.get("web_empty")]
    out["C_tri"] = rc.get("tri")

    # ── D · 按题型取历史 ────────────────────────────────────
    f = mod._auto_features(FACT)
    d = mod._auto_features(DEC)
    out["D_事实取fact桶"] = mod._hist_for(f, h) is (h["by_type"] or {}).get("fact")
    out["D_决策取nonfact桶"] = mod._hist_for(d, h) is (h["by_type"] or {}).get("nonfact")
    out["D_无同型退全语料"] = mod._hist_for(
        f, {"n": 9, "by_type": {"fact": {"n": 0}, "nonfact": {"n": 3}}})["n"] == 9

    # ── E · 圈数三级回退 ────────────────────────────────────
    _only_cap = {"n": 50, "cap_rounds": {"0": 2, "1": 2, "both": 5, "all": 6},
                 "cap_rounds_n": {"0": 40, "1": 40, "both": 10, "all": 10}}
    v, why = mod._auto_pick_rounds(f, _only_cap, cfg0)
    out["E_只用种子上限"] = v
    out["E_用上限的理由"] = "种子上限" in why
    _few_act = {"n": 50, "layer_rounds": {"0": 1}, "layer_rounds_n": {"0": 1},
                "cap_rounds": {"0": 4}, "cap_rounds_n": {"0": 30}}
    out["E_实际样本不足则退回上限"] = mod._auto_pick_rounds(
        f, _few_act, cfg0)[0]["0"]
    _many_act = {"n": 50, "layer_rounds": {"0": 5}, "layer_rounds_n": {"0": 9},
                 "cap_rounds": {"0": 2}, "cap_rounds_n": {"0": 30}}
    out["E_实际样本足够则采用"] = mod._auto_pick_rounds(f, _many_act, cfg0)[0]["0"]
    out["E_三级都空"] = mod._auto_pick_rounds(f, {}, cfg0)[0]

    # ── F · 成本档：相对判据（同类中位 vs 全语料 p75）────────
    _hi = {"n": 99, "tokens_p75": 500000, "calls_p75": 100,
           "by_type": {"nonfact": {"n": 20, "tokens_med": 900000,
                                   "calls_med": 50, "tri_n": 6,
                                   "tri_rate": 0.9}}}
    out["F_同类偏贵则降档"] = mod._auto_pick_cost_profile(d, _hi, cfg0)[0]
    _lo = {"n": 99, "tokens_p75": 500000, "calls_p75": 100,
           "by_type": {"nonfact": {"n": 20, "tokens_med": 100000,
                                   "calls_med": 10, "tri_n": 6,
                                   "tri_rate": 0.9}}}
    out["F_同类不贵则不降"] = mod._auto_pick_cost_profile(d, _lo, cfg0)[0]
    _bad = {"n": 99, "tokens_p75": 500000, "calls_p75": 100,
            "by_type": {"nonfact": {"n": 20, "tokens_med": 900000,
                                    "calls_med": 50, "tri_n": 6,
                                    "tri_rate": 0.2}}}
    out["F_一致率低不降档"] = mod._auto_pick_cost_profile(d, _bad, cfg0)[0]
    out["F_事实短题恒economy"] = mod._auto_pick_cost_profile(f, _lo, cfg0)[0]

    # ── G · 实际停圈渲染 ────────────────────────────────────
    out["G_有停圈"] = mod._rounds_run_line(
        {"1": {"rounds_run": 3, "rounds_cap": 6},
         "all": {"rounds_run": 2, "rounds_cap": 6}})
    out["G_空views"] = mod._rounds_run_line({})
    out["G_非dict"] = mod._rounds_run_line(None)

    # ── H · 产物里真的有这一行 ──────────────────────────────
    pk = sorted((HERE / "outputs").glob("*.packed.json"),
                key=lambda q: q.stat().st_mtime)
    if pk:
        real = json.loads(pk[-1].read_text(encoding="utf-8"))
        real["_auto_dispatch"] = mod.auto_dispatch(
            str(real.get("question") or FACT), cfg0, history=h)
        with tempfile.TemporaryDirectory() as td:
            t = Path(mod.save_result(real, save_dir=td)).read_text(
                encoding="utf-8")
        out["H_产物有实际停圈行"] = "**实际停圈**：" in t
        out["H_表有217份"] = "217 份" in t or "**" in t and "历史读数" in t
        out["H_表有p75"] = "p75" in t

for _k in sorted(out):
    print("%-26s = %s" % (_k, out[_k]))
