# EML + DSH 全流程闭环（app V1.1.0）

## 闭环阶段

1. 知识刷新：DeepSeek Search 优先，arXiv API 兜底，入库去重。
2. 引擎跑次：默认 mock；显式 mock=False 才真跑。
3. 消费者/任务：agent_worker.run_once 处理任务队列。
4. 自审提案：DSH 批量提案；已确认提案可进入 autofix。

## 单一闭环入口

| 入口 | stage | 做什么 | 不做什么 |
|---|---|---|---|
| DSH 全流程闭环 | full | 知识刷新 → 引擎跑次（默认 mock）→ 任务/消费者 → 自审提案 | 不自动付费真跑（需显式 mock=false） |

`full` 已包含原轻量提案闭环（任务队列 → 消费者 → 自审提案）。
`stage:"all"` 仅保留为兼容 API / 旧脚本，Agent 面板不再暴露第二个按钮。

## 入口

- UI：Agent 面板“DSH 全流程闭环”（唯一按钮）。
- API：POST /api/agent/auto/start {stage:"full", mock:true, question:"..."}
- 兼容：POST /api/agent/auto/start {stage:"all"}（轻量，仅脚本使用）
- 单独知识：POST /api/agent/knowledge/refresh {queries:[...]}

## 预算保护

- 全流程默认 mock；
- 真跑必须显式 mock=false；
- 建议真跑带 overrides.max_tokens，并在网络不稳时用 --web off。

## 边界

- 知识刷新是外部检索与摘要入库，不会自动改写引擎逻辑；
- 全流程不等于 LLM 权重训练。