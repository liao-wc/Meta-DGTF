$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$UrlFile = Join-Path $Desktop "元DGTF-快速.url"
$badLnk = Join-Path $Desktop "元DGTF-快速.lnk"
if (Test-Path -LiteralPath $badLnk) { Remove-Item -LiteralPath $badLnk -Force }
$content = "[InternetShortcut]`r`nURL=https://127.0.0.1:8765/`r`n"
[IO.File]::WriteAllText($UrlFile, $content, (New-Object Text.ASCIIEncoding))
Write-Host ("已创建快速入口: " + $UrlFile)