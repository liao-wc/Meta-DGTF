param(
  [string]$Cert = (Join-Path (Split-Path -Parent $PSScriptRoot) "dgtf_memory\tls\cert.pem")
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Cert)) {
  Write-Error "找不到证书：$Cert"
}
# 只把本机自签名证书加入「当前用户」根存储，不写入机器级根存储；
# 仅信任这一张证书，不要把它做成通用 CA。
certutil -addstore -user Root $Cert | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "已信任本地 HTTPS 证书。请完全关闭并重新打开浏览器后访问 https://127.0.0.1:8765/"
