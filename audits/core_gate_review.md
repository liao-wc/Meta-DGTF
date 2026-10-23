# core 职责门禁复核（Q2 600k 验证跑 vs 最近 20 份历史 packed）

> 执行：teammate `core-audit` · 共享任务 task-2 · 只读 `outputs/` 与 `dgtf_v2/`，写域仅 `audits/`
> 生成时间：2026-10-19T11:07:38+08:00
> 审计引擎：`dgtf_v2/core_duty.py:audit_packed` / `repair_packed`（先记修复前越权 → 修复 → 按修复后判缺口）
> 契约体检：`dgtf_v2/bridge.py:V2MemoryBridge.contract_report(gate="warn")`（内部同样先 repair 再 validate）
> 新 packed：`outputs/20261019_110457_AI能否独立完成数字IC设计边界.packed.json`（mtime 2026-10-19T11:04:58，id `20261019_104331`）
> 历史样本：`outputs/*.packed.json` 按 mtime 取 2026-10-19T10:43:27（Q2 跑启动时刻）之前最近 20 份 → 2026-10-14T20:14:23 ~ 2026-10-19T10:11:17

## 0. 结论速览

| 检查项 | 结果 | 判定 |
|---|---|---|
| 新 packed：`views.1` 是否有 `_actions` | **否**（无该键，长度 0；`decidable_product` 也不含 `actions`） | ✅ 放对层 |
| 新 packed：`views.all.actions` / `not_do` 长度 | **3 / 3** | ✅ 非空 |
| 新 packed：`views.all` 原生 decision / residual_risks | **均缺失（None）** | ⚠️ 原始字段不齐，靠 repair 兜底 |
| 新 packed：`v2_shadow.core` | **ok=true，gaps=[]，overreach=[]**（与重新审计逐字段一致） | ✅ 一致 |
| 新 packed：core_duty.audit | ok=true，overreach=[]，gaps=[]，repairs=[] | ✅ 通过（无需修复） |
| 新 packed：contract_report | ok=true，4 层全查，violations={}（gate=warn） | ✅ 通过 |
| 历史 20 份：ok / 越权 / gaps | ok 2（但均为单层跑次）；越权 18；gaps 4 | 18/20 不通过 |
| 历史 20 份：契约体检 | 16/20 通过，4 份 FAIL（均因 all 层未执行、为空） | 4 份不通过 |
| 新代码是否把 actions 放对层 | **是**：落盘时 1 层 actions/not_do 归位到 all（代码路径见 §2.4），packed 上复核一致 | ✅ 通过 |
| 未完成项 | 无阻塞；细节与风险见 §5 | — |

**一句话结论**：Q2 新 packed 把 actions/not_do 正确落到了 `views.all`（3/3），`views.1` 已无 `_actions`，`v2_shadow.core.ok=true` 且与新审计完全一致、无需任何 repair；但 **`views.all` 的原生 `decision`/`residual_risks`/`provenance`/`confidence` 仍为空**，"通过"是 repair 兜底后的结论（decision←manifest、residual←threads、provenance←["v1:packed"]、confidence←tri_ratio=0.1667，且 repairs 列表不记录这次兜底）——这是本次唯一需要 Lead 决策的遗留缺口。历史 20 份中四层实跑的 17 份全部存在 1 层 actions 错位（另 1 份两层跑次也越权；2 份"ok"是单层跑次不算四层通过），4 份 all 层 `dispatch.missing` 未执行而缺 decision/residual。

## Lead 后续修正（2026-10-19T11:15+08:00）

本报告 §0/§1 的“repairs=[] 却 ok=true”是当时 core_duty 的旧行为，已在后续修复：

1. repair_packed 现在记录 all.decision/all.residual/all.provenance 兜底项；
2. audit_packed 的 ok 要求 repairs 为空；修复后通过不算原始合规；
3. 用当前 core_duty 重审新 packed（110457）：
   - views.1 无 actions、all.actions/not_do 3/3；
   - 原始 all.decision/residual/provenance 缺失；
   - ok=false，repairs=[all.decision<-manifest/product, all.residual<-threads, all.provenance<-v1:packed]。
4. 已在 _pack_result 源头补 all 四件套；mock 全四层已验证 decision/provenance 落盘；
   真实跑次尚未覆盖该补丁，因此“all 原生四件套”仍不宣布关闭。
5. core_gate 已实现（默认 warn）：core 存在且不 ok → packed.core_ok=false + quality.flags 加 core_audit_gaps + warning；core 缺失不写 core_ok。
6. 判别力：_gate_core_gate_probe.py 12/0、_gate_core_e2e.py 15/0；最终 smoke 266/0、verify 319/0、audit 70/0、app 371/0。

## Lead 最终端到端验证（2026-10-19T11:45+08:00）

跑次 outputs/20261019_114408_AI能否独立完成数字IC设计边界.packed.json（91 calls / 603,153 tokens / dispatch.ran=0,1,both,all / missing=[]）：

| 检查 | 结果 |
|---|---|
| views.1._actions / decidable_product.actions | 均无 ✅ |
| packed.actions / not_do | 5 / 3 ✅ |
| views.all.actions / not_do | 5 / 3 ✅ |
| views.all.decision | 非空 ✅ |
| views.all.residual_risks | 5 条 ✅ |
| views.all.provenance | ["v1:packed"] ✅ |
| packed.core_ok | True ✅ |
| quality.flags | 无 core_audit_gaps ✅ |
| v2_shadow.core.ok | true，gaps=[]、overreach=[] ✅ |
| core_duty.audit | ok=true，repairs=[]、gaps=[]、overreach=[] ✅ |

结论：§0 的“all 四件套靠 repair”遗留缺口已在源头补丁后的真实跑次关闭。之前 110457 的 partial 结果保留为中间证据。

## 1. 口径与判定（为什么必须区分"原始字段"与"repair 后通过"）

- `audit_packed` 判定链：① 先看**修复前** packed，若 `views.0/1/both` 出现 `_actions` 或 `decidable_product.actions` → 记越权；② `repair_packed` 做三类搬运式修复：`1.actions->all`、`1.citations<-evidence`、`all` 四件套按**已有内容**补齐（decision←`decidable_product.answer` 或 `manifest`；residual_risks←`threads[].desc`；provenance←`["v1:packed"]`；confidence←`quality.tri_ratio`）；③ 修复后按各层判据统计 gaps；④ `ok = 无 gaps 且无越权`。
- 关键区分：**越权（overreach）是针对原始 packed 的判定，不会被修复掩盖**；**缺口（gaps）与 ok 是修复后判定**。因此 `ok=true` 只说明"修复后四层齐全"，不等于"原始字段齐全"。`repair_packed` 的 `repairs` 列表只记录 citations 与 actions 迁移，**不记录 all 四件套的兜底**——本次新 packed 的 `repairs=[]` 却 `ok=true`，正是这个原因。
- 历史样本切点：Q2 跑于 2026-10-19T10:43:27 启动，取该时刻之前最近 20 份 packed（按 mtime）。历史集固定、不受新 packed 落盘后"挤掉最旧一份"影响；新 packed 单独审计（§2）。
- 契约口径：`contract_report` 内部同样先 `repair_packed` 再逐层 `validate_result`；gate=warn 只报不抛（pilot 配置 `scheduler.v2.contract_gate: warn`）。**契约体检不抓"落盘 1 层错位"**：对旧 10:11 packed 重算契约同样 ok=true（见 §2.3 对照），因为 repair 已先把 actions 搬走。抓落盘错位要靠 `audit.overreach`。
- 「四层实跑」口径：以 packed.`dispatch.ran` 为准（`route`/rounds 是计划，`dispatch.missing` 是实际未执行的层）。

## 2. 新 packed 逐项结果（20261019_110457）

### 2.1 四层职责实测

| 检查项 | 实测 | 判定 |
|---|---|---|
| `views.1._actions` | 无该键（长度 0） | ✅ |
| `views.1.decidable_product.actions` | 无该键；dp 键 = `answer/answered_sub_ids/distance/evidence/not_do`（evidence 2 条） | ✅ |
| `views.all.actions` / `not_do` | 3 / 3（条目含 `_source: schema`，动作四件套齐全） | ✅ |
| **原始** `views.all` decision / residual_risks / provenance / confidence | None / None / None / None（**均缺失**） | ⚠️ 不齐 |
| 根级 `packed.actions` / `packed.not_do`（V1 兼容位） | 3 / 3 | ✅ |
| core_duty 分层 | 0 层 ok（aspects 49/probes 3/suspensions 3）；1 层 ok（subs 6/decidable 1/layer_evidence 2）；both ok（adjudications 3/threads 5）；all ok | ✅ 4/4 |
| audit.overreach / gaps / repairs / ok | [] / [] / [] / true | ✅（无越权，无需修复） |
| v2_shadow.core | ok=true，gaps=[]，overreach=[]；**与重新跑 `audit_packed(packed)` 逐字段相等** | ✅ 一致 |
| v2_shadow.contracts | gate=warn，checked=[0,1,all,both]，violations={}，ok=true | ✅ |
| v2_takeover | applied=true，order 0→1→both→all，rounds {0:3,1:2,both:2,all:1} | ✅ |
| dispatch.ran / missing | 0,1,both,all / []（四层实跑完毕） | ✅ |
| quality / 成本 | 覆盖 100%（3/3）、三态 1/6=0.1667、决策 3 / 不做 3；89 calls / 562,638 tokens（600k 软预算内） | — |
| md 交叉校验 | `**层核心职责**: 通过`、`决策 3 条 / 不做 3 条`、V2 影子起点一致=True | ✅ |

### 2.2 原始字段 vs repair 后（Lead 重点关注）

| all 层四项 | 原始 packed | repair 后 | 来源 |
|---|---|---|---|
| decision | **无** | 有（manifest 前 400 字） | `va["manifest"]`（1806 字） |
| residual_risks | **无** | 有（4 条） | `va["threads"][].desc` |
| provenance | **无** | `["v1:packed"]` | 硬编码兜底 |
| confidence | **无** | 0.1667 | `quality.tri_ratio` |

结论：`audit.ok=true` / `v2_shadow.core.ok=true` / `contracts.ok=true` 三者都是 **repair 后**语义，彼此一致；但**原始 packed 的 all 层四件套并不齐**，且 `repairs=[]` 未留痕。若下游只读裸 packed（不经 repair），会看到 decision/residual 缺失。

### 2.3 新旧对照（同题最近一次旧 packed vs Q2 新 packed）

| 指标 | 旧 20261019_101117 | 新 20261019_110457 |
|---|---|---|
| route / rounds | 0,1,both,all / 0:3,1:2,both:2,all:1 | 相同 |
| dispatch.ran | 0,1,both,all（无 missing） | 相同 |
| `views.1._actions` | 有（5 条） | **无（0）** |
| `views.1.decidable_product.actions` | 有（5 条） | **无** |
| `views.all` 层产物 | 有（76 键，含 manifest/threads，但无 actions/not_do） | 有（77 键，新增 **actions 3 / not_do 3**） |
| all 原生 decision / residual | 无 / 无 | 无 / 无（仍需 repair 兜底） |
| audit.ok / overreach / repairs | false / [1 层越权] / [`1.actions->all:5`] | **true / [] / []** |
| 本审计重算的 contract.ok | true（repair 后；旧跑内当时记的是 raw 违规：1 层无 citations、all actions 空） | true |
| v2_shadow 子块 | 有（at_start/at_end/eml/**contracts**，**无 core**） | 有（含 **core（ok）+ contracts（ok）**） |
| md 输出 | 无「层核心职责」行（跑内契约是 raw 校验且 fail） | `**层核心职责**: 通过` |
| quality | 覆盖 41.3%（5/6），三态 3/6，决策 5 / 不做 3 | 覆盖 100%（3/3），三态 1/6，决策 3 / 不做 3 |
| 成本 | 89 calls / 576,285 tokens | 89 calls / 562,638 tokens（-13,647） |

> 注：旧 10:11 packed 的 `v2_shadow.contracts` 是**未修复的 raw 校验**（当时 bridge/shadow 版本在 10:11 之后才补上 repair-first），violations={1: "1 层 decidable 答案必须带 citations", all: "all 层 actions 不能为空"}；用**当前** bridge 重算同一 packed 则 ok=true。这正好说明"契约先 repair"会放过 1 层错位——判断落盘是否正确只能看 `audit.overreach`。

### 2.4 代码路径核对（"actions 放对层"不是审计时补的）

- `元DGTF-V1.24.0.py:20896-20915`（`_pack_result` · Phase5 职责归位）：从 1 层 `_extract_actions/_extract_not_do` 抽出 `_acts/_nd`，写入 `packed["actions"]`、`packed["not_do"]` 和 `views["all"]["actions"]/["not_do"]`；随后 `views["1"].pop("_actions")`、`views["1"]["decidable_product"].pop("actions")`。
- `元DGTF-V1.24.0.py:21856-21872`：收尾把 `v2_shadow.finish(...)` 写进 packed；`dgtf_v2/shadow.py:155-186` 的 finish 内写 `core = audit_packed(packed)` 与 `contracts = contract_report(packed, gate)`。
- `元DGTF-V1.24.0.py:26033-26039` 的 md 渲染输出「层核心职责」一行（本次 md 实测为"通过"，与 packed core 块一致）。
- 因此即使旧式落盘再出现，`audit_packed` 仍会在**修复前**状态抓到 `1: 出现 action_plan（越权）`——门禁没有被"落盘修复"绕过；本次新 packed 的 `repairs=[]` 也说明它落盘即合规，而不是靠 repair 补救 actions。

## 3. 历史 20 份重跑结果（audits/core_duty_20_latest.json）

### 3.1 汇总

| 指标 | 数值 |
|---|---|
| 样本数 / 时间跨度 | 20 / 2026-10-14T20:14:23 ~ 2026-10-19T10:11:17 |
| audit ok | 2（均为 10-15 的 `route=['0']` 单层跑次；all 层 skipped） |
| 越权文件 | 18（全部为 `1: 出现 action_plan（越权）`） |
| gaps 文件 | 4（`all: 缺 decision` ×4、`all: 缺 residual_risks` ×4） |
| 修复动作 | `1.actions->all` ×18 |
| 分层 ok | 0 层 20/20；1 层 20/20；both 20/20；all 16/20 |
| 原始 `views.1._actions` 非空 | 18/20 |
| 原始 `views.all.actions / not_do / decision / residual_risks` 非空 | 0/20 / 0/20 / 0/20 / 0/20（**20 份全部没有原生 all 四件套**） |
| 有 `v2_shadow` / 有 `v2_shadow.core` | 15/20 / **0/20** |
| 契约体检 ok | 16/20（4 份 FAIL 的 violations 均为 `all 层必须显式写 residual_risks`） |

### 3.2 逐份明细

route = 计划层；dispatch = 实际执行；core_duty = 本次重跑判定；contract = 当前 contract_report(gate=warn)。

| # | 落盘时间 | route | dispatch.ran | views.1._actions | all 层产物 | core_duty.audit | contract |
|---|---|---|---|---|---|---|---|
| 1 | 10-14 20:14 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 2 | 10-15 04:27 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 3 | 10-15 13:35 | 0 | 0 | 0 | 未跑 | ok | ok |
| 4 | 10-15 14:04 | 0,1 | 0,1 | 4 | 未跑 | 越权 | ok |
| 5 | 10-15 15:11 | 0 | 0 | 0 | 未跑 | ok | ok |
| 6 | 10-19 05:06 | 0,1,both,all | 全部 | 6 | 有 | 越权 | ok |
| 7 | 10-19 05:35 | 0,1,both,all | 0,1,both（**缺 all**） | 6 | **空** | 越权 + gaps（缺 decision/residual） | FAIL |
| 8 | 10-19 05:59 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 9 | 10-19 06:25 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 10 | 10-19 06:46 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 11 | 10-19 06:47 | 0,1,both,all | 全部 | 5 | 有 | 越权 | ok |
| 12 | 10-19 07:12 | 0,1,both,all | 0,1,both（**缺 all**） | 4 | **空** | 越权 + gaps（缺 decision/residual） | FAIL |
| 13 | 10-19 07:14 | 0,1,both,all | 0,1,both（**缺 all**） | 4 | **空** | 越权 + gaps（缺 decision/residual） | FAIL |
| 14 | 10-19 07:38 | 0,1,both,all | 全部 | 4 | 有 | 越权 | ok |
| 15 | 10-19 07:42 | 0,1,both,all | 0,1,both（**缺 all**） | 5 | **空** | 越权 + gaps（缺 decision/residual） | FAIL |
| 16 | 10-19 08:08 | 0,1,both,all | 全部 | 5 | 有 | 越权 | ok |
| 17 | 10-19 08:56 | 0,1,both,all | 全部 | 5 | 有 | 越权 | ok |
| 18 | 10-19 08:58 | 0,1,both,all | 全部 | 6 | 有 | 越权 | ok |
| 19 | 10-19 09:46 | 0,1,both,all | 全部 | 3 | 有 | 越权 | ok |
| 20 | 10-19 10:11 | 0,1,both,all | 全部 | 5 | 有 | 越权 | ok |

### 3.3 三条口径澄清（避免误读上面的"ok 2"）

1. **ok=2 不是"四层通过"**：2 份是 10-15 的 `route=['0']` 单层跑次（auto 层裁剪），all 层 `skipped`，所以不判 gap/越权。真正**四层实跑的 17 份全部越权（17/17）**；另 1 份 `route=['0','1']` 的两层跑次也越权。
2. **4 份"all 缺 decision/residual"的直接原因是 all 层没执行**：这 4 份 `dispatch.missing=["all"]`、`views.all={}`（route/rounds 却仍声明 all）。repair 对空 all 层只迁入 actions/not_do，无法从 `manifest/threads` 兜底 decision/residual，所以留 gap——符合"修不了就记 gap、不伪造"。但更底层的事实是：**20 份历史 packed 没有任何一份原生写过 all 的 decision/residual**，只是 16 份能用 manifest/threads 兜底、4 份没有可兜底内容。
3. **`v2_shadow.core` 在历史集里 0 覆盖**：15 份 10-19 跑次有 `v2_shadow`（mode=serial、含旧版 contracts），但均无 `core` 子块——core 是 `dgtf_v2/core_duty.py`（10:31 落盘）接入 `shadow.finish` 后才有的，历史 packed 最晚 10:11。**Q2 新跑是该路径的首次真实覆盖。**

## 4. 历史 vs 新 packed 的差异

- **1 层越权**：历史 18/20（四层实跑 17/17）→ 新 packed `views.1._actions` 无、`dp.actions` 无、`audit.overreach=[]`、`repairs=[]`（落盘即合规）。
- **all 层 actions/not_do**：历史 0/20 有原生 actions → 新 packed 3/3。
- **all 层 decision/residual 原生**：历史 0/20 → 新 packed 仍 0（均依赖 repair 兜底）；**这不是回退，而是历史就存在的口径问题，本次被 Q2 的 ok=true 暴露得更清楚**。
- **v2_shadow.core/contracts**：历史 0/20 有 core、15/20 有旧版 contracts（其中旧跑内 raw 校验曾 fail）→ 新 packed core=ok、contracts=ok（repair-first）。
- **审计结论**：旧 10:11 → `ok=false（1 层越权）`；新 → `ok=true，gaps=[]，overreach=[]`。新代码在**落盘环节**（不是审计环节）把 actions/not_do 归位到 all，审计在 packed 上复核通过；历史 20 份的 1 层错位属旧落盘行为，不能用 audit 修复后判"ok"来掩盖。
- **判定**：**Q2 验证跑在"1 层 actions 归位"这一项上通过**；在"all 原生四件套"这一项上仍未达标（但 audit/contract 口径下可判通过，属语义口径问题，需 Lead 决定是否算 gate 缺口）。

## 5. 未完成项 / 风险 / 建议

**无阻塞项**：Q2 新 packed 在 40 分钟观察窗口内落盘（10:43:27 启动 → 11:04:58 落盘，约 21.5 分钟；89 calls / 562,638 tokens，600k 预算内），审计、契约、历史对照均完成。

需要 Lead 注意的风险：

1. **⚠️ all 层四件套仍非原生（本次唯一实质缺口）**：新 packed `views.all` 的 decision/residual_risks/provenance/confidence 为 None，`audit.ok=true` 依赖 `repair_packed` 从 manifest/threads 兜底，且 `repairs=[]` **不留痕**。建议二选一：① V1 落盘直接写这四个字段（decision 取 all 的结论段、residual 取 threads）；② 让 `repair_packed` 对 all 四件套兜底也记入 `repairs`（如 `all.decision<-manifest`、`all.residual<-threads`、`all.provenance<-default`），并把 audit 输出增加 `repaired=true` 标记，避免 `ok=true` 被误读为"原始齐全"。
2. **契约闸 repair-first 会放过 1 层错位**：旧 10:11 packed 用当前 `contract_report` 重算同样 ok=true（跑内旧版 raw 校验当时是 fail）。要抓落盘错位，门禁必须看 `audit.overreach`（或让 contract 对**修复前**视图也校验一次）。建议把 `core_gate` 的判据定为 `core.overreach 非空 或 core.ok=false`，并考虑把 `contract_gate=raise` 分成"落盘前/修复后"两档。
3. **验证跑与源码写入并发**：`元DGTF-V1.24.0.py` 在 Q2 跑启动（10:43:27）后于 **10:58:38** 被再次写入（当前源码含新增 `[core_gate]` 段，见 21873-21901；`dgtf_config.yaml` 同步 10:58:38）。运行进程在启动时已加载代码，因此 **Q2 packed 反映的是 10:43:27 版本**：证据是 packed **无** top-level `core_ok` 字段、`_ab_core_q2b.log` 无 `core_gate` 告警。也就是说：本次验证覆盖了"Phase5 落盘归位 + v2_shadow.core/contracts"，**未覆盖 10:58 之后新增的 core_gate 段**。若 Lead 要 core_gate 也被 Q2 验证，需要另跑一次（或采用 core-gate 自己的门禁产物佐证）。
4. **单样本限制**：新 packed 仅 1 份（同题、serial、V2 takeover 生效、rounds 0:3/1:2/both:2/all:1）。"新落盘已修复"目前只在这 1 份上被证实；建议再用 2–3 个题型 / 不同并行模式（如 auto/C）回归后再宣告全面通过。
5. **历史统计按 dispatch 分组更准**：20 份里有 2 份单层、1 份两层，四层样本实为 17。后续审计建议直接按 `dispatch.ran` 分组统计，避免"ok=2"被误读。
6. **4 份历史 all missing 的元数据不一致**：route/rounds 声明 all 但 `dispatch.missing=["all"]`；审计建议在输出中带 `dispatch.ran` 证据，避免"没跑"被当成"缺字段"。

## 附录 A · 复现命令与工件

```powershell
# 历史 20 份重跑（cutoff = Q2 跑启动 epoch，本地 2026-10-19T10:43:27 → 1792377807）
python audits/_core_audit.py hist --out audits/core_duty_20_latest.json --n 20 --cutoff 1792377807
# 新 packed 单份审计
python audits/_core_audit.py one --packed "outputs/20261019_110457_AI能否独立完成数字IC设计边界.packed.json" --out audits/core_duty_new_packed.json
# 审计引擎自检（9 项，本次实跑 PASS 9 / FAIL 0）
python dgtf_v2/tests_core.py
```

工件：
- `audits/core_duty_20_latest.json` — 20 份逐份 raw 事实 + audit + contract（本次生成）
- `audits/core_duty_new_packed.json` — 新 packed 的逐项审计（本次生成）
- `audits/_core_audit.py` — 只读审计脚本（读 outputs/ 与 dgtf_v2/，只写指定 --out）
- 注：`audits/core_duty_20.json` 是 10:31 的早期同类产物，本次**另写** `*_latest.json`，未覆盖旧件。

### 附录 B · 证据文件

- `outputs/20261019_110457_AI能否独立完成数字IC设计边界.packed.json`（560,824 B，11:04:58）
- `outputs/20261019_110457_AI能否独立完成数字IC设计边界.md`（126,400 B；含「层核心职责: 通过」「决策 3 条 / 不做 3 条」）
- `_ab_core_q2b.log`（231,085 B，11:04:58；起首含 `元 DGTF v1.24.0` / `V2 接管` / `V2 影子已挂载`，末尾是四层读数总表；**无** `core_gate` 行）
- 只读声明：本次审计未修改 `outputs/`、`dgtf_v2/`、主引擎或配置；仓库根目录 10:58 之后的其余写入来自并发 teammate（`_gate_core_*` 等），与本审计无关。
