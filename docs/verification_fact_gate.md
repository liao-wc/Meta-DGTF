# 事实题质量门验证

日期：2026-10-24

## 修复

- evidence.detect_conflicts 忽略裸数字（无 anchor/context/unit）；
  之前 1..30 的任务编号/步骤计数会被误判成数值冲突，导致 FactCard=conflict、answer unverified。
- question_terms 增加“的返回值/返回值/返回什么”停用词，避免“返回什么”被误判题面未覆盖。
- 新增 tests_evidence 负对照：两段不同任务列表的裸数字不报冲突。

## 证据

- 事实题四层真跑：83 calls / 671,144 tokens；route 0,1,both,all；每层 2 圈。
- process_ready=true；answer_ready=true；answer_quality=verified；coverage=0.67。
- FactCard status=answered，official evidence 7 条，gaps=[]。
- 产物：outputs/20261024_082341_Python中len函数的作用是什.packed.json

## 边界

事实题仍要求官方证据；不为了通过把 unverified 硬改 verified。
