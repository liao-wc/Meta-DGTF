# -*- coding: utf-8 -*-
"""四层目标读数的真实入口探针（route=0 / 1 / both / all，每层 rounds=2）。

为什么需要它
-----------
纯函数判据（tests_layer_goal.py）全绿不等于读数在真跑里可达。本探针走 App 的
真实入口：params.build_temp_config()（App 生成任务配置）+ engine_runner.build_cmd()
（App 拼命令行）-> 子进程跑引擎 -> 引擎经 8773 OpenAI 适配层调本地 0.5B ->
产物落盘。逐层断言：

  P1 views[层].goal_verdict 非空，且形态合法（有值 / 未测出（可指认原因））；
  P2 goal_now 落盘，含该层主读数与依据字段（0: basis/n_hist；1: settlement；
     both: n_new/n_upstream；all: n_hits/crystallize_detail）；
  P3 goal_now 与「lead_layer_goal_audit.py 的**独立复算**」逐字段一致（读数可复现；
     复算为审计脚本内的独立实现，**不 import 引擎 layer_goal_readings/_lg_***
     —— 引擎改了公式、落盘还是旧值，自己校验自己永远绿，所以必须独立实现）；
  P4 同层连续两圈：goal_trace 条数 = rounds_run、圈号严格递增、每圈含主读数键；
  P5 verdict 与 goal_now 同源（数值一致 / 同为未测出且有原因）；
  P6 provenance.engine_version = 引擎目录里最高版（App 自动选版的连带验证）；
  P7 目标判定可解释：达成 / 受阻 / 未达成 / 判据样本不足 / 未测出（原因非空）
     —— 这是**读数报告**，不要求目标必须达成（达成与否是模型能力，不是接线）。

三态退出码（区分「没跑」与「判红」）
------------------------------------
  0 = 四个 case 全部通过：读数通道通、形态合法、可复算；
  1 = 判红：真跑发生了（有 LLM 调用、产物落盘），但上述接线/形态断言失败；
  2 = 没跑/没跑通：服务未起、配置/命令构造失败、产物未落盘、零 LLM 调用
      （四层自动调度白跑）、目标层被引擎调度跳过。**没跑 != 通过，也 != 判红。**
      ★ 零 LLM 产物额外过「零 LLM 判据」：跑过的层 verdict 必须非空、未测出必须带
      可指认原因、**不许判「达成」**（没调用就没证据）。判据不成立 => **判红(1)**，
      而不是记「没跑」；判据成立 => 记「没跑(2)」，避免 12:55 shim 死掉那类跑次
      被读成「模型能力不足」或「挖尽」。

GPU 规则：本脚本会真跑本地模型，只在 Lead 给的 GPU 窗口里执行。
--dry-run 只打印将执行的命令 + 自检命令拼接，不建配置、不跑子进程；
只对 8772/8773 发只读 /health 探活而不发任何推理请求。dry-run 还会静态核对
「复算实现独立」（不出现引擎内部函数名）这条判据自身没有退化成 import 引擎。

用法
----
  python scripts/local_model/probe_layer_goals.py --dry-run
  python scripts/local_model/probe_layer_goals.py                  # 四个 case 全跑
  python scripts/local_model/probe_layer_goals.py --only 0,1
  python scripts/local_model/probe_layer_goals.py --rounds 2 --timeout 900
  python scripts/local_model/probe_layer_goals.py --evidence outputs/_e2e_local/_layer_goals_probe.json

route=both / route=all 为什么带上游
----------------------------------
引擎的调度计划里 both 依赖 0、1（_ENTRY_DEPS），all 需要至少 2 个上游 view
（_ENTRY_MIN_UPSTREAM），单跑 both/all 会被判「上游不足」直接跳过 -> 目标层根本
不跑。所以本探针的 case 是：0 / 1 / 0,1,both / 0,1,all。
"""
from __future__ import annotations

from _serial_lock import acquire_serial_lock  # [V2.2.59] 串行锁
_SERIAL_LOCK = acquire_serial_lock("local_chain")

import argparse
import glob
import inspect
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # scripts/local_model -> 仓库根
APP_DIR = ROOT / "dgtf_app"
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(SCRIPTS_DIR))

import params  # noqa: E402
import engine_runner as er  # noqa: E402
# 单一口径来源：verdict 解析 / 目标判定 / 离线复算加载器都复用审计脚本，
# 不在探针里另写一份（同一语义两处定义迟早漂移）。
import lead_layer_goal_audit as lga  # noqa: E402

SAVE_DIR = ROOT / "outputs" / "_e2e_local"
CFG_PATH = SAVE_DIR / "_layer_goals_cfg.yaml"
EVIDENCE_DEFAULT = SAVE_DIR / "_layer_goals_probe_latest.json"

PASS, FAIL = [], []
NOT_RUN = []      # 没跑/没跑通（不是判红）


def ck(name: str, ok: bool, info: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(("✓ " if ok else "✗ ") + name + (("  — " + str(info)) if info else ""),
          flush=True)


def note_not_run(name: str, why: str) -> None:
    NOT_RUN.append(name)
    print("⚠ 没跑：" + name + " — " + why, flush=True)


def _up(port: int, path: str) -> bool:
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (port, path), timeout=4) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _health(port: int, path: str):
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (port, path), timeout=4) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def _new_packs(before: dict) -> list:
    out = []
    for p in glob.glob(str(SAVE_DIR / "*.packed.json")):
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        b = before.get(p)
        if b is None or m > b + 1e-6:
            out.append((m, p))
    out.sort(reverse=True)
    return [p for _, p in out]


def _shape_ok(v) -> bool:
    """读数形态：None 或 [0,1] 内数值（bool 不算数）。"""
    num = lga._num(v)
    return num is None or (0.0 <= num <= 1.0)


CASES = [
    {"id": "0", "route": "0", "target": ["0"],
     "why": "修行层单跑"},
    # ★ [V2.2.67] 研究层需要上游层0：route=1 单跑时 candidates=0、settlement.total=0；
    #   route=0,1 时 candidates>0、settle 有值。3 圈才能让「连续不涨」可判定。
    {"id": "1", "route": "0,1", "target": ["1"],
     "question": "2025年全球主要经济体的GDP增速分别是多少？",
     "why": "研究层需上游层0 + 可生成候选的题面（原题面无候选）"},
    {"id": "both", "route": "0,1,both", "target": ["both"],
     "why": "对撞层依赖上游 0/1（_ENTRY_DEPS）；单跑 both 会被调度跳过"},
    {"id": "all", "route": "0,1,all", "target": ["all"],
     "why": "元层需 >=2 个上游 view（_ENTRY_MIN_UPSTREAM all=2）"},
]


# ─────────────────────────── 单 case 断言 ───────────────────────────
def check_target_layer(case: str, L: str, d: dict, pack_path: Path,
                       eng, want_rounds: int) -> dict:
    """对一个「确实跑了的」目标层做读数/形态/可复算断言，返回证据行。"""
    checks = []
    view = ((d.get("views") or {}).get(L) or {})
    main_key = eng._LG_KEYS[L]
    info = {"case": case, "layer": L, "pack": str(pack_path),
            "checks": checks, "target_status": None, "main_value": None,
            "verdict": "", "trace": [], "goal_now": {}}

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
        ck("%s/%s %s" % (case, L, name), ok, detail)

    # P2a goal_now 落盘
    gn = view.get("goal_now")
    ok_gn = isinstance(gn, dict) and bool(gn)
    add("P2 goal_now 落盘", ok_gn,
        json.dumps(gn, ensure_ascii=False)[:150] if ok_gn else "缺 goal_now")
    if not ok_gn:
        return info
    info["goal_now"] = gn
    add("P2b goal_now 含主读数键 %s" % main_key, main_key in gn,
        str(sorted(gn.keys()))[:150])

    # P3 与**独立复算**一致（读数可复现，不是一次性的内存数字）。
    # ★ 复算函数来自审计脚本的独立实现（lead_layer_goal_audit.recompute_layer_goal），
    #   刻意不调用引擎 layer_goal_readings/_lg_* —— 独立实现才有牙。
    try:
        fresh = lga.recompute_layer_goal(view, L)
    except Exception as e:  # noqa: BLE001
        fresh = None
        add("P3 独立复算", False, "%s: %s" % (type(e).__name__, e))
    if fresh is not None:
        same = lga._deep_same(gn, fresh)
        add("P3 goal_now 与独立复算逐字段一致", same,
            "" if same else ("不一致：%s vs %s"
                             % (json.dumps(gn, ensure_ascii=False)[:100],
                                json.dumps(fresh, ensure_ascii=False)[:100])))
        info["recomputed"] = fresh

    # P2c 逐层依据字段（读数「凭什么」）
    req = {
        "0": ["excavate_basis", "n_hist", "n_aspects"],
        "1": ["settle", "non_degenerate"],
        "both": ["n_new", "n_upstream"],
        "all": ["crystallize", "n_hits", "crystallize_detail"],
    }[L]
    miss = [k for k in req if k not in gn]
    add("P2c 依据字段齐 %s" % "/".join(req), not miss, "缺：%s" % miss)
    if L == "0":
        add("P2d 修行层口径标注合法（2pt/halves/None）",
            gn.get("excavate_basis") in ("2pt", "halves", None),
            str(gn.get("excavate_basis")))
        add("P2e 修行层 aspect_hist 逐圈点数 = n_hist",
            isinstance(view.get("aspect_hist"), list)
            and len(view.get("aspect_hist") or []) == gn.get("n_hist"),
            "hist=%s n_hist=%s" % (view.get("aspect_hist"), gn.get("n_hist")))
    if L == "1":
        co = view.get("settlement") or {}
        add("P2d 研究层 settlement 真落盘（answered/total）",
            "answered" in co and "total" in co, str(co)[:120])
    if L == "both":
        add("P2d 对撞层分母来源可见（view.upstream_layers）",
            "upstream_layers" in view, str(view.get("upstream_layers")))

    # P1 verdict 非空 + 形态合法
    pv = lga.parse_verdict(view.get("goal_verdict"))
    info["verdict"] = pv.get("raw", "")
    add("P1 verdict 非空", pv["state"] in ("valued", "unmeasured"),
        "state=%s raw=%s" % (pv["state"], pv.get("raw", "")[:100]))
    if pv["state"] in ("valued", "unmeasured"):
        add("P1b verdict 标签/键与引擎口径一致",
            pv.get("label") == eng._LG_LABELS.get(L)
            and pv.get("key") == main_key,
            "label=%s key=%s" % (pv.get("label"), pv.get("key")))
    if pv["state"] == "unmeasured":
        add("P1c 未测出原因可指认（非空、非「未知」）",
            bool(pv.get("why")) and "未知" not in pv.get("why", ""),
            repr(pv.get("why"))[:120])

    # ★ [V2.2.65] 研究层未测出：结构化归因（settlement.total=0 ⇒ decidability 不可判定）
    if pv["state"] == "unmeasured" and L == "1":
        try:
            _pm = json.loads(pack_path.read_text(encoding="utf-8",
                                                errors="replace"))
        except Exception:  # noqa: BLE001
            _pm = {}
        _co = view.get("settlement") or {}
        _total = int(_co.get("total") or 0)
        _det = {
            "settlement_total": _total,
            "settlement_answered": int(_co.get("answered") or 0),
            "decidability": str((_pm.get("decidability") or {}).get("status")
                                or ""),
            "reason": str(pv.get("why") or ""),
        }
        info["unmeasured_detail"] = _det
        _why_ok = ("settlement.total=0" in _det["reason"]
                   or "settlement.total=0" in str(pv.get("why") or ""))
        add("P2g 未测出归因结构化（settlement.total=0 且原因指向分母为 0）",
            _total == 0 and _why_ok,
            json.dumps(_det, ensure_ascii=False)[:150])

    # P5 verdict 与 goal_now 同源
    main = lga._num(gn.get(main_key))
    info["main_value"] = main
    if pv["state"] == "valued":
        add("P5 verdict 数值与 goal_now 一致",
            main is not None and abs(pv["value"] - main) <= 5e-4,
            "verdict=%s goal_now=%s" % (pv.get("value"), main))
    elif pv["state"] == "unmeasured":
        add("P5 同为未测出（verdict 未测出 => goal_now 主读数 None）",
            main is None, "verdict 未测出但 goal_now=%s" % main)
    add("P2f 主读数形态合法（None 或 [0,1]）", _shape_ok(main), repr(main))

    # P4 同层连续两圈读数形态
    trace = view.get("goal_trace") or []
    info["trace"] = trace
    add("P4 goal_trace 条数 = rounds_run（%d）" % int(view.get("rounds_run") or 0),
        len(trace) == int(view.get("rounds_run") or 0),
        "trace=%d rounds_run=%s" % (len(trace), view.get("rounds_run")))
    rounds = [lga._num((t or {}).get("round")) for t in trace
              if isinstance(t, dict)]
    add("P4b 圈号严格递增 1..N",
        bool(rounds) and [int(x) for x in rounds]
        == list(range(1, len(rounds) + 1)),
        str(rounds))
    row_ok = all(isinstance(t, dict) and main_key in t for t in trace)
    add("P4c 每圈都含主读数键 %s" % main_key, row_ok,
        "缺键圈：" + str([i + 1 for i, t in enumerate(trace)
                          if not (isinstance(t, dict) and main_key in t)]))
    vals_ok = all(_shape_ok((t or {}).get(main_key)) for t in trace
                  if isinstance(t, dict))
    add("P4d 逐圈读数形态合法（None 或 [0,1]）", vals_ok,
        str([(t or {}).get(main_key) for t in trace])[:120])
    # 同层至少有一个「可判」的读数来源：verdict / goal_now / 逐圈。
    add("P4e 同层读数链条完整（verdict+goal_now+trace 互不打架）",
        (main is not None or pv["state"] == "unmeasured"), "—")

    # P7 目标判定可解释（不要求一定达成）。
    status, why = lga.classify_target(L, gn, trace, eng,
                                      ran=bool(view.get("rounds_run")))
    info["target_status"] = status
    info["target_why"] = why
    add("P7 目标判定可解释（%s）" % lga.TARGET_CN.get(status, status),
        status in ("achieved", "blocked", "not_achieved", "not_judgeable",
                   "unmeasured"),
        str(why)[:160])

    # P2g 该 run 的 rounds 与请求一致（不许「少跑一圈」蒙混）。
    # ★ 元层允许 +spiral.all_extra_rounds：引擎对 all 层默认多跑 all_extra_rounds
    #   圈（设计如此；V2.2.16 局部读数变化使 all 层不再提前停 ⇒ 实跑 3 圈）。
    #   允许集合从产物 _config 里读，不钉死数字。
    _extra = 0
    try:
        # 优先取产物快照里的有效配置；快照没有就取引擎 DEFAULT_CONFIG。
        _sp = ((d.get("_config") or {}).get("spiral") or {})
        _extra = int(_sp.get("all_extra_rounds") or 0)
    except (TypeError, ValueError, AttributeError):
        _extra = 0
    if not _extra:
        try:
            _dc = getattr(eng, "DEFAULT_CONFIG", None) or {}
            _extra = int(((_dc.get("spiral") or {})
                          .get("all_extra_rounds")) or 0)
        except (TypeError, ValueError, AttributeError):
            _extra = 0
    _allow = {int(want_rounds)}
    if L == "all":
        _allow |= {int(want_rounds) + i for i in range(0, max(0, _extra) + 1)}
    add("P2g 目标层 rounds_run 在允许集合（请求 %d；all 允许多 %d 圈）"
        % (want_rounds, _extra if L == "all" else 0),
        int(view.get("rounds_run") or 0) in _allow,
        "rounds_run=%s allow=%s" % (view.get("rounds_run"), sorted(_allow)))
    return info


#: 独立复算实现里**不许出现**的引擎内部调用（出现即判「退化成 import 引擎」）。
_FORBIDDEN_RECOMPUTE = ("eng.layer_goal_readings", "eng._lg_",
                        "_mod.layer_goal_readings", "_mod._lg_",
                        "_mod.layer_goal_readings")


def check_recompute_independence() -> tuple:
    """静态核对：审计脚本的复算实现**没有** import 引擎内部函数（独立实现才有牙）。"""
    try:
        funcs = (lga.recompute_layer_goal, lga._ind_num, lga._ind_ratio,
                 lga._ind_aspect_margin, lga._ind_stag_ratio,
                 lga._ind_diverge_state)
        src = "\n".join(inspect.getsource(f) for f in funcs)
    except Exception as e:  # noqa: BLE001
        return False, ["取源码失败：%s: %s" % (type(e).__name__, e)]
    bad = [tok for tok in _FORBIDDEN_RECOMPUTE if tok in src]
    params = list(inspect.signature(lga.recompute_layer_goal).parameters)
    if any(p.startswith("eng") or p.startswith("engine") for p in params):
        bad.append("recompute_layer_goal 签名带 engine 参数")
    return (not bad), bad


def check_ran_layers_consistency(case: str, d: dict, eng) -> bool:
    """本产物里**每一个**「跑过且落盘 goal_now」的层，都与独立复算逐字段一致。

    lead 口径：用审计脚本的独立复算对每层 goal_now 断言一致（不只目标层），
    这才是 V2.2.12+ 护栏的真正范围（上游层被携带也算跑过）。
    """
    ok = True
    for L in ("0", "1", "both", "all"):
        v = (d.get("views") or {}).get(L) or {}
        if not v.get("rounds_run") or not isinstance(v.get("goal_now"), dict):
            continue
        try:
            fresh = lga.recompute_layer_goal(v, L)
        except Exception as e:  # noqa: BLE001
            ck("%s P3x %s 层独立复算" % (case, L), False,
               "%s: %s" % (type(e).__name__, e))
            ok = False
            continue
        same = lga._deep_same(v["goal_now"], fresh)
        ck("%s P3x %s 层 goal_now 与独立复算逐字段一致" % (case, L), same,
           "" if same else ("不一致：%s vs %s"
                            % (json.dumps(v["goal_now"], ensure_ascii=False)[:100],
                               json.dumps(fresh, ensure_ascii=False)[:100])))
        ok = ok and same
    return ok


def check_zero_llm_pack(d: dict, eng) -> tuple:
    """零 LLM 产物判据（12:55 那类跑次不许被读成「模型能力不足」或「挖尽」）。

    返回 (ok, violations)。判据：
      · 跑过的层 verdict 必须非空且形态合法（有值 / 未测出）；
      · 未测出必须带**可指认原因**（非空、非「未知」）；
      · **不许判「达成」**（没调用就没证据）。
    """
    bad = []
    for L in ("0", "1", "both", "all"):
        v = (d.get("views") or {}).get(L) or {}
        if not v.get("rounds_run"):
            continue
        pv = lga.parse_verdict(v.get("goal_verdict"))
        if pv["state"] not in ("valued", "unmeasured"):
            bad.append("%s 层 verdict 空/非法（零 LLM 也必须有说法）" % L)
            continue
        if pv["state"] == "unmeasured" and not pv.get("why"):
            bad.append("%s 层未测出但原因空（不可指认）" % L)
        gn = v.get("goal_now") or {}
        status, why = lga.classify_target(L, gn, v.get("goal_trace") or [],
                                          eng, ran=True)
        if status == "achieved":
            bad.append("%s 层零 LLM 却判「达成」（%s）" % (L, str(why)[:80]))
    return (not bad), bad


def run_case(case: dict, question: str, rounds: int, timeout: float,
             eng, want_version: str) -> dict:
    """跑一个 case：真入口构造配置/命令 -> 子进程 -> 产物断言。"""
    print("\n" + "=" * 72)
    print("CASE route=%s 目标层=%s ｜ %s"
          % (case["route"], "+".join(case["target"]), case["why"]))
    _rounds = int(case.get("rounds") or rounds)
    _question = str(case.get("question") or question)
    cmd = er.build_cmd(_question, {"_config": str(CFG_PATH),
                                  "route": case["route"],
                                  "rounds": str(_rounds)})
    print("   命令：" + subprocess.list2cmdline(cmd), flush=True)
    before = {p: os.path.getmtime(p)
              for p in glob.glob(str(SAVE_DIR / "*.packed.json"))}
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
        rc = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        rc, out = None, "TIMEOUT %.0fs" % timeout
    wall = round(time.time() - t0, 1)
    print("   引擎退出码=%s 墙钟=%ss" % (rc, wall), flush=True)
    rec = {"case": case["id"], "route": case["route"],
           "targets": list(case["target"]), "requested_rounds": _rounds,
           "question": _question,
           "cmd": cmd, "exit": rc,
           "wall_sec": wall, "layers": [], "ok": False, "not_run": None}
    if rc != 0:
        rec["ok"] = False
        rec["not_run"] = "引擎非零退出（%s）" % rc
        note_not_run("case %s 引擎退出码 %s" % (case["id"], rc),
                     (out or "")[-300:])
        return rec
    after = _new_packs(before)
    if not after:
        rec["not_run"] = "没有新 packed 产物落盘"
        note_not_run("case %s 产物未落盘" % case["id"],
                     (out or "")[-300:])
        return rec
    pack_path = Path(after[0])
    print("   新产物：%s" % pack_path.name, flush=True)
    d = json.loads(pack_path.read_text(encoding="utf-8", errors="replace"))
    calls = d.get("llm_calls")
    rec["llm_calls"] = calls
    rec["pack"] = str(pack_path)

    # ── 零 LLM 产物判据：先验「产物诚实」，再决定记没跑还是判红。 ──
    if calls == 0:
        z_ok, z_bad = check_zero_llm_pack(d, eng)
        if not z_ok:
            # 零 LLM 却判「达成」/未测出无原因 => 诚实化通道坏了，**判红(1)**。
            for m in z_bad:
                ck("case %s Z 零 LLM 产物判据" % case["id"], False, m)
            rec["ok"] = False
            rec["zero_llm_violation"] = z_bad
            print("   ✗ 零 LLM 产物违反判据 => 判红（不是「没跑」）：%s"
                  % z_bad[:3], flush=True)
            return rec
        ck("case %s Z 零 LLM 产物判据通过（verdict 有说法、未测出有原因、无达成）"
           % case["id"], True,
           "llm_cb_opened=%s skipped=%s"
           % (d.get("llm_cb_opened"), d.get("llm_cb_skipped")))
        rec["not_run"] = "零 LLM 调用（链路故障：四层自动调度白跑，产物诚实）"
        note_not_run("case %s 零 LLM 调用" % case["id"],
                     "llm_calls=0 llm_cb_opened=%s llm_cb_skipped=%s；"
                     "产物已过零 LLM 判据（不冒充挖尽/未达成）"
                     % (d.get("llm_cb_opened"), d.get("llm_cb_skipped")))
        return rec
    if not isinstance(calls, int):
        rec["not_run"] = "llm_calls 缺失（无法判断是否真调用）"
        note_not_run("case %s llm_calls 缺失" % case["id"],
                     "llm_calls=%r" % (calls,))
        return rec

    # P3x 每层都做独立复算对账（不只目标层）
    check_ran_layers_consistency(case["id"], d, eng)

    # P6 provenance = 最高版引擎（App 自动选版）
    pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
    ck("case %s P6 provenance 是最高版引擎（%s）" % (case["id"], want_version),
       pv == want_version, pv)

    disp = d.get("dispatch") or {}
    ran = [str(x) for x in (disp.get("ran") or [])]
    skipped = disp.get("skipped") or []
    missing = [str(x) for x in (disp.get("missing") or [])]
    for L in case["target"]:
        if L in missing:
            rec["not_run"] = "目标层 %s 在 dispatch.missing（引擎层失败）" % L
            note_not_run("case %s 目标层 %s 失败" % (case["id"], L),
                         str(disp)[:300])
            continue
        if L not in (d.get("views") or {}):
            rec["not_run"] = "目标层 %s 无 view" % L
            note_not_run("case %s 目标层 %s 无 view" % (case["id"], L),
                         "dispatch=%s" % json.dumps(disp, ensure_ascii=False)[:300])
            continue
        rec["layers"].append(check_target_layer(
            case["id"], L, d, pack_path, eng, _rounds))
    if rec["not_run"]:
        return rec
    rec["ok"] = all(all(c["ok"] for c in lay["checks"])
                    for lay in rec["layers"])
    # 调度跳过信息（例如 both 缺上游）也要留痕
    if skipped:
        print("   引擎调度跳过：%s" % json.dumps(skipped, ensure_ascii=False)[:300])
    return rec


# ─────────────────────────── 打印 / 主流程 ───────────────────────────
def print_case_table(recs: list) -> None:
    print("\n" + "-" * 72)
    print("%-6s %12s %6s %10s %-4s %-8s %-6s %-12s %s"
          % ("case", "route", "exit", "llm_calls", "层", "读数", "目标",
             "目标判定", "PASS/FAIL"))
    for r in recs:
        if not r.get("layers"):
            print("%-6s %12s %6s %10s %-4s %-8s %-6s %-12s %s"
                  % (r["case"], r["route"], r["exit"],
                     r.get("llm_calls", "—"), "—", "—", "—", "没跑/没跑通",
                     "NOT_RUN"))
            continue
        for lay in r["layers"]:
            ok = sum(1 for c in lay["checks"] if c["ok"])
            bad = len(lay["checks"]) - ok
            print("%-6s %12s %6s %10s %-4s %-8s %-6s %-12s %d/%d"
                  % (r["case"], r["route"], r["exit"], r.get("llm_calls", "—"),
                     lay["layer"], lga._fmtval(lay["main_value"]),
                     (lga.parse_verdict(lay["verdict"]).get("state") or "—"),
                     lga.TARGET_CN.get(lay["target_status"], "—"),
                     ok, ok + bad))
            if bad:
                print("        判红项：%s"
                      % [c["name"] for c in lay["checks"] if not c["ok"]][:6])


def write_evidence(recs: list, path: Path, meta: dict) -> None:
    payload = {"meta": meta, "cases": recs,
               "pass": len(PASS), "fail": len(FAIL), "not_run": NOT_RUN}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print("\n证据 -> %s" % path)
    except OSError as e:  # noqa: BLE001
        print("\n⚠ 证据写入失败（不影响判据）：%s" % e)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        description="四层目标读数的真实入口探针（默认真跑，需 8772/8773）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将执行的命令 + 自检拼接，不建配置、不跑子进程")
    ap.add_argument("--only", default="",
                    help="只跑指定 case（逗号分隔：0,1,both,all）")
    ap.add_argument("--rounds", type=int, default=2, help="每层圈数（默认 2）")
    ap.add_argument("--timeout", type=float, default=900.0,
                    help="单个 case 的超时秒数（默认 900）")
    ap.add_argument("--question", default=os.environ.get("DGTF_LG_Q")
                    or "水的三态变化有哪些驱动因素", help="题面")
    ap.add_argument("--temperature", type=float, default=None,
                    help="透传 api.temperature（如 0.0 做确定性对照；默认不设=0.6）")
    ap.add_argument("--isolate-eml", action="store_true",
                    help="隔离 EML/playbook（playbook.mode=off + 独立目录），"
                         "用于跨跑可复现对照")
    ap.add_argument("--evidence", default="",
                    help="证据 JSON 路径（真跑时默认 outputs/_e2e_local/"
                         "_layer_goals_probe_latest.json）")
    args = ap.parse_args(argv)

    eng_path = lga.latest_engine_path()
    want_version = "V%d.%d.%d" % tuple(lga.vtuple(eng_path.name))
    app_engine = er.find_engine()
    print("=" * 72)
    print("四层目标读数真实入口探针 · scripts/local_model/probe_layer_goals.py")
    print("App 自动选版引擎：%s" % app_engine)
    print("引擎目录最高版：%s（%s）" % (eng_path.name, want_version))
    print("每层圈数=%d ｜ 题面=%r" % (args.rounds, args.question))
    print("=" * 72)

    want_cases = [c for c in CASES
                  if not args.only
                  or c["id"] in [x.strip() for x in args.only.split(",")]]
    if not want_cases:
        print("--only 没有匹配的 case：%s" % args.only)
        return 2

    # 命令拼接自检（dry-run 与真跑都做；App 自动选版漂移会在这里被抓住）。
    ck("E1 App engine_runner.find_engine() 与引擎目录最高版同源",
       app_engine.resolve() == eng_path.resolve(),
       "%s vs %s" % (app_engine, eng_path))
    try:
        eng = lga.load_engine(eng_path)
    except Exception as e:  # noqa: BLE001
        print("引擎加载失败（读数口径无法复算）：%s: %s" % (type(e).__name__, e))
        return 3
    print("复算口径引擎已加载：_LG_KEYS=%s" % eng._LG_KEYS)

    svc_ok = _up(8772, "/health")
    shim_ok = _up(8773, "/v1/models")
    shim_h = _health(8773, "/health") if shim_ok else None
    print("本地服务：8772=%s 8773=%s%s"
          % ("在" if svc_ok else "未起", "在" if shim_ok else "未起",
             ("（shim stage_channel=%s）"
              % (shim_h or {}).get("stage_channel")
              if isinstance(shim_h, dict) else "")))

    if args.dry_run:
        # dry-run：不建配置、不跑子进程，只验证命令拼接与 case 设计。
        for c in want_cases:
            cmd = er.build_cmd(args.question, {"_config": str(CFG_PATH),
                                               "route": c["route"],
                                               "rounds": str(args.rounds)})
            joined = subprocess.list2cmdline(cmd)
            print("\n[dry-run] CASE %s（目标层=%s）" % (c["id"],
                                                       "+".join(c["target"])))
            print("  计划配置：%s（dry-run 不落盘）" % CFG_PATH)
            print("  计划命令：%s" % joined)
            ck("D1 case %s 命令含 --config" % c["id"], "--config" in cmd)
            ck("D2 case %s 命令含 --rounds %d" % (c["id"], args.rounds),
               "--rounds" in cmd and str(args.rounds) in cmd)
            ck("D3 case %s 命令含 --route %s" % (c["id"], c["route"]),
               "--route" in cmd and c["route"] in cmd)
            ck("D4 case %s 命令指向最高版引擎" % c["id"],
               any(Path(x).name == eng_path.name for x in cmd))
            if c["id"] == "both":
                ck("D5 both case 带足上游（0,1）", all(x in c["route"]
                                                       for x in ("0", "1")))
            if c["id"] == "all":
                ck("D6 all case 带足上游（>=2 个 view）",
                   len([x for x in c["route"].split(",") if x]) >= 2)
        ck("D7 dry-run 不验收在服务（服务在不在只打印，不判红）", True,
           "8772=%s 8773=%s" % (svc_ok, shim_ok))
        ind_ok, ind_bad = check_recompute_independence()
        ck("D8 ★ 复算实现独立（不调用引擎 layer_goal_readings/_lg_*）",
           ind_ok, ind_bad or "独立实现")
        try:
            _src_probe = inspect.getsource(check_target_layer)
        except Exception:  # noqa: BLE001
            _src_probe = ""
        ck("D9 ★ 探针 P3 断言 goal_now 与独立复算一致（钩子存在）",
           "recompute_layer_goal" in _src_probe)
        try:
            _src_zero = inspect.getsource(check_zero_llm_pack)
        except Exception:  # noqa: BLE001
            _src_zero = ""
        ck("D10 ★ 零 LLM 产物判据存在（未测出原因/不许达成）",
           ("未测出但原因空" in _src_zero) and ("判「达成」" in _src_zero
                                                or "achieved" in _src_zero))
        print("\n" + "-" * 72)
        print("dry-run %d/%d 通过%s"
              % (len(PASS), len(PASS) + len(FAIL),
                 ("，判红：%s" % FAIL) if FAIL else ""))
        print("dry-run 完成：未建配置、未跑子进程、未占 GPU。"
              "真跑请等 Lead 的 GPU 窗口。")
        return 1 if FAIL else 0

    # ── 真跑前置：两段本地服务必须在（没跑 ≠ 判红）。 ──
    if not svc_ok or not shim_ok:
        print("\n⚠ 本地服务未起（8772=%s / 8773=%s）：本判据无法执行"
              "（不是判红，是没跑）" % (svc_ok, shim_ok))
        return 2
    _ov = dict(OVERRIDES)
    if args.temperature is not None:
        _ov["api.temperature"] = float(args.temperature)
        print("温度对照：api.temperature=%s" % args.temperature)
    if args.isolate_eml:
        _ov["playbook.mode"] = "off"
        _ov["playbook.dir"] = "outputs/_e2e_local/_probe_eml_off"
        print("EML 隔离模式：playbook.mode=off，dir=outputs/_e2e_local/_probe_eml_off")
    cfg = params.build_temp_config(_ov, CFG_PATH)
    ck("E2 App params.build_temp_config() 生成本地档配置",
       bool(cfg) and Path(cfg).is_file(), str(cfg))
    if not cfg:
        print("⚠ 配置生成失败（没跑通），中止")
        return 2
    txt = Path(cfg).read_text(encoding="utf-8", errors="replace")
    ck("E3 配置确实指向 8773 适配层且 gates 不阻断",
       "127.0.0.1:8773" in txt and "answer_gates" in txt)
    # App 命令拼接（真入口）
    _probe_cmd = er.build_cmd(args.question, {"_config": str(cfg),
                                              "route": want_cases[0]["route"],
                                              "rounds": str(args.rounds)})
    ck("E4 App engine_runner.build_cmd() 拼的命令含本地配置",
       "--config" in _probe_cmd and str(cfg) in _probe_cmd,
       subprocess.list2cmdline(_probe_cmd)[:160])

    t_all = time.time()
    recs = [run_case(c, args.question, args.rounds, args.timeout, eng,
                     want_version) for c in want_cases]
    print_case_table(recs)
    meta = {"question": args.question, "rounds": args.rounds,
            "engine": str(eng_path.relative_to(ROOT)),
            "engine_version": want_version,
            "app_engine": str(app_engine),
            "wall_sec": round(time.time() - t_all, 1),
            "isolate_eml": bool(args.isolate_eml),
            "temperature": (None if args.temperature is None
                            else float(args.temperature)),
            "services": {"8772": svc_ok, "8773": shim_ok,
                         "shim_health": shim_h},
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ev = Path(args.evidence) if args.evidence else EVIDENCE_DEFAULT
    write_evidence(recs, ev, meta)

    red = len(FAIL)
    not_run = len(NOT_RUN)
    print("\n" + "=" * 72)
    print("墙钟 %.1fs ｜ 断言 %d 项：PASS %d / FAIL %d ｜ 没跑/没跑通 case/层：%d"
          % (meta["wall_sec"], len(PASS) + len(FAIL), len(PASS), red, not_run))
    if red:
        print("判红：%s" % FAIL[:10])
        return 1
    if not_run:
        print("没跑/没跑通项（不是判红）：%s" % NOT_RUN[:10])
        return 2
    print("四层读数通道全部通过（读数存在、形态合法、可离线复算；"
          "目标达成与否见上面的目标判定列）。")
    return 0


#: App 任务配置覆盖（与 scripts/local_model/e2e_app_local.py 同一套本地档口径）。
OVERRIDES = {
    "api.base_url": "http://127.0.0.1:8773/v1",
    "api.key": "local-shim",
    "api.default_model": "local",
    "api.reasoner_model": "local",
    "web_search.enabled": False,
    "api.circuit_breaker.enabled": True,
    "output.answer_gates.enabled": True,
    # 本地档只留痕不阻断：探针验的是「读数在」，不是「答得准」。
    "output.answer_gates.block": False,
    # 探针产物独立落盘：不混进 outputs/*.packed.json 的生产质量统计。
    "output.save_dir": "outputs/_e2e_local",
}


if __name__ == "__main__":
    raise SystemExit(main())
