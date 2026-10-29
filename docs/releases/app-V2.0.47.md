# App 2.0.47 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.22（动态最优配置全流程可达）。
> 主题：融合模式「更优」证明 + 动态最优配置接通全流程。

## 1. 变更

- 预算配置全流程可达：App 任务 opts 新增 max_minutes / max_tokens 透传
  （能力门控：旧引擎自动不透传），引擎 V2.2.22 新增 --max-minutes / --max-tokens
  并传给 MetaDGTF.run() —— 此前 run() 支持预算但 main 从不传，墙钟降档是死路径。
- 动态最优配置：预算到达时引擎在层/波边界 dynamic_adjust 自动降档 fast
  （质量下限允许时）；显式圈数锁定场景只调 thinking/web、不改圈（与 V2.2.20 语义一致）。
- 融合模式能力对等与"更优"判据：新增 scripts/local_model/test_fused_optimal.py（24 项）：
  · 能力对等（质量策略/缓存/预算/背景注入/web 规则/失败回退）；
  · 更优（用 MEASURED_SCENARIOS 同题真跑：成本档质量在 ±0.02 内、tokens 省 ≥15%，
    三个场景至少 2 个成立；质量优先档保持 B 不低于历史 auto）；
  · 动态配置（引擎 tick 真代码：锁定不压圈/未锁定压圈/fast 质量代理低升 B）；
  · 变异体（删预算 CLI/忽略 rounds_locked/丢质量策略 ⇒ 判红）。

## 2. 兼容性

- 默认行为不变：不传 max_minutes/max_tokens 时与 App 2.0.46 一致；
- 旧引擎能力门控自动不透传 --max-minutes/--max-tokens；
- 全链路真跑判据 fused_full_chain 继续覆盖 App→调度→引擎→本地模型→产物→读数。

## 3. 判据

- 新增 fused_optimal（24 项，进一键验收 strict）；
- 一键验收步数 28 → 29（fused_full_chain / daosheng_unified / auto_mode_local 等继续跑）。
