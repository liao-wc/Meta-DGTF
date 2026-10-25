# -*- coding: utf-8 -*-
<#
.SYNOPSIS
  启动 Meta-DGTF 本地推理服务（dgtf_local_llm/service.py，默认 127.0.0.1:8772）。

.DESCRIPTION
  - 模型在后台线程加载，/health 立即可访问（status=loading → ready）。
  - 日志：llm_sft/local_llm/service.out.log / service.err.log
  - 默认后台启动并等待 /health 变 ready（最多 180s），打印 PID/端口/延迟。
  - app/engine 通过 HTTP 调用：POST http://127.0.0.1:8772/generate

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/local_model/start_local_llm.ps1
  powershell -ExecutionPolicy Bypass -File scripts/local_model/start_local_llm.ps1 -Port 8772 -Foreground
#>
param(
  [int]$Port = 8772,
  [string]$Model = "",
  [int]$WaitSeconds = 180,
  [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$Py = Join-Path $Root "local_model\envs\dgtf_llm_env\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "找不到 python: $Py" }

$LogDir = Join-Path $Root "llm_sft\local_llm"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLog = Join-Path $LogDir "service.out.log"
$ErrLog = Join-Path $LogDir "service.err.log"
$ArgsList = @("dgtf_local_llm\service.py", "--port", "$Port")
if ($Model -ne "") { $ArgsList += @("--model", $Model) }

if ($Foreground) {
  Write-Host "[start] foreground: $Py $($ArgsList -join ' ')"
  & $Py @ArgsList
  exit $LASTEXITCODE
}

$p = Start-Process -FilePath $Py -ArgumentList $ArgsList `
  -WorkingDirectory $Root -RedirectStandardOutput $OutLog `
  -RedirectStandardError $ErrLog -PassThru -WindowStyle Hidden
Write-Host "[start] PID=$($p.Id) port=$Port logs=$LogDir"

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 1500
  if ($p.HasExited) {
    Write-Host "[start] 进程已退出 code=$($p.ExitCode)"
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 }
    exit 1
  }
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
    if ($h.status -eq "ready") {
      $ready = $true
      Write-Host ("[start] READY ok={0} model={1} adapters={2} load={3}s warmup={4}ms gpu_mem={5}MB" -f `
        $h.ok, $h.model, ($h.adapter -join ","), $h.load_sec, $h.warmup_ms, $h.gpu_mem_mb)
      break
    } elseif ($h.status -eq "error") {
      Write-Host "[start] 加载失败: $($h.error)"
      if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 40 }
      exit 1
    }
  } catch { }
}
if (-not $ready) {
  Write-Host "[start] 超时：$WaitSeconds s 内未 ready（进程仍在跑，可稍后查 /health）"
}
Write-Host "[start] PID=$($p.Id) URL=http://127.0.0.1:$Port"
Write-Host "[start] health : Invoke-RestMethod http://127.0.0.1:$Port/health"
Write-Host "[start] generate: Invoke-RestMethod -Method Post http://127.0.0.1:$Port/generate -ContentType 'application/json; charset=utf-8' -Body (@{stage='self_check_min';text='...';timeout=60} | ConvertTo-Json -Depth 6)"
