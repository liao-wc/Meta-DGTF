# 优化预算与真跑实验计划（2026-10-25，Lead 维护）

## 一、账户与价格事实

- 账户余额（2026-10-25 07:40）：约 **¥23.2**（`https://api.deepseek.com/user/balance`，DGTF_API_KEY）。
- **同一账户同时承载 DSH Agent 会话消耗**：DSH 凭据 refs `DEEPSEEK_API_KEY`（sk-64b2…）
  与项目 `.env` 的 `DGTF_API_KEY`（sk-97d2…）查询到同一个余额（07:31 两边同读 23.21）。
  ⇒ 预算 = Agent 推理 + 引擎真跑的总和。Agent 侧实测燃烧约 ¥4~6/小时（4~5 个并发 agent）。
- deepseek-flash 官方价（每 1M tokens，USD；谷时/峰时）：
  | 项 | 谷时 | 峰时 |
  |---|---|---|
  | 输入 cache hit | $0.003 | $0.006 |
  | 输入 cache miss | $0.15 | $0.30 |
  | 输出（含推理 token） | $0.60 | $1.20 |
  - 峰时：UTC 01:00–04:00、06:00–10:00，周一至周五；**周末/中国法定假日全天谷时**。
  - 2026-10-25 是周日 ⇒ 今天全天谷时，真跑不受时间窗限制。

## 二、实测成本基线（Lead 探针，V2.2.2）

`scripts/lead_probe_run.py`，route 0 / 1 圈 / thinking auto / web off：

| 读数 | 值 |
|---|---|
| calls / prompt / completion | 23 / 74,131 / 41,507 |
| 其中 reasoning tokens | **32,602（completion 的 79%）** |
| wall | 312.4s |
| 估算成本（按 tokens 计） | **≈ ¥0.26**（余额差被 Agent 消耗污染，以 tokens 计为准） |

分阶段（calls / prompt / completion / reasoning / avg ms）：

| stage | calls | prompt | completion | reasoning | avg ms |
|---|---|---|---|---|---|
| unknown（ing/生成等） | 9 | 37,049 | 27,382 | 21,723 | 21,177 |
| self_check | 2 | 11,516 | 6,220 | 5,712 | 20,150 |
| dual_judge | 2 | 6,613 | 3,861 | 3,176 | 11,694 |
| phase_probe | 2 | 7,671 | 2,474 | 1,653 | 8,272 |
| re_anchor | 2 | 4,804 | 248 | 0 | 1,444 |
| assess_decidability_from_pool_view | 1 | 3,465 | 282 | 0 | 1,810 |
| re_evaluate_pool | 2 | 1,423 | 444 | 0 | 1,333 |
| assess_decidability | 1 | 539 | 516 | 338 | 4,065 |
| check_input_sanity / check_structure_saturation | 2 | 1,051 | 80 | 0 | ~770 |

**结论**：辅助阶段的成本大头是**推理 token 与墙钟**，不是输入 prompt；
双跑全量 B 估算 ¥1.8~2.9（1.27M tokens 口径），与历史「约 ¥2~4」一致。

## 三、预算分配（总额 ¥23.2，硬上限）

| 用途 | 预算 | 说明 |
|---|---|---|
| Agent 会话（4 名 teammate + Lead） | ≤ ¥9 | 按 ~¥5/h 估，约 1.5~2h 工作窗口 |
| 真跑实验（E1–E4） | ≤ ¥9 | 见第四节；单项超支即停 |
| 保留缓冲（修复/复验/收尾） | ≥ ¥5 | 不到缓冲不动 |

纪律：
1. 真跑前必须 `python scripts/ab_bench.py run ...`（内置余额门槛 + 花费落账），
   一律用 `lead_probe_run.py` 或 ab_bench 记录 tokens 级成本；
2. 每次真跑必须带 `--tag`，结果进 `docs/ab_results.jsonl`，可 `pair` 复算；
3. 余额 < ¥8 时停止新增真跑，只做离线验证与门禁；
4. 同一结论不得重复买数据：先离线回放，再真跑确认。

## 四、真跑实验清单（按优先级）

| # | 实验 | 配置 | 成本估算 | 成功判据 | 状态 |
|---|---|---|---|---|---|
| E1 | self_check auto 局部对照 | route 0；rounds 1；web off；behavior-fusion off；`--self-check-mode auto` vs V2.2.2 探针基线 | ≈¥0.25 | self_check calls 15→明显下降；无崩溃/决策缺失 | 待 V2.2.3 |
| E2 | self_check auto 全量对照 | route 0,1,both,all；rounds 0:2,1:4,both:2,all:3；web off；`--self-check-mode auto` | ≈¥2.5 | quality ≥ 对照 - 0；tokens/wall 双降；answer_ready/quality 不降 | 待 E1 通过 |
| E3 | stage thinking 关闭对照 | 同 E2 + `--stage-thinking "dual_judge=disabled,self_check=disabled"` | ≈¥2.5 | 质量不降；reasoning tokens 明显下降；wall ≤ 对照 | 待 E2 |
| E4 | 道生专属模式端到端 | App mode=daosheng（真实引擎一次项目题） | ≈¥2.5 | answer_ready=True；plan/落账可审计 | 待 app-mode + V2.2.3 |
| E5 | 本地模型草稿 go/no-go | 离线评测（GPU，零 API） | ¥0 | position 高置信覆盖率×一致率 ≥ 阈值 | 随 T2 |

对照数据来源（零成本）：
- V2.2.2 全量基线：`20261024_205018`（quality 1.0000 / 119 calls / 1.269M tokens / rounds 0:2,1:4,both:2,all:3）；
- 局部基线：本次探针 `outputs/_lead_audit/probe_route0_r1.json`（23 calls / 115,638 tokens / 312.4s）；
- 历史负例：`20261024_221714`（关 self_check → quality 0.94），用于证明「不能直接关」。

## 五、本轮（Round 1）退出条件

1. fast_gate 12/12、V2 tests 全绿（含新增）；
2. self_check 确定性核离线回放证据（决策等价率/召回数字）；
3. E1/E2 至少完成 E1，E2 视余额；
4. App selftest 全绿 + mock 端到端；
5. 本地模型训练/评测数字（无论 go/no-go）；
6. CHANGELOG + 文档 + 提交，余额余量如实记录。
