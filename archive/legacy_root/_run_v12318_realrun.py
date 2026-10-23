# -*- coding: utf-8 -*-
"""v1.23.18 真跑：同题 × auto 默认 × **不带锚点文件** —— 与 v1.23.17 auto 组对照。

★ 量的正是本版的净效果：锚点通道默认打开后，
  产物头部文本通道应写「**开（未挂锚点文件）**」、**不写**「锚点异常」、
  **不写**五行零明细；且**成本不增**（无锚点 = 收尾对照直接早退）。
  v1.23.17 auto 组读数：自然停 4/4、168 calls / 2,039,789 tokens。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.18.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
ROOT = HERE / "outputs"


def run_one(tag, extra):
    _dir = ROOT / ("_v12318_" + tag)
    _dir.mkdir(parents=True, exist_ok=True)
    _cfg = HERE / ("_v12318_cfg_%s.yaml" % tag)
    _cfg.write_text("output:\n  save_dir: \"%s\"\n"
                    % str(_dir).replace("\\", "/"), encoding="utf-8")
    _log = HERE / ("_v12318_run_%s.log" % tag)
    cmd = [sys.executable, str(ENGINE), "-c", str(_cfg)] + extra + [Q]
    t0 = time.time()
    print("=== [%s] 起跑（auto 默认，不带锚点文件）===" % tag, flush=True)
    with open(_log, "w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            cwd=str(HERE)).returncode
    dt = time.time() - t0
    print("=== [%s] 完成 rc=%d 用时 %.0fs ===" % (tag, rc, dt), flush=True)
    return {"group": tag, "rc": rc, "secs": round(dt, 1), "args": extra,
            "dir": str(_dir.relative_to(HERE))}


if __name__ == "__main__":
    rows = [run_one("auto", [])]
    (HERE / "_v12318_realrun_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("汇总已写: _v12318_realrun_summary.json")
