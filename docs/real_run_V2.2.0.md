# V2.2.0 四层真跑

## 4. 四层真跑

- 命令：route 0,1,both,all；rounds 2；web off；thinking off；behavior-fusion on。
- 结果：完整四层真跑完成，四视图 0/1/both/all 均落盘。
- llm_calls：85
- llm_tokens：534,928
- rounds：0=2、1=2、both=2、all=2
- process_ready：true
- answer_ready：false
- answer_quality：unverified
- coverage：0.8773（answered 3 / answerable_total 3）
- history_fusion：178 个历史版本 / 17 条能力轴 / readiness=1.0
- behavior_fusion：arm=v1_frontier / capabilities_total=3 / 178 历史版本
- 产物：outputs/20261023_231902_Python中len函数的作用是什.packed.json
- 附：单圈同路径也完成，42 calls / 251,719 tokens。
- 说明：四层流程已跑完，但最终质量门未 ready，不冒充 verified。

## 4.1 引擎修复

- 发现 --thinking off 只关了 default/stages，未关 reasoner 档，导致 ing/view 长调用卡住。
- V2.2.0 引擎已修：_apply_runtime 同步写 api.thinking.reasoner。
- 新增内联判据 case_runtime_thinking_off。
