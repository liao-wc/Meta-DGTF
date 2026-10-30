# 动态 min_rounds 设计（层1 可判定化，2026-10-31 · 零成本设计稿）

> 状态：**设计稿，未改引擎默认行为**；所有数字来自本会话零 API 实验与既有证据。

## 1. 证据链

| 版本 | 发现 |
|---|---|
| V2.2.90 | 研究层拆解回退：LLM JSON 失败时从探针/线头生成子问题 ⇒ settlement.total 0→2，层1 从「未测出」→「有值」 |
| V2.2.91 | `--rounds 3 + spiral.min_rounds.1=3` ⇒ 研究层跑满 3/3 圈、trace 3 点、目标 **not_achieved**（不再判据样本不足） |
| §7.10 | 同口径复跑 3/3 均 not_achieved（可判定性稳定；main 0.5/0.0/0.0 随状态波动） |

结论：**研究层跑满 3 圈是可判定性的充分条件**；但默认全量加圈会增加成本，故设计为 opt-in。

## 2. 方案比较

| 方案 | 做法 | 优点 | 风险 |
|---|---|---|---|
| A. 引擎自动 | `spiral.min_rounds_judgeable`（默认 false）开启时，研究层/both 至少 3 圈 | 一处生效，所有入口一致 | 需覆盖串行+并行两条路径；误开成本上升 |
| B. App 计划 | daosheng 计划在 quality 档/预算 ok 时通过 profile 传 min_rounds | 可按题型/预算精细控制 | 要新增 CLI/配置通道，App 需版本 |
| C. 探针/实验 | 仅 probe `--config-set` 使用（当前已可用） | 零产品风险 | 不是生产策略 |

**建议**：先做 A 的**默认关闭配置键**（零行为差），在门槛满足时由 App/profile 显式开启；
B 作为下一阶段（需要真实 A/B 预算）。

## 3. 成本估算（依据既有校准）

- 引擎 `_CALIB.u1 = 37,119` tokens/圈（层1，fast 口径）；DeepSeek 价 ¥2/M tokens ⇒ **约 ¥0.074/额外圈**；
- 本地链实验：2 圈 case1 约 36-43 calls；3 圈 53-77 calls（本地费用 0）；
- 若仅对「research/reasoning + quality 档 + 预算 ok」开启，预估单次增加 1 圈 ≈ ¥0.07-0.15；
- 收益：层1 从「判据样本不足」变为**可判定**（本次判 not_achieved），即可进入达成/未达成统计。

## 4. 门槛建议（默认全关）

```yaml
spiral:
  min_rounds_judgeable: false   # 默认关：零行为差
  min_rounds_judgeable_layers: ["1", "both"]
  min_rounds_judgeable_target: 3
```

开启条件（建议）：预算层级 ok、tier=quality、题型非 fact、且目标层是研究/对撞；
critical/warn 预算不开启（避免预算边界被加圈放大）。

## 5. 验收计划（零成本先行）

1. 纯函数/配置测试：默认 false ⇒ `min_rounds` 不变；true ⇒ 研究层 3 圈（probe `--config-set` 验证）；
2. 串行与并行两条入口都验证（B 模式）；
3. 有预算时做 1 次真 API A/B（2 圈 vs 3 圈，同题）记录 tokens/墙钟/判定。

