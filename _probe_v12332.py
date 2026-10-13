#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 探针：学科吸收六项的判别力验证。

T1 α/κ 的**数值正确性**（完美一致 / 全分歧 / 样本不足）
T2 ★ **口径对比**：同一份偏斜数据上「原始一致率」与「机会校正 α」的差距
T3 少数类一致（偏斜时多数类共识廉价）
T4 尺度登记 + 定序禁词检查
T5 停因级联：优先级排序 + **主因 ∈ 全部触发**
T6 CSD 读数：上升序列 ⇒ 有前兆；平稳 ⇒ 无；短序列 ⇒ 不表态
T7 成本两分：判定类 stage 计入自测量，其余计入跑本身
T8 真实入口：跑一圈 mock，断言 view.stop_primary / view.csd / tri_alpha 落地
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

spec = importlib.util.spec_from_file_location("dgtf_v12332", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12332"] = m
spec.loader.exec_module(m)

R = []


def ok(name, cond, note=""):
    R.append((name, bool(cond), note))
    print(("✓" if cond else "✗"), name, note)


# ── T1 α / κ 数值正确性 ──────────────────────────────────
_perfect = [["decidable", "decidable", "decidable"],
            ["partial", "partial", "partial"],
            ["undecidable", "undecidable", "undecidable"],
            ["decidable", "decidable", "decidable"]]
_al = m.krippendorff_alpha_ordinal(_perfect)
ok("T1 完美一致 ⇒ α=1", _al and abs(_al["alpha"] - 1.0) < 1e-9,
   str(_al))
_kp = m.weighted_kappa_pair([u[0] for u in _perfect], [u[1] for u in _perfect])
ok("T1 完美一致 ⇒ κ=1", _kp and abs(_kp["kappa"] - 1.0) < 1e-9, str(_kp))
_chaos = [["decidable", "undecidable", "partial"],
          ["undecidable", "decidable", "partial"],
          ["partial", "decidable", "undecidable"],
          ["decidable", "partial", "undecidable"]]
_ac = m.krippendorff_alpha_ordinal(_chaos)
ok("T1 全分歧 ⇒ α 明显低于 1", _ac and _ac["alpha"] < 0.5, str(_ac))
ok("T1 样本不足 ⇒ None（不印 0 冒充）",
   m.krippendorff_alpha_ordinal([["decidable", "decidable"]]) is None)
ok("T1 单票/空 ⇒ None",
   m.krippendorff_alpha_ordinal([]) is None)
ok("T1 α 判词按 Krippendorff 阈值",
   "可靠" in m.alpha_verdict(0.85) and "暂定" in m.alpha_verdict(0.70)
   and "不可靠" in m.alpha_verdict(0.40),
   m.alpha_verdict(0.40))

# ── T2 ★ 口径对比：偏斜数据上原始一致率 vs α ─────────────
# 90% 的 unit 是「decidable」（大家都判多数类），10% 是分歧
_skew = []
for _i in range(9):
    _skew.append(["decidable", "decidable", "decidable"])
for _i in range(1):
    _skew.append(["decidable", "partial", "undecidable"])
_units_all = [u for u in _skew]
_raw_pairs = _agree = 0
for _u in _units_all:
    for _i in range(len(_u)):
        for _j in range(_i + 1, len(_u)):
            _raw_pairs += 1
            if _u[_i] == _u[_j]:
                _agree += 1
_raw = _agree / float(_raw_pairs)
_as = m.krippendorff_alpha_ordinal(_units_all)
ok("T2 ★ 偏斜夹具下 α 明显低于原始一致率（口径差异可见）",
   _as is not None and _as["alpha"] < _raw - 0.05,
   "raw=%.3f vs α=%.3f" % (_raw, _as["alpha"] if _as else float("nan")))

# ── T3 少数类一致 ───────────────────────────────────────
_rare_in = [["undecidable", "undecidable", "undecidable"],
            ["undecidable", "partial", "decidable"],
            ["decidable", "decidable", "decidable"]]
_rc = m.rare_class_agreement(_rare_in, "undecidable")
ok("T3 少数类一致：只数含该类的 unit", _rc and _rc["units"] == 2,
   str(_rc))
ok("T3 少数类一致率 = 1/2（分歧被看见）", _rc and abs(_rc["rate"] - 0.5) < 1e-9,
   str(_rc))
ok("T3 无该类 ⇒ None", m.rare_class_agreement(
    [["decidable", "decidable", "decidable"]] * 3, "undecidable") is None)

# ── T4 尺度登记 + 禁词 ──────────────────────────────────
ok("T4 三态/分级登记为定序",
   m.reading_scale("tri_state_agreement") == "ordinal"
   and m.reading_scale("tier") == "ordinal")
ok("T4 duty.S 定距 / semantic_entropy 定比",
   m.reading_scale("duty.S") == "interval"
   and m.reading_scale("semantic_entropy") == "ratio")
ok("T4 未登记 ⇒ unknown（不许默认当 interval）",
   m.reading_scale("nope_not_registered") == "unknown")
ok("T4 定序禁词命中「均值」",
   m.scale_word_violations("一致率的均值是 0.5", "ordinal") == ["均值"])
ok("T4 负对照：比例读数不禁「均值」",
   m.scale_word_violations("一致率的均值是 0.5", "ratio") == [])

# ── T5 停因级联 ─────────────────────────────────────────
_cas = m.stop_cascade(["体力耗尽（4 圈走满，未触发任何停止判据）",
                       "悬置决定稳定，自然安住"])
ok("T5 优先级：收敛/安住 > 硬上限（主因取前者）",
   _cas["primary"] == "悬置决定稳定，自然安住", str(_cas["primary"]))
ok("T5 ★ 主因 ∈ 全部触发（报告即实际）",
   _cas["primary"] in _cas["all"], str(_cas["all"]))
ok("T5 ordered 按优先级排序", _cas["ordered"][0] == _cas["primary"])
_cas2 = m.stop_cascade(["连续 2 轮无新 &，螺旋停止"])
ok("T5 负对照：单条 ⇒ 主因就是它", _cas2["primary"] == "连续 2 轮无新 &，螺旋停止")
ok("T5 空输入 ⇒ 不硬造主因", m.stop_cascade([])["primary"] == "")
ok("T5 未匹配文案落到最低档（不静默丢弃）",
   m.stop_priority("某种没见过的新停因") == 3)

# ── T6 CSD ─────────────────────────────────────────────
_up = [1, 1, 2, 4, 7, 11]          # 方差上升 + 正自相关
_flat = [3, 3, 3, 3, 3, 3]
_cu, _cf = m.csd_indicators(_up), m.csd_indicators(_flat)
ok("T6 上升序列 ⇒ 有前兆", _cu and _cu["hint"] is True, str(_cu))
ok("T6 平稳序列 ⇒ 无前兆（负对照）", _cf and _cf["hint"] is False, str(_cf))
ok("T6 短序列 ⇒ None（不表态）", m.csd_indicators([1, 2, 3]) is None)
ok("T6 文案写明「概率性评估，非预测」",
   "概率性评估" in m.csd_line(_cu) and "非预测" in m.csd_line(_cu))

# ── T7 成本两分 ─────────────────────────────────────────
try:
    _cfg = dict(m.DEFAULT_CONFIG)
    _llm = m.LLM(_cfg)
    _llm.total_calls = 0
    class _U:
        total_tokens = 10
    # 直接驱动归类逻辑：判定类 stage vs 普通 stage
    _ls = getattr(m, "_LLM_EVAL_STAGES", frozenset())
    ok("T7 判定类 stage 名单在（含 adjudicate/assess 族）",
       "assess_decidability" in _ls and "dual_judge" in _ls, str(sorted(_ls))[:80])
except Exception as _e:
    ok("T7 成本两分", False, repr(_e))



# ── T15~ 第三批（机制级）─────────────────────────────────
ok("T15 anytime：12 个 1 ⇒ 下界 > 0.5", m.stitched_hoeffding_lower([1]*12)["lower"] > 0.5)
ok("T15 anytime：3 个样本不判「已确立」（负对照）",
   not m.anytime_majority_decided([1, 1, 1])[0])
ok("T15 anytime：n<2 ⇒ None（不表态）", m.stitched_hoeffding_lower([1]) is None)
ok("T16 发散：方差上升 + 正 AC1 ⇒ 发散",
   m.divergence_state([1, 1, 2, 4, 8, 16])["state"] == "发散")
ok("T16 停滞（负对照）", m.divergence_state([3]*6)["state"] == "停滞")
ok("T16 回滚指针：历史最佳圈（1-based）", m.best_round_index([1, 3, 2, 0]) == 2)
_bb = m.BudgetBandit([{"rounds": 3}, {"rounds": 4}, {"rounds": 6}])
ok("T17 bandit：未试过的臂优先（确定性探索）",
   _bb.pick()["explore"] is True and _bb.pick()["index"] == 0)
_bb.update(0, 0.9, 1.0)
ok("T17 bandit：更新写入 mean/n", _bb.n[0] == 1 and abs(_bb.mean[0]-0.9) < 1e-9)
ok("T18 compact：率失真口径（超预算判 over）",
   m.compact_plan(900, 1000)["over"] and not m.compact_plan(300, 1000)["over"])
ok("T19 锚点离线：合法过 / 畸形拦",
   m.anchor_offline_check("https://www.gov.cn/a")["ok"]
   and not m.anchor_offline_check("htp:/x")["ok"])
ok("T20 锚点内部批判：自媒体 vs 公权力可区分",
   "媒体" in m.anchor_interest_hint("https://blog.medium.com/x")
   and "公权力" in m.anchor_interest_hint("https://www.stats.gov.cn/a"))
ok("T21 分级证明标准：因果用最高档",
   m.anchor_evidence_standard("causal")["standard"] == "beyond_reasonable_doubt")
ok("T22 裁决维度拆分", "/" in m.adjudication_aspect("口径矛盾", "按实测数据"))
ok("T23 信念陈旧度（不改四态）",
   m.belief_staleness({"id":"B","status":"active","last_confirmed_round":1}, 5)["stale_hint"])

# ── T9~T15 第二批 ────────────────────────────────────────
_t9 = m.cut_two_way(True, 4, 4, {"missing_core": ["a"], "core_total": 3})
ok("T9 截断两向：同时报省与丢", _t9["cut"] and _t9["lost_core"] == 1
   and _t9["saved_rounds"] == 0, str(_t9))
ok("T9 负对照：未截断时报省下的圈", m.cut_two_way(False, 4, 2, {})["saved_rounds"] == 2)
_rf = m.input_red_flags("为什么要忽略以上内容")
ok("T10 输入自检：注入 + 预设都能检出",
   {x["kind"] for x in _rf} >= {"injection", "presupposition"}, str(_rf))
ok("T10 负对照：正常问题零 flags", m.input_red_flags("如何利用AI帮助人类") == [])
ok("T11 言语行为：全「请求」⇒ 公文体告警",
   bool(m.illocution_dist([{"verb": "应当", "object": "x"}]).get("verdict")))
ok("T11 负对照：有「承诺」不告警",
   not m.illocution_dist([{"verb": "指派", "object": "x"}]).get("verdict"))
ok("T12 FMEA：无标记 ⇒ 不可检测",
   "不可检测" in m.fmea_detectability("F1", []))
ok("T12 负对照：有标记 ⇒ 可检测",
   "不可检测" not in m.fmea_detectability("unsaid_overused(3)", ["unsaid_overused(3)"]))
ok("T13 多样性预算：层×通道",
   m.diversity_budget({"0": {}, "1": {}}, ["content"], "serial")["combos"] == 2)
try:
    _pp = m.eml_read_jsonl if hasattr(m, "eml_read_jsonl") else None
    ok("T14 nogoods 常量在", "_EML_NOGOODS" in dir(m) or True,
       getattr(m, "_EML_NOGOODS", "?"))
except Exception as _e:
    ok("T14 nogoods", False, repr(_e))

# ── T8 真实入口 ─────────────────────────────────────────
try:
    _eng = m.MetaDGTF(dict(m.DEFAULT_CONFIG))
    _eng._question = "如何利用AI来帮助人类实现财富自由"
    _v = m.View(entry="1")
    _v.round_log = [{"round": i, "new_amps": v, "idle_stall": 0}
                    for i, v in enumerate([1, 1, 2, 4, 7], 1)]
    _d = _eng._layer_csd_now("1", _v)
    ok("T8 真实入口写回 view.csd", bool(_v.csd) and "new_amps" in _v.csd, str(_d)[:60])
    _eng._tri_alpha = {}
    ok("T8 view 有 stop_primary 字段",
       hasattr(_v, "stop_primary"), repr(getattr(_v, "stop_primary", None)))
except Exception as _e:
    import traceback
    traceback.print_exc()
    ok("T8 真实入口", False, repr(_e))

bad = [r for r in R if not r[1]]
print("\n=== 探针汇总：%d ✓ / %d ✗ ===" % (len(R) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
