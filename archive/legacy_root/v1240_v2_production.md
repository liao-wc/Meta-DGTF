# V2 生产接入与回滚矩阵

## 默认值（主配置 dgtf_config.yaml）

| 键 | 默认 | 开启后 | 回滚 |
|---|---|---|---|
| actions.all_v2 | **true** | packed.all_closure | 关 flag，回到 F1 |
| actions.one_v2 | **true** | packed.one_contract | 关 flag，无契约块 |
| actions.both_v2 | **true** | packed.both_argument + 原生 graph | 关 flag，无 both_argument |
| actions.zero_v2 | **true** | packed.zero_contract + novelty 读数 | 关 flag，无契约块 |
| actions.l0_v2_curate | **true** | 0 层 archive 只读档案/novelty（不改生成） | 关 flag 回退 |
| actions.tri_test_retest | false | 同 prompt 重测 2 次（诊断开销） | 关 flag |

默认全关 ⇒ V1 行为不变；preset 仅供实验：
- configs/方案I-AllV2-pilot.yaml（all_v2）
- configs/方案J-1V2-pilot.yaml（one_v2）
- configs/方案K-BothV2-pilot.yaml（both_v2）
- configs/方案L-ZeroV2-pilot.yaml（zero_v2；0 层延期）
- 各 flag off 回滚配置（J-off/K-off）。

## 真实证据

| 层 | on 跑 | off 回滚 | 结果 |
|---|---|---|---|
| F2 all | 124316 / 140654 | — | all_closure.ok=true |
| F3 one | 151716（28/110k） | 152307（25/94.8k） | one_contract.ok=true，citations 2/2 |
| F4 both | 160157（44/164k） | 161136（44/173k） | native=true，completeness=1.0 |
| F5 zero | 待补 | — | 审计 54/54 ok；novelty 派生已接 |

## 生产放行条件

1. F3/F4 各 5 题样本（当前 1 题）；
2. 默认保持 false，直到样本全绿；
3. F5 继续延期（L0-v2 未过 A/B）；
4. 所有门禁绿后，才允许改默认。

## 安全边界

- 观测/闭合 flag 都只读已有产物，不生成新句子；
- 1 层不得出现 actions/not_do（源头已移 all）；
- all 的 confidence 只在 all 自带/tri 可靠/coverage 代理三选一，且标来源；
- 三态一致率仅标签定义/诊断，不作质量门。
