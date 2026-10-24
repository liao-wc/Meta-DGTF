# App V2.0.18 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 变更：模式融合全自动

按要求移除前端“模式融合”场景选择按钮，M4 恢复全自动：

- 默认无约束：按 quality 优先选 B；需要墙钟/tokens/联网时由引擎内部/API 参数决定；
- 前端不再发送 fused_* 场景参数；
- 后端仍保留 fused_min_quality / fused_max_wall / fused_max_tokens / fused_require_web / fused_prefer 作为 API opt-in；
- 任务响应仍回显 mode_fusion.mode/reason/readout/quality_prediction。

## 验证

- py_compile 0；App 2.0.18 重启；
- 默认任务 cmd：--parallel B / --web off / --behavior-fusion off / --rounds 0:1...；
- 前端已无 fused-scenario 控件。
