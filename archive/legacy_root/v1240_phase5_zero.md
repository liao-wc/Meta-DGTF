# Phase 5 · F5 0 层审计契约

状态：**审计/novelty 已完成**；actions.zero_v2 默认 true（只读）；生成机制按设计延期。

## 代码

- dgtf_v2/layers_zero.py：ZeroLayerPackage / assemble_zero_package
- dgtf_v2/tests_zero.py：10 / 10
- 引擎 actions.zero_v2（默认 true）→ packed.zero_contract（只读，不改 views）
- 预设 configs/方案L-ZeroV2-pilot.yaml

## 判定

- aspects>0；probes/suspensions 至少一项 > 0；
- actions/not_do 出现 → 0 层越权；
- novelty_curve 空 → novelty_measured=False，但**不记 gap**（延期读数）；
- deferred 恒 True；ok=原生齐全且 gaps 空。

## 真实回放

54 份 packed 的 views.0：ok=54、overreach=0、gap=0、novelty 均未测。  
历史回放：0 层核心职责干净；novelty 已在真实跑接入；生成机制仍延期，不接 L0-v2。

## 真实跑（只跑 0 层，163612）

- 29 calls / 104,545 tokens；route=['0']；
- packed.zero_contract.ok=**true**、aspects=49、probes=3、suspensions=3；
- novelty_measured=**true**、deferred=**true**、no_actions=**true**、gaps=[]；
- novelty_curve：R1 new 6 / R2 new 7 / R3 new 7（从 round_log 只读派生，不改 0 层选择）。

结论：**F5 0 层审计/novelty 真跑通过；actions.zero_v2 默认 true（只读）；生成机制仍延期**。

## 放行条件

1. 0 层 contract ok；
2. novelty_curve 已有真实读数（163612：6/7/7）；
3. L0-v2 生成机制重新通过 Q2 A/B 前不接；
4. 审计 flag 默认 true，生成机制仍延期。
