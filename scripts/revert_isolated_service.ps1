# 需管理员 PowerShell 执行：
#   powershell -ExecutionPolicy Bypass -File .\scripts\revert_isolated_service.ps1 -Apply
param(
  [string]$Account = "DGTFApp",
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$Apply
)
$ErrorActionPreference = "Stop"
$TaskName = "DGTFWeb"
$Data = "C:\ProgramData\DGTF"

Write-Host "=== 回退 DGTFApp 隔离服务 ==="
Write-Host ("账户: " + $Account)
Write-Host ("任务: " + $TaskName)
Write-Host ("项目: " + $ProjectRoot)
Write-Host "动作: 停止服务/任务 -> 移除权限 -> 删除账户 -> 恢复当前用户 app"
if (-not $Apply) {
  Write-Host "计划模式：未修改系统。确认后加 -Apply 并以管理员运行。"
  exit 0
}

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "需要管理员权限：请以管理员身份运行 PowerShell 后重试。"
}

Write-Host "1) 停止计划任务"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Write-Host "2) 停止服务账户 python 进程"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match "dgtf_app[\\/]server.py" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "3) 移除批处理登录权"
$sid = (New-Object Security.Principal.NTAccount($Account)).Translate([Security.Principal.SecurityIdentifier]).Value
$inf = Join-Path $env:TEMP ("dgtf_revert_" + $sid.Replace('-','') + ".inf")
secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$lines = Get-Content -LiteralPath $inf -Encoding Unicode
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '^SeBatchLogonRight\s*=') {
    $vals = ($lines[$i] -split '=',2)[1].Trim() -split ','
    $keep = $vals | Where-Object { $_ -and $_ -notmatch 'DGTFApp' -and $_ -notmatch [regex]::Escape($sid) }
    $lines[$i] = 'SeBatchLogonRight = ' + ($keep -join ',')
  }
}
[IO.File]::WriteAllLines($inf, $lines, [Text.Encoding]::Unicode)
secedit /configure /db ($inf + '.sdb') /cfg $inf /areas USER_RIGHTS /quiet | Out-Null

Write-Host "4) 恢复 .env / TLS 私钥继承 ACL"
foreach ($f in @((Join-Path $ProjectRoot ".env"),
                 (Join-Path $ProjectRoot "dgtf_memory\tls\ca.key"),
                 (Join-Path $ProjectRoot "dgtf_memory\tls\server.key"))) {
  if (Test-Path -LiteralPath $f) {
    icacls $f /inheritance:e 2>&1 | Out-Null
    icacls $f /remove:g $Account 2>&1 | Out-Null
  }
}

Write-Host "5) 移除项目 / DSH / AppData 下的 DGTFApp ACL"
icacls $ProjectRoot /remove:g $Account /T /C 2>&1 | Out-Null
$dshRoot = Join-Path $env:LOCALAPPDATA "Programs\DeepSeek Harness"
if (Test-Path -LiteralPath $dshRoot) { icacls $dshRoot /remove:g $Account /T /C 2>&1 | Out-Null }
$localAppData = Join-Path $env:USERPROFILE "AppData\Local"
$programs = Join-Path $localAppData "Programs"
if (Test-Path -LiteralPath $programs) { icacls $programs /remove:g $Account 2>&1 | Out-Null }
if (Test-Path -LiteralPath $localAppData) { icacls $localAppData /remove:g $Account 2>&1 | Out-Null }
$appData = Join-Path $env:USERPROFILE "AppData"
if (Test-Path -LiteralPath $appData) { icacls $appData /remove:g $Account 2>&1 | Out-Null }

Write-Host "6) 删除本地账户"
if (Get-LocalUser -Name $Account -ErrorAction SilentlyContinue) {
  Remove-LocalUser -Name $Account
}

Write-Host "7) 清理服务数据目录"
if (Test-Path -LiteralPath $Data) { Remove-Item -LiteralPath $Data -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "回退完成。现在用普通 PowerShell 启动当前用户 app："
Write-Host ('cd "' + $ProjectRoot + '"')
Write-Host "python dgtf_app/server.py --port 8765"
Write-Host "访问 https://127.0.0.1:8765/ ，用控制台/日志打印的 ?t= URL 打开。"
