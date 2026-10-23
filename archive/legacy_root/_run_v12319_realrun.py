# -*- coding: utf-8 -*-
"""v1.23.19 真跑：同题 × `retriever: "tavily"` —— 验证修好的那条路端到端。

★ 默认路径（`retriever: "snapshot"`）**不重复跑**：本版对它逐字不变 ——
  早退条件只是把「已有锚点」这一项挪到模式分流之后，snapshot 模式下两支
  结果相同（探针 `B_snapshot_*` 前后一致）。所以只跑**真检索那一态**。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.19.py"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"
ROOT = HERE / "outputs"

CFG = """output:
  save_dir: "{d}"
external_anchor:
  enabled: true
  retriever: "tavily"
  path: ""
"""


def run_one(tag, extra):
    _dir = ROOT / ("_v12319_" + tag)
    _dir.mkdir(parents=True, exist_ok=True)
    _cfg = HERE / ("_v12319_cfg_%s.yaml" % tag)
    _cfg.write_text(CFG.format(d=str(_dir).replace("\\", "/")), encoding="utf-8")
    _log = HERE / ("_v12319_run_%s.log" % tag)
    cmd = [sys.executable, str(ENGINE), "-c", str(_cfg)] + extra + [Q]
    t0 = time.time()
    print("=== [%s] 起跑（retriever=tavily）===" % tag, flush=True)
    with open(_log, "w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            cwd=str(HERE)).returncode
    dt = time.time() - t0
    print("=== [%s] 完成 rc=%d 用时 %.0fs ===" % (tag, rc, dt), flush=True)
    return {"group": tag, "rc": rc, "secs": round(dt, 1), "args": extra,
            "dir": str(_dir.relative_to(HERE))}


if __name__ == "__main__":
    rows = [run_one("tavily", [])]
    (HERE / "_v12319_realrun_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("汇总已写: _v12319_realrun_summary.json")
