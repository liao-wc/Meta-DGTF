param([int]$Port = 8765, [switch]$Http)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TokenFile = Join-Path $Root "dgtf_memory\.access_token"
if (-not (Test-Path -LiteralPath $TokenFile)) { throw "找不到访问口令文件：$TokenFile" }
$token = (Get-Content -LiteralPath $TokenFile -Raw -Encoding UTF8).Trim()
if (-not $token) { throw "访问口令文件为空：$TokenFile" }
$scheme = if ($Http) { "http" } else { "https" }
Write-Output ($scheme + "://127.0.0.1:" + $Port + "/?t=" + $token)
