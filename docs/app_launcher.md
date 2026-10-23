# 元DGTF 启动与访问（app_launcher）

> 适用：元DGTF 本地 Web 应用（`dgtf_app/server.py`）。
> 入口：`scripts/start_app.ps1`（唯一实现）+ `scripts/start_app.cmd` / `scripts/stop_app.cmd`（Windows 双击/快捷方式包装）。
> 目标：一键启动、稳定访问口令、启动后健康检查、失败可定位、绝不误杀别的进程。

## 1. 日常使用

桌面快捷方式：**元DGTF**（目标 `scripts/start_app.cmd`，参数 `-Restart`）。

命令行等价：

    .\scripts\start_app.cmd            # 启动/复用默认 8765（已运行则做健康检查后直接打开）
    .\scripts\stop_app.cmd             # 停止 8765 上的 DGTF app

测试/第二实例（不要动 8765 生产实例）：

    .\scripts\start_app.cmd -Port 8766 -NoBrowser
    .\scripts\stop_app.cmd -Port 8766

只预演、不产生任何副作用（不启动、不停止、不写 token、不写日志）：

    .\scripts\start_app.cmd -DryRun -Port 8766

## 2. 参数

| 参数 | 默认 | 含义 |
|---|---|---|
| `-Port <int>` | 8765 | 监听端口；同时决定日志文件名 `_app_out_<port>.log` / `_app_err_<port>.log` |
| `-Http` | 关（HTTPS） | 显式用 HTTP；默认 HTTPS（自签名证书） |
| `-NoBrowser` | 关 | 启动成功后不自动打开浏览器 |
| `-Stop` | 关 | 只停止该端口的 DGTF app；端口无监听时返回 0 |
| `-Restart` | 关 | 先停止该端口的 DGTF app，再启动新实例（快捷方式用的就是这个） |
| `-NewToken` | 关 | 生成新的稳定访问口令并写入 `dgtf_memory/.access_token`；**对运行中实例要配合 `-Restart` 才生效** |
| `-DryRun` | 关 | 只打印计划；不启动/停止/写 token/写日志（-Stop/-Restart 也只打印） |
| `-NoAgentDaemon` | 关 | 直接透传 `server.py --no-agent-daemon`：不起常驻 Agent，适合测试/第二实例，避免与生产实例的守护互相影响 |
| `-HealthTimeoutSec <int>` | 60 | 启动后等待 `/api/health` 200 的超时秒数（最小按 3 秒处理） |

`-Stop` 与 `-Restart` 同时给时，以 `-Restart` 为准（先停后启）。

## 3. 稳定访问口令

- 文件：`dgtf_memory/.access_token`（64 位字母/数字/下划线/连字符）。
- 启动时默认**复用**该文件里的口令；重启 app、重开浏览器书签都不失效。
- 文件不存在或格式不对时自动生成；`-NewToken` 强制轮换。
- 生成后脚本会收紧 ACL：当前用户完全控制，SYSTEM/Administrators 可管理。
- 口令通过环境变量 `DGTF_ACCESS_TOKEN` 传给新进程；不会写进日志。
- 访问地址形如 `https://127.0.0.1:8765/?t=<token>`；首次打开会把 token 记进 cookie。
- ★ 轮换只对“之后启动的实例”生效：生产实例在运行时改文件不会改它内存里的口令。若要让 8765 立即用新口令，必须 `-Restart`（会短暂中断 8765——先确认可以）。

## 4. 启动后健康检查

启动流程：解析 python → 生成/复用 token → 轮换旧日志 → 起子进程 → **轮询 HTTPS `/api/health?t=…` 直到返回 200 且 JSON `ok=true`**。

- 健康检查通过才打印“启动成功”并自动开浏览器；否则按失败处理。
- 默认最多等 `-HealthTimeoutSec`（60s）；期间若子进程提前退出，立即判失败。
- 证书：app 是自签名证书。启动器只在**自己的进程内**放开证书校验（只访问 127.0.0.1），不修改系统证书库；浏览器仍需先信任本机 CA（见 `scripts/trust_https_cert.ps1`）。
- 兼容多协议：端口上已有 DGTF app 时，先按请求的协议健康检查（默认 https），失败再试另一协议；仍失败会提示用 `-Restart`。

### 失败时做什么

1. 打印失败原因（进程提前退出 exitCode / HTTPS 超时 / HTTP 非 200 / 401 等）；
2. 打印 `_app_out_<port>.log`、`_app_err_<port>.log` 的**尾部 30 行**；
3. 若进程还活着，只停掉**本次启动器拉起的那个 pid**（不会碰别的进程）；
4. 返回非 0，`.cmd` 会 pause 并显示错误码，日志路径可直接打开。

## 5. 端口占用与误杀保护

- 若端口被**非 DGTF 进程**占用：直接报错退出（列出 pid/命令行），**绝不 kill**。
- 若端口上是**本项目的 DGTF app**：不重复启动，直接做健康检查；通过则打印访问地址并（除非 `-NoBrowser`）打开浏览器；失败则提示用 `-Restart`。
- `-Stop` 只停命令行里含 `dgtf_app\server.py` 的进程，且停止后等待端口真正释放；释放不了会报错。

## 6. 日志

| 文件 | 内容 |
|---|---|
| `_app_out_<port>.log` | 子进程 stdout（启动横幅、引擎信息等） |
| `_app_err_<port>.log` | 子进程 stderr（异常/警告） |
| 同路径 `.1` | 上一次启动留下的日志（每次启动前自动轮换，避免读到旧 URL） |

## 7. 编码与 PowerShell 5 约束（改脚本必看）

- `scripts/start_app.ps1` **必须是 UTF-8 with BOM**。Windows PowerShell 5 读取无 BOM 的 UTF-8 中文脚本会解析失败（乱码/语法错误）。
- 修改后用如下命令校验 BOM 与语法（PowerShell 5）：

      $p = (Resolve-Path .\scripts\start_app.ps1).Path
      $b = [System.IO.File]::ReadAllBytes($p)
      "BOM=" + ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
      $tokens = $null; $errors = $null
      [System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$tokens, [ref]$errors) | Out-Null
      "parseErrors=" + @($errors).Count      # 必须是 0

- `.cmd` 保持纯 ASCII、无 BOM（避免 cmd 把 BOM 当命令），内部用 `powershell -Command` 调 ps1；本环境用 `-File` 启动 ps1 曾失败，不要改成 `-File`。
- 脚本里避免写 `"$var:` 这类拼接（PowerShell 会把它当驱动器限定变量），统一用 `("..." + $var + "...")`。

## 8. 桌面快捷方式兼容

- 快捷方式：`%Desktop%\元DGTF.lnk` → 目标 `<repo>\scripts\start_app.cmd`，参数 `-Restart`，工作目录仓库根。
- 本次改动未改快捷方式、未改 `.cmd` 入口名与转发方式；`-Restart` 语义保持：先停默认 8765 上的 DGTF app，再启动/复用。
- 重新生成快捷方式（仅需要时）：`powershell -ExecutionPolicy Bypass -File .\scripts\create_desktop_shortcut.ps1`。

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| `端口 X 被非 DGTF 进程占用` | 换端口（如 `-Port 8766`）或先停占用进程；启动器不会替你 kill 它 |
| `健康检查失败：HTTP 401` | 稳定 token 与运行中实例不一致：对**测试实例**用 `-Restart -NewToken`；对生产 8765 先确认可重启 |
| `找不到 python 命令` | 把 Python 加入 PATH（当前用户安装即可），重开终端 |
| 浏览器提示证书不受信任 | 先运行 `scripts/trust_https_cert.ps1` 信任本机 CA（CurrentUser Root） |
| 启动很慢/健康超时 | 看 `_app_err_<port>.log`；RAG/Agent 初始化慢时可临时加 `-HealthTimeoutSec 120` |
| 脚本报语法错误/中文乱码 | 检查是否丢了 UTF-8 BOM，按 §7 校验并恢复 BOM |
| 双击后窗口一闪而过 | 失败时 `.cmd` 会 pause；若没看到，在终端运行同一 `.cmd` 复现 |

## 10. 安全边界

- 当前模式：当前 Windows 用户运行，无独立服务账户；token 文件与浏览器 profile 对**同用户**的进程不设防。
- 启动器不会把 token 写进日志/stdout；但访问地址本身带 token（浏览器书签同源），这是本机使用方式的既定妥协。
- `-NewToken` 后旧书签失效（需用新 `?t=` 地址或重启实例），应在确认可中断时执行。

## 11. 自检记录（2026-10-22）

> 详细命令与结果见交付消息；本章只留结论，便于下次改脚本后回归。

| 项 | 预期 | 结果 |
|---|---|---|
| UTF-8 BOM + Parser | parseErrors=0 | 见交付记录 |
| `-DryRun -Port 8766` | exit 0、无副作用 | 见交付记录 |
| 8766 启动/健康/停止 | exit 0、/api/health 200、端口释放 | 见交付记录 |
| token 复用 | 两次启动 token 不变 | 见交付记录 |
| `-Restart -NewToken` | token 轮换、旧 token 401 | 见交付记录（测试后恢复原 token） |
| 8765 生产实例 | pid/健康不变 | 见交付记录 |
