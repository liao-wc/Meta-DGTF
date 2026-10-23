# bench 全量报告 · v1221_full

- src：`元DGTF-V1.22.1.py`　mock：False　产物 20/20
- profile 覆盖：`economy`　rounds 覆盖：`0:2,1:2,both:2,all:3`
- 题目来源：按目录枚举 `meta.json`（20 题）
- ⚠️ **本批为降档跑**（预算受限）：原始档见题目 yaml；原始档的真跑证据在阶段 1 的 `bench/runs/p1v2`。

| 题 | 取向 | 判定 | 一致率 | 分层 pass | rubric | 层 | 调用 |
|---|---|---|---|---|---|---|---|
| biz_001 | decision | partial | 100%（5/1/0） | ✅ | 2/3 | 0、1、all、both | 94 |
| biz_002 | decision | decidable | 67%（3/1/2） | ✅ | 2/3 | 0、1、all、both | 94 |
| biz_003 | decision | partial | 83%（1/4/1） | ✅ | 2/3 | 0、1、all、both | 99 |
| eng_001 | decision | partial | 100%（6/0/0） | ✅ | 0/3 | 0、1、all、both | 91 |
| eng_002 | boundary | partial | 100%（4/2/0） | ✅ | 2/3 | 0、1、all、both | 96 |
| eng_003 | decision | decidable | 50%（0/3/3） | ✅ | 2/3 | 0、1、all、both | 81 |
| eng_004 | decision | partial | 100%（3/3/0） | ✅ | 2/3 | 0、1、all、both | 95 |
| law_001 | decision | partial | 83%（0/5/1） | ✅ | 2/3 | 0、1、all、both | 96 |
| law_002 | boundary | partial | 83%（1/4/1） | ✅ | 2/3 | 0、1、all、both | 96 |
| law_003 | decision | partial | 100%（3/3/0） | ✅ | 0/3 | 0、1、all、both | 90 |
| med_001 | decision | partial | 83%（0/5/1） | ✅ | 2/3 | 0、1、all、both | 97 |
| med_002 | decision | decidable | 100%（0/6/0） | ✅ | 0/3 | 0、1、all、both | 98 |
| med_003 | boundary | partial | 67%（0/4/2） | ✅ | 2/3 | 0、1、all、both | 91 |
| org_001 | decision | partial | 100%（2/4/0） | ✅ | 2/3 | 0、1、all、both | 80 |
| org_002 | decision | partial | 100%（2/4/0） | ✅ | 1/3 | 0、1、all、both | 99 |
| org_003 | boundary | partial | 100%（3/3/0） | ✅ | 2/3 | 0、1、all、both | 96 |
| tech_001 | decision | partial | 100%（3/3/0） | ✅ | 1/3 | 0、1、all、both | 88 |
| tech_002 | decision | partial | 0%（0/0/6） | ✅ | 2/3 | 0、1、all、both | 94 |
| tech_003 | decision | decidable | 100%（0/6/0） | ✅ | 2/3 | 0、1、all、both | 88 |
| tech_004 | boundary | decidable | 83%（2/3/1） | ✅ | 2/3 | 0、1、all、both | 96 |

**分层 pass**：20/20　**一致率可算**：20/20　**rubric 平均**：1.60/3
