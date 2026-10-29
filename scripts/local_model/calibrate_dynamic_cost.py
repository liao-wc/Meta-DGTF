# -*- coding: utf-8 -*-
"""[V2.2.26] 动态成本模型校准：路线子集 × 圈数 的有界云端实测（3 臂）。

用途：dynamic_config 目前按整单四层估算（偏保守）。本脚本用最小配置实测：
  R1 route=1, rounds=1（单层 1 圈）
  R2 route=0,1, rounds=1（两层各 1 圈）
  R3 route=0, rounds=2（单层 2 圈，验证圈数线性）
每臂 max_tokens=150000 / fast / web off / thinking off / parallel B，成本有界（合计约 ¥0.3）。
证据：docs/dynamic_cost_calibration_20261029.json
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVE = ROOT / "outputs" / "_e2e_local" / "cost_calib"
SAVE.mkdir(parents=True, exist_ok=True)
CFG = ROOT / "outputs" / "_e2e_local" / "cost_calib_config.yaml"
QUESTION = "成年人正常心率是多少次每分钟？"
ENGINE = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.26.py"
ARMS = [
    ("R1_route1_r1", "1", "1"),
    ("R2_route01_r1", "0,1", "0:1,1:1"),
    ("R3_route0_r2", "0", "0:2"),
]


def main():
    src = (ROOT / "dgtf_config.yaml").read_text(encoding="utf-8")
    old = '  save_dir: "outputs"'
    assert src.count(old) == 1
    CFG.write_text(src.replace(
        old, '  save_dir: "outputs/_e2e_local/cost_calib"'), encoding="utf-8")
    rows = []
    t_all = time.time()
    for name, route, rounds in ARMS:
        before = set(glob.glob(str(SAVE / "*.packed.json")))
        cmd = [sys.executable, "-u", str(ENGINE), QUESTION,
               "--config", str(CFG), "--route", route, "--rounds", rounds,
               "--parallel", "B", "--thinking", "off", "--mode", "fast",
               "--web", "off", "--max-tokens", "150000", "--quiet"]
        t0 = time.time()
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        wall = round(time.time() - t0, 1)
        new = [p for p in glob.glob(str(SAVE / "*.packed.json"))
               if p not in before]
        d = {}
        if new:
            d = json.loads(Path(sorted(new, key=os.path.getmtime)[-1])
                           .read_text(encoding="utf-8", errors="replace"))
        row = {"arm": name, "route": route, "rounds": rounds,
               "rc": r.returncode, "wall_s": wall,
               "llm_calls": d.get("llm_calls"),
               "tokens": d.get("llm_tokens"),
               "est_cost_cny": round((d.get("llm_tokens") or 0) / 1e6 * 2.0, 3),
               "answer_quality": (d.get("quality") or {}).get("answer_quality"),
               "packed": Path(new[0]).name if new else ""}
        rows.append(row)
        print("[calib]", json.dumps(row, ensure_ascii=False), flush=True)
    # 拟合：u0 取 R3/2（圈数线性假设的校验），u1 取 R1；R2 用于验证可加性
    r0 = next(x for x in rows if x["arm"].startswith("R3"))
    r1 = next(x for x in rows if x["arm"].startswith("R1"))
    r2 = next(x for x in rows if x["arm"].startswith("R2"))
    u0 = round((r0.get("tokens") or 0) / 2.0, 1)
    u1 = float(r1.get("tokens") or 0)
    additive_pred = round(u0 + u1, 1)
    additive_err = round((additive_pred - (r2.get("tokens") or 0))
                         / max(1.0, float(r2.get("tokens") or 1)), 3)
    out = {"schema": "metadgtf.dynamic_cost_calibration.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": QUESTION, "engine": ENGINE.name,
           "fixed": {"parallel": "B", "thinking": "off", "mode": "fast",
                     "web": "off", "max_tokens": 150000},
           "arms": rows,
           "fit": {"u0_per_round": u0, "u1_per_round": u1,
                   "two_layer_pred": additive_pred,
                   "two_layer_actual": r2.get("tokens"),
                   "additivity_err": additive_err,
                   "note": "fast/web-off 单层单圈口径；both/all 单位由整单实测反解（见 dynamic_config）"},
           "total_wall_s": round(time.time() - t_all, 1),
           "total_est_cost_cny": round(sum(x.get("est_cost_cny") or 0
                                           for x in rows), 3)}
    (ROOT / "docs" / "dynamic_cost_calibration_20261029.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fit:", json.dumps(out["fit"], ensure_ascii=False))
    print("evidence -> docs/dynamic_cost_calibration_20261029.json")
    bad = [x for x in rows if x["rc"] != 0 or not x["tokens"]]
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
