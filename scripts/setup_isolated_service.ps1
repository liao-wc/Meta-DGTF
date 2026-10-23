# 需管理员（UAC 提权）执行：
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_isolated_service.ps1 -Apply
# 默认只打印计划，不改系统。
param(
  [string]$Account = "DGTFApp",
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [int]$Port = 8765,
  [string]$Python = "",
  [string]$DSH = "",
  [switch]$Apply
)
$ErrorActionPreference = "Stop"
if (-not $Python) { $Python = (Get-Command python -ErrorAction Stop).Source }
if (-not $DSH) { $DSH = Join-Path $env:LOCALAPPDATA "Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd" }
$Data = "C:\ProgramData\DGTF"
$TaskName = "DGTFWeb"

Write-Host "=== DGTF 隔离服务账户计划 ==="
Write-Host ("账户: " + $Account + "（普通用户，非管理员）")
Write-Host ("项目: " + $ProjectRoot)
Write-Host ("数据: " + $Data)
Write-Host ("端口: " + $Port)
Write-Host "方式: Windows 计划任务（开机，密码登录）"
if (-not $Apply) {
  Write-Host "计划模式：未修改系统。确认后加 -Apply 并以管理员运行。"
  exit 0
}

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "需要管理员权限：请以管理员身份运行 PowerShell 后重试。"
}
$hasAccount = [bool](Get-LocalUser -Name $Account -ErrorAction SilentlyContinue)
if (-not (Test-Path -LiteralPath $Python)) { throw "找不到 Python: " + $Python }
if (-not (Test-Path -LiteralPath $DSH)) { throw "找不到 DSH: " + $DSH }
$listen = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listen) { throw ("端口 " + $Port + " 已被占用，请先停止旧 app 再运行 -Apply。") }

function Grant-BatchLogon([string]$Name) {
  try {
    $sid = (New-Object Security.Principal.NTAccount($Name)).Translate([Security.Principal.SecurityIdentifier]).Value
    $inf = Join-Path $env:TEMP ("dgtf_secpol_" + $sid.Replace('-','') + ".inf")
    secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
    $lines = Get-Content -LiteralPath $inf -Encoding Unicode
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
      if ($lines[$i] -match '^SeBatchLogonRight\s*=') {
        $found = $true
        if ($lines[$i] -notmatch [regex]::Escape('*' + $sid)) {
          $lines[$i] = $lines[$i].TrimEnd() + ',*' + $sid
        }
      }
    }
    if (-not $found) { $lines += ('SeBatchLogonRight = *' + $sid) }
    [IO.File]::WriteAllLines($inf, $lines, [Text.Encoding]::Unicode)
    secedit /configure /db ($inf + '.sdb') /cfg $inf /areas USER_RIGHTS /quiet | Out-Null
    Write-Host "已授予批处理登录权: $Name"
    Remove-Item -LiteralPath $inf,($inf + '.sdb'),($inf + '.jfm') -Force -ErrorAction SilentlyContinue
  } catch {
    Write-Host ("授予批处理登录权失败（可稍后手动检查）: " + $_.Exception.Message)
  }
}

$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$password = [Convert]::ToBase64String($bytes).Replace("+","").Replace("/","").Replace("=","")
$bytes2 = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes2)
$token = [Convert]::ToBase64String($bytes2).Replace("+","").Replace("/","").Replace("=","")

$sec = ConvertTo-SecureString $password -AsPlainText -Force
if ($hasAccount) {
  Set-LocalUser -Name $Account -Password $sec -PasswordNeverExpires $true
  net user $Account /passwordchg:no | Out-Null
  Write-Host ("复用已存在账户并重置密码: " + $Account)
} else {
  New-LocalUser -Name $Account -Password $sec -PasswordNeverExpires -UserMayNotChangePassword -Description "DGTF isolated web service" | Out-Null
}
Grant-BatchLogon $Account
New-Item -ItemType Directory -Force -Path $Data | Out-Null
# 服务账户必须能读取/执行 Python（它位于当前用户 profile）
$pythonDir = Split-Path -Parent $Python
icacls $pythonDir /grant ($Account + ':(OI)(CI)RX') | Out-Null

$grant = $Account + ':(OI)(CI)M'
icacls $Data /inheritance:r /grant:r $grant 'Administrators:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' | Out-Null
# 代码需要可写：DSH 自动修复会改源码；当前用户仍保留自己的 ACL。
icacls $ProjectRoot /grant ($Account + ':(OI)(CI)M') | Out-Null
foreach ($d in @("dgtf_memory", "outputs", "dgtf_app\runs")) {
  $p = Join-Path $ProjectRoot $d
  if (Test-Path -LiteralPath $p) { icacls $p /grant ($Account + ':(OI)(CI)M') | Out-Null }
}
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path -LiteralPath $envFile) {
  icacls $envFile /inheritance:r /grant:r ($Account + ':R') 'Administrators:F' 'SYSTEM:F' | Out-Null
}
$tls = Join-Path $ProjectRoot "dgtf_memory\tls"
if (Test-Path -LiteralPath $tls) {
  # 公钥证书允许浏览器/信任脚本读取；私钥只允许服务账户和管理员。
  $caKey = Join-Path $tls "ca.key"
  $srvKey = Join-Path $tls "server.key"
  foreach ($k in @($caKey, $srvKey)) {
    if (Test-Path -LiteralPath $k) {
      icacls $k /inheritance:r /grant:r ($Account + ':F') 'Administrators:F' 'SYSTEM:F' | Out-Null
    }
  }
}
$dshDir = Split-Path -Parent (Split-Path -Parent $DSH)
icacls $dshDir /grant ($Account + ':(OI)(CI)RX') | Out-Null
if (Test-Path -LiteralPath "D:\元DGTF-多模并行架构\local_model\envs\dgtf_llm_env") {
  icacls "D:\元DGTF-多模并行架构\local_model\envs\dgtf_llm_env" /grant ($Account + ':(OI)(CI)RX') | Out-Null
}

$wrapper = Join-Path $Data "run_server.ps1"
$lines = @(
  ('$env:DGTF_ACCESS_TOKEN = "' + $token + '"'),
  ('$env:SystemRoot = "C:\Windows"'),
  ('$env:windir = "C:\Windows"'),
  ('$env:ComSpec = "C:\Windows\System32\cmd.exe"'),
  ('$env:PATH = "C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;C:\Windows\System32\Wbem;' + (Split-Path -Parent $Python) + ';' + (Split-Path -Parent $Python) + '\Scripts;" + $env:PATH'),
  ('$env:PYTHONUTF8 = "1"'),
  ('$env:PYTHONIOENCODING = "utf-8"'),
  ('$env:DSH_BIN = "' + $DSH + '"'),
  ('$env:DSH_HOME = "' + $Data + '\dsh_home"'),
  ('Set-Location "' + $ProjectRoot + '"'),
  ('$p = Start-Process -FilePath "' + $Python + '" -ArgumentList @("' + $ProjectRoot + '\dgtf_app\server.py","--port","' + $Port + '") -WorkingDirectory "' + $ProjectRoot + '" -NoNewWindow -PassThru -RedirectStandardOutput "' + $Data + '\server.log" -RedirectStandardError "' + $Data + '\server.err.log"'),
  ('$p.WaitForExit()')
)
Set-Content -LiteralPath $wrapper -Value $lines -Encoding UTF8
icacls $wrapper /inheritance:r /grant:r ($Account + ':F') 'Administrators:F' 'SYSTEM:F' | Out-Null

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $wrapper + '"')
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
$task = Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User $Account -Password $password -RunLevel Highest -Description "DGTF isolated HTTPS web app"
if ($task.State -eq 'Disabled') { Enable-ScheduledTask -TaskName $TaskName | Out-Null }
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
$ti = Get-ScheduledTaskInfo -TaskName $TaskName
if ($ti.LastRunTime.Year -lt 2000) {
  Write-Host "任务尚未运行，使用 schtasks /run 再触发一次..."
  schtasks /run /tn $TaskName | Out-Null
  Start-Sleep -Seconds 3
}
$url = "https://127.0.0.1:" + $Port + "/?t=" + $token
$check = $null
for ($i = 0; $i -lt 15; $i++) {
  $check = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($check) { break }
  Start-Sleep -Seconds 1
}
if (-not $check) {
  Write-Host "服务未监听，读取日志..."
  if (Test-Path (Join-Path $Data 'server.log')) { Get-Content (Join-Path $Data 'server.log') -Tail 40 -Encoding UTF8 }
  Get-ScheduledTaskInfo -TaskName $TaskName | Format-List LastRunTime,LastTaskResult,NextRunTime
  throw ("计划任务已创建但端口 " + $Port + " 未监听；请把上面的 server.log 发回。")
}
$curl = Join-Path $env:SystemRoot 'System32\curl.exe'
try {
  if (Test-Path $curl) {
    $code = (& $curl -k -s -o NUL --max-time 15 -w "%{http_code}" $url | Out-String).Trim()
    if ($code -ne "200") { throw ("curl HTTP " + $code) }
  } else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $oldCb = [Net.ServicePointManager]::ServerCertificateValidationCallback
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    try {
      $probe = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
      if ([int]$probe.StatusCode -ne 200) { throw ("HTTP " + $probe.StatusCode) }
    } finally {
      [Net.ServicePointManager]::ServerCertificateValidationCallback = $oldCb
    }
  }
} catch {
  if (Test-Path (Join-Path $Data 'server.log')) { Get-Content (Join-Path $Data 'server.log') -Tail 40 -Encoding UTF8 }
  if (Test-Path (Join-Path $Data 'server.err.log')) { Get-Content (Join-Path $Data 'server.err.log') -Tail 40 -Encoding UTF8 }
  throw ("服务已监听但访问口令 URL 校验失败: " + $_.Exception.Message)
}
$urlFile = Join-Path $Data "access_url.txt"
[IO.File]::WriteAllText($urlFile, $url, (New-Object Text.UTF8Encoding($false)))
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $urlFile /inheritance:r /grant:r ($currentUser + ':R') 'Administrators:F' 'SYSTEM:F' | Out-Null
Write-Host "已创建隔离账户/计划任务。"
Write-Host ("服务 URL（已写入当前用户可读的 " + $urlFile + "）: " + $url)
Write-Host "当前浏览器仍需信任 DGTF Local CA（scripts\trust_https_cert.ps1）。"
Write-Host ("卸载: Stop-ScheduledTask " + $TaskName + "; Unregister-ScheduledTask " + $TaskName + " -Confirm:$false; Remove-LocalUser " + $Account)
