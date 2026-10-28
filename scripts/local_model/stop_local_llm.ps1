# -*- coding: utf-8 -*-
<#
.SYNOPSIS
  停止 Meta-DGTF 本地推理服务（按端口找监听进程并结束）。
.DESCRIPTION
  默认只停 8772（与旧行为一致）。本地全链路是**两段**服务，加 -Shim 才顺带
  停 8773 OpenAI 适配层（scripts/local_model/openai_shim.py）。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/local_model/stop_local_llm.ps1
  powershell -ExecutionPolicy Bypass -File scripts/local_model/stop_local_llm.ps1 -Shim
#>
param(
  [int]$Port = 8772,
  [switch]$Shim,
  [int]$ShimPort = 8773
)

$ports = @($Port)
if ($Shim) { $ports += $ShimPort }
foreach ($p in $ports) {
  $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if (-not $conn) { Write-Host "[stop] 端口 $p 没有监听进程"; continue }
  $pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $pids) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
      Write-Host "[stop] killing PID=$procId ($($proc.ProcessName)) port=$p"
      Stop-Process -Id $procId -Force
    }
  }
}
Start-Sleep -Milliseconds 800
Write-Host "[stop] done"
