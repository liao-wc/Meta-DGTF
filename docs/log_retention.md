# 日志与运行态保留策略

## 保留

- `outputs/`：真实产物、packed、run 记录，永久保留（人工归档除外）。
- `dgtf_memory/`：任务、提案、知识、调度策略、守护状态，保留并纳入备份。
- `reports/`：质量重放、真实跑验收、审计报告，保留。
- `dgtf_app/runs/`：每个任务日志，建议保留 30 天。

## 可清理

- `_audit_tmp/`：无头浏览器 profile / 临时审计，生成型，可清空。
- `smoke_outputs/`：冒烟产物，生成型，可清空。
- `__pycache__/`：可清空。
- `_app_out_*.log*` / `_app_err_*.log*`：启动器日志，保留最近 7 天；含旧口令的已清洗。
- 顶层 `*.log`：运行证据，按需保留；`.gitignore` 已排除。

## 禁止

- 不删除 `outputs/`、`dgtf_memory/`、`.env`、TLS 私钥、模型文件。
- 不把日志/运行态提交到 git。

## 当前执行

- 2026-10-22 已清理 `_audit_tmp` 与 `smoke_outputs` 生成型内容，释放约 3.5GB。
- 未删除任何真实产物或运行记录。
