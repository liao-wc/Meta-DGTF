# 元DGTF app V1.4.0 发布说明

日期：2026-10-21
类型：minor

## 新增

- 神经 RAG v2：本地 BGE-small-zh（512 维）+ BM25 混合检索，引用 [S#]/[K#]/[I#]/[E#]、分层索引、上下文追溯；
- DSH 会话：当前/历史会话、实时事件、点击续聊、同一会话多轮、陈旧 running 标中断、按会话取消；
- DSH 读写：workspace-write 内读取/修改项目，禁止 danger-full-access、.env/密钥、第三方上传；
- 产物命名：项目上下文不再污染引擎产物文件名（runner 后处理）；
- 质量替代分：/api/quality/<task>，覆盖×回答率×收尾完整度−flags；
- DeepSeek 血统：DeepSeek-R1-Distill-Qwen-1.5B LoRA，route 0.214 / rounds MAE 1.286；新增 qwen05b/qwen15b/deepseek15b/hybrid 底座；
- V2 调度只保留挡位选择，切换自动评估帕累托/最佳模板/UCB 并写最优；
- 首屏输入框/欢迎语整体上移；
- 隐私：DGTF_CONTEXT_EXTERNAL=0 仅发 brief；本地 embedding；敏感脱敏。

## 验证

- 依赖链审计 40/0；
- app selftest 371/0；
- 集成探针 78/0；
- DSH 多轮/历史/写读实测；
- 2M 四层真跑 179 calls / 1.49M tokens / 四层自然收尾。

## 边界

- 默认 LLM 仍是 0.5B（route 最好）；DeepSeek/hybrid 为可选；
- DSH 独立席位由 core-gate 代持；
- BGE 索引 136 chunks，需重建脚本更新。