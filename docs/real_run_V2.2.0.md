# V2.2.0 四层真跑与质量门

## 4. 四层真跑与质量门

- 主题：如何决定一个四层推理系统先优化哪一层？
- route：0 → 1 → both → all；四视图齐全
- rounds：0/1/both/all 各 2 圈
- llm_calls：82
- llm_tokens：511,634
- process_ready：true
- raw_answer_ready：true
- answer_ready：true
- answer_quality：verified
- behavior_fusion：v2_pareto（capabilities_total=3）
- history_fusion：178 版本 / 17 轴 / readiness=1.0
- 产物：outputs/20261024_075807_如何决定一个四层推理系统先优化哪一层.packed.json

## 4.1 质量门语义

- 事实题：仍要求官方证据，冲突/未覆盖不冒充 verified。
- 非事实题（decision/reasoning）：四层过程合同全达标且答案非空 ⇒ answer_ready=true、answer_quality=verified（过程合同验证，不是官方事实证据）。
- 新增判据：非事实题质量门；事实题路径不变。

## 4.2 引擎修复

- --thinking off 只关 default/stages、未关 reasoner 档，导致 ing/view 长调用卡住；已修。
- 修复后四层真跑可稳定完成。
