# 元DGTF app V1.2.3 发布说明

日期：2026-10-21
类型：patch

## 新增

- app 本地导入文件（dgtf_app/anchors/external_anchor.json）纳入 RAG；
- 项目上下文注入 = 项目文档 + agent_knowledge 资料库 + 本地上传资料；
- 导入文件按问题关键词取 top-3 分块，随任务默认注入（真实任务）；
- /api/project/context 返回 imported_sources。

## 验证

- 实测导入 rag_probe.txt 后，context.imported_sources 包含该文件；
- 探针新增 imported file RAG 检查并自动清理。