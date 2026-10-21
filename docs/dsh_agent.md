# DSH Agent 会话与安全（app V1.4.0）

## 会话模型

- 一次 DSH 对话 = 一个 `conversation_id`，内含多轮 `turns`；
- 同一会话继续提问：POST /api/dsh/chat 带同一 conversation_id；
- 多轮只算一条历史会话；
- 历史/当前：GET /api/dsh/chats、GET /api/dsh/chat/<id>；
- 服务重启后无 worker 的 queued/running 标 `stale`（前端显示“中断”），不再误报运行中；
- 按会话取消：POST /api/dsh/chat/<id>/cancel 只终止该会话进程，不再全局 taskkill。

## 前端

- DSH 会话顶部显示当前会话/轮数/状态；
- “历史会话”面板列出 id、轮数、完成/中断、最近任务；
- 点击历史项恢复；同一对话继续追加轮次；
- 深链：`?dsh=1&dsh_conv=<id>`；历史面板：`&dsh_history=1`。

## 能力与安全

- workspace-write：可读取项目、outputs、docs、dgtf_memory、app 导入文件；可修改项目文件；
- 修改源码后要求运行 fast_gate；不自动 git commit/push；
- 禁止 danger-full-access（API 返回安全错误）；
- 禁止 .env/密钥/凭据/.git 内部文件；禁止联网搜索/抓取/第三方上传；仅 DeepSeek API；
- 独立席位：core-gate 代持 task-11；
- 实测：读取 README 版本、写入 docs/dsh_capability_probe.md 后清理，fast_gate 12/0。

## 接口

- GET /api/dsh/chats
- GET /api/dsh/chat/<cid>
- POST /api/dsh/chat
- POST /api/dsh/chat/<cid>/cancel
- GET /api/dsh/sessions、/api/dsh/artifacts
- GET /api/security/context-policy