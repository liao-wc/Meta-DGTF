# App 2.0.46 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.21（零行为差，参数通道沿用 V2.2.20）。
> 主题：**道生模式与标准模式融合——道生模式成为标准模式（单一链路）+ 全链路打通判据**。

## 1. 融合语义

- `resolve_mode`：
  - `auto` ⇒ **daosheng**（source=auto-fused；project_related 只决定是否注入项目背景，不改链路）；
  - `standard` ⇒ **daosheng**（source=fused-standard，requested 保留原入口）；
  - `daosheng` / `daosheng_fast` 保持不变。
- 所有真实任务统一走一条链路：**道生 plan（preset + M4 + 预算守卫）→ MODE_CONFIGS 默认参数 →
  --mode 透传 → 运行期 dynamic_adjust → 产物/回显**。
- 旧 standard 链路仅作为**计划生成失败时的 fail-open 回退**保留（不删除，保可用性）。
- mode 回显新增 `fused / fused_from`；前端模式标签显示"标准·道生"。

## 2. 全链路打通

- 新增 `scripts/local_model/test_fused_full_chain.py`：起临时 App server → POST /api/tasks
  （mode=auto，默认）→ 引擎真跑本地 0.5B 链路 → 校验任务 mode.id=daosheng/fused、
  plan.policy=daosheng.v1、engine_mode∈{B,fast}、packed provenance=V2.2.21、
  auto_mode.plan 与 adjustments、answer_gates/calls 读数，最后关服。
- 一键验收新增 `fused_full_chain` 步骤（服务型）：App → 调度 → 引擎 → 本地模型 → 产物 → 读数 全链真跑。
- 默认入口（auto）不再分流到旧链路；standard 显式入口同样融合。

## 3. 判据

- App selftest：mode 解析/端到端三处更新为融合语义（总数不变）；
- 新增 fused_full_chain（全链路真跑，含 mode/fused/plan/provenance/auto_mode/answer_gates）；
- 既有 daosheng_unified（27）与 auto_mode_local（12）继续跑。

## 4. 兼容性

- 显式 mode=standard 的调用方无感（仍 201，只是实际走道生 plan，回显 id=daosheng/requested=standard）；
- 道生计划异常的 fail-open 回退保留（旧链路兜底）；
- 旧引擎无 --mode 时能力门控自动不透传（App 2.0.46 与引擎 V2.2.21 配套）。
