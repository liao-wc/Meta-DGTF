param(
  [int]$Port = 8765,
  [switch]$Http,
  [switch]$NoBrowser,
  [switch]$Stop,
  [switch]$Restart,
  [switch]$NewToken,
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Log = Join-Path $Root ("_app_out_" + $Port + ".log")
$Err = Join-Path $Root ("_app_err_" + $Port + ".log")

function Get-AppListener {
  Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
}

function Stop-App {
  $listeners = @(Get-AppListener)
  foreach ($l in $listeners) {
    $proc = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $l.OwningProcess) -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -match "dgtf_app[\\/]server.py") {
      Stop-Process -Id $l.OwningProcess -Force -ErrorAction SilentlyContinue
      Write-Host ("已停止 pid=" + $l.OwningProcess)
    } else {
      throw ("端口 " + $Port + " 被非 DGTF 进程占用: pid=" + $l.OwningProcess)
    }
  }
  Start-Sleep -Milliseconds 500
}

if ($Stop -or $Restart) { Stop-App }
if ($Stop) { Write-Host "DGTF app 已停止"; exit 0 }
if ($DryRun) {
  Write-Host ("计划: python " + (Join-Path $Root "dgtf_app\server.py") + " --port " + $Port)
  Write-Host ("HTTPS: " + (-not $Http))
  Write-Host ("日志: " + $Log)
  exit 0
}
if (Get-AppListener) {
  throw ("端口 " + $Port + " 已被占用；先运行 -Stop 或 -Restart")
}

$py = (Get-Command python -ErrorAction Stop).Source

# 稳定访问口令：默认复用 dgtf_memory/.access_token，重启不失效；-NewToken 重新生成。
$TokenFile = Join-Path $Root "dgtf_memory\.access_token"
$token = ""
if (-not $NewToken -and (Test-Path -LiteralPath $TokenFile)) {
  $token = (Get-Content -LiteralPath $TokenFile -Raw -Encoding UTF8).Trim()
}
if ($NewToken -or $token -notmatch '^[A-Za-z0-9_-]{16,}$') {
  $token = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
  Set-Content -LiteralPath $TokenFile -Value $token -Encoding ASCII
  $u = $env:USERNAME
  icacls $TokenFile /inheritance:r /grant:r ($u + ':F') 'SYSTEM:F' 'Administrators:F' | Out-Null
  Write-Host "已生成本机稳定访问口令: dgtf_memory/.access_token"
}
$env:DGTF_ACCESS_TOKEN = $token
$serverArgs = @("dgtf_app\server.py", "--port", "$Port")
if ($Http) { $serverArgs += "--http" }
Write-Host ("启动: " + $py + " " + ($serverArgs -join " "))
$p = Start-Process -FilePath $py -ArgumentList $serverArgs -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $Log -RedirectStandardError $Err

$url = $null
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  if (-not (Test-Path $Log)) { continue }
  $txt = Get-Content -LiteralPath $Log -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
  $pattern = 'https?://127\.0\.0\.1:' + $Port + '/\?t=[A-Za-z0-9_-]+'
  $m = [regex]::Match([string]$txt, $pattern)
  if ($m.Success) { $url = $m.Value; break }
}
if (-not $url) {
  if (Test-Path $Err) { Get-Content $Err -Tail 40 -Encoding UTF8 }
  throw "未在日志中找到带 ?t= 的访问 URL；请检查 _app_err_日志"
}
Write-Host ("访问地址: " + $url)
Write-Host ("进程: " + $p.Id)
if (-not $NoBrowser) {
  try { Start-Process $url } catch { Write-Host ('自动打开浏览器失败: ' + $_.Exception.Message) }
}
