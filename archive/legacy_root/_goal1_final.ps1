$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
$src=(Get-ChildItem -File -Filter "*V1.30.0.py" | Select-Object -First 1).FullName
python _run_gate.py _gate_goal1_fast2.log -- python fast_gate.py 2>&1 | Select-Object -Last 2
"FAST=$LASTEXITCODE"
python _v122_verify.py --src "$src" --phase all *> _gate_goal1_verify5.log
"VERIFY=$LASTEXITCODE"
python _run_gate.py _gate_goal1_app2.log -- python dgtf_app/selftest.py 2>&1 | Select-Object -Last 2
"APP=$LASTEXITCODE"
"DONE"
