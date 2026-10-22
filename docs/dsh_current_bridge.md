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
## Agent 面板透明背景恢复（2026-10-22 15:50）

- 按用户要求，Agent 面板恢复为透明页底，与其它 sheet 页原有观感一致；移除上一轮的深色玻璃渐变和 backdrop blur。
- `#view-agent` 与内部 `agent-grid` 均恢复 `background: transparent`。
- 静态版本 v1.5.00；其余信息屏、工具条、知识检索、DSH 动作交接不变。
## 对话内容与运行状态一致（2026-10-22 15:55）

- `/api/dsh/current/messages` 增加 `running`、`inbox_next_turn`、`inbox_next_step`、`updated_at`，供主 DSH 视图判断真实状态。
- 提交到当前 DSH 后，主视图先显示“排队”，随后按真实会话状态显示“运行中/排队/完成”；不再提交后立即标完成。
- 主 DSH 视图每 2.5s 用最近消息同步对话内容；Agent 面板仍不显示实时 DSH 镜像/连接按钮。
- 状态与内容来自同一接口和同一会话，避免 UI 状态与对话内容脱节。
- 静态版本 v1.5.01。

## 一致性验证

- CDP 主视图测试：提交任务后 badge 显示“排队”，视图显示用户任务、DSH 回复和“已排队，等待当前 DSH 轮次完成…”，dsh-mode=true。
- 真实接口：`running=true`，inbox 字段可读，最近消息可读。
- fast_gate 12/0；selftest 371/0；依赖审计 65/0。
## DSH 对话历史库/产物库归档与续聊（2026-10-22 16:10）

- `/api/dsh/current/messages` 同步时自动写：
  - `dgtf_memory/dsh_conversations/dsh-current-<session>.json`：当前 DSH 对话摘要（最近 200 条消息，external=dsh-current，实时 running 状态）。
  - `dgtf_memory/dsh_artifacts/dsh-current-<session>.json`：对话产物（最近对话正文 + 工作区生成/修改文件清单）。
- Agent 面板 DSH 会话库会出现“当前对话”记录，可打开查看历史轮次；继续输入会走 `/api/dsh/current` 续聊。
- DSH 产物库显示当前对话产物，点击后展示对话正文与生成/修改文件；文件链接调用 `/api/fs/file`，文本/图片可点击查看。
- Agent 面板打开时每 3 秒轻量刷新 DSH 会话/产物库，状态实时更新。
- Agent 面板仍不显示实时 DSH 对话镜像/连接按钮。
- 静态版本 v1.5.03。

## 历史库/产物库验收

- 当前会话归档：25 轮、running=true。
- 当前产物：40 个生成/修改文件链接。
- CDP：历史会话打开成功；产物文件链接点击后打开 `_audit_v122_result.json` 内容。
- CDP 续聊：历史会话中再次发送，实际调用 `/api/dsh/current`，主视图 badge 进入“排队/运行中”。
- fast_gate 12/0；selftest 371/0；依赖审计 68/0。
## DSH守护接管自动检查/修复（2026-10-22 16:10）

- 新增持久化守护状态 `/api/dsh/guard`（`dgtf_memory/dsh_guard.json`）：enabled / interval / started_at / last_tick / last_result / checks。
- 开启后 app 内守护线程按 interval（默认 600 秒）巡检；当前 DSH 会话忙碌或队列有任务时跳过本轮，避免叠加 prompt。
- 巡检任务由当前 DSH 对话执行：检查日志/队列/提案/门禁/工作区；只做低风险可验证修复；高风险、删除、密钥、外部服务、git push、账户/ACL 修改一律留人工确认。
- Agent 面板 DSH守护按钮改为读写该状态；不再发送单独“启动守护”prompt。
- 首次触发在 20 秒后；忙碌时每 60 秒重试；idle 后每 interval 执行。
- 当前状态：enabled=true、thread_running=true、interval=600；本轮首次巡检因当前 DSH 运行中跳过，属预期。

## DSH守护验收

- `/api/dsh/guard` GET/POST 正常；页面按钮显示“DSH守护：开”。
- 守护状态：enabled=true、thread_running=true、last_result=busy 跳过巡检。
- fast_gate 12/0；selftest 371/0；依赖审计 69/0。
- 静态版本 v1.5.04。
## 连贯性适配（2026-10-22 16:35，v1.5.05）

- DSH守护开启不再跳转首屏：只创建/切换一个逻辑 DSH 历史会话（silent），守护巡检后续写入该会话；历史库可打开查看状态与内容。
- 逻辑会话隔离：`dgtf_memory/dsh_active_conversation.json` 记录当前会话 id 与 start_seq；同一条主输入续聊沿用当前逻辑会话，面板动作/“新对话”创建新逻辑会话；历史记录按 start_seq 分段保留并可续聊。
- 主 DSH 视图 1 秒同步并自动滚动；Agent 面板库刷新 1.2 秒。
- 主输入在 DSH 排队/运行时再次发送使用 `mode=steer` 插话；首次发送仍为 queue。
- DSH 视图新增“终止本轮”按钮，调用 `/api/dsh/current/cancel`（session/cancel）；新增“新对话”按钮创建独立逻辑会话。
- 移除左上角运行日志诊断按钮；其诊断 API/数据面保留但不暴露入口。
- V2 挡位 `#pareto-prefer` 悬停/聚焦/选项保持透明背景。
- Agent 面板新增“DSH 对话按钮”：深度思考 / 智能搜索 / 演练模式 / DSH Agent，与首屏按钮双向同步并可调节。
- 静态版本 v1.5.05。

## 连贯性验收

- CDP 插话测试：第一次 mode=queue，第二次 mode=steer；主视图 badge=排队，内容含用户/DSH 文本，终止按钮可见。
- 逻辑会话：当前存在 2 个 dsh-current 会话（守护会话 + 原会话）；active 指向守护会话；旧会话状态收口不显示运行中。
- 页面：无 diag-btn；dsh-stop-btn/dsh-newchat-btn/cfg-thinking/cfg-web/cfg-mock/cfg-dsh 均存在。
- 配置映射：点击 cfg-thinking 后首屏 pill-thinking 为 on；点击 cfg-mock 后 mock.checked=true。
- fast_gate 12/0；selftest 371/0；依赖审计 73/0；HTTP 200。
## 守护巡检低风险修复（2026-10-22 16:40）

- 巡检发现 err 日志中的 `ConnectionResetError` 来自浏览器/无头客户端提前断开连接，发生在 JSON 响应写回阶段。
- 低风险修复：`_json()` 捕获 `ConnectionResetError`/`BrokenPipeError` 并静默关闭连接，避免此类正常断连继续污染 err 日志；不吞业务异常。
- 历史旧 err 记录保留，未做删除/裁剪。
- fast_gate 12/0；selftest 371/0；依赖审计 73/0；HTTP 200。
## 守护巡检二次低风险修复（2026-10-22 16:45）

- 巡检发现 err 日志出现子进程 reader 线程 `UnicodeDecodeError`：Windows 本地命令输出不是 UTF-8 时，`text=True` 子进程读取崩溃。
- 修复 `icacls`、`openssl`、`git rev-parse/log` 子进程读取：显式 `encoding="utf-8", errors="replace"`，避免本地化输出击穿读取线程。
- 修复后重启，err 日志 0 行；HTTP 200；DSH守护仍 enabled=true/thread_running=true。
- fast_gate 12/0；selftest 371/0；依赖审计 73/0。
## DSH 配置键映射（2026-10-22 16:50，v1.5.06）

- Agent 面板的四个“对话按钮”映射改为前一轮 DSH 配置键：`dsh-model`、`dsh-effort`、`dsh-network`、`dsh-perm`。
- 可选项对应 Harness 标准配置：Model（Flash/Reasoner）、Reasoning effort（Provider default / Low / Medium / High / Max）、联网（关闭/授权公开网站）、权限（只读/读写/完全/自动审查）。
- 新增 `GET/POST /api/dsh/config`，配置持久化到 `dgtf_memory/dsh_config.json`；Agent 面板打开/展开 DSH 配置时读取并保存。
- DSH 配置按钮在 Agent 工具条中，默认折叠；与旧 DSH配置键一致。
- 已验证 UI：配置框展开、选项数量 model/effort/network/perm = 2/5/2/4，保存提示“配置已保存：deepseek-flash / default”。
- fast_gate 12/0；selftest 371/0；依赖审计 73/0。
## 发送/终止按钮与原新对话按钮适配（2026-10-22 17:00，v1.5.07）

- 移除 DSH 视图内额外的“终止本轮”和“新对话”按钮。
- 终止复用首屏发送按钮：DSH 排队/运行中且输入框为空时，发送按钮变为终止图标；点击调用 `/api/dsh/current/cancel`。
- 排队/运行中若输入框有文字，按钮恢复发送形态，点击发送 `mode=steer` 插话；两种行为按输入内容动态切换。
- 新对话恢复使用首屏左上角原有 `#newchat-btn`；DSH 模式下点击它创建新的独立逻辑历史会话，不再另设按钮。
- 配置键仍为 `dsh-model`、`dsh-effort`、`dsh-network`、`dsh-perm`；DSH配置按钮折叠可调节。
- 静态版本 v1.5.07。

## 按钮一致性验收

- 页面无 dsh-stop-btn、无 dsh-newchat-btn。
- 首屏 run-btn 在 DSH 忙且空输入时使用 stop 形态；输入文字后恢复 send 形态。
- fast_gate 12/0；selftest 371/0；依赖审计 74/0。
