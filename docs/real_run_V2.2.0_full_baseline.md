# V2.2.0 四层真跑基线与融合审计

日期：2026-10-23
类型：真实四层基线回放 + V2.2.0 内联融合审计
**不是新的 V2.2.0 API 真跑。**

## 基线

- 文件：outputs/20261023_082429_Python中len函数的作用.packed.json
- route：0 → 1 → both → all（四视图齐全）
- llm_calls：90
- llm_tokens：881,364
- answer_ready：true
- process_ready：true
- answer_quality：verified
- coverage：0.5

## V2.2.0 融合审计

- history_fusion：178 个历史版本 / 17 条能力轴 / readiness=1.0
- behavior_fusion：v2_contract
- capabilities_total：5
- audit_behavior：full_route=true / quality_score=0.875 / answer_ready=true
- 回放输出：outputs/20261023_V2.2.0_full_baseline_replay.packed.json

## 边界

V2.2.0 新 API 真跑在多次尝试中遭遇 DeepSeek 长请求无返回，未生成新 packed。
因此本文件只能证明“历史四层真实跑基线 + V2.2 融合审计”，
不能替代“V2.2.0 新 API 四层真跑通过”。
新真跑需要在 API 恢复或换通道后重跑。
