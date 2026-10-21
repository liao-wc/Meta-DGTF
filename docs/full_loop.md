# EML + DSH 全流程闭环（app V1.1.0）

## 闭环阶段

1. 知识刷新：DeepSeek Search 优先，arXiv API 兜底，入库去重。
2. 引擎跑次：默认 mock；显式 mock=False 才真跑。
3. 消费者/任务：agent_worker.run_once 处理任务队列。
4. 自审提案：DSH 批量提案；已确认提案可进入 autofix。

## 入口

- UI：Agent 面板“全流程闭环”。
- API：POST /api/agent/auto/start {stage:"full", mock:true, question:"..."}
- 单独知识：POST /api/agent/knowledge/refresh {queries:[...]}

## 预算保护

- 全流程默认 mock；
- 真跑必须显式 mock=false；
- 建议真跑带 overrides.max_tokens，并在网络不稳时用 --web off。

## 边界

- 知识刷新是外部检索与摘要入库，不会自动改写引擎逻辑；
- 全流程不等于 LLM 权重训练。