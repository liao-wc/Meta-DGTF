# -*- coding: utf-8 -*-
"""v8b/候选适配器：一键评测 + 与基线对比（Round 75）。

训练完成后运行：
  python scripts/local_model/eval_and_compare.py \
      --adapter llm_sft/adapter_dgtf_selfcheck_05b_v8b \
      --out llm_sft/eval_dgtf_stage_05b_v8b_limit30.json \
      --baseline llm_sft/eval_dgtf_stage_05b_v6_limit30.json \
      --limit-scmin 30

行为：用 DGTF_LOCAL_ADAPTER 指定候选跑 eval_dgtf_stage.py（30 条 held-out），
再用 compare_eval.py 对比基线；退出码即 compare 的判定（0=SWITCH_CANDIDATE）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent if (
    Path(__file__).resolve().parent.name == "local_model") else (
        Path(__file__).resolve().parent.parent)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--limit-scmin", type=int, default=30)
    args = ap.parse_args()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["DGTF_LOCAL_ADAPTER"] = args.adapter
    eval_py = (ROOT / "local_model" / "envs" / "dgtf_llm_env" / "Scripts"
               / "python.exe")
    py = str(eval_py) if eval_py.exists() else sys.executable
    cmd = [py, str(ROOT / "scripts" / "local_model" / "eval_dgtf_stage.py"),
           "--limit-scmin", str(args.limit_scmin), "--out", args.out]
    print("[eval] adapter =", args.adapter)
    print("[eval] cmd =", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=3600)
    if r.returncode != 0:
        # eval 脚本末尾的附加评测偶发 OOM，但 JSON 已写出时仍可对比
        out = Path(args.out)
        if not out.exists():
            print("[eval] FAILED (exit=%d) and no output" % r.returncode)
            return 2
        print("[eval] eval 脚本非零退出，但输出已存在，继续对比")
    cmp_cmd = [sys.executable,
               str(ROOT / "scripts" / "local_model" / "compare_eval.py"),
               str(Path(args.out)), str(Path(args.baseline))]
    print("[compare]", " ".join(cmp_cmd))
    return subprocess.run(cmp_cmd, cwd=str(ROOT), env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
