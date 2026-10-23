$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
python _run_gate.py _gate_goal1_smoke.log -- python smoke_test.py
"SMOKE=$LASTEXITCODE"
$src=(Get-ChildItem -File -Filter "*V1.30.0.py" | Select-Object -First 1).FullName
python _v122_verify.py --src "$src" --phase all *> _gate_goal1_verify.log
"VERIFY=$LASTEXITCODE"
python _probe_v1232_audit.py "$src" *> _gate_goal1_audit.log
"AUDIT=$LASTEXITCODE"
"GOAL1_DONE"
