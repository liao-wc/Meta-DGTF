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
- 不另起 headless DSH；/api/dsh/agent 和 /api/dsh/agent/stream 已改为转交当前对话（保留 URL 兼容，但不再拉起 headless 进程）。
- GET /api/dsh/current/messages 读取当前会话最近消息，供 app 实时镜像面板轮询。
- 首屏输入框在 DSH 模式（DSH Agent 按钮）下直接调用 /api/dsh/current，不再创建本地引擎任务。
- 实时镜像：Agent 面板 #dsh-current-log 每 2.5s 同步当前 DSH 对话消息；主 DSH 视图同步显示。
- /api/dsh/current 仍受 app 访问口令、Host/Origin/CSRF 保护；DSH cookie 不返回浏览器。
- 当前会话的权限档位决定项目修改能力，桥接不提升权限。

## 验证

- 会话解析：session-bdf9ff8b...
- dry-run：accepted=false，返回当前会话 id。
- live：accepted=true，任务进入当前对话队列。
- 前端静态：dsh-current-input、dsh-current-log、/api/dsh/current、v1.4.92。
- 浏览器镜像验收：headless Edge 打开 ?dsh=1，DOM 中 dsh-current-log 含当前对话消息；v1.4.92。
- 回归：selftest 371/0，fast_gate 12/0，依赖审计 59/0。
## DSH 接管 UI 合并（2026-10-22 15:xx）

- 原“常驻守护”按钮改为“DSH守护”：开关不再调用本地 autopilot，而是把启动/停止任务交给当前 DSH 对话。
- 原“DSH 全流程闭环”与“自动修复提案”合并为一个按钮：“DSH 接管：闭环 + 修复”。
- Agent 面板移除：DSH 本对话输入框、知识检索输入框、提交用户任务对话框；任务统一从首屏输入框进入当前 DSH。
- Agent 面板执行类按钮（闭环/修复/知识检索/学习刷新/发起提案/自主审视/自学习/库去重）统一调用 dshDispatchAction：先 POST /api/dsh/current，再切换对话同步视图。
- 运行信息屏（最近动作）只保留最新一条，新动作自动覆盖旧行，不再显示五条历史。
- 静态版本 v1.4.95；DSH 对话镜像仍由 dsh-current-log 轮询显示。
- 提案“补充方案”改为交给当前 DSH 对话；“不修复”去掉 prompt，使用固定原因并保留提案历史。

## 浏览器级验收

- headless Edge DOM：Agent 面板不存在 agent-kn-q、agent-kn-search、prop-autofix、agent-overlay、dsh-current-input、dsh-current-send。
- CDP 点击 agent-auto / agent-autopilot-btn / agent-knowledge-btn / agent-kn-dedupe / ap-learn：只产生 /api/dsh/current 调用，没有 /api/agent/auto*、/api/agent/autopilot、/api/agent/knowledge。
- v1.4.95 最终 CDP：上述 5 个动作全部走 /api/dsh/current；动作日志行数 1；DSH守护：开；无被移除的输入/弹窗节点。
- 动作日志行数为 1；DSH守护按钮显示“DSH守护：开”；执行后进入 dsh-mode。
## Agent 面板清理与实时信息屏（2026-10-22 15:30）

- 移除旧 DSH Agent 配置条：`dsh-config-btn`、`dsh-config-box`、档位/模型/联网/权限选择。
- 移除隐藏的 `ap-learn/ap-spawn/ap-scan/ap-selflearn` 残留按键及其监听。
- 工具条只保留：刷新全部库、DSH 接管闭环+修复、DSH守护、知识检索（本对话）、库去重。
- 新增“实时信息屏”单行条：所有动作、库读取、DSH 新消息、错误都经 `agentLogAction` 汇总；新事件自动覆盖旧行。
- 库读取只在计数/错误签名变化时写入信息屏，避免轮询制造重复刷屏。
- Agent 面板采用深色玻璃底、信息屏脉冲点、紧凑工具条；空 DSH 镜像不再显示空黑条。
- 静态版本 v1.4.97。

## 本轮验收

- 页面无 dsh-config / ap-* / agent-kn-q / agent-overlay 等残留节点。
- CDP 点击 DSH 接管按钮：只调用 /api/dsh/current 与 /api/dsh/current/messages；信息屏单行显示“DSH 接管：闭环 + 修复 · 已交给 DSH 本对话”，日志行数 1。
- `/api/dsh/current` live：返回 `mode=current-session`、`accepted=true`，任务进入当前会话队列。
- fast_gate 12/0；selftest 371/0；依赖审计 61/0。
## 面板镜像移除与知识检索恢复（2026-10-22 15:40）

- 移除 Agent 面板中的 DSH 本对话/实时镜像与连接 DSH：`dsh-current-box`、`dsh-current-log`、`dsh-current-connect` 均不再存在，也不再轮询 `/api/dsh/current/messages`。
- 知识检索恢复为原有行为：`agent-kn-q` + `查询` + `#agent-kn-dedupe`，走 `/api/agent/knowledge/agent-search` 与 `/api/agent/knowledge/dedupe`；不强制交给 DSH 本对话。
- DSH 接管类按钮（闭环/修复、DSH守护、学习刷新等）仍通过 `/api/dsh/current` 进入当前 DSH 对话。
- 静态版本 v1.4.98。

## 本轮验证

- 页面：无 dsh-current-box/log/connect；知识检索输入与查询恢复；实时信息屏保留单行。
- CDP：点击 DSH 接管按钮只调用 `/api/dsh/current`；点击知识检索调用 `/api/agent/knowledge/agent-search`；没有镜像消息轮询。
- DSH 本对话 live：`mode=current-session`、`accepted=true`；此前已实际执行 bridge-ok 任务。
- 自我反馈修复迭代：audit 发现 `dsh network configurable hooks` 依赖旧 UI 选择器，DSH 修复审计断言后重跑；fast_gate 12/0、selftest 371/0、audit 62/0。
- 知识 API 可读 69 条；本地 autopilot 关闭；app HTTP 200。
## 自我反馈学习修复闭环验证（2026-10-22 15:45）

- “DSH 接管：闭环 + 修复”任务提示已明确为：读取状态 → 自我反馈定位缺口 → 学习/检索知识 → 安全修复 → fast_gate/selftest/依赖审计验证 → 失败继续迭代 → 高风险留人工。
- 本轮 DSH 实际完成一次自我反馈修复迭代：移除面板实时镜像/恢复知识检索后，依赖审计因旧网络配置选择器失败；DSH 修复审计断言并重跑，最终 fast_gate 12/0、selftest 371/0、audit 64/0。
- 当前 DSH 会话仍独立留存：/api/dsh/chats 43 条，当前会话可读 `/api/dsh/current/messages`；本次只移除面板镜像，不改会话归档。
- 知识检索恢复原链路 `/api/agent/knowledge/agent-search` 与去重；知识 API 可读 69 条。
- 静态版本 v1.4.99；页面无 dsh-current-box/log/connect；实时信息屏保留。
