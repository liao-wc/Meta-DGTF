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
- 自学习提案：无待处理提案时，DSH 可读项目+知识库自提优化提案；提案持久化 self_learned/source 标记；安全评估为 auto 才自动修复，否则 pending 人工确认。
- server.py/dsh_tool.py：自动修复硬拒绝；人工 confirmed 后允许修复，但提交前必须通过 security_invariants（Host/CSRF/CSP/权限/工作台令牌等关键结构仍在）和新增代码安全扫描；.env/.ssh/.git/依赖清单即使人工确认也拒绝。
- 复合提案支持拆分；批量归档/清理/删除/根目录/历史版本等词转人工，避免一条提案混入大范围文件移动。
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

## 出站网络 / HTTPS（V1.4.84）

- 外部检索/爬取 URL：只允许 http(s) 公网，阻断 localhost、私网、回环、链路本地、云元数据地址和带 userinfo 的 URL；重定向逐跳复检；下载大小上限 25MB；论文 PDF 下载走安全 opener。
- 知识检索结果：服务端剥离不安全 URL（url_blocked/pdf_blocked），前端 publicUrl() 再挡 localhost/私网/云元数据，避免点击外部结果探测内网。
- DSH Agent 联网由 dgtf_memory/dsh_network.json 控制，默认关闭；开启仅授权公开网站检索/抓取，仍禁止内网、凭据上传和把网页内容当指令执行。
- HTTPS 默认：python dgtf_app/server.py 默认 HTTPS；`--http` 或 DGTF_HTTP=1 显式回退。自签名证书位于 dgtf_memory/tls；HTTPS 下启用 HSTS、Secure cookie、TLS1.2+。
- 本地信任：运行 scripts/trust_https_cert.ps1 把 DGTF Local CA 根加入 CurrentUser\Root；服务器使用 CA 签发的叶子证书（CA:FALSE + serverAuth + SAN），HTTPS 链为 server-chain.pem。CA 私钥 ca.key 与服务器私钥 server.key 仅当前用户/SYSTEM/Administrators 可读。旧的自签名 localhost 根已移除。
- 访问口令：默认启动随机生成本机口令，只放进程内存；API 和静态资源都要求带 ?t= 或 HttpOnly/Secure cookie。DSH 工作台使用独立一次性令牌绕过浏览器口令。可用 DGTF_ACCESS_TOKEN 固定注入（测试/自动化）。
- 同用户边界：如果恶意进程与 app 运行在同一 Windows 用户下，它可以读取 `_app_out.log`、浏览器 profile/内存或调用用户态工具；应用层 token 不能提供强隔离。要做到防同用户恶意进程，需要独立 Windows 用户/服务账户、容器或 VM，并把项目/密钥 ACL 只授予该账户。
- 隔离账户准备：`scripts/setup_isolated_service.ps1` 默认只打印计划；管理员 `-Apply` 会创建普通用户 DGTFApp + 开机计划任务，服务私钥/.env/token 包装器 ACL 限制到服务账户/管理员，当前用户只读 `C:\ProgramData\DGTF\access_url.txt` 中的浏览器 URL。当前会话为 Medium 完整性，未执行 -Apply。
## 已知边界
DSH 的 Windows 文件沙箱（dsh-sandbox-windows-acl）只限制写入，不限制读取；
因此应用层做敏感路径硬拦截 + 输出脱敏，但内核级读隔离需要独立 Windows 用户/容器/VM。

## 2026-10-22 上线前 P1 修复

- 启动日志不打印 `?t=` 口令；访问地址由 `scripts/show_access_url.ps1` 本机生成，旧启动日志已清洗。
- POST 先做 Host/口令/Origin/CSRF 校验，再读 body；JSON 上限 32MB，资料导入 200MB。
- 多实例孤儿任务回收用 `app_pid` 判断归属，不再误标其它实例任务。
- Git 提交范围收紧：未跟踪文件只在 dgtf_app/dgtf_v2/docs/scripts/configs/anchors/bench/llm_sft 下放行；日志/临时文件忽略。
- 真实任务默认 3600s 超时，可用 `DGTF_TASK_TIMEOUT_S` 调整。

## 2026-10-23 公开仓库安全

- 公开仓库已移除 `dgtf_memory`、跑批日志、缓存和运行态输出，并重建为干净历史。
- 开启 Secret scanning、Push protection、Private Vulnerability Reporting、CodeQL 默认扫描。
- 所有 GitHub Actions 固定到完整 commit SHA，并显式声明最小权限。
- main 分支禁止强推和删除，并配置 required checks。
- 本地模型权重、训练环境、访问口令和会话数据不进入仓库。
- 公网访问应使用正式 TLS、登录、限流；自签名证书只用于本机。

