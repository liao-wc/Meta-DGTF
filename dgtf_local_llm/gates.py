# -*- coding: utf-8 -*-
"""本地服务侧的纯函数判据（**不依赖 torch**，零 GPU 也能测）。

为什么单独放一个模块
--------------------
`service.py` 顶部 `import torch`，于是任何「从 service 里 import 一个纯函数
来测」的判据都被迫跑在带 torch 的本地 env 里（系统 python 直接 ModuleNotFound）。
把判定逻辑搬到这里，判据就能在**任何** python 下跑，且 `service.py` 只有一处
定义（不是复制一份）。
"""
from __future__ import annotations

_MB = 1024 * 1024

#: 有 LoRA 适配器的 stage（唯一定义处；`service.py` 的 STAGES 从这里取）。
#: 其余 stage 一律走 base model —— V2.2.13 起 service 不再按白名单拒绝。
LORA_STAGES = ("self_check", "self_check_min", "dual_judge", "route")

#: 各 stage 适配器的**训练长度**（= 该 stage 一条输出该有多少 token）。
#: 这是唯一定义处：`service.py` 与 `openai_shim.py` 都从这里取，避免两处漂移。
#:
#: ★★ [V2.2.13] 表项分两档：
#:   1. LoRA 四件套（self_check / dual_judge / route）——按适配器训练长度；
#:   2. 引擎经 extra_body 发来的其余 stage（expand_pair_merged / decompose_*
#:      / probe_* 等）——走 **base model**（无适配器）。这些此前不在表里
#:      ⇒ 落兜底 64 ⇒ 主生成 JSON 截断。初始统一 224（与 dual_judge 同档：
#:      prompt~2k + 224 + 2 < 3072 仍在 CUDA graph 快路径内），后续按 e2e
#:      实测的各 stage gen_tokens 分布校准 —— 表项**只压不抬**，模型自然
#:      EOS 时多要的 token 不生成、不付费。
#:   ★ 有牙判据 `tests_stage_coverage.py` 扫引擎源码的全部 stage 字面量，
#:     新增 stage 不登记就判红（否则又静默落 64 兜底）。
DEFAULT_MAX_NEW = {"self_check": 64, "self_check_min": 64,
                   "dual_judge": 224, "route": 96,
                   "expand_pair_merged": 224, "expand_pair_merged_fixup": 224,
                   # ---- 以下为 V2.2.13 登记（base model 通路，初始 224）----
                   "expand_pair": 224, "json_repair": 224, "ing": 224,
                   "assess_decidability": 224,
                   "assess_decidability_from_pool_view": 224,
                   "anchor_crosscheck": 224, "adjudicate_sub_tristate": 224,
                   "adjudicate_sub_tristate_multi": 224, "auto_plan": 224,
                   "he_amps": 224, "manifest": 224, "re_evaluate_pool": 224,
                   "re_anchor": 224, "ask_missing_polarity": 224,
                   "check_input_sanity": 224,
                   "check_structure_saturation": 224,
                   "decompose_normal": 224, "decompose_hybrid": 224,
                   "decompose_koan": 224, "decompose_from_pool": 224,
                   "decide_parallel_mode": 224, "probe_research": 224,
                   "probe_duel": 224, "probe_meta": 224, "phase_probe": 224,
                   "settle_research": 224, "plan_orientation": 224,
                   "plan_resources": 224, "tool_preflight": 224,
                   "tri_test_retest": 224}
#: 未登记 stage 的上限（防御值：只够小 JSON 决策，逼着新 stage 去登记）。
DEFAULT_MAX_NEW_FALLBACK = 64


def sanitize_stage(raw) -> str:
    """清洗 stage 字符串：只留 [a-z0-9_]，限长 48。空/全非法 ⇒ 空串。

    ★ 唯一定义处（V2.2.13 起从 openai_shim 迁来）：shim 与 service 都从
      这里 import —— stage 的合法字符集若两处各说各话，就会出现
      「shim 放行的 stage 到 service 被 400」的对不上。
    """
    s = "".join(ch for ch in str(raw or "").strip().lower()
                if ch in "abcdefghijklmnopqrstuvwxyz0123456789_")
    return s[:48]


def finish_reason_for(gen_tokens, max_new) -> str:
    """按「是否撞到长度上限」给出诚实的 finish_reason。

    ★ 适配层此前**硬编码 "stop"** —— 本地侧被 max_new 掐断的输出也报
      「正常结束」，引擎的续跑机制（last_finish == "length" ⇒ 续写）
      在本地链路上是死的：截断 JSON 全靠 json_repair 硬修。
    ★ 判据：生成 token 数 ≥ 上限 ⇒ "length"；否则 "stop"。
      解析失败/上限 ≤ 0 ⇒ "stop"（不假装截断）。
    """
    try:
        ct, mx = int(gen_tokens), int(max_new)
    except (TypeError, ValueError):
        return "stop"
    return "length" if (mx > 0 and ct >= mx) else "stop"


def cap_max_new(stage: str, requested) -> int:
    """把「调用方要的生成长度」压到该 stage 用得上的长度。

    ★★ 为什么必须压（实测，不是推断）
    本地服务的 CUDA graph 快路径有两条硬门槛：
      1. `prompt + max_new + 2 > 3072` ⇒ 直接抛错回退**慢路径**；
      2. 只有 `temperature == 0` 才走 graph。
    引擎调用普遍 temp 0.9/0.3 ⇒ 本来就走慢路径（约 150ms/token），
    于是 `max_new` 就是**纯成本**：慢路径下每多要一个 token 就多付 150ms。

    实测同一条 2048-token 的 prompt：
      · 要 2048 → 110s 撞超时（503），引擎再按 max_retries 重试 3 次 ⇒ 整跑拖死
      · 要 256  → 40.0s
      · 要 64   → 11.0s
    而模型在该 stage 实际只吐 22~27 个 token 就 EOS ⇒ 多要的那 2000 个 token
    是纯浪费。压到 stage 训练长度即可，一个 token 的有效输出都不会少。

    ★ 只做「压」，不做「抬」：调用方要得更少时原样返回。
    """
    cap = DEFAULT_MAX_NEW.get(str(stage or ""), DEFAULT_MAX_NEW_FALLBACK)
    try:
        req = int(requested)
    except (TypeError, ValueError):
        return int(cap)
    return max(1, min(req, int(cap)))


def should_reclaim(allocated: int, reserved: int,
                   ratio: float = 1.5, slack_mb: int = 512) -> bool:
    """显存碎片是否多到值得回收。

    `allocated` 是模型真正在用，`reserved` 是缓存分配器向驱动要来的总量；
    后者远大于前者就是碎片（空块仍占着驱动内存）。

    ★ 实测形态：服务连跑 7 小时后 allocated≈1075MB、reserved≈5818MB，
      推理慢约 10 倍，把 `test_judge_fastfail` 从 15.5s 拖到 307s 并判红。
      重启后恢复。⇒ 这条判定的阈值不是拍脑袋，是照着实测形态定的：
      5818 > 1075 × 1.5 + 512 = 2124 ⇒ True。

    ★ 也要保证**不该**回收时不回收：正常态（1086/1126MB）和「只有小量
      缓存」（0/400MB）都必须返回 False —— 过度回收会让下次分配重新向驱动
      申请，白增开销。
    """
    try:
        return (int(reserved)
                > int(allocated) * float(ratio) + int(slack_mb) * _MB)
    except (TypeError, ValueError):
        return False
