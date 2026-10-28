# -*- coding: utf-8 -*-
"""APP → 引擎 → 本地模型 端到端判据（零 API 成本）。

为什么需要它
------------
项目此前有三段链路验证，但**三段之间从未连起来跑通过**：

  · 引擎单测（`run_v2_tests`）：打桩 LLM，不碰真实推理服务
  · 本地服务判据（`judge_fastfail` / `generate_batch` / `graph_decode`）：
    只测服务自身，不经过引擎
  · App 判据（`selftest.py`）：静态源码扫描，不跑引擎

⇒ 结果是「`answer_gates` 的静态接线判据全绿，但**真实出口从来没被验证过**」
   （按项目规矩：**纯函数判据全绿 ≠ 能力在引擎里可达**）。

本脚本把三段接起来，并且**走 App 的真实入口**：
  `params.build_temp_config()`（App 生成任务配置）+ `engine_runner.build_cmd()`
  （App 拼命令行）→ 子进程跑引擎 → 引擎经 shim 调本地 0.5B → 产物落盘。

判的是「链路通 + 读数不空 + 结构完整」，**不是质量**：本地 0.5B 的答案质量
远低于云模型，产物里的答案内容不能当质量指标看。
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
APP_DIR = ROOT / "dgtf_app"

FAILS: list[str] = []
N = [0]


def check(name: str, cond: bool, detail: str = "") -> None:
    N[0] += 1
    if not cond:
        FAILS.append(f"✗ {name}" + (f" — {detail}" if detail else ""))
        print(f"✗ {name}" + (f" — {detail}" if detail else ""), flush=True)
    else:
        print(f"✓ {name}", flush=True)


def _up(port: int, path: str) -> bool:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=4) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# ───────────────────── 前置：两段服务必须在 ─────────────────────
# ★ 「没跑」和「跑了判红」必须分得开：前置不满足就**显式告警并退出非零**，
#   不许静默变绿。
if not _up(8772, "/health"):
    print("⚠ 本地推理服务 8772 未起，本判据无法执行（不是判红，是没跑）")
    sys.exit(2)
if not _up(8773, "/v1/models"):
    print("⚠ OpenAI 适配层 8773 未起，本判据无法执行（不是判红，是没跑）")
    sys.exit(2)
check("E1 两段本地服务都在（8772 推理 + 8773 适配）", True)

# ───────────────────── 走 App 真实入口构造配置与命令行 ─────────────────────
sys.path.insert(0, str(APP_DIR))
import params  # noqa: E402
import engine_runner as er  # noqa: E402

QUESTION = os.environ.get("DGTF_E2E_Q") or "成年人正常心率是多少次每分钟"
TMP_CFG = ROOT / "outputs" / "_e2e_local_cfg.yaml"
TMP_CFG.parent.mkdir(parents=True, exist_ok=True)

OVERRIDES = {
    "api.base_url": "http://127.0.0.1:8773/v1",
    "api.key": "local-shim",
    "api.default_model": "local",
    "api.reasoner_model": "local",
    "web_search.enabled": False,
    "api.circuit_breaker.enabled": True,
    "output.answer_gates.enabled": True,
    # ★ 本地档只留痕不阻断：链路验证要的是「读数在」，不是「判得准」
    "output.answer_gates.block": False,
    # ★ e2e 产物独立落盘：它们是「链路验证」样本（本地 0.5B，不代表生产质量），
    #   不能混进 outputs/*.packed.json 的生产质量统计（一致性护栏只扫该 glob）。
    "output.save_dir": "outputs/_e2e_local",
}
cfg_path = params.build_temp_config(OVERRIDES, TMP_CFG)
check("E2 App 的 `params.build_temp_config()` 生成了本地档配置",
      bool(cfg_path) and Path(cfg_path).is_file(), str(cfg_path))

if not cfg_path:
    print("⚠ 配置生成失败，中止")
    sys.exit(1)

_cfg_txt = Path(cfg_path).read_text(encoding="utf-8", errors="replace")
check("E3 生成本地档确实指向 8773 适配层（覆盖生效，不是出厂值）",
      "127.0.0.1:8773" in _cfg_txt)

cmd = er.build_cmd(QUESTION, {"_config": str(cfg_path), "route": "1",
                              "rounds": "1"})
check("E4 App 的 `engine_runner.build_cmd()` 拼出的命令带 `--config`",
      "--config" in cmd and str(cfg_path) in " ".join(cmd))
check("E5 命令指向的是引擎目录里**最高版本**（App 自动选版）",
      any("Meta-DGTF-V" in c for c in cmd),
      " ".join(cmd[:4]))

# ───────────────────── 真跑 ─────────────────────
before = {p: os.path.getmtime(p) for p in
          glob.glob(str(ROOT / "outputs" / "_e2e_local" / "*.packed.json"))}
t0 = time.time()
proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                      text=True, encoding="utf-8", errors="replace",
                      timeout=int(os.environ.get("DGTF_E2E_TIMEOUT") or 900))
wall = round(time.time() - t0, 1)
log = (proc.stdout or "") + (proc.stderr or "")
print(f"   引擎退出码={proc.returncode} 墙钟={wall}s "
      f"调用数(日志)={log.count('chat/completions')}", flush=True)

check("E6 引擎跑完并正常退出（不是被超时杀掉）", proc.returncode == 0,
      f"exit={proc.returncode}")

after = [p for p in glob.glob(str(ROOT / "outputs" / "_e2e_local" / "*.packed.json"))
         if p not in before or os.path.getmtime(p) > before.get(p, 0)]
check("E7 落了新产物（链路真的走到底，而不是中途断了）", bool(after),
      f"新产物 {len(after)} 个")
check("E7b ★ e2e 产物落在独立目录（不污染生产质量统计）",
      all("_e2e_local" in p for p in after) and bool(after),
      str([os.path.basename(p) for p in after][:2]))

packed = {}
if after:
    packed = json.loads(Path(after[0]).read_text(encoding="utf-8",
                                                 errors="replace"))

# ───────────────────── 产物判据：读数真的出得来 ─────────────────────
q = packed.get("quality") or {}
ag = q.get("answer_gates") or {}
check("E8 ★ 真实入口产物里有 `quality.answer_gates`（此前只有静态接线判据）",
      bool(ag), f"quality 键 = {sorted(q.keys())[:8]}")
check("E9 answer_gates 的读数非空（有 relevance 与 agreement 两个维度）",
      "relevance" in ag and "agreement" in ag, str(sorted(ag.keys())))
check("E10 relevance 给了分档结论（不是空壳）",
      str((ag.get("relevance") or {}).get("verdict") or "") != "",
      str(ag.get("relevance")))

# ★ [真实入口证明] V2.2.11 修的是「answer_ready_reason 只有 1 个出口」：
#   answer_ready 有 3 个出口，reason 此前只写进 decision_trace ⇒ 读 quality 的
#   消费者永远看不见「为什么没就绪」。纯函数/静态判据全绿不等于在真跑里可达，
#   所以这条必须由**真跑产物**来证明。
_ready = q.get("answer_ready")
_reason = str(q.get("answer_ready_reason") or "").strip()
_dt_reason = str(((packed.get("decision_trace") or {})
                 .get("answer_ready_reason")) or "").strip()
check("E10b ★ 真跑产物里 `quality.answer_ready_reason` 出口存在且非空"
      "（未就绪必须给原因，不能留空）",
      (_ready is not True) and bool(_reason),
      f"answer_ready={_ready} reason={_reason[:60]!r}")
check("E10c 三出口同源：quality / decision_trace / answer_summary 的就绪原因一致",
      _reason == _dt_reason
      and _reason == str((packed.get("answer_summary") or {})
                         .get("answer_ready_reason") or "").strip(),
      f"q={_reason[:40]!r} dt={_dt_reason[:40]!r}")

#: `llm_by_stage` 在产物里**两种形态都出现过**（dict 桶 / list 明细），
#: 判据必须两种都认 —— 只认一种会在换形态时假红。
def _stage_rows(by):
    if isinstance(by, dict):
        return [{"stage": k, **(v if isinstance(v, dict) else {"calls": v})}
                for k, v in by.items()]
    return [x for x in (by or []) if isinstance(x, dict)]


rows = _stage_rows(packed.get("llm_by_stage") or {})
unknown = next((r for r in rows if r.get("stage") == "unknown"), None)
check("E11 ★ 成本归因无盲区：没有 `unknown` 桶（所有调用都带 stage）",
      unknown is None, f"unknown = {unknown}")
check("E12 成本归因桶非空（本地模型确实被调用了）",
      bool(rows), f"桶 = {sorted(r.get('stage') for r in rows)[:8]}")

# ★ 熔断留痕出口：默认配置下不该触发，但**字段必须存在**——
#   否则真出故障时会误判成「熔断没工作」，实际是「读数没出口」。
check("E13 熔断留痕字段在产物里（llm_cb_opened / llm_cb_skipped）",
      "llm_cb_opened" in packed and "llm_cb_skipped" in packed,
      f"实际键 = {sorted(k for k in packed if 'cb' in k)}")

calls = packed.get("llm_calls") or packed.get("calls")
check("E14 调用计数 > 0（本地模型真的被调了，不是空跑）",
      isinstance(calls, int) and calls > 0, f"llm_calls = {calls}")

# ★ 成本判据：省钱改动必须有「省钱真发生」的对照，否则会悄悄退化回去。
#   max_new 压缩前：第 4 次调用就 110s 撞超时；压缩后整跑应远快于此。
check("E15 ★ 成本：整跑墙钟在预算内（压缩前单次调用就要 110s）",
      wall < float(os.environ.get("DGTF_E2E_WALL_CAP") or 600),
      f"墙钟 {wall}s")

# 写证据
OUT = ROOT / "docs" / "e2e_app_local_latest.json"
try:
    OUT.write_text(json.dumps({
        "ok": not FAILS, "question": QUESTION, "wall_sec": wall,
        "exit": proc.returncode, "packed": str(after[0]) if after else "",
        "quality_keys": sorted(q.keys()),
        "answer_gates": ag,
        "llm_by_stage": rows,
        "llm_calls": calls,
        "checks": N[0], "fails": FAILS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   证据 → {OUT}")
except OSError as e:
    print(f"⚠ 证据写入失败：{e}")

print("─" * 60)
print(f"{N[0] - len(FAILS)}/{N[0]} 通过" + (f"，{len(FAILS)} 项判红" if FAILS else ""))
sys.exit(1 if FAILS else 0)
