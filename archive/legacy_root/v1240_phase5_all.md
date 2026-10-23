# Phase 5 · F2 all 元层闭合机制

## 定位

F1 职责收口已通过（新跑 114408：all 四件套原生、core_ok=true、repairs=[]）。
F2 只做 all 元层：让闭合成为**可验证的 ClosurePackage**，不生成新内容。

## 机制

dgtf_v2/layers_all.py：

- 六件套：decision / actions / not_do / residual_risks / provenance / confidence；
- 动作四字段：owner / deadline / acceptance / rollback；
- 允许从 1 层继承 actions/not_do，但必须标 actions_origin / not_do_origin，不能冒充 all 原生；
- 读数：closure_completeness、risk_transparency、action_quality；
- 缺项进 gaps，不补空话；validate_closure 对不合规包抛错。

引擎：actions.all_v2（默认 true）；开启后只写 packed.all_closure，**不改 views**；
不通过时 quality.flags 加 all_closure_gaps。

## 离线验证（114408）

| 指标 | 值 |
|---|---|
| ok | true |
| closure_completeness | 1.0 |
| risk_transparency | 1.0 |
| actions_origin | all |
| 动作四字段 | 5 / 5 |
| gaps | [] |
| confidence | .6667 |

## 判据

python dgtf_v2/tests_all.py -> 9 / 9

覆盖：完整包、缺 actions、动作四字段不全、继承 origin、空 all、validate 抛错、真实 packed 组装。

## 真实 all_v2 跑（124316）

Q2 600k / takeover / all_v2=true：**88 calls / 565,297 tokens**，四层全跑。

| 检查 | 结果 |
|---|---|
| packed.all_closure.ok | **true** |
| closure_completeness | **1.0** |
| risk_transparency | **1.0** |
| actions | **6 / 6 四字段齐** |
| actions_origin | **all** |
| confidence | .3333 |
| gaps | [] |
| core_ok | **true** |
| quality.flags | 无 all_closure_gaps |
| core_duty | ok=true、repairs=[]、overreach=[]

无 `all_closure_gaps`，结构门通过。

### 质量口径：tri_ratio 与 α 都不能用于放行

- 旧 quality.tri_ratio = **原始一致率**（agree/total），不是三态质量；
- 新 quality.tri_alpha 是 **跨视角一致性**（strict/conservative/angle 三个视角被刻意设计成不同）；
  它衡量的是**集成多样性**，不是 test-retest 可靠性；
- 124316：tri_ratio .333、跨视角 α .082；baseline Q2：tri_ratio 1.000、跨视角 α 0.000；
- 两者都不构成“三态可靠”证据；当前 **tri_quality="unmeasured"**，不拿 raw/α 放行。

F2 质量门改用**可测的量**：coverage + ClosurePackage 结构 + core_duty。

## 最终放行（四层真跑 5/5）

| 题 | calls/tokens | all_closure.ok | cc | core_ok |
|---|---|---|---:|---|
| Q2 124316 | 88 / 565k | true | 1.0 | true |
| Q2 140654 | 88 / 570k | true | 1.0 | true |
| biz001 181557 | 91 / 449k | true | 1.0 | true |
| law002 184834 | 93 / 443k | true | 1.0 | true |
| biz002 194142 | 89 / 447k | true | 1.0 | true |

- 全部 route 0,1,both,all，成本 5/5 在 600k 内；
- boundary profile：边界题不强制 actions/not_do，只要求 decision/residual/provenance/confidence；
- actions.all_v2 已默认 true；
- eng001 664k 超预算 10.6%，仅作额外结构证据，不计入成本合格 5 题。

F2 **放行完成**。

