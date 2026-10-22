# 并行改进验收报告

日期：2026-10-22
范围：任务重试、排队位置、启动器、回归

## 结果总览

| 项 | 结果 | 证据 |
|---|---|---|
| 后端 retry API | PASS | 队友独立 8767 测试 21/0；Lead 生产 8765 实测 retry 200 / 不存在 404 |
| queued queue_pos | PASS（后端/纯函数） | 后端单测顺序 1..n；前端 queueBadgeText 单测 8/8 |
| 前端重试按钮 | PASS（静态/语法） | node --check；index.html #rl-retry；app.js retryTask |
| 静态版本 | PASS | index.html style/app.js 均为 v=1.4.87 |
| 一键启动 8766 | PASS | start_app.ps1 启动成功 HTTP 200，随后 stop 释放端口 |
| 稳定 token | PASS | dgtf_memory/.access_token 复用；8766 启动使用同一 token |
| -NewToken | 未实测 | 未执行轮换（避免影响当前 8765） |
| app selftest | PASS | 371 / 0（新后端已重启后） |
| fast_gate | PASS | 12 / 0 |
| 依赖链审计 | PASS | 58 / 0（修复服务账户遗留 ACL 后） |
| 浏览器真实点击重试 | 未实测 | 当前会话没有完成浏览器点击级自动化；需人工或后续 Playwright |

## 生产实例

- 8765 当前用户运行，HTTPS + 稳定 token；健康检查 HTTP 200，app version 1.4.1。
- 生产进程在集成过程中重启一次以加载后端/静态改动。
- 未使用 DGTFApp 服务账户/计划任务。

## 关键修复

1. 服务账户遗留的 dgtf_memory/playbook.jsonl、auto_jobs.json ACL 导致：
   - eml_memory = 0
   - job_persistence Permission denied
   已用管理员 ACL 修复脚本重置 owner/ACL；一致性恢复 58/0。
2. 启动器 -File 调用在 Windows PowerShell 5 下失败，.cmd 入口改用 -Command &；脚本加 UTF-8 BOM。
3. 启动器新增稳定 token 复用、HTTPS 健康检查、失败日志、-Stop/-Restart/-NewToken/-NoBrowser。

## 提交

- 1826ae2 feat(app): 任务重试/排队位置/一键启动并行改进

## 边界

- 后端 retry 409（running/queued 不可重试）由后端队友独立测试覆盖，Lead 浏览器端未重复构造 running 任务再验。
- 前端真实点击未自动化；静态与纯函数已验证。
- 当前运行实例的旧历史任务在重启后不保留内存态，属既有设计。
