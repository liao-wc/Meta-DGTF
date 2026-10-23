# -*- coding: utf-8 -*-
"""v1.23.15 真跑对照实验：同题 × 全四层 × 不同圈数上限 + 一次 auto 默认。

【要回答的问题】
  ① 「停止行为」样本：自然停 vs 被截断，随**上限**怎么变？（语料里只有 5 层样本）
  ② 「上限给多少最省」：同一题不同上限下的实际停圈 / 成本 / 截断率
  ③ v1.23.13/14 新加的渲染行（**自动调度**表 / **实际停圈** / **外部锚点 · 联网**）
     在真跑产物里是否真的出现
  ④ 联网侧失败/空结果样本（语料里 0 次）

【设计】同题、同模式（serial）、同 route（全四层），只改 `--rounds`：
  · 上限 2  → 预期四层全被截断（停止判据需累计 2 轮）
  · 上限 6  → 预期部分层自然停
  · 上限 10 → 预期更多层自然停（「上限最省」的对照上界）
  · auto    → 不传任何参数：验证统一调度器 + 联网行
每组写**独立目录**（outputs/_v12315_<组>/），互不覆盖、又都进历史语料。

★ stdout 直写日志文件（不用 capture_output）—— 长跑要能 tail。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.14.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"

GROUPS = [
    ("up2", ["--route", "0,1,both,all", "--rounds", "0:2,1:2,both:2,all:2",
             "--parallel", "serial", "--profile", "economy", "--web", "off",
             "--orientation", "decision", "--landing", "decision"]),
    ("up6", ["--route", "0,1,both,all", "--rounds", "0:6,1:6,both:6,all:6",
             "--parallel", "serial", "--profile", "economy", "--web", "off",
             "--orientation", "decision", "--landing", "decision"]),
    ("up10", ["--route", "0,1,both,all", "--rounds", "0:10,1:10,both:10,all:10",
              "--parallel", "serial", "--profile", "economy", "--web", "off",
              "--orientation", "decision", "--landing", "decision"]),
    ("auto", []),
]

ROOT = HERE / "outputs"
SUMMARY = HERE / "_v12315_realrun_summary.json"


def main():
    rows = []
    for tag, extra in GROUPS:
        _dir = ROOT / ("_v12315_" + tag)
        _dir.mkdir(parents=True, exist_ok=True)
        _cfg = HERE / ("_v12315_cfg_%s.yaml" % tag)
        _cfg.write_text(
            "output:\n  save_dir: \"%s\"\n" % str(_dir).replace("\\", "/"),
            encoding="utf-8")
        _log = HERE / ("_v12315_run_%s.log" % tag)
        cmd = [sys.executable, str(ENGINE), "-c", str(_cfg)] + extra + [Q]
        t0 = time.time()
        print("=== [%s] 起跑：%s" % (tag, " ".join(extra) or "（全 auto）"))
        with open(_log, "w", encoding="utf-8", errors="replace") as fh:
            rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                cwd=str(HERE)).returncode
        dt = time.time() - t0
        _txt = _log.read_text(encoding="utf-8", errors="replace")
        rows.append({"group": tag, "rc": rc, "secs": round(dt, 1),
                     "args": extra, "log": _log.name,
                     "dir": str(_dir.relative_to(HERE))})
        print("=== [%s] 完成 rc=%d 用时 %.0fs" % (tag, rc, dt))
    SUMMARY.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print("汇总已写:", SUMMARY.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
