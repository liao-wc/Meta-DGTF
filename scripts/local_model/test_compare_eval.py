# -*- coding: utf-8 -*-
"""compare_eval.py 的自检（Round 68，零 API）：判定逻辑/两种 JSON 结构回归。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "local_model" / "compare_eval.py"

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def _run(cand: dict, base: dict):
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "cand.json"
        bp = Path(td) / "base.json"
        cp.write_text(json.dumps(cand), encoding="utf-8")
        bp.write_text(json.dumps(base), encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), str(cp), str(bp)],
                           capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout


def _metrics(field=0.5, esc=0.5, f1=0.2, p50=6000, p95=8000):
    return {"json_valid_rate": 1.0, "decision_field_mean_acc": field,
            "unsaid_is_escape_acc": esc, "susp_f1": f1,
            "ing_rephrased_acc": 0.9, "decision_all3_acc": 0.0,
            "susp_set_acc": 0.0,
            "latency_ms": {"p50": p50, "p95": p95}}


def main() -> int:
    # ① 候选全面更好 → SWITCH_CANDIDATE
    code, out = _run({"adapter": _metrics(field=0.6, esc=0.8, p50=5800)},
                     {"adapter": _metrics()})
    ck("① 全面更优 → exit 0 / SWITCH_CANDIDATE",
       code == 0 and "SWITCH_CANDIDATE" in out, (code, out[-120:]))

    # ② 候选某项明显变差 → KEEP_BASELINE
    code, out = _run({"adapter": _metrics(field=0.2)}, {"adapter": _metrics()})
    ck("② 字段明显变差 → exit 1 / KEEP_BASELINE",
       code == 1 and "KEEP_BASELINE" in out, (code, out[-120:]))

    # ③ 噪声容差：suspF1 -0.01 不算变差
    code, out = _run({"adapter": _metrics(f1=0.19, field=0.55)},
                     {"adapter": _metrics()})
    ck("③ suspF1 −0.01 在噪声内（不阻断切换）", code == 0, (code, out[-160:]))

    # ④ 新版 stages 字典结构可解析
    code, out = _run({"stages": {"self_check_min": _metrics(field=0.6)}},
                     {"stages": {"self_check_min": _metrics()}})
    ck("④ stages 字典结构 → 可比较（SWITCH）",
       code == 0 and "0.6000" in out, (code, out[-160:]))

    # ⑤ 结构无法解析 → 不崩溃（KEEP_BASELINE）
    code, out = _run({"foo": 1}, {"bar": 2})
    ck("⑤ 未知结构 → 不崩溃且 KEEP_BASELINE",
       code == 1 and "KEEP_BASELINE" in out, (code, out[-80:]))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
