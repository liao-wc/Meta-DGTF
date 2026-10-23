# 元DGTF app V1.1.1 发布说明

日期：2026-10-21
类型：patch（DSH Agent 自修复）
基线：V1.1.0

## 修复

- _auto_engine_run 原先局部 import engine_runner，会把同一模块加载成第二个实例；
  _tasks 等运行态与 API 侧不共享，全流程闭环可能查不到刚启动的任务。
- 改用模块级 runner；运行态恢复共享。

## 来源

- DSH headless session：session-a8745322-0bf7-4362-94fd-7a980f313b4e
- 子智能体：core-gate（本会话团队 DSH bridge）

## 验证

- fast_gate 12/0
- app selftest 371/0
- 集成探针 67/0
- 实测 _auto_engine_run mock 任务 done，且同一模块 runner.get_task(id) 可见（运行态共享）

## 边界

- 只改 dgtf_app/server.py 一处；引擎/模型/其他源码未动。