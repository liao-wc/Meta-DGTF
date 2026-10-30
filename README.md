# Meta-DGTF-道生三阶模型

一个**单文件四层螺旋推理引擎** + **V2 三平面核心** + **本地 Web 工作台**：
修行 / 研究 / 对撞 / 元，跑出可审计、可回放、可融合的产物。

- **当前版本**：V2.2.79（证据答案语言匹配） / App 2.0.83（本地链路全生命周期守护 + health 读数 + 本地档预设；道生专属模式 + 三体动态计划 + 预算守卫）
- **生产引擎**：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.56.py
- **V2 核心**：dgtf_engine/dgtf_v2/
- **人用界面**：dgtf_app/（App 2.0.83，本地链路两段守护 + 道生专属模式 + DSH 本对话实时镜像 + 会话列表实时打开 + 健康读数缓存）
- **本地链路**：dgtf_local_llm/（8772 推理服务，fp32 底座 + CUDA graph 采样/复用）+ scripts/local_model/openai_shim.py（8773 OpenAI 适配层）
- **融合实现**：单引擎内联（Meta-DGTF-V2.2.79.py）；V2.1 外部模块仅作回滚参考
- **历史清单**：dgtf_engine/dgtf_v2/history_manifest.json
- **版本规范**：dgtf_engine/dgtf_v2/NAMING.md
- **历史归档**：元DGTF-V1历史归档-20261023.zip（V1.0 → V1.30.4）

> 这份 README 只写能被验证的事；详细来源、能力、版本演化见 docs/history/。
> **2026-10-30 收束同步（V2.2.79 / App 2.0.83）**
> 
> 一页看全「能力 ↔ 证据 ↔ 已知限制」：[docs/能力与证据矩阵_20261030.md](docs/能力与证据矩阵_20261030.md)。：V2 **71/71（1208 checks，SKIP 0）**；fast_gate **19/19**（动态选最高版引擎；含发布流程门自检；audit70 71/0）；
> App selftest **459/0**（自动门）；一键验收 **PASS 30 / SKIP 0 / FAIL 0**；发布流程门 **PASS（N/A 项带原因）**；动态配置/优先成本 **132/132**、更优/route 安全门 **30/30**、全链路真跑 **25/25**、道生统一模式 **27/27**、自动模式真跑 **12/12**；服务适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1。
| **四层目标探针**（route 0/1/0,1,both/0,1,all） | **84 / 84 PASS**（V2.2.79 复跑：4 case 共 260 calls，墙钟 662.0s）；层0 未达成（excavate=1.0，单次方差）/ 层1 未测出 / both 判据样本不足 / all 未达成（0.75） |
| **四层读数方差（刷新）** | 46 次历史复跑：case0 均值 **0.36**（0–1）/ both **0.021**（0–0.37）/ all **0.582**（0.5–0.75，从未到 1.0）| docs/probe_variance_20261030.json |
> 四层目标逐层结论（V2.2.49 复跑）：层0 达成（excavate=0，读数在 0/0.25/0.5/1 间波动的单次方差已多轮记录）/ 层1 未测出（settlement.total=0）/ both 受阻（读数通道全通）/ all 未达成（0.5）。
> 完整现状见 `docs/项目状态快照_20261030.md`。

## 一、它是什么

Meta-DGTF-道生三阶模型源于用户与 DGTF 的长对话（分享 ID: 44iynplni6iqr4am3f），
从 V1.0 的单文件四层螺旋引擎演化而来。

四层各有一个目标，圈数螺旋推进，三通道并行展开：

| 层 | 目标 | 收敛形态 |
|---|---|---|
| 0 修行 | 用最少圈数把各层面挖尽 | 趋近无穷收敛（Heaps 饱和） |
| 1 研究 | 用最少圈数给出确定答案 | 趋近有限收敛 |
| both 对撞 | 无穷发散 ∩ 有限确定 ⇒ 融合生成新层面 | 产出率 ×(1−语义停滞罚) |
| all 元 | 对前三层产物做记忆结晶 / 决策 / 行动 + 回看全程 | 四件事留痕完整度 |

三通道：content（写了什么）/ context（凭什么写）/ self（自己怎么看这次写）。

详细定义、边界、不是什么：docs/history/Meta-DGTF-道生三阶模型-来源与定义.md。

## 二、V2.2.x 的核心能力（V2.2.0 行为融合 + V2.2.1–V2.2.13 补丁谱系 + V2.2.14 本地档 few-shot/降档 + V2.2.15 stage 登记闭环与本地链路提速 + V2.2.16 JSON 结构门与本地档自动切 + V2.2.17 本地 prompt 瘦身 + V2.2.18 发布流程门与证据出口 + V2.2.19 输入驱动自动模式/每模式专属配置/动态调整 + V2.2.20 道生支路接入统一模式体系 + V2.2.21 道生=标准模式融合 + V2.2.22 动态最优配置全流程可达与更优判据 + V2.2.23 route 安全门修复 + V2.2.24 动态配置/依赖优化 + V2.2.25 多圈档/缓存感知 + V2.2.26 route 子集成本模型 + V2.2.27 App 开销/阶段路由/引擎依赖闭包 + V2.2.28 预算 token 硬上限 + V2.2.29 预算墙钟硬上限 + V2.2.30 层子集质量风险 + V2.2.31 省层收益判定 + V2.2.32 kind-aware 收益 + V2.2.33 短程成本锚点 + V2.2.34 choice 省层收益 + V2.2.35 rounds 依赖收益 + V2.2.36 上下文成本 + V2.2.37 quality-retry 决策 + V2.2.38 续航预测 + V2.2.39 未验证缓存复用 + V2.2.40 新鲜度门 + V2.2.41 语义缓存预判 + V2.2.42 预判缓存 + V2.2.43 质量证据 + V2.2.44 题型矩阵 + V2.2.45 语义索引持久化 + V2.2.46 创建前预期 + V2.2.47 项目证据/预判落盘 + V2.2.48 前端预期展示 + V2.2.49 阈值/选档建议 + V2.2.50 tier A/B 证据 + V2.2.51 opt-in 优先成本 + V2.2.52 rl-qf 修复/提示 + V2.2.53 预期 vs 实测 + V2.2.54 README 数字同步 + V2.2.55 fast_gate 校验 + V2.2.56 历史卡片预期/实测）

### 四层螺旋

- 四层可单独跑、可并行、可断点续跑；
- 每层有各自的池、悬置/债务/张力、停止判据与 view 形态；
- 悬置不打分，未对齐是合法结果，失败留痕。

### V2 三平面

- **知识面 EML v2**：双时态事件溯源、AGM/TMS、BM25+RRF+MMR、只给调度数值先验。
- **控制面 Scheduler v2**：MAPE-K + EVOI + MPC + Pareto + 安全盾。
- **执行面四层契约**：0 层不答、1 层不闭合、both 不删败方、all 不重写前层。

### F2–F5 契约

- F2 all ClosurePackage：decision / actions / not_do / residual_risks / provenance / confidence；
- F3 1 层 AnswerSet：三态答案、coverage、citations、无越权；
- F4 both 论证契约：argument_graph、defeated/undecided、不强行消解；
- F5 0 层生成+审计：aspect_map / probes / suspensions / novelty_curve。

### 事实门与答案门

FactCard、证据去重/预算、官方源、引用、retrieval-vs-reasoning 一致性，
answer_quality=verified / needs_evidence；答案门与过程门分离。

### 历史谱系融合（V2.1 创新）

- history_manifest.json 记录 178 个历史快照；
- 17 条能力轴：V1 来源 → V2 实现 → 测试判据；
- 每次运行选择 contract-first / exploration-first 作业剖面；
- packed 写入 history_fusion provenance，不改写答案；
- 连续性 readiness=1.00，continuity_ok=True。

详见：
- docs/history/Meta-DGTF-道生三阶模型-版本演化史.md
- docs/history/Meta-DGTF-道生三阶模型-V1-V2能力融合矩阵.md

### 行为级融合（V2.2 创新）

- 5 个历史 arm：v1_spiral / v1_frontier / v2_contract / v2_pareto / fusion_full；
- 按题面特征与历史 outcome 选择 arm；
- 只修改 auto 调度项（mode/rounds/stop/thinking/effort），不改显式 CLI；
- 每次运行记录 outcome（quality/calls/tokens，不含答案文本），下一跑用 UCB 选择；
- packed 写入 behavior_fusion provenance，不生成或改写答案。

### 本地工作台

- HTTPS、访问口令、CSRF、Host 校验、上传/JSON 上限；
- 任务、产物、层视图、质量、DSH 会话、Agent 提案、知识检索；
- RAG v2：BGE + BM25 + 引用 + 分层索引 + 追溯；
- 本地模型：Qwen2.5-0.5B/1.5B、DeepSeek-R1-Distill-Qwen-1.5B；LoRA/scheduler 脚本可复跑。

## 三、快速开始

### 依赖

~~~bash
pip install -r requirements.txt
~~~

本地模型环境见 requirements-local-model.txt，安装到 local_model/envs/dgtf_llm_env/，不要装进 App 运行环境。

### 凭据

在仓库根建 .env：

~~~text
DGTF_API_KEY=sk-...
DGTF_BASE_URL=https://api.deepseek.com
# 联网检索 / 抓取默认走 DeepSeek 官方（/v1/tools/search + /v1/tools/fetch），复用 DGTF_API_KEY
~~~

### 跑一次

~~~bash
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.79.py "你的问题"

# 四层各一圈
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.79.py --route 0,1,both,all --rounds 1 "你的问题"

# 质量/成本预设
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.79.py -c configs/方案F-帕累托最优.yaml "你的问题"
~~~

常用参数：

| 参数 | 作用 |
|---|---|
| --route 0,1,both,all | 只跑部分层 |
| --rounds 4 | 每层圈数，也可写 0:6,both:5 |
| --parallel serial/A..H | 串行 / 并行档位 |
| --web auto/on/off | 联网检索 |
| --history-fusion auto/on/off | 历史融合 provenance |

产物落在 outputs/（md 正文 + json）。空题会被拒绝，零 LLM 调用。

## 四、验证

当前版本实测：

| 门 | 结果 |
|---|---|
| fast_gate | **19 / 19 PASS**（动态选最高版引擎 + engine_alignment + release_process_selftest；audit70 71/0） |
| V2 tests_*.py | **71 / 71 PASS（1209 项检查，SKIP 0）** |
| App selftest | **PASS 459 / FAIL 0**（含本地链路 11 项） |
| 一键验收 `scripts/final_acceptance.py --with-service` | **PASS 30 / SKIP 0 / FAIL 0**（29+1 步；含 dynamic_opt、fused_optimal、fused_full_chain、daosheng_unified、auto_mode_local） |
| **APP→引擎→本地模型 e2e** | **18 / 18 PASS**，冷缓存真跑 **14.7～106.7s**（本地链路验证档；V2.2.15 同判据 124.9～157.9s；热缓存不计），零 API 成本 |
| **JSON 结构门受控 A/B**（17 条固定真实 prompt） | JSON 解析率 35%→**59%**、撞上限率 41%→**6%**、总墙钟 −**55%**（详见 docs/releases/V2.2.16.md） |
| **本地 prompt 瘦身**（584 条真实 prompt 离线 + 16 条机制级 A/B） | 可省 **45.3%** token（schema 零丢失）；机制级 prompt 字符 −38.7%、token −15.4%（受 2048 截断上限所限）；尾部指令不再被右截断（详见 docs/releases/V2.2.17.md） |
| **四层目标探针**（route 0/1/0,1,both/0,1,all） | **81 / 81 PASS**（V2.2.52 复跑：4 case 共 219 calls，墙钟 538.1s；层1 转为「判据样本不足」少 1 条断言）；层0 达成（excavate=0.0）/ 层1 判据样本不足 / both 判据样本不足 / all 未达成（0.75） |
| 本地服务延迟 | p50 3.0–3.5s、p95 8–9s（单 token graph replay 59→28ms）；JSON 约束后单次中位 3842→1651ms |
| 四层全跑 | 136 calls / 818.4s（V2.2.14 快照；四层读数全出） |
| **透传降质修复（V2.2.77）** | v2_online 结构化 route/rounds 被 str() 传给引擎 ⇒ 四层跳过/圈数忽略；修复后 calls 1→91、tokens 570→699,592、verified、ready=True |
| 矩阵自检（V2.2.76） | detect_violations 自检 3/3 mutants caught |
| 动态矩阵门禁（V2.2.75） | fast_gate dynamic_matrix（18→19），36 组合 0 违反才 PASS |
| 动态配置矩阵（V2.2.74） | 36 组合 0 违反；<¥8 fast、≥¥8 quality/B；fact/choice web on |
| 方差行自动同步（V2.2.73） | sync 自动重写方差两行 |
| 复现性矩阵（V2.2.72） | 默认温度不可复现；temp0 下可复现（可测❌） |
| playbook 只读基线（V2.2.71） | temp0+只读基线可复现（见 V2.2.72 矩阵） |
| playbook 状态实验（V2.2.70） | temp0+已有 playbook 可测稳定；fresh playbook 稳定但未测出 |
| 层1 可测可复现（V2.2.69） | api.temperature=0 固定解码；默认仍 0.6 |
| 层1 不可复现根因（V2.2.68） | EML/playbook 状态 + 温度 0.6 共同造成波动 |
| 层1 可测性（V2.2.67，复跑修正） | 曾观测 valued 一次，复跑均 unmeasured；不可稳定复现 |
| 证据时序检查（V2.2.66） | 证据不得早于当前引擎构件 |
| 研究层归因（V2.2.65） | probe P2g（82→83）结构化归因 |
| 稳定性文档护栏（V2.2.64） | stability_guard 扩展文档/README 断言 |
| 历史/归档 quality 护栏（V2.2.63） | App selftest 457→459：list_chats/archivedTask quality 字段 |
| 稳定性护栏（V2.2.62） | fast_gate stability_guard（17→18） |
| 判据稳定性根因（V2.2.61） | docs/判据稳定性根因与修复_20261030.md |
| 串行锁可重入（V2.2.60） | 锁可重入；验收/V2/App selftest 取锁；并发验收+ffc 30/30+25/25 |
| 判据串行锁/ffc 稳健（V2.2.59） | 7 个重资源判据共享锁；并发 ffc+fo 25/25+30/30 |
| 读数方差统计（刷新） | 46 次历史：case0 均值 0.36 / both 0.021 / all 0.582 |
| 归档视图预期/实测（V2.2.57） | 归档详情展示「预期 x% · 实测 y」 |
| 历史卡片预期/实测（V2.2.56） | /api/chats 附 quality 字段（120s 时间窗） |
| fast_gate 数字校验（V2.2.55） | readme_numbers 检查（16→17） |
| README 数字同步（V2.2.54） | sync_readme_numbers.py --check/--write |
| 预期 vs 实测（V2.2.53） | quality_actual 随任务 GET；前端展示实测 |
| rl-qf 修复/提示（V2.2.52） | 修复 rl-qf 属性拼接 bug；tier_advice 提示 |
| opt-in 优先成本（V2.2.51） | prefer_cost_when_unverified（默认关）；fact 不降 |
| tier A/B 证据（V2.2.50） | fast 省 ~3.6% tokens、墙钟减半 |
| 阈值/选档建议（V2.2.49） | 0.98 边界 3/3；tier_advice advisory |
| 前端预期展示（V2.2.48） | renderMeta 新增 rl-qf 只读标签 |
| 项目证据/预判落盘（V2.2.47） | project 0/4；预判结果落盘 120s/300 条 |
| 创建前预期（V2.2.46） | quality_forecast 三维随响应 |
| 语义索引持久化（V2.2.45） | 候选清单落盘 300s；跨进程 0.01s 恢复；启动预热 |
| 题型矩阵（V2.2.44） | fact 2/2；reasoning 0/6、choice 0/6、project 0/2 |
| 质量证据（V2.2.43） | fact+web on 2/2 verified；加圈未提升；fact 高圈锚点 67,753 |
| 语义预判缓存（V2.2.42） | 候选清单 300s + 结果 120s；dynamic_opt 97s→6.5s |
| 语义缓存预判（V2.2.41） | verified TTL 168h；BGE≥0.98 按 10% 成本计 |
| 缓存新鲜度门（V2.2.40） | 未验证复用 max_age_h（warn 24h/critical 72h）；D5 拒绝/D6 放行 |
| 未验证缓存复用（V2.2.39） | 预算紧时同题精确匹配复用 unverified 产物；语义回退仍 verified |
| 余额续航预测（V2.2.38） | budget_forecast（safe_runs/balance_after/advice）；续航不足降 fast |
| quality-retry 决策（V2.2.37） | plan.quality_retry advisory + budget_cap 上下文分解 + cache_roi |
| 上下文成本（V2.2.36） | 项目题注入 +5,662 tokens；候选 context_tokens/context_cost |
| rounds 依赖收益（V2.2.35） | reasoning 高圈收益≈0；高圈 keep_four_layers；高圈锚点 |
| choice 题型收益（V2.2.34） | choice 省 ~40%；kind 表/锚点/风险证据补全 |
| 短程成本锚点（V2.2.33） | fact 65,427 / reasoning 72,799 实测锚点；显式 rounds 只评估该档 |
| kind-aware 省层收益（V2.2.32） | reasoning 实测省 ~39%，fact ≈0；route_pruning 题型实测优先 |
| 省层收益判定（V2.2.31） | 6 跑多样本 A/B：短程事实 keep_four_layers；长程模型估算 may_save |
| 层子集质量风险（V2.2.30） | 3 臂 A/B；默认 union 四层；显式省层标 high/info + 证据 |
| 预算墙钟硬上限（V2.2.29） | max_minutes=估算 tokens/600×1.5（最低 1 分钟）→ --max-minutes；显式优先、ok 档不限 |
| 预算 token 硬上限（V2.2.28） | plan.max_tokens=估算×1.5（最低 20k）→ --max-tokens；显式优先；budget_cap 可审计 |
| App 开销 + 阶段路由（V2.2.27） | App 开销系数 1.10；有效 route 成本；warn/critical 非项目 → dual_judge=cache；引擎 route 依赖闭包 |
| route 子集成本模型（V2.2.26） | 3 臂有界云实测校准层×圈可加模型（R2 误差 0.05%）；候选成本按自身 route/rounds 估算 |
| 动态配置细化（V2.2.25） | fast/economy/critical 三档多目标；缓存命中按 10% 成本放宽；fast 下限 0.90 |
| 全链路动态配置 + 动态依赖（V2.2.24） | 余额×预留×质量下限×成本多目标；budget_level 降圈；route 依赖闭包 both⇒0/1、all⇒both/0/1 |
| route 安全门（V2.2.23） | 本地 route 预测默认 union（预设∪预测；预设四层时结果恒四层，不再砍层）；preset/predict 可配；plan 带 route_policy/source/prediction |
| 融合模式更优 + 动态最优配置 | 预算参数 --max-minutes/--max-tokens 接通 CLI/App（层/波边界降档 fast，锁定不改圈）；能力对等 + 实测矩阵对比（成本档 tokens 省 ≥15%、质量 ±0.02 内）+ 引擎 tick 真代码判据 |
| 道生=标准模式（融合，V2.2.21） | auto/standard 统一解析为 daosheng（单一链路）；旧 standard 仅 plan 失败时 fail-open 回退；mode 回显 fused/fused_from |
| 道生支路统一模式（V2.2.20） | daosheng/daosheng_fast 采用 MODE_CONFIGS 默认参数 + 透传 --mode（动态调整生效）；显式 rounds 锁定不改圈 |
| 发布流程门（scripts/release_process_check.py --pre-tag/--post-tag） | **PASS（N/A 项均带原因）**：版本 8 处一致 / 发布产物 / 证据新鲜度 / README 数字逐项对齐 / 三标签 / 完整性路径 / DSH 闭环 |
| App plan 不变量 / dual_judge 防护 | 18/18、7/7（进一键验收） |
| 场景矩阵一致性护栏 | 进一键验收（scripts/update_scenario_matrix.py） |
| 离线重放护栏 / 过程门审计护栏 | 进一键验收（scripts/lead_offline_fact_replay.py、lead_process_gate_audit.py） |
| 文件完整性 / 路径 | file_integrity bad=0；verify_project_paths PASS（发布流程门内） |
| 依赖 pip check | 0 broken（主环境 + 本地模型环境） |
| 全流程帕累托基线 | python scripts/pareto_flow.py 可复跑（质量/tokens/calls 非支配前沿） |
| 历史融合 readiness | 1.00 / continuity_ok=True / manifest_digest 8a3c18076a478406 |
| 本地模型 stage 服务 | 8772 /health、/metrics；适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；fp32 + CUDA graph + JSON 约束生效 |
| DSH 全流程闭环检查 | **PASS 4 / FAIL 2→N/A**（「生产包早于引擎修复」「用户 App 实例不可达」显式归 N/A，原因见发布流程门证据） |

### 阶段历史真跑读数（需 API 预算/真跑，本轮未复跑；引用需注明版本）

| 项 | 读数 |
|---|---|
| 四层全跑（V2.2.14） | 136 calls / 818.4s |
| 离线重放护栏（阶段快照） | answered 81 / gaps 清零 17 / 数值 34→38 / 0 新答案变差 |
| 过程门审计护栏（阶段快照） | standard 83.5% / 审计已修复 27 / 未修复 0 |
| 场景矩阵 live 对照（阶段快照） | 60 行（fact 50/App 12），max 0.032 |
| 行为融合 | 5 arms / auto 调度融合 / outcome UCB |
| 细粒度自省回放 | 177 packs / 577 views；auto 跳过率上界 23.7%；auto_narr prompt −29.9% |
| M4 保形下界 | OOF 0.800（n=90）/ 留出 0.778（n=18）；下界 0.72~0.77；alpha=0.2 |
| 道生专属模式 e2e | quality 0.9465 / verified / ready=True；723K tokens / 97 calls / 586s |
| 道生专属模式 | mode=daosheng mock 201；selftest ★T3 73 条全绿 |
| 定向 0 层真跑 | 20 calls / 85,807 tokens / zero_contract ok / provenance 17/17 |

~~~bash
python fast_gate.py

$env:PYTHONPATH="$PWD;$PWD/dgtf_engine"
Get-ChildItem dgtf_engine\dgtf_v2\tests_*.py | ForEach-Object { python $_.FullName }

python -m dgtf_v2.history_fusion --markdown

python dgtf_app/server.py
python dgtf_app/selftest.py

python -m pip check
local_model\envs\dgtf_llm_env\Scripts\python.exe -m pip check
~~~

## 五、目录

| 路径 | 是什么 |
|---|---|
| dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.79.py | 当前生产引擎 |
| dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.19.py | 上一基线（输入驱动自动模式 + 动态调整） |
| dgtf_local_llm/ + scripts/local_model/openai_shim.py | 本地链路：8772 推理服务 / 8773 OpenAI 适配层 |
| configs/本地模型-全链路.yaml | App 本地档预设（零 API 成本链路） |
| dgtf_engine/dgtf_v2/ | V2 核心：契约/EML/调度/四层/F2–F5/融合 |
| dgtf_engine/dgtf_v1/ | V1 归档（引擎/报告/脚本/fixtures） |
| dgtf_app/ | 本地 Web 工作台 |
| docs/history/ | 来源、能力、版本演化、融合矩阵 |
| docs/releases/ | 版本发布说明 |
| CHANGELOG.md | 全版本变更记录 |
| outputs/ / dgtf_memory/ | 运行产物 / 运行记忆（不进公开仓库） |
| local_model/ | 本地模型、venv、训练脚本（权重不进仓库） |

## 六、版本迭代规则

采用语义化版本 VMAJOR.MINOR.PATCH：

- MAJOR：架构断代或不可回滚契约变更；
- MINOR：能力融合、新增机制、发布级功能；
- PATCH：修复、判据补强、文档/依赖同步。

每版固定动作：

1. 复制上一版引擎，升 __version__（只在新版上改）；
2. 新增/更新判据：V2 `tests_*.py`（自动进 run_v2_tests）；必要时 `scripts/local_model/test_*.py`（进 final_acceptance）；
3. 跑门并**留证据**：`fast_gate.py` → `docs/fast_gate_latest.json`；`scripts/run_v2_tests.py` → `docs/v2_tests_latest.json`；`scripts/app_selftest_gate.py`（自动起临时 App server）→ `docs/app_selftest_latest.json`；`scripts/final_acceptance.py --with-service` → `docs/acceptance_latest.json`；两套 python 的依赖检查；
4. 写 CHANGELOG、`docs/releases/V<版本>.md`、根 `V<版本>-发布报告.md` / `V<版本>-收束报告.md`；
5. 更新 README / PROJECT_MAP / PROJECT_LAYOUT / NAMING / Pages(`docs/index.html`) / `docs/README.md` 索引 / `docs/项目状态快照_<日期>.md`；
6. 提交后打 `V<版本>`、`engine-V<版本>`；App 有变更时打 `app-V<App版本>`（未变则沿用已发布标签、不移动）；最后跑 `scripts/release_process_check.py --pre-tag`（提交前）/ `--post-tag`（打标签后）作为发版回执。

机器核对（防漏/防漂）：版本 8 处一致、发布产物、证据新鲜度、**README 数字 ↔ 证据逐项相等**、三标签策略、N/A 必须带原因。

完整规范：dgtf_engine/dgtf_v2/NAMING.md。

## 七、红线

1. 输入是形状，不是数据。
2. 悬置不打分。
3. 未对齐是合法状态。
4. 停止与清算分开。
5. 失败留痕，不删行。
6. 入池前挡重复。
7. 参数按层可覆盖。
8. 自省是另一个视角，不可合并。
9. EML 只动调度与守卫阈值，不碰答案。
10. 没有读数就不假装有。

完整决策记录见 docs/不做什么-v1221.md。

## 八、开源、安全与运行数据

- 许可证：Apache-2.0，见 LICENSE 与 NOTICE；模型权重不随仓库分发。
- 项目门户：https://liao-wc.github.io/Meta-DGTF/
- 运行数据：dgtf_memory/、outputs/、runs/、cache/ 不进入公开仓库。
- 漏洞报告：使用 GitHub Private Vulnerability Reporting。
- 安全边界：App 默认仅监听本机；公网部署需自行加 TLS、认证、限流和独立服务账户。

## 九、当前收束

- 版本：V2.2.79（App 2.0.83）
- 历史版本：178 个快照（V1.0 → V2.0.0）
- 能力轴：17 条，readiness=1.00
- 行为臂：5 个（v1_spiral / v1_frontier / v2_contract / v2_pareto / fusion_full）
- 收束报告：V2.2.79-收束报告.md
- 发布说明：docs/releases/V2.2.79.md / docs/releases/V2.2.78.md / docs/releases/app-V2.0.83.md
- **优化交付（Round 1–83）**：`docs/最终交付说明-20261026.md`、
  `docs/验收总览-20261026.md`、`docs/ab_evidence_20261025.md`（§1–§78）
- **本地模型默认**：v8b（mixed 配方，质量持平 v6、p50/p95 更快；训练/评测/切换全链证据）
- **事实成本档**：fast+web 20 类领域 verified，质量 0.92–0.99、tokens 570–750K、
  墙钟 190–290s；场景矩阵事实 **60 行** + App e2e **12 行**
- **一键验收**：`python scripts/final_acceptance.py --with-service` → PASS 29 / SKIP 0 / FAIL 0（三态语义，SKIP 单列）
- **发布流程门**：`python scripts/release_process_check.py --pre-tag`（提交前）/ `--post-tag`（打标签后）→ 版本/文档/证据/标签/N-A 逐项核对
- **本地全链路**：`python scripts/local_model/e2e_app_local.py`（18/18）与 `python scripts/local_model/probe_layer_goals.py`（四层目标，81/81）
- 已知边界：检索依赖、跨片段语义（成年年龄）、多值列举；0.5B 本地底座结构化输出能力（层1/both/all 的「达成」需更强模型）；本地档非生产质量档
