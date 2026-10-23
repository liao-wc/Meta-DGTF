# 管理员修复服务账户遗留的运行文件 ACL（仅 dgtf_memory 下指定的运行文件）。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Files = @(
  (Join-Path $Root "dgtf_memory\playbook.jsonl"),
  (Join-Path $Root "dgtf_memory\auto_jobs.json")
)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "需要管理员权限"
}
foreach ($f in $Files) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Host ("跳过不存在: " + $f); continue }
  & takeown.exe /f $f | Out-Null
  & icacls.exe $f /reset | Out-Null
  Write-Host ("已重置 ACL: " + $f)
}
Write-Host "ACL 修复完成"
