# Phase 5 扩样记录

## F3 1 层（route=1）

| 题 | packed | calls/tokens | one_contract.ok | citations | core 1 层 |
|---|---|---|---:|---|---|
| Q2 | 151716 | 28 / 110034 | true | 2/2 | ok, cited 2 |
| biz001 | 162801 | 25 / 68689 | true | 2/2 | ok, cited 2 |
| law002 | 163040 | 26 / 63625 | true | 2/2 | ok, cited 2 |
| eng002 | 164640 | 26 / 66332 | true | 2/2 | ok, cited 2 |
| tech002 | 165201 | 25 / 136943 | true | 1/1 | ok, cited 1 |

5/5 契约通过，无 overreach/gap/repair；tri α 仅诊断，均未覆盖标签。

追加四层 full-4：204700，91 calls / 572,524，route 0,1,both,all，one_contract.ok=true、completeness=1.0、core_ok=true。

## F4 1+both（route=1,both）

| 题 | packed | calls/tokens | ok | native | completeness |
|---|---|---|---:|---|---:|
| Q2 | 160157 | 44 / 164651 | true | true | 1.0 |
| biz002 | 163121 | 46 / 149682 | true | true | 1.0 |
| tech001 | 164458 | 46 / 248840 | true | true | 1.0 |
| law002 | 164848 | 45 / 136703 | true | true | 1.0 |
| org001 | 165457 | 46 / 155549 | true | true | 1.0 |
| med001 | 165958 | 47 / 134636 | true | true | 1.0 |

6/6 native=true/completeness=1.0。

追加四层 full-4：204724，89 calls / 551,258，route 0,1,both,all，native=true、completeness=1.0、core_ok=true。  
已知异常：law002 跑在 conflict_resolution 修复前，值为字面 "None"；org/med 为修复后。另 org001 有 1 次 json 修复，med001 有 1 条 ing 解析失败留痕，均不阻断。

## F5 0 层（route=0）

| packed | calls/tokens | zero_contract.ok | novelty_measured | deferred |
|---|---|---:|---|---|
| 163612 | 29 / 104545 | true | true | true |

## F2 all

124316 / 140654：all_closure.ok=true；三态仅标签诊断。

## 结论

- F3/F4 达到 5+ 样本；F5 读数接入但机制延期。
- 生产默认全部 false；preset 实验配置。
