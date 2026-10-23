# 四层核心职责审计与可靠性修复

## 问题不是 LLM 波动，而是三个结构性错位

1. **1 层越权**：历史 packed 里 18/20 把 actions/not_do 写进 views.1。  
   契约明确：1 研究禁止 action_plan；行动属于 all。  
   来源不是 LLM，而是 _pack_result 为了报告把 1 层 actions 塞进 views.1。

2. **all 层缺行动**：views.all.actions 为空，最终只能靠 manifest 文本。  
   同时 1 层的 actions 已经存在——不是没做，是放错层。

3. **证据映射误报**：1 层 decidable 有 decidable_product.evidence，  
   但旧 bridge 只读每个 sub_question.citations，误报“无引用”。

## 职责修复（不造内容）

### 1. 源头上移 actions/not_do

_pack_result 不再写 views.1._actions / views.1._not_do；改为：

- packed.actions / packed.not_do（顶层）；
- 若 all 存在：views.all.actions / views.all.not_do；
- 同时从 views.1 的 decidable_product 中移除 actions。

旧消费者 bench_report.py 已加回退：all.actions → packed.actions → views.1._actions（兼容旧产物）。

### 2. 契约映射修正

- 1 层按真实产物 decidable_product（answer + evidence）映射，而不是逐 sub_question 硬找 citations；
- all 层 actions/not_do/residual/provenance 从实际产物读取；
- 动作字段对齐：owner_role→owner、deadline_hint→deadline、fallback→rollback（只换字段名，不改内容）。

### 3. core_duty 审计

新增 dgtf_v2/core_duty.py：

| 层 | 必须做 | 禁止 |
|---|---|---|
| 0 | aspect_map、probe 或 suspension | answer / action / decision |
| 1 | 子问题 + decidable 证据（层 evidence 或逐条 citation） | action_plan / final_decision |
| both | synthesis/张力/论证图 | final_decision / action_plan / 删败方 |
| all | decision、actions、not_do、residual_risks、provenance | 新内容 / 伪造闭合 |

- 修复是“搬已有内容 + 换字段”，不是补空话；
- 修不了就记 gap，不把 gap 伪装成 pass；
- 未跑的层（route 不含 / 无 view）标 skipped/blocked，不误判。

## 20 份历史 packed 审计结果

| 指标 | 数值 |
|---|---|
| 全过 | **2 / 20** |
| 1 层 action_plan 越权 | **18 / 20** |
| all 缺 decision | **4** |
| all 缺 residual_risks | **4** |
| actions 从 1 迁到 all | 18 |
| 0 层核心失败 | 0 |
| both 核心失败 | 0 |

说明：18 份是历史落盘错位；4 份 all 缺项集中在没有产出 all 的跑次（预算/裁层），审计不伪造闭合。证据：audits/core_duty_20.json。

## 判据

python dgtf_v2/tests_core.py -> **9 / 9**

覆盖：新式 packed 四层通过、旧式 1 层越权、actions 迁移、all 缺 actions、0 缺 probe、未跑层跳过、修复不改原 packed、真实 packed 审计、修复记录。

## 新跑次验证（最终通过）

### 跑次 1：110457（源头补丁前）

| 检查 | 结果 |
|---|---|
| views.1._actions | 无 ✅ |
| packed.actions / all.actions | 3 / 3 ✅ |
| all.decision / residual / provenance | 原始均 None ⚠️ |
| 当前 core_duty 重审 | ok=false，repairs=3 项 |

### 跑次 2：114408（源头补丁后，最终验证）

outputs/20261019_114408_AI能否独立完成数字IC设计边界.packed.json  
**91 calls / 603,153 tokens / 四层全跑（dispatch.ran=0,1,both,all / missing=[]）**

| 检查 | 结果 |
|---|---|
| views.1._actions | **无** ✅ |
| views.1.decidable_product.actions | **无** ✅ |
| packed.actions / not_do | **5 / 3** ✅ |
| views.all.actions / not_do | **5 / 3** ✅ |
| views.all.decision | **非空**（结构化 manifest 段） ✅ |
| views.all.residual_risks | **5 条** ✅ |
| views.all.provenance | ["v1:packed"] ✅ |
| packed.core_ok | **True** ✅ |
| quality.flags | 无 core_audit_gaps ✅ |
| v2_shadow.core.ok | **true**，gaps=[]，overreach=[] ✅ |
| core_duty.audit | **ok=true，repairs=[]，gaps=[]，overreach=[]** ✅ |
| 质量 | coverage .5234 / tri .6667 / 决策 5 / 不做 3 |

**结论：1 层越权与 all 原生四件套都已在真实跑次端到端关闭，core_audit 无 repair。**

## core_gate 已接

- scheduler.v2.core_gate（默认 warn，off 可关）；
- gate≠off 且 core 存在：packed.core_ok = core.ok；
- core 缺失：不写 core_ok（不把“没跑审计”误读成“不通过”）；
- 不通过：quality.flags 加 core_audit_gaps + 一行 warning，不阻断；
- md 增加“层核心职责”行；
- 判别力：_gate_core_gate_probe.py 12/0、_gate_core_e2e.py 15/0。

## 职责修复后的门禁

| 门 | 结果 |
|---|---|
| 冒烟 | 266 / 0 |
| 跨档验收 | 319 / 0 |
| 工程审计 | 70 / 0 |
| 前端自检 | 371 / 0 |
| 核心职责判据 | 9 / 9 |
| core_gate 判别力（probe） | 12 / 12 |
| core_gate 端到端（e2e） | 15 / 15 |
| V2 判据 | 41 / 41 |
| L0-v2 判据 | 16 / 16 |

