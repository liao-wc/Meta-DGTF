# RAG v2（app V1.3.0）

## 数据源

- 项目文档：README / 映射 / 闭环 / LLM / 调度模型 / 报告；
- 本地资料库：dgtf_memory/agent_knowledge.jsonl；
- app 本地上传：dgtf_app/anchors/external_anchor.json。

## 检索与重排

- 文档按 mtime/size 缓存；
- 关键词/短语召回 → BM25 重排（k1=1.2，b=0.75）；
- 本地 BGE-small-zh-v1.5（512 维）语义召回，与 BM25 融合；
- 查询走 127.0.0.1:8771 常驻 embedding 服务，失败回退 BM25；
- 每类取 top-k；导入文件取 top-3；
- 分源编号：[S#] 文档、[K#] 资料库、[I#] 导入文件。

## 每层检索

- /api/project/context 返回 layer_contexts：0/1/both/all；
- 每层按对应关键词（展开/证据/裁决/闭环）取相关片段；
- 当前在 app 层提供索引，引擎仍接收单一上下文。

## 引用与追溯

- citations：id/kind/source/url（S/K/I/E 四类）；
- BGE 索引：dgtf_memory/rag_index.json（136 chunks，512 维）；
- 重建：`D:\Meta-DGTF-道生三阶模型\local_model\envs\dgtf_llm_env\Scripts\python.exe build_rag_index.py`；
- /api/tasks 创建时写 dgtf_memory/context_traces.jsonl；
- /api/project/context/history 查询最近 50 次。

## 隐私

- DGTF_CONTEXT_EXTERNAL=1 默认允许外部上下文；=0 只注入最小 brief，不外发本地资料/导入文件；
- 敏感片段过滤（api_key/secret/token/sk- 等）；
- 文本脱敏（key/Bearer/邮箱）；
- 长度上限 DGTF_PROJECT_CONTEXT_MAX_CHARS=7000。

## 当前边界

- 已使用本地神经 embedding；仍是单路 top-k 融合，未做 cross-encoder rerank；
- 分层检索结果只是 app 侧索引，未做到引擎每层独立二次检索；
- 引用编号已注入上下文，最终答案逐条引用尚未强制校验。