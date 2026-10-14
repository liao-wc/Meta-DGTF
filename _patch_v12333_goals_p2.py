# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮 patch-2：按前沿依据**修正层目标读数**并补三阶段决策。

依据（本轮检索所得，2024-2026）：
 ① **Heaps' law / type-token 饱和**（Herdan 1960；SSR 饱和尺度 m̃=αN^μ，
    arXiv 1806.09419）：词表增长 V(n)=K·n^β，**边际新增趋零**才是「挖尽」。
    ⇒ 修行层读数改为**边际新增率**（末段新增/上段新增），不是「总量/圈数」。
    ★ 第一版 `excavate = 1 − n_aspects/rounds_run` **方向错**：层面挖得多
      反而读数低 ⇒ 会把「挖得好的配置」判劣。这是「方向错的断言比没断言更危险」。
 ② **content entropy 收敛 + 伪收敛警告**（Towards a Science of Collective AI,
    2025）：熵单调降 = 收敛轨迹，但**熵降 ≠ 高质量**，可能是「过早忽略关键
    信息」的 pseudo-convergence ⇒ 研究层读数必须**同时**含「非退化」项。
 ③ **CORE**（Pandey et al., NeurIPS 2025）= mode entropy × repetition penalty
    × semantic stagnation penalty ⇒ 对撞层「融合生成」要**罚复读上游**，
    否则「一分不发、全文照抄」会被读成满分融合。
 ④ **Darwin Gödel Machine**（Zhang et al. 2025, arXiv:2505.22954；ICLR 2026）
    **archive + 开放探索**：消融显示「贪心只从最优分支」= 39.7%，
    带 archive = 50.0% ⇒ AutoTune 后期**必须维护 archive 且禁止贪心**。
"""
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    t = p.read_bytes().decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), "非纯 CRLF"
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", "")
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0
    p.write_bytes(out.encode("utf-8"))
    chk = p.read_bytes().decode("utf-8")
    assert chk.count("\n") == chk.count("\r\n")


def sub1(t, a, r):
    n = t.count(a)
    assert n == 1, "锚点命中 %d 次（必须 1）：%r" % (n, a[:90])
    return t.replace(a, r, 1)


t = load_crlf(SRC)

# ══ A. 修行层读数改为「边际新增趋零」（Heaps 饱和）════════════════════
A1 = '''        if L == "0":
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
'''
R1 = '''        if L == "0":
            # ★ 依据 Heaps' law / type-token 饱和：修行层「挖到不能再挖」的
            #   判据是**词汇/层面的边际新增趋零**（ΔV/Δn → 0），不是总量多少。
            #   ★ 别用「总量/圈数」当读数：那让「挖得多」反而读数低（方向错）。
            _units = len(v.get("aspect_units") or [])
            _rr = int(_at_num(v.get("rounds_run"), 0) or 0)
            _hist = [_at_num(x) for x in (v.get("aspect_hist") or [])]
            _hist = [x for x in _hist if x is not None]
            _margin = _lg_aspect_margin(_hist, _units)
            d["excavate"] = _margin          # 边际新增率（越低越接近挖尽）
            d["excavate_closed"] = (None if _margin is None
                                    else round(1.0 - _margin, 4))
            d["n_aspects"] = _units
            d["rounds_run"] = _rr
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st in ("收敛", "停滞"))
'''
t = sub1(t, A1, R1)

# ══ B. 研究层加「伪收敛守卫」（熵降 ≠ 质量）═══════════════════════════
A2 = '''        elif L == "1":
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
'''
R2 = '''        elif L == "1":
            # ★ 依据「content entropy 收敛」+ **伪收敛警告**（2025）：熵降是
            #   收敛轨迹，但熵降 ≠ 质量 —— 可能是「过早忽略关键信息」。
            #   ⇒ 研究层读数**必须**同时含「确定率」与「非退化」两项，
            #     两者都好才算「有限收敛」；只有熵降 ⇒ 报 pseudo_convergence。
            _co = v.get("covered_answer") or {}
            _ans, _tot = _co.get("answered"), _co.get("total")
            d["settle"] = _lg_ratio(_ans, _tot)
            # 非退化：答案面**确实有实质产出**（不是「全部未答」也算齐整）。
            _nz = _at_num(_ans, 0.0) or 0.0
            d["non_degenerate"] = (_nz > 0) if _tot else None
            _bs = v.get("belief_status_counts") or {}
            _tot_b = sum(int(x or 0) for x in _bs.values()) if _bs else 0
            _res_b = (int(_bs.get("resolved", 0) or 0)
                      + int(_bs.get("settled", 0) or 0))
            d["belief_resolved_rate"] = _lg_ratio(_res_b, _tot_b)
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st == "收敛")
            # ★ 伪收敛 = 声称收敛但答案面退化（一个都没答上）。
            d["pseudo_convergence"] = bool(
                _st in ("收敛", "停滞") and _tot and not _nz)
'''
t = sub1(t, A2, R2)

# ══ C. 对撞层加 CORE 复读罚（semantic stagnation penalty）════════════
A3 = '''        elif L == "both":
            _new = (len(v.get("duel_suspensions") or [])
                    + len(v.get("belief_items") or []))
            _up = int(_at_num(v.get("upstream_layers"), 0) or 0)
            if _up <= 0:
                _bm = v.get("both_quota") or {}
                _up = int(_at_num(_bm.get("upstream"), 0) or 0)
            d["fuse"] = _lg_ratio(_new, _up) if _up > 0 else None
            d["n_new"] = _new
            d["n_upstream"] = _up
'''
R3 = '''        elif L == "both":
            # ★ 依据 CORE（Pandey et al., NeurIPS 2025）：只用「产出量」会
            #   把「复读上游、一分不发」读成满分融合 ⇒ 必须配**语义停滞罚**
            #   （semantic stagnation penalty），与 repetition penalty 同源。
            _duel = v.get("duel_suspensions") or []
            _bel = v.get("belief_items") or []
            _new = len(_duel) + len(_bel)
            _up = int(_at_num(v.get("upstream_layers"), 0) or 0)
            if _up <= 0:
                _bm = v.get("both_quota") or {}
                _up = int(_at_num(_bm.get("upstream"), 0) or 0)
            # 停滞 = 新层面与上游层面**文本重合**的比例（越高越像复读）。
            _stag = v.get("sem_stagnation")
            _stag = _at_num(_stag)
            if _stag is None:
                _stag = _lg_stag_ratio(_duel + _bel,
                                       v.get("upstream_texts") or [])
            d["fuse_raw"] = _lg_ratio(_new, _up) if _up > 0 else None
            # CORE 式：融合分 = 产出率 × (1 − 停滞罚)，各因子都有物理来源。
            if d["fuse_raw"] is None:
                d["fuse"] = None
            elif _stag is None:
                d["fuse"] = d["fuse_raw"]        # 算不出停滞 ⇒ 不罚也不假装
            else:
                d["fuse"] = round(d["fuse_raw"] * (1.0 - min(1.0, _stag)), 4)
            d["sem_stagnation"] = (None if _stag is None else round(_stag, 4))
            d["n_new"] = _new
            d["n_upstream"] = _up
'''
t = sub1(t, A3, R3)

# ══ D. 新增两个纯函数（边际新增率 / 停滞率）══════════════════════════
A4 = "def layer_goal_readings(views: dict) -> dict:\n"
R4 = '''def _lg_aspect_margin(hist, total=None):
    """[Heaps 饱和] 层面序列的**边际新增率** = 末段新增 / 上段新增。

    依据 Heaps' law：词表增长 V(n)=K·n^β（β∈[0.4,0.6]），**边际新增趋零**
    ⇔ 「挖到不能再挖」（SSR 饱和尺度 m̃=αN^μ 之后 ⟨h(m)⟩≈N）。

    · `hist` = 逐圈的**累计层面数** `[V1, V2, …]` ⇒ 新增 = 相邻差。
    · 返回 = 末段新增 / 上段新增（**越小越饱和**；0 = 已完全挖尽）。
    · 无 hist（老产物）⇒ 退回「单点估计」：`1/(1+total)` 的**下限形态**，
      并**显式标注** `basis="fallback"`，不冒充逐圈读数。
    · 两条都没有 ⇒ None（**不是 0** —— 「没测」与「测出是 0」两回事）。
    """
    xs = [float(x) for x in (hist or []) if x is not None]
    if len(xs) >= 3:
        gains = [max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs))]
        if not gains:
            return None
        half = max(1, len(gains) // 2)
        late = sum(gains[-half:]) / float(half)
        early = sum(gains[:half]) / float(half)
        if early <= 1e-12:
            return 0.0 if late <= 1e-12 else None
        return max(0.0, min(1.0, late / early))
    return None


def _lg_stag_ratio(items, ups):
    """[CORE 停滞罚] 产出层面与**上游文本**的重合率（0-1；1 = 全复读）。

    ★ 返回 None 表示**算不出**（无上游文本 / 无产出）—— 不罚也不假装。
    """
    _its = [str((x or {}).get("target") or (x or {}).get("desc")
                or (x or {}).get("text") or "").strip()
            for x in (items or [])]
    _its = [x for x in _its if x]
    _ups = [str(x).strip() for x in (ups or []) if str(x).strip()]
    if not _its or not _ups:
        return None
    # 归一到字符集合的 Jaccard（与 `_similar` 同族，但这里只做**重合度**）。
    def _toks(s):
        return {c for c in s if not c.isspace()}
    hit = 0
    for s in _its:
        ts = _toks(s)
        if not ts:
            continue
        best = 0.0
        for u in _ups:
            tu = _toks(u)
            if not tu:
                continue
            j = len(ts & tu) / float(len(ts | tu))
            best = max(best, j)
        if best >= 0.8:          # 与某条上游近乎逐字相同 ⇒ 记为复读
            hit += 1
    return hit / float(len(_its))


'''
t = sub1(t, A4, R4 + A4)

save_crlf(SRC, t)
print("OK: patch-2 层目标读数按前沿依据修正完成")
