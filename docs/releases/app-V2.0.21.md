# App V2.0.21 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 新机制：同题运行任务去重

- 同一问题、同 web/parallel/rounds/config/behavior_fusion 的任务已在 running/queued 时，
  新请求直接复用现有任务，返回 dedup_hit=true，不再启动第二个引擎子进程；
- 避免重复提交造成双倍 LLM 费用与并发争用；
- 与已验证答案缓存互补：运行中去重、完成后缓存；
- 响应新增 dedup_hit；缓存/普通任务响应统一为 false。

## 验证

- py_compile 0；App 2.0.21 重启；
- 同一问题连续两次 POST：第二次 dedup_hit=true 且 id 相同；
- 取消首个任务后无残留。
