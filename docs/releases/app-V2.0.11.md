# App V2.0.11 发布说明（补丁）

日期：2026-10-24
类型：PATCH（App；引擎 V2.2.2 不变）

## 新功能：M4 auto-fused 接入任务启动

- 真实任务默认启用 M4 auto-fused（mock/自检默认关闭以稳定基线）；
- 任务启动参数支持：
  - fused_min_quality、fused_max_wall、fused_max_tokens、fused_require_web、fused_prefer；
  - backend 按约束选 B / serial / fast / web，并映射到 Engine 的 parallel/thinking/web 参数；
- 任务创建响应新增 mode_fusion 字段（mode/reason/scenario/readout）；
- 新增只读接口 GET /api/mode-fusion：返回保留模式、场景表、可选参数与默认值；
- 前端运行栏新增「模式融合」场景下拉（自动/质量墙钟/墙钟≤900s/tokens≤1M/必须联网）；
- 不覆盖用户显式指定的 route/rounds/parallel/thinking/web/profile。

## 变更

- APP_VERSION 2.0.10 → 2.0.11；静态缓存串 ?v=2.0.11-dshlive；
- 质量预测器（dgtf_engine/dgtf_v2/quality_predictor.py）已训练并作为 M4 的保守守卫；
  历史 141 样本，随机切分 R²=0.676 / MAE=0.127，时间切分 R²=-0.26（跨版本漂移），只在模型可用且预测明确时启用。

## 验证

- py_compile 0；
- GET /api/mode-fusion 返回 4 模式 + 5 场景；
- mock 任务启动返回 mode_fusion.mode 且不报错；
- selftest 371/0。
