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
  [switch]$Foreground,
  # ★ 本地全链路是**两段**服务：默认只起 8772 推理服务（与旧行为一致，
  #   云端档用户完全不受影响）；加 -Shim 才同时起 8773 OpenAI 适配层。
  #   App 的 /api/health 会同时读两段（见 dgtf_app/local_chain.py）。
  [switch]$Shim,
  [int]$ShimPort = 8773
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

# ── 可选第二段：OpenAI 适配层（8773）—— 本地全链路 ───────────────────
# 为什么默认不起：云端档不需要它；引擎只有在 api.base_url 指向
# http://127.0.0.1:8773/v1 时才走这条链（App 预设「本地模型-全链路.yaml」）。
# 起来之后 App 的 watchdog 会一并守护两段（失败按指数退避重启，见 local_chain.py）。
if ($Shim -and -not $Foreground) {
  $ShimPy = (Get-Command python -ErrorAction SilentlyContinue).Source
  if (-not $ShimPy) { $ShimPy = $Py }
  $ShimScript = Join-Path $Root "scripts\local_model\openai_shim.py"
  $ShimOut = Join-Path $LogDir "shim.out.log"
  $ShimErr = Join-Path $LogDir "shim.err.log"
  $Listening = Get-NetTCPConnection -LocalPort $ShimPort -State Listen -ErrorAction SilentlyContinue
  if ($Listening) {
    Write-Host "[shim] 端口 $ShimPort 已有监听进程，复用（不重复启动）"
  } elseif (-not (Test-Path $ShimScript)) {
    Write-Host "[shim] 找不到适配层脚本：$ShimScript"
  } else {
    $sp = Start-Process -FilePath $ShimPy -ArgumentList @($ShimScript, "--port", "$ShimPort", "--upstream", "http://127.0.0.1:$Port") -WorkingDirectory $Root -RedirectStandardOutput $ShimOut -RedirectStandardError $ShimErr -PassThru -WindowStyle Hidden
    Write-Host "[shim] PID=$($sp.Id) port=$ShimPort -> http://127.0.0.1:$Port logs=$LogDir"
    $ShimDeadline = (Get-Date).AddSeconds(25)
    $ShimReady = $false
    while ((Get-Date) -lt $ShimDeadline) {
      Start-Sleep -Milliseconds 800
      if ($sp.HasExited) {
        Write-Host "[shim] 进程已退出 code=$($sp.ExitCode)"
        if (Test-Path $ShimErr) { Get-Content $ShimErr -Tail 30 }
        break
      }
      try {
        $m = Invoke-RestMethod -Uri "http://127.0.0.1:$ShimPort/v1/models" -TimeoutSec 3
        if ($m.data) { $ShimReady = $true; break }
      } catch { }
    }
    if ($ShimReady) {
      Write-Host "[shim] READY http://127.0.0.1:$ShimPort/v1 （本地档 api.base_url 用这个）"
    } else {
      Write-Host "[shim] 25s 内未就绪（进程仍在跑，可稍后查 /v1/models）"
    }
  }
}
