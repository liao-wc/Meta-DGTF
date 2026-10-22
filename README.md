# meta-dgtf · 元 DGTF

一个**单文件**的四层螺旋推理引擎：修行 / 研究 / 对撞 / 元，跑出可审计的产物。

- **当前版本**：`元DGTF-V1.30.4.py`（单文件引擎）
- **人用界面**：`dgtf_app/`（app V1.5.19；本地 Web 工作台，见 `dgtf_app/README.md`）
- **版本历史**：`CHANGELOG.md`；app 发布说明见 `docs/releases/`

> 这份 README 只写**能被验证**的事：命令都真跑过，数字都是当前版本的实测值。

## 最新能力（2026-10-22，app V1.5.11）

- **EML + DSH 全流程闭环**：知识刷新 → 引擎跑次 → 消费者/任务 → 自审提案；见 docs/full_loop.md。
- **本地 LLM LoRA fine-tune**：Qwen2.5-0.5B-Instruct 学习“问题 → route/rounds JSON”；留出 route 42.9% / rounds MAE 1.446；见 docs/llm_lora_finetune.md。
- **调度与帕累托**：方案F profile、V2 模板质量-成本前沿、UCB/上下文 UCB、本地调度模型；见 docs/scheduler_model.md。
- **自洽审计**：GET /api/consistency + 审计历史；见 docs/app_engine_mapping.md。
- **针对性真跑**：60 calls / 341K tokens / 758.9s；见 docs/real_run_20261021.md。
- **项目背景内置**：真实任务默认注入元DGTF权威背景，融合本地资料库与 app 本地上传文件；RAG v2 = BGE 语义检索 + BM25 + 引用 + 分层索引 + 追溯；GET /api/project/context 可查看。
- **DSH 会话**：当前/历史、点击续聊、同一会话多轮=一条历史、实时事件、按会话取消；workspace-write 可读写项目，禁止 danger-full-access。
- **知识检索**：Agent 面板“知识检索”与查询框统一走 DSH 知识检索会话，按官方/权威/最新/高置信/高相关筛选后入库；本地资料库导入文件参与 RAG，不训练、不外发。
- **V2 自动选优**：只保留挡位选择；切换挡位自动评估帕累托/最佳模板/UCB 并写最优。
- **三本地底座**：Qwen2.5-0.5B / 1.5B / DeepSeek-R1-Distill-Qwen-1.5B；hybrid = Qwen route + DeepSeek rounds。
- **质量替代分**：/api/quality/<task>，覆盖×回答率×收尾完整度−flags。

---

## 一、它是什么

四层各有一个目标，圈数螺旋推进，三通道并行展开：

| 层 | 目标 | 收敛形态 |
|---|---|---|
| `0` 修行 | 用最少圈数把各层面挖尽 | 趋近无穷收敛（Heaps 饱和） |
| `1` 研究 | 用最少圈数给出确定答案 | 趋近有限收敛 |
| `both` 对撞 | 无穷发散 ∩ 有限确定 ⇒ **融合生成新层面** | 产出率 ×(1−语义停滞罚) |
| `all` 元 | 对前三层产物做记忆结晶 / 决策 / 行动 + **回看全程** | 四件事留痕完整度 |

三通道：`content`（写了什么）/ `context`（凭什么写）/ `self`（自己怎么看这次写）。

### 前沿内核（v1.23.64 进主文件，默认关）

| 编号 | 机制 | 判据（可复跑） | 默认 |
|---|---|---|---|
| F1 | e-process 任意停时检验（Ramdas et al. 2023） | 边跑边看假阳率 0.031 ≤ 0.05；功效中位 37 圈 vs Hoeffding 54 圈 | `stop.anytime_mode=hoeffding`（不变） |
| F2 | 保形预测（Vovk et al. 2005） | 覆盖率 0.940 ≥ 0.9；空校准集保守全弃权 | 仅函数，未接停止 |
| F3 | BOCPD（Adams & MacKay 2007） | 5σ 漂移 0..7 步内检出；平稳序列误报 0 | 仅函数，只读诊断 |
| F4 | Dung 论证 + 负担排序 | 二元环不硬选；真实库注入冲突可检出 | **v1.23.66 起本地开**（`argumentation.enabled=true`；出厂仍 false） |

判据分别在 `_chk_v12364_kernel.py`（24 项）与 `_chk_v12364_dev.py`（33 项），
真实产物实证在 `audits/frontier_v12364.md`。

### 质量 / 成本（v1.23.65 实测帕累托）

| 跑次 | calls | tokens | 覆盖率 | 三态一致 | rubric |
|---|---:|---:|---:|---:|---:|
| 成本膝点 | 59 | 0.37M | 75.0% | 66.7% | 3/3 |
| **质量膝点** | **129** | **1.16M** | **100%** | **60.0%** | **3/3** |
| 成本尾部 | 199 | 2.94M | 83.3% | 50.0% | 3/3 |

配置已朝质量膝点收敛：`spiral.shape_limit=8`（A/B −8.8% tokens）、
`spiral.all_extra_rounds=1`、`api.thinking.effort=low`、
三个实测无收益的思考环节关闭、`decompose_normal` 开启；
新增 `max_tokens=2000000` 软预算，到点层/圈边界优雅停、可续跑。
质量尺子（`bench/bench_score.py`）已同时认 v1.22 单行与 v1.23 缩进两代模板。

### v1.23.66：判据纠偏 + 质量闭环

- **anytime 停止判据修正**：原实现用「多数圈仍在长」当停止条件，会把仍在产出的层提前停掉；
  现在改为「多数圈不再长」才停（生长序列取反），串行 / B 两处同步。
- **JSON 自修复**：json_mode 解析失败时多做一次低温修复（只修格式、不改语义），
  配置 api.json_repair；默认关、本机开。
- **分环节成本 + 质量闭环**：packed/md 新增按 stage 的 calls/tokens/ms、覆盖率（分子/分母）、
  三态、决策动作数、not_do、各层质量线索。
- **池窗口同源**：spiral.shape_limit 现在同时裁 view 与池（默认 0 时仍 8 条）。
- **F4 论证裁决本地开**：只标 defeated/召回排除，不删行。

更细的判据与边界见 v12366_报告.md。

### V2 三平面设计（参考内核，未接管生产）

- 知识面 EML v2：双时态事件溯源 + AGM/TMS + 混合检索 + 只给数值先验。
- 控制面 Scheduler v2：MAPE-K + EVOI + 有限视界 MPC + Pareto + 安全盾。
- 执行面四层契约：0 发散 / 1 收敛 / both 辩证 / all 闭合；越权直接 ContractViolation。
- 参考实现 dgtf_v2/：41 项判据；真实 packed 回放 20 份。
- **V2 已接 Phase 1–4**：影子建议 + 双写 + 契约 warn；takeover 默认 false，开启才接管串行初始排程（层内仍是 V1）。
- **5 对真跑 pilot**：V2 5/5 闭合，calls −24%、tokens −16%，研究覆盖 90% vs 86%，三态 .633 vs .447；推荐 preset：configs/方案G-V2接管.yaml（2M）。
- **2M 追加**：V2 89 calls / 528k 闭合；V1 到 128 calls / 882k 仍卡在 both（手动停止）。
- **Phase 5 完成**：F2/F3/F4/F5 契约层全接、默认开；F3/F4 四层 full-4 通过；F5 只开只读审计，生成机制延期；L0-v2 archive 只读默认恢复。
- **职责修复**：actions/not_do 从 views.1 迁到 all/顶层；1 层不再越权；core_duty 审计 20 份历史 packed（18 份错位、4 份 all 缺项）；新跑 114408 已通过（all 四件套原生、core_ok=true、repairs=[]）。
- **F2 放行并默认开**：四层真跑 5/5（成本 5/5 在 600k）；boundary profile 支持无 actions；三态仅诊断。
- **F3 通过并默认开**：分层 5/5 + 四层 full-4 204700；one_contract.ok=true，flag off 回滚 152307。
- **F4 通过并默认开**：分层 6/6 + 四层 full-4 204724；native=true、completeness=1.0，flag off 回滚 161136。
- **F5 只读审计默认开**：0 层真跑 163612，novelty_measured=true；生成机制仍延期，不接 L0-v2。
- **L0-v2 恢复**：默认 `l0_v2_curate: true` / `l0_v2_mode: archive`（只读档案/novelty，不改生成）；guide/filter 仍实验。tests_l0 16/16。
- **右栏实时日志**：DSH 右栏 Browser 打开 http://127.0.0.1:8770 ；说明见 docs/实时日志右栏.md。
- **三态口径**：tri_ratio 是原始一致率，不是三态质量；quality 增 tri_alpha/tri_reliable/tri_unreliable/tri_distribution，α 是跨视角（非 test-retest），未重测前不放行。
- 详细设计：docs/元DGTF-V2-三平面架构.md。

---

## 二、快速开始

### 依赖

Python 3.11+，第三方只要四个：

```bash
pip install openai pyyaml jieba python-dotenv
```

### 凭据

在仓库根建 `.env`：

```
DGTF_API_KEY=sk-...
DGTF_BASE_URL=https://api.deepseek.com
TAVILY_API_KEY=tvly-...        # 可选：联网检索；不填则联网自动关闭
```

### 跑一次

```bash
python 元DGTF-V1.30.4.py "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住"

# 质量/成本帕累托预设（v1.23.65 基线实测：129 calls / 1.16M → 覆盖 100% / 三态 60%；v1.23.66 预设已同步）
python 元DGTF-V1.30.4.py -c configs/方案F-帕累托最优.yaml "你的问题"
```

常用参数（`--help` 有全量）：

| 参数 | 作用 |
|---|---|
| `--route 0,1,both,all` | 只跑部分层（默认四层） |
| `--rounds 4` | 每层圈数（也可写成 `0:6,both:5`） |
| `--parallel serial\|A..H` | 串行 / 并行档位 |
| `--web auto\|on\|off` | 联网检索 |
| `--config x.yaml` | 换配置 |

产物落在 `outputs/`（md 正文 + json）。**空题会被拒绝**（返回 `refused.reason=empty_question`，且零 LLM 调用）。

---

## 三、怎么验证它（五道门）

改动之后**必须全绿**才算完。每次版本迭代的固定动作见 `CHANGELOG.md` 各版收束摘要。

```bash
# 1) 全套冒烟（266 项）
python smoke_test.py

# 2) 跨档验收（319 项）：审计 + 探针 + 一致性
python _v122_verify.py --src 元DGTF-V1.23.61.py --phase all

# 3) 工程审计（70 项）
python _probe_v1232_audit.py 元DGTF-V1.23.61.py

# 4) 变异体（110 条，每条都必须判红 —— 证明判据有牙）
python _mut_v12332.py --only 1,2,3          # 吃逗号列表 + 1-based，不吃区间
#   大批量建议切片并行（本机实测：6 片并行 ~24 分钟跑完 110 条）

# 5) 应用端自检（371 项，需先起服务，mock 零花费）
CODEBUDDY_SAFE_DELETE_ENABLED=0 python dgtf_app/server.py &
python dgtf_app/selftest.py
```

**当前版本（v1.25.0）的实测基线**：

| 门 | 结果 |
|---|---|
| 冒烟 | **266 ✓ / 0 ✗** |
| 跨档验收 | **PASS 319 / FAIL 0** |
| 工程审计 | **PASS 70 / FAIL 0** |
| 变异体 | **3/3 子集判红**（全套 113 条为上一版基线，本轮未重跑） |
| 应用自检 | **371 ✓ / 0 ✗** |
| 内核判据 | **KERNEL PASS 24 / FAIL 0** |
| 机制判据 | **14 / 14** |
| V2 参考内核 | **41 / 41**（契约 / 双时态 / 调度 / 端到端 / 双写 / 提案） |
| V2 L0-v2 内核 | **16 / 16**（MAP-Elites / novelty / Heaps / Thompson / observe / 真实回放） |
| 四层核心职责 | **9 / 9**（0/1/both/all 职责、actions 归位、证据回退） |
| F2 all ClosurePackage | **9 / 9**（六件套/动作四字段/origin/真实 all_v2） |
| F3 1 层 AnswerSet | **10 / 10**（三态/coverage/citations/无越权） |
| F4 both 论证契约 | **10 / 10**（原生/桥接来源/三件套） |
| F5 0 层审计契约 | **10 / 10**（aspects/probes/novelty 延期） |

> 长跑建议包一层 `_run_gate.py <log> -- <command>`：它落日志、抓退出码，
> 便于事后查（本机 sandbox 的 `>` 重定向不可靠）。

---

## 四、目录里什么是什么

| 路径 | 是什么 | 能不能动 |
|---|---|---|
| `元DGTF-V1.23.*.py` | **主文件各版本**（99 个） | 只增不改；新版复制上一版再改 |
| `smoke_test.py` | 冒烟判据（含 `SRC` 指向当前版） | 每版随之更新 |
| `_mut_v12332.py` | 变异体清单（113 条） | 每版追加 |
| `_v122_verify.py` / `_probe_v1232_audit.py` | 跨档验收 / 工程审计 | 同上 |
| `_run_gate.py` / `_git_save.py` | 门禁包装 / 存档（四项防呆） | 同上 |
| `dgtf_app/` | 本地 Web 工作台（标准库 + 原生前端） | 可改，须跑 selftest |
| `dgtf_v2/` | V2 三平面参考内核（EML / 调度 / 四层契约） | **设计验证器，不接管生产**；不改 V1 引擎 |
| `docs/` | 设计文档与**决策记录** | 只增；`docs/不做什么-v1221.md` 请先读；V2 见 `docs/元DGTF-V2-三平面架构.md` |
| `docs/架构图/` | 整体架构图（PNG / SVG / Mermaid + 读图说明） | 只增；升版后同步重生成 |
| `dgtf_memory/` | EML 记忆库（episodes / playbook / nogoods） | **运行数据，改动前先问** |
| `outputs/` | 产物 | 永不删 |
| `_mk_v1*.py` / `_chk_*.py` / `_bak_*` | 补丁 / 判据 / 备份**脚本**（约 1000 个） | **是证据链，不许删** |
| `_archive/` | 归档备份（git 忽略） | 只增 |

> 根目录脚本很多，这是**刻意的**：每个版本改动都留了可复跑的补丁脚本与判据。
> 想找某个版本改了什么，看 `CHANGELOG.md` 对应段落，或 `git log`。

---

## 五、红线（不可违反）

1. **输入是形状，不是数据** —— 不把题面当语料去"总结"。
2. **悬置不打分** —— 判不出是性质，不是缺陷。
3. **未对齐是合法状态** —— 不许强行对齐成一个答案。
4. **停止与清算分开** —— 停是停（`paused` / 自然停 / 截断），结算是结算（成本、证据）。
5. **失败留痕** —— 失败只加记录，不删行。
6. **入池前挡重复** —— 换学法复述不算新证据。
7. **参数按层可覆盖**。
8. **自省是另一个视角，不可合并**。
9. **EML 只动调度与守卫阈值，不碰答案**。
10. **没有读数就不假装有** —— 缺读数回 `None`，不印 0；空题直接拒跑。

完整决策记录（含"为什么不做"的三件事）见 `docs/不做什么-v1221.md`。

---

## 六、配置

- `dgtf_config.yaml` —— **出厂配置**（只读，201 个叶子键）
- `dgtf_config.user.yaml` —— 用户改动（只存改过的键）
- 加载优先级：`load_config()` 合并两者，`effective_flat()` 给 app 展示用

**本机最优配置已逐项显式写在 `dgtf_config.yaml`（`all_on: false`）**：
`playbook.mode=on` / `stop.anytime_alpha=0.05` / `web_search.enabled=true` /
`external_anchor.as_evidence=gate` / `api.thinking.default=enabled, effort=low` /
`actions.merge_expand=true` / `spiral.shape_limit=8` / `max_tokens=2000000`，
三个实测无收益的思考环节关闭。

`dgtf_config.user.yaml` 已清空（原先把 `default_model` 写成 `777`、并把全部
`thinking.stages` 置 enabled，会覆盖主配置）。应用端 `effective_flat()` 现在等于主配置。
`all_on: true` 仍是一键全开入口（见 `_ALL_ON_ITEMS`），但本机不再依赖它。

---

## 七、跑真跑实验要注意

- **必须显式给 `run_id`**，否则 EML 不学习这一跑（`anon_skipped`）。
- **预算三件套**：`max_calls`（调用次数硬顶）、`max_minutes`（墙钟硬顶）、
  `resume_ckpt`（中断续跑）。三者配合才能"分片跑完、不撞宿主回收窗口"。
- 续跑时快照里的 `llm_calls` 是**按 run_id 累计**的（`window_*` 是本窗口读数）。
- 成本参考（deepseek-flash，非高峰）：四层一趟 ≈ 230 calls / 1.7M tokens / ¥4.3 / 70 分钟。

---

## 八、许可证

内部研究项目，未声明开源许可。
