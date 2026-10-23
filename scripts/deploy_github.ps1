param(
  [switch]$PushTags,
  [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne 'main') { throw "当前分支是 $branch，不是 main" }
$local = (git rev-parse HEAD).Trim()
Write-Host ("local HEAD: " + $local)
if ($CheckOnly) { Write-Host 'CheckOnly：不执行推送'; exit 0 }

$candidates = @('20.27.177.113','140.82.113.3','140.82.112.3','4.208.26.197','20.233.83.145','20.200.245.247')
function Test-Tcp443([string]$Ip) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $a = $c.BeginConnect($Ip, 443, $null, $null)
    $ok = $a.AsyncWaitHandle.WaitOne(2500, $false)
    if ($ok) { try { $c.EndConnect($a) } catch { $ok = $false } }
    $c.Close()
    return $ok
  } catch { return $false }
}
$ip = $null
foreach ($cand in $candidates) {
  if (Test-Tcp443 $cand) { $ip = $cand; break }
}
if (-not $ip) { throw 'GitHub 443 候选 IP 全部不可达；请检查网络/代理' }
Write-Host ("using github.com -> " + $ip)
$env:GIT_TERMINAL_PROMPT = '0'
$common = @('-c', ('http.curloptResolve=github.com:443:' + $ip))
$out = & git @common push origin main 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Host $out
if ($code -ne 0) { throw ("push main failed: exit=" + $code) }
if ($PushTags) {
  $tagOut = & git @common push origin --tags 2>&1 | Out-String
  Write-Host $tagOut
  if ($LASTEXITCODE -ne 0) { throw 'push tags failed' }
}
$remote = (& git @common ls-remote --heads origin main 2>&1 | Out-String).Trim()
Write-Host ("remote main: " + (($remote -split "\s+")[0]))
if (-not $remote.StartsWith($local)) { throw '远程 main 与本地 HEAD 不一致' }
Write-Host 'DEPLOY OK'
