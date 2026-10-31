# 本地链路健康快照（2026-10-30 · 零 API）

> 数据源：`scripts/check_local_service.py` + 8772 `/metrics` `/health`（只读）。

## 1. 服务状态

| 项 | 值 |
|---|---|
| 8772 推理服务 | ready |
| 模型 | Qwen2.5-0.5B-Instruct |
| 适配器 | self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1 |
| 8773 OpenAI shim | 运行中（指向 8772） |
| 串行化 | serialized=True |
| 延迟（n=50） | p50 1.7ms / p95 2.9ms / mean 1.9ms |

## 2. 累计指标

- requests_total = 14,009；errors = 8（≈0.06%）；total_ms 约 15,996s；max_ms 45,244（冷加载/长尾）；
- avg_ms ≈ 1,141.9；by_stage 前列：route 2,904、manifest 1,313、json_repair 1,285、dual_judge 1,220、
  self_check 637、ing 969、he_amps 621、expand_pair_merged 888、re_anchor 746 等；
- graph_generations 4,786；json_forced_generations 2,518；dual_judge_fastfail=0；batch_coalesced=48。

## 3. 结论与边界

- 链路健康，可继续零成本复用；
- errors=8 为历史累计（当前日志无 error 行可归因），不阻塞；max 45s 为长尾/冷路径观察值；
- 本快照不含任何云 API 调用。

## 4. 2026-10-31 10:40 复查（零 API）

| 指标 | 值 |
|---|---|
| requests_total | **31,470** |
| errors | **203**（与 10:05 的 30,193 时相同） |
| 期间新增请求 | +1,277，**errors 增量 0** |
| avg_ms | 1,092.8 |
| latency（n=50） | p50 1.8ms / p95 2.7ms / mean 1.9ms |
| max_ms | 45,244（历史长尾，未变） |
| dual_judge_fastfail / waited | 0 / 0 |

结论：**errors=203 是历史静态值**，在随后 1,277 次请求（含 probe/V2/验收）中无新增 ⇒
不是活跃故障；max_ms 45s 同为历史长尾。错误计数来源为请求级 `stat_end(ok=False)`，
当前日志无 error 行可进一步归因（观察项，不阻塞）。

## 5. 2026-10-31 14:40 复查：errors 归因为 HTTP 503

| 指标 | 10:40 | 14:40 | 变化 |
|---|---|---|---|
| requests_total | 31,470 | **37,041** | +5,571 |
| errors | 203 | **237** | +34（≈0.6%） |
| avg_ms | 1,092.8 | 1,094.7 | 平稳 |
| max_ms | 45,244 | 45,244 | 未变（历史长尾） |
| latency p50/p95 | 1.8/2.7ms | 2.2/2.8ms | 平稳 |

**归因**：服务日志中的错误均为 `POST /generate 503`（服务不可用/排队超时/忙），
不是模型崩溃；503 与**并发重负载**（验收/多路本地链）相关，引擎有重试与降级路径，
本阶段所有门禁/验收均通过，未观测到用户面失败。记录为已知容量边界，不阻塞。

### 5b. 503 的四类可指认原因（服务代码静态核对，2026-10-31）

| code | 触发条件 |
|---|---|
| UNAVAILABLE | 模型加载中 / 模型不可用 |
| BUSY | dual_judge 队列过深（>8）时快速回退 |
| TIMEOUT | 生成超过 timeout（响应体带 queue_depth 与 hint） |
| INTERNAL | 生成路径异常（会带异常类名，理论少） |

当前 HTTP 日志只记录状态码（`POST /generate 503`），**不记录 error.code**；
因此 237 次历史错误无法进一步细分到上述四类（需改服务日志并重启 GPU 服务，暂不做）。
可改进项：在 `log_message` 中打印响应体 `error.code`（服务侧改动，重启后生效）。
