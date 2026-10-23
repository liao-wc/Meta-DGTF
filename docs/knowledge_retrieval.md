# 知识检索（app V1.4.1）

## 入口合并

- 原“联网”和“刷新技术知识”合并为 Agent 面板单一 **知识检索** 按钮；
- 知识查询框 + “查询”按钮用于自由查询；
- 两者都调用 `/api/agent/knowledge/agent-search`，生成同一种 DSH 知识检索会话。

## 检索质量

- 官方/权威域名优先（DeepSeek、arXiv、Semantic Scholar、OpenReview、ACL、NeurIPS/ICML、OpenAI/Microsoft/NVIDIA 等）；
- 时效（2025/2026）、可抓取正文、摘要充分、相关命中、authority/confidence 加权；
- 低价值源（pypi/npm/medium/reddit/x/youtube/facebook）降权并排除；
- 无网络结果时回退本地知识库按查询命中，不返回无关条目；
- 选中条目写 `agent_knowledge_patch.md` 并入库去重。

## DSH 会话

- 每次检索写一条 `dgtf_memory/dsh_conversations/dshknow-*.json`；
- 会话事件包含：检索查询、爬取候选、每条质量分/依据、knowledge.select、入库结果；
- 前端自动打开该 DSH 会话，可回看/续聊/历史；
- 当前是由知识代理生成的过程记录，不是独立 DSH CLI 进程。

## 本地资料库

- 导入文件解析/分块为 anchors 证据，参与 BGE+BM25 RAG；
- 原文留档 anchors/_raw；不训练、不自动外发、可删除；
- 与“技术知识库”分开：技术知识库是检索筛选后的条目。