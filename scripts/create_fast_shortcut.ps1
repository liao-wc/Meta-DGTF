$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$UrlFile = Join-Path $Desktop "元DGTF-快速.url"
$badLnk = Join-Path $Desktop "元DGTF-快速.lnk"
if (Test-Path -LiteralPath $badLnk) { Remove-Item -LiteralPath $badLnk -Force }
$nl = [string][char]13 + [string][char]10
$content = "[InternetShortcut]" + $nl + "URL=https://127.0.0.1:8765/" + $nl + "IconFile=" + (Join-Path $Root "dgtf_app\static\dgtf.ico") + $nl
[IO.File]::WriteAllText($UrlFile, $content, (New-Object Text.UnicodeEncoding($false, $true)))
Write-Host ("已创建快速入口: " + $UrlFile)