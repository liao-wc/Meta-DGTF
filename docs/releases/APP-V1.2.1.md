# 元DGTF app V1.2.1 发布说明

日期：2026-10-21
类型：patch

## 变更

- 元DGTF 项目背景改为内置默认注入：真实任务自动前置权威背景+本地资料库；
- 保留 GET /api/project/context 与 opts.project_context 覆盖能力；
- 与本地资料库（agent_knowledge）融合：检索相关标题/摘要/URL；
- 移除前端“项目上下文”按钮，不再需要每次手动选择；
- mock/自检默认不注入，保持基线稳定；
- 文档读取按 mtime 缓存，敏感片段过滤，长度上限默认 7000 字符。

## 验证

- app selftest 371/0；
- 集成探针 74/0；
- /api/project/context 含 修行/研究/对撞/元、EML、DSH；
- 真实任务默认 project_context=true，mock 默认 false。