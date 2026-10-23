# v1.22 阶段 6 报告 · 双实现收口（6B）

## 一、目标

| 编号 | 目标 | 量化验收 | 结果 |
|---|---|---|---|
| G6.1 | 行为对照 | before/after 快照 | ✅ |
| G6.2 | `auto_plan` 收口 | 薄壳 + 行为逐字相同 | ✅ |
| G6.3 | `_rephrase_streak` 收口 | 唯一实现（定义数 = 1） | ✅ |
| G6.4 | 产物文本一致 | 逐字（排时间戳） | ⏳ 见第八节 |
| G6.5 | 审计文档更新 | `resolved` 段有 | ✅ |
| G6.6 | AST | 逐节点差异有解释 | ✅ 27 项全解释 |

## 二、改前基线（探针 before）

`python _probe_v122_phase6.py baseline --out _v122_phase6_baseline_before.json`

探针**打桩**：把模块级 `LLM` 换成按 `stage` 返回固定 JSON 的桩
（`plan_orientation` / `plan_resources` / `auto_plan` 三个 stage 各一份固定
返回值）。不打桩的话每次调用都是新抽样，对照毫无意义。

改前实测（`_v122_phase6_baseline_before.json`）：

```
A_method_auto_plan          : {mode: serial, rounds: {0:4,1:4,both:4,all:5}, confidence: 0.8}
A_stages                    : ["auto_plan"]                       ← 1 次调用
B_module_auto_plan          : {route:[0,1], mode: serial, rounds:{0:4,1:4}, max_calls: 96, ...}
B_stages                    : ["plan_orientation","plan_resources"] ← 2 次调用
C_module_auto_plan_with_llm : TypeError: auto_plan() got an unexpected keyword argument 'llm'
D_rephrase_streak           : {impl: "inline(两处各一份)", values: [2,3,0,0]}
```

★ 注意 `A` 的 rounds 是 `{0:4,1:4,both:4,all:5}` —— 桩给的是 3，出来是 4/5，
说明**归一化规则**（逐层钳位 + 中位数补漏）确实在跑。这一格正是收口时
最容易改坏的地方，所以它是行为对照的主判据。

## 三、改了什么（逐条 + 落点）

| # | 改动 | 落点 |
|---|---|---|
| 1 | `_auto_plan` 的方法体（141 行）**原样搬入**模块级 `auto_plan` 的单调用分支并**内联** | 主文件 `auto_plan` 函数体内 |
| 2 | `MetaDGTF._auto_plan` 退薄壳：`return auto_plan(question, self.config, llm=self.llm)` | 主文件 13731 行附近（8 行） |
| 3 | 模块级 `auto_plan` 加 `llm` 形参 + 单调用分支 | 主文件 18644 行附近 |
| 4 | 新增 `_compute_rephrase_streak(view, state)` 唯一实现 | 主文件 `_anchor_enters_citation` 之前 |
| 5 | 串行 `_run_layer` 调用点改调它 | 主文件 14479 行附近 |
| 6 | 并行 `_b_check_stop` 调用点改调它 | 主文件 15967 行附近 |

### 为什么是「单调用那一支」当唯一实现

任务书给的壳是 `return auto_plan(question, self.config, llm=self.llm)`。
而模块级 `auto_plan` 原本是**两次调用**（`plan_orientation` +
`plan_resources`）。如果让方法去调那个两次调用版，成本与结果都会变 ——
可阶段 6 的验收恰恰要求 before/after **逐字一致**。

所以收口的口径是：**同一函数、两条入参路径**。
- 给 `llm` → 走单调用路径（原 `_auto_plan` 的正文，`run()` 用的就是它）；
- 不给 `llm` → 保留 v1.21.62 的两次调用路径（对外 API 兼容）。

### 为什么内联而不是新开一个 `_auto_plan_once`

第一版做成了「搬到模块级新函数 `_auto_plan_once`」，函数节点 +2。任务书
Step 7.4 的判据是「函数节点数**不增加**」。内联掉搬运那股之后，阶段 6 的
净增只剩任务书**点名要求新增**的 `_compute_rephrase_streak`（+1），
节点差异因此可以逐条解释干净（见第六节）。

### 搬运方式

不手抄。补丁脚本用 **AST 行号**定位 `_auto_plan` 的方法体，原样取出、
去 4 格缩进、`self.config → config` / `self.llm → llm`，再写进模块级函数。
其余一字未动。搬运脚本另外校验：方法体里**除了 config 与 llm 没有别的
`self.` 依赖** —— 有的话搬运会静默丢掉状态。

## 四、改后对照（探针 after）

```
A_method_auto_plan          : {mode: serial, rounds: {0:4,1:4,both:4,all:5}, confidence: 0.8}  ← 与改前逐字相同
A_stages                    : ["auto_plan"]
B_module_auto_plan          : {与改前逐字相同}
B_stages                    : ["plan_orientation","plan_resources"]
C_module_auto_plan_with_llm : {mode: serial, rounds: {0:4,1:4,both:4,all:5}}  ← 新增入口，与 A 逐字相同
D_rephrase_streak           : {impl: "module-level _compute_rephrase_streak", values: [2,3,0,0]}
```

逐字段核对（程序判定，非目测）：

```
A(method) == C(module+llm) ? True
A before == after ?          True
B before == after ?          True
D.values before == after ?   True
行为字段 before/after 全等 ? True
```

`diff -u` 的全部差异只有两处，且都是**应该变的**：

1. `C_module_auto_plan_with_llm`：改前是 `TypeError`（这个入口不存在），
   改后返回 `{mode, rounds}` —— 新增能力。
2. `D_rephrase_streak.impl`：标签从 `inline(两处各一份)` 变成
   `module-level _compute_rephrase_streak` —— 实现方式的标签。

**`D.values` 不变**（`[2,3,0,0]`）是关键：收口改的是「怎么写」，
而四个边界输入的**结果**逐字相同（含 `None` state 与 `None` 属性两个边界）。

## 五、冒烟结果

```
python smoke_test.py
✓ 158 / ✗ 0 / EXIT=0
```

- `check_v122_phase6`（新）：薄壳行数 ≤ 12、AST 里
  `_compute_rephrase_streak` 定义数 = 1、审计文档 `resolved` 段在、
  AST 登记表两向对账、产物对照。
- **旧判据回归 1 处，如实记**：`check_v71_auto_plan_agreement`（v1.21.71 F8）
  报「`_auto_plan` 的 docstring 没标注与模块级 `auto_plan` 的关系」。
  这不是代码错 —— 收口后方法只剩 8 行壳，我把新 docstring 写成了
  「唯一实现搬到模块级」，漏了它要求的 `plan_resources` 字样。
  **修法是把关系写全**（壳 → 单调用路径 = 原正文；不给 llm = 
  `plan_orientation` + `plan_resources`），不是把判据改宽。改后该判据绿。
  ★ 这条判据恰好证明了它的价值：它拦的是「两份实现的漂移没人标注」，
  收口之后**更该留** —— 读者得一眼看出「这里只是壳，实现在哪」。

## 六、AST 等价证据（逐节点差异 + 解释）

本版**不可能** AST 等价（六个阶段各自新增函数）。走任务书的第二条路：
**逐节点差异有解释**。

- 符号级：基线 **290** 个（函数 + 类名）→ 本版 **317** 个；
- 新增 **27** 项，**全部**逐条挂了「属于哪个阶段 + 为什么必须有」，
  落在 `_v122_ast_registry.json`；
- 消失 **0** 项（红线：不许删机制）；
- 判定**两向对账**：新增未登记 → 红；登记了却不存在 → 红。
  实测 `新增 27 / 未登记 0 / 过期登记 0 / 符号消失 0`。

阶段 6 自身的净增只有 1 项：

| 新增 | 阶段 | 为什么必须有 |
|---|---|---|
| `_compute_rephrase_streak` | 6 | 任务书 Step 6.3 点名要求的唯一实现（原为两处各一份的行数） |

“搬运”那股没有留下新符号 —— 因为它**内联**进了 `auto_plan`。

### 函数体骤减（须解释）

`function_shrunk()` 报 **2 项**，两条都是**设计**，不是丢内容：

| 函数 | 行数 | 解释 |
|---|---|---|
| `render_landing` | 259 → 8 | 阶段 3 分流壳：正文整体改名 `_render_landing_boundary`（一行没删），壳里只有 3 行判断 |
| `_auto_plan` | 142 → 8 | 阶段 6 收口：正文内联进模块级 `auto_plan`（AST 搬运，非手抄） |

两条都满足「内容还在别处、且能被指到」：前者在
`_render_landing_boundary`，后者在 `auto_plan` 的 `if llm is not None:`
分支里。

## 七、验收判据核对

```
── 阶段 6 ──
  ✅ [6.2] _auto_plan 薄壳（行数 8）
  ✅ [6.3] AST 里 _compute_rephrase_streak 定义 1 处（期望 1）；字面串出现 1 次
  ✅ [6.5] 审计文档 resolved 段存在
  ✅ [6.6] AST 登记对账：新增 27 / 未登记 0 / 过期登记 0 / 符号消失 0
  ✅ [6.4] 产物对照 before=True after=True（排时间戳后逐字一致=True）
```

全局：

```
✅ [G.del] 纯删除行 0（≤0）；改写行 183（如实报，不计删）
✅ [G.mech] 机制未被移除（符号消失 0 项）
ℹ️  函数体骤减 2 项：render_landing 259 → 8；_auto_plan 142 → 8（已在第六节解释）
```

## 八、G6.4 产物逐字一致

按任务书 Step 6.4 跑两份：

```bash
python 元DGTF-V1.22.0-rc1.py "老城区暴雨内涝频发…" \
  --route 0,1 --rounds "0:3,1:3" --parallel serial --quiet --profile balanced
python 元DGTF-V1.22.0.py     "老城区暴雨内涝频发…" （同上参数）
grep -v "^\*\*时间\*\*" before > _b.md ; 同样处理 after ; diff -q _b.md _a.md
```

**口径说明（重要）**：`元DGTF-V1.22.0.py` 与 rc1 的差异**只有 3 个块**
（标题行、`__version__`、changelog 六段），已由 `_mk_v122_final.py` 断言。
所以这一步能证明的是**「定稿没有顺手改行为」**，不能替代阶段 6 的
收口等价性 —— 后者由第四节那套打桩对照负责（那才是收口前后的对照）。

## 九、遗留与下一版

- `auto_plan` 的**归一化规则**仍是两份（模式白名单 + 逐层钳位 + 中位数
  补漏 + 低置信退 serial）。本版收口的是「同一个函数」，不是「同一份规则」。
  合并要贯通 `plan_resources` 的签名，列入
  `docs/机制审计-v122.md` 的 `pending_fix` #1。
- `_compute_rephrase_streak` 已唯一，但两处调用点传的 `state` 形状不同
  （串行传 `{"meta_idle_streak": meta_idle_streak}`、并行传整个 state）。
  这是**调用点差异**不是实现差异；若下一版把串行的 `meta_idle_streak`
  也放进 state，签名可以再收窄一次。
