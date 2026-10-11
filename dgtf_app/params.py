# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 把 `dgtf_config.yaml` 摊成可调参数（给「高级参数」面板）。

为什么：改配置以前要开 yaml 文件手动编辑。这里把 yaml **扁平化**成
`a.b.c → 值` 的列表交给前端渲染，用户改了以后由 `build_temp_config()`
生成一份**临时副本**用 `--config` 传给引擎 —— 原件不动。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import outputs_index as oi

CFG = oi.PROJECT_ROOT / "dgtf_config.yaml"

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

# ── 参数键 → 中文说明（标签统一成「键（说明）」，与 CLI 参数那一组同格式）──────
# ★ 为什么写显式表、不去抓 yaml 注释：注释是给**一整段**写的，逐键抓会继承到
#   容器 / 甚至文件头的文字（实测 164 个键里 47 个只能继承，抓出来是
#   「元 DGTF · v1.23…」这种噪声），格式反而更乱。这张表一一对应，改配置时同步改。
_KEY_CN: dict[str, str] = {
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
    "web_search.tier_proposal": "tier 提案表（人工确认前不生效）",
    "web_search.domain_tier_rules": "域名 → tier 人工确认表",
}

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


def load_params() -> dict:
    """返回 {groups:[{key,label,items:[…]}], total}。"""
    try:
        raw = yaml.safe_load(CFG.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        raw = {}
    flat = _flatten(raw)
    groups: dict[str, list] = {}
    for k, v in flat.items():
        groups.setdefault(k.split(".")[0], []).append(_item(k, v))
    out = []
    for top, items in groups.items():
        items.sort(key=lambda x: (0 if x.get("pinned") else 1, x["key"]))
        out.append({"key": top,
                    "label": dict(GROUP_LABEL).get(top, top),
                    "items": items})
    out.sort(key=lambda g: (_ORDER.get(g["key"], 99), g["key"]))
    return {"groups": out, "total": len(flat)}


def build_temp_config(overrides: dict, out_path: Path) -> str | None:
    """把 `{扁平键: 值}` 覆盖到 yaml 副本上，返回可传给 `--config` 的路径。"""
    overrides = overrides or {}
    try:
        raw = yaml.safe_load(CFG.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        return None
    for k, v in overrides.items():
        node = raw
        parts = str(k).split(".")
        ok = True
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        if ok:
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
