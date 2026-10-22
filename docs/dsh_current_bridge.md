# DSH 本对话桥接

## 目标

元DGTF app 的 DSH 本对话输入框把任务直接排队给当前 DeepSeek Harness 会话；当前会话有项目权限时可直接修改元DGTF项目。

## 入口

- Agent 面板：DSH Agent 配置下方新增“DSH 本对话”输入框和“交给本对话”按钮。
- 位置：index.html 的 dsh-current-box。

## 数据流

1. app POST /api/dsh/current {task}
2. 读取本机 DSH credentials，生成签名 cookie（只在后端进程内使用）。
3. POST http://127.0.0.1:56632/api/session/list，选择 DSH_SESSION_ID 或当前 cwd 的最近会话。
4. POST http://127.0.0.1:56632/api/session/prompt，mode=queue。
5. 当前 DSH 对话接收任务并执行。

## 行为与安全

- dry_run=true 只解析凭据/会话，不发送。
- 任务自动加前缀：直接执行、可修改项目、完成后给中文摘要和验证结果。
- 不另起 headless DSH；原 /api/dsh/agent 保留给需要事件流的历史功能。
- /api/dsh/current 仍受 app 访问口令、Host/Origin/CSRF 保护；DSH cookie 不返回浏览器。
- 当前会话的权限档位决定项目修改能力，桥接不提升权限。

## 验证

- 会话解析：session-bdf9ff8b...
- dry-run：accepted=false，返回当前会话 id。
- live：accepted=true，任务进入当前对话队列。
- 前端静态：dsh-current-input、/api/dsh/current、v1.4.89。
- 回归：selftest 371/0，fast_gate 12/0，依赖审计 59/0。