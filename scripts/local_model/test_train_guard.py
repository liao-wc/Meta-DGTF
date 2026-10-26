# -*- coding: utf-8 -*-
"""训练防错训守卫判据（Round 118，零 GPU/零 API）。

L1：out 名含 05b 但 base 模型非 0.5B ⇒ 训练脚本拒绝（exit 2）。
L2：显式 --allow-model-mismatch 时 dry-run 可继续（DRY_RUN_OK）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PY = ROOT / "local_model" / "envs" / "dgtf_llm_env" / "Scripts" / "python.exe"
TRAIN = ROOT / "scripts" / "local_model" / "train_dgtf_stage_lora.py"
PY = PY if PY.exists() else Path(sys.executable)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def _run(args, timeout=180):
    env = dict(__import__("os").environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([str(PY), "-u", str(TRAIN)] + args, cwd=str(ROOT),
                       env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    out = "llm_sft/adapter_dgtf_selfcheck_05b_guardtest"
    code, txt = _run(["--stage", "self_check", "--variant", "min",
                      "--out", out, "--dry-run"])
    ck("L1 05b 输出 + 非 0.5B base ⇒ 拒绝（exit 2）",
       code == 2 and "拒绝训练" in txt, (code, txt[-160:]))

    code2, txt2 = _run(["--stage", "self_check", "--variant", "min",
                        "--out", out, "--dry-run",
                        "--allow-model-mismatch"])
    ck("L2 --allow-model-mismatch ⇒ dry-run 通过",
       code2 == 0 and "DRY_RUN_OK" in txt2, (code2, txt2[-160:]))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
