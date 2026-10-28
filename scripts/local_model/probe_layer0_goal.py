# -*- coding: utf-8 -*-
"""[V2.2.12] 修行层（route=0）目标读数的**真实入口**验证。

背景：修行层读数此前结构性读不出（213 包里 211 个 verdict 空白）。
V2.2.12 修了 2pt 口径 + 未测出原因 + goal_now 出口。纯函数判据全绿
不等于在真跑里可达 —— 本探针走 App 真入口（params.build_temp_config +
engine_runner.build_cmd）跑 route=0 / 2 圈，直接验产物：

  P1 views["0"].goal_verdict 非空（有值或「未测出（原因）」）
  P2 读数明细 goal_now 落盘（含 excavate / basis / n_hist）
  P3 恰 2 圈 ⇒ 若有存量，excavate_basis 应为 "2pt"（新口径真被走到）
  P4 产物 provenance 是 V2.2.12（溯源指纹动态推导的连带验证）

本地 0.5B，零 API 成本。验的是「读数通道通」，不是答案质量。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/local_model -> 仓库根
APP_DIR = ROOT / "dgtf_app"
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ROOT / "dgtf_engine"))

import params  # noqa: E402
import engine_runner as er  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("✓ " if ok else "✗ ") + n + (("  — " + str(info)) if info else ""))


# 服务在不在
import urllib.request  # noqa: E402
try:
    urllib.request.urlopen("http://127.0.0.1:8773/health", timeout=5)
    ck("P0 本地适配层（8773）在", True)
except Exception as e:  # noqa: BLE001
    print("❌ 本地服务未起（先起 8772/8773）：", e)
    raise SystemExit(2)

QUESTION = os.environ.get("DGTF_L0_Q") or "水的三态变化有哪些驱动因素"
TMP_CFG = ROOT / "outputs" / "_e2e_local" / "_l0_cfg.yaml"
TMP_CFG.parent.mkdir(parents=True, exist_ok=True)

OVERRIDES = {
    "api.base_url": "http://127.0.0.1:8773/v1",
    "api.key": "local-shim",
    "api.default_model": "local",
    "api.reasoner_model": "local",
    "web_search.enabled": False,
    "api.circuit_breaker.enabled": True,
    "output.answer_gates.enabled": True,
    "output.answer_gates.block": False,
    "output.save_dir": "outputs/_e2e_local",
}
cfg_path = params.build_temp_config(OVERRIDES, TMP_CFG)
ck("P1a App 真入口生成本地档配置", bool(cfg_path) and Path(cfg_path).is_file())

cmd = er.build_cmd(QUESTION, {"_config": str(cfg_path),
                              "route": "0", "rounds": "2"})
ck("P1b 命令指向最高版引擎且带 --config",
   any("Meta-DGTF-V" in c for c in cmd) and "--config" in cmd)

before = {p: os.path.getmtime(p) for p in
          glob.glob(str(ROOT / "outputs" / "_e2e_local" / "*.packed.json"))}
t0 = time.time()
proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=600)
wall = round(time.time() - t0, 1)
print(f"   引擎退出码={proc.returncode} 墙钟={wall}s")
ck("P1c 引擎正常退出", proc.returncode == 0)

after = [p for p in glob.glob(str(ROOT / "outputs" / "_e2e_local" / "*.packed.json"))
         if p not in before or os.path.getmtime(p) > before.get(p, 0)]
ck("P1d 落了新产物", bool(after))
if not after:
    print((proc.stdout or "")[-1500:])
    raise SystemExit(1)

d = json.loads(Path(after[0]).read_text(encoding="utf-8", errors="replace"))
v0 = (d.get("views") or {}).get("0") or {}
gv = str(v0.get("goal_verdict") or "").strip()
ck("P2 ★ 修行层 goal_verdict 非空（跑了就有说法 —— 此前 211/213 空白）",
   bool(gv), repr(gv[:70]))
ck("P2b verdict 要么带数值要么带可指认的未测出原因",
   ("=" in gv) and (gv.split("=", 1)[1].strip()[:1].isdigit()
                    or "未测出（" in gv), repr(gv[:70]))

gn = v0.get("goal_now") or {}
ck("P3 ★ 读数明细 goal_now 落盘（含 excavate / basis / n_hist）",
   isinstance(gn, dict) and {"excavate", "excavate_basis", "n_hist"}
   <= set(gn.keys()), str(sorted(gn.keys())))

hist = v0.get("aspect_hist") or []
units = len(v0.get("aspect_units") or [])
basis = gn.get("excavate_basis")
if len(hist) == 2 and units > 0 and hist[0] > 0:
    ck("P4 ★ 恰 2 圈且有存量 ⇒ excavate_basis='2pt'（新口径真被走到）",
       basis == "2pt", f"hist={hist} units={units} basis={basis}")
    ev = gn.get("excavate")
    if ev is not None:
        want = (hist[1] - hist[0]) / hist[0]
        ck("P4b excavate 数值与 hist 一致（ΔV/V）",
           abs(float(ev) - want) < 1e-6, f"{ev} vs {want:.4f}")
elif len(hist) == 2 and (units == 0 or not hist[0]):
    ck("P4 零存量 ⇒ 未测出原因可指认（不冒充挖尽）",
       "未测出" in gv and ("存量为 0" in gv or "无增益" in gv),
       f"hist={hist} units={units} gv={gv[:60]!r}")
else:
    ck("P4 hist 形态记录（供人工复核）", True,
       f"hist={hist} units={units} basis={basis} gv={gv[:50]!r}")

pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
ck("P5 产物 provenance 是 V2.2.12（溯源指纹连带验证）",
   pv == "V2.2.12", pv)

print("─" * 60)
print(f"{len(P)}/{len(P) + len(F)} 通过" + (f"，{len(F)} 项判红" if F else ""))
raise SystemExit(1 if F else 0)
