# -*- coding: utf-8 -*-
"""[V2.2.20 / App 2.0.45] 道生支路接入统一模式体系（方案 A）判据（零成本）。

判据：
  A 道生 plan 采用 MODE_CONFIGS 作为默认参数（parallel/thinking/effort），
    道生预设的 rounds / rounds_fast / scenario web 规则仍优先；
  B plan 带 mode / unified_config / rounds_locked；apply_plan 透传 mode 且显式 opts 优先；
  C rounds_locked 语义：动态降档不压圈、升档不补圈；未锁定则相反；
  D M4 回显 first_config/optimality/policy（可用时）；
  E 静态接线：引擎 V2.2.20 rounds_locked 处理 + tick patch 键守卫 + server 回显；
  F 变异体：fast 用 serial（非统一配置）/ apply_plan 不传 mode => 必须判红。
"""
from __future__ import annotations

from _serial_lock import acquire_serial_lock  # [V2.2.59] 串行锁
_SERIAL_LOCK = acquire_serial_lock("local_chain")

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "dgtf_engine"), str(ROOT / "dgtf_app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daosheng_mode as DS  # noqa: E402
from dgtf_v2.mode_fusion import MODE_CONFIGS, dynamic_adjust  # noqa: E402

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


REASON_Q = "为什么城市热岛效应在夜间比白天更明显？"
FACT_Q = "2024年中国GDP增速最新数据是多少？"


def mk_plan(q=REASON_Q, requested="daosheng"):
    return DS.build_plan(q, {}, requested=requested, is_mock=True,
                         balance_cny=50.0)


print("── A 道生 plan 采用统一模式配置 ──")
p_ds = mk_plan(REASON_Q, "daosheng")
ck("A1 daosheng（质量档）engine_mode=B", p_ds.get("engine_mode") == "B",
   p_ds.get("engine_mode"))
ck("A2 plan.mode 与 engine_mode 一致（供 --mode 透传）",
   p_ds.get("mode") == p_ds.get("engine_mode") == "B", p_ds.get("mode"))
ck("A3 unified_config == MODE_CONFIGS[B]",
   p_ds.get("unified_config") == MODE_CONFIGS["B"], p_ds.get("unified_config"))
ck("A4 质量档 parallel/thinking/effort 来自统一配置（B/auto/auto）",
   p_ds.get("parallel") == "B" and p_ds.get("thinking") == "auto"
   and p_ds.get("effort") == "auto",
   (p_ds.get("parallel"), p_ds.get("thinking"), p_ds.get("effort")))
ck("A5 质量档默认 rounds=auto => 不锁定圈数",
   str(p_ds.get("rounds")) == "auto" and p_ds.get("rounds_locked") is False,
   (p_ds.get("rounds"), p_ds.get("rounds_locked")))

p_fast = mk_plan(REASON_Q, "daosheng_fast")
ck("A6 daosheng_fast engine_mode=fast / mode=fast",
   p_fast.get("engine_mode") == "fast" and p_fast.get("mode") == "fast",
   (p_fast.get("engine_mode"), p_fast.get("mode")))
ck("A7 fast 采用统一配置 parallel=B / thinking=off（不再是旧 serial）",
   p_fast.get("parallel") == MODE_CONFIGS["fast"]["parallel"]
   and p_fast.get("thinking") == MODE_CONFIGS["fast"]["thinking"],
   (p_fast.get("parallel"), p_fast.get("thinking")))
ck("A8 fast 的 rounds_fast 仍优先且 rounds_locked=True",
   str(p_fast.get("rounds") or "").startswith("0:2") and p_fast.get("rounds_locked") is True,
   (p_fast.get("rounds"), p_fast.get("rounds_locked")))

p_fact = mk_plan(FACT_Q, "daosheng_fast")
ck("A9 场景规则优先：事实题 fast 强制 web=on（统一配置 web=False 不覆盖）",
   p_fact.get("web") == "on", p_fact.get("web"))

print("── B apply_plan：mode 透传 + 显式 opts 优先 ──")
opts = {}
applied = DS.apply_plan(p_fast, opts)
ck("B1 apply_plan 落 mode=fast（引擎据此启用动态调整）",
   opts.get("mode") == "fast" and applied.get("mode") == "fast",
   (opts.get("mode"), applied.get("mode")))
ck("B2 apply_plan 落 parallel/thinking/rounds（引擎显式参数）",
   opts.get("parallel") == p_fast.get("parallel")
   and opts.get("thinking") == p_fast.get("thinking")
   and opts.get("rounds") == p_fast.get("rounds"),
   {k: opts.get(k) for k in ("parallel", "thinking", "rounds")})
opts2 = {"parallel": "serial", "rounds": "0:5,1:5,both:5,all:5"}
applied2 = DS.apply_plan(p_fast, opts2)
ck("B3 显式 opts 优先：parallel/rounds 不被 plan 覆盖",
   opts2.get("parallel") == "serial"
   and opts2.get("rounds") == "0:5,1:5,both:5,all:5"
   and "parallel" not in applied2)
ck("B4 mode 仍然透传（未被显式 opts 占用）", opts2.get("mode") == "fast")

print("── C rounds_locked：动态调整不改圈 ──")
_locked = {"mode": "B", "config": dict(MODE_CONFIGS["B"]),
           "preferences": {"min_quality": 0.90}, "rounds_locked": True}
_unlocked = dict(_locked, rounds_locked=False)
_prog = {"elapsed_sec": 600, "wall_budget_sec": 900,
         "layers_done": 0, "layers_total": 4}
_d1 = dynamic_adjust(_locked, _prog)
_d2 = dynamic_adjust(_unlocked, _prog)
ck("C1 锁定：降档 patch 不含 cap_rounds 且理由注明锁定",
   _d1["action"] == "downgrade" and "cap_rounds" not in _d1["patch"]
   and "锁定" in _d1["reason"], _d1)
ck("C2 未锁定：降档仍压圈（cap_rounds=1）",
   _d2["action"] == "downgrade" and _d2["patch"].get("cap_rounds") == 1, _d2)
_up_locked = {"mode": "fast", "config": dict(MODE_CONFIGS["fast"]),
              "cascade": {"on_quality_below": 0.95},
              "preferences": {"min_quality": 0.90}, "rounds_locked": True}
_up_unlocked = dict(_up_locked, rounds_locked=False)
_u1 = dynamic_adjust(_up_locked, {"quality_proxy": 0.5})
_u2 = dynamic_adjust(_up_unlocked, {"quality_proxy": 0.5})
ck("C3 锁定：升档 patch 不含 rounds_extra",
   _u1["action"] == "upgrade" and "rounds_extra" not in _u1["patch"], _u1)
ck("C4 未锁定：升档补 1 圈（rounds_extra=1）",
   _u2["action"] == "upgrade" and _u2["patch"].get("rounds_extra") == 1, _u2)

print("── D M4 回显（可用时）──")
_m4 = p_ds.get("m4") or {}
if _m4.get("ok"):
    ck("D1 M4 回显 first_config/optimality/policy",
       isinstance(_m4.get("first_config"), dict)
       and isinstance(_m4.get("optimality"), dict)
       and isinstance(_m4.get("policy"), str), _m4)
else:
    ck("D1 M4 未就绪时不阻塞（fail-open 记录 ok=False）",
       _m4.get("ok") is False, _m4)

print("── E 静态接线 ──")
ENG_DIR = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
_engs = sorted(ENG_DIR.glob("Meta-DGTF-V*.py"),
               key=lambda p: tuple(int(x) for x in
                                   re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name).groups()))
_eng = _engs[-1]
_esrc = _eng.read_text(encoding="utf-8-sig")
ck("E1 引擎最高版 >= V2.2.20", tuple(int(x) for x in
   re.search(r"V(\d+)\.(\d+)\.(\d+)", _eng.name).groups()) >= (2, 2, 20), _eng.name)
ck("E2 引擎 --mode 规划：显式 rounds => rounds_locked",
   ' _auto_mode_plan["rounds_locked"] = True' in _esrc
   or "_auto_mode_plan[\"rounds_locked\"] = True" in _esrc)
ck("E3 tick 只在 patch 带 cap_rounds 时改圈",
   'dec["patch"].get("cap_rounds")' in _esrc)
ck("E4 tick 只在 patch 带 rounds_extra 时补圈",
   'dec["patch"].get("rounds_extra")' in _esrc)
_dsrc = (ROOT / "dgtf_app" / "daosheng_mode.py").read_text(encoding="utf-8")
ck("E5 道生 plan 引用 MODE_CONFIGS 并写 rounds_locked",
   "MODE_CONFIGS" in _dsrc and '"rounds_locked"' in _dsrc)
_ssrc = (ROOT / "dgtf_app" / "server.py").read_text(encoding="utf-8", errors="replace")
ck("E6 server 道生分支回显 unified/config/rounds_locked",
   '"unified": True' in _ssrc and '"rounds_locked"' in _ssrc)

print("── F 变异体（有牙）──")
_bad_fast = {"parallel": "serial", "thinking": "off"}
ck("F1 变异体：fast 若用 serial（非统一配置）=> A7 口径会判红",
   _bad_fast["parallel"] != MODE_CONFIGS["fast"]["parallel"])
_opts_bad = {}
_apply_bad = DS.apply_plan({"mode": ""}, _opts_bad)
ck("F2 变异体：apply_plan 不传 mode => B1 口径会判红",
   _opts_bad.get("mode") in (None, ""))
_bad_locked = dict(_locked, rounds_locked=False)
_d_bad = dynamic_adjust(_bad_locked, _prog)
ck("F3 变异体：rounds_locked 失效 => C1 口径会判红（出现 cap_rounds）",
   _d_bad["patch"].get("cap_rounds") == 1)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
