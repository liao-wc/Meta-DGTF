# -*- coding: utf-8 -*-
"""v1.23.15 真跑（补充组）：只跑 `auto` 默认路径 —— 验证统一调度器在真跑里生效。

★ 起这个 runner 的原因：主实验（`_run_v12315_uppers.py`）的组序是
  up2 → up6 → up10 → auto，而 `auto` 在最后；up10（四层 × 10 圈）成本最高、
  边际价值最低。这里**并行**先把 `auto` 跑出来（独立目录，互不干扰），
  主实验跑到 up10 时直接停掉。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.14.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
ROOT = HERE / "outputs"

def run_one(tag, extra):
    _dir = ROOT / ("_v12315_" + tag)
    _dir.mkdir(parents=True, exist_ok=True)
    _cfg = HERE / ("_v12315_cfg_%s.yaml" % tag)
    _cfg.write_text("output:\n  save_dir: \"%s\"\n"
                    % str(_dir).replace("\\", "/"), encoding="utf-8")
    _log = HERE / ("_v12315_run_%s.log" % tag)
    cmd = [sys.executable, str(ENGINE), "-c", str(_cfg)] + extra + [Q]
    t0 = time.time()
    print("=== [%s] 起跑（auto 默认）===" % tag, flush=True)
    with open(_log, "w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            cwd=str(HERE)).returncode
    dt = time.time() - t0
    print("=== [%s] 完成 rc=%d 用时 %.0fs ===" % (tag, rc, dt), flush=True)
    return {"group": tag, "rc": rc, "secs": round(dt, 1), "args": extra,
            "dir": str(_dir.relative_to(HERE))}


if __name__ == "__main__":
    rows = [run_one("auto", []), run_one("up6", [
        "--route", "0,1,both,all", "--rounds", "0:6,1:6,both:6,all:6",
        "--parallel", "serial", "--profile", "economy", "--web", "off",
        "--orientation", "decision", "--landing", "decision"])]
    (HERE / "_v12315_realrun_summary_b.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("汇总已写: _v12315_realrun_summary_b.json")
