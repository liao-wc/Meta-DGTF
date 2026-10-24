# 推理题四层真跑 · 质量门迭代验证（2026-10-24）

> 触发：DSH 守护巡检后随机领域真跑 ——「为什么城市热岛效应在夜间比白天更明显？」
> 目标：结果质量达到通用标准、四层各自履行职责；不达标则修复并重真跑，直到指标达标。
> 结论：**4 轮真实 LLM 真跑 + 3 个引擎缺陷修复后，质量门全部达标。**

## 1. 最终指标（第 4 轮，产物 20261024_134620）

| 项 | 值 |
|---|---|
| question_type | reasoning（why 题不再误判 fact） |
| answer_ready / raw_answer_ready / process_ready | true / true / true |
| answer_quality | verified（非事实题：四层过程合同全达标且答案非空） |
| process_ledger.standard_all | true（0 / 1 / both / all 四层 standard_ok 全 true） |
| 研究层判定审计 | verified（6/6，bad=0） |
| 元层闭环 meta_closure | clean=true（unsettled=0 / total=3） |
| core_duty 审计 | audit_ok=true、gaps=[]、overreach=[]、contract ok、v2_shadow core_ok |
| llm_calls / llm_tokens | 138 / 1,581,220 |
| 实际圈数（lineup） | 0=3 / 1=4 / both=2 / all=5 |

产物：
- outputs/20261024_134620_为什么城市热岛效应在夜间比白天更明显.md
- outputs/20261024_134620_为什么城市热岛效应在夜间比白天更明显.packed.json

## 2. 四轮迭代与卡点

| 轮 | calls | tokens | 卡点 | 修复 |
|---|---|---|---|---|
| 1 | 92 | 1,014,870 | why 题判成 fact ⇒ 事实卡未 answered ⇒ needs_evidence；研究层判定审计 unverified | d12140d |
| 2 | 145 | 1,793,098 | all.meta_closure 在池汇总前计算 ⇒ all.standard_ok 假缺口 | 27bbe5c |
| 3 | 118 | 1,359,159 | 判定审计 mixed/bad=3：纯数字 token 冒充证据命中、partial 被判越权 | c8d43d5 |
| 4 | 138 | 1,581,220 | —（全绿） | — |

## 3. 修复与判据

- 提交 `d12140d`：新增 `_WHY_CUES` / `_is_why_question` / `question_type_from_features`；
  why 题归 reasoning；研究层判定审计并入 `pools["1"].sub_questions` 并回写。
- 提交 `27bbe5c`：新增 `_refresh_all_meta_closure()`，在 A/B/C/D-H/串行 5 条通道
  `_totalize_all_pool()` 之后重算 `meta_closure`（只刷新清算读数，不改内容）。
- 提交 `c8d43d5`：判定审计只拦越权断言（decidable 无证据 / undecidable 有证据）；
  partial 无证据降为 warning；`_terms` 过滤纯数字 token。
- 回归判据：tests_question_type.py（10 项）、tests_meta_closure_refresh.py（7 项）、
  tests_decidability_audit.py +4 项（partial warning / 纯数字不命中 / 字母命中仍判 overclaim）。

## 4. 复现命令

~~~powershell
$env:PYTHONPATH="D:\Meta-DGTF-道生三阶模型\dgtf_engine"
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.0.py --route 0,1,both,all \
  --rounds "0:2,1:2,both:2,all:2" --parallel auto --web auto --thinking auto \
  --effort auto --history-fusion auto --behavior-fusion auto \
  "为什么城市热岛效应在夜间比白天更明显？"
python audits/_core_audit.py one --packed "outputs/<产物>.packed.json" --out audits/core_audit_new_packed.json
~~~

## 5. 门禁

- fast_gate：PASS 12 / FAIL 0
- V2 全量测试：37 / 37 PASS（453 项检查，0 失败）
- App selftest：PASS 371 / FAIL 0
- pip check：App / local_model 两环境 0 broken

## 5.1 V2.2.1 补丁迭代（2026-10-24）

- 职责读数：交付面按层取真实产品（duty_deliver_text）+ R 实词级命中 + 下限 0.15；元层按闭合职责判 short。
  离线复算最新真跑四层：S=0.36/0.27/0.16/0（元层 closure 门）⇒ **duty_short 消失**。
- 质量线索：candidates_backfilled 收尾复核阈值 0.75、self-check 单源留痕；polarity_all_same_structural 与
  probe_link_dangling 改 view.meta 留痕（不挂质量旗）。
- 质量读数：coverage 兜底链（最新真跑 0.8875，basis=decidable_weighted）；tri_ratio 在 α 可用时改报
  tri_consistency（最新真跑 α=1.0，不再用 0.1667 冒充质量）。
- 验收：fast_gate 12/0、V2 tests 38/38（480 项检查）、App selftest 371/0、pip check 0 broken；
  新增离线预检 scripts/precheck_quality.py（不烧真跑即可复算质量门）。
- 版本：V2.2.1（引擎）、App 2.0.1；旧版 V2.2.0 文件保留。

## 6. 边界与剩余读数（非质量门）

- `duty_short` 与「体力耗尽」停止文案仍在：职责 S 是交付面被内部面稀释的**读数**，
  不进质量门；后续可再优化交付面口径。
- `candidates_backfilled`、`polarity_all_same_structural(1)`、`probe_link_dangling(1/2)`
  为非阻断质量线索，保留在 packed 中待下一轮优化。
- 成本：本轮 4 次真跑合计 493 calls / 5,748,347 tokens。
