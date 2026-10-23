$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
python _run_gate.py _gate_final2_fast.log -- python fast_gate.py
"FAST=$LASTEXITCODE"
python _run_gate.py _gate_final2_app.log -- python dgtf_app/selftest.py
"APP=$LASTEXITCODE"
python _run_gate.py _gate_final2_smoke.log -- python smoke_test.py
"SMOKE=$LASTEXITCODE"
$src=(Get-ChildItem -File -Filter "*V1.30.0.py" | Select-Object -First 1).FullName
python _v122_verify.py --src "$src" --phase all *> _gate_final2_verify.log
"VERIFY=$LASTEXITCODE"
python _probe_v1232_audit.py "$src" *> _gate_final2_audit.log
"AUDIT=$LASTEXITCODE"
"ALLDONE"
