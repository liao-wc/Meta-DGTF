param(
  [string]$Cert = (Join-Path (Split-Path -Parent $PSScriptRoot) "dgtf_memory\tls\ca.pem")
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Cert)) {
  Write-Error "找不到证书：$Cert"
}
# 只把本机 DGTF Local CA 根加入「当前用户」根存储，不写入机器级根存储；
# 服务器叶子证书 CA:FALSE，仅用于 localhost/127.0.0.1。
certutil -addstore -user Root $Cert | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "已信任本地 HTTPS 证书。请完全关闭并重新打开浏览器后访问 https://127.0.0.1:8765/"
