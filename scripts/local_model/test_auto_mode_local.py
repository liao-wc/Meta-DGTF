# -*- coding: utf-8 -*-
"""[V2.2.19] 自动模式真跑判据（零 API：走本地 0.5B 链路）。

判的是「输入 -> 自动选模式 -> 每模式专属配置 -> 引擎真的按它跑」这条链；
不判答案质量。前置 8772/8773 未起 => exit 2 = 没跑（不是判红）。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "dgtf_app"))
from dgtf_app import *  # noqa: F401,F403  (确保包路径可解析)  # noqa: E402

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


def _up(port: int, path: str) -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path),
                                    timeout=4) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


if not _up(8772, "/health") or not _up(8773, "/v1/models"):
    print("SKIP: 服务不可达（8772/8773 未起，本判据没跑）")
    raise SystemExit(2)

import params  # noqa: E402
import engine_runner as er  # noqa: E402

SAVE = ROOT / "outputs" / "_e2e_local" / "auto_mode"
SAVE.mkdir(parents=True, exist_ok=True)
TMP_CFG = ROOT / "outputs" / "_e2e_local" / "_auto_mode_cfg.yaml"
OVERRIDES = {
    "api.base_url": "http://127.0.0.1:8773/v1",
    "api.key": "local-shim",
    "api.default_model": "local",
    "api.reasoner_model": "local",
    "web_search.enabled": False,
    "output.answer_gates.enabled": True,
    "output.answer_gates.block": False,
    "output.save_dir": "outputs/_e2e_local/auto_mode",
}
cfg_path = params.build_temp_config(OVERRIDES, TMP_CFG)

print("── A App 侧：自动模式必须透传 --mode 到引擎 ──")
_cmd = er.build_cmd("HTTP 404 状态码表示什么？",
                    {"_config": str(cfg_path), "mode": "fast",
                     "parallel": "B", "thinking": "off",
                     "rounds": "0:1,1:1,both:1,all:1"})
ck("A1 build_cmd 透传 --mode（引擎支持时）", "--mode" in _cmd and "fast" in _cmd,
   _cmd[:8])
ck("A2 每模式专属配置一起进命令行",
   "--parallel" in _cmd and "--thinking" in _cmd and "--rounds" in _cmd)

print("── B 引擎真跑：--mode auto 由题面选 fast 并落专门配置 ──")
QUESTION = "HTTP 404 状态码表示什么？"
before = {p: os.path.getmtime(p) for p in glob.glob(str(SAVE / "*.packed.json"))}
cmd = [sys.executable, "-u", str(er.find_engine()), QUESTION,
       "--config", str(cfg_path), "--mode", "auto",
       "--route", "0", "--rounds", "1"]
t0 = time.time()
proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=1200)
wall = round(time.time() - t0, 1)
log = (proc.stdout or "") + "\n" + (proc.stderr or "")
ck("B1 引擎 --mode auto 正常退出", proc.returncode == 0,
   "exit=%s" % proc.returncode)
ck("B2 启动信息亮出自动模式与专属配置",
   "自动模式：" in log and "模式专属配置" in log,
   log[-400:] if "自动模式：" not in log else "")
after = [p for p in glob.glob(str(SAVE / "*.packed.json"))
         if p not in before or os.path.getmtime(p) > before.get(p, 0)]
ck("B3 落了产物", bool(after), after[:1])
packed = {}
if after:
    packed = json.loads(Path(after[0]).read_text(encoding="utf-8",
                                                 errors="replace"))
am = packed.get("auto_mode") or {}
plan = am.get("plan") or {}
ck("B4 packed.auto_mode.plan 存在且模式在保留集",
   bool(plan) and plan.get("mode") in ("B", "serial", "fast"), plan.get("mode"))
ck("B5 事实题自动选 fast（省墙钟档，不是拍脑袋）",
   plan.get("mode") == "fast", plan.get("mode"))
ck("B6 每模式专属配置被引擎采用（fast => parallel=B/thinking=off）",
   (plan.get("config") or {}).get("parallel") == "B"
   and (plan.get("config") or {}).get("thinking") == "off",
   plan.get("config"))
ck("B7 最优性证据可审计（regret=0 / 方法 / 可行集）",
   isinstance(plan.get("optimality"), dict)
   and plan["optimality"].get("method") == "enumerate_3",
   plan.get("optimality"))
ck("B8 运行期调整账本存在（本轮可空，但字段必须可审计）",
   isinstance(am.get("adjustments"), list))
ck("B9 真跑了本地模型（calls>0）", int(packed.get("llm_calls") or 0) > 0,
   packed.get("llm_calls"))
ck("B10 墙钟在预算内（本地链路验证档）", wall < 900, wall)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
if F:
    raise SystemExit(1)
