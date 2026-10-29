# App 2.0.45 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同步发版 V2.2.20（道生支路接入统一模式体系 · 方案 A）。

## 1. 变更

- 道生支路接入统一模式体系（方案 A）
  - daosheng_mode.build_plan：engine_mode（B/fast/serial）对应的 MODE_CONFIGS
    作为默认参数来源（parallel/thinking/effort），道生预设显式值（rounds /
    rounds_quality / rounds_fast / parallel）与场景规则（事实/选项题强制 web）优先；
  - plan 新增 mode / unified_config / rounds_locked；
  - apply_plan 把 mode 透传给引擎 ⇒ 引擎启用 MODE_CONFIGS + 运行期
    dynamic_adjust（此前道生支路不传 --mode，动态调整不生效）；
  - 显式 rounds（道生质量档/快档）⇒ rounds_locked=true：运行期调整只调
    thinking/web、不改圈（与「显式圈数优先」补丁口径一致）。
- server 道生分支回显：mode_fusion.unified=true / config / rounds_locked / dynamic=true。
- M4 预测回显：first_config / optimality / policy，道生选档最优性可审计。

## 2. 兼容性

- 默认行为不变：道生质量档仍 quality-first、事实题仍强制 web、预算守卫仍可降级；
- standard 支路（V2.2.19 输入驱动自动选档）不受影响；
- 不新增端口/服务；App 2.0.45 与引擎 V2.2.20 配套，旧引擎下 --mode 能力门控自动不传。

## 3. 判据

- 新增 scripts/local_model/test_daosheng_unified.py（零成本；含 rounds_locked /
  统一配置 / mode 透传 / 场景规则优先 / 变异体）；
- 一键验收新增 daosheng_unified 步骤（strict）。

## 4. 验收

- App selftest：见本轮自动门证据；
- 一键验收 --with-service：PASS 27 / SKIP 0 / FAIL 0；
- 发布流程门 pre/post-tag 全 PASS（N/A 带原因）。
