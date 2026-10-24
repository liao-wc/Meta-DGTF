# App V2.0.3 发布说明（补丁）

日期：2026-10-24
类型：PATCH（App；引擎 V2.2.2）

## 修复/优化

1. **/api/health 读数缓存**：2s TTL 缓存（import 探测 + git commit + 参数展平 + daemon 状态
   原来每次重算，实测 p50≈475ms）⇒ 高频轮询/启动检查从 ~475ms 降到 **~16–18ms**（冷启动仍 ~900ms）。
2. **联网状态显示 DeepSeek 官方**：工作台环境信息「联网」改为显示官方后端（复用 DGTF_API_KEY），
   不再显示 Tavily。
3. **引擎入口切 V2.2.2**：默认联网检索/抓取走 DeepSeek 官方；引擎引用同步。
4. 缓存串升 `?v=2.0.3-dshlive`（前端 app.js 变更）。

## 验证

- py_compile 0、node --check 0；App 重启后 health ok=true、app=2.0.3、engine=2.2.2。
- health 端点重复调用实测：冷 ~900ms，缓存命中 ~16–18ms（优化前 450–550ms）。
- App selftest 371/0；DSH 实时视图/独立会话窗口保持正常。

## 边界

- 缓存只影响 /api/health（最多滞后 2s），不影响任务/引擎/会话数据。
- 本地模型与引擎逻辑未改。
