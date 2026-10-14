# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮：把「四层目标语义」编码进引擎与 AutoTune。

用户定义的四层目标（战略指令）：
  · 修行层(0)：最少圈数把问题的各不同层面**挖到不能再挖** ⇒ **趋近无穷收敛**。
  · 研究层(1)：最少圈数给各层面**确定的答案** ⇒ **趋近有限收敛**。
  · 对撞层(both)：把**无穷发散的层面**与**有限确定的层面融合生成** ⇒ 创新层面。
  · 元层(all)：对三层**所有产物**做**记忆结晶 / 决策 / 行动**，并**回看整个过程**。

本轮落地三件事（全部走「读数 + 判据 + 变异体」，不发明新分数）：
  1. `layer_goal_readings(views)` 纯函数：把 `views` 压成**每层一条目标读数**，
     读数**分开报**、算不出回 None（绝不 0 冒充）。
  2. `episode_from_result` 增写 `goal_readings` 出口（否则 AutoTune 读不到）。
  3. `autotune_score` 增 `quality_goal` 口径（按层目标聚合），并新增
     `autotune_progress()` —— **中期动态调整**判据：同一 (mode,route) 的
     目标读数随轮次是否在改善 ⇒ 决定继续 / 收敛 / 回滚。

写文件铁律：read_bytes → 断言纯 CRLF → 转 LF → replace（锚点命中==1）
          → 转回 CRLF → write_bytes。绝不用 write_text。
"""
import io
import sys
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    b = p.read_bytes()
    t = b.decode("utf-8")
    n_crlf = t.count("\r\n")
    n_lf = t.count("\n")
    n_cr = t.count("\r")
    assert n_lf == n_crlf, "裸 LF：%d" % (n_lf - n_crlf)
    assert n_cr == n_crlf, "裸 CR：%d" % (n_cr - n_crlf)
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", ""), "正文里混入裸 CR"
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0, "出现 \\r\\r\\n（write_text 事故特征）"
    p.write_bytes(out.encode("utf-8"))
    # 写后自检
    chk = p.read_bytes().decode("utf-8")
    assert chk.count("\r\r\n") == 0
    assert chk.count("\n") == chk.count("\r\n"), "落盘后不是纯 CRLF"


def sub1(t, anchor, repl):
    n = t.count(anchor)
    assert n == 1, "锚点命中 %d 次（必须 1）：%r" % (n, anchor[:80])
    return t.replace(anchor, repl, 1)


# ── 1. 在 autotune_score 之前插入 layer_goal_readings 与常量 ────────────
A1 = "def autotune_score(ep: dict) -> dict:\n"

R1 = '''#: [层目标] 四层目标语义的**读数键名**（与用户战略指令逐字对应）。
#:   ★ 每条读数都是「**越大越接近该层目标**」，但**各自独立成轴** ——
#:     绝不合成一个总分（红线「未对齐合法」：不同层的目标本就不在同一尺度）。
_LG_KEYS = {
    "0": "excavate",      # 修行：层面挖掘的**边际新增趋零度**（挖不动了 ⇒ 趋近无穷收敛）
    "1": "settle",        # 研究：层面**答案确定率**（有限收敛）
    "both": "fuse",       # 对撞：由发散∩有限**融合生成**的新层面率
    "all": "crystallize",  # 元：记忆结晶 / 决策 / 行动 / 回看的**留痕完整度**
}
#: [层目标] 元层「回看」的最小留痕项数（结晶 + 决策 + 行动 + 回看 四件事）。
_LG_META_MIN = 4


def _lg_ratio(num, den):
    """安全比率：分母 <=0 或非数 ⇒ **None**（不是 0）。"""
    try:
        _n = float(num)
        _d = float(den)
    except (TypeError, ValueError):
        return None
    if _d <= 0:
        return None
    return max(0.0, min(1.0, _n / _d))


def _lg_diverge_state(v: dict):
    return str(((v or {}).get("divergence") or {}).get("state") or "").strip()


def layer_goal_readings(views: dict) -> dict:
    """[层目标] 把 `views` 压成**每层一条目标读数**（纯函数，可判据）。

    读数**按用户给的四层目标定义**，每条都回答「这一层离它的目标还差多少」：

      · `0` 修行 —— `excavate` = 层面挖掘的**边际新增趋零度**。
        分子 = `aspect_units` 数，分母 = 实际跑的圈数（`rounds_run`）。
        ★ 语义：修行层要在**最少圈数**里把层面挖尽。若圈数多而层面不再增长
          （比值趋 0）⇒ 已「挖到不能再挖」⇒ **趋近无穷收敛**。
          故本读数 = **1 − 归一化边际新增**：边际新增越低 ⇒ 读数越高。
        辅读：`divergence.state == "收敛"/"停滞"` ⇒ 属于「趋近收敛」。
      · `1` 研究 —— `settle` = 层面**答案确定率** = `decidable_product`
        已答数 / 层面总数（`covered_answer` 的 `answered/total` 同源）。
        辅读：`belief_status_counts` 里 resolved/settled 占比。
      · `both` 对撞 —— `fuse` = **融合生成率** = 对撞产出的**新层面数**
        （`duel_suspensions` + `belief_items` 中对撞来源的条目）/ 上游可用层面数。
        ★ 语义：融合「无穷发散 ∩ 有限确定」⇒ **创新出新的发散/有限层面**。
      · `all` 元 —— `crystallize` = **留痕完整度** = 四件事（结晶/决策/行动/回看）
        中真正留下产物的项数 / 4。产出面 = `meta_closure`（结晶+回看）、
        `engagements`（决策）、`suspensions`（行动/交代）。
      ★ 任一层缺产物 ⇒ 该层读数 = **None**（不印 0 冒充「读了是 0」）。
    """
    vs = views or {}
    out = {}
    for L in _AT_LAYERS:
        v = vs.get(L) or {}
        if not v:
            continue
        d = {}
        if L == "0":
            _units = len(v.get("aspect_units") or [])
            _rr = int(_at_num(v.get("rounds_run"), 0) or 0)
            _margin = _lg_ratio(_units, _rr) if _rr > 0 else None
            # 边际新增越低 ⇒ 越接近「挖尽」；故取 1 − min(margin,1)。
            d["excavate"] = (None if _margin is None
                             else round(1.0 - min(1.0, _margin), 4))
            d["n_aspects"] = _units
            d["rounds_run"] = _rr
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st in ("收敛", "停滞"))
        elif L == "1":
            _co = v.get("covered_answer") or {}
            d["settle"] = _lg_ratio(_co.get("answered"), _co.get("total"))
            _bs = v.get("belief_status_counts") or {}
            _tot_b = sum(int(x or 0) for x in _bs.values()) if _bs else 0
            _res_b = (int(_bs.get("resolved", 0) or 0)
                      + int(_bs.get("settled", 0) or 0))
            d["belief_resolved_rate"] = _lg_ratio(_res_b, _tot_b)
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st == "收敛")
        elif L == "both":
            _new = (len(v.get("duel_suspensions") or [])
                    + len(v.get("belief_items") or []))
            _up = int(_at_num(v.get("upstream_layers"), 0) or 0)
            if _up <= 0:
                _bm = v.get("both_quota") or {}
                _up = int(_at_num(_bm.get("upstream"), 0) or 0)
            d["fuse"] = _lg_ratio(_new, _up) if _up > 0 else None
            d["n_new"] = _new
            d["n_upstream"] = _up
        elif L == "all":
            _clo = v.get("meta_closure") or {}
            _hits = 0
            if _clo:
                _hits += 1                                   # 结晶（闭环清算）
                if _clo.get("total") is not None:
                    _hits += 1                               # 回看（张力总数盘点）
            if (v.get("engagements") or []):
                _hits += 1                                   # 决策
            if (v.get("suspensions") or []):
                _hits += 1                                   # 行动/交代
            d["crystallize"] = round(_hits / float(_LG_META_MIN), 4)
            d["n_hits"] = _hits
            d["meta_clean"] = bool(_clo.get("clean")) if _clo else None
        out[L] = d
    return out


def layer_goal_summary(views: dict) -> dict:
    """[层目标] 只回**每层的主读数**（`_LG_KEYS` 那条）—— 给 AutoTune 用。

    返回 `{层: {"key":..., "value": float|None, "converging": bool|None}}`。
    ★ 缺读数的层**不进**结果（`None` 与「跑了但读数算不出」都表现为缺键）——
      两者对「选层集」的建议是**一样的**：没有证据就不要拿来淘汰（红线）。
    """
    rd = layer_goal_readings(views)
    out = {}
    for L, d in rd.items():
        k = _LG_KEYS.get(L)
        if not k or k not in d:
            continue
        v = d.get(k)
        out[L] = {"key": k, "value": (None if v is None else float(v)),
                  "converging": d.get("converging")}
    return out


'''

t = load_crlf(SRC)
t = sub1(t, A1, R1 + A1)

# ── 2. episode_from_result 增写 goal_readings 出口 ─────────────────────
A2 = '        "cost": {"tokens": int(r.get("llm_tokens") or 0),\n                 "calls": int(r.get("llm_calls") or 0)},\n    }\n'
R2 = ('''        "cost": {"tokens": int(r.get("llm_tokens") or 0),
                 "calls": int(r.get("llm_calls") or 0)},
        # ★ [层目标] 四层目标读数必须**出口**，否则 AutoTune 读不到
        #   （「字段有值 ≠ 有出口」—— 本项目已栽过）。
        "goal_readings": layer_goal_summary(vs),
    }
''')
t = sub1(t, A2, R2)

# ── 3. autotune_score 增按层目标的 quality 口径 ────────────────────────
A3 = '''    duty = ep.get("duty") or {}
    dv = [_at_num(x) for x in duty.values()]
    dv = [x for x in dv if x is not None]
    q_duty = _at_med(dv)
    tri = _at_num(ep.get("tri_rate"))
    cut = [str(x) for x in (ep.get("cut_layers") or [])]
    if q_duty is not None:
        quality, basis = q_duty, "duty_med"
    elif tri is not None:
        quality, basis = tri, "tri_rate"
    else:
        quality, basis = None, "unknown"
'''
R3 = '''    duty = ep.get("duty") or {}
    dv = [_at_num(x) for x in duty.values()]
    dv = [x for x in dv if x is not None]
    q_duty = _at_med(dv)
    tri = _at_num(ep.get("tri_rate"))
    cut = [str(x) for x in (ep.get("cut_layers") or [])]
    # ★ [层目标] 优先用「按层目标定义的读数」—— 它比 duty 更贴用户给的目标语义
    #   （duty 只答「层替问题干了多少活」，goal 答「离该层目标还有多远」）。
    _gr = ep.get("goal_readings") or {}
    gv = []
    for _L, _d in (_gr or {}).items():
        if isinstance(_d, dict):
            _x = _at_num(_d.get("value"))
            if _x is not None:
                gv.append(_x)
    q_goal = _at_med(gv)
    if q_goal is not None:
        quality, basis = q_goal, "goal_med"
    elif q_duty is not None:
        quality, basis = q_duty, "duty_med"
    elif tri is not None:
        quality, basis = tri, "tri_rate"
    else:
        quality, basis = None, "unknown"
'''
t = sub1(t, A3, R3)

# ── 4. autotune_score 返回里带上 goal 明细 ─────────────────────────────
A4 = '''        "rounds_cap": dict(ep.get("rounds_cap") or {}),
        "run_id": str(ep.get("run_id") or ""),
    }
'''
R4 = '''        "rounds_cap": dict(ep.get("rounds_cap") or {}),
        "run_id": str(ep.get("run_id") or ""),
        # ★ 层目标明细随行（供 `autotune_progress` 做「中期动态调整」判据）。
        "goal_readings": {str(k): dict(v) for k, v in (_gr or {}).items()
                          if isinstance(v, dict)},
    }
'''
t = sub1(t, A4, R4)

# ── 5. 新函数 autotune_progress（中期动态调整） ────────────────────────
A5 = "def autotune_load_episodes(base=None, dirpath=None) -> list:\n"
R5 = '''def autotune_progress(episodes: list, min_n: int = 2) -> dict:
    """[中期动态调整] 判「同一 (模式,层集) 的目标读数**随轮次是否在改善**」。

    依据 **CSD / 早期预警（Scheffer et al. 2009）** 与 **Successive Halving**：
      同一配置连跑多次，若目标读数**单调不降且末端仍升** ⇒ 继续（预算给得起）；
      若**已平/在退** ⇒ 收敛（停手，把预算抽回）；若**在退** ⇒ 建议回滚到最佳轮。

    返回 `{key: {trend, first, last, best_ep_idx, advice}}`，`advice ∈
    {"继续","收敛","回滚"}`。★ 每个 key 至少要 `min_n` 个**带目标读数**的
    episode 才判；不足 ⇒ 不出现该 key（**绝不瞎猜**）。
    ★ 与 `autotune_rank` **各自独立**：那个答「选哪套配置」，这个答「这套还要不要跑」。
    """
    need = max(2, int(min_n))
    groups = {}
    for ep in (episodes or []):
        s = autotune_score(ep)
        key = (s["mode"], tuple(s["route"]))
        _g = s.get("goal_readings") or {}
        # 主读数：取该跑里**数值最多**的那条目标读数之和的中位（同分母）。
        _vals = []
        for _L, _d in _g.items():
            k = _LG_KEYS.get(_L)
            if not k:
                continue
            _x = _at_num((_d or {}).get(k)) if k in (_d or {}) else None
            if _x is None and "value" in (_d or {}):
                _x = _at_num(_d.get("value"))
            if _x is not None:
                _vals.append(_x)
        if not _vals:
            continue
        groups.setdefault(key, []).append((float(s["t"]), _at_med(_vals), s))
    out = {}
    for key, arr in groups.items():
        if len(arr) < need:
            continue
        arr = sorted(arr, key=lambda x: x[0])           # 按时间排
        ys = [a[1] for a in arr]
        _f, _l = ys[0], ys[-1]
        _best = max(range(len(ys)), key=lambda i: ys[i])
        if _l > _f + 1e-9:
            advice, trend = "继续", "上升"
        elif _l < _f - 1e-9:
            advice, trend = "回滚", "下降"
        else:
            advice, trend = "收敛", "平稳"
        out["%s|%s" % (key[0], ",".join(key[1]))] = {
            "trend": trend, "first": round(_f, 4), "last": round(_l, 4),
            "best_ep_idx": int(_best), "n": len(arr), "advice": advice}
    return out


'''
t = sub1(t, A5, R5 + A5)

save_crlf(SRC, t)
print("OK: patch v1.23.33 layer_goals 应用完成")
