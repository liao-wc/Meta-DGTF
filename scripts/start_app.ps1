param(
  [int]$Port = 8765,
  [switch]$Http,
  [switch]$NoBrowser,
  [switch]$Stop,
  [switch]$Restart,
  [switch]$NewToken,
  [switch]$DryRun,
  [switch]$NoAgentDaemon,
  [int]$HealthTimeoutSec = 120
)

# 元DGTF 一键启动器。
# 关键约定：
#   · 稳定访问口令默认复用 dgtf_memory/.access_token，重启/再启动不失效；
#   · -NewToken 生成新口令（配合 -Restart 才对运行中实例生效）；
#   · 启动后必须通过 HTTPS /api/health 健康检查才算成功；
#   · -DryRun 只打印计划，不启动、不停止、不写 token、不写日志；
#   · 本文件必须保存为 UTF-8 with BOM：Windows PowerShell 5 读无 BOM 中文脚本会解析失败。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Log = Join-Path $Root ("_app_out_" + $Port + ".log")
$ErrLog = Join-Path $Root ("_app_err_" + $Port + ".log")
$TokenFile = Join-Path $Root "dgtf_memory\.access_token"
$HealthTimeoutSec = [Math]::Max(3, [int]$HealthTimeoutSec)
if ($PSBoundParameters.ContainsKey("Http")) {
  $PreferredScheme = if ($Http) { "http" } else { "https" }
} else {
  $PreferredScheme = "https"
}

# 本机 app 使用自签名证书；这里只给健康检查放开证书校验（只访问 127.0.0.1）。
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
try { [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true } } catch { }

function Fail([string]$Message) {
  Write-Host ("错误: " + $Message) -ForegroundColor Red
  exit 1
}

function Get-AppListeners {
  return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Get-ProcessInfo([int]$ProcessId) {
  try {
    return Get-CimInstance Win32_Process -Filter ("ProcessId=" + $ProcessId) -ErrorAction SilentlyContinue
  } catch {
    return $null
  }
}

function Test-DgtfAppProcess($Info) {
  if (-not $Info) { return $false }
  return ([string]$Info.CommandLine -match "dgtf_app[\\/]server\.py")
}

function Get-PortState {
  $out = @()
  foreach ($l in @(Get-AppListeners)) {
    $procId = [int]$l.OwningProcess
    $seen = $false
    foreach ($x in $out) { if ($x.Pid -eq $procId) { $seen = $true } }
    if ($seen) { continue }
    $info = Get-ProcessInfo $procId
    $out += [pscustomobject]@{
      Pid         = $procId
      IsDgtf      = (Test-DgtfAppProcess $info)
      CommandLine = [string]($info.CommandLine)
    }
  }
  return @($out)
}

function Read-AppToken {
  if (-not (Test-Path -LiteralPath $TokenFile)) { return "" }
  try {
    $raw = Get-Content -LiteralPath $TokenFile -Raw -Encoding UTF8
    return (([string]$raw) -replace "[\r\n]", "").Trim()
  } catch {
    return ""
  }
}

function Test-TokenFormat([string]$Token) {
  return ($Token -match '^[A-Za-z0-9_-]{16,}$')
}

function New-AppToken {
  return ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
}

function Save-AppToken([string]$Token) {
  $dir = Split-Path -Parent $TokenFile
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  Set-Content -LiteralPath $TokenFile -Value $Token -Encoding ASCII
  try {
    $u = $env:USERNAME
    $null = icacls $TokenFile /inheritance:r /grant:r ($u + ':F') 'SYSTEM:F' 'Administrators:F' 2>&1
  } catch {
    Write-Host ("警告：设置 token 文件 ACL 失败（不影响启动）：" + $_.Exception.Message)
  }
}

function Format-TokenBrief([string]$Token) {
  if (-not $Token) { return "无" }
  if ($Token.Length -le 8) { return "***" }
  return ($Token.Substring(0, 6) + "…（len=" + $Token.Length + "）")
}

function Stop-AppProcesses {
  $state = @(Get-PortState)
  if ($state.Count -eq 0) {
    Write-Host ("端口 " + $Port + " 没有监听进程，无需停止")
    return
  }
  foreach ($item in $state) {
    if (-not $item.IsDgtf) {
      Fail ("端口 " + $Port + " 被非 DGTF 进程占用（pid=" + $item.Pid + "）：" + $item.CommandLine + "；为避免误杀已中止")
    }
    Write-Host ("停止 DGTF app：pid=" + $item.Pid)
    Stop-Process -Id $item.Pid -Force -ErrorAction SilentlyContinue
  }
  for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep -Milliseconds 250
    if (@(Get-AppListeners).Count -eq 0) { break }
  }
  if (@(Get-AppListeners).Count -gt 0) {
    Fail ("端口 " + $Port + " 停止后仍被占用")
  }
  Write-Host ("端口 " + $Port + " 已释放")
}

function Invoke-BoundedHttpGet([string]$Url, [int]$TimeoutSec = 4) {
  # 硬超时探针：优先 curl --max-time。
  # 为什么不用 Invoke-WebRequest：PS5 在「TCP 已连上、TLS 握手卡住」时
  # -TimeoutSec 可能不生效，会把一键启动卡死（实测过）。
  $curl = $null
  try { $curl = (Get-Command curl.exe -ErrorAction Stop).Source } catch { $curl = $null }
  if ($curl) {
    $raw = & $curl '-k' '-s' '--noproxy' '*' '--max-time' ([string]$TimeoutSec) '-w' '__CODE__%{http_code}' $Url 2>$null
    $exitCode = $LASTEXITCODE
    $text = [string]($raw | Out-String)
    $idx = $text.LastIndexOf('__CODE__')
    if ($idx -ge 0) {
      return @{ Code = $text.Substring($idx + 8).Trim(); Body = $text.Substring(0, $idx); Exit = $exitCode }
    }
    return @{ Error = ("curl 未返回状态码（exit=" + $exitCode + "）") }
  }
  # 兜底：HttpClient 自带 Timeout（同样能取消 TLS 握手）。
  try {
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
    $resp = $client.GetAsync($Url).GetAwaiter().GetResult()
    $code = [string]([int]$resp.StatusCode)
    $body = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    $resp.Dispose()
    $client.Dispose()
    return @{ Code = $code; Body = $body; Exit = 0 }
  } catch {
    return @{ Error = $_.Exception.Message }
  }
}

function Get-HealthStatus([string]$Scheme, [string]$Token) {
  $url = ($Scheme + "://127.0.0.1:" + $Port + "/api/health?t=" + $Token)
  $probe = Invoke-BoundedHttpGet $url 4
  if ($probe.Error) {
    return @{ Ok = $false; Scheme = $Scheme; Url = $url; Message = ("探针失败：" + $probe.Error) }
  }
  $code = [string]$probe.Code
  if ($code -ne "200") {
    return @{ Ok = $false; Scheme = $Scheme; Url = $url; Message = ("HTTP " + $code + "（未就绪 / 口令不匹配 / 被拒绝）") }
  }
  $body = $null
  try { $body = $probe.Body | ConvertFrom-Json } catch { $body = $null }
  if ($body -and $body.ok -eq $true) {
    return @{ Ok = $true; Scheme = $Scheme; Url = $url }
  }
  return @{ Ok = $false; Scheme = $Scheme; Url = $url; Message = "HTTP 200，但健康响应缺少 ok=true" }
}

function Wait-AppHealth([string]$Scheme, [string]$Token, $Process) {
  $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
  $last = $null
  while ((Get-Date) -lt $deadline) {
    if ($Process) {
      try { if ($Process.HasExited) { return @{ Ok = $false; Message = ("进程提前退出（exitCode=" + $Process.ExitCode + "）") } } } catch { }
    }
    $last = Get-HealthStatus $Scheme $Token
    if ($last.Ok) { return $last }
    Start-Sleep -Milliseconds 700
  }
  if ($last) { return @{ Ok = $false; Message = ("健康检查超时（" + $HealthTimeoutSec + "s）：" + $last.Message) } }
  return @{ Ok = $false; Message = "健康检查超时（未拿到任何响应）" }
}

function Open-AppBrowser([string]$Url) {
  if ($NoBrowser) { return }
  try { Start-Process $Url | Out-Null } catch { Write-Host ("自动打开浏览器失败：" + $_.Exception.Message) }
}

function Show-LogTail([string]$Path, [string]$Label, [int]$Lines = 30) {
  if (-not (Test-Path -LiteralPath $Path)) {
    Write-Host ("  [无 " + $Label + "] " + $Path)
    return
  }
  Write-Host ("  [" + $Label + "] " + $Path + "（最后 " + $Lines + " 行）")
  try {
    Get-Content -LiteralPath $Path -Tail $Lines -Encoding UTF8 | ForEach-Object { Write-Host ("    " + $_) }
  } catch {
    Write-Host ("    读取失败：" + $_.Exception.Message)
  }
}

function Resolve-Python {
  try { return (Get-Command python -ErrorAction Stop).Source } catch { return "" }
}

function Enter-LauncherLock {
  # 同一端口只允许一个启动器操作：防止双击/并发 -Restart 互相抢停、互相杀进程。
  # 进程退出/被关时 mutex 自动释放；若是被强杀的“已放弃”mutex，WaitOne 会抛
  # AbandonedMutexException，此时所有权已归我们，按成功处理。
  $mutex = $null
  foreach ($ns in @("Global", "Local")) {
    $name = $ns + "\DGTFLauncher_Port" + $Port
    try {
      $mutex = New-Object -TypeName System.Threading.Mutex -ArgumentList @($false, $name)
      break
    } catch {
      $mutex = $null
    }
  }
  if (-not $mutex) { return }
  $got = $false
  try {
    $got = $mutex.WaitOne(0)
  } catch [System.Threading.AbandonedMutexException] {
    $got = $true
  }
  if (-not $got) {
    try { $mutex.Dispose() } catch { }
    Fail ("另一个启动器正在操作端口 " + $Port + "（并发启动/停止已阻止）；请等它结束，或先关掉卡住的启动窗口")
  }
  $script:LauncherMutex = $mutex
}

Write-Host "=== 元DGTF 启动器 ==="

$py = Resolve-Python
$portState = @(Get-PortState)
$runningDgtf = @($portState | Where-Object { $_.IsDgtf })
$runningOther = @($portState | Where-Object { -not $_.IsDgtf })
$fileToken = Read-AppToken
$fileTokenOk = Test-TokenFormat $fileToken
$willRotate = ($NewToken -or (-not $fileTokenOk))

# ---------- DryRun：只打印计划，不产生副作用 ----------
if ($DryRun) {
  Write-Host "模式: DryRun（不启动 / 不停止 / 不写 token / 不写日志）"
  Write-Host ("端口: " + $Port + "    协议: " + $PreferredScheme + "    健康检查超时: " + $HealthTimeoutSec + "s")
  if ($py) { Write-Host ("python: " + $py) } else { Write-Host "python: 未找到（真正启动会失败）" -ForegroundColor Yellow }
  Write-Host ("日志: " + $Log)
  Write-Host ("错误日志: " + $ErrLog)
  if ($Restart) {
    Write-Host ("动作: 先停止端口 " + $Port + " 上由本启动器管理的 DGTF app，再启动新实例")
  } elseif ($Stop) {
    Write-Host ("动作: 仅停止端口 " + $Port + " 的 DGTF app")
  } elseif ($runningOther.Count -gt 0) {
    Write-Host ("动作: 端口被非 DGTF 进程占用（pid=" + ((@($runningOther | ForEach-Object { $_.Pid })) -join ",") + "），真正启动会中止")
  } elseif ($runningDgtf.Count -gt 0) {
    Write-Host ("动作: 检测到 DGTF app 已在运行（pid=" + ((@($runningDgtf | ForEach-Object { $_.Pid })) -join ",") + "），将做健康检查并直接打开，不重启")
  } else {
    Write-Host "动作: 启动新实例"
  }
  if ($willRotate) {
    Write-Host ("访问口令: " + $(if ($fileTokenOk) { "将轮换（-NewToken）" } else { "token 文件缺失/格式不对，将生成" }))
  } else {
    Write-Host ("访问口令: 复用 token 文件（" + (Format-TokenBrief $fileToken) + "）")
  }
  $dashArgs = @("dgtf_app\server.py", "--port", [string]$Port)
  if ($Http) { $dashArgs += "--http" }
  if ($NoAgentDaemon) { $dashArgs += "--no-agent-daemon" }
  Write-Host ("启动命令: python " + ($dashArgs -join " "))
  Write-Host ("访问地址（口令取自 token 文件）: " + $PreferredScheme + "://127.0.0.1:" + $Port + "/?t=<token>")
  exit 0
}

if ($Port -lt 1 -or $Port -gt 65535) { Fail ("端口非法：" + $Port) }

# 非 DryRun 的任何操作（停止/重启/启动/复用打开）都先拿端口级锁。
Enter-LauncherLock

# ---------- 仅停止 ----------
if ($Stop -and -not $Restart) {
  Stop-AppProcesses
  Write-Host ("DGTF app 已停止（端口 " + $Port + "）")
  exit 0
}

# ---------- 重启：先停（端口为空时 Stop-AppProcesses 会提示无需停止） ----------
if ($Restart) {
  Stop-AppProcesses
  $portState = @(Get-PortState)
  $runningDgtf = @()
  $runningOther = @()
}

# ---------- 端口已存在监听：拒绝误杀；若是本应用则健康检查后直接打开 ----------
$portState = @(Get-PortState)
$runningDgtf = @($portState | Where-Object { $_.IsDgtf })
$runningOther = @($portState | Where-Object { -not $_.IsDgtf })
if ($runningOther.Count -gt 0) {
  Fail ("端口 " + $Port + " 被非 DGTF 进程占用（pid=" + ((@($runningOther | ForEach-Object { $_.Pid })) -join ",") + "）；请换端口或先处理该进程")
}
if ($runningDgtf.Count -gt 0) {
  if ($NewToken) {
    Fail ("端口 " + $Port + " 上已有 DGTF app 在运行；轮换口令请用 -Restart -NewToken（会先停止再启动）")
  }
  $token = Read-AppToken
  if (-not (Test-TokenFormat $token)) {
    Fail ("端口 " + $Port + " 上已有 DGTF app，但稳定口令文件缺失或格式不对：" + $TokenFile + "；可用 -Restart -NewToken 重新生成并重启")
  }
  $health = Get-HealthStatus $PreferredScheme $token
  if (-not $health.Ok) {
    $alt = if ($PreferredScheme -eq "https") { "http" } else { "https" }
    $altHealth = Get-HealthStatus $alt $token
    if ($altHealth.Ok) { $health = $altHealth }
  }
  # 进程刚启动时可能已经监听端口、但健康接口尚未完全就绪；
  # 在这里短暂等待，避免“端口有 DGTF 进程但健康 200 尚未 ok”的误报。
  $healthDeadline = (Get-Date).AddSeconds(15)
  while (-not $health.Ok -and (Get-Date) -lt $healthDeadline) {
    Start-Sleep -Milliseconds 700
    $health = Get-HealthStatus $PreferredScheme $token
    if (-not $health.Ok) {
      $altHealth = Get-HealthStatus $alt $token
      if ($altHealth.Ok) { $health = $altHealth }
    }
  }
  if (-not $health.Ok) {
    Write-Host ("已有 DGTF app 但健康检查失败：" + $health.Message) -ForegroundColor Yellow
    Write-Host "自动停止该实例并重新启动（避免双击后发现应用卡死无法恢复）..." -ForegroundColor Yellow
    Stop-AppProcesses
    $runningDgtf = @()
  } else {
    $url = ($health.Scheme + "://127.0.0.1:" + $Port + "/?t=" + $token)
    Write-Host ("DGTF app 已在运行：pid=" + ((@($runningDgtf | ForEach-Object { $_.Pid })) -join ",") + "，健康检查通过（HTTP 200）")
    Write-Host "访问地址：已用浏览器自动打开（含口令 URL 不写入日志）"
    Open-AppBrowser $url
    exit 0
  }
}

# ---------- 启动新实例 ----------
if (-not $py) {
  Fail "找不到 python 命令；请确认 Python 已加入 PATH（当前用户安装即可）"
}

$token = Read-AppToken
if ($NewToken -or (-not (Test-TokenFormat $token))) {
  $token = New-AppToken
  Save-AppToken $token
  Write-Host ("已生成稳定访问口令: " + $TokenFile + "（后续启动复用；-NewToken 才会轮换）")
} else {
  Write-Host ("复用稳定访问口令: " + (Format-TokenBrief $token))
}

# 每次启动前轮换旧日志，避免读到上一次运行的输出/URL。
if (Test-Path -LiteralPath $Log) { Move-Item -LiteralPath $Log -Destination ($Log + ".1") -Force -ErrorAction SilentlyContinue }
if (Test-Path -LiteralPath $ErrLog) { Move-Item -LiteralPath $ErrLog -Destination ($ErrLog + ".1") -Force -ErrorAction SilentlyContinue }

$env:DGTF_ACCESS_TOKEN = $token
$serverArgs = @("dgtf_app\server.py", "--port", [string]$Port)
if ($Http) { $serverArgs += "--http" }
if ($NoAgentDaemon) { $serverArgs += "--no-agent-daemon" }

Write-Host ("启动: python " + ($serverArgs -join " "))
try {
  $p = Start-Process -FilePath $py -ArgumentList $serverArgs -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $Log -RedirectStandardError $ErrLog
} catch {
  Fail ("无法启动 python 进程：" + $_.Exception.Message)
}

$health = Wait-AppHealth $PreferredScheme $token $p
if (-not $health.Ok) {
  Write-Host ("启动失败：" + $health.Message) -ForegroundColor Red
  Write-Host ("进程: pid=" + $p.Id)
  if (-not $p.HasExited) {
    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
  }
  for ($i = 0; $i -lt 16; $i++) {
    Start-Sleep -Milliseconds 250
    if (@(Get-AppListeners).Count -eq 0) { break }
  }
  Write-Host "最近日志（用于定位）："
  Show-LogTail $Log "stdout"
  Show-LogTail $ErrLog "stderr"
  Write-Host ("完整日志: " + $Log + " / " + $ErrLog)
  exit 1
}

$url = ($health.Scheme + "://127.0.0.1:" + $Port + "/?t=" + $token)
Write-Host ("启动成功：pid=" + $p.Id + "，健康检查通过（HTTP 200）")
Write-Host "访问地址：已用浏览器自动打开（含口令 URL 不写入日志）"
Write-Host ("日志: " + $Log + " / " + $ErrLog)
Open-AppBrowser $url
exit 0
