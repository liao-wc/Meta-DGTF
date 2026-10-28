# Meta-DGTF-道生三阶模型

一个**单文件四层螺旋推理引擎** + **V2 三平面核心** + **本地 Web 工作台**：
修行 / 研究 / 对撞 / 元，跑出可审计、可回放、可融合的产物。

- **当前版本**：V2.2.4（V2.2.3 机制基线 + 本地档 CUDA graph/合批/贪心/超时补丁；默认零行为差） / App 2.0.36（道生专属模式 + 三体动态计划 + 预算守卫）
- **生产引擎**：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py
- **V2 核心**：dgtf_engine/dgtf_v2/
- **人用界面**：dgtf_app/（App 2.0.36，道生专属模式 + DSH 本对话实时镜像 + 会话列表实时打开 + 健康读数缓存）
- **融合实现**：单引擎内联（Meta-DGTF-V2.2.4.py）；V2.1 外部模块仅作回滚参考
- **历史清单**：dgtf_engine/dgtf_v2/history_manifest.json
- **版本规范**：dgtf_engine/dgtf_v2/NAMING.md
- **历史归档**：元DGTF-V1历史归档-20261023.zip（V1.0 → V1.30.4）

> 这份 README 只写能被验证的事；详细来源、能力、版本演化见 docs/history/。
> **2026-10-27 收束同步**：验收 **18/18（有服务）/17/17（无服务）**；V2 **54/54（855 checks）**；
> fast_gate 12/12；packs **198**；服务适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3；
> CUDA graph（单/批，cache 3072）与 dual_judge local（质量优先 opt-in）已合并。
> 完整现状见 `docs/项目状态快照_20261027.md`。

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

## 二、V2.2.x 的核心能力（V2.2.0 行为融合 + V2.2.1/V2.2.2 补丁 + V2.2.3 细粒度自省 + V2.2.4 本地档加速补丁）

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
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py "你的问题"

# 四层各一圈
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py --route 0,1,both,all --rounds 1 "你的问题"

# 质量/成本预设
python dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py -c configs/方案F-帕累托最优.yaml "你的问题"
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
| fast_gate | PASS 12 / FAIL 0 |
| V2 tests_*.py | **51 / 51 PASS（806 项检查）** |
| App selftest | PASS 444 / FAIL 0 |
| 一键验收 `scripts/final_acceptance.py --with-service` | **18 / 18 PASS**（无服务 17/17）；含四道护栏 + 防错训/probe/缓存/快失败/一致性/fx 判据 |
| 离线重放护栏（124 packs） | answered 81 / gaps 清零 17 / 数值 34→38 / **0 新答案变差** |
| 过程门审计护栏（85 packs） | standard 83.5% / 审计已修复 27 / **未修复 0** |
| App plan 不变量 / dual_judge 防护 | 18/18、7/7 |
| 场景矩阵一致性 | **60 行 live 对照**（fact 50/App 12），max |Δ| 0.032 |
| 依赖 pip check | 0 broken |
| DSH 全流程闭环检查 | PASS 6 / FAIL 0 |
| 全流程帕累托基线 | scripts/pareto_flow.py（质量/tokens/calls 非支配前沿） |
| 历史融合 readiness | 1.00 / continuity_ok=True |
| 行为融合 | 5 arms / auto 调度融合 / outcome UCB |
| 细粒度自省回放 | 177 packs / 577 views；auto 跳过率上界 23.7%；auto_narr prompt -29.9% |
| M4 保形下界 | OOF 覆盖率 0.800（n=90 有效样本）/ 留出 0.778（n=18）；下界 0.72~0.77；alpha=0.2 |
| 本地模型 stage 服务 | 8772 /health、/metrics（含 latency p50/p95）；**v9b 默认**（0.5B base，val_loss 0.1989；30 条 held-out 与 v8b 质量持平、p50 4.77s/p95 5.69s；v8b/v6/v5/v2 兜底） |
| 道生专属模式 e2e | quality 0.9465 / verified / ready=True；723K tokens / 97 calls / 586s（rounds=auto 8 圈） |
| 道生专属模式 | mode=daosheng mock 201；selftest ★T3 73 条全绿 |
| 定向0层真跑 | 20 calls / 85,807 tokens / zero_contract ok / provenance 17/17 |

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
| dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py | 当前生产引擎 |
| dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py | 上一基线（保留回滚） |
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

1. 复制上一版引擎，升 __version__；
2. 新增 tests_*.py；
3. 跑 fast_gate + V2 全量 + App selftest + 依赖检查 + 必要真跑；
4. 写 CHANGELOG、docs/releases/V<版本>.md、收束报告；
5. 更新 README / PROJECT_MAP / Pages；
6. 提交，打 V<版本>、app-V<版本>、engine-V<版本> 三标签并发布。

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

- 版本：V2.2.4（App 2.0.36）
- 历史版本：178 个快照（V1.0 → V2.0.0）
- 能力轴：17 条，readiness=1.00
- 行为臂：5 个（v1_spiral / v1_frontier / v2_contract / v2_pareto / fusion_full）
- 收束报告：V2.2.2-收束报告.md
- 发布说明：docs/releases/V2.2.4.md / docs/releases/V2.2.3.md / docs/releases/app-V2.0.33.md
- **优化交付（Round 1–83）**：`docs/最终交付说明-20261026.md`、
  `docs/验收总览-20261026.md`、`docs/ab_evidence_20261025.md`（§1–§78）
- **本地模型默认**：v8b（mixed 配方，质量持平 v6、p50/p95 更快；训练/评测/切换全链证据）
- **事实成本档**：fast+web 20 类领域 verified，质量 0.92–0.99、tokens 570–750K、
  墙钟 190–290s；场景矩阵事实 **60 行** + App e2e **12 行**
- **一键验收**：`python scripts/final_acceptance.py --with-service` → 18/18 PASS（无服务 17/17）
- 已知边界：检索依赖、跨片段语义（成年年龄）、多值列举、dual_judge 无 local 档
