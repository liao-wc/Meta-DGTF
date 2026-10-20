# DSH Agent 自动修复闭环验收记录

- 日期：2026-10-20
- 范围：提案 → 确认/自动代理 → 改源码/文件 → fast_gate → 只提交本次变更
- 运行：http://127.0.0.1:8765

## 场景 1：干净文件新增

- 提案 prop-1792491523732 -> dsh_auto -> applied
- 结果：仅提交 `docs/dsh_autorepair_probe.md`（commit 46be974）
- fast_gate：10/0

## 场景 2：已脏文件再修改

- 先预置脏内容，再让 DSH Agent 修改同一文件
- 提案 prop-1792493278201 -> applied
- 结果：`changed` 仅 `docs/dsh_autorepair_probe.md`（commit e81157a）
- 运行记录 `dgtf_memory/agent_daemon.log`、`agent_patch_audit.jsonl` 被提交范围过滤，未进入提交
- 该提案后经回退接口撤销：status=`rolled_back`，revert commit effc4fc

## 验证过的安全边界

- read-only：写入返回 BLOCKED，文件不存在
- workspace-write：写入成功，内容 OK
- danger-full-access：未做破坏性验证，保持默认关闭

## 结论

- 自动修复只提交源码/文档，运行记录不进入提交。
- 修复提案库会记录 pending / applied / failed / rolled_back 状态。
- applied 提案支持“回退并撤销修复”（git revert 对应提交）。
