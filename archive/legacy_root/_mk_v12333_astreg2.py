# -*- coding: utf-8 -*-
"""补齐 v1.22 立项（基线 v1.21.77）至 v1.23.32 之间**历史累积未登记**的 55 个符号。

★ 为什么补：6.6 判据是**两向对账**（未登记判红 / 过期登记判红 / 符号消失判红）。
  只补本版 57 项 ⇒ 判据仍红在历史的 55 项上。判据没错、登记表缺账，
  所以正解是**补登记**（每条都必须写出「它干什么的」，不许写占位）。
"""
import ast, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
REG = HERE / "_v122_ast_registry.json"

R = {
    # ── EML 经验记忆回路（v1.23.31）
    "_eml_prepare": ("EML", "经验记忆：写前准备（闸门 + 去重检查）"),
    "_eml_note_use": ("EML", "经验记忆：记录一次使用（RRIF 只增）"),
    "_eml_apply": ("EML", "经验记忆：把召回条目应用到本轮"),
    "_eml_finish": ("EML", "经验记忆：收尾（升格 / 隔离）"),
    "eml_dir": ("EML", "经验记忆目录解析"),
    "eml_read_jsonl": ("EML", "经验记忆读 JSONL"),
    "eml_append_jsonl": ("EML", "经验记忆追加 JSONL（只增）"),
    "eml_rewrite_jsonl": ("EML", "经验记忆重写（升格路径专用）"),
    "eml_candidates_from_result": ("EML", "从本轮产物抽经验候选"),
    "eml_merge_candidate": ("EML", "经验候选去重合并（入池前挡重复）"),
    "eml_q_features": ("EML", "经验条目质量特征"),
    "eml_recall": ("EML", "经验召回"),
    "eml_note_contra": ("EML", "经验反面证据记录（双面）"),
    "eml_promote": ("EML", "经验升格（跨轮稳定才升）"),
    "eml_sweep_forget": ("EML", "经验遗忘扫描"),
    "eml_summarize": ("EML", "经验库汇总（留痕行）"),
    "eml_aggregate_macro": ("EML", "经验宏聚合"),
    "eml_write_memory_md": ("EML", "经验写回 memory.md"),
    "episode_from_result": ("EML", "从产物构造 episode（AutoTune 消费）"),
    # ── 学科吸收 v1.23.32
    "krippendorff_alpha_ordinal": ("学科吸收", "序数 Krippendorff α（多标注者一致率）"),
    "weighted_kappa_pair": ("学科吸收", "配对加权 kappa"),
    "rare_class_agreement": ("学科吸收", "稀有类一致率（α 对稀有类不敏感 ⇒ 要单列）"),
    "diversity_budget": ("学科吸收", "多样性预算"),
    "cost_bucket": ("学科吸收", "成本分桶（成本两分）"),
    "reading_scale": ("学科吸收", "读数量级尺"),
    "scale_word_violations": ("学科吸收", "量级词的越界检查"),
    "csd_indicators": ("学科吸收", "CSD 临界慢化指标"),
    "csd_line": ("学科吸收", "CSD 留痕行"),
    "_layer_csd_now": ("学科吸收", "当前层 CSD 读数"),
    "alpha_verdict": ("学科吸收", "α 判定"),
    "sem_thr_relative": ("学科吸收", "语义熵阈值相对分位（本批相对，非绝对）"),
    "input_red_flags": ("学科吸收", "输入红旗（FMEA 检测度）"),
    "fmea_detectability": ("学科吸收", "FMEA 检测度评估"),
    # ── 层职责 / 停因
    "duty_of_layer": ("层职责", "层职责打分（覆盖 C × 相关 R）"),
    "duty_components": ("层职责", "层职责分项"),
    "duty_short_line": ("层职责", "层职责不足留痕行"),
    "_duty_marginal_streak": ("层职责", "职责边际连续未提升计数"),
    "_layer_duty_now": ("层职责", "当前层职责读数"),
    "stop_cascade": ("停因", "停因级联"),
    "stop_priority": ("停因", "停因优先级（档 0~3）"),
    "gate_check": ("停因", "闸门检查（留痕 vs 拦截的分界，走 `_quality_verdict`）"),
    # ── 模式判别
    "_mode_rule": ("模式判别", "模式判别方法包装"),
    "mode_rule": ("模式判别", "模式判别唯一实现（三处接线同源）"),
    # ── 其余
    "adjudication_aspect": ("裁决维度", "裁决维度标签"),
    "question_aspects": ("裁决维度", "题面侧面抽取"),
    "illocution_of": ("言语行为", "语句的言语行为归类"),
    "illocution_dist": ("言语行为", "言语行为分布"),
    "cut_two_way": ("两向切分", "两向切分辅助"),
    "nogood_record": ("nogood", "禁止记录（约束违反留痕）"),
    "_marg": ("边际", "边际辅助"),
    "_lv_med": ("留痕", "留痕中位数辅助"),
    "_tri_rank": ("三角排序", "三值排序辅助"),
    "_hit": ("打分", "命中判定辅助"),
    "_d": ("辅助", "通用字典取值辅助"),
    "_w": ("辅助", "通用权重辅助"),
    "_grams": ("辅助", "n-gram 切分辅助"),
}


def syms(p):
    return {n.name for n in ast.walk(ast.parse(Path(p).read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


cur = syms(SRC)
base = syms(HERE / "_baseline_v12177.py")
added = sorted(cur - base)
d = json.loads(REG.read_text(encoding="utf-8"))
reg = d.setdefault("registry", {})
add, missing = [], []
for name in added:
    if name in reg:
        continue
    r = R.get(name)
    if r is None:
        missing.append(name); continue
    reg[name] = {"phase": r[0], "reason": r[1]}
    add.append(name)
if missing:
    raise SystemExit("仍缺 reason：%r" % (missing,))
d["current"] = SRC.name
d["n_symbols_current"] = len(cur)
d["n_symbols_baseline"] = len(base)
REG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("OK 补登记 %d 项；registry → %d（新增总数 %d）" % (len(add), len(reg), len(added)))
