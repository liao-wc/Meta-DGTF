# -*- coding: utf-8 -*-
"""[V2.2.18] 给 fast_gate / run_v2_tests 加证据出口（docs/*_latest.json）。"""
import py_compile
from pathlib import Path

# ── 1) fast_gate.py ─────────────────────────────────────────────────
P = Path("fast_gate.py")
t = P.read_bytes().decode("utf-8")
assert t.count("import argparse") == 1

t = t.replace("import argparse\nimport os\n",
              "import argparse\nimport json\nimport os\n", 1)
t = t.replace("import sys\nfrom concurrent.futures",
              "import sys\nimport time\nfrom concurrent.futures", 1)

OLD_RET = '''    print("\\nFAST GATE PASS %d / FAIL %d" % (len(checks) - len(bad), len(bad)))
    return 0 if not bad else 1
'''
NEW_RET = '''    print("\\nFAST GATE PASS %d / FAIL %d" % (len(checks) - len(bad), len(bad)))
    # ★ [V2.2.18] 证据出口：release_process_check 用它校验「门有没有新鲜跑过」
    #   以及 README 的「当前版本实测」数字是否与真实结果一致（防文档漂移）。
    try:
        _now = time.time()
        _ev = {
            "schema": "dgtf.fast_gate.v1",
            "ts": _now,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now)),
            "engine": str(engine) if engine else "",
            "engine_name": Path(engine).name if engine else "",
            "engine_version": engine_version_str() if engine else "",
            "engine_source": source,
            "total": len(checks),
            "passed": len(checks) - len(bad),
            "failed": len(bad),
            "failed_names": list(bad),
            "ok": not bad,
        }
        _p = ROOT / "docs" / "fast_gate_latest.json"
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(json.dumps(_ev, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return 0 if not bad else 1
'''
assert t.count(OLD_RET) == 1
t = t.replace(OLD_RET, NEW_RET)

# 新增检查：发布流程门自检（零 GPU、秒级）
OLD_CHK = '''        # task-3 判据：快速门禁自身的语义（动态发现 + 对齐 + acceptance 三态）
        ("acceptance_semantics", [sys.executable,
         str(ROOT / "scripts" / "tests_acceptance_semantics.py")]),
'''
NEW_CHK = '''        # task-3 判据：快速门禁自身的语义（动态发现 + 对齐 + acceptance 三态）
        ("acceptance_semantics", [sys.executable,
         str(ROOT / "scripts" / "tests_acceptance_semantics.py")]),
        # [V2.2.18] 发布流程门自检：版本/文档/证据/标签/N-A 分类的构造性判据
        ("release_process_selftest", [sys.executable,
         str(ROOT / "scripts" / "tests_release_process.py")]),
'''
assert t.count(OLD_CHK) == 1
t = t.replace(OLD_CHK, NEW_CHK)
P.write_bytes(t.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK fast_gate evidence + release_process_selftest step")

# ── 2) scripts/run_v2_tests.py ─────────────────────────────────────
P2 = Path("scripts/run_v2_tests.py")
t2 = P2.read_text(encoding="utf-8")
assert t2.count("import argparse\n") == 1
t2 = t2.replace("import argparse\n", "import argparse\nimport json\n", 1)
OLD2 = '''    if bad:
        print("\\nV2 TESTS FAILED: %d / %d" % (len(bad), len(files)))
        return 1
    print("V2 TESTS PASS: %d / %d" % (len(files), len(files)))
    return 0
'''
NEW2 = '''    # ★ [V2.2.18] 证据出口：release_process_check 校验新鲜度 + README 数字一致性
    try:
        _ev = {
            "schema": "dgtf.v2_tests.v1",
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "files": len(files),
            "passed": len(files) - len(bad),
            "failed": len(bad),
            "skips": total_skips,
            "checks": total_checks,
            "elapsed_sec": round(elapsed, 1),
            "failed_names": [b[0] for b in bad],
            "ok": not bad,
        }
        _p = ROOT / "docs" / "v2_tests_latest.json"
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(json.dumps(_ev, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if bad:
        print("\\nV2 TESTS FAILED: %d / %d" % (len(bad), len(files)))
        return 1
    print("V2 TESTS PASS: %d / %d" % (len(files), len(files)))
    return 0
'''
assert t2.count(OLD2) == 1
t2 = t2.replace(OLD2, NEW2)
P2.write_text(t2, encoding="utf-8")
py_compile.compile(str(P2), doraise=True)
print("OK run_v2_tests evidence")
