# ============================================================
# 统一自适应调度器
# ============================================================
# 【要解决的问题】本版之前，「自动」散在 8 处：main() 里三条纯规则、
#   run() 里两次 LLM 调用、_route_by_decidability 一处，停止 / 降级 / 配额
#   写死在配置里。读者无法回答「这一次到底是**谁**定了 route / 圈数 / 联网」；
#   也没有任何一项能单独交给 auto —— 想「只让 auto 管圈数、其余固定」做不到。
#
# 【本版做法】把十二项收进**一个调度器**，逐项独立：
#       route / cost_profile / mode / rounds / orientation /
#       web / thinking / effort / stop / web_downgrade /
#       decidability / landing
#   每项按同一优先级取 4 个来源之一，并**逐项留痕**：
#       explicit（命令行显式给了） > config（配置被改过） > auto > default
#   ★ 铁律：explicit 或 config 给了，auto **就不碰那一项**（逐项独立，
#     不是「一个总开关管全部」）。
#   ★ 全关开关：`auto.enabled=false` ⇒ 全项退回 config/default，
#     行为与上一版逐字相同（判据守着这条）。
#
# 【auto 的输入】三样，全部本地可得、**零 LLM**：
#     ① 题型特征（`_auto_features`，纯规则，复用 `_has_decision_context`）
#     ② 成本质量意图（cost_profile / effort 的显式值、rounds 的效率约束）
#     ③ 历史读数（`_auto_history`，扫最近 N 份 `*.packed.json`）
#   auto 的**输出**是该项的值 + 理由，全部写进产物头部，可复盘。
#
# 【设计纪律】
#   · 每项都是可单独测的纯函数 `_auto_pick_<项>(feat, hist, cfg)`；
#   · 不引入任何新的判定语义 —— 停止 / 降级 / 配额本就是**配置驱动**的，
#     auto 接手的方式是「按题型与历史算出更合适的配置值」，判据本身一行未改；
#   · 历史读不到（0 份样本）时一律走「无历史」分支，不猜、不崩。
_AUTO_ITEM_ORDER = ("route", "cost_profile", "mode", "rounds", "orientation",
                    "web", "thinking", "effort", "stop", "web_downgrade",
                    "decidability", "landing")

_AUTO_ITEM_LABEL = {
    "route": "层集合",
    "cost_profile": "成本档",
    "mode": "并行模式",
    "rounds": "圈数",
    "orientation": "取向路由",
    "web": "联网检索",
    "thinking": "思考",
    "effort": "思考强度",
    "stop": "停止阈值",
    "web_downgrade": "联网降级",
    "decidability": "可判定性判定",
    "landing": "落地层模板",
}

_AUTO_SRC_LABEL = {
    "explicit": "显式",
    "config": "配置",
    "auto": "auto",
    "default": "默认",
}

_AUTO_PROFILES_ORDER = ("quality", "balanced", "economy")

_AUTO_META_MARKS = ("本身", "自身", "递归", "元", "整体", "到底")

#: 该项「配置给了」的判定路径（任一被改过即算）。值 = 路径元组的列表。
_AUTO_CONFIG_PATHS = {
    "cost_profile": [("cost_profile",)],
    "web": [("runtime", "web")],
    "thinking": [("runtime", "thinking")],
    "effort": [("runtime", "effort")],
    "mode": [("actions", "parallel_mode")],
    "stop": [("spiral", "round_stall_limit"),
             ("spiral", "round_idle_limit")],
    "web_downgrade": [("web_search", "auto_disable_after_failures"),
                      ("web_search", "quota", "per_run_total")],
}


def _auto_enabled(cfg) -> bool:
    """总开关。缺省 True（出厂即接管）；显式 false 回到 v1.23.12 行为。"""
    return bool(((cfg or {}).get("auto") or {}).get("enabled", True))


def _auto_save_dir(cfg) -> str:
    return str(((cfg or {}).get("output") or {}).get("save_dir", "outputs"))


def _cfg_get_path(cfg, path, default=None):
    cur = cfg
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _cfg_has_path(cfg, path) -> bool:
    """配置里**改过**该路径（与出厂 DEFAULT_CONFIG 不同）才算「配置给了」。"""
    _cur, _def = _cfg_get_path(cfg, path), _cfg_get_path(DEFAULT_CONFIG, path)
    return _cur is not None and _cur != _def


def _cfg_overridden(cfg, name) -> bool:
    return any(_cfg_has_path(cfg, p) for p in _AUTO_CONFIG_PATHS.get(name, []))


def _set_cfg_path(cfg, path, value) -> None:
    cur = cfg
    for k in path[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[path[-1]] = value


def _auto_normalize_explicit(ex) -> dict:
    """把命令行原值归一成调度器的取值域（`auto` / 空串 = 没给 ⇒ None）。

    ★ 不做归一化会把 `--web auto` 当成「显式给了 on」—— `"auto"` 是**真值**
      字符串，直接用会静默把「没指定」记成「显式指定」。
    """
    out = {}
    for k, v in dict(ex or {}).items():
        if v is None:
            continue
        if k in ("web", "thinking"):
            s = str(v).strip().lower()
            if s == "auto":
                continue
            out[k] = {"on": True, "off": False}.get(s)
            if out[k] is None:
                out.pop(k)
            continue

        if k in ("cost_profile", "mode", "orientation", "landing",
                 "decidability"):
            s = str(v).strip()
            if not s or s.lower() == "auto":
                continue
            out[k] = s
            continue
        if k == "effort":
            s = str(v).strip().lower()
            if not s or s == "auto":
                continue
            out[k] = s
            continue
        if k == "route":
            if isinstance(v, (list, tuple)):
                _r = [str(x).strip() for x in v if str(x).strip()]
            else:
                _r = [x.strip() for x in str(v).split(",") if x.strip()]
            if not _r:
                continue
            out[k] = _r
            continue
        if k == "rounds":
            s = str(v).strip()
            if not s or s == "0":
                continue
            out[k] = s
            continue
        out[k] = v
    return out


# ------------------------------------------------------------
# ① 题型特征（纯规则，零 LLM）
# ------------------------------------------------------------
def _auto_features(question: str) -> dict:
    """题型 + 规模 + 意图线索。全部来自题面字符，可复现、可断言。"""
    q = str(question or "").strip()
    return {
        "len": len(q),
        "blank": not q,
        "fact": (not q) or (not _has_decision_context(q)),
        "meta": any(k in q for k in _AUTO_META_MARKS),
        "multi": (q.count("，") + q.count(",")) >= 3,
        "choice": ("或" in q) or ("还是" in q),
        "how": any(k in q for k in ("如何", "怎样", "怎么")),
        "what": any(k in q for k in ("是什么", "为什么")),
        "short": 0 < len(q) <= 40,
    }


# ------------------------------------------------------------
# ② 历史读数（扫最近 N 份 packed，零 LLM）
# ------------------------------------------------------------
def _auto_history(save_dir, limit: int = 20) -> dict:
    """从历次真跑的 `*.packed.json` 里抽可复用的读数。

    ★ 为什么读 packed 而不另建统计文件：packed 是**每次运行必然落盘**的全量
      快照，已含 llm_calls / tri_state / dispatch / pools.web_results。
      再建一份统计 = 同一条逻辑第二份实现（本项目头号复发问题）。
    ★ 只读最近 `limit` 份（按 mtime 倒序）；单份解析失败只跳过该份 ——
      「零样本」「半损坏」都必须能跑，调度层不是新的崩溃点。
    """
    h = {
        "n": 0, "calls_med": 0, "tokens_med": 0,
        "tri_rate": None, "cut_rate": None,
        "layer_rounds": {}, "modes": {}, "profiles": {},
        "web_hit": 0, "web_fail": 0, "web_empty": 0, "mismatch": 0,
    }
    try:
        _d = Path(str(save_dir or "outputs"))
        if not _d.is_dir():
            return h
        _fs = sorted(_d.glob("*.packed.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
        _fs = _fs[:max(1, int(limit or 20))]
    except Exception as exc:  # noqa: BLE001
        logger.warning("调度历史：列目录失败，按无历史处理（%s）", exc)
        return h

    calls, toks, tris = [], [], []
    cut = nat = 0
    layer_rounds = {}
    for f in _fs:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                continue
        except Exception:  # noqa: BLE001
            continue
        h["n"] += 1
        try:
            calls.append(int(d.get("llm_calls") or 0))
            toks.append(int(d.get("llm_tokens") or 0))
        except (TypeError, ValueError):
            pass
        _tri = d.get("tri_state") or [0, 0]
        try:
            _ag, _tt = int(_tri[0]), int(_tri[1])
            if _tt > 0:
                tris.append(_ag / _tt)
        except (TypeError, ValueError, IndexError):
            pass
        for _e, _v in (d.get("views") or {}).items():
            _sr = str((_v or {}).get("stop_reason") or "")
            if _sr:
                if any(_m in _sr for _m in _STOP_CUT_MARKS):
                    cut += 1
                else:
                    nat += 1
            _rn = (_v or {}).get("rounds")
            if isinstance(_rn, int) and _rn > 0:
                layer_rounds.setdefault(_e, []).append(_rn)
        _pm = str(((d.get("dispatch") or {}).get("_parallel_mode")) or "")
        if _pm:
            h["modes"][_pm] = h["modes"].get(_pm, 0) + 1
        _pf = str(d.get("cost_profile") or "")
        if _pf:
            h["profiles"][_pf] = h["profiles"].get(_pf, 0) + 1
        try:
            _ap = d.get("_auto_plan_used") or {}
            _sug = str(_ap.get("orientation") or "")
            _act = str(d.get("orientation") or "")
            if _sug and _act and _sug != _act:
                h["mismatch"] += 1
        except Exception:  # noqa: BLE001
            pass
        for _p in (d.get("pools") or {}).values():
            if not isinstance(_p, dict):
                continue
            h["web_hit"] += len(_p.get("web_results") or [])
            h["web_fail"] += len(_p.get("web_errors") or [])
            for _m in (_p.get("meta") or []):
                if "[W-EMPTY]" in str(_m):
                    h["web_empty"] += 1

    def _med(xs):
        xs = sorted(x for x in xs if x)
        return xs[len(xs) // 2] if xs else 0

    h["calls_med"] = _med(calls)
    h["tokens_med"] = _med(toks)
    if tris:
        h["tri_rate"] = sum(tris) / len(tris)
    if cut + nat:
        h["cut_rate"] = cut / (cut + nat)
    h["layer_rounds"] = {k: _med(v) for k, v in layer_rounds.items()}
    return h


# ------------------------------------------------------------
# ③ 十二项策略（各自适应条件）
#   返回 (值, 理由)。返回 None = **auto 不表态**（按配置/默认）。
# ------------------------------------------------------------
def _auto_pick_cost_profile(feat, hist, cfg):
    """成本档：先按题型定基线，再按历史成本与质量读数微调。"""
    if feat["fact"] and feat["short"]:
        base, why = "economy", "事实型短题（无决策语境）"
    elif feat["meta"] or feat["choice"]:
        base, why = "balanced", "含元层/选择，需要摊开"
    else:
        base, why = "balanced", "决策型题面，用 token 精简档"
    _tm = int(hist.get("tokens_med") or 0)
    _tr = hist.get("tri_rate")
    if _tm >= 400000 and base == "balanced":
        base, why = "economy", why + "；历史 token 中位 %d 偏高，降一档" % _tm
    if _tr is not None and _tr < 0.5 and base == "economy" and not feat["fact"]:
        base, why = "balanced", "历史三态一致率 %.2f 偏低，不降到 economy" % _tr
    return base, why


def _auto_pick_web(feat, hist, cfg):
    """联网：事实题与「要外部标准」的题默认接；历史收 0 条则不再接。"""
    _n = int(hist.get("n") or 0)
    if _n >= 3 and int(hist.get("web_hit") or 0) == 0 \
            and int(hist.get("web_empty") or 0) >= 3:
        return False, ("历史 %d 份里联网入池 0 条、空结果 ≥3 次，该类题不再"
                       "自动接入（要接：--web on）" % _n)
    if feat["fact"]:
        return True, "事实型询问：史实结论需要外部证据支撑"
    if feat["meta"] or feat["how"]:
        return True, "含元层/过程：需要外部标准与先例"
    return None, "既非事实型也无外部标准需求"


def _auto_pick_thinking(feat, hist, cfg):
    if feat["fact"] and feat["short"]:
        return False, "事实型短题：一次判定够用，省 token"
    if feat["meta"] or feat["choice"]:
        return True, "含元层/选择：需要跨步推理"
    return None, "无明确信号"


def _auto_pick_effort(feat, hist, cfg):
    if feat["meta"] or feat["choice"] or feat["how"]:
        return "high", "含元层/选择/过程：拉高思考强度"
    if feat["fact"] and feat["short"]:
        return "low", "事实型短题：低强度"
    return None, "无明确信号"


def _auto_pick_route(feat, hist, cfg):
    """层集合：默认全四层；只在有正当理由时才砍（`auto.allow_route_trim` 可关）。"""
    if not bool(((cfg or {}).get("auto") or {}).get("allow_route_trim", True)):
        return list(_ENTRIES), "auto.allow_route_trim=false：不砍层"
    _cr = hist.get("cut_rate")
    if _cr is not None and _cr >= 0.5:
        return list(_ENTRIES), ("历史被截断率 %.2f 偏高，样本不足，"
                                "保留全四层" % _cr)
    if feat["meta"] or feat["choice"] or feat["how"] or feat["multi"]:
        return list(_ENTRIES), "题面需要对撞/元层"
    if feat["fact"] and feat["short"]:
        return ["0", "1", "both"], "事实型短题：元层不参与判定，砍掉省一段"
    return list(_ENTRIES), "无砍层依据，保留全四层"


def _auto_pick_orientation(feat, hist, cfg):
    """取向路由：决定是否按可判定性砍层（与落地层模板**已解耦**）。"""
    if feat["fact"]:
        return "boundary", "事实型询问：要边界与事实，不要行动方案"
    if feat["meta"] or feat["how"] or feat["choice"]:
        return "decision", "含元层/过程/选择：要可落地方案"
    _mm = int(hist.get("mismatch") or 0)
    if _mm >= 2:
        return "decision", "历史取向错配 %d 次，保守取 decision" % _mm
    return "boundary", "无决策语境：保守走边界清单"


def _auto_pick_mode(feat, hist, cfg):
    """并行模式：规则能定时不调 LLM（省一次调用）；返回 `llm` = 交 LLM 兜底。"""
    if feat["blank"]:
        return "serial", "空题面"
    if feat["fact"] and feat["short"]:
        return "serial", "事实型短题：层间依赖强，无并行收益"
    if feat["meta"] and feat["multi"]:
        return "A", "多分句且含元层：四层可独立产出后汇流"
    if feat["choice"]:
        return "B", "含选择：需要震荡收敛"
    if feat["how"] and feat["multi"]:
        return "C", "多分句且讲过程：层界清楚，可流水线压缩时长"
    return "llm", "规则拿不准，交 LLM 决策"


def _auto_pick_rounds(feat, hist, cfg):
    """圈数：有历史就按「各层实际停在第几圈」+1，无历史按题型给基线。"""
    hard = int(((cfg or {}).get("spiral") or {}).get("hard_max", 12) or 12)
    soft = int(((cfg or {}).get("spiral") or {}).get("soft_max", 3) or 3)
    _lr = hist.get("layer_rounds") or {}
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    out = {}
    for e in _ENTRIES:
        _h = int(_lr.get(e) or 0)
        if _h > 0:
            _v = _h + 1
        elif feat["fact"] and feat["short"]:
            _v = _floor
        else:
            _v = max(soft, _floor) + 1
        out[e] = min(max(_v, _layer_floor(e, hard, _floor)),
                     _layer_ceil(e, hard, _floor))
    _src = ("历史各层停圈中位 %s +1" % _lr) if _lr else "无历史，按题型给基线"
    return out, _src


def _auto_pick_stop(feat, hist, cfg):
    """停止阈值：只调**阈值**，不动判据本身。"""
    if feat["fact"] and feat["short"]:
        return ({"round_stall_limit": 1, "round_idle_limit": 1},
                "事实型短题：收紧停滞阈值，早停")
    if feat["meta"]:
        return ({"round_stall_limit": 3, "round_idle_limit": 3},
                "含元层：放宽停滞阈值，允许更久收敛")
    return {}, "无明确信号，按配置"


def _auto_pick_web_downgrade(feat, hist, cfg):
    """联网降级：失败历史决定「连败几次置 disabled」，成本档决定配额。"""
    _f = int(hist.get("web_fail") or 0)
    _lim = 2 if _f >= 3 else (4 if _f == 0 else 3)
    _why = "历史联网失败 %d 条 ⇒ 连败阈值 %d" % (_f, _lim)
    _prof = _auto_pick_cost_profile(feat, hist, cfg)[0]
    _q = {"per_run_total": 30, "per_stage_total": 8, "per_stage_round": 2}
    if _prof == "economy":
        _q = {"per_run_total": 15, "per_stage_total": 4, "per_stage_round": 1}
        _why += "；economy 档配额减半"
    return {"auto_disable_after_failures": _lim, "quota": _q}, _why


def _auto_pick_decidability(feat, hist, cfg):
    """要不要花那次**外部可判定性评估**（route 侧那次 LLM 调用）。"""
    if feat["fact"] and feat["short"]:
        return False, "事实型短题：层集合已按题型定，不必再花一次外部评估"
    return True, "需要按可判定性决定砍层"


def _auto_pick_landing(feat, hist, cfg):
    """落地层模板 —— 与取向**已解耦**（取向管砍层，本项管产物形态）。"""
    if feat["fact"]:
        return "boundary", "事实型询问：要边界清单，不要行动闭环"
    if feat["meta"] or feat["how"] or feat["choice"]:
        return "decision", "含元层/过程/选择：要可落地方案"
    return "boundary", "无决策语境：边界清单"


_AUTO_PICKERS = {
    "cost_profile": _auto_pick_cost_profile,
    "web": _auto_pick_web,
    "thinking": _auto_pick_thinking,
    "effort": _auto_pick_effort,
    "route": _auto_pick_route,
    "orientation": _auto_pick_orientation,
    "mode": _auto_pick_mode,
    "rounds": _auto_pick_rounds,
    "stop": _auto_pick_stop,
    "web_downgrade": _auto_pick_web_downgrade,
    "decidability": _auto_pick_decidability,
    "landing": _auto_pick_landing,
}


def auto_dispatch(question: str, config=None, explicit=None,
                  save_dir=None, history=None) -> dict:
    """十二项一次算完。返回 dict：每项一个值 + `_items` 逐项来源留痕。

    ★ 逐项优先级：explicit > config（**改过**才认）> auto > default。
    ★ `auto.enabled=false` ⇒ 十二项一律不进 auto 分支（回 v1.23.12 行为）。
    ★ 纯函数：不改入参 config；写回配置由调用方调 `_apply_auto_dispatch`。
    """
    cfg = config if config is not None else load_config("")
    ex = _auto_normalize_explicit(explicit)
    feat = _auto_features(question)
    hist = history if history is not None else _auto_history(
        save_dir or _auto_save_dir(cfg),
        int(((cfg or {}).get("auto") or {}).get("history_limit", 20) or 20))
    _on = _auto_enabled(cfg)

    plan = {"_features": feat, "_history": hist, "_items": {}, "_auto_on": _on}
    for name in _AUTO_ITEM_ORDER:
        val, why = _AUTO_PICKERS[name](feat, hist, cfg)
        if ex.get(name) is not None:
            src, v = "explicit", ex[name]
        elif _cfg_overridden(cfg, name):
            src = "config"
            v = _cfg_get_path(cfg, _AUTO_CONFIG_PATHS[name][0], None)
        elif (not _on) or val is None:
            src, v = "default", None
            for _p in _AUTO_CONFIG_PATHS.get(name, []):
                _cv = _cfg_get_path(cfg, _p, None)
                # ★ 配置里的字面 `"auto"` 等于「没表态」（运行期三项的默认值
                #   就是它）；把它当成「配置给了」会把「没指定」记成「指定」。
                if _cv is not None and _cv != "auto":
                    v, src = _cv, "config"
                    break
            if v is None:
                v = val
                why = "auto 不表态（" + str(why) + "），不覆盖配置"
        else:
            src, v = "auto", val
        plan[name] = v
        plan["_items"][name] = {"value": v, "source": src,
                                "reason": why, "auto_value": val}
    return plan


def _apply_auto_dispatch(cfg: dict, plan: dict) -> List[str]:
    """把 plan 写进配置键（来源 ∈ {auto, 显式} 的项）。返回留痕行。

    ★★ 必须写 **explicit** 项，不能只写 auto 项 —— 这是本版首版的一个真 bug：
      explicit 的值原先只存在于 plan 里、没人搬进 cfg，于是
      `--web off` / `--profile quality` / `--thinking on` / `--effort max`
      **全部失效**（`_apply_runtime` 读到的还是配置里的 `auto`）。
      「来源」是给**留痕**用的（产物表里显示谁定的），不是给「写不写」用的。
    ★ 不写 config / default 项：它们的值本来就已在 cfg 里，再写是空转。
    ★ 停止 / 降级 / 配额本就是配置驱动 ⇒ auto 接手的落点就是这些键，
      不改任何判据语义（判据一行未动）。
    """
    notes: List[str] = []
    items = (plan or {}).get("_items") or {}

    def _is_mine(name):
        return (items.get(name) or {}).get("source") in ("auto", "explicit")

    if _is_mine("cost_profile"):
        cfg["cost_profile"] = str(plan["cost_profile"])
        notes.append("成本档 %s（%s）" % (plan["cost_profile"],
                                       items["cost_profile"]["reason"]))
    if _is_mine("web"):
        # ★ 写**运行期总控**而不是 `web_search.enabled` 本身 —— 后者的写入者
        #   是 `_apply_runtime`（唯一写入者）。两处都写等于同一条逻辑两条
        #   实现（本项目头号复发问题）。
        _set_cfg_path(cfg, ("runtime", "web"),
                      "on" if plan["web"] else "off")
        notes.append("联网 %s（%s）" % ("开" if plan["web"] else "关",
                                       items["web"]["reason"]))
    for _n in ("thinking", "effort"):
        if _is_mine(_n) and plan[_n] is not None:
            _v = plan[_n]
            _s = "on" if _v is True else ("off" if _v is False else str(_v))
            _set_cfg_path(cfg, ("runtime", _n), _s)
            notes.append("%s %s（%s）" % (_AUTO_ITEM_LABEL[_n], _s,
                                          items[_n]["reason"]))
    if _is_mine("web_downgrade") and isinstance(plan["web_downgrade"], dict):
        _wd = plan["web_downgrade"]
        _set_cfg_path(cfg, ("web_search", "auto_disable_after_failures"),
                      int(_wd.get("auto_disable_after_failures", 3)))
        for _k, _v in (_wd.get("quota") or {}).items():
            _set_cfg_path(cfg, ("web_search", "quota", _k), int(_v))
        notes.append("联网降级（%s）" % items["web_downgrade"]["reason"])
    if _is_mine("stop") and isinstance(plan["stop"], dict) and plan["stop"]:
        for _k, _v in plan["stop"].items():
            _set_cfg_path(cfg, ("spiral", _k), int(_v))
        notes.append("停止阈值（%s）" % items["stop"]["reason"])
    return notes


def _auto_dispatch_lines(res: dict) -> List[str]:
    """产物头部的「自动调度 · 逐项来源」表（无 plan 时返回空）。"""
    plan = res.get("_auto_dispatch")
    if not isinstance(plan, dict) or not (plan.get("_items") or {}):
        return []
    items = plan["_items"]
    _on = plan.get("_auto_on", True)
    _feat = plan.get("_features") or {}
    _hist = plan.get("_history") or {}
    _n_auto = sum(1 for v in items.values()
                  if (v or {}).get("source") == "auto")
    out = ["**自动调度**（十二项逐项来源；%s，auto 接管 %d 项）\n\n"
           % ("总开关开" if _on else "总开关**关**", _n_auto)]
    out.append("| 项 | 取值 | 来源 | 理由 |\n|---|---|---|---|\n")
    for _k in _AUTO_ITEM_ORDER:
        _it = items.get(_k) or {}
        _v = _it.get("value")
        if isinstance(_v, dict):
            _v = "／".join("%s=%s" % (a, b) for a, b in _v.items()) or "（无）"
        elif isinstance(_v, list):
            _v = "、".join(str(x) for x in _v)
        elif isinstance(_v, bool):
            _v = "开" if _v else "关"
        elif _v is None:
            _v = "（不覆盖）"
        out.append("| %s | %s | %s | %s |\n"
                   % (_AUTO_ITEM_LABEL.get(_k, _k), _v,
                      _AUTO_SRC_LABEL.get(_it.get("source"),
                                          _it.get("source")),
                      str(_it.get("reason") or "")[:120]))
    out.append("\n- 题型特征：%s\n"
               % "、".join("%s=%s" % (k, v) for k, v in _feat.items()))
    out.append("- 历史读数：%d 份 · tokens 中位 %s · 三态一致率 %s · "
               "被截断率 %s · 联网 收%s/失败%s · 取向错配 %s\n"
               % (int(_hist.get("n") or 0), _hist.get("tokens_med") or "—",
                  ("%.2f" % _hist["tri_rate"]) if _hist.get("tri_rate")
                  is not None else "—",
                  ("%.2f" % _hist["cut_rate"]) if _hist.get("cut_rate")
                  is not None else "—",
                  _hist.get("web_hit", 0), _hist.get("web_fail", 0),
                  _hist.get("mismatch", 0)))
    out.append("- 各项可取 `显式 ＞ 配置 ＞ auto ＞ 默认`；"
               "想固定某项：命令行显式传（来源显示「显式」）。\n\n")
    return out
