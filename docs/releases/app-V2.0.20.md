# App V2.0.20 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 新机制：已验证答案缓存

- 同一问题、同一 web/parallel 条件下，若 6 小时内有 answer_ready=true 且 answer_quality=verified 的 packed，直接复用产物，不再启动引擎；
- 命中时创建“缓存任务”（status=done，cached_from 指向来源），响应 cache_hit=true；
- 默认 use_cache=true；可 API 传 use_cache=false 关闭；
- 只缓存 verified 结果，needs_evidence/unverified 不复用，避免缓存低质量答案；
- 项目背景前缀参与问题匹配（不会把不同背景的答案混用）。

## 预期效果

- 重复问题从约 5 分钟/数十万 tokens 降到 **秒级、零 LLM 调用**；
- 适用于反复追问同一问题的场景；结果带 cached_from 可审计。

## 验证

- py_compile 0；App 2.0.20 重启；
- 同题 verified web 任务二次请求 cache_hit=true、无引擎进程；
- 未命中任务正常启动引擎。
