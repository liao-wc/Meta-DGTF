# -*- coding: utf-8 -*-
"""v1.23.17 真跑：同题 × auto 默认 —— 与 v1.23.16 的 auto 组逐项对照。

★ 对照口径：题面与调用方式完全同上一版（`-c` 一张极简 cfg ⇒ 走引擎**默认值**）。
  所以这一跑量的正是「三个阈值/门槛从 3/3+门槛 → 2/2+四层通用」的净效果。
  v1.23.16 auto 组读数：自然停 3/4 层、截断 1/4、实际停圈 3/4/3/7、
  174 calls / 2,080,311 tokens、sat 触发 5 次、模式 B。
  ★ 预期：sat 间隔 2 ⇒ 检查点更密（第 2/4/6 圈）；soft_max 2 ⇒ 自然安住从第 2 圈
    起可触发；条件 1 对四层通用 ⇒ 修行/研究也有复述/自省的早停出口。
    但历史上 v1.21.48 记录过「间隔 2 ⇒ 研究层 2 圈就停、可判定覆盖率仅 33%」——
    本跑同时盯着这条老风险。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.17.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
ROOT = HERE / "outputs"


def run_one(tag, extra):
    _dir = ROOT / ("_v12317_" + tag)
    _dir.mkdir(parents=True, exist_ok=True)
    _cfg = HERE / ("_v12317_cfg_%s.yaml" % tag)
    _cfg.write_text("output:\n  save_dir: \"%s\"\n"
                    % str(_dir).replace("\\", "/"), encoding="utf-8")
    _log = HERE / ("_v12317_run_%s.log" % tag)
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
    (HERE / "_v12317_realrun_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("汇总已写: _v12317_realrun_summary.json")
