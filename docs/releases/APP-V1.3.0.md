# 元DGTF app V1.3.0 发布说明

日期：2026-10-21
类型：minor

## 新增

- RAG v2：来源编号 [S#]/[K#]/[I#]、每层索引 layer_contexts、上下文追溯；
- 导入文件与本地资料库融合；
- 隐私策略：外部上下文开关、敏感过滤、脱敏、长度上限；
- /api/project/context/history；
- /api/security/context-policy。

## 实验

- Qwen2.5-1.5B LoRA 可在 6GB 训练，但留出 route/rounds 不如 0.5B，默认不切换；
- 0.5B adapter 已可 merge 为自包含模型（约 988MB）。

## 边界

- 未引入神经 embedding 模型；
- 未强制引擎最终答案逐条引用。