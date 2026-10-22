# 元DGTF app 上线标准审计报告

- 审计对象：元DGTF 本地 Web 应用（`dgtf_app`，生产实例 127.0.0.1:8765）
- 审计日期：2026-10-22（17:33–17:55 Asia/Shanghai）
- 审计方式：**只读**（不启动/停止服务、不 git commit、不改源码/配置/运行态；唯一写入本报告 `reports/goal_app_prod_audit.md`）
- 工作区：`C:\Users\18432\Desktop\元DGTF-多模并行架构`，HEAD `a6a7f0c`，工作树 732 项脏改动 / 650 项未跟踪
- 审计人：core-gate（Team Lead 委派）

> 结论速览：**P0 = 0**，**P1 = 6**，**P2 = 12**。默认本机模式没有可直接远程利用的未授权入口；主要风险集中在「口令明文落盘、请求体/多实例/成本等边界、发布门禁与版本一致性」。建议按 §5 的 P1 清单收口后重新跑门禁（目标：fast_gate 12/0、selftest 371/0、依赖链审计 78/0）再上线。

---

## 1. 审计范围与门禁结果

| 维度 | 方法（只读） | 结果 |
|---|---|---|
| 认证 / CSRF / HTTPS | 读 `dgtf_app/server.py` 的 `_guard/_granted/_cookies/_ensure_tls_cert`；核对证书与 ACL | 主体达标；口令落盘风险见 P1-1 |
| 进程与日志 | 进程树、端口、日志大小/租约、轮换逻辑、`.1` 日志、`C:\ProgramData\DGTF` | 见 P1-1、P2-3/P2-4/P2-7 |
| 错误处理 | 逐路由 try/except、do_GET/do_POST 边界、Content-Length/body 读取 | 见 P1-2、P2-1 |
| 持久化并发 | 锁、原子写、多实例、恢复逻辑 | 见 P1-3、P2-2 |
| API 契约 | 路由盘点（100 个 `if p == "/api/..."` + 16 个正则路由 = 116 个判定点）、返回形状、错误码 | 见 P2-1/P2-5 |
| 前端交互 | `static/app.js` / `index.html` 静态分析（innerHTML/esc/CSRF/fetch/定时器/CSP） | 见 P2-6 |
| 测试覆盖 | 本次只读跑 `fast_gate.py`；读最新 selftest/依赖审计证据 | fast_gate **PASS 12 / FAIL 0**；selftest 最新日志 **PASS 371 / FAIL 0**；依赖链审计当前 **PASS 76 / FAIL 2**（见 P1-6） |
| 发布/回滚/版本 | 版本号、发布说明、git tag、提交范围、回滚端点、launcher | 见 P1-4/P1-6/P2-9 |
| validation_report 遗留 | 逐条核对 §2–§11 与当前代码/状态 | 见 §6 |

**只读门禁命令**（未写字节码；未触碰生产实例）：

```
$env:PYTHONDONTWRITEBYTECODE="1"; $env:PYTHONUTF8="1"; python -X utf8 fast_gate.py
→ PASS api_policy / self_feedback / facet / vision / input_sanity / agent_repair / agent_worker /
  agent_bridge / agent_daemon / compile / structural_diversity / audit70
→ FAST GATE PASS 12 / FAIL 0
```

> 说明：selftest 371/0 与依赖链审计为**读取既有证据**（最新 `_gate_*_app.log` 尾部、`docs/dependency_chain_audit.md`），本次未重启/重跑 selftest（它会向运行中的生产实例发任务并写产物，违反只读约束）。审计期间生产 8765 被其它进程重启过（PID 8088→25728→26564），非本审计所为；审计前后 8765 均由当前用户监听 127.0.0.1。

---

## 2. P0（上线阻断）

**无。** 理由：服务默认只绑 127.0.0.1（`server.py` CLI 默认 `--host 127.0.0.1`）；所有 `/api/*` 与静态资源经过 `_guard`（Host 白名单 + 口令 + Origin/Referer + CSRF）；未发现无需口令即可造成远程代码执行/数据删除的默认路径。下列 P1 在「同机多用户 / 项目目录被备份或误提交 / 被诱导点击」场景下可升级，必须收口。

---

## 3. P1（上线前必须修复）

### P1-1 访问口令明文落盘（日志 + ProgramData 残留）
- **证据**
  - `dgtf_app/server.py:8726-8728`：启动时打印 `元DGTF 应用已启动： https://127.0.0.1:8765/?t=<token>`；
  - `scripts/start_app.ps1:370`：`Start-Process ... -RedirectStandardOutput $Log`（`$Log = _app_out_<port>.log`，L25），于是该行连同真实 token 写入 `_app_out_8765.log`；L360-361 只把旧日志轮换为 `.1`，**不脱敏、不删除**；
  - 实测：`_app_out_8766.log`、`_app_out_8766.log.1` 命中 `t=[A-Za-z0-9_-]{8,}`（token 真实值已核实存在，报告不复制）；`_app_out_8765.log` 当前被运行中进程占用，此前读取同样命中；
  - `C:\ProgramData\DGTF\access_url.txt` 长 67B，内容形如 `https://127.0.0.1:<port>/?t=<token>`（旧服务账户模式残留；当前用户可读执行，目录列表被 ACL 限制）；
  - 文档矛盾：`docs/app_launcher.md:47/117` 称「口令…不会写进日志/stdout」；`docs/security_hardening.md` 称「只放进程内存」；`server.py` 启动文案亦称「只保存在本进程内存」。
- **影响**：任何能读取项目目录/备份/日志收集器/ProgramData 文件的进程或人，都能拿到完整访问口令 → 可跑引擎（花 API 额度）、调用 DSH（含 danger-full-access 档）、读写资料库。属本机信任边界内泄露，故 P1 而非 P0。
- **最小修复**：① 启动横幅把 URL 中的 token 打码（`?t=***`），另加 `--print-token-url` 才显式打印（或仅 TTY 时打印）；② launcher 已在控制台打印带 token 的 URL（L393-395），子进程日志不再需要它；③ 对已有 `_app_out_*.log*` 做一次性脱敏/删除，并把 `_app_*.log*` 加 ACL；④ 删除/轮换 `C:\ProgramData\DGTF\access_url.txt`；⑤ 修正两份文档与启动文案。
- **验收**：`Select-String -Path _app_out_*.log* -Pattern "t=[A-Za-z0-9_-]{8,}"` 无命中；launcher 控制台仍能显示可用 URL；`/api/logs` 读取时 `redacted` 计数为 0。

### P1-2 POST 请求体无上限，且先读 body 后鉴权
- **证据**：`server.py:7737-7747` `do_POST` 先 `n = int(Content-Length)`、`self.rfile.read(n)`，再 `_guard(mutate=True)`；仅 `/api/library/import` 在读完 200MB 后才检查 `MAX_UPLOAD_BYTES`（L7755-7760）。`int(...)` 位于 try 外（L7740；`_read_json` L7064 同样），非法 Content-Length 会抛未捕获异常。
- **影响**：本机任意进程可对监听端口发超大 Content-Length（或超慢 body），在鉴权前占用内存/连接 → 内存 DoS、keep-alive 连接被拖死；错误首行会让 handler 直接断连并打印 traceback。
- **最小修复**：读 body 前先做 `try: n=int(...) except: 400`；`if n > CAP (建议 32MB，库导入单独 200MB 且分路由)` → 413 + `Connection: close`，再 `_guard`；`_read_json` 统一复用该检查。
- **验收**：`Content-Length: 999999999` 的未授权 POST 返回 413 JSON、进程内存不涨；非法 Content-Length 返回 400 而非 traceback。

### P1-3 多实例启动会「回填」掉其它实例正在跑的任务
- **证据**：`engine_runner.recover_orphans()`（L299-348）在启动时遍历 `outputs/*.run.json`，凡 `live=true` 且不在本进程 `_tasks` 的 running/queued 记录一律改成 `interrupted`；**没有校验文件里的 pid/实例是否仍存活**。启动流程 `server.py:8696+（recover_orphans 调用）` 无条件执行。
- **影响**：文档/验收支持「第二实例 8766」与开发期自检；一旦 8766 启动，可能把 8765 正在运行的任务在产物库/历史对话里标成「服务中断」，且 8765 内存任务仍在跑 → 状态分叉、产物归档冲突（数据完整性）。
- **最小修复**：`_write_live_run` 增加 `pid` + `instance_id`；`recover_orphans` 仅在「pid 不存在 / pid 不匹配该仓库进程」时回填（Windows 用 `OpenProcess`/`tasklist` 只读判断），否则跳过；另加仓库级单实例互斥（锁文件/命名互斥量）供需要时选配。
- **验收**：双实例（8765 跑 mock + 启动 8766）时，8765 任务状态不被改写；8766 自己的孤儿仍能正确回填。

### P1-4 Git 提交范围漏洞：token 日志 `.log.1` 可被提交
- **证据**：
  - `server.py:1223-1243` `_commit_scope` 只过滤 `p.startswith(_RUNTIME_PREFIXES)` 与 `.endswith((".log",".pyc",".sqlite3"))`；当 `allowed` 为空时（L1240 `if allowed and ...`）**未跟踪文件全部放行**；
  - `_git_commit_scoped`（L1246-1280）把 `git status --porcelain` 的全部路径交给上述逻辑 → `/api/git/commit` 会 `git add` 未跟踪的 `_app_out_8766.log.1`、`_app_err_8766.log.1`、`.tmp_fastgate/` 等；
  - `.gitignore:26` 仅 `/*.log`；实测 `git check-ignore` 不匹配 `_app_out_8766.log.1`，`git status` 显示 `?? _app_out_8766.log.1`、`?? .tmp_fastgate/`；
  - 未跟踪文件里有 P1-1 的 token 日志（`_app_out_8766.log.1` 命中 token 模式）。
- **影响**：通过 UI/API 提交时可能把 token 与运行 scratch 永久写进 git 历史；与 `docs/validation_report` §5「只提交源码/文档」的验收结论不一致。
- **最小修复**：`_commit_scope` 改为白名单式——只接受「已跟踪文件」或调用方显式 `allowed`；补充拒绝 `.log.*`、`.tmp*`、`.bak`、目录型未跟踪项；\`.gitignore` 增加 `*.log.*`、`.tmp_fastgate/`、`_app_*.log*`；提交前 `git check-ignore -q` 复核。
- **验收**：构造 `_app_out_8766.log.1`/scratch 后调用 `/api/git/commit`，返回不允许/不 staged；`git show --stat` 只含源码/文档。

### P1-5 引擎默认不设超时，成本/时长可失控
- **证据**：`engine_runner.start_task` 中 `"timeout_s": float(opts.get("timeout_s") or opts.get("max_seconds") or 0)`（默认 0 = 不限制）；`docs/validation_report_2026-10-22.md:78/118` 记录：一次默认真实任务 >300s 未结束需人工取消，且「默认不设上限，需按预算显式传」为遗留。
- **影响**：真实跑（付费 API）可能长时间/高额度运行，用户忘记取消即持续消耗；上线后若对外演示/共享，成本不可控。
- **最小修复**：给真实引擎默认上限（建议 1800s，可配置 `DGTF_DEFAULT_TIMEOUT_S`/参数页），任务卡显示剩余时间与预估花费；超时按现有 timeout 路径标 `timeout/partial`；在 `/api/tasks` 返回该默认值便于前端提示。
- **验收**：不传 `opts.timeout_s` 的真实任务到默认上限自动终止并落 `partial`；mock 不受影响。

### P1-6 版本/发布门禁漂移：应用版本、静态资源版本、发布说明、依赖链审计不一致
- **证据**：
  - `server.py:33` `APP_VERSION = "1.4.1"`；`static/index.html:9/552` 引用 `?v=1.5.11`；`docs/goal_master_plan.md` 基线写 app v1.5.11；
  - `docs/releases/` 最新为 `APP-V1.4.1.md`（无 1.5.x 发布说明）；`git tag` 为空；HEAD `a6a7f0c` 已在 1.4.1 之后多轮提交；
  - `docs/dependency_chain_audit.md`（2026-10-22 17:38:13）当前 **PASS 76 / FAIL 2**，FAIL 项为 `app version present 1.4.1` 与 `health ok`（该文件由并行工作生成，本次只读引用）。
- **影响**：发布门禁无法稳定转绿；「发布的是哪个版本、回滚到哪」靠人脑；依赖审计的 version/health 两处 FAIL 使「上线证据」不可复现（health FAIL 也可能是审计侧 token/协议不匹配，需要重跑确认）。
- **最小修复**：统一 bump → `APP_VERSION`/静态查询串/README/发布说明/tag（如 `app-v1.5.11`）一处生成；把「version 一致 + health 200（带 token）」纳入发布检查单；重跑依赖链审计至 78/0 后留证据文件。
- **验收**：三处版本一致；`git tag` 指向发布 commit；依赖链审计 78/0；发布说明含回滚点。

---

## 4. P2（可上线后按优先级修）

1. **错误处理与契约一致性（P2-1）**：`do_POST` L7740 / `_read_json` L7064 的 `int(Content-Length)` 未防护；`do_GET/do_POST` 无顶层 try/except，未捕获异常由 `BaseHTTPRequestHandler` 打印 traceback 并断连；404/500 响应存在 `{"error":...}` 与 `{"ok":false,"error":...}` 两种形状；`do_HEAD` 固定 405（L7716-7720）与 `do_OPTIONS` 宣称的 PUT/DELETE/PATCH 不一致（L7722-7726）；无失败限速/登录尝试计数（token 64 位随机，本地风险低）。建议：统一错误信封 + 顶层兜底 500 JSON + 统一方法处理。
2. **持久化原子性/并发（P2-2）**：`_save_proposal`（L1388-1395）无锁、直接 `write_text`；`_write_live_run`（engine_runner L226-253）直接写 `<tid>.run.json`，崩溃可能留半截 JSON，而 `recover_orphans` 对 `ValueError` 静默 `continue`（L316-318）→ 该任务凭空消失；`_autopilot_cfg_save`/`save_params` 非原子（后者有 .bak+回读校验）。正面参照：`_auto_jobs_save`（L4648-4661）使用 `.tmp`+`replace()`。建议统一 `_atomic_write_json`，提案/配置加进程内锁与文件锁。
3. **日志/磁盘治理（P2-3）**：`_app_out/_app_err` 仅 launcher 轮换一份 `.1`（start_app.ps1:360-361），`agent_daemon.log`/引擎 run 日志无轮换；当前 `outputs` 120.4MB/1451 文件、`dgtf_app/runs` 33.0MB/1671、`dsh_conversations` 4.3MB/115、`_audit_tmp` **3120.7MB/49237 文件**、`smoke_outputs` 358.6MB/12251。建议：定时/启动时按大小或天数清理 scratch 与超期产物（保留最近 N），加磁盘占用健康检查。
4. **进程生命周期（P2-4）**：RAG embedding 服务进程 `27336`（02:22:12 启动，父进程 26880 已不存在）及其子 `25796`（监听 127.0.0.1:8771）在当前 app 17:15 重启后仍被复用；无显式停止/回收路径。建议：embed service 加父进程存活检测与退出回调，或 app 退出时按 pid 文件停止自己拉起的实例。
5. **API 文档/版本化（P2-5）**：路由判定点 116 个，而 `dgtf_app/README.md` API 表仅约 12 条；`/api/tasks/<id>/retry`、`queue_pos`、`/api/logs` 未进 README；无 `/api/v1` 版本前缀；`/static/_accept.html`（155KB）与 `app.v1.js/style.v1.css/index.v1.html` 作为静态资源仍可访问（旧版页面暴露风险低但无必要）。建议：README 由路由表生成或补全，删旧静态资产。
6. **前端健壮性（P2-6）**：无 401/token 过期提示（只在 403 时自动取 CSRF 重试一次，`app.js:47/62/109`）；8 处 `fetch` 无 `AbortController`/超时（后端卡住时页面只能干等）；token 保留在地址栏/浏览器历史（文档已声明为书签式妥协）；82 处 `innerHTML` 中 285 处 `esc()` 覆盖较好，仅 1 处未转义（`app.js:3017` 的静态 `label`，当前安全但属脆弱模式）；11 处 `setInterval` / 6 处 `clearInterval`（全局轮询有意常驻，视图切换不清定时器）。建议：统一 `fetchJSON` 封装（超时+401 引导重新打开带 token 的 URL）、模板统一 `esc`。
7. **ACL/凭据残留（P2-7）**：`dgtf_memory/tls/server.key`、`ca.key` ACL 含已删除账户 SID `…-1007`、`…-1008`（当前 `Get-LocalUser` 无此二账户）及 CSRF token 上的异常 capability SID；`C:\ProgramData\DGTF\access_url.txt` 为服务账户模式残留（含 token 的 URL）；`docs/security_hardening.md` 称 CA/服务器私钥「仅当前用户/SYSTEM/Administrators 可读」与实测 ACL 不符。建议：删除服务账户遗留 ACL（icacls 只留当前用户/SYSTEM/Administrators），删除/轮换 ProgramData 残留文件，清理后复核 `icacls`。
8. **测试覆盖（P2-8）**：门禁以单测/静态检查为主——selftest 对认证只有源码字符串断言（`selftest.py:313-334`），无 401/403/CSRF/Host 负向行为测试；fast_gate 12 项不含 HTTP 契约测试；`/api/logs`、`/api/tasks/<id>/retry`、`queue_pos` 无自动化测试（仅并行验收手测）；无多实例/崩溃一致性/超大 body 测试；浏览器全按钮 E2E 仍为待办（`task-18` pending）；依赖链审计当前 76/2。建议：加一个轻量 HTTP 契约测试脚本（起临时实例 8767、带 token 跑 404/409/脱敏/413/401），纳入 fast_gate 或 CI。
9. **发布/回滚流程（P2-9）**：无 git tag/正式发布检查单；回滚依赖 `/api/dsh/proposals/<id>/rollback` 在主工作树 `git revert`（`server.py:8171+`），提交前未校验工作树是否干净——当前 732 项脏改动/650 未跟踪，revert 可能失败或混入无关改动；autopilot 开启时 `_auto_commit` 可自动提交（当前 `dgtf_memory/agent_autopilot.json: enabled=false`，风险未激活）。建议：发布前 `git status` 干净检查 + tag；回滚优先在隔离 worktree 验证（validation §5 已演练过）；文档化「回滚 runbook」。
10. **可观测/健康（P2-10）**：依赖链审计的 `health ok` FAIL（17:38）说明健康检查口径不统一（`/api/health` 无 token 返回 401，审计侧易误判）；审计期间生产 PID 多次变化（8088→25728→26564），无重启审计日志/结构化 metrics；`/api/health`、任务、DSH 无 SLO 看板。建议：健康检查统一带 token/协议并记录，启动/退出写审计行。
11. **文档/行为偏差（P2-11）**：`docs/app_launcher.md:47/117` 与 `docs/security_hardening.md` 关于 token 不落盘的表述与实现不符（P1-1）；security 文档称 DSH「不能 git 提交」，但 autopilot 开启时主进程 `_auto_commit` 会提交（`server.py:1283-1311`）；launcher 文档暗示默认起 agent daemon，而 `_autopilot_cfg_load()` 默认 `enabled:false`（当前 daemon/app.state=stopped）；`docs/validation_report` 中「静态资源 v=1.4.86」已过期（现 1.5.11）。建议：随 P1-1/P1-6 一并修文档。
12. **仓库/磁盘卫生（P2-12）**：工作树 732 脏 / 650 未跟踪；scratch 合计 >3.6GB（`_audit_tmp` 3.1GB、`smoke_outputs` 359MB、`outputs` 120MB、`runs` 33MB）；`.tmp_fastgate/`、`.log.1` 未被 ignore（关联 P1-4）。建议：`.gitignore` 补全、定期清理 scratch、发布前 `git clean -nd` 审查。

---

## 5. 已达标项（可保留的现有保障）

- **传输/认证**：HTTPS 默认（`--http`/`DGTF_HTTP=1` 才回退）；本地 CA 签发链 + TLS1.2+（`dgtf_memory/tls/server-chain.pem`）；HTTPS 下 HSTS、Secure Cookie；口令默认启用、首次 `?t=` 种 HttpOnly/SameSite=Strict Cookie（`_cookies` L6965-6974）；Host 白名单 + Origin/Referer + CSRF 双提交（`_guard` L7038-7058；`_load_csrf_token` 持久化）。
- **响应安全头**：CSP（script-src self）、X-Frame-Options DENY、nosniff、Referrer-Policy、Permissions-Policy、CORP（`_security_headers` L6985+）；前端 0 个内联事件处理器，CSP 兼容。
- **出站安全**：`dgtf_v2/net_policy.py` 阻断 localhost/私网/回环/链路本地/云元数据/带 userinfo URL，重定向逐跳校验、25MB 上限；知识检索 URL 服务端剥离不安全链接，前端 `publicUrl()` 二次拦截（validation §2）。
- **DSH 受控边界**：权限档位（read-only/workspace-write/danger-full-access 二次确认）；`_dsh_workbench` 只允许固定动作（fast_gate/acceptance/status/project/proposals/queue），短期令牌（环境变量 + 令牌文件回退），不能任意命令/git；敏感路径运行时拦截与输出脱敏（docs/security_hardening.md）。
- **Git 提交安全（已跟踪路径）**：`_commit_scope`/`_git_commit_scoped` 对**已跟踪**源码/文档生效，拒绝 `dgtf_memory/`、产物、`.log` 等；validation §5 有隔离 worktree 实测（仅 `server.py`+`docs` 进提交）——但未跟踪 `.log.1` 漏洞见 P1-4。
- **任务/日志 API**：`POST /api/tasks/<id>/retry`（仅 error/cancelled，404/409 契约）、`queue_pos`（仅 queued，1-based 入队序）、`GET /api/logs`（白名单、尾 512KB、按行、脱敏 `t=`/DGTF_ACCESS_TOKEN/DEEPSEEK_API_KEY/DGTF_API_KEY、无绝对路径）已按任务契约实现并各自通过测试。
- **持久化（部分）**：`_auto_jobs_save` 用 `.tmp`+`replace()` 原子写；CSRF token 跨重启稳定；`engine_runner._tasks` 有锁；live-run 崩溃回填设计（缺陷见 P1-3/P2-2）。
- **进程/启动器**：launcher 健康检查（HTTPS 200+ok）、端口占用不误杀、`-DryRun` 无副作用、失败打印日志尾部、日志单代轮换 `.1`、稳定 token `dgtf_memory/.access_token`（仅当前用户/SYSTEM/Administrators ACL）；8765 当前 owner=当前用户、监听 127.0.0.1。
- **运行态安静**：`dgtf_memory/agent_autopilot.json: enabled=false`、`agent_daemon.app.state=stopped`（与 validation §4 一致，避免自动修复/自动提交在审计期活动）。
- **测试证据**：本次只读 fast_gate **12/0**；最新 `_gate_dsh_bridge_app.log`/`_gate_parallel_app.log` 尾行均 **PASS 371/0**；任务级 retry/queue/logs 验收通过（task-12/13/16）。

---

## 6. `docs/validation_report_2026-10-22.md` 遗留核对

| 遗留项（报告位置） | 当前状态 | 关联 |
|---|---|---|
| §9.1 服务账户下 DSH 子 shell 0xC0000142，补环境后待管理员重启复测 | **未收尾**：`Get-LocalUser` 无 DGTFApp、`schtasks` 无 DGTFWeb（隔离模式当前未部署，生产以当前用户运行）；`C:\ProgramData\DGTF` 残留 | P2-7 |
| §3 同用户恶意进程可读 `_app_out.log`/profile（应用层 token 非内核隔离） | **仍成立且更严重**：token 明文在 `_app_out_*.log*`/ProgramData 残留（P1-1 已升级处理） | P1-1 |
| §10 长真实跑默认不设上限、需显式传 timeout_s | **仍存在** | P1-5 |
| §10 更多供应商故障注入 / 全量长时压力 / 前端交互全按钮回归 | **未完成**（task-18 pending） | P2-8 |
| §9 依赖链审计 58/0、应用版本 1.4.1/静态 v=1.4.86 | **漂移**：当前依赖审计 76/2 FAIL；静态 v=1.5.11；APP_VERSION 仍 1.4.1 | P1-6/P2-11 |
| §4 AP/daemon 均 false | **符合**（autopilot enabled=false、state=stopped） | P2-11（文档默认值表述） |
| §5 Git 提交/回滚隔离演练 | 已演练；但当前提交范围存在未跟踪文件漏洞、回滚无干净树校验 | P1-4/P2-9 |
| §2 出站网络与 DSH 授权 | **已达标**（net_policy + 默认关闭 + 前端二次拦截） | — |

---

## 7. 最小上线路径（建议顺序）

1. **P1-1** 启动横幅 token 打码 + 清理/脱敏现有 `_app_out_*.log*` 与 ProgramData 残留 + 修文档；
2. **P1-2** body 上限/Content-Length 防护前移到鉴权之前；
3. **P1-3** live-run 写入 pid/instance + `recover_orphans` 活性校验（可选单实例互斥）；
4. **P1-4** 提交范围白名单 + `.gitignore` 补全 + 提交前 `git check-ignore` 复核；
5. **P1-5** 真实引擎默认超时（可配置）；
6. **P1-6** 版本三处同步 + 发布说明 + tag，重跑 **fast_gate 12/0、selftest 371/0、依赖链审计 78/0**，存档证据；
7. 发布前 `git status` 干净检查 + 回滚 drill（隔离 worktree）记录；P2 项排入迭代。

---

## 8. 审计方法与证据索引（只读）

- 代码：`dgtf_app/server.py`（认证/CSRF/HTTPS/错误处理/提交范围/回滚/日志接口/参数接口）、`dgtf_app/engine_runner.py`（任务、timeout、孤儿恢复、live-run 原子性）、`dgtf_app/selftest.py`（安全断言范围）、`dgtf_app/params.py`（密钥只读掩码）、`dgtf_app/library.py`（扩展名白名单）、`dgtf_app/static/app.js`+`index.html`（CSP/XSS/CSRF/定时器/401）。
- 脚本/文档：`scripts/start_app.ps1`、`scripts/stop_app.cmd`、`scripts/setup_isolated_service.ps1`、`scripts/trust_https_cert.ps1`；`docs/app_launcher.md`、`docs/security_hardening.md`、`docs/validation_report_2026-10-22.md`、`docs/parallel_acceptance.md`、`docs/goal_master_plan.md`、`docs/dependency_chain_audit.md`、`docs/releases/*`、`README.md`。
- 运行态（只读观测）：`Get-NetTCPConnection`（8765/8771）、`Get-WmiObject Win32_Process`（owner=当前用户）、`Get-LocalUser`/`schtasks /query`、`icacls`（`.access_token`/`.csrf_token`/tls 私钥/ProgramData）、`Get-ChildItem`（日志/产物/scratch 体积）、`git status/rev-parse/tag/check-ignore`、`Select-String`（token 模式命中与否，未输出真实值）。
- 门禁：`fast_gate.py`（本次，PYTHONDONTWRITEBYTECODE=1）→ 12/0；最新 selftest 371/0 日志尾部；`docs/dependency_chain_audit.md` 76/2。
- 本次**未做**：服务启动/停止、git 写操作、selftest 重跑、任何源码/配置修改；报告为唯一写入文件。

---

> 快照说明：本报告以审计开始时的只读快照为准（HEAD `a6a7f0c`、工作树 732 脏/650 未跟踪）。审计期间并行工作使 HEAD 前移（至 `d5a264c`）并多次重启生产 8765（PID 8088→25728→26564→25212），均非本审计所为；结论不依赖 HEAD 之后的提交。工作区 `M dgtf_app/server.py` 等为审计前既有未提交改动，本审计未触碰任何源码/配置。

*报告生成：2026-10-22 17:55（Asia/Shanghai），core-gate。*
