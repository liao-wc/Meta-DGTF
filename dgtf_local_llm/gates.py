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

#: 各 stage 适配器的**训练长度**（= 该 stage 一条输出该有多少 token）。
#: 这是唯一定义处：`service.py` 与 `openai_shim.py` 都从这里取，避免两处漂移。
DEFAULT_MAX_NEW = {"self_check": 64, "self_check_min": 64,
                   "dual_judge": 224, "route": 96}
#: 未登记 stage 的上限（引擎绝大多数调用会落到兜底 stage）。
DEFAULT_MAX_NEW_FALLBACK = 64


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
