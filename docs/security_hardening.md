# 本地 Web 应用安全加固

## 已启用
- Host 白名单：默认 127.0.0.1 / localhost / ::1；--lan 时只加入本机网卡地址。
- Origin/Referer 校验：浏览器跨站写请求必须来自白名单 Host。
- CSRF：静态首页下发 dgtf_csrf Cookie，所有写请求带 X-CSRF-Token；无浏览器 Origin 的本地 CLI 兼容；令牌持久化到 dgtf_memory/.csrf_token，app 重启不失效；前端在 403 时自动取新令牌重试一次。
- 安全响应头：CSP（script-src self）、X-Frame-Options DENY、nosniff、Referrer-Policy、Permissions-Policy、CORP。
- 口令 Cookie 改为 HttpOnly + SameSite=Strict。
- DSH Agent 敏感路径运行时拦截：tool_call 事件命中 .env/.credentials/dsh_conversations 等立即终止本轮；输出中的已知 API key 值脱敏。
- 自动修复安全门槛：提案阶段检查敏感词/敏感路径/危险命令（密钥、token、.env、server.py、curl/wget、powershell -enc、reg/schtasks、外链等）；提交前检查新增代码的密钥、eval/exec、subprocess、网络请求、注册表/提权、敏感文件；命中不提交。
- 提案驱动学习：修复前最多等 12 秒检索相关知识，超时/空结果回退本地知识库，保证不阻塞修复；DSH 会话 final 8 秒不退时由工作台结束进程，避免自动修复卡死。
- 自动修复必须先 fast_gate + 针对性验收都通过才提交；失败回灌同会话继续修。

## DSH 受控工作台工具
- 每次 DSH run 发一个短期能力令牌（环境变量 + 工作台令牌文件回退，因为 DSH 沙箱子进程可能清洗 env）；
- 只允许固定动作：fast_gate / acceptance / status / project / proposals / queue；
- 不能传任意命令、不能读密钥、不能 git 提交；
- status/acceptance 以本次 run 启动前的文件快照为基线，只返回本次 DSH 改动；
- 每次调用写 dgtf_memory/dsh_workbench_calls.jsonl 审计；
- 最终提交前工作台仍会重新跑 fast_gate + 针对性验收，不信任 DSH 自报结果。

## DSH 权限档位（用户配置）
- 只读：DSH 使用自定义 read-only 预设，写文件返回 FS_SANDBOX_DENIED；
- 读写工作区：workspace-write，默认；
- 完全访问：danger-full-access，UI 需二次确认；敏感路径拦截在此模式下放宽；
- 自动审查：DSH 实际使用 workspace-write，由工作台做自动分流/安全审查，高风险仍停人工。
权限选择会对 DSH 面板对话、提案自动修复、人工确认修复同时生效；最终提交仍由工作台复核。

## 启动服务
app 启动会确保：
- 本地 BGE embedding 服务（127.0.0.1:8771）；
- 可选常驻队列守卫（Autopilot 开关开启时）；
- DSH Agent 按需拉起 headless 进程。

## 已知边界
DSH 的 Windows 文件沙箱（dsh-sandbox-windows-acl）只限制写入，不限制读取；
因此应用层做敏感路径硬拦截 + 输出脱敏，但内核级读隔离需要独立 Windows 用户/容器/VM。
