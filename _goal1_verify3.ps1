$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
$src=(Get-ChildItem -File -Filter "*V1.30.0.py" | Select-Object -First 1).FullName
"SRC=$src"
python _v122_verify.py --src "$src" --phase all *> _gate_goal1_verify3.log
"VERIFY=$LASTEXITCODE"
python smoke_test.py *> _gate_goal1_smoke2.log
"SMOKE=$LASTEXITCODE"
python _probe_v1232_audit.py "$src" *> _gate_goal1_audit2.log
"AUDIT=$LASTEXITCODE"
"DONE"
