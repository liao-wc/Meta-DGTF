$Root = Split-Path -Parent $PSScriptRoot
$Hook = Join-Path $Root '.git\hooks\post-commit'
$content = @'
#!/bin/sh
repo=$(git rev-parse --show-toplevel)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$repo/scripts/dsh_repo_manage.ps1" >/dev/null 2>&1 &
exit 0
'@
[IO.File]::WriteAllText($Hook, $content, (New-Object Text.UTF8Encoding($false)))
Write-Host ("installed: " + $Hook)
