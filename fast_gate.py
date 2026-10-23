# -*- coding: utf-8 -*-
"""快速门禁：并行跑关键语法/模块/审计检查，缩短反馈；完整门禁仍用 _run_gate。"""
from __future__ import annotations
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CHECKS = [
    ("compile", [sys.executable, "-c",
     "import py_compile;py_compile.compile('元DGTF-V2.0.0.py',doraise=True)"]),
    ("audit70", [sys.executable, "_probe_v1232_audit.py", "元DGTF-V2.0.0.py"]),
    ("input_sanity", [sys.executable, "-c",
     "import dgtf_v2.tests_input_sanity as t;raise SystemExit(t.main())"]),
    ("facet", [sys.executable, "-c", "import dgtf_v2.tests_facet_ledger as t;raise SystemExit(t.main())"]),
    ("structural_diversity", [sys.executable, "-c",
     "import dgtf_v2.tests_structural_diversity as t;raise SystemExit(t.main())"]),
    ("self_feedback", [sys.executable, "-c", "import dgtf_v2.tests_self_feedback as t;raise SystemExit(t.test())"]),
    ("api_policy", [sys.executable, "-c", "import dgtf_v2.tests_api_policy as t;raise SystemExit(t.main())"]),
    ("vision", [sys.executable, "-c", "import dgtf_v2.tests_vision_input as t;raise SystemExit(t.main())"]),
    ("agent_bridge", [sys.executable, "-c", "import dgtf_v2.tests_agent_bridge as t;raise SystemExit(t.main())"]),
    ("agent_worker", [sys.executable, "-c", "import dgtf_v2.tests_agent_worker as t;t.main()"]),
    ("agent_repair", [sys.executable, "-c", "import dgtf_v2.tests_agent_repair as t;t.main()"]),
    ("agent_daemon", [sys.executable, "dgtf_v2/tests_agent_daemon.py"]),
]


def main() -> int:
    bad = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        child_env = dict(os.environ)
        child_env["PYTHONUTF8"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"
        futs = {ex.submit(subprocess.run, cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=child_env,
                          timeout=900): name for name, cmd in CHECKS}
        for f in as_completed(futs):
            name = futs[f]
            try:
                r = f.result()
                ok = r.returncode == 0
            except Exception:
                ok = False
                r = None
            print(("PASS " if ok else "FAIL ") + name)
            if not ok:
                bad.append(name)
                if r is not None:
                    print((r.stdout or r.stderr or "")[-800:])
    print("\nFAST GATE PASS %d / FAIL %d" % (len(CHECKS) - len(bad), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
