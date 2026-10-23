# -*- coding: utf-8 -*-
"""v1.23.16 真跑：同题 × auto 默认路径 —— 与 v1.23.15 的 auto 组逐项对照。

★ 对照口径（必须同题、同调用方式）：
   题面 = v1.23.15 auto 组那条（老城区暴雨内涝权衡题）
   调用 = 不传任何调度参数（走 auto 十一项）
  v1.23.15 auto 组读数：自然停 1/4 层、截断 3/4、193 calls / 2,420,429 tokens、
  模式 B、联网收 24 条。
  ★ 本版预期：删档后不再有「候选截断 / shape 缩放 / 低频惰性化 / 探针按角色跳」，
    且 sat 判定对四层同等生效 ⇒ **自然停层数应上升**（这是治本的疗效判据）。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.16.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
ROOT = HERE / "outputs"


def run_one(tag, extra):
    _dir = ROOT / ("_v12316_" + tag)
    _dir.mkdir(parents=True, exist_ok=True)
    _cfg = HERE / ("_v12316_cfg_%s.yaml" % tag)
    _cfg.write_text("output:\n  save_dir: \"%s\"\n"
                    % str(_dir).replace("\\", "/"), encoding="utf-8")
    _log = HERE / ("_v12316_run_%s.log" % tag)
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
    rows = [run_one("auto", [])]
    (HERE / "_v12316_realrun_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("汇总已写: _v12316_realrun_summary.json")
