# App 上线检查单（2026-10-22）

## 已通过（P0/P1）

- [x] HTTPS 默认 + 本地 CA 信任脚本。
- [x] 访问口令启用；启动日志不打印口令；scripts/show_access_url.ps1 本机获取。
- [x] POST 先鉴权再读 body；JSON 32MB/上传 200MB 上限。
- [x] CSRF/Origin/Referer/Host 校验。
- [x] 多实例孤儿任务 app_pid 归属。
- [x] Git 自动提交范围收紧；日志/临时文件忽略。
- [x] 真实任务默认 timeout_s=3600。
- [x] 前端 30s 请求超时 + 401 可读提示。
- [x] fast_gate 12/0；selftest 371/0；依赖审计 78/0；HTTP 200。
- [x] app/engine 版本与发布说明、tag 对齐。

## 上线前仍需确认（P2/运维）

- [ ] 清理历史 _audit_tmp / 临时目录（约 3GB，需人工确认保留策略）。
- [ ] 日志轮转与保留天数策略。
- [ ] 提案/策略 JSON 原子写全覆盖。
- [ ] 统一 API 错误信封与顶层异常处理。
- [ ] 浏览器全按钮 E2E 与 401 场景回归。
- [ ] 独立服务账户部署的 DSH headless 0xC0000142 收尾（当前不依赖 headless）。
- [ ] 生产备份/恢复演练。
- [ ] 发布 tag/检查单/回滚演练。
