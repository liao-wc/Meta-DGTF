# -*- coding: utf-8 -*-
"""[V2.2.19] 重写 mode_fusion 选档段：输入驱动 + 每模式专属参数 + 可证最优 + 动态调整。"""
from pathlib import Path

F = Path("dgtf_engine/dgtf_v2/mode_fusion.py")
src = F.read_text(encoding="utf-8")
MARK = "# ── 实测场景矩阵（2026-10-25 Round 4，引擎 CLI 真跑）"
i = src.index(MARK)
tail = src[i:]
assert "MEASURED_SCENARIOS" in tail

HEAD = '''# -*- coding: utf-8 -*-
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
    return {"prefer": prefer, "min_quality": min_quality,
            "max_wall": max_wall, "max_tokens": max_tokens,
            "require_web": require_web, "kind": kind,
            "long_question": bool(long_q),
            "features_used": bool(features),
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
    chosen = _choose(feasible, prefs["prefer"])
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
    if (wall_over or token_over) and mode != "fast" and qprox is None:
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
                             "reason": "保形下界：fast %.3f < %.2f <= B %.3f，直接选 B"
                                       % (_lower.get("fast", 0.0), min_quality,
                                          _lower.get("B", 0.0)),
                             "config": dict(MODE_CONFIGS["B"]), "web": False}
                    plan["mode"] = "B"
                    plan["config"] = dict(MODE_CONFIGS["B"])
                    quality_guard = "fast->B by conformal lower"
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

'''
F.write_text(HEAD + "\n\n" + tail, encoding="utf-8")
import py_compile
py_compile.compile(str(F), doraise=True)
print("OK rewrite mode_fusion.py", len(F.read_text(encoding="utf-8")), "bytes")
