$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$Lnk = Join-Path $Desktop "元DGTF.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Sc = $Shell.CreateShortcut($Lnk)
$Sc.TargetPath = Join-Path $Root "scripts\start_app.cmd"
$Sc.Arguments = "-Restart"
$Sc.WorkingDirectory = $Root
$Sc.IconLocation = (Join-Path $Root "dgtf_app\static\favicon.svg")
$Sc.Description = "启动元DGTF（HTTPS，稳定访问口令）"
$Sc.Save()
Write-Host ("已创建桌面快捷方式: " + $Lnk)
