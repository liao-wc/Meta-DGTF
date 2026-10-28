# 验收语义对齐说明（2026-10-28 · task-3）

> 范围：`fast_gate.py`（动态引擎发现）、`scripts/final_acceptance.py`（三态语义）、
> 新增判据 `scripts/tests_acceptance_semantics.py`、`_probe_v1232_audit.py`（AST 一次解析性能重构）。
> 同时记录 README 第四节 / `docs/项目状态快照_20261027.md` 第 1 节数字与当前代码的口径差异。
> 历史文档按要求**不改**；数字以本文「复跑命令 + 日期 + 结果」为准。

## 0. TL;DR

| 改动 | 旧语义 | 新语义 |
|---|---|---|
| fast_gate 的 compile / audit70 | 钉死 `Meta-DGTF-V2.2.3.py` | 完全委托 App 唯一真相源 `dgtf_app/engine_runner.find_engine()` 动态选版；无候选/静默回落/文件缺失/选版漂移 ⇒ 判红 |
| final_acceptance | 只看 exit code（0=PASS，其它=FAIL） | **PASS / SKIP / FAIL 三态**：没跑显式 SKIP 并打印原因、汇总单列、默认不算失败；`--with-service` 下服务缺失仍 FAIL |
| 服务型步骤「假绿」 | 服务不可达 exit0 + 输出 `SKIP:` ⇒ 被当 PASS | ⇒ SKIP（数据型同理） |
| e2e「假红」 | 服务未起 exit=2 ⇒ 被当 FAIL | 服务型步骤 exit=2 ⇒ SKIP；`--with-service` 时 ⇒ FAIL |
| audit 探针性能 | `body_of()` 每次调用 `ast.parse(全文)`，V2.2.15 实测 **181.1s** | 全文 AST 一次解析 + 一次遍历索引；V2.2.15 实测 **16.5s**（同一台机、同负载） |

## 1. 背景：两个真实缺陷 + 一个口径漂移

### 1.1 fast_gate 钉死 V2.2.3（门跟不上生产引擎）

旧版 `fast_gate.py` 的 compile / audit70 两项是常量命令：

```python
("compile", [... py_compile.compile('dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py' ...) ...]),
("audit70", [... "_probe_v1232_audit.py", "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py"]),
```

而 App 的 `engine_runner.find_engine()` 会自动取**最高版本**。生产引擎从 V2.2.4 起一路升级到
V2.2.15，快速门禁却仍在检查 V2.2.3 —— 「12/12 全绿」实际是**旧引擎在绿灯**。
动态化后第一次真检查 V2.2.14，audit70 立刻报出 4 项真实回归（C3/C4/H1 + K4 的 8 处未声明
thinking stage）；V2.2.15 修完 K4 后为 3 项（C3/C4/H1，属发版动作）。**这就是动态发现的直接价值。**

### 1.2 「没跑」被误判成「判红 / 假绿」

- **假红**：`e2e_app_local.py` 在 8772/8773 未起时打印「⚠ 不是判红，是没跑」并 `sys.exit(2)`；
  旧 final_acceptance 只看 `returncode != 0` ⇒ FAIL。
- **假绿**：`test_judge_fastfail.py` / `test_generate_batch.py` / `test_graph_decode.py` 在服务不可达时
  `return 0` 且打印 `SKIP: 服务不可达`；旧版只看 `returncode == 0` ⇒ PASS（把「没跑」算成通过）。
- **反例（不能一刀切）**：`scripts/run_v2_tests.py` 的 exit 2 是「未发现测试 / 用法错误」——是真错误，
  **不是**没跑。因此「exit2 ⇒ SKIP」只能对**声明为服务型**的步骤生效（见 §3）。

### 1.3 口径漂移（git 事实，只读审计）

`git log -- scripts/final_acceptance.py` 显示 STEPS 数量演化：

| 提交 | 日期 | STEPS | 说明 |
|---|---|---|---|
| e4eddd8 | 2026-10-26 | 8 | Round 73 首版 |
| 0cb0090 | 2026-10-27 | 14 | 验收 15 项（含 local_service） |
| d01a795 | 2026-10-27 | **17** | +graph_decode；**README/快照的 18/18（有服务）/17/17（无服务）= 本提交**（17+local_service=18） |
| 855f588 | 2026-10-28 | **21** | +openai_shim / mem_reclaim / max_new_cap / e2e_app_local（**文档未同步**） |
| 本次（task-3） | 2026-10-28 | **22** | +graph_sampling（V2.2.15 发布新增，Lead 提供）；`--with-service` 时 23 |

⇒ README 第四节 / 快照 §1 的「18/18 / 17/17」并非现在的代码事实：10-28 的 855f588 新增 4 步后
文档没跟上；本次又新增 1 步。**旧数字不删（历史文档按要求保留），此处给出对齐关系。**

## 2. fast_gate：与 App 同源的动态选版

### 2.1 契约（唯一真相源 = `engine_runner.find_engine()`）

Lead 明确要求「能 import 就直接 import，不要复制正则；复制必漂移」。实现**不复制**任何 glob /
版本正则 / 排序 / `DGTF_APP_ENGINE` 覆盖逻辑，而是直接调用 App 的函数对象：

| 项 | 行为 |
|---|---|
| 选版入口 | `fast_gate._app_find_engine_fn()` 返回 `dgtf_app.engine_runner.find_engine` 本身；测试做**函数对象同一性 + 注入委托判据**（把 App.find_engine 换成桩，fast_gate 必须跟着桩走） |
| glob / 版本排序 / 旧文件名 / env 覆盖 | **全部由 App 实现**，fast_gate 不复制 |
| 无候选 | App 会静默回落到硬编码旧版；fast_gate 用「空 PROJECT_ROOT 反推兜底路径形态」识别该回落并**判红**（不复制版本号常量） |
| 选中的文件必须存在 | 不存在 ⇒ 判红 |
| 对齐判据 | ① 选版入口就是 App 的 find_engine（函数对象同一性，防复制实现）；② 本脚本最终检查的文件 == App 现在选中的文件（防漂移） |
| 可审计 | 首行打印 `ENGINE <路径> (V<版本>, source=glob|env)`；`--print-engine` 供脚本/CI 消费 |

实现位置：`fast_gate.py` `_app_module` :45 / `_app_find_engine_fn` :58 / `app_find_engine` :63 /
`_fallback_rel` :68 / `resolve_engine` :91 / `discover_engine` :124 / `engine_version_str` :130 /
`check_engine_alignment` :139 / `build_checks` :194 / `main` :236。

### 2.2 检查清单：15 项

动态引擎相关 4 项：`engine_discovery`（解析 + 无候选/回落/存在性）、`engine_alignment`（同一性 + 同一文件）、
`compile`（py_compile 当前引擎）、`audit70`（_probe 审计当前引擎）；
既有 10 项模块/代理判据不变；新增 `acceptance_semantics`（本文件判据自身进快速门禁）。
原 12 项中的 compile/audit70 由「钉死」改为「动态绑定」，另加 3 项 ⇒ 15。

### 2.3 有牙判据（`scripts/tests_acceptance_semantics.py` A/B 组）

- A1 临时项目树 V2.2.9 / V2.2.10 ⇒ 选 V2.2.10（数值序，非字典序；走 App 真实逻辑）；
- A2 造 V9.9.9 ⇒ 选中它；A3 删空候选 ⇒ 判红（识别 App 回落）；
- A4 旧文件名 `元DGTF-V8.0.0.py` 参与比较；A5 compile/audit 命令必须指向解析到的引擎，无候选占位命令判红；
- A6 alignment 在真实仓库为真；A7 ★ **函数对象注入**：App.find_engine 换桩 ⇒ fast_gate 跟随（复制实现即红）；
- A8 `DGTF_APP_ENGINE` 覆盖与 App 同源；
- 变异体：M1 接受静默回落 ⇒ 被 A3 抓；M2 复制选版逻辑 ⇒ 被 A7 抓；M3 对齐漂移放行 ⇒ 被 A6 抓；M4 exit=2 当 PASS ⇒ 被 C3 抓。

### 2.4 当前实测（2026-10-28，V2.2.15 已含 release 文档）

```text
$ python fast_gate.py
ENGINE ...\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.15.py  (V2.2.15, source=glob)
PASS engine_discovery / engine_alignment / compile / audit70 / (既有 10 项) / acceptance_semantics
FAST GATE PASS 15 / FAIL 0          （本机负载下 elapsed≈21.8s；audit70 单独≈16–20s）
```

对照（动态绑定是否正确跟随旧版）：把 `DGTF_APP_ENGINE` 指向 V2.2.3 时，compile/audit70 检查的
就是 V2.2.3（同一判据输出随引擎变化 ⇒ 不再是「旧引擎在绿灯」）。

## 3. final_acceptance：PASS / SKIP / FAIL 三态

### 3.1 三态定义

| 状态 | 含义 | 计入 |
|---|---|---|
| PASS | exit 0，且（服务型/数据型步骤）没有「SKIP」标记 | 通过 |
| SKIP | **没跑**：服务未起 exit=2 / 输出 `SKIP:` 行 / `--skip-service` 显式跳过 | 单列，默认不算失败、不冒充绿 |
| FAIL | 跑了判红；或没跑但当前模式要求必须跑（`--with-service` 的服务型步骤） | 失败 |

### 3.2 步骤策略（`STEPS` :52，共 22 步；`--with-service` 追加 1 = 23）

- `strict`：只认 exit 0 = PASS（默认；不吞任何「没跑」）；
- `service`（4 步：judge_fastfail / generate_batch / graph_decode / e2e_app_local）：
  exit 0 + 输出 `SKIP:` ⇒ SKIP；exit=2 ⇒ SKIP；`--with-service` 时 SKIP 升级为 **FAIL**（服务缺失必须判红）；
- `data`（1 步：fx_anchor_replay）：历史 packs 缺失时脚本自己输出 `SKIP:` ⇒ SKIP（与模式无关）；
- 其余 17 步 strict（含新增 graph_sampling：零 GPU/零 HTTP，25 项自检）。
- 反例锁死：strict 步骤 exit 2 仍是 FAIL（run_v2_tests 的 exit2 = 未发现测试/用法错误，不是没跑）。

分类器是纯函数 `classify_step` :125；`--with-service` 升级逻辑 `apply_service_requirement` :142；
执行器 `run_step` :157；入口 `main` :185。`--list-steps` 可打印全清单与策略（审计用）。

### 3.3 模式开关与退出码

- `--with-service`：纳入 local_service 检查；服务型 SKIP ⇒ FAIL（服务缺失仍算 FAIL）。
- `--skip-service`（与 --with-service 互斥）：**显式**跳过服务型步骤、记 SKIP「未执行」——用于
  GPU/服务被其他任务独占时防误跑（本仓库 GPU 窗口归 Lead）。不执行 ≠ 通过。
- `--require-all`：SKIP 也按失败处理（CI/有服务环境严格模式）。
- 退出码：0 = 没有 FAIL（默认 SKIP 不算失败）；1 = 有 FAIL，或 `--require-all` 下有 SKIP。
- 汇总格式：`FINAL ACCEPTANCE: PASS a / SKIP b / FAIL c (n steps)` + `SKIPPED（没跑，默认不算失败）` 明细。

### 3.4 当前实测（`--skip-service`，2026-10-28）

```text
$ python scripts/final_acceptance.py --skip-service
PASS  fast_gate 21.1s      PASS  v2_tests 191.4s    PASS replay_guard 3.5s
PASS  process_gate_guard 2.2s   PASS app_plan_matrix 0.6s   PASS app_dual_judge_guard 0.6s
PASS  compare_eval_selftest 0.6s  PASS train_guard 31.6s    PASS app_cache_bypass 0.3s
SKIP  judge_fastfail      --skip-service 显式跳过（未执行）
SKIP  generate_batch      --skip-service 显式跳过（未执行）
SKIP  graph_decode        --skip-service 显式跳过（未执行）
PASS  probe_cover_wide 4.5s   PASS ab_repeat_guard 0.1s   PASS outputs_consistency 2.3s
PASS  fx_anchor_replay 0.2s   PASS scenario_matrix_guard 0.2s   PASS openai_shim 1.6s
PASS  graph_sampling 0.3s     PASS mem_reclaim 14.5s      PASS max_new_cap 1.5s
SKIP  e2e_app_local       --skip-service 显式跳过（未执行）

FINAL ACCEPTANCE: PASS 18 / SKIP 4 / FAIL 0  (22 steps)
SKIPPED（没跑，默认不算失败；原因见下）:
  - judge_fastfail / generate_batch / graph_decode / e2e_app_local：--skip-service 显式跳过（未执行）
ALL GUARDS PASS（含 4 个 SKIP 单列；--require-all 可把 SKIP 当失败）
```

- 总墙钟 ≈ **4.6 分钟**（< 5 分钟目标）；`v2_tests` = **66 文件全 PASS（191.4s）**；新增 `graph_sampling` 步 PASS。
- 4 个 SKIP 全部出现在**服务型步骤**且**原因显式**：没跑 ≠ PASS（旧版里 judge_fastfail/generate_batch/graph_decode
  会 exit 0 被当 PASS；e2e 会 exit 2 被当 FAIL —— 两种误判都已消除）。

说明：本环境 8772/8773 在线且归 Lead 独占（GPU 窗口），因此用 `--skip-service` 复现「服务步骤没跑」口径：
服务型步骤**显式 SKIP + 原因**、不算 PASS。真实「服务未起 ⇒ e2e exit=2 ⇒ SKIP」路径由
`tests_acceptance_semantics.py` 的构造性子进程（真实 exit 0/1/2）与 `--with-service` 分支判据证明；
真跑（含 e2e）由 Lead 在 GPU 窗口用 `--with-service` 执行（本任务不跑 GPU/e2e）。

## 4. 口径对齐表（历史文档 vs 当前代码事实）

| 出处 | 历史数字 | 当前代码事实（2026-10-28 复跑） | 差异原因 / 建议写法 |
|---|---|---|---|
| README §四 fast_gate | PASS 12 / FAIL 0 | **15 项；15/15 PASS** | compile/audit70 改为动态绑定 + 新增 engine_discovery/engine_alignment/acceptance_semantics；写「15/15 + 引擎版本」 |
| README §四 一键验收 | 18/18 PASS（无服务 17/17） | **22 步（--with-service 23）**；三元组见 §3.4 | 数字停在 d01a795（17+1）；855f588 新增 4 步、本次 +graph_sampling；旧二元组表达不了 SKIP |
| 快照 §1 一键验收 | 18/18 / 17/17 | 同上 | 同上（快照日期 10-27） |
| 快照 §1 V2 全量 | 54/54 文件 · 855 checks | 本次 acceptance 串跑：`v2_tests` **66 文件全 PASS（191.4s）**（checks 数见 run_v2_tests 当次输出） | 测试文件数随版本增长；README §四的 51/51(806) 是更早口径 |
| README 顶部生产引擎 | V2.2.4 | 仓库工作区已到 **V2.2.15** | 版本迭代规则 §6 的文档同步滞后，属发版动作（Lead 域） |

**口径原则**：门禁/验收数字必须写「命令 + 日期 + PASS/SKIP/FAIL 三元组（或文件数/checks）」；
单一「x/x PASS」在存在 SKIP 的验收里已不足以表达真实状态。

## 5. audit 探针性能重构（`_probe_v1232_audit.py`，同期交付）

**根因（实测热点，cProfile）**：
1. `body_of()` 每次调用都 `ast.parse(全文)`（V2.2.15 33.2k 行）；
2. 死类判据对**每个类**都 `ast.walk(全文)` 数裸名引用（≈22 类 × 全文 AST，`_code_refs` 累计 36.8s）；
3. `J2`（配置键可达性）对**每个配置键**都扫一遍 33k 行（O(键数×行数)）；
4. K/E1 各再 `ast.walk(全文)` 一遍；变异体自检还重解析变异后的全文两次。

**改法**：`_AST = ast.parse(txt)` 全文**只解析一次**（`_parse_cached` 对目标文本返回它）；
一次遍历 `_index_ast(_AST)` 建好函数/类/裸名计数/stage/thinking 接线/_web_search 调用索引，后续判据全部查表；
J2 改为一次扫描取「DEFAULT_CONFIG 块之外的引号字面量集合」；变异体自检里 A3 用已算好的
`_DEAD_FOUND` + 注入登记表复算、I3 用最小合成片段打 `_round_args`，不再重解析 1.6MB 全文。

**逐条一致（重构不改判定）**：用同一 `__file__`（仓库根，保证 H1/C2/C3/C4 等 HERE 相对判据一致）
在**同一时间窗口**分别跑「HEAD 旧探针」与「新探针」，逐条比对 `✓/✗` 明细：

用同一 `__file__`（仓库根，保证 C2/C3/C4/H1/F4 等 HERE 相对判据一致）、同一时间窗口成对执行
「HEAD 旧探针」与「新探针」：

```text
V2.2.15：before=72 条明细 / after=72 条明细 → Compare-Object：DETAIL IDENTICAL（逐条一致）
         before AUDIT PASS 71 / FAIL 0  →  after AUDIT PASS 71 / FAIL 0
V2.2.3 ：before=72 条明细 / after=72 条明细 → Compare-Object：DETAIL IDENTICAL（逐条一致）
         before AUDIT PASS 70 / FAIL 1  →  after AUDIT PASS 70 / FAIL 1
         （唯一 FAIL = C3：根 dgtf_config.yaml 头已随发版写 V2.2.15 ≠ 引擎 2.2.3，属发版态）
```

结论：性能重构**不改变任何一条 PASS/FAIL 判定**（72 条明细逐条一致，两侧 rc 也一致）。

**性能（同一台机、同一负载窗口，成对测量）**：

| 引擎 | 改前（HEAD 旧探针） | 改后（一次解析 + 一次遍历索引） | 加速 |
|---|---|---|---|
| V2.2.15（33.2k 行） | **77.00s** | **18.77s** | **4.1x** |
| V2.2.3 （32.9k 行） | 72.86s | 18.51s | 3.9x |

上表为同机同负载窗口的**成对测量**（并行还有验收串跑任务，属偏保守读数）。Lead 在另一负载窗口实测
V2.2.15：**181.1s → 16.5s ≈ 9x**，同口径结论一致（目标 < 20s 达成）。
热点（cProfile，改前）：`_code_refs` 22 类 × 全文 AST ≈36.8s、全文 AST 重复解析、J2 键×行扫描、变异体重解析；改后均消除。

**有牙判据**（`tests_acceptance_semantics.py` E 组）：
- E1 源码级：`ast.parse(txt)` 全文仅 1 次、`body_of` 查表不再解析、`_parse_cached` 只对目标文本复用；
- E2 ★ 行为级：monkeypatch `ast.parse` 计数 + 守卫（第 2 次全文解析即判红），跑**真实审计主流程**
  （当前生产引擎）断言 target 全文解析次数 == 1；
- E3 ★ 变异体：把 `body_of` 改回逐次解析 ⇒ 守卫必须命中（E2 有牙）。

## 6. 判据与复跑

```powershell
cd "D:\Meta-DGTF-道生三阶模型"
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"

python scripts/tests_acceptance_semantics.py    # 45 checks：A 同源选版 / B 变异体 / C 三态 / D 端到端 / E 探针性能
python fast_gate.py                             # 15 项快速门禁（含 acceptance_semantics 自身）
python scripts/final_acceptance.py --skip-service   # 三态验收（服务步骤显式 SKIP）
python scripts/final_acceptance.py --with-service   # 有服务环境（Lead 的 GPU 窗口执行）
python scripts/final_acceptance.py --list-steps     # 只看步骤清单与策略
```

## 7. 未测出 / 剩余风险（如实）

- **未实测**：本环境 8772/8773 在线且归 Lead 独占，普通无服务口径的 plain `final_acceptance.py`
  （会真跑 e2e/GPU 推理）未执行；替代证据 = `--skip-service` 实测（§3.4）+ 构造 exit0/1/2 子进程判据（C11–C13/T1/T5）。
- **未实测**：`--with-service` 端到端（e2e 真跑）由 Lead 在 GPU 窗口执行；本任务不跑 GPU/e2e。
- audit70 对 **V2.2.3** 的 C3（配置头版本）会红：根 `dgtf_config.yaml` 头已随发版写成 V2.2.15，
  这是发版态而非回归 —— 动态门禁检查的是**当前生产引擎**，不再要求旧版全绿。
- 同版本双文件（tie-break）未构造：当前引擎目录无同版本重复文件；若出现，由 `engine_alignment`
  判红兜底，而不是静默选错。
- `fast_gate` 仍是「并行 15 项」的快速反馈门，不替代 `final_acceptance` / App selftest / 真跑。
