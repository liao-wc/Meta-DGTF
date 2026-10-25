<#
.SYNOPSIS
  重训 + 重启 8772 服务 + 重评（等 Lead 通知 GPU 可用后执行）。

.DESCRIPTION
  第一轮 eval 的根因：self_check 训练 60 条样本在 max_len=1536 下**全部被截断**，
  截断策略保头保尾把候选列表中段切掉，模型因此学到「按看到的索引尾部乱喷」
  （suspicious_candidates=[10..39]），JSON 非法 + 决策全错。
  本轮按 Lead 修正方案：
    · self_check：**min 变体**（3 字段 target、26 token）max_len=2048，
      **截断样本直接丢弃**（不中段切候选）；180 条、1 epoch、lr=1e-4
    · dual_judge：why_position 截到 30 字（target 更短）+ max_len=2048；
      130 条、1 epoch、lr=1e-4
    · 重训后重启服务、重跑 eval（含 base 对照 + 逐字段 F1 + τ 曲线）
  预计 33-35 分钟（0.5B + fp32 GEMM ≈ 5s/step）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/local_model/retrain_after_window.ps1
#>
param(
  [int]$ScSamples = 180,
  [int]$DjSamples = 110,
  [int]$MaxLen = 2048,
  [switch]$SkipEval
)

$ErrorActionPreference = "Continue"  # 原生 python 会往 stderr 写 tqdm，Stop 会误判为终止错误
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$Py = Join-Path $Root "local_model\envs\dgtf_llm_env\Scripts\python.exe"
$LogDir = Join-Path $Root "llm_sft\local_llm"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "retrain.log"
function Say($m) {
  $line = "[$([DateTime]::Now.ToString('HH:mm:ss'))] $m"
  Write-Host $line
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

Say "=== 重训开始 (sc=$ScSamples dj=$DjSamples max_len=$MaxLen lr=1e-4 drop_truncated) ==="

# 1) 停服务，释放 GPU
$conn = Get-NetTCPConnection -LocalPort 8772 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  $conn | ForEach-Object {
    Say "停止服务 PID=$($_.OwningProcess)"
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 3
}
& nvidia-smi --query-gpu=memory.used --format=csv,noheader

# 2) self_check_min（干净、不截断、丢弃截断样本）
Say "训练 self_check (min, $ScSamples 条, max_len=$MaxLen)"
$scArgs = @("scripts\local_model\train_dgtf_stage_lora.py",
  "--model", "local_model/models/Qwen2.5-0.5B-Instruct",
  "--stage", "self_check", "--variant", "min",
  "--max-train", "$ScSamples", "--max-len", "$MaxLen",
  "--epochs", "1", "--val-subset", "20", "--log-every", "10",
  "--save-every", "60", "--lr", "1e-4", "--drop-truncated",
  "--out", "llm_sft/adapter_dgtf_selfcheck_05b_v2")
$scProc = Start-Process -FilePath $Py -ArgumentList $scArgs -WorkingDirectory $Root `
  -RedirectStandardOutput (Join-Path $LogDir "retrain_sc.log") `
  -RedirectStandardError (Join-Path $LogDir "retrain_sc.err.log") -Wait -PassThru -NoNewWindow
Say "self_check 训练退出码=$($scProc.ExitCode)"
if ($scProc.ExitCode -ne 0) { Say "self_check 训练失败，终止编排"; exit 2 }

# 3) dual_judge
Say "训练 dual_judge ($DjSamples 条, max_len=$MaxLen)"
$djArgs = @("scripts\local_model\train_dgtf_stage_lora.py",
  "--model", "local_model/models/Qwen2.5-0.5B-Instruct",
  "--stage", "dual_judge", "--max-train", "$DjSamples",
  "--max-len", "$MaxLen", "--epochs", "1", "--val-subset", "20",
  "--log-every", "10", "--save-every", "60", "--lr", "1e-4",
  "--drop-truncated", "--out", "llm_sft/adapter_dgtf_judge_05b_v2")
$djProc = Start-Process -FilePath $Py -ArgumentList $djArgs -WorkingDirectory $Root `
  -RedirectStandardOutput (Join-Path $LogDir "retrain_dj.log") `
  -RedirectStandardError (Join-Path $LogDir "retrain_dj.err.log") -Wait -PassThru -NoNewWindow
Say "dual_judge 训练退出码=$($djProc.ExitCode)"
if ($djProc.ExitCode -ne 0) { Say "dual_judge 训练失败，继续重启服务保住可用性" }

# 4) 重启服务
Say "重启 8772"
$p = Start-Process -FilePath $Py -ArgumentList @("dgtf_local_llm\service.py", "--port", "8772") `
  -WorkingDirectory $Root -RedirectStandardOutput (Join-Path $LogDir "service.out.log") `
  -RedirectStandardError (Join-Path $LogDir "service.err.log") -PassThru -WindowStyle Hidden
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 1500
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8772/health" -TimeoutSec 3
    if ($h.status -eq "ready") {
      $ready = $true
      Say ("SERVICE READY PID=" + $p.Id + " " + ($h | ConvertTo-Json -Compress))
      break
    }
  } catch { }
}
if (-not $ready) { Say "服务未 ready（进程 $($p.Id) 仍在跑）" }

if (-not $SkipEval) {
  # 5) 重评（含 base 对照）
  Say "重跑 eval"
  $evArgs = @("scripts\local_model\eval_dgtf_stage.py", "--limit-dj", "8",
    "--limit-sc", "5", "--limit-scmin", "14",
    "--out", "llm_sft/dgtf_stage/eval_dgtf_stage_v2.json")
  $evProc = Start-Process -FilePath $Py -ArgumentList $evArgs -WorkingDirectory $Root `
    -RedirectStandardOutput (Join-Path $LogDir "eval_v2.log") `
    -RedirectStandardError (Join-Path $LogDir "eval_v2.err.log") -Wait -PassThru -NoNewWindow
  Say "eval(v2) 退出码=$($evProc.ExitCode)"
  # base 对照只跑 self_check_min（最省时）
  $evArgs2 = @("scripts\local_model\eval_dgtf_stage.py", "--stages", "self_check_min",
    "--limit-scmin", "14", "--base",
    "--out", "llm_sft/dgtf_stage/eval_dgtf_stage_v2_base_scmin.json")
  $evProc2 = Start-Process -FilePath $Py -ArgumentList $evArgs2 -WorkingDirectory $Root `
    -RedirectStandardOutput (Join-Path $LogDir "eval_v2_base.log") `
    -RedirectStandardError (Join-Path $LogDir "eval_v2_base.err.log") -Wait -PassThru -NoNewWindow
  Say "eval(v2 base) 退出码=$($evProc2.ExitCode)"
  Say "eval 退出码=$LASTEXITCODE"
}
Say "=== 完成 ==="
