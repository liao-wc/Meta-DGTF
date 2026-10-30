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

