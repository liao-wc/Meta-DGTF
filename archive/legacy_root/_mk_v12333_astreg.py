# -*- coding: utf-8 -*-
"""把 v1.23.33 相对 v1.23.32 新增的 **57 个符号**逐条登记进 `_v122_ast_registry.json`。

背景：`_v122_verify.py --phase all` 的 6.6 判据（AST 登记两向对账）以
`_baseline_v12177.py` 为基线 ⇒ 从 v1.22 立项到本版累计新增 284 个符号，
其中 112 项**从未登记**（历史累积缺口），本版自己贡献 **57** 项。

★ 这不是「判据过时」，是**真缺口**：登记表的意义就是「每个新符号都要有人解释
  它是干什么的」。所以修法是**补登记**，不是放宽判据。
★ 只补本版新增的 57 项；历史累积的 55 项（112-57）不动 —— 那属于历史欠账，
  本轮不做无限追补（会掩盖本轮的账）。
"""
import ast, io, json, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
PREV = HERE / "元DGTF-V1.23.32.py"
REG = HERE / "_v122_ast_registry.json"

REASONS = {
    # ── 第六期：各环节量化（纯函数 · 零成本）
    "restate_fidelity": ("第六期-量化", "锚点保真度：重述 vs 原锚点的保真读数（依据 ① 重述失真毁下游链）"),
    "yin_yang_divergence": ("第六期-量化", "阴阳分歧度：正反题是否真分叉（依据 ② 对抗性依从率，区别真对撞/假对撞）"),
    "semantic_density": ("第六期-量化", "语义密度：实词占比（依据 ④ 信息瓶颈，>5 个无信息 token 性能降 15%+）"),
    "_sd_is_punct": ("第六期-量化", "语义密度的标点判定辅函数"),
    "_quant_note": ("第六期-量化", "六个量化读数的**唯一写入口**（模块级：调用点在 DGTF，与 MetaDGTF 无继承）"),
    "candidate_yield": ("第六期-量化", "候选生成产出率：本圈候选相对上圈是否只是复述（依据 ③ 早期信号；缺输入不表态）"),
    # ── 第一期：四层目标读数 + AutoTune
    "layer_goal_readings": ("目标读数", "四层目标读数（excavate/settle/fuse/crystallize）逐层计算"),
    "layer_goal_stop_signal": ("目标读数", "目标读数转停止信号（与体力/结构化停因并列）"),
    "layer_goal_summary": ("目标读数", "四层目标读数汇总（层末并列判定与留痕）"),
    "layer_goal_action_hint": ("目标读数", "第二期：目标读数转**圈内动作**指引（纯函数）"),
    "_goal_action_hint": ("目标读数", "第二期：动作指引的方法包装（读配置 + 组 prompt 片段）"),
    "_goal_stop_signal": ("目标读数", "目标读数 → 停因的迁移判定"),
    "_refresh_goal_hint": ("目标读数", "第二期：每圈刷新 `_goal_hint_next`（复用 `_layer_goal_now`，零新增接线点）"),
    "_layer_goal_now": ("目标读数", "第一期接线：取当前层目标读数（并行/串行共用）"),
    # ── AutoTune（帕累托 · 层集膝盖 · 圈数+1）
    "autotune_pareto": ("AutoTune", "质量×成本帕累托前沿"),
    "autotune_dominates": ("AutoTune", "支配判定（缺读数 ⇒ 淘汰已知是错的，必须回 None）"),
    "autotune_rank": ("AutoTune", "前沿内排序"),
    "autotune_score": ("AutoTune", "单臂打分（质量 + 成本）"),
    "autotune_sh_rounds": ("AutoTune", "圈数建议（截断层不加圈 = 硬约束）"),
    "autotune_progress": ("AutoTune", "学习进度（前期选择 / 后期学习分段）"),
    "autotune_archive": ("AutoTune", "开放探索档案（DGM 已证优于贪心留最优臂）"),
    "autotune_decide": ("AutoTune", "主决策"),
    "autotune_recommend": ("AutoTune", "推荐输出（**只出建议不落地配置** —— 红线：建议与执行分开）"),
    "autotune_run": ("AutoTune", "跑批入口"),
    "autotune_load_episodes": ("AutoTune", "历史 episode 载入"),
    # ── AutoTune 三阶段
    "autotune_phase_select": ("AutoTune", "三阶段决策 · 阶段一：选择"),
    "autotune_phase_adjust": ("AutoTune", "三阶段决策 · 阶段二：调整"),
    "autotune_phase_learn": ("AutoTune", "三阶段决策 · 阶段三：学习"),
    # ── Bandit
    "BudgetBandit": ("预算 bandit", "圈数上限 bandit（动作空间故意做小：越大探索代价越高）"),
    "_load_bandit": ("预算 bandit", "bandit 状态载入"),
    "_save_bandit": ("预算 bandit", "bandit 状态落盘"),
    # ── 其余各期
    "anytime_majority_decided": ("anytime", "anytime 停止：多数已定即停（**opt-in**）"),
    "best_round_index": ("best-round", "取最佳圈索引"),
    "stitched_hoeffding_lower": ("分级证明标准", "缝接 Hoeffding 下界（分级证明标准的低档）"),
    "belief_staleness": ("陈旧度", "信念陈旧度读数"),
    "divergence_state": ("发散+指针", "发散状态（带指针）"),
    "adjudication_aspect": ("裁决维度", "裁决维度标签"),
    "compact_plan": ("compact", "compact 读数计划"),
    "anchor_offline_check": ("锚点离线", "锚点离线自检"),
    "anchor_evidence_standard": ("锚点证据", "锚点证据标准（作 gate 证据）"),
    "anchor_interest_hint": ("锚点兴趣", "锚点兴趣提示"),
    "eml_lock": ("EML", "经验记忆库锁（O_EXCL 互斥，防并发互相覆盖）"),
    # ── 第六期小工具（纯函数）
    "_toks": ("第六期-量化", "分词辅助（语义密度用）"),
    "_var": ("AutoTune", "方差辅助"),
    "_rv": ("AutoTune", "读数取值辅助"),
    "_at_num": ("AutoTune", "数值归一化辅助"),
    "_at_med": ("AutoTune", "中位数辅助（★ 分母只算有质量读数的跑次）"),
    "_apply_all_on": ("all_on", "all_on 开关批量应用"),
    "_score": ("AutoTune", "打分辅助"),
    "_var": ("AutoTune", "方差辅助"),
    "pick": ("AutoTune", "取用辅助"),
    "_var2_unused": ("占位", "占位（不应出现）"),
    "_lg_num": ("目标读数", "目标读数 · 数值归一化"),
    "_lg_flat": ("目标读数", "目标读数 · 扁平化"),
    "_lg_ratio": ("目标读数", "目标读数 · 比率"),
    "_lg_stag_ratio": ("目标读数", "目标读数 · 停滞比率"),
    "_lg_diverge_state": ("目标读数", "目标读数 · 发散状态"),
    "_lg_aspect_margin": ("目标读数", "目标读数 · 侧面边际"),
    "update": ("目标读数", "目标读数增量更新"),
}


def syms(p):
    t = ast.parse(Path(p).read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


cur, prev = syms(SRC), syms(PREV)
mine = sorted(cur - prev)
d = json.loads(REG.read_text(encoding="utf-8"))
reg = d.setdefault("registry", {})
_added = []
_missing = []
for name in mine:
    if name in reg:
        continue
    r = REASONS.get(name)
    if r is None:
        _missing.append(name)
        continue
    reg[name] = {"phase": r[0], "reason": r[1]}
    _added.append(name)

if _missing:
    raise SystemExit("以下新符号**没有 reason**，必须逐条补：%r" % (_missing,))

d["current"] = SRC.name
d["n_symbols_current"] = len(cur)
REG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("OK 补登记 %d 项（本版新增共 %d 项）；registry %d → %d"
      % (len(_added), len(mine), len(reg) - len(_added), len(reg)))
