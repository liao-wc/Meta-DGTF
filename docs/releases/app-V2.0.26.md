# App V2.0.26 发布说明

发布日期：2026-10-26

上一版：App 2.0.25

## 主题

DSH 全接管闭环加固：守卫版本同步约束、安全回退与提案指标实时化。

## 主要改动

- 守卫任务加入【App 版本同步】强制流程。
- app_release / app_version_check 纳入发布与 App 检查。
- 提案复评实时刷新 audit 提案标题指标。
- 保留 2.0.25 的 DSH 会话/产物依赖、内部事件留痕、守卫回执、120 分钟调度、本地 LLM watchdog、V2 在线策略和安全文件回退。

## 验证

- app_full_check PASS
- app_version_check PASS
- 依赖审计 PASS
- fast_gate 12/12
- V2 tests 51/51（835 checks）
- App selftest 444/0
- guard_policy_check PASS

## 静态缓存

`2.0.26-takeover`
