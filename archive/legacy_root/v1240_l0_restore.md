# L0-v2 恢复记录（archive 只读）

## 恢复内容

- 默认 actions.l0_v2_curate: true
- 默认 actions.l0_v2_mode: archive
- archive 模式：只读 MAP-Elites 档案、novelty、极性缺口、archive_dirs；不裁剪候选、不注入 prompt。
- guide（可选提示）/ filter（旧硬裁剪）仍保留为实验模式，默认不用。

## 失败历史与修复

| 变体 | 旧结果 | 处理 |
|---|---|---|
| v1 filter | Q2 覆盖 4/4→2/6，三态 .5 | 否决，不默认 |
| v2 guide（旧） | 2/2/.333 或 5/6/.5 | 改为可选提示，仍不默认 |
| v2-safe guide | 单样本 on coverage .792 vs off .954 | 仍不默认 |
| archive | 单样本 on .692 vs off .954（无生成副作用，判为采样波动） | 默认恢复为只读 |

## 代码

- dgtf_v2/layers_l0.py：observe 增 should_guide/missing_polarity/archive_dirs；guide 仅 round≥3 且停滞/极性缺口时提示；新增 archive 分支。
- 引擎 _l0_v2_guidance_block：可选检查，不强制换词。
- 配置 方案N-L0v2-archive.yaml；主配置默认 archive。

## 验证

- python dgtf_v2/tests_l0.py：16 / 16
- archive 0+1 单层 A/B：172638 guide / 172713 off / 175236 archive
- archive 无 behavior path（无候选裁剪、无 prompt 注入）；coverage 差异不归因于 L0，需重复样本判定。

## 限制

- archive 不等于“L0 生成机制恢复”；只恢复可观测/档案。
- guide/filter 生产默认关闭。
- A/B 单样本受 LLM 采样波动影响，不能声称收益。
