# -*- coding: utf-8 -*-
"""模式级最优选档（V2.2.19：输入驱动 + 每模式专属参数 + 可证最优 + 运行期动态调整）。

保留模式（KEPT）
----------------
只有三个：B / serial / fast。其余并行模式（A、C-H）已从用户面移除；
web 不再是一个"模式"，而是选中模式上的一个标志位 —— 只有 B + 官方联网
有实测读数，因此 require_web 时只考虑 B(+web)（不拿没测过的组合冒充）。

每个模式的专门配置
------------------
MODE_CONFIGS 是唯一事实源（App 与引擎共用）：
  · B      —— parallel=B，thinking=auto，质量/墙钟双优（实测 quality 1.0 / 1064s）
  · serial —— parallel=serial，thinking=auto，低 tokens 备选（997k / 1920s）
  · fast   —— parallel=B，thinking=off，墙钟/tokens 最低（782s / 817k）
显式任务参数（opts/CLI）优先于模式默认值（记录在 applied 里，可审计）。

"最优"的定义（可穷举证明）
--------------------------
候选集 = KEPT 中满足约束（quality >= min_quality、wall <= max_wall、
tokens <= max_tokens；require_web => 仅 B+web）。目标函数是枚举的：
  · quality：max(quality)，平手 min(wall)；
  · wall：   min(wall)，平手 max(quality)；
  · tokens： min(tokens)，平手 max(quality)；
  · balanced：归一化加权（质量 0.5 / 墙钟 0.25 / tokens 0.25）。
候选只有 3 个 => 选出的就是精确最优：regret = 0，且选中项不被任何可行候选支配
（测试用暴力 oracle + 支配关系双重核对）。无可行候选时显式标 fallback=True、
regret=None（不假装最优），并按"质量下限优先 -> 墙钟短"给出可解释退路。

输入驱动
--------
plan_for_input(question)：从题面类型（事实/推理/选择）+ 长度 + 显式预算推出
偏好与约束，再调用最优选档。事实题默认 prefer=wall, min_quality=0.90 => fast；
推理/选择题默认 prefer=quality, min_quality=0.95 => B；长题/多问默认质量优先；
显式 opts 的 min_quality/max_wall/max_tokens/prefer/require_web/mode 一律优先。

运行期动态调整
--------------
dynamic_adjust(plan, progress)：纯函数。预算超支（墙钟过半但进度不足半 / tokens
过 70%）=> 降档 fast（仅当质量下限允许）；fast 且有 cascade 且运行期质量代理
低于目标 => 升档 B。每次调整都带 reason 与备选（引擎落在 packed.auto_mode 里可审计）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

MODES: Dict[str, dict] = {
    "B": {"name": "模式B·动态规划", "quality": 1.0, "quality_low": 0.9592,
          "tokens": 1269082, "wall": 1064.3, "wall_high": 1064.3,
          "web": False, "run": "20261024_205018",
          "strength": "质量/墙钟双优（方差 0.959–1.000）"},
    "serial": {"name": "serial·低tokens", "quality": 0.99, "quality_low": 0.99,
               "tokens": 997457, "wall": 1920.6, "wall_high": 1920.6,
               "web": False, "run": "20261024_163455",
               "strength": "质量高且 tokens 低于 B"},
    "fast": {"name": "thinking off·时间档", "quality": 0.93, "quality_low": 0.93,
             "tokens": 816983, "wall": 782.6, "wall_high": 782.6,
             "web": False, "run": "20261024_193452",
             "strength": "墙钟/tokens 最低"},
}

#: 保留模式（用户面只有这三个；A、C-H 已移除）。
KEPT = ("B", "serial", "fast")

#: web 不是模式，而是标志位：唯一有实测的联网档 = B + 官方联网。
WEB_READING: Dict[str, dict] = {
    "name": "B + 官方联网", "quality": 0.933, "quality_low": 0.933,
    "tokens": 1062012, "wall": 1073.3, "wall_high": 1073.3,
    "web": True, "run": "20261024_215545",
    "strength": "必须联网场景（唯一有实测的联网档）",
}

#: 每个保留模式的专门配置参数（App 与引擎共用；显式 opts/CLI 优先）。
MODE_CONFIGS: Dict[str, dict] = {
    "B": {"parallel": "B", "thinking": "auto", "effort": "auto",
          "web": False, "behavior_fusion": "off",
          "rounds_hint": "0:1,1:1,both:1,all:1",
          "quality_floor": 0.95, "quality_target": 0.99,
          "rationale": "质量/墙钟双优：实测 quality 1.0、1064s"},
    "serial": {"parallel": "serial", "thinking": "auto", "effort": "auto",
               "web": False, "behavior_fusion": "off",
               "rounds_hint": "0:1,1:1,both:1,all:1",
               "quality_floor": 0.95, "quality_target": 0.99,
               "rationale": "低 tokens 备选：997k、质量 0.99（墙钟最长）"},
    "fast": {"parallel": "B", "thinking": "off", "effort": "auto",
             "web": False, "behavior_fusion": "off",
             "rounds_hint": "0:1,1:1,both:1,all:1",
             "quality_floor": 0.90, "quality_target": 0.95,
             "rationale": "墙钟/tokens 最低：782s / 817k、质量 0.93"},
}

PREFERS = ("quality", "wall", "tokens", "balanced")


def _candidate_rows(require_web: bool = False) -> List[dict]:
    """候选 = KEPT 读数；require_web 时只有 B+web（唯一有实测的联网档）。"""
    if require_web:
        return [dict(WEB_READING, mode="B", config=dict(MODE_CONFIGS["B"], web=True))]
    rows = []
    for m in KEPT:
        rows.append(dict(MODES[m], mode=m, config=dict(MODE_CONFIGS[m])))
    return rows


def _dominates(a: dict, b: dict) -> bool:
    """a 支配 b：质量不低、tokens 不多、墙钟不长，且至少一项严格更好。"""
    try:
        ge = (float(a["quality"]) >= float(b["quality"])
              and float(a["tokens"]) <= float(b["tokens"])
              and float(a["wall"]) <= float(b["wall"]))
        strict = (float(a["quality"]) > float(b["quality"])
                  or float(a["tokens"]) < float(b["tokens"])
                  or float(a["wall"]) < float(b["wall"]))
        return bool(ge and strict)
    except Exception:  # noqa: BLE001
        return False


def _norm(vals: List[float]) -> Dict[float, float]:
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return {v: 1.0 for v in vals}
    return {v: (v - lo) / (hi - lo) for v in vals}


def _choose(rows: List[dict], prefer: str) -> Optional[dict]:
    """在可行候选里按偏好枚举选最优；打平用 KEPT 顺序保证确定性。"""
    if not rows:
        return None
    if prefer == "balanced":
        qs = _norm([float(r["quality"]) for r in rows])
        ws = _norm([float(r["wall"]) for r in rows])
        ts = _norm([float(r["tokens"]) for r in rows])
        return max(rows, key=lambda r: (0.5 * qs[float(r["quality"])]
                                        + 0.25 * (1.0 - ws[float(r["wall"])])
                                        + 0.25 * (1.0 - ts[float(r["tokens"])])))
    if prefer == "wall":
        return min(rows, key=lambda r: (float(r["wall"]),
                                        -float(r["quality"]),
                                        float(r["tokens"])))
    if prefer == "tokens":
        return min(rows, key=lambda r: (float(r["tokens"]),
                                        -float(r["quality"]),
                                        float(r["wall"])))
    return max(rows, key=lambda r: (float(r["quality"]),
                                    -float(r["wall"]),
                                    -float(r["tokens"])))


def infer_preferences(question: str = "", opts: Optional[dict] = None,
                      features: Optional[dict] = None) -> dict:
    """由用户输入推出偏好与约束（显式 opts 优先）。纯函数。"""
    o = dict(opts or {})
    q = str(question or "")
    kind = kind_of_question(q) if q else "reasoning"
    long_q = (len(q) >= 200) or (q.count("？") + q.count("?") >= 2)
    src = []
    prefer = o.get("prefer")
    if prefer not in PREFERS:
        prefer = None
    if prefer is None:
        mq = o.get("min_quality")
        if mq is not None and float(mq) >= 0.95:
            prefer = "quality"
        elif kind == "fact" and not long_q:
            prefer = "wall"
        else:
            prefer = "quality"
        src.append("kind=%s" % kind)
    else:
        src.append("explicit prefer")
    min_quality = o.get("min_quality")
    if min_quality is None:
        min_quality = 0.95 if prefer == "quality" else 0.90
        src.append("floor=%.2f" % min_quality)
    min_quality = float(min_quality)
    max_wall = o.get("max_wall")
    max_wall = None if max_wall in (None, "", 0) else float(max_wall)
    max_tokens = o.get("max_tokens")
    max_tokens = None if max_tokens in (None, "", 0) else int(max_tokens)
    require_web = bool(o.get("require_web"))
    if require_web:
        src.append("require_web")
    hard = {"prefer": "explicit prefer" in src,
            "min_quality": o.get("min_quality") is not None,
            "max_wall": o.get("max_wall") not in (None, "", 0),
            "max_tokens": o.get("max_tokens") not in (None, "", 0),
            "require_web": "require_web" in src}
    return {"prefer": prefer, "min_quality": min_quality,
            "max_wall": max_wall, "max_tokens": max_tokens,
            "require_web": require_web, "kind": kind,
            "long_question": bool(long_q),
            "features_used": bool(features),
            "hard": hard,
            "source": "explicit" if "explicit prefer" in src else "inferred",
            "notes": src}


def select_optimal_mode(question: str = "", opts: Optional[dict] = None,
                        features: Optional[dict] = None) -> dict:
    """输入 -> 最优模式（可证最优；不可行时显式 fallback）。纯函数、确定性。"""
    o = dict(opts or {})
    prefs = infer_preferences(question, o, features)
    rows = _candidate_rows(prefs["require_web"])
    feasible = []
    for r in rows:
        if float(r["quality"]) < prefs["min_quality"]:
            continue
        if prefs["max_wall"] is not None and float(r["wall"]) > prefs["max_wall"]:
            continue
        if (prefs["max_tokens"] is not None
                and float(r["tokens"]) > prefs["max_tokens"]):
            continue
        feasible.append(r)
    fallback = False
    relaxed = []
    chosen = _choose(feasible, prefs["prefer"])
    if chosen is None and not prefs["hard"]["min_quality"]:
        # ★ 最优性策略：显式约束（墙钟/tokens）不可破；「推断出来的质量下限」
        #   在无解时让位（记录在 optimality.relaxed 里），否则等于用一条猜的
        #   下限把整题判成"无可行模式"，反而不如 fast 的 0.93/782s 可用。
        relaxed.append("min_quality(inferred)")
        _mq_saved = prefs["min_quality"]
        prefs["min_quality"] = 0.0
        feasible = []
        for r in rows:
            if prefs["max_wall"] is not None and float(r["wall"]) > prefs["max_wall"]:
                continue
            if (prefs["max_tokens"] is not None
                    and float(r["tokens"]) > prefs["max_tokens"]):
                continue
            feasible.append(r)
        chosen = _choose(feasible, prefs["prefer"])
        if chosen is None:
            prefs["min_quality"] = _mq_saved
    if chosen is None:
        fallback = True
        above = [r for r in rows if float(r["quality"]) >= prefs["min_quality"]]
        pool = above or rows
        chosen = min(pool, key=lambda r: (float(r["wall"]),
                                          float(r["tokens"]),
                                          -float(r["quality"])))
    dominated = []
    for r in rows:
        ds = [a["mode"] for a in rows if a is not r and _dominates(a, r)]
        if ds:
            dominated.append({"mode": r["mode"], "dominated_by": sorted(ds)})
    explicit = o.get("mode") if o.get("mode") in MODES else None
    if explicit:
        chosen = next((r for r in rows if r["mode"] == explicit), chosen)
    optimality = {
        "method": "enumerate_%d" % len(rows),
        "regret": (0.0 if (feasible and not fallback and not explicit) else None),
        "override": bool(explicit),
        "feasible_n": len(feasible),
        "dominated": dominated,
        "objective": prefs["prefer"],
        "hard_constraints": dict(prefs.get("hard") or {}),
        "relaxed": list(relaxed),
        "note": ("可行集内枚举取最优，regret=0" if feasible and not fallback
                 and not explicit else
                 ("显式指定模式（非最优化，约束仍核对）" if explicit else
                  "无可行候选 => fallback（不假装最优）")),
    }
    chosen = dict(chosen)
    chosen["config"] = dict(chosen.get("config") or {})
    chosen["config"]["web"] = bool(prefs["require_web"])
    target = float(prefs.get("min_quality") or 0.0)
    cascade = None
    if chosen["mode"] == "fast":
        tgt = max(target, float(MODE_CONFIGS["fast"]["quality_target"]))
        if tgt > float(MODES["fast"]["quality"]):
            cascade = {"upgrade_to": "B", "on_quality_below": round(tgt, 3),
                       "why": "fast 先跑；运行期质量代理低于目标再升 B（时间换质量）"}
    reason = ("满足全部约束（prefer=%s，可行 %d 个）" % (prefs["prefer"], len(feasible))
              if feasible and not fallback else
              ("无可行候选：质量下限 %.2f 不可满足，退为墙钟最短" % prefs["min_quality"]
               if fallback else "显式指定 %s" % chosen["mode"]))
    return {"mode": chosen["mode"], "web": bool(prefs["require_web"]),
            "config": chosen["config"], "reading": {
                k: chosen.get(k) for k in ("quality", "quality_low", "tokens",
                                           "wall", "run", "name", "strength")},
            "candidates": [{"mode": r["mode"], "quality": r["quality"],
                            "tokens": r["tokens"], "wall": r["wall"],
                            "feasible": r in feasible} for r in rows],
            "feasible": [r["mode"] for r in feasible],
            "fallback": bool(fallback), "reason": reason,
            "preferences": prefs, "cascade": cascade,
            "optimality": optimality}


def plan_for_input(question: str = "", opts: Optional[dict] = None,
                   features: Optional[dict] = None) -> dict:
    """输入驱动的完整运行计划（模式 + 配置 + 约束 + 动态调整策略 + 最优性证据）。"""
    sel = select_optimal_mode(question, opts, features)
    cfg = dict(sel["config"])
    return {"schema": "dgtf.mode_plan.v1",
            "question_kind": sel["preferences"]["kind"],
            "mode": sel["mode"], "web": sel["web"], "config": cfg,
            "preferences": sel["preferences"], "cascade": sel["cascade"],
            "selection": sel, "optimality": sel["optimality"],
            "reason": sel["reason"]}


def apply_mode_opts(opts: Optional[dict], plan: dict) -> tuple:
    """把模式配置落成任务 opts（显式值优先）；返回 (new_opts, applied)。"""
    out = dict(opts or {})
    cfg = dict((plan or {}).get("config") or {})
    if not cfg:
        return out, {}
    out.setdefault("parallel", cfg.get("parallel"))
    out.setdefault("thinking", cfg.get("thinking"))
    out.setdefault("effort", cfg.get("effort"))
    out.setdefault("web", "on" if (plan or {}).get("web") else "off")
    out.setdefault("behavior_fusion", cfg.get("behavior_fusion"))
    out.setdefault("rounds", cfg.get("rounds_hint"))
    out.setdefault("mode", (plan or {}).get("mode"))
    applied = {k: out.get(k) for k in ("parallel", "thinking", "effort", "web",
                                       "behavior_fusion", "rounds", "mode")}
    out["_mode_plan"] = plan
    return out, applied


def dynamic_adjust(plan: Optional[dict], progress: Optional[dict]) -> dict:
    """运行期动态调整（纯函数）：预算超支降档 / fast 质量不达标升档。"""
    plan = dict(plan or {})
    pg = dict(progress or {})
    mode = str(plan.get("mode") or "")
    target = (plan.get("cascade") or {}).get("on_quality_below")
    qprox = pg.get("quality_proxy")
    if (mode == "fast" and target is not None and qprox is not None
            and float(qprox) < float(target)):
        return {"action": "upgrade", "from": mode, "to": "B",
                "patch": {"thinking": "auto", "rounds_extra": 1},
                "reason": "运行期质量代理 %.2f < 目标 %.2f => 升档 B（时间换质量）"
                          % (float(qprox), float(target)),
                "alternatives": ["keep fast（质量不达标，拒绝）", "downgrade（无更低档）"],
                "optimality": {"method": "policy_check", "regret": None,
                               "note": "质量优先约束下的必需动作"}}
    wall = pg.get("wall_budget_sec")
    elapsed = pg.get("elapsed_sec")
    tbudget = pg.get("token_budget")
    tokens = pg.get("tokens_used")
    done = float(pg.get("layers_done") or 0)
    total = float(pg.get("layers_total") or 0)
    wall_over = bool(wall and elapsed and elapsed >= 0.5 * float(wall)
                     and total > 0 and done / total < 0.5)
    token_over = bool(tbudget and tokens and float(tokens) >= 0.7 * float(tbudget))
    # ★ 质量代理正常（或未知）时才允许降档：代理已明显偏低时降档会雪上加霜。
    if ((wall_over or token_over) and mode != "fast"
            and (qprox is None or float(qprox) >= 0.9)):
        floor = float((plan.get("preferences") or {}).get("min_quality") or 0.0)
        if floor <= float(MODES["fast"]["quality"]):
            why = ("墙钟预算过半而进度不足半" if wall_over else "tokens 已用 70%")
            return {"action": "downgrade", "from": mode, "to": "fast",
                    "patch": {"thinking": "off", "web": False, "cap_rounds": 1},
                    "reason": "%s => 降档 fast（质量下限 %.2f <= fast 0.93，仍满足）"
                              % (why, floor),
                    "alternatives": ["keep %s（预算会超支）" % mode],
                    "optimality": {"method": "policy_check", "regret": None,
                                   "note": "预算约束下的可行最优（keep 不可行）"}}
    return {"action": "keep", "from": mode, "to": mode, "patch": {},
            "reason": "进度与预算正常，无需调整",
            "alternatives": [], "optimality": {"method": "policy_check",
                                               "regret": 0.0,
                                               "note": "当前已是最优计划"}}


def select_mode(min_quality: Optional[float] = None,
                max_wall: Optional[float] = None,
                max_tokens: Optional[int] = None,
                require_web: bool = False,
                prefer: str = "quality") -> dict:
    """向后兼容包装：旧 API 形状（mode/info/reason），内部走最优选档。"""
    opts = {"min_quality": min_quality, "max_wall": max_wall,
            "max_tokens": max_tokens, "require_web": require_web,
            "prefer": prefer}
    sel = select_optimal_mode("", opts=opts)
    info = dict(sel["reading"])
    if sel["web"]:
        info = dict(WEB_READING)
    return {"mode": sel["mode"], "info": info, "reason": sel["reason"],
            "config": sel["config"], "web": sel["web"],
            "optimality": sel["optimality"]}


def fused_plan(min_quality: Optional[float] = None,
               max_wall: Optional[float] = None,
               max_tokens: Optional[int] = None,
               require_web: bool = False,
               cascade: bool = True,
               features: Optional[dict] = None,
               history: Optional[dict] = None,
               model_path: str = "dgtf_memory/quality_predictor.json") -> dict:
    """M4 auto-fused：先选首选模式；cascade=True 给 fast->B 的升级路径。"""
    opts = {"min_quality": min_quality, "max_wall": max_wall,
            "max_tokens": max_tokens, "require_web": require_web,
            "prefer": "quality"}
    plan = plan_for_input("", opts=opts, features=features)
    first = {"mode": plan["mode"], "info": plan["selection"]["reading"],
             "reason": plan["reason"], "config": plan["config"],
             "web": plan["web"], "optimality": plan["optimality"]}
    _first_mode = first["mode"]
    quality_guard = None
    pred = {}
    _lower = {}
    _conf = {}
    if features and not require_web:
        try:
            from dgtf_v2.quality_predictor import load_model, predict
            _model_path = (str((Path(__file__).resolve().parents[2] / model_path))
                           if not Path(model_path).is_absolute() else model_path)
            model = load_model(_model_path)
            if model:
                pred_raw = {
                    m: predict(model, features, route_n=4, rounds_avg=2.0,
                               web=bool(require_web), mode=m,
                               history=history or {})
                    for m in ("fast", "B", "serial")
                }
                for k, v in pred_raw.items():
                    _lo = float(MODES[k].get("quality_low", MODES[k]["quality"]))
                    _hi = float(MODES[k]["quality"])
                    pred[k] = round(max(_lo, min(_hi, 0.5 * v + 0.5 * _lo)), 4)
                try:
                    from dgtf_v2.quality_predictor import predict_lower
                    for _m in ("fast", "B", "serial"):
                        _lv = predict_lower(model, features, route_n=4,
                                            rounds_avg=2.0, web=bool(require_web),
                                            mode=_m, history=history or {})
                        if _lv is not None:
                            _lower[_m] = round(float(_lv), 4)
                    if _lower:
                        _conf = dict(model.get("conformal") or {})
                except Exception as _ce:  # noqa: BLE001
                    quality_guard = "conformal_error: %s" % _ce
                if (min_quality is not None and _first_mode == "fast"
                        and _lower.get("fast", 1.0) < min_quality
                        and _lower.get("B", 0.0) >= min_quality):
                    first = {"mode": "B", "info": dict(MODES["B"]),
                             "reason": "保形下界：fast %.3f < %.2f ≤ B %.3f，直接选 B"
                                       % (_lower.get("fast", 0.0), min_quality,
                                          _lower.get("B", 0.0)),
                             "config": dict(MODE_CONFIGS["B"]), "web": False}
                    plan["mode"] = "B"
                    plan["config"] = dict(MODE_CONFIGS["B"])
                    quality_guard = "fast→B by conformal lower"
                elif (min_quality is not None and _first_mode == "fast"
                        and _lower.get("fast", 0.0) >= min_quality):
                    quality_guard = "conformal lower: fast meets target"
                elif (min_quality is not None and _first_mode == "fast"
                        and _lower and _lower.get("B", 0.0) < min_quality):
                    quality_guard = "conformal abstain：所有模式下界 < 目标"
        except Exception as exc:  # noqa: BLE001
            plan["quality_prediction_error"] = str(exc)
    if cascade and not require_web and plan["mode"] == "fast":
        plan["cascade"] = {"on_quality_below": min_quality,
                           "upgrade_to": "B",
                           "why": "fast 先跑；实测质量低于目标再升级 B（用时间换质量）"}
    plan["first"] = first
    plan["policy"] = "B/serial/fast 三模式按约束枚举取最优；quality 优先默认 B"
    if pred:
        plan["quality_prediction_raw"] = {k: round(v, 4) for k, v in pred.items()}
        plan["quality_prediction"] = pred
        plan["quality_prediction_kind"] = "ridge+mode_prior(0.5/0.5)"
    if _lower:
        plan["quality_prediction_lower"] = _lower
    if _conf:
        plan["conformal"] = _conf
    if require_web:
        plan["web_required"] = True
        plan["web_reading"] = dict(WEB_READING)
    if quality_guard:
        plan["quality_guard"] = quality_guard
    return plan


def scenario_table() -> List[dict]:
    """不同场景下的选择（用于文档/App 展示；最优性证据在 select_mode 返回里）。"""
    scenarios = [
        ("质量/墙钟优先", {"min_quality": 0.99, "prefer": "quality"}),
        ("墙钟 <=900s", {"min_quality": 0.9, "max_wall": 900, "prefer": "quality"}),
        ("tokens <=1.0M", {"min_quality": 0.95, "max_tokens": 1000000,
                           "prefer": "quality"}),
        ("必须联网", {"min_quality": 0.9, "require_web": True}),
        ("最快", {"min_quality": 0.9, "prefer": "wall"}),
    ]
    out = []
    for name, kw in scenarios:
        r = select_mode(**kw)
        out.append({"scenario": name, "mode": r.get("mode"),
                    "web": bool(r.get("web")),
                    "reason": r.get("reason"),
                    "quality": (r.get("info") or {}).get("quality"),
                    "tokens": (r.get("info") or {}).get("tokens"),
                    "wall": (r.get("info") or {}).get("wall"),
                    "optimality": r.get("optimality")})
    return out



# ── 实测场景矩阵（2026-10-25 Round 4，引擎 CLI 真跑）────────────────────
# 用途：把「不同场景/领域/维度」的实测最优形态写成机器可读表，供 App/M4 选档
# 与文档展示。数字全部来自 docs/ab_results.jsonl 的同题真跑（引擎 V2.2.3，
# configs/道生专属模式.yaml，web 按场景开关）。
MEASURED_SCENARIOS: Dict[str, dict] = {
    "reasoning": {
        "label": "推理/机制解释",
        "question": "为什么城市热岛效应在夜间比白天更明显？",
        "runs": {
            "auto": {"quality": 0.9465, "tokens": 723064, "calls": 97,
                     "wall": 586.2, "verified": True,
                     "config": "B parallel + thinking auto + rounds auto"},
            "serial": {"quality": 0.9456, "tokens": 644954, "calls": 89,
                       "wall": 1019.0, "verified": True,
                       "config": "serial + thinking auto + rounds auto"},
            "fast": {"quality": 0.9366, "tokens": 481050, "calls": 89,
                     "wall": 188.4, "verified": True,
                     "config": "B parallel + thinking off + rounds auto"},
            "fast_domain2": {"quality": 0.9535, "tokens": 579083, "calls": 98,
                             "wall": 282.7, "verified": True,
                             "question": "为什么冬天的静电现象比夏天更常见？",
                             "config": "B parallel + thinking off + rounds auto"},
            "fast_domain3": {"quality": 0.9687, "tokens": 588198, "calls": 98,
                             "wall": 212.0, "verified": True,
                             "question": "为什么飞机在起飞前要除冰？",
                             "config": "B parallel + thinking off + rounds auto"},
            "fast4": {"quality": 0.9376, "tokens": 546566, "calls": 98,
                      "wall": 230.3, "verified": True,
                      "question": "为什么海水是咸的？（fast 回归）",
                      "config": "B parallel + thinking off + rounds auto"},
        },
        "rules": {
            "quality_first": "auto",
            "cost_first": "fast",
            "low_tokens": "fast",
            "note": ("fast 已在三个推理域验证（0.9366 / 0.9535 / 0.9687 vs auto 0.9465；"
                     "差值在单跑方差内），tokens −33%、墙钟 −68~75% ⇒ 成本档首选；"
                     "serial 只省 11% tokens 但墙钟 +74%，已被 fast/auto 支配"
                     "（仅作历史对照保留）"),
        },
    },
    "choice": {
        "label": "选择/决策",
        "question": "在城市热岛研究中，应该优先补观测还是优先统一定义？",
        "runs": {
            "auto": {"quality": 0.9487, "tokens": 842151, "calls": 98,
                     "wall": 869.3, "verified": True,
                     "config": "B parallel + thinking auto + rounds auto"},
            "fast": {"quality": 0.9481, "tokens": 593788, "calls": 97,
                     "wall": 272.8, "verified": True,
                     "config": "B parallel + thinking off + rounds auto"},
            "fast2": {"quality": 0.9497, "tokens": 672011, "calls": 109,
                      "wall": 219.6, "verified": True,
                      "question": "在选择保温材料时应该优先考虑导热系数还是防火等级？",
                      "config": "B parallel + thinking off + rounds auto"},
            "auto3": {"quality": 0.9387, "tokens": 976311, "calls": 98,
                      "anchor_status": "pending_live",
                      "wall": 905.5, "verified": True,
                      "question": "以下哪项属于可再生能源？"
                                  "A. 煤炭 B. 太阳能 C. 石油 D. 天然气",
                      "config": "B parallel + thinking auto + web auto"
                                "（选项题官方源豁免后）"},
        },
        "rules": {"quality_first": "auto", "cost_first": "fast",
                  "note": ("fast 实测与 auto 同质量（0.9481 vs 0.9487，差值在单跑方差内），"
                           "tokens −30%、墙钟 −69% ⇒ 成本档/多数场景可用；"
                           "质量优先仍保留 auto（thinking 保留更稳）")},
    },
    "fact": {
        "label": "事实/数值",
        "question": "光在水中传播的速度是多少？",
        "runs": {
            "web_on_auto": {"quality": 0.9581, "tokens": 1154024, "calls": 108,
                            "wall": 965.7, "verified": True,
                            "config": "B parallel + thinking auto + web on"},
            "web_on_auto2": {"quality": 0.9764, "tokens": 1120591, "calls": 109,
                             "wall": 1218.5, "verified": True,
                             "question": "2024年中国GDP增速最新数据是多少？",
                             "config": "B parallel + thinking auto + web on"},
            "web_on_auto3": {"quality": 0.9062, "tokens": 992929, "calls": 101,
                             "wall": 958.0, "verified": True,
                             "question": "HTTP 404状态码表示什么？",
                             "config": "B parallel + thinking auto + web on"},
            "web_on_auto4": {"quality": 0.9153, "tokens": 973543, "calls": 101,
                             "wall": 965.9, "verified": True,
                             "question": "2024年中国GDP总量是多少亿元？"
                                         "（answer=1348066亿；probe flag 拉低质量分）",
                             "config": "B parallel + thinking auto + web on"},
            "web_on_fast_pre_fix": {"quality": 0.4741, "tokens": 836464,
                                    "anchor_status": "pending_live",
                                    "calls": 108, "wall": 316.1,
                                    "verified": False,
                                    "config": "B parallel + thinking off + web on",
                                    "answer_quality": "needs_evidence",
                                    "note": "修复前历史负结果（官方检索/审计未修时）"},
            "web_on_fast": {"quality": 0.9472, "tokens": 558195, "calls": 88,
                            "wall": 174.4, "verified": True,
                            "question": "HTTP 404状态码表示什么？",
                            "config": "B parallel + thinking off + web on"},
            "web_on_fast2": {"quality": 0.9726, "tokens": 738637, "calls": 107,
                             "wall": 202.2, "verified": True,
                             "question": "2024年中国GDP增速最新数据是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast3": {"quality": 0.9532, "tokens": 690842, "calls": 98,
                             "wall": 222.5, "verified": True,
                             "question": "长江的长度是多少千米？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast4": {"quality": 0.9508, "tokens": 727103, "calls": 98,
                             "wall": 275.6, "verified": True,
                             "question": "光在水中传播的速度是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast5": {"quality": 0.9633, "tokens": 746308, "calls": 101,
                             "wall": 291.1, "verified": True,
                             "question": "2024年中国GDP总量是多少亿元？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast6": {"quality": 0.9789, "tokens": 679027, "calls": 98,
                             "wall": 258.2, "verified": True,
                             "question": "中国现行宪法是哪一年颁布的？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast7": {"quality": 0.9625, "tokens": 592698, "calls": 91,
                             "wall": 238.4, "verified": True,
                             "question": "人体的正常体温是多少摄氏度？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast8": {"quality": 0.9417, "tokens": 686520, "calls": 97,
                             "wall": 281.4, "verified": True,
                             "question": "2024年中国CPI涨幅是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast9": {"quality": 0.9673, "tokens": 705691, "calls": 108,
                             "wall": 263.0, "verified": True,
                             "question": "2024年中国出生人口是多少万人？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast10": {"quality": 0.9900, "tokens": 793041, "calls": 108,
                              "wall": 272.9, "verified": True,
                              "question": "2024年中国新能源汽车产量是多少万辆？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast11": {"quality": 0.9495, "tokens": 684973, "calls": 98,
                              "wall": 271.1, "verified": True,
                              "question": "我国法定结婚年龄是多少岁？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast12": {"quality": 0.9431, "tokens": 749542, "calls": 101,
                              "wall": 283.4, "verified": True,
                              "question": "2024年中国贸易顺差是多少亿美元？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast13": {"quality": 0.9800, "tokens": 703097, "calls": 99,
                              "wall": 261.2, "verified": True,
                              "question": "中国恢复高考是哪一年？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast14": {"quality": 0.9800, "tokens": 670445, "calls": 98,
                              "wall": 260.1, "verified": True,
                              "question": "奥林匹克五环的颜色有哪几种？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast15": {"quality": 0.9460, "tokens": 649612, "calls": 97,
                              "wall": 229.9, "verified": True,
                              "question": "地球到月球的平均距离是多少千米？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast16": {"quality": 0.9900, "tokens": 644425, "calls": 98,
                              "wall": 243.0, "verified": True,
                              "question": "联合国的总部设在哪个城市？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast17": {"quality": 0.9507, "tokens": 661287, "calls": 98,
                              "wall": 250.4, "verified": True,
                              "question": "联合国的总部设在哪个城市？"
                                            "（地点收窄复验）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast18": {"quality": 0.9374, "tokens": 653047, "calls": 97,
                              "wall": 233.6, "verified": True,
                              "question": "2024年末中国外汇储备是多少亿美元？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast19": {"quality": 0.9900, "tokens": 656371, "calls": 100,
                              "wall": 247.3, "verified": True,
                              "question": "成年人正常心率是多少次每分钟？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast20": {"quality": 0.9200, "tokens": 708694, "calls": 98,
                              "wall": 205.0, "verified": True,
                              "question": "港珠澳大桥全长多少公里？"
                                            "（全长口径修复后）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast21": {"quality": 0.9900, "tokens": 704307, "calls": 98,
                              "wall": 192.1, "verified": True,
                              "question": "中国空间站的名字是什么？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast22": {"quality": 0.9768, "tokens": 682746, "calls": 98,
                              "wall": 244.3, "verified": True,
                              "question": "2024年我国粮食总产量是多少亿斤？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast23": {"quality": 0.9575, "tokens": 600637, "calls": 98,
                              "wall": 202.4, "verified": True,
                              "question": "民法典规定多少岁成年？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast24": {"quality": 0.9400, "tokens": 663063, "calls": 97,
                              "wall": 219.9, "verified": True,
                              "question": "中国最长的河流是哪条？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast25": {"quality": 0.9544, "tokens": 686721, "calls": 98,
                              "wall": 247.1, "verified": True,
                              "question": "水的沸点是多少摄氏度？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast26": {"quality": 0.9860, "tokens": 673064, "calls": 99,
                              "wall": 198.7, "verified": True,
                              "question": "中国最大的淡水湖是哪个？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast27": {"quality": 0.9523, "tokens": 661177, "calls": 98,
                              "wall": 200.4, "verified": True,
                              "question": "人体最大的器官是什么？"
                                            "（辟谣降权后）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast28": {"quality": 0.9446, "tokens": 575889, "calls": 90,
                              "wall": 182.4, "verified": True,
                              "question": "联合国安理会常任理事国共有几个？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast29": {"quality": 0.9476, "tokens": 543416, "calls": 88,
                              "wall": 154.1, "verified": True,
                              "question": "世界上海拔最高的高原是什么？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast30": {"quality": 0.9700, "tokens": 714718, "calls": 108,
                              "wall": 211.0, "verified": True,
                              "question": "2024年我国货物贸易进出口总值是多少万亿元？"
                                          "（display=43.85万亿元）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast31": {"quality": 0.9776, "tokens": 727457, "calls": 108,
                              "wall": 198.9, "verified": True,
                              "question": "世界上海拔最高的高原是什么？"
                                          "（命名题数值劫持修复后）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast32": {"quality": 0.9303, "tokens": 664454, "calls": 97,
                              "wall": 217.3, "verified": True,
                              "question": "三峡大坝全长多少米？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast33": {"quality": 0.9800, "tokens": 728616, "calls": 108,
                              "wall": 258.6, "verified": True,
                              "question": "我国义务教育法规定小学入学年龄是多少岁？"
                                          "（法定例外条款修复后，display=六周岁）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast34": {"quality": 0.9682, "tokens": 760055, "calls": 108,
                              "wall": 262.2, "verified": True,
                              "question": "我国成年人高血压的诊断标准是多少？"
                                          "（display=140/90毫米汞柱）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast35": {"quality": 0.9973, "tokens": 647188, "calls": 98,
                              "wall": 240.1, "verified": True,
                              "question": "世界卫生组织总部设在哪个城市？"
                                          "（display=日内瓦）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast36": {"quality": 0.9809, "tokens": 764986, "calls": 107,
                              "wall": 238.1, "verified": True,
                              "question": "我国现行法定节假日一年共有多少天？"
                                          "（逐项聚合法，display=13天）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast37": {"quality": 0.9800, "tokens": 759199, "calls": 110,
                              "wall": 300.0, "verified": True,
                              "question": "我国现行个人所得税起征点是多少元？"
                                          "（display=5000元）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast38": {"quality": 0.9671, "tokens": 705631, "calls": 98,
                              "wall": 267.0, "verified": True,
                              "question": "中国空间站由几个舱段组成？"
                                          "（display=三舱）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast39": {"quality": 0.9800, "tokens": 623031, "calls": 99,
                              "wall": 208.6, "verified": True,
                              "question": "截至2024年底我国高速公路总里程是多少万公里？"
                                          "（display=19.07万公里）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast40": {"quality": 0.9771, "tokens": 647386, "calls": 98,
                              "wall": 267.4, "verified": True,
                              "question": "奥运会每隔几年举办一次？"
                                          "（display=每4年）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast41": {"quality": 0.9782, "tokens": 790366, "calls": 109,
                              "wall": 283.5, "verified": True,
                              "question": "2024年我国居民人均可支配收入是多少元？"
                                          "（display=41314元）",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast42": {"quality": 0.9639, "tokens": 683419, "calls": 96,
                              "wall": 260.6, "verified": True,
                              "question": "嫦娥六号是哪一年发射的？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast43": {"quality": 0.9409, "tokens": 711596, "calls": 100,
                              "wall": 276.8, "verified": True,
                              "question": "成年人每天建议的睡眠时间是多少小时？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast44": {"quality": 0.9857, "tokens": 635713, "calls": 98,
                              "wall": 334.5, "verified": True,
                              "question": "HTTP 404状态码表示什么？"
                                          "（dual_judge local 合并后真跑）",
                              "config": "B parallel + thinking off + web on"},
            "web_off_auto": {"quality": 0.4440, "tokens": 1015910, "calls": 111,
                             "wall": 980.3, "verified": False,
                             "config": "B parallel + thinking auto + web off",
                             "answer_quality": "unverified"},
        },
        "rules": {
            "quality_first": "web_on_auto",
            "cost_first": "web_on_fast",
            "requires_web": True,
            "forbid": ["web_off_auto", "web_on_fast_pre_fix"],
            "note": ("事实门需要官方证据（web on）；2026-10-25 修复后重测："
                     "fast + web on（thinking off）质量 0.9472/0.9726 且 verified，"
                     "tokens −34~44%、墙钟 −82% ⇒ 成本档可用。"
                     "旧 0.4741/needs_evidence 为修复前历史（保留对照）。"
                     "「事实题无 web」仍是双输档。"),
        },
    },
}

KIND_BUCKETS = ("reasoning", "choice", "fact")


def measured_matrix() -> List[dict]:
    """返回实测场景矩阵（扁平列表，便于 App/文档渲染）。"""
    out = []
    for kind, cfg in MEASURED_SCENARIOS.items():
        for mode, run in (cfg.get("runs") or {}).items():
            out.append({"scenario": kind, "label": cfg.get("label", kind),
                        "mode": mode, "question": cfg.get("question", ""),
                        "quality": run.get("quality"),
                        "verified": run.get("verified"),
                        "tokens": run.get("tokens"),
                        "calls": run.get("calls"),
                        "wall": run.get("wall"),
                        "config": run.get("config", ""),
                        "answer_quality": run.get("answer_quality", "")})
    return out


def kind_of_question(question: str) -> str:
    """题面→场景桶（轻量规则；未知返回 reasoning）。"""
    q = str(question or "")
    if not q.strip():
        return "reasoning"
    fact_markers = ("多少", "是什么", "表示什么", "什么意思", "什么含义",
                    "指什么", "哪一年", "是谁", "等于几", "速度",
                    "多少度", "几岁", "多远", "定义",
                    # ★ [Round 90] 地点/排序/选择型事实问句（App 事实档需 web on）
                    "哪个", "哪座", "哪条", "哪种", "哪里", "位于",
                    "设在", "最大", "最高", "最长", "最小")
    # ★ [Round 91] 选项题（A./B./C./D. ≥2）优先判 choice（App choice 档）
    _opt_marks = re.findall(r"(?:^|[\s（(])[A-DＡＢＣＤ]\s*[.、)）．]", q)
    if len(_opt_marks) >= 2:
        return "choice"
    choice_markers = ("还是", "或者", "应该", "如何取舍", "优先", "选择",
                      "方案")
    if any(k in q for k in choice_markers):
        return "choice"
    if any(k in q for k in fact_markers) and not any(
            k in q for k in ("为什么", "为何", "机制", "原因")):
        return "fact"
    return "reasoning"


def recommend_scenario(kind: str = "reasoning",
                       min_quality: Optional[float] = None,
                       max_wall: Optional[float] = None,
                       prefer: str = "quality") -> dict:
    """按实测场景矩阵给推荐档；不满足约束时回退并写入 reason。"""
    k = kind if kind in MEASURED_SCENARIOS else "reasoning"
    cfg = MEASURED_SCENARIOS[k]
    rules = cfg.get("rules") or {}
    runs = cfg.get("runs") or {}
    require_web = bool(rules.get("requires_web"))
    pool = {name: r for name, r in runs.items() if r.get("verified")}
    if not pool:
        return {"scenario": k, "mode": None, "reason": "该场景无 verified 实测档"}
    feasible = {}
    for name, r in pool.items():
        if min_quality is not None and float(r.get("quality") or 0) < min_quality:
            continue
        if max_wall is not None and float(r.get("wall") or 1e9) > max_wall:
            continue
        feasible[name] = r
    fallback = False
    if not feasible:
        feasible = pool
        fallback = True
    _qfirst = str(rules.get("quality_first") or "")
    if (prefer == "quality" and min_quality is None and max_wall is None
            and _qfirst in feasible):
        name = _qfirst
        reason = "按实测场景规则选择质量优先档（rules.quality_first）"
        return {"scenario": k, "label": cfg.get("label", k), "mode": name,
                "run": dict(feasible[name]), "require_web": require_web,
                "forbid": list(rules.get("forbid") or []), "reason": reason,
                "note": rules.get("note", "")}
    if prefer == "wall":
        name = min(feasible, key=lambda n: feasible[n].get("wall") or 1e9)
    elif prefer == "tokens":
        name = min(feasible, key=lambda n: feasible[n].get("tokens") or 1e18)
    else:
        name = max(feasible, key=lambda n: (feasible[n].get("quality") or 0,
                                            -(feasible[n].get("wall") or 1e9)))
    reason = "按实测场景矩阵选择（prefer=%s）" % prefer
    if fallback:
        reason = "无满足约束的档，回退为最接近档（prefer=%s）" % prefer
    return {"scenario": k, "label": cfg.get("label", k), "mode": name,
            "run": dict(feasible[name]), "require_web": require_web,
            "forbid": list(rules.get("forbid") or []), "reason": reason,
            "note": rules.get("note", "")}


# ── App 维度实测跑次（2026-10-25 e2e 真跑，Round 27）────────────────────
# 用途：场景矩阵此前只有引擎 CLI 维度；App 端到端（含 plan/编排/归档）的实际
# 成本-质量需要独立锚点，供 App 展示与动态选档参考。
MEASURED_APP_RUNS: List[dict] = [
    {"id": "app-fast-reasoning", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "reasoning", "question": "为什么在高原上煮饭更容易夹生？",
     "quality": 0.9588, "tokens": 698602, "calls": 107, "wall": 573.3,
     "verified": True, "ready": True, "plan": "fast/thinking off/web off"},
    {"id": "app-fast-fact", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "HTTP 500状态码表示什么？",
     "quality": 0.9740, "tokens": 745091, "calls": 99, "wall": 493.0,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-population", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "2024年中国出生人口是多少万人？",
     "quality": 0.9724, "tokens": 567594, "calls": 87, "wall": 385.8,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-legal", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "我国法定结婚年龄是多少岁？",
     "quality": 0.9769, "tokens": 719919, "calls": 97, "wall": 465.0,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-hr", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "成年人正常心率是多少次每分钟？",
     "quality": 0.9581, "tokens": 640366, "calls": 90, "wall": 403.3,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-hzmb", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "港珠澳大桥全长多少公里？",
     "quality": 0.9744, "tokens": 658091, "calls": 87, "wall": 353.2,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-adult", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "民法典规定多少岁成年？",
     "quality": 0.9677, "tokens": 637098, "calls": 96, "wall": 423.2,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-unhq", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "联合国的总部设在哪个城市？",
     "quality": 0.9288, "tokens": 689975, "calls": 96, "wall": 442.9,
     "verified": True, "ready": True,
     "plan": "fast/thinking off/web on（地点问句分类修复后）"},
    {"id": "app-fast-choice-renew", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "choice", "question": "以下哪项属于可再生能源？"
     "A. 煤炭 B. 太阳能 C. 石油 D. 天然气",
     "quality": 0.9516, "tokens": 776826, "calls": 97, "wall": 392.8,
     "verified": True, "ready": True,
     "plan": "fast/thinking off/web on（选项题 web 强制+uncovered 豁免后）"},
    {"id": "app-fast-fact-birth", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "2024年中国出生人口是多少万人？",
     "quality": 0.9842, "tokens": 552847, "calls": 88, "wall": 392.9,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-grain", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "2024年我国粮食总产量是多少亿斤？",
     "quality": 0.9500, "tokens": 635524, "calls": 87, "wall": 423.6,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-quality-fact", "mode": "daosheng", "tier": "quality",
     "scenario": "fact", "question": "珠穆朗玛峰的海拔是多少米？",
     "quality": 0.9447, "tokens": 1182916, "calls": 112, "wall": None,
     "verified": True, "ready": True, "plan": "B/thinking auto/web on"},
]


def measured_app_runs() -> List[dict]:
    """App 维度实测跑次（扁平副本）。"""
    return [dict(x) for x in MEASURED_APP_RUNS]


def app_runs_summary() -> List[dict]:
    """按 (scenario, tier) 聚合 App 实测：均值质量/tokens/calls、verified 率。"""
    groups: Dict[tuple, List[dict]] = {}
    for r in MEASURED_APP_RUNS:
        groups.setdefault((str(r.get("scenario")), str(r.get("tier"))),
                          []).append(r)
    out = []
    for (sc, tier), rows in sorted(groups.items()):
        n = len(rows)
        out.append({
            "scenario": sc, "tier": tier, "n_runs": n,
            "quality_mean": round(sum(float(r.get("quality") or 0)
                                      for r in rows) / n, 4),
            "tokens_mean": int(sum(int(r.get("tokens") or 0)
                                   for r in rows) / n),
            "calls_mean": round(sum(int(r.get("calls") or 0)
                                    for r in rows) / n, 1),
            "walls": [r.get("wall") for r in rows],
            "verified_ratio": round(sum(1 for r in rows
                                        if r.get("verified")) / n, 3),
            "ready_ratio": round(sum(1 for r in rows
                                     if r.get("ready")) / n, 3),
        })
    return out

