# App V2.0.25 发布说明

发布日期：2026-10-26

上一版：App 2.0.24

## 主题

DSH 会话-产物依赖、内部事件留痕、守卫调度与完成回执、文件安全回退、版本发布自动化。

## 主要改动

- DSH 会话按任务入口拆分，产物关联具体任务（task_id/task_title）。
- 内部事件写入 conversation/artifact，空占位会话不生成新空产物。
- 守卫完整模板、dispatch_id、完成回执、pending 保护、完整性预检。
- 120 分钟调度改为 last_dispatch_at + interval；运行中到点排队。
- 本地 LLM watchdog 恢复，V2 在线策略恢复任务闭环。
- V2 自动策略校准门禁恢复；调度策略恢复四层 route / rounds=2 / 空模板。
- safe_file_ops / file_integrity_check / app_version_check / app_release。
- 侧边栏北斗星链恢复原布局，窄侧栏保留星链视觉。

## 验证

- app_full_check PASS
- 关键文件完整性 bad=0
- App 版本一致性 PASS
- fast_gate 12/12
- V2 tests 51/51（835 checks）
- App selftest 444/0
- guard_policy_check PASS

## 静态缓存

`2.0.25-dshguard`
