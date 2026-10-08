# bench 全量报告 · v122_full

- src：`元DGTF-V1.22.0.py`　mock：False　产物 20/20
- profile 覆盖：`economy`　rounds 覆盖：`0:1,1:1,both:1,all:1`
- 题目来源：按目录枚举 `meta.json`（20 题）
- ⚠️ **本批为降档跑**（预算受限）：原始档见题目 yaml；原始档的真跑证据在阶段 1 的 `bench/runs/p1v2`。

| 题 | 取向 | 判定 | 一致率 | 分层 pass | rubric | 层 | 调用 |
|---|---|---|---|---|---|---|---|
| biz_001 | decision | partial | 100%（3/2/0） | ✅ | 0/3 | 0、1、all、both | 95 |
| biz_002 | decision | partial | 100%（5/1/0） | ✅ | 1/3 | 0、1、all、both | 97 |
| biz_003 | decision | partial | 33%（0/2/4） | ✅ | 0/3 | 0、1、all、both | 88 |
| eng_001 | decision | partial | 100%（5/1/0） | ✅ | 0/3 | 0、1、all、both | 55 |
| eng_002 | boundary | partial | 33%（2/0/4） | ✅ | 0/3 | 0、1、all、both | 55 |
| eng_003 | decision | partial | 100%（6/0/0） | ✅ | 0/3 | 0、1、all、both | 54 |
| eng_004 | decision | partial | 67%（0/4/2） | ✅ | 0/3 | 0、1、all、both | 54 |
| law_001 | decision | partial | 100%（3/3/0） | ✅ | 0/3 | 0、1、all、both | 54 |
| law_002 | boundary | partial | 67%（1/3/2） | ✅ | 1/3 | 0、1、all、both | 52 |
| law_003 | decision | decidable | 100%（0/6/0） | ✅ | 0/3 | 0、1、all、both | 53 |
| med_001 | decision | partial | 0%（0/0/6） | ✅ | 0/3 | 0、1、all、both | 53 |
| med_002 | decision | partial | 100%（2/4/0） | ✅ | 0/3 | 0、1、all、both | 53 |
| med_003 | boundary | partial | 100%（2/4/0） | ✅ | 0/3 | 0、1、all、both | 56 |
| org_001 | decision | partial | 83%（0/5/1） | ✅ | 0/3 | 0、1、all、both | 55 |
| org_002 | decision | partial | 100%（1/5/0） | ✅ | 0/3 | 0、1、all、both | 53 |
| org_003 | boundary | partial | 100%（2/4/0） | ✅ | 0/3 | 0、1、all、both | 53 |
| tech_001 | decision | decidable | 100%（5/1/0） | ✅ | 0/3 | 0、1、all、both | 53 |
| tech_002 | decision | partial | 100%（0/6/0） | ✅ | 0/3 | 0、1、all、both | 55 |
| tech_003 | decision | decidable | 100%（4/2/0） | ✅ | 0/3 | 0、1、all、both | 54 |
| tech_004 | boundary | decidable | 33%（0/2/4） | ✅ | 0/3 | 0、1、all、both | 53 |

**分层 pass**：20/20　**一致率可算**：20/20　**rubric 平均**：0.10/3
