# 本地 Web 应用安全加固

## 已启用
- Host 白名单：默认 127.0.0.1 / localhost / ::1；--lan 时只加入本机网卡地址。
- Origin/Referer 校验：浏览器跨站写请求必须来自白名单 Host。
- CSRF：静态首页下发 dgtf_csrf Cookie，所有写请求带 X-CSRF-Token；无浏览器 Origin 的本地 CLI 兼容。
- 安全响应头：CSP（script-src self）、X-Frame-Options DENY、nosniff、Referrer-Policy、Permissions-Policy、CORP。
- 口令 Cookie 改为 HttpOnly + SameSite=Strict。
- DSH Agent 敏感路径运行时拦截：tool_call 事件命中 .env/.credentials/dsh_conversations 等立即终止本轮；输出中的已知 API key 值脱敏。
- 自动修复安全门槛：提案含敏感词转人工；提交前扫描新增行的硬编码密钥、eval/exec、pickle.loads、shell=True、danger-full-access，命中不提交。
- 自动修复必须先 fast_gate + 针对性验收都通过才提交；失败回灌同会话继续修。

## 启动服务
app 启动会确保：
- 本地 BGE embedding 服务（127.0.0.1:8771）；
- 可选常驻队列守卫（Autopilot 开关开启时）；
- DSH Agent 按需拉起 headless 进程。

## 已知边界
DSH 的 Windows 文件沙箱（dsh-sandbox-windows-acl）只限制写入，不限制读取；
因此应用层做敏感路径硬拦截 + 输出脱敏，但内核级读隔离需要独立 Windows 用户/容器/VM。
