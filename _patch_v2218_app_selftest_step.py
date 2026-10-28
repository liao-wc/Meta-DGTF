# -*- coding: utf-8 -*-
"""[V2.2.18] final_acceptance：新增 app_selftest 步骤 + 验收证据出口。"""
import py_compile
from pathlib import Path

P = Path("scripts/final_acceptance.py")
t = P.read_text(encoding="utf-8")

def rep(old, new, cnt=1):
    global t
    c = t.count(old)
    assert c == cnt, "锚点命中 %d 次（应为 %d）：%r" % (c, cnt, old[:60])
    t = t.replace(old, new)

rep("import argparse\nimport os\n", "import argparse\nimport json\nimport os\n")

rep('''    # ★ APP → 引擎 → 本地模型 端到端（零 API 成本；服务未起时退出码 2 = 没跑）
    ("e2e_app_local", ["scripts/local_model/e2e_app_local.py"], POLICY_SERVICE),
''',
'''    # [V2.2.18] App selftest 自动门（自起临时 server；起不来 exit=2 = 没跑）
    ("app_selftest", ["scripts/app_selftest_gate.py"], POLICY_SERVICE),
    # ★ APP → 引擎 → 本地模型 端到端（零 API 成本；服务未起时退出码 2 = 没跑）
    ("e2e_app_local", ["scripts/local_model/e2e_app_local.py"], POLICY_SERVICE),
''')

rep('''    npass = sum(1 for _, st, _, _ in results if st == PASS)
    nskip = sum(1 for _, st, _, _ in results if st == SKIP)
    nfail = sum(1 for _, st, _, _ in results if st == FAIL)
''',
'''    npass = sum(1 for _, st, _, _ in results if st == PASS)
    nskip = sum(1 for _, st, _, _ in results if st == SKIP)
    nfail = sum(1 for _, st, _, _ in results if st == FAIL)
    # ★ [V2.2.18] 证据出口：release_process_check 用它校验「验收新鲜度 + 三态计数」，
    #   同时让 README 的「一键验收 PASS/SKIP/FAIL」数字可被机器核对（防文档漂移）。
    _write_evidence(results, args, npass, nskip, nfail)
''')

rep('''def _print_steps(steps: list) -> None:
''',
'''def _write_evidence(results, args, npass: int, nskip: int, nfail: int) -> None:
    """把本次验收结果写 docs/acceptance_latest.json（失败不阻断验收）。"""
    try:
        now = time.time()
        ev = {
            "schema": "dgtf.acceptance.v1",
            "ts": now,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "with_service": bool(getattr(args, "with_service", False)),
            "skip_service": bool(getattr(args, "skip_service", False)),
            "require_all": bool(getattr(args, "require_all", False)),
            "passed": int(npass),
            "skipped": int(nskip),
            "failed": int(nfail),
            "steps": [{"name": n, "status": s, "sec": c, "reason": r}
                      for n, s, c, r in results],
            "ok": bool(nfail == 0 and not (
                getattr(args, "require_all", False) and nskip)),
        }
        p = ROOT / "docs" / "acceptance_latest.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _print_steps(steps: list) -> None:
''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK final_acceptance: app_selftest step + evidence")
