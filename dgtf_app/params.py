# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 把 `dgtf_config.yaml` 摊成可调参数（给「高级参数」面板）。

为什么：改配置以前要开 yaml 文件手动编辑。这里把 yaml **扁平化**成
`a.b.c → 值` 的列表交给前端渲染，用户改了以后由 `build_temp_config()`
生成一份**临时副本**用 `--config` 传给引擎。

★★ R36 起分两份文件（用户要求「参数改动永久写回另一份配置文件，另加一个
恢复默认配置按钮，恢复后端原始默认配置 yaml」）：

- `dgtf_config.yaml`      —— **后端出厂原始默认配置**，只读，前端永不改它；
- `dgtf_config.user.yaml` —— **前端用户的运行配置**（增量：只存用户改过的键），
  「保存」写这份，「恢复默认配置」删这份。

生效规则：**用户配置优先、出厂 yaml 兜底**（同一套合并逻辑在 `load_params`
与 `build_temp_config` 里共用，避免两处口径漂移）。用户配置删掉
⇒ 全部回落到出厂值，不需要任何「反向还原」逻辑。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import outputs_index as oi

CFG = oi.PROJECT_ROOT / "dgtf_config.yaml"           # 后端出厂默认（只读）
USER_CFG = oi.PROJECT_ROOT / "dgtf_config.user.yaml"  # 前端用户运行配置（增量）

# 分组中文名（顺序即展示顺序；没列到的按字母排后面）
GROUP_LABEL = [
    ("api", "模型与 API"),
    ("runtime", "运行档位"),
    ("web_search", "联网检索"),
    ("external_anchor", "外部锚点"),
    ("auto", "自适应调度"),
    ("output", "输出"),
    ("memory", "记忆通道"),
    ("spiral", "螺旋与停止"),
    ("probe", "探针"),
    ("actions", "动作开关"),
]
_ORDER = {k: i for i, (k, _) in enumerate(GROUP_LABEL)}

# 几个「枚举」键给下拉选项（其余按值类型渲染输入框）
OPTIONS = {
    "api.default_model": ["deepseek-flash", "deepseek-reasoner", "deepseek-chat"],
    "api.reasoner_model": ["deepseek-flash", "deepseek-reasoner", "deepseek-chat"],
    "web_search.backend": ["tavily", "snapshot"],
    "external_anchor.retriever": ["snapshot", "tavily"],
    "runtime.web": ["auto", "on", "off"],
    "runtime.thinking": ["auto", "on", "off"],
    "runtime.effort": ["auto", "low", "medium", "high", "max"],
}
# 置顶项（面板最先看到的几个）
PINNED = ("api.default_model", "web_search.backend", "runtime.thinking",
          "runtime.effort", "web_search.enabled")

# ★ 只读键：密钥 / 凭据一类的值**不允许从面板写回 yaml**。
#   两个理由：① 它多半是「环境变量名」或空串，面板上看着像个可编辑项，改坏了
#   会让凭据链路静默失效；② 保存走的是「整键回写」，一旦面板把空串写回去，
#   原本有值的键会被**抹成空**（比不改更糟）。
#   前端据 `readonly` 渲染成不可编辑，后端 save_params 再兜一层拒绝。
READONLY_KEYS = frozenset({
    "api.key",
    "web_search.api_key",
    "web_search.api_key_env",
    "external_anchor.api_key",
    "external_anchor.api_key_env",
})

# ★★ R38：CLM（任务级）参数 —— 12 个，**不在 dgtf_config.yaml 里**，是随任务当命令行
#   flag 传给引擎的（见 engine_runner._ARG_SPEC）。用户要求把它们也做进参数面板、
#   能保存、能回显（「永久写进用户参数配置文件里」），所以用户配置里单独开一个 `cli:`
#   段存它们；运行时先读这段当默认值，任务级覆盖再压一层。
#   ★ 名字沿用用户在界面上看到的叫法（CLM = 任务命令行）。
CLI_KEYS = (
    "route", "rounds", "channels", "parallel", "web", "thinking",
    "effort", "orientation", "landing", "decidability", "appendix", "keep",
)
CLI_SECTION = "cli"        # 用户配置里的段名（`cli:` → 上面这 12 个键）

# ── 参数键 → 中文说明（标签统一成「键（说明）」，与 CLI 参数那一组同格式）──────
# ★ 为什么写显式表、不去抓 yaml 注释：注释是给**一整段**写的，逐键抓会继承到
#   容器 / 甚至文件头的文字（实测 164 个键里 47 个只能继承，抓出来是
#   「元 DGTF · v1.23…」这种噪声），格式反而更乱。这张表一一对应，改配置时同步改。
_KEY_CN: dict[str, str] = {

    # ★ [app 同步] 下面是**补录**的键（原先 `_KEY_CN` 里没有）——
    #   25 个 `api.thinking.stages.*`（一直没补）+ 30 个
    #   `web_search.stages.*`（v1.23.36 新增的环节开关）。
    #   判定口径同本文件下方注释：「label 必须含 `（`」。
    "api.thinking.stages.adjudicate_sub_tristate": "思考档 · adjudicate_sub_tristate（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.adjudicate_sub_tristate_multi": "思考档 · adjudicate_sub_tristate_multi（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.anchor_crosscheck": "思考档 · anchor_crosscheck（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.ask_missing_polarity": "思考档 · ask_missing_polarity（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.assess_decidability": "思考档 · assess_decidability（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.assess_decidability_from_pool_view": "思考档 · assess_decidability_from_pool_view（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.auto_plan": "思考档 · auto_plan（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.check_input_sanity": "思考档 · check_input_sanity（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.check_structure_saturation": "思考档 · check_structure_saturation（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.decide_parallel_mode": "思考档 · decide_parallel_mode（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.decompose_from_pool": "思考档 · decompose_from_pool（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.decompose_hybrid": "思考档 · decompose_hybrid（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.decompose_koan": "思考档 · decompose_koan（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.decompose_normal": "思考档 · decompose_normal（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.dual_judge": "思考档 · dual_judge（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.phase_probe": "思考档 · phase_probe（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.plan_orientation": "思考档 · plan_orientation（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.plan_resources": "思考档 · plan_resources（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.probe_duel": "思考档 · probe_duel（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.probe_meta": "思考档 · probe_meta（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.probe_research": "思考档 · probe_research（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.re_anchor": "思考档 · re_anchor（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.re_evaluate_pool": "思考档 · re_evaluate_pool（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.self_check": "思考档 · self_check（enabled/disabled；显式 > 本表 > default）",
    "api.thinking.stages.settle_research": "思考档 · settle_research（enabled/disabled；显式 > 本表 > default）",
    "web_search.stages.adjudicate_sub_tristate": "环节授权 · 子问题三态裁决（默认关；开=该环节可按需联网）",
    "web_search.stages.adjudicate_sub_tristate_multi": "环节授权 · 子问题三态裁决（多）（默认关；开=该环节可按需联网）",
    "web_search.stages.anchor_crosscheck": "环节授权 · 锚点交叉核对（默认关；开=该环节可按需联网）",
    "web_search.stages.ask_missing_polarity": "环节授权 · 极性追问（默认关；开=该环节可按需联网）",
    "web_search.stages.assess_decidability": "环节授权 · 可判定性评估（默认关；开=该环节可按需联网）",
    "web_search.stages.assess_decidability_from_pool_view": "环节授权 · 池视角可判定性（默认关；开=该环节可按需联网）",
    "web_search.stages.auto_plan": "环节授权 · 自动计划（默认关；开=该环节可按需联网）",
    "web_search.stages.check_input_sanity": "环节授权 · 输入自检（默认关；开=该环节可按需联网）",
    "web_search.stages.check_structure_saturation": "环节授权 · 结构饱和度（默认关；开=该环节可按需联网）",
    "web_search.stages.decide_parallel_mode": "环节授权 · 并行模式决策（默认关；开=该环节可按需联网）",
    "web_search.stages.decompose_from_pool": "环节授权 · 池内拆解（默认关；开=该环节可按需联网）",
    "web_search.stages.decompose_hybrid": "环节授权 · 混合拆解（默认关；开=该环节可按需联网）",
    "web_search.stages.decompose_koan": "环节授权 · 公案式拆解（默认关；开=该环节可按需联网）",
    "web_search.stages.decompose_normal": "环节授权 · 常规拆解（默认关；开=该环节可按需联网）",
    "web_search.stages.dual_judge": "环节授权 · 对偶判断（默认关；开=该环节可按需联网）",
    "web_search.stages.expand_pair": "环节授权 · 阴阳展开（默认关；开=该环节可按需联网）",
    "web_search.stages.expand_pair_merged_once": "环节授权 · 阴阳合并展开（默认关；开=该环节可按需联网）",
    "web_search.stages.he": "环节授权 · & 沉淀（默认关；开=该环节可按需联网）",
    "web_search.stages.ing": "环节授权 · ing 对撞（默认关；开=该环节可按需联网）",
    "web_search.stages.manifest": "环节授权 · 清单（默认关；开=该环节可按需联网）",
    "web_search.stages.phase_probe": "环节授权 · 分阶段探针（默认关；开=该环节可按需联网）",
    "web_search.stages.plan_orientation": "环节授权 · 取向规划（默认关；开=该环节可按需联网）",
    "web_search.stages.plan_resources": "环节授权 · 资源规划（默认关；开=该环节可按需联网）",
    "web_search.stages.probe_duel": "环节授权 · 对撞探针（默认关；开=该环节可按需联网）",
    "web_search.stages.probe_meta": "环节授权 · 元层探针（默认关；开=该环节可按需联网）",
    "web_search.stages.probe_research": "环节授权 · 研究探针（默认关；开=该环节可按需联网）",
    "web_search.stages.re_anchor": "环节授权 · 锚点重述（默认关；开=该环节可按需联网）",
    "web_search.stages.re_evaluate_pool": "环节授权 · 池重评（默认关；开=该环节可按需联网）",
    "web_search.stages.self_check": "环节授权 · 自检（默认关；开=该环节可按需联网）",
    "web_search.stages.settle_research": "环节授权 · 研究清算（默认关；开=该环节可按需联网）",

    "auto.bandit.c": "预算 bandit 的探索系数 c（UCB 宽度；越大越爱探索）",
    "auto.bandit.cost_w": "预算 bandit 的成本权重（奖励里扣多少成本；默认 0.3）",
    "auto.bandit.enabled": "预算 bandit 总开关（默认关；开机会故意选较差档）",
    "probe.marginal_floor": "探针边际增益下限（≥此值才算有增益；0=分支恒不触发）",
    "belief.merge_semantic": "语义归并开关（默认关；开=换说法记为一次复现）",
    "belief.merge_sim": "语义归并阈值（默认 0.85，近乎逐字才算，宁可漏并）",
    "belief.revoke_sources": "信念撤销所需的不同攻击来源数（与 stable 对称）",
    "belief.sem_entropy_thr": "语义熵聚类阈值（0.30；填 rel 改用本批相对分位）",
    "duty.floor": "层职责度下限（低于它不许署自然安住，并点名缺的 core）",
    "duty.patience": "职责增益收敛所需连续圈数（ΔS<τ 连续几圈算推不动）",
    "duty.remedy_rounds": "职责未尽时的定向补救圈数（并入下游 carry；0=关）",
    "duty.tau": "职责边际增益阈值 τ（连续低于它记一次推不动）",
    "playbook.dir": "经验记忆库目录（默认空=仓库根 dgtf_memory/）",
    "playbook.halflife_days": "记忆半衰期（天）：检索排序与遗忘共用（默认 14）",
    "playbook.learn_from_anon": "是否收无 run_id 的跑次（默认否，防测试替生产刷票）",
    "playbook.mode": "经验记忆模式：off 不读不写 / shadow 只记不生效 / on 生效",
    "playbook.promote_n": "同向证据达几条才 shadow→active（默认 3）",
    "playbook.top_k": "每次读几条经验（默认 3）",
    "stop.anytime_alpha": "anytime-valid 停止的 δ（默认 0=关；>0 才启用该停因）",
    "all_on": "【一键全开】本机真跑默认全开（出厂 true；引擎默认 false）",
    "autotune.min_n": "自调优：同(模式,层集)至少几次跑才进榜（防偶发）",
    "autotune.out": "自调优：建议落盘路径（空=仓库根 dgtf_autotune.json）",
    "autotune.quality_tau": "自调优：层集取舍容差 τ（同质量内取成本最低 = 帕累托膝盖）",
    # ── actions 动作开关 ──
    "actions.assess_decidability": "全局可判定性评估",
    "actions.decidability_source": "可判定性来源",
    "actions.decompose_question": "子问题分解",
    "actions.decompose_source": "分解来源",
    "actions.dual_judge": "对偶判断",
    "actions.expand_yang": "阳视角展开",
    "actions.expand_yin": "阴视角展开",
    "actions.he": "& 沉淀",
    "actions.ing": "ing 对撞",
    "actions.input_sanity": "输入健全性自检",
    "actions.landing_decision": "落地决策模板",
    "actions.manifest": "view 显形",
    "actions.merge_expand": "阴阳合并成一次调用（省 token）",
    "actions.parallel_expand": "展开内并行",
    "actions.parallel_mode": "四层执行策略",
    "actions.parallel_warmup_rounds": "并行预热圈数",
    "actions.phase_probe": "探针回归",
    "actions.pipeline_gate_timeout": "流水闸门超时（秒）",
    "actions.re_anchor": "层内锚点重述",
    "actions.re_evaluate_pool": "池重估",
    "actions.self_check": "自省自检",
    "actions.settle_research": "研究层债务终局清算",
    "actions.tri_multi_vote": "可判定性三态多票",
    "actions.tri_vote_retry_empty": "空票重试",
    # ── api 模型与 API ──
    "api.base_url": "接口地址",
    "api.default_model": "默认模型（大部分调用）",
    "api.key": "API 密钥",
    "api.max_retries": "网络最大重试次数",
    "api.reasoner_model": "推理模型（长链推理两处）",
    "api.retry_backoff": "重试退避基数（秒）",
    "api.thinking.default": "思考档位 · 默认",
    "api.thinking.effort": "推理强度 · 全局",
    "api.thinking.reasoner": "思考档位 · 推理模型",
    "api.timeout": "请求超时（秒）",
    # ── auto 自适应调度 ──
    "auto.enabled": "自适应调度总开关",
    "auto.allow_route_trim": "允许 auto 砍层",
    "auto.history_limit": "历史取样份数",
    "auto.history_md": "扫产物 md 头部",
    "auto.history_batch": "扫跑批记录",
    "auto.history_halflife_days": "历史半衰期（天，0=等权）",
    # ── external_anchor 外部锚点 ──
    "external_anchor.enabled": "外部锚点总开关",
    "external_anchor.retriever": "检索后端（snapshot / tavily）",
    "external_anchor.path": "锚点快照 JSON 路径",
    "external_anchor.api_key_env": "密钥环境变量名",
    "external_anchor.max_items": "锚点上限条数",
    "external_anchor.per_round": "每圈并入几条（0=不检索）",
    "external_anchor.as_evidence": "证据资格（off/record/crosscheck/evidence/gate）",
    "external_anchor.crosscheck": "收尾锚点只读对照",
    "external_anchor.tier_floor": "引用分级门槛（tier ≤ 此值）",
    "external_anchor.triage": "分诊降级",
    "external_anchor.answers_max_n": "单条锚点 answers 上限",
    "external_anchor.answers_min_len": "answer 最短长度（中文字符）",
    "external_anchor.cache_ttl_hours": "检索缓存小时数",
    # ── memory 记忆通道 ──
    "memory.channels": "启用通道（content/context/self）",
    "memory.self_layers": "self 通道保留最近几层",
    "memory.self_layers_per_entry": "self 通道每层保留几条",
    "memory.shape_items": "池形状最多注入几条",
    "memory.shape_chars": "形状每条截断字符数",
    "memory.carry_feedback": "自省回流当下一圈硬约束",
    # ── output 输出 ──
    "output.save_dir": "结果保存目录",
    "output.verbose": "详细日志（开发调试）",
    "output.dump_rounds": "每圈产物都落盘",
    "output.self_check": "对偶判断后回看一遍",
    "output.show_dual_judge": "打印对偶判断候选细节",
    "output.show_manifest": "打印 view 显形全文",
    "output.show_ing": "打印 ing 输出全文",
    "output.show_probe_diag": "探针 covers 字段诊断",
    # ── probe 探针 ──
    "probe.select_n": "每圈筛几条新探针进下一轮",
    "probe.min_gain": "探针最低 expected_gain",
    # ── runtime 运行档位 ──
    "runtime.thinking": "思考档位（auto/on/off）",
    "runtime.effort": "推理强度（auto/low/medium/high/max）",
    "runtime.web": "联网检索（auto/on/off）",
    # ── spiral 螺旋与停止 ──
    "spiral.soft_max": "软最大圈数（超过才查自然安住）",
    "spiral.hard_max": "硬最大圈数（体力上限，走满截断）",
    "spiral.min_rounds.0": "最低圈数 · 修行(0)",
    "spiral.min_rounds.1": "最低圈数 · 研究(1)",
    "spiral.min_rounds.both": "最低圈数 · 对撞(both)",
    "spiral.min_rounds.all": "最低圈数 · 元(all)",
    "spiral.idle_limit": "空转上限（连续 idle 即停）",
    "spiral.round_idle_limit": "每圈空转上限",
    "spiral.round_stall_limit": "有新增无推进的上限",
    "spiral.stall_streak_limit": "双通道停滞（qdist 无改善次数）",
    "spiral.convergence_window": "双通道收敛窗口",
    "spiral.min_distance_improvement": "qdist 最小改善量",
    "spiral.stop_similarity": "停止判据相似度阈值",
    "spiral.rehash_similarity": "入池挡重复的相似度",
    "spiral.new_item_overlap": "新条目重叠阈值（主判据）",
    "spiral.new_item_similarity": "新条目相似度阈值（辅助）",
    "spiral.batch_similarity": "判定「同一批」的相似度",
    "spiral.thread_new_overlap": "线头去重 · 重叠阈值（更严）",
    "spiral.thread_new_similarity": "线头去重 · 相似度阈值",
    "spiral.dedup_candidate_overlap": "候选二次去重 · 重叠阈值",
    "spiral.dedup_candidate_similarity": "候选二次去重 · 相似度阈值",
    "spiral.dedup_amp_overlap": "&/线头去重 · 重叠阈值",
    "spiral.dedup_amp_similarity": "&/线头去重 · 相似度阈值",
    "spiral.both_quota.enabled": "对撞配额追问开关",
    "spiral.both_quota.max_ratio": "对撞占比上限（超过则追问）",
    "spiral.both_quota.min_items": "追问最少条数",
    "spiral.both_tighten_ratio": "对撞过载收紧阈值",
    "spiral.qc_both_ratio": "候选极性 both 占比线索线",
    "spiral.qc_rephrase_ratio": "ing 复述率线索线",
    "spiral.alignment_similarity": "四象限对齐 · 相似度",
    "spiral.alignment_containment": "四象限对齐 · 包含度",
    "spiral.all_drift_threshold": "元层跨层描述占比阈值",
    "spiral.all_selfref_threshold": "元层自指占比阈值",
    "spiral.all_extra_rounds": "元层额外多跑圈数",
    "spiral.meta_cover_similarity": "闭环清算覆盖相似度",
    "spiral.stable_need": "悬置稳定所需条数",
    "spiral.stable_layers": "悬置转稳所需连续层数",
    "spiral.re_eval_every_n": "极性重估频率（每 N 圈）",
    "spiral.re_eval_recent_k": "极性重估取池尾几条",
    "spiral.structure_saturation_enabled": "结构饱和度检查开关",
    "spiral.structure_saturation_every_n": "每 N 圈检查一次结构饱和度",
    "spiral.unsaid_escape_limit": "「此处未生」逃避判定处数",
    "spiral.escalate_starve_rounds": "无进展 N 圈 → 迁向不可判定",
    "spiral.no_push_when_idle": "层内空转时不再被「还有方向」推迟",
    "spiral.budget_per_round_cap": "不限预算时每圈兜底上限",
    "spiral.budget_per_round_floor": "自动预算每圈下限",
    # ── web_search 联网检索 ──
    "web_search.enabled": "联网总闸（false=零调用）",
    "web_search.backend": "检索后端",
    "web_search.api_key_env": "密钥环境变量名",
    "web_search.timeout_seconds": "单次请求超时（秒）",
    "web_search.max_retries": "最大重试次数",
    "web_search.backoff_seconds": "重试退避基数（秒）",
    "web_search.cache_ttl_hours": "结果缓存小时数",
    "web_search.quota.per_stage_round": "配额 · 每环节每圈",
    "web_search.quota.per_stage_total": "配额 · 每环节全程",
    "web_search.quota.per_run_total": "配额 · 每跑总量",
    "web_search.stages.practice_term_calibration": "环节授权 · 修行层（默认关）",
    "web_search.stages.research_decompose": "环节授权 · 研究层分解",
    "web_search.stages.research_evidence": "环节授权 · 研究层取证",
    "web_search.stages.research_precedent": "环节授权 · 研究层先例",
    "web_search.stages.duel_arbitration": "环节授权 · 对撞仲裁",
    "web_search.stages.meta_clean_check": "环节授权 · 元层清算",
    "web_search.stages.stop_criteria": "环节授权 · 停止判据（默认关）",
    "web_search.as_evidence": "引用授权（off/record/crosscheck/evidence/gate）",
    "web_search.tier_floor": "引用表 tier 上限",
    "web_search.auto_disable_after_failures": "连续失败 N 次自动关闭联网",
    "web_search.relax_force": "【强制放宽】每圈都放宽放宽表（12 环节）联网（默认关）",
    "web_search.tier_proposal": "tier 提案表（人工确认前不生效）",
    "web_search.domain_tier_rules": "域名 → tier 人工确认表",
    # ★ v1.23.26（另一条并行线）新增的 sim 段两个键 —— 语义取自
    #   `dgtf_config.yaml` 的版本段注释（权威来源，别按键名猜）：
    #   · dedup      池内 amp / thread / probe **入池去重阈值**（旧：硬编码 0.9）
    #   · dedup_susp **悬置目标去重阈值**（旧：硬编码 0.85）
    #   不登记会让参数面板露出英文键名（selftest「参数标签统一」判据会红）。
    #   ★ 说明里**别自带括号**：`label_for()` 会把「较长（≥3 字）的内层括号」换成中点
    #     （避免双括号），换掉后就不再含 `（` ⇒ 那条判据反而判红。
    "sim.dedup": "入池去重阈值 · amp/thread/probe",
    "sim.dedup_susp": "悬置目标去重阈值",
    #   同一版（v1.23.27 批）又加的三个键，语义取自 `_patch_v12327_step12a.py` 的
    #   版本说明（权威来源）：
    #   · sim.cluster      D3 语义熵聚类阈值（默认 0.70）
    #   · probe.submodular E2 子模批选开关（默认开）
    #   · probe.stop_floor E6 自适应停止阈值（默认 0.02，`max_gain == stop_floor` 不算停）
    "sim.cluster": "语义熵聚类阈值",
    "probe.submodular": "子模批选开关",
    "probe.stop_floor": "自适应停止阈值",
}

# ★★ 备忘（下次别再来回补）：本条「参数标签统一」判据的失败**几乎总是**
#   另一条并行线 v1.23.2x 新增了配置键、而 `_KEY_CN` 没跟上。
#   判定口径 = `/api/params` 里**每一项**的 label 都要含 `（`。
#   ★ 补的时候**说明里不要自带括号**：`label_for()` 会把「≥3 字的内层括号」
#     换成中点（防双括号），换掉后 label 就不含 `（` ⇒ 判据**照样红**（本轮踩过）。

# api.thinking.stages.* 是**逐环节**的思考档位接管，24 个键共用「思考档位 · <环节>」
_STAGE_CN = {
    "auto_plan": "自动计划",
    "plan_orientation": "取向规划",
    "plan_resources": "资源规划",
    "decide_parallel_mode": "并行模式决策",
    "decompose_normal": "常规分解",
    "decompose_hybrid": "混合分解",
    "decompose_koan": "公案式分解",
    "decompose_from_pool": "池内分解",
    "check_input_sanity": "输入健全性检查",
    "check_structure_saturation": "结构饱和度检查",
    "assess_decidability": "可判定性评估",
    "assess_decidability_from_pool_view": "池视图可判定性评估",
    "ask_missing_polarity": "补问缺失极性",
    "adjudicate_sub_tristate": "三态裁定",
    "adjudicate_sub_tristate_multi": "三态多票裁定",
    "dual_judge": "对偶判断",
    "re_anchor": "层内锚点重述",
    "re_evaluate_pool": "池重估",
    "anchor_crosscheck": "锚点交叉核对",
    "phase_probe": "探针回归",
    "probe_research": "研究探针",
    "probe_duel": "对撞探针",
    "probe_meta": "元层探针",
    "self_check": "自省自检",
    "settle_research": "研究层债务清算",
}
for _s, _cn in _STAGE_CN.items():
    _KEY_CN.setdefault(f"api.thinking.stages.{_s}", f"思考档位 · {_cn}")


def label_for(key: str) -> str:
    """参数标签 = `键（中文说明）`；没有说明就退回裸键。

    ★ 说明自己已经带括号的（如「默认模型（大部分调用）」），外层再套一层会变成双括号、
      读起来乱 ⇒ 把**内容较长**的内层括号换成中点（「默认模型 · 大部分调用」）；
      短的（如「请求超时（秒）」）保留 —— 那是单位，中点会读着别扭。
    """
    cn = _KEY_CN.get(key) or ""
    if cn:
        cn = re.sub(r"（([^（）]{3,})）", r" · \1", cn)
    return f"{key}（{cn}）" if cn else key


def _flatten(d, prefix: str = "") -> dict:
    out: dict = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def _is_flat_list(v) -> bool:
    return isinstance(v, list) and all(not isinstance(x, (list, dict)) for x in v)


def _item(key: str, val) -> dict:
    it = {"key": key, "value": val, "label": label_for(key)}
    if key in READONLY_KEYS:
        # 密钥键：**只读显示**（前端不渲染 data-cfg ⇒ collectOpts 收不到
        # ⇒ 既不会被改、也不会被写回）。值本身也不回传，只报「有没有」。
        it["type"] = "readonly"
        it["readonly_key"] = True
        it["has_value"] = bool(str(val or "").strip())
        it["value"] = "已配置" if it["has_value"] else "（空）"
        return it
    if isinstance(val, bool):
        it["type"] = "bool"
    elif isinstance(val, (int, float)):
        it["type"] = "number"
    elif _is_flat_list(val):
        # 一维标量列表（如 memory.channels）：逗号串起来交给前端编辑，
        # `build_temp_config` 回写时按原类型切回**列表**（见 _coerce_like）。
        it["type"] = "list"
        it["value"] = ",".join(str(x) for x in val)
    elif isinstance(val, list):
        # 嵌套结构（如 web_search.domain_tier_rules = [[".gov.cn",1],…]）**不给编辑**：
        # 前端只有字符串，往返会把二维结构写坏。标 readonly，前端不渲染 `data-cfg`
        # ⇒ collectOpts 收不到它 ⇒ 引擎用出厂值。
        it["type"] = "readonly"
        it["value"] = yaml.safe_dump(val, allow_unicode=True,
                                     default_flow_style=True).strip()
    else:
        it["type"] = "str"
    if key in OPTIONS:
        it["type"] = "select"
        it["options"] = OPTIONS[key]
    if key in PINNED:
        it["pinned"] = True
    return it


def _coerce_like(orig, val):
    """按**出厂 yaml 里的原类型**把前端回传的值还原（前端控件只会给字符串）。

    ★ 这是真跑必失败的那个 bug 的修法：`memory.channels` 出厂是列表
      `["content","context","self"]`，经参数面板往返后变成字符串
      `"content,context,self"`，引擎 `for c in m` 就**逐字符**迭代
      ⇒ `ValueError: 未知通道 'c'`（真跑 2–7 秒即崩）。
    """
    if isinstance(orig, list):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            if _is_flat_list(orig):
                return [x.strip() for x in val.split(",") if x.strip()]
            return orig          # 嵌套结构还原不了 —— 宁可保留原值，也别写坏
    if isinstance(orig, dict) and not isinstance(val, dict):
        return orig
    if isinstance(orig, bool) and isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(orig, (int, float)) and isinstance(val, str):
        try:
            return float(val) if "." in val else int(val)
        except ValueError:
            return val
    return val


def _load_yaml_flat(path: Path) -> dict:
    """读一份 yaml 并摊平；读不到 / 坏掉一律当空（调用方按「兜底」语义处理）。"""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        return {}
    return _flatten(raw) if isinstance(raw, dict) else {}


def effective_flat() -> dict:
    """**出厂默认 + 用户配置覆盖** 合并后的扁平值表（生效值）。

    ★ 单一实现：`load_params()`（给前端看）与 `build_temp_config()`（给引擎用）
      都从这里取值 —— 两处各写一遍「谁优先」迟早漂移。
    """
    base = _load_yaml_flat(CFG)
    user = _load_yaml_flat(USER_CFG)
    if user:
        base.update(user)
    return base


def user_overrides() -> dict:
    """用户配置里**实际改过的**键（显示「已改 N 项」/ 判断要不要给恢复按钮）。"""
    return _load_yaml_flat(USER_CFG)


def load_cli_saved() -> dict:
    """★ R38：用户配置里 `cli:` 段保存的 CLM（任务级）参数值（`{键: 值}`，只留非空）。

    面板靠它回显「用户上次保存的值」—— 用户要求「用户保存的参数，数字显示在参数
    设置框里」。出厂没有这一段（这 12 个键不属于 yaml 配置）⇒ 未保存时返回空表。
    """
    try:
        raw = yaml.safe_load(USER_CFG.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        return {}
    seg = raw.get(CLI_SECTION) if isinstance(raw, dict) else None
    if not isinstance(seg, dict):
        return {}
    return {k: v for k, v in seg.items() if k in CLI_KEYS and str(v).strip() != ""}


def load_params() -> dict:
    """返回 {groups:[{key,label,items:[…]}], total, user_keys:[…], cli:{…}}。

    每项带 `user_set`：该键是否被用户配置覆盖过（前端据此标「已改」）。
    ★ R38 增 `cli`：CLM 组**已保存**的值（见 `load_cli_saved`）—— 前端 `buildAdv()`
      用它回显输入框，用户上次存的 CLM 参数就还在。
    """
    flat = effective_flat()
    uset = set(user_overrides().keys())
    groups: dict[str, list] = {}
    for k, v in flat.items():
        it = _item(k, v)
        if k in uset:
            it["user_set"] = True
        groups.setdefault(k.split(".")[0], []).append(it)
    out = []
    for top, items in groups.items():
        items.sort(key=lambda x: (0 if x.get("pinned") else 1, x["key"]))
        out.append({"key": top,
                    "label": dict(GROUP_LABEL).get(top, top),
                    "items": items})
    out.sort(key=lambda g: (_ORDER.get(g["key"], 99), g["key"]))
    return {"groups": out, "total": len(flat),
            # ★★ R38 真 bug（判据抓出来的）：`uset` 里是**扁平键名** `cli.route`，
            #   而 `CLI_KEYS` 里是**叶子名** `route` —— 直接做差集**一个都排不掉**，
            #   于是「已改 N 项」会把 CLM 也算进去。要按前缀排。
            "user_keys": sorted(k for k in uset
                                if not k.startswith(CLI_SECTION + ".")),
            "cli": load_cli_saved()}


def _fmt_scalar(v, quote_str: bool = False) -> str:
    """把一个 Python 标量按 yaml 写法渲染成一行文本（**不带换行**）。

    ★ 为什么不用 `yaml.safe_dump`：它会把整个文件重写，**1627 行注释全没**
      —— 这份 yaml 的注释就是配置说明书（也是历次实验记录），抹掉等于毁档。
      写回只做**逐行文本替换**，注释原样留着。

    `quote_str=True`（列表项用）时，凡是字符串**一律加引号** —— 出厂文件就是
    `channels: ["content", "context", "self"]` 这个写法，保持一致少一次无谓 diff。
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if v is None:
        return "null"
    s = str(v)
    # 需要引号的情形：空串 / 首尾空白 / 含会歧义的字符 / 看着像别的类型 / 列表项且是字符串
    need_quote = (
        quote_str
        or s == "" or s != s.strip()
        or any(c in s for c in ":#{}[],&*?|-<>=!%@`\"'\\")
        or s.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~")
        or re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", s) is not None
    )
    if need_quote:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _fmt_value(v, indent: int) -> str:
    """渲染成「`key:` 后面那一截」的文本（标量带前导空格）。

    ★ 列表一律写成**同行流式** `["a", "b"]` —— 出厂 `dgtf_config.yaml` 就是这么写的
      （`channels: ["content", "context", "self"]`）。改成块序列虽然 yaml 语义等价，
      但会在 diff 里造成无谓的格式漂移，而且**续行的缩进一旦算错就会把后续注释吃掉**。
      同行流式没有续行，最稳。
    """
    if isinstance(v, list):
        if not v:
            return " []"
        return " [" + ", ".join(_fmt_scalar(x, quote_str=isinstance(x, str)) for x in v) + "]"
    return " " + _fmt_scalar(v)


def _set_flat_in_text(text: str, flat_key: str, new_val) -> tuple[str, str]:
    """在 yaml **文本**里把 `flat_key`（点分）对应的那一行改掉，返回 (新文本, 结果)。

    结果取值：`changed` / `unchanged` / `missing`。
    ★ 只认**键的整行**（`^\\s*key:`），不会误伤注释里出现的同名字符串、也不会被
      前缀同名的键子串命中（如 `web` 与 `web_search`）。
    """
    parts = flat_key.split(".")
    lines = text.split("\n")

    def _ind(raw: str) -> int:
        return len(raw) - len(raw.lstrip(" "))

    def _block_end(start: int, ind: int) -> int:
        """从 `start` 的下一行起，直到缩进回到 <= ind（含注释/空行也算块内）。"""
        j = start + 1
        while j < len(lines):
            raw = lines[j]
            if raw.strip() and not raw.lstrip().startswith("#") and _ind(raw) <= ind:
                break
            j += 1
        return j

    # 逐段下钻：每段在自己的父块范围内找**缩进更深**的整行键
    lo, hi = 0, len(lines)
    parent_ind = -1
    for depth, part in enumerate(parts):
        want = re.compile(r"^(\s*)" + re.escape(part) + r"\s*:(.*)$")
        found = None
        for i in range(lo, hi):
            raw = lines[i]
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            m = want.match(raw)
            if m and _ind(raw) > parent_ind:
                found = (i, _ind(raw), m.group(2))
                break
        if found is None:
            return text, "missing"
        i, ind, rest = found
        if depth == len(parts) - 1:
            # 叶子：把这一行（及其缩进续块）换成新的一行；流式列表没有续行
            end = i + 1
            if rest.strip() == "":                      # 值在下面的缩进块里
                end = _block_end(i, ind)
                while end - 1 > i and not lines[end - 1].strip():
                    end -= 1                            # 不吞掉尾部空行
            old = "\n".join(lines[i:end])
            newline = " " * ind + part + ":" + _fmt_value(new_val, ind)
            if newline == old:
                return text, "unchanged"
            return "\n".join(lines[:i] + [newline] + lines[end:]), "changed"
        # 下钻：把范围收窄到该键的块内
        lo, hi, parent_ind = i + 1, _block_end(i, ind), ind
    return text, "missing"


def _dump_user_cfg(flat_user: dict) -> str:
    """把扁平键表还原成嵌套 dict 并 dump 成 yaml 文本（带文件头说明）。

    ★ R38：`cli.*` 这几个键单独成段（`cli:` 下挂 route/rounds/…）——
      它们**不是** `dgtf_config.yaml` 里的配置键，混进普通键表会让人误以为出厂有它们。
      `mk <flat_key>` 时把 `cli.route` 还原成 `{cli: {route: …}}` 是天然成立的
      （点分键按段嵌套），所以这里不需要特判 —— 只要保证写回时键名带 `cli.` 前缀。
    """
    root: dict = {}
    for k, v in flat_user.items():
        node = root
        parts = k.split(".")
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        node[parts[-1]] = v
    # 让 `cli:` 段排在最前（其余按字母），读文件时一眼看到任务级参数
    ordered: dict = {}
    if CLI_SECTION in root:
        ordered[CLI_SECTION] = root.pop(CLI_SECTION)
    ordered.update(root)
    body = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=True,
                          default_flow_style=False)
    head = (
        "# 元DGTF · 前端用户运行配置（由工作台「高级参数 → 保存」自动维护）\n"
        "#\n"
        "# 这是一份**增量配置**：只记录你在工作台里改过的键。\n"
        "# 生效规则：用户配置优先，未在此文件出现的键一律回落到\n"
        "# `dgtf_config.yaml`（后端出厂原始默认）。\n"
        "# 想整体回到出厂状态 —— 在工作台点「恢复出厂设置」，或直接删掉本文件。\n"
        "# ★ 手改本文件也生效；改动会在下次跑任务时被读到。\n"
        "#\n"
        "# `cli:` 段 = 工作台「CLM 参数（随机任务传）」那一组 —— 12 个**任务级**参数，\n"
        "# 它们不在 dgtf_config.yaml 里，是随任务当命令行参数传给引擎的。\n"
        "# ★ 这一段的键在**每次任务跑完后会被清空**（CLM 参数只作用于当次任务）。\n"
    )
    return head + body


def save_params(overrides: dict) -> dict:
    """把 `{扁平键: 值}` **持久化写回用户配置** `dgtf_config.user.yaml`。

    返回 `{"saved": [...], "skipped": [...], "missing": [...], "unchanged": [...],
    "error": str|None, "user_file": str}`。四条硬约束：
      · 密钥键（READONLY_KEYS）**拒绝写回** —— 见那张表的注释；
      · ★ R38：CLM（`cli.*`）键**允许写回** —— 它们不在出厂 yaml 里，但要持久化到
        用户配置的 `cli:` 段（判「存在」时不能只对照出厂表，要单独放行）；
      · 类型按**出厂 yaml 里的原类型**还原（`_coerce_like`），列表不会被写成字符串；
      · **出厂 `dgtf_config.yaml` 一个字节都不动**（它是对照基线，「恢复出厂」靠它）；
        写前备份用户配置，写完**回读校验**读回来的值确实变了。
    """
    out = {"saved": [], "skipped": [], "missing": [], "unchanged": [],
           "error": None, "user_file": USER_CFG.name}
    overrides = overrides or {}
    if not isinstance(overrides, dict) or not overrides:
        return out
    factory = _load_yaml_flat(CFG)          # 校验「这个键存在吗」+ 取原类型
    if not factory:
        out["error"] = "读不到出厂配置，拒绝写回"
        return out
    cur = _load_yaml_flat(USER_CFG)         # 用户配置现状（可能不存在）

    merged = dict(cur)
    for k, v in overrides.items():
        k = str(k)
        if k in READONLY_KEYS:
            out["skipped"].append(k)
            continue
        # ★ R38：CLM 键 —— 不在出厂表里，但仍要持久化（落到 `cli:` 段）
        if k.startswith(CLI_SECTION + "."):
            leaf = k.split(".", 1)[1]
            if leaf not in CLI_KEYS:
                out["missing"].append(k)
                continue
            val = str(v).strip()
            merged[k] = val
            out["saved"].append(k)
            continue
        if k not in factory:
            out["missing"].append(k)
            continue
        val = _coerce_like(factory[k], v)
        if k in merged and merged[k] == val:
            out["unchanged"].append(k)
            continue
        merged[k] = val
        out["saved"].append(k)

    if not out["saved"]:
        return out
    try:
        if USER_CFG.exists():
            USER_CFG.with_suffix(".yaml.bak").write_bytes(USER_CFG.read_bytes())
        USER_CFG.write_text(_dump_user_cfg(merged), encoding="utf-8", newline="\n")
    except OSError as e:
        out["error"] = f"写盘失败：{e}"
        out["saved"] = []
        return out
    # 回读校验：写进去的键，读回来的值必须真的变了（防「写了但没生效」）
    try:
        after = _load_yaml_flat(USER_CFG)
        bad = [k for k in out["saved"] if after.get(k) != merged[k]]
    except Exception as e:  # noqa: BLE001
        out["error"] = f"回读校验失败：{e}"
        return out
    if bad:
        out["error"] = "回读校验不一致：" + ", ".join(bad)
    return out


def reset_params() -> dict:
    """**恢复默认配置**：删掉用户配置 ⇒ 全部键回落到 `dgtf_config.yaml` 出厂值。

    返回 `{"ok": bool, "removed": bool, "user_file": str, "error": str|None}`。
    ★ 只删**用户配置**这一份；出厂 yaml 永不触碰（删了就没有「默认」可言了）。
    """
    out = {"ok": True, "removed": False, "user_file": USER_CFG.name, "error": None}
    if not USER_CFG.exists():
        return out
    # 先备份一份（用户可能想找回自己那套），再删
    try:
        USER_CFG.with_suffix(".yaml.bak").write_bytes(USER_CFG.read_bytes())
    except OSError:
        pass
    try:
        USER_CFG.unlink()
        out["removed"] = True
    except OSError as e:
        out["ok"] = False
        out["error"] = f"删除用户配置失败：{e}"
    return out


def clear_cli_saved() -> dict:
    """★ R38：**清空用户配置里的 `cli:` 段**（CLM 参数「每执行一次任务清零」）。

    返回 `{"ok": bool, "removed": int, "error": str|None}`。
    ★ 只动 `cli:` 这一段：把它的键从扁平表里剔掉，其余用户保存的键**一字不动**地写回
      —— 不能整个删文件（那样会把模型 / 联网那些用户配置一起抹了）。
    ★ 没有 `cli:` 段时是**幂等空操作**（连文件都不重写），避免无谓的 mtime 抖动。
    """
    out = {"ok": True, "removed": 0, "error": None}
    if not USER_CFG.exists():
        return out
    cur = _load_yaml_flat(USER_CFG)
    cli_keys = [k for k in cur if k.startswith(CLI_SECTION + ".")]
    if not cli_keys:
        return out
    kept = {k: v for k, v in cur.items() if not k.startswith(CLI_SECTION + ".")}
    try:
        if USER_CFG.exists():
            USER_CFG.with_suffix(".yaml.bak").write_bytes(USER_CFG.read_bytes())
        if kept:
            USER_CFG.write_text(_dump_user_cfg(kept), encoding="utf-8", newline="\n")
        else:
            # 只剩 cli 段 ⇒ 整份用户配置没内容了，删掉它（等于回到全出厂）
            USER_CFG.unlink()
        out["removed"] = len(cli_keys)
    except OSError as e:
        out["ok"] = False
        out["error"] = f"清空 CLM 参数失败：{e}"
    return out


def build_temp_config(overrides: dict, out_path: Path) -> str | None:
    """把 `{扁平键: 值}` 覆盖到 yaml 副本上，返回可传给 `--config` 的路径。

    起点 = **出厂 yaml + 用户配置**（`effective_flat`），再套本次任务的
    `overrides`（「仅本次任务生效」那条路 —— 不落盘）。
    """
    overrides = overrides or {}
    flat = effective_flat()
    if not flat:
        return None
    raw: dict = {}
    for k, v in flat.items():          # 先铺生效值（嵌套需要字典结构）
        node = raw
        parts = str(k).split(".")
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        node[parts[-1]] = v
    for k, v in overrides.items():     # 再叠本次一次性覆盖
        node = raw
        parts = str(k).split(".")
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        leaf = parts[-1]
        # ★ 按原类型还原（列表 / 布尔 / 数字）—— 直接写字符串会把
        #   channels 这类列表型键写坏（见 _coerce_like 注释）。
        node[leaf] = _coerce_like(node.get(leaf), v)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8", newline="")
        return str(out_path)
    except OSError:
        return None
