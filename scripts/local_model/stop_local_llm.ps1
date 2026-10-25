# -*- coding: utf-8 -*-
<#
.SYNOPSIS
  停止 Meta-DGTF 本地推理服务（按端口找监听进程并结束）。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/local_model/stop_local_llm.ps1
#>
param([int]$Port = 8772)

$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $conn) { Write-Host "[stop] 端口 $Port 没有监听进程"; exit 0 }
$pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $pids) {
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p) {
    Write-Host "[stop] killing PID=$procId ($($p.ProcessName))"
    Stop-Process -Id $procId -Force
  }
}
Start-Sleep -Milliseconds 800
Write-Host "[stop] done"
