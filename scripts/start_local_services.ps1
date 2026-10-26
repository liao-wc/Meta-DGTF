# 一键启动本地服务（训练结束后恢复 App/本地模型链路）
# 用法: pwsh -NoProfile -File scripts/start_local_services.ps1
param(
    [int]$EmbedPort = 8771,
    [int]$LlmPort = 8772
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'local_model\envs\dgtf_llm_env\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "local model python missing: $py" }
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'

function Get-ListenerPid([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $conn) { return 0 }
    return [int]$conn.OwningProcess
}

function Wait-Health([string]$url, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-RestMethod -Uri $url -TimeoutSec 3
            if ($h) { return $h }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $null
}

# 1) BGE embed service
$embedPid = Get-ListenerPid $EmbedPort
if ($embedPid -eq 0) {
    $log = Join-Path $root 'outputs\_lead_audit\rag_embed_start.log'
    Start-Process -FilePath $py -ArgumentList 'dgtf_app\rag_embed_service.py' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    Write-Host "[start] BGE embed service port=$EmbedPort log=$log"
} else {
    Write-Host "[ok] BGE embed service already running port=$EmbedPort pid=$embedPid"
}

# 2) local LLM service
$llmPid = Get-ListenerPid $LlmPort
if ($llmPid -eq 0) {
    $log2 = Join-Path $root 'outputs\_lead_audit\local_llm_start.log'
    Start-Process -FilePath $py -ArgumentList 'dgtf_local_llm\service.py', '--port', "$LlmPort" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $log2 -RedirectStandardError "$log2.err"
    Write-Host "[start] local LLM service port=$LlmPort log=$log2"
} else {
    Write-Host "[ok] local LLM service already running port=$LlmPort pid=$llmPid"
}

# 3) health check
$base = "http://127.0.0.1:$LlmPort"
$health = Wait-Health "$base/health" 120
if ($null -eq $health) {
    Write-Host "[fail] local LLM /health not ready; see outputs/_lead_audit/local_llm_start.log" -ForegroundColor Red
    exit 1
}
$adapters = $health.adapter_paths
Write-Host "[health] status=$($health.status) self_check_min=$($adapters.self_check_min)"
try {
    $m = Invoke-RestMethod -Uri "$base/metrics" -TimeoutSec 5
    Write-Host "[metrics] total=$($m.stats.requests_total) errors=$($m.stats.errors)"
} catch {
    Write-Host "[warn] metrics read failed (not blocking)" -ForegroundColor Yellow
}
exit 0
