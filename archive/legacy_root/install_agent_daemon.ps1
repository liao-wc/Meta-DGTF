$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbs = Join-Path $root "start_agent_daemon.vbs"
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "DGTF-Agent-Daemon.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = "wscript.exe"
$s.Arguments = '"' + $vbs + '"'
$s.WorkingDirectory = $root
$s.WindowStyle = 7
$s.Description = "DGTF Agent daemon (no window)"
$s.Save()
Write-Output $lnk
