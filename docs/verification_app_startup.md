# App 启动与全链路稳定性验证

日期：2026-10-24

## 根因

scripts/*.ps1 存为 UTF-8 无 BOM。Windows PowerShell 5 按 GBK/ANSI 读取中文，
在 Format-TokenBrief 等中文行直接 ParserError，start_app.cmd 双击立即失败。
后来 edit 工具改写脚本时再次丢 BOM，复现了“APP 启动不了”。

## 修复

- scripts/*.ps1 全部转为 UTF-8 with BOM。
- start_app.ps1 默认 HealthTimeoutSec=120。
- 已有 DGTF app 但 health 失败时：自动停止并重新启动，不再只报错。
- server.py 的 BGE embedding 初始化移到后台线程，避免冷启动阻塞 HTTP 健康检查。
- engine_runner.py 启动引擎子进程加 CREATE_NO_WINDOW，消除任务黑窗弹窗。

## 实测

- PowerShell 5 解析 start_app.ps1：PARSE_OK。
- 已有 app 在跑时执行 start_app.ps1 -Port 8765 -NoBrowser：
  DGTF app 已在运行 pid=13304，健康检查通过 HTTP 200，exit 0，6.3s。
- 停止后重新启动：app 进程启动，8765 监听，health 200。
- 健康：app 2.0.0 / engine Meta-DGTF-V2.2.0.py / engine 2.2.0。


## App 全链路任务实测

- 任务 20261024_082813_b7348f：status=done，exit_code=0。
- 87 calls / 733,605 tokens；answer_ready=true；answer_quality=verified；process_ready=true。
- 产物 20261024_083648_Python中len函数的作用是什.packed.json。
- 冷启动 stop→hidden start：6.8s health 200；启动器不再依赖 BGE 冷加载完成。
