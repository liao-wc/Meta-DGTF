param([switch]$Quiet)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$logPath = Join-Path $Root '_repo_manager.log'
function Log([string]$m) {
  if (-not $Quiet) { Write-Host $m }
  try { Add-Content -LiteralPath $logPath -Value ((Get-Date).ToString('s') + ' ' + $m) -Encoding UTF8 } catch {}
}
try {
  $branch = (git rev-parse --abbrev-ref HEAD).Trim()
  if ($branch -ne 'main') { Log "SKIP branch=$branch"; exit 0 }
  $local = (git rev-parse HEAD).Trim()
  $env:GIT_TERMINAL_PROMPT = '0'
  $ips = @('20.27.177.113','140.82.113.3','140.82.112.3','4.208.26.197','20.233.83.145','20.200.245.247')
  $common = $null
  $remoteLine = $null
  foreach ($ip in $ips) {
    $c = New-Object System.Net.Sockets.TcpClient
    $a = $c.BeginConnect($ip, 443, $null, $null)
    $ok = $a.AsyncWaitHandle.WaitOne(2000, $false)
    if ($ok) { try { $c.EndConnect($a) } catch { $ok = $false } }
    $c.Close()
    if (-not $ok) { continue }
    $common = @('-c', ('http.curloptResolve=github.com:443:' + $ip))
    $raw = & git @common ls-remote --heads origin main 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $raw.Trim()) {
      $remoteLine = ($raw.Trim() -split "\s+")[0]
      Log ("ip=$ip remote=$remoteLine local=$local")
      break
    }
    $common = $null
  }
  if (-not $common) { Log 'ERROR no reachable GitHub IP'; exit 1 }
  if ($remoteLine -eq $local) { Log 'SYNCED'; exit 0 }
  & git @common merge-base --is-ancestor $remoteLine $local 2>$null
  if ($LASTEXITCODE -eq 0) {
    $out = & git @common push origin main 2>&1 | Out-String
    Log $out.Trim()
    if ($LASTEXITCODE -ne 0) { Log 'ERROR push failed'; exit 1 }
    $after = & git @common ls-remote --heads origin main 2>&1 | Out-String
    $afterSha = ($after.Trim() -split "\s+")[0]
    if ($afterSha -eq $local) { Log 'PUSHED'; exit 0 }
    Log 'ERROR remote mismatch'; exit 1
  }
  & git merge-base --is-ancestor $local $remoteLine 2>$null
  if ($LASTEXITCODE -eq 0) { Log 'BEHIND remote; DSH will not auto-merge'; exit 0 }
  Log 'DIVERGED; no force push'; exit 1
} catch {
  Log ('ERROR ' + $_.Exception.Message)
  exit 1
}
