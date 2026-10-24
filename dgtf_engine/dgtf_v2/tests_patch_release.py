# -*- coding: utf-8 -*-
"""V2.2.2 补丁判据：职责终局刷新 / 部分覆盖 C / unsaid 双源闸 / 官方联网默认。

承接 V2.2.1 判据（职责交付面、质量线索降噪、覆盖与三态读数），V2.2.2 新增：
  · C 改为部分覆盖计分（同义表述不再假 0），根治 duty_short 误报；
  · _refresh_duty_final：产物落定后重算四层职责（元层闭合 false 根治）；
  · unsaid_overused 双源闸：单源计数只留痕，模型判逃避/显著超阈才挂旗；
  · 默认联网检索+抓取切到 DeepSeek 官方（backend=deepseek / DGTF_API_KEY）。
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.2.py"


def _load():
    spec = importlib.util.spec_from_file_location("metadgtf_v221", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_v221"] = mod
    spec.loader.exec_module(mod)
    return mod


ENG = _load()
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if info and not ok else ""))


def _fake_engine(entry_view, question):
    eng = object.__new__(ENG.MetaDGTF)
    eng.config = {"duty": {"span_tolerant": True}}
    eng._question = question
    eng._sim_corpus = None
    eng._duty_floor = ENG._DUTY_FLOOR
    return eng


def main():
    ck("版本号按补丁位递增", ENG.__version__ == "2.2.2", ENG.__version__)
    # 融合 provenance 目标版本保持 2.2.0 谱系（补丁不改变融合事实）
    ck("历史融合目标保持 2.2.0", ENG._HF_TARGET == "2.2.0", ENG._HF_TARGET)
    ck("行为融合目标保持 2.2.0", ENG._BEHAVIOR_TARGET == "2.2.0", ENG._BEHAVIOR_TARGET)

    # ── 1. 职责交付面按层取真实产品 ──
    v0 = {"manifest": "修行显形", "threads": [{"desc": "线头A"}]}
    v1 = {"manifest": "研究显形", "decidable_product": {"answer": "答案正文"},
          "sub_questions": [{"answer": "子答"}]}
    vb = {"collision": "碰撞正文", "adjudications": [{"desc": "裁决"}], "manifest": "综合"}
    va = {"manifest": "元显形", "decision": "决策正文", "actions": [{"what": "行动"}],
          "not_do": ["不做1"], "residual_risks": ["残余1"], "meta_closure": {"text": "闭合"}}
    d0 = ENG.duty_deliver_text("0", v0)
    d1 = ENG.duty_deliver_text("1", v1)
    db = ENG.duty_deliver_text("both", vb)
    da = ENG.duty_deliver_text("all", va)
    ck("0 层交付面含 manifest/线头", "修行显形" in d0 and "线头A" in d0, d0[:60])
    ck("1 层交付面含 answer", "答案正文" in d1 and "子答" in d1, d1[:60])
    ck("both 层交付面含碰撞/裁决", "碰撞正文" in db and "裁决" in db, db[:60])
    ck("all 层交付面含决策/行动/残余", "决策正文" in da and "行动" in da and "残余1" in da, da[:60])

    # ── 2. 长问项实词命中 + 下限 ──
    q = "为什么城市热岛效应在夜间比白天更明显？"
    asp = ENG.question_aspects(q)
    good = ("城市热岛效应在夜间更强；白天城乡温差小；夜间边界层稳定，"
            "城市储热释放，郊区辐射冷却快。夜间风弱时更明显。")
    bad = "今天天气不错。我们聊点别的。这里没有任何答句。"
    dg = ENG.duty_components(asp, good, span_tolerant=True)
    dbad = ENG.duty_components(asp, bad, span_tolerant=True)
    ck("相关交付面 C>0", dg["C"] > 0, dg)
    ck("相关交付面 S>=0.3", dg["S"] >= 0.3, dg)
    ck("无关交付面 S<0.3", dbad["S"] < 0.3, dbad)
    ck("缺核心问项被点名", bool(dbad["missing_core"]), dbad["missing_core"])
    dep = ENG.duty_of_layer("0", q, "", floor=None, span_tolerant=True)
    ck("空交付面判 short", dep["short"] is True and dep["floor"] == 0.15, dep)

    # ── 3. 元层按闭合职责判 short ──
    eng = _fake_engine({}, q)
    ns = SimpleNamespace(manifest="元显形", decision="决策正文", actions=[{"what": "行动"}],
                         residual_risks=["残余"], not_do=[],
                         threads=[], decidable_product={}, sub_questions=[],
                         collision="", adjudications=[], meta_closure={},
                         duty_trace=[], rounds_run=2)
    da_all = eng._layer_duty_now("all", ns)
    ck("元层有闭合产品 ⇒ short=False", da_all.get("short") is False, da_all)
    ck("元层职责模式=closure", da_all.get("duty_mode") == "closure", da_all)
    ns2 = SimpleNamespace(manifest="", decision="", actions=[], residual_risks=[],
                          not_do=[], threads=[], decidable_product={}, sub_questions=[],
                          collision="", adjudications=[], meta_closure={},
                          duty_trace=[], rounds_run=1)
    da0 = eng._layer_duty_now("all", ns2)
    ck("元层无闭合产品 ⇒ short=True", da0.get("short") is True, da0)

    # ── 4. quality 覆盖率兜底：无可判定子问题时用方面覆盖 ──
    eng2 = object.__new__(ENG.MetaDGTF)
    eng2.config = {}
    pool = ENG.Pool()
    pool.sub_questions = [
        {"id": 1, "decidability": "undecidable", "status": "open"},
        {"id": 2, "decidability": "undecidable", "status": "open"},
    ]
    eng2.pools = {"1": pool}
    eng2._tri_agree = 0
    eng2._tri_total = 0
    eng2._tri_alpha = {}
    eng2._tri_unreliable = False
    v1ns = SimpleNamespace(quality_flags=[], divergence={}, rounds_run=1,
                           stop_primary="", quality_verdict="",
                           covered_aspects=["a", "b", "c"],
                           uncovered_aspects=["d"])
    rep = eng2._quality_report({"1": v1ns})
    ck("coverage 兜底非空", rep.get("coverage") == 0.75, rep.get("coverage"))
    ck("coverage_basis=undecidable_aspects",
       rep.get("coverage_basis") == "undecidable_aspects", rep.get("coverage_basis"))

    # ── 5. 三态 α 可用时不再用原始一致率冒充质量 ──
    eng2._tri_agree = 1
    eng2._tri_total = 6
    eng2._tri_alpha = {"alpha": 1.0, "kappa": 1.0, "n_units": 6}
    rep2 = eng2._quality_report({"1": v1ns})
    ck("α 可用 ⇒ tri_ratio=None", rep2.get("tri_ratio") is None, rep2.get("tri_ratio"))
    ck("α 可用 ⇒ tri_consistency=α", rep2.get("tri_consistency") == 1.0, rep2.get("tri_consistency"))
    ck("α 可用 ⇒ kind=chance_corrected_alpha",
       rep2.get("tri_ratio_kind") == "chance_corrected_alpha", rep2.get("tri_ratio_kind"))
    ck("原始一致率仍可查", rep2.get("tri_agreement_raw") == 0.1667, rep2.get("tri_agreement_raw"))

    # ── 6. 线索降噪落在源码（结构性一致 / 悬空 link / 后补双源）──
    src = ENGINE.read_text(encoding="utf-8")
    ck("结构性极性不再挂质量旗", "flags.append(f\"polarity_all_same_structural" not in src)
    ck("结构性极性改留痕", "[QC] 池极性全同" in src)
    ck("悬空 link 不再挂质量旗", 'flags.append("probe_link_dangling' not in src)
    ck("悬空 link 改置空留痕", "[QC] 探针 link 悬空" in src)
    ck("收尾复核后补阈值 0.75",
       "_bf_thr" in src and "min(0.9, _QC_BACKFILL_RATIO * 1.5)" in src)
    ck("self-check 双源门槛", "_sc_need" in src)

    # ── 7. V2.2.2：部分覆盖 C / 终局职责刷新 / unsaid 双源闸 / 官方联网默认 ──
    q2 = "为什么城市热岛效应在夜间比白天更明显？"
    asp2 = ENG.question_aspects(q2)
    paraphrase = "夜间城乡温差比白天更大。"
    dp = ENG.duty_components(asp2, paraphrase, span_tolerant=True)
    ck("部分覆盖 C 在 (0,1)", 0 < dp["C"] < 1, dp)
    ck("部分覆盖 S 达到下限", dp["S"] >= ENG._DUTY_FLOOR, dp)
    du = ENG.duty_components(asp2, "今天天气不错。我们聊点别的。", span_tolerant=True)
    ck("无关交付 C 接近 0", du["C"] <= 0.01, du)

    eng3 = _fake_engine({}, q2)
    views = {
        "0": {"manifest": "夜间城乡温差明显，白天差异小。", "threads": [], "rounds_run": 2},
        "1": {"manifest": "", "decidable_product": {"answer": "夜间更强，白天差异小。"},
              "rounds_run": 2},
        "both": {"collision": "夜间城乡温差更强，白天偏弱。", "rounds_run": 3},
        "all": {"decision": "结论", "actions": [{"what": "行动"}],
                "residual_risks": ["风险"], "rounds_run": 3},
    }
    results = {e: SimpleNamespace(quality_flags=["duty_short"], duty_trace=[], duty={})
               for e in views}
    eng3._results = results
    eng3._refresh_duty_final({"views": views, "rounds": {e: 2 for e in views}})
    ck("终局刷新后四层均不 short",
       all((views[e].get("duty") or {}).get("short") is False for e in views),
       {e: views[e].get("duty") for e in views})
    ck("终局刷新清除 duty_short",
       all("duty_short" not in (results[e].quality_flags or []) for e in results))
    ck("元层终局闭合交付", views["all"]["duty"].get("closure_delivered") is True,
       views["all"]["duty"])

    ck("unsaid 单源计数降为留痕", ENG._unsaid_flag_gate(3, 2, False) == "note")
    ck("unsaid 模型判逃避挂旗", ENG._unsaid_flag_gate(3, 2, True) == "flag")
    ck("unsaid 显著超阈挂旗", ENG._unsaid_flag_gate(6, 2, False) == "flag")
    ck("unsaid 未超阈关闭", ENG._unsaid_flag_gate(1, 2, False) == "off")

    ws_def = (ENG.DEFAULT_CONFIG.get("web_search") or {})
    ck("引擎默认联网后端=deepseek", ws_def.get("backend") == "deepseek", ws_def)
    ck("引擎默认联网 key=DGTF_API_KEY",
       ws_def.get("api_key_env") == "DGTF_API_KEY", ws_def)
    ck("官方搜索端点正确",
       ENG.WebSearchClient("deepseek", "")._endpoint()
       == "https://api.deepseek.com/v1/tools/search")
    cfg_path = HERE.parents[1] / "dgtf_config.yaml"
    cfg_txt = cfg_path.read_text(encoding="utf-8", errors="replace")
    ck("主配置联网后端=deepseek", 'backend: "deepseek"' in cfg_txt)
    ck("主配置联网 key=DGTF_API_KEY", 'api_key_env: "DGTF_API_KEY"' in cfg_txt)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
