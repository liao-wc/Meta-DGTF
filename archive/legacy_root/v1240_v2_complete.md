# V2 完成报告（reference）

## 完成结论

V2 reference 已收口：F2/F3/F4 全部有真实跑与回滚证据，F5 审计/novelty 真实跑通过；F5 生成机制按设计延期。L0-v2 以 archive 只读默认恢复。所有门禁绿。

## 生产默认（全开）

| 键 | 默认 |
|---|---|
| actions.l0_v2_curate | true（archive 只读） |
| actions.all_v2 | true |
| actions.one_v2 | true |
| actions.both_v2 | true |
| actions.zero_v2 | true（只读审计） |

## F2 all_v2（5 真跑，4 层）

| 题 | calls/tokens | all_closure.ok | cc | core_ok | 备注 |
|---|---|---|---:|---|---|
| Q2 124316 | 88 / 565k | true | 1.0 | true | |
| Q2 140654 | 88 / 570k | true | 1.0 | true | |
| biz001 181557 | 91 / 449k | true | 1.0 | true | coverage null：6 条全 undecidable |
| law002 184834 | 93 / 443k | true | 1.0 | true | boundary profile，actions_expected=false |
| biz002 194142 | 89 / 447k | true | 1.0 | true | coverage .4786；6 个 answerable 全答 |

结构 **5/5**、成本 **5/5 在 600k 内**。

额外第 6 个结构样本 eng001 184904：92 / 664k，all_closure.ok=true，但超软预算 10.6%，只作结构证据、不计入成本合格 5 题。

## F3 1 层（5/5 + full-4）

分层 5/5：151716、162801、163040、164640、165201，one_contract.ok=true、complete=1.0。  
四层 full-4 204700：91 / 572k，route 0,1,both,all，one_contract.ok=true、complete=1.0、core_ok=true。

## F4 both（6/6 + full-4）

分层 6/6：160157、163121、164458、164848、165457、165958，native=true、completeness=1.0。  
四层 full-4 204724：89 / 551k，route 0,1,both,all，native=true、completeness=1.0、core_ok=true。

## F5 0 层（审计/novelty）

163612：29 calls / 104.5k；zero_contract.ok=true、novelty_measured=true、deferred=true；novelty curve 6/7/7。

## L0-v2 恢复

- 默认 actions.l0_v2_curate=true、l0_v2_mode=archive。
- archive 已移出生成路径：只在 _pack_result 对最终候选做只读档案/novelty，写 packed.l0_v2_archive；不裁剪、不注入 prompt、不改 views ⇒ 零生成行为差。
- guide/filter 仍实验，不默认；tests_l0 16/16。

## 门禁

| 门 | 结果 |
|---|---|
| 冒烟 | 266 / 0 |
| 跨档验收 | 319 / 0 |
| 前端自检 | 371 / 0 |
| L0-v2 | 16 / 16 |
| F3 | 10 / 10 |
| F4 | 10 / 10 |
| F5 | 10 / 10 |
| F2 | 9 / 9 |
| 核心职责 | 9 / 9 |
| V2 判据 | 41 / 41 |
| 变异体 / 内核 | 3 / 3、24 / 0 |

## 已知残留

1. eng001 额外样本成本 +10.6%：结构过，但未计入成本合格 5 题；
2. F5 生成机制按设计延期；
3. F2 biz/law coverage null 是“无 answerable 分母”，非质量 0；
4. L0 archive 是只读可观测，不是原 L0 生成机制；
5. F2/F3/F4/F5 flags 现已全部生产默认开；F5 只开只读审计，生成机制仍延期。

## 证据

- F2 成本合格 5：outputs/20261019_124316、140654、181557、184834、194142 packed
- F2 额外：184904（超预算，结构证据）
- F3：151716、162801、163040、164640、165201
- F4：160157、163121、164458、164848、165457、165958
- F5：163612
- 门禁日志：_gate_v2final_*、_smoke_rs.log
