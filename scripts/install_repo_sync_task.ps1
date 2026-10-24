$Root = Split-Path -Parent $PSScriptRoot
$TaskName = 'DSH-MetaDGTF-RepoSync'
$Script = Join-Path $Root 'scripts\dsh_repo_manage.ps1'
$cmd = 'powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $Script + '" -Quiet'
schtasks.exe /Create /TN $TaskName /SC MINUTE /MO 5 /TR $cmd /F | Out-Host
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
schtasks.exe /Query /TN $TaskName /V /FO LIST | Select-String -Pattern 'TaskName|Status|Schedule Type|Repeat: Every|Task To Run' | Out-Host
