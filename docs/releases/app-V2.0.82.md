# App 2.0.82 发布说明（2026-10-30）

> 类型：PATCH（真 bug 修复）。

## 1. 修复

- `dgtf_app/engine_runner.py`：新增 `cli_value()`，把 list/dict 的 opts 规范化为引擎 CLI 字符串；
- `dgtf_app/server.py`：应用 `v2_online` 的 route/rounds 前先规范化；
- 根因：在线策略返回结构化 route=list、rounds=dict，旧 `str(v)` 把 Python repr 传给引擎，
  导致四层入口与圈数全部解析失败、任务静默降质（1 call、答案靠证据拼、质量门 blocked）。

## 2. 验证（真 API）

- 修复前后：llm_calls 1 → **91**；tokens 570 → 699,592；调度日志由全非法 → **0 → 1 → both → all**；
- answer_quality needs_evidence → **verified**；answer_ready False → **True**。

## 3. 兼容性

- 只影响 App→引擎 args 组装；引擎零行为差；默认行为（无 v2_online 结构化 opts）不变。
- 标签：app-V2.0.82。
