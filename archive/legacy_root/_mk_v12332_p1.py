#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 补丁：吸收「学科 + 前沿 + 开源」清单的前 6 项。

1) 三态一致率改用 **ordinal Krippendorff α / weighted κ + rare-class 一致**
   （依据：评分者一致性研究 —— 原始一致率不计机会一致；原始 79% 对应 κ 0.34~0.44。
    三态天然定序 ⇒ 用 ordinal 距离函数。）
2) **读数尺度登记 + 按尺度限制运算**（Stevens 测量论）—— 把「读数不是分数」
   变成可执行红线：定序读数不许出现「均值/倍数/百分比提升」类措辞。
3) **halt cascade 优先级 + 报告即实际**（SHP）：停因按优先级排序，产物报
   「主因（最高优先级）」与「全部触发」，并保证主因 ∈ 全部触发。
4) **成本两分**（SHP）：operational vs evaluation（自测量）两类调用分开计。
5) **CSD 早期预警读数**（复杂系统/生态学）：每层逐圈序列的方差与 lag-1 自相关
   —— 只作**读数**，不改任何停止行为（口径：概率性评估，不是预测）。
6) 版本号。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.32.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


# ── 纯函数块 ────────────────────────────────────────────────
NEW_FUNCS = '''# ============================================================
# [v1.23.32] 学科吸收：评分者一致性 / 测量尺度 / 停因级联 / 早期预警
#
# ★ 为什么这些是**判据口径**而不是「新机制」：
#   本项目早就写着「读数不是分数」「同一把尺子」「不许只升不降」，
#   但从没有把「尺子」本身形式化。以下三段把那些口号变成可执行的东西。
# ============================================================

#: 三态的**定序**顺序（可判定性由高到低）。★ 三态天然有序，
#:   所以一致性必须用 ordinal 距离，不能用 nominal（同一份数据两者能差很多）。
_TRI_ORDER = {"decidable": 2, "partial": 1, "undecidable": 0}


def _tri_rank(lab) -> Optional[int]:
    return _TRI_ORDER.get(str(lab or "").strip().lower())


def krippendorff_alpha_ordinal(units) -> Optional[dict]:
    """**ordinal Krippendorff α**（缺失值容忍；任意评审人数）。

    `units`：`[[label, label, ...], ...]`（每个 unit 一个评分者列表，可缺）。
    返回 `{alpha, n_units, n_pairs, do_observed, do_expected}`；
    样本不足（有效 unit < 2 或总配对 < 2）⇒ 返回 None（**不印 0 冒充读数**）。

    ★ 依据：Krippendorff 的口径 —— **α ≥ 0.800 才算可靠；0.667~0.800 只支持
      暂定结论；0.667 是下限不是目标**。原始一致率忽略机会一致，
      在标签偏斜时会严重高估（实证：原始 79% ↔ κ 0.34~0.44）。
    """
    _units = []
    for u in (units or []):
        _r = [_tri_rank(x) for x in (u or [])]
        _r = [x for x in _r if x is not None]
        if len(_r) >= 2:
            _units.append(_r)
    if len(_units) < 2:
        return None
    _npairs = sum(len(u) * (len(u) - 1) // 2 for u in _units)
    if _npairs < 2:
        return None
    # 观察不一致度 Do（ordinal 距离：用排名差归一化到 [0,1]）
    _span = max(1, len(_TRI_ORDER) - 1)
    # 全局值分布（用于 De 的期望）
    _all = [x for u in _units for x in u]
    _n = len(_all)
    _n_total = sum(len(u) for u in _units)

    def _d(a, b):
        return float(abs(a - b)) / float(_span)

    _do_num = 0.0
    for u in _units:
        _m = len(u)
        for i in range(_m):
            for j in range(i + 1, _m):
                _do_num += _d(u[i], u[j])
    Do = _do_num / float(_npairs)
    # De：每个 unit 内配对，按**合并后的经验分布**算期望距离
    #   （与 Krippendorff 的 ordinal De 同构：E[d] over the pooled distribution）
    _exp_d = 0.0
    for _x in _all:
        for _y in _all:
            _exp_d += _d(_x, _y)
    _exp_d = _exp_d / float(max(1, _n * _n))
    De = _exp_d
    if De <= 1e-12:
        # 全体同值 ⇒ 无可测分歧；返回 1.0 但**注明**（不是「没测」）
        return {"alpha": 1.0, "n_units": len(_units), "n_pairs": _npairs,
                "do_observed": round(Do, 6), "do_expected": 0.0, "degenerate": True}
    return {"alpha": 1.0 - (Do / De), "n_units": len(_units),
            "n_pairs": _npairs, "do_observed": round(Do, 4),
            "do_expected": round(De, 4), "degenerate": False}


def weighted_kappa_pair(a_labels, b_labels, weights="ordinal") -> Optional[dict]:
    """两名评分者之间的 **weighted κ**（线性权重；容忍缺失对）。

    ★ 与 α 并列报：κ 好算好解释，α 更通用（人数/缺失/尺度）。
      两者都报，避免「换个统计量把结论做绿」的嫌疑。
    """
    _lv = sorted(_TRI_ORDER.values())
    _span = max(1, (max(_lv) - min(_lv)))
    _pairs = []
    for x, y in zip(a_labels or [], b_labels or []):
        _rx, _ry = _tri_rank(x), _tri_rank(y)
        if _rx is None or _ry is None:
            continue
        _pairs.append((_rx, _ry))
    if len(_pairs) < 2:
        return None
    _n = len(_pairs)

    def _w(x, y):
        # 线性权重：完全一致 = 1，差满格 = 0
        return 1.0 - abs(x - y) / float(_span)

    Po = sum(_w(x, y) for x, y in _pairs) / float(_n)
    _ax = [x for x, _ in _pairs]
    _ay = [y for _, y in _pairs]

    def _marg(v):
        _d = {}
        for z in v:
            _d[z] = _d.get(z, 0) + 1
        return {k: c / float(_n) for k, c in _d.items()}

    _mx, _my = _marg(_ax), _marg(_ay)
    Pe = 0.0
    for _x, _px in _mx.items():
        for _y, _py in _my.items():
            Pe += _px * _py * _w(_x, _y)
    if abs(1.0 - Pe) < 1e-12:
        return {"kappa": 1.0, "n": _n, "po": round(Po, 4), "pe": round(Pe, 4),
                "degenerate": True}
    return {"kappa": (Po - Pe) / (1.0 - Pe), "n": _n,
            "po": round(Po, 4), "pe": round(Pe, 4), "degenerate": False}


def rare_class_agreement(units, rare="undecidable") -> Optional[dict]:
    """**少数类一致**：只看被判为该类的 unit 里，评审是否一致。

    ★ 依据：标签偏斜时「大家都判多数类」的共识是**廉价**的；
      真正有信息的是少数类上的分歧（本项目关心的恰是「判不出」这个少数类）。
    """
    _rare = str(rare or "").strip().lower()
    _n_unit = _n_any = 0
    for u in (units or []):
        _r = [str(x or "").strip().lower() for x in (u or [])]
        _r = [x for x in _r if x in _TRI_ORDER]
        if len(_r) < 2:
            continue
        if _rare not in _r:
            continue
        _n_unit += 1
        if len(set(_r)) == 1:
            _n_any += 1
    if _n_unit == 0:
        return None
    return {"rare": _rare, "units": _n_unit, "unanimous": _n_any,
            "rate": _n_any / float(_n_unit)}


def alpha_verdict(alpha) -> str:
    """把 α 翻成**口径化**的判词（Krippendorff 阈值，不用「看起来低/高」）。"""
    if alpha is None:
        return "未测（样本不足）"
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        return "未测（样本不足）"
    if a >= 0.800:
        return "可靠（α≥0.800）"
    if a >= 0.667:
        return "仅支持暂定结论（0.667≤α<0.800）"
    return "不可靠（α<0.667，Krippendorff 下限）"


#: [成本两分] **自测量（判定类）** stage 名单 —— 这些调用不产出任务内容，
#:   产出的是「对内容的判定/评估」。未登记的一律计入「跑本身」（宁少算自测量）。
_LLM_EVAL_STAGES = frozenset({
    "assess_decidability", "assess_decidability_from_pool_view",
    "adjudicate_sub_tristate", "adjudicate_sub_tristate_multi",
    "anchor_crosscheck", "dual_judge", "re_evaluate_pool",
    "self_check", "input_sanity", "landing_decision",
})


# ── 读数尺度登记（Stevens 测量论）────────────────────────────
#: **尺度类型**：nominal（定类）/ ordinal（定序）/ interval（定距）/ ratio（定比）。
#: ★ 允许的运算不同 —— 定序**不许**求均值、不许说「两倍」、不许报「百分比提升」。
#:   这不是文风要求，是测量论：定序尺度的差值无定义。
_READING_SCALE = {
    "tri_state_agreement": "ordinal",   # 三态一致率（分母是定序标签）
    "tri_alpha": "interval",            # α ∈ (-1,1]，可比较大小
    "tri_kappa": "interval",
    "duty.S": "interval",               # 调和平均，零点非自然零点
    "duty.C": "ratio",
    "duty.R": "ratio",
    "semantic_entropy": "ratio",        # 熵有真零
    "touch_rate": "ratio",
    "aspect_carry_rate": "ratio",
    "tier": "ordinal",                  # 锚点分级
    "anchor_tier_floor": "ordinal",
    "csd_warning": "ordinal",           # 有前兆/无前兆/样本不足
    "playbook_evidence_n": "ratio",
}

#: **定序读数禁止出现的措辞**（出现即违测量论：在无差值的尺度上做算术）。
_SCALE_FORBIDDEN = {
    "ordinal": ("均值", "平均", "两倍", "翻倍", "百分比提升", "提升了",
                "加权平均", "标准差"),
}


def reading_scale(name: str) -> str:
    """查某读数的尺度类型（未登记 ⇒ 返回 "unknown"）。

    ★ 未登记不是错误，但**不许**默默当 interval 用 —— 那正是「读数当分数」。
    """
    return _READING_SCALE.get(str(name), "unknown")


def scale_word_violations(text: str, scale: str) -> list:
    """定序读数的措辞检查：返回命中的违禁词（空列表 = 合规）。"""
    _bad = _SCALE_FORBIDDEN.get(str(scale), ())
    _t = str(text or "")
    return [w for w in _bad if w in _t]


# ── 停因级联（halt cascade，吸收 SHP）──────────────────────
#: 停因的**优先级**（数字越小越优先）。依据 SHP 的 halt cascade：
#: ① 判定/收敛达成 ② 熵收敛（复述）③ 无信息增益（停滞/空转）④ 硬上限。
#: ★ 纪律：**报告的主因必须就是真正停下来的那个**（一个级联、无漂移）。
_STOP_CASCADE = (
    (0, ("职责增益收敛", "结构饱和度", "悬置决定稳定", "自然安住")),
    (1, ("复述", "自省连续")),
    (2, ("无新", "无推进", "连续空转", "停滞", "材料耗尽", "耗尽")),
    (3, ("体力耗尽", "预算用尽", "min_rounds")),
)


def stop_priority(reason: str) -> int:
    """把一条停因文案映射到优先级（未匹配 ⇒ 落到最低档 3，不静默丢弃）。"""
    _r = str(reason or "")
    for _p, _keys in _STOP_CASCADE:
        if any(k in _r for k in _keys):
            return int(_p)
    return 3


def stop_cascade(reasons) -> dict:
    """把一组停因整理成 `{primary, ordered, all}`（**主因 ∈ 全部触发**）。

    ★ 不变量：`primary` 必须出现在 `all` 里 —— 报告的原因不能是「没触发的那个」。
    """
    _rs = [str(x) for x in (reasons or []) if str(x).strip()]
    if not _rs:
        return {"primary": "", "ordered": [], "all": []}
    _ordered = sorted(_rs, key=lambda r: (stop_priority(r), _rs.index(r)))
    return {"primary": _ordered[0], "ordered": _ordered, "all": _rs}


# ── CSD 早期预警（复杂系统 / 生态学）────────────────────────
#: 有效样本下限：少于这个数**不表态**（CSD 指标在短序列上噪声极大）。
_CSD_MIN_N = 4


def csd_indicators(series) -> Optional[dict]:
    """逐圈序列的 CSD 指标：**方差 + lag-1 自相关**（+ 是否上升趋势）。

    ★ 依据：系统接近临界转变时恢复速率下降 ⇒ 方差与 AC(1) 上升
      （已在生态/气候/生理/金融反复验证）。
    ★ 但口径必须写死：**这是「韧性的概率性评估」，不是「迫近崩溃的预测」**——
      六种 regime shift 机制里多数**没有** CSD 前兆，红噪声会造成虚警。
      ⇒ 本函数只出读数，**绝不参与任何停止判定**。
    """
    try:
        _s = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    if len(_s) < _CSD_MIN_N:
        return None
    _n = len(_s)
    _m = sum(_s) / _n
    _var = sum((x - _m) ** 2 for x in _s) / _n
    _num = sum((_s[i] - _m) * (_s[i - 1] - _m) for i in range(1, _n))
    _den = sum((x - _m) ** 2 for x in _s)
    _ac1 = (_num / _den) if _den > 1e-12 else 0.0
    _half = _n // 2
    _v1 = sum((x - sum(_s[:_half]) / _half) ** 2 for x in _s[:_half]) / _half \\
        if _half else 0.0
    _v2 = (sum((x - sum(_s[_half:]) / (_n - _half)) ** 2
               for x in _s[_half:]) / (_n - _half)) if (_n - _half) else 0.0
    _rising = _v2 > _v1
    return {"n": _n, "var": round(_var, 6), "ac1": round(_ac1, 4),
            "var_rising": bool(_rising),
            "hint": bool(_rising and _ac1 > 0.3)}


def csd_line(indic) -> str:
    """CSD 读数的一行文案（口径写在文案里，防止被读成预测）。"""
    if not indic:
        return "早期预警 —（样本不足，不表态）"
    return ("早期预警（CSD：方差 %s / AC1 %s，%s；**概率性评估，非预测**）"
            % ("↑" if indic.get("var_rising") else "→",
               indic.get("ac1"),
               "有前兆" if indic.get("hint") else "无前兆"))


'''


def main():
    s = _load()

    # 0) 版本号
    s = rep(s, "元 DGTF · v1.23.31", "元 DGTF · v1.23.32", "docstring 标题")
    s = rep(s, '__version__ = "1.23.31"', '__version__ = "1.23.32"', "__version__")

    # 1) 纯函数块（插在 EML 块之前）
    _anchor = "# ============================================================\n" \
              "# EML · 经验记忆回路（Experiential Memory Loop）"
    s = rep(s, _anchor, NEW_FUNCS + _anchor, "学科吸收纯函数块")

    # 2) 成本两分：LLM 计数器
    s = rep(s, "        self.total_calls = 0\n        self.total_tokens = 0",
            "        self.total_calls = 0\n        self.total_tokens = 0\n"
            "        # [成本两分] 跑本身 vs 自测量（判定类）分开计 —— 依据 SHP：\n"
            "        #   「operational tokens」与「evaluation tokens」不是一回事，\n"
            "        #   混在一起会让「自测量的开销」看起来像「任务本身的成本」。\n"
            "        self.ops_calls = 0\n        self.ops_tokens = 0\n"
            "        self.eval_calls = 0\n        self.eval_tokens = 0",
            "LLM 四项计数")

    s = rep(s, "                    self.total_calls += 1",
            "                    self.total_calls += 1\n"
            "                    # [成本两分] 按 stage 归类（未登记的 stage 一律算 ops，\n"
            "                    #   宁少算自测量、不多算）。\n"
            "                    _tk = 0\n"
            "                    try:\n"
            "                        _tk = int(getattr(usage, \"total_tokens\", 0) or 0)\n"
            "                    except Exception:\n"
            "                        _tk = 0\n"
            "                    if str(stage or \"\") in _LLM_EVAL_STAGES:\n"
            "                        self.eval_calls += 1\n"
            "                        self.eval_tokens += _tk\n"
            "                    else:\n"
            "                        self.ops_calls += 1\n"
            "                        self.ops_tokens += _tk",
            "LLM 归类计数")

    # 3) 三态多票：α / κ / 少数类一致
    s = rep(s, "        self._tri_consensus = (high, med, low)",
            "        # ★ [v1.23.32] 一致性口径修正：原始一致率**不计机会一致**，\n"
            "        #   在标签偏斜时严重误导（实证：原始 79% ↔ κ 0.34~0.44）。\n"
            "        #   三态天然定序 ⇒ 用 **ordinal α / 加权 κ**，并单报少数类一致。\n"
            "        try:\n"
            "            _units = []\n"
            "            _a_lab, _b_lab = [], []\n"
            "            for _it in items:\n"
            "                _vs = _it.get(\"votes\") or []\n"
            "                _ls = [v.get(\"label\") for v in _vs]\n"
            "                if len(_ls) >= 2:\n"
            "                    _units.append(_ls)\n"
            "                    _a_lab.append(_ls[0])\n"
            "                    _b_lab.append(_ls[1])\n"
            "            _al = krippendorff_alpha_ordinal(_units)\n"
            "            _kp = weighted_kappa_pair(_a_lab, _b_lab)\n"
            "            _rc = rare_class_agreement(_units, \"undecidable\")\n"
            "            self._tri_alpha = {\n"
            "                \"alpha\": (None if _al is None else _al.get(\"alpha\")),\n"
            "                \"kappa\": (None if _kp is None else _kp.get(\"kappa\")),\n"
            "                \"rare\": _rc,\n"
            "                \"n_units\": len(_units),\n"
            "                \"verdict\": alpha_verdict(\n"
            "                    None if _al is None else _al.get(\"alpha\")),\n"
            "            }\n"
            "        except Exception:\n"
            "            self._tri_alpha = {}\n"
            "        self._tri_consensus = (high, med, low)",
            "三态 α/κ 计算")

    # 4) pack：出口
    s = rep(s, '        _pack["tri_consensus"] = list(getattr(self, "_tri_consensus",',
            '        _pack["tri_alpha"] = dict(getattr(self, "_tri_alpha", None) or {})\n'
            '        _pack["llm_ops_calls"] = int(getattr(self.llm, "ops_calls", 0) or 0)\n'
            '        _pack["llm_ops_tokens"] = int(getattr(self.llm, "ops_tokens", 0) or 0)\n'
            '        _pack["llm_eval_calls"] = int(getattr(self.llm, "eval_calls", 0) or 0)\n'
            '        _pack["llm_eval_tokens"] = int(getattr(self.llm, "eval_tokens", 0) or 0)\n'
            '        _pack["tri_consensus"] = list(getattr(self, "_tri_consensus",',
            "pack 出口")

    # 5) 渲染：一致率行补 α/κ/少数类（定序读数，措辞受尺度约束）
    s = rep(s, '''    if _tt > 0:
        _pct = _ag / _tt
        out.append(f"- 📊 **三态判决一致率**：{_ag}/{_tt}"
                   f"（{_pct:.0%}）—— 低于 33% 时标签在此次运行里不稳定，"
                   f"分母不可当判据。\\n")''',
            '''    if _tt > 0:
        _pct = _ag / _tt
        # ★ [v1.23.32] 原始一致率**必须与机会校正指标并列报** ——
        #   单报原始值在偏斜标签上会严重高估（实证：原始 79% ↔ κ 0.34~0.44）。
        #   口径：三态定序 ⇒ 用 ordinal α / 加权 κ；阈值用 Krippendorff 的
        #   α≥0.800 可靠 / 0.667~0.800 暂定 / <0.667 不可靠。
        out.append(f"- 📊 **三态判决一致率（原始）**：{_ag}/{_tt}"
                   f"（{_pct:.0%}）—— ★ 原始值不计机会一致，须与下行的"
                   f"机会校正指标一起读。\\n")
        _ta = res.get("tri_alpha") or {}
        if _ta:
            _a_v = _ta.get("alpha")
            _k_v = _ta.get("kappa")
            _a_s = "—（样本不足）" if _a_v is None else "%.3f" % float(_a_v)
            _k_s = "—（样本不足）" if _k_v is None else "%.3f" % float(_k_v)
            out.append(f"- 📊 **机会校正一致（ordinal）**："
                       f"Krippendorff α = {_a_s} · 加权 κ = {_k_s}"
                       f"（n_unit={_ta.get('n_units', 0)}）"
                       f"｜判词：{_ta.get('verdict', '未测')}\\n")
            _rc = _ta.get("rare") or {}
            if _rc:
                out.append(f"- 📊 **少数类一致（{_rc.get('rare')}）**："
                           f"{_rc.get('unanimous')}/{_rc.get('units')}"
                           f"（{float(_rc.get('rate', 0)):.0%}）"
                           f"—— 偏斜标签下多数类共识廉价，少数类一致才有信息。\\n")''',
            "一致率渲染")

    # 6) 成本两分渲染
    s = rep(s, '''        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\\n\\n")''',
            '''        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\\n")
        # ★ [成本两分] 跑本身 vs 自测量（判定类）：混在一起会让「自测量的开销」
        #   看起来像「任务本身的成本」。未登记的 stage 一律计入前者（宁少算）。
        _oc = int(result.get("llm_ops_calls") or 0)
        _ec = int(result.get("llm_eval_calls") or 0)
        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "
                    f"{int(result.get('llm_ops_tokens') or 0)} tokens ｜ "
                    f"自测量（判定类）{_ec} 次 / "
                    f"{int(result.get('llm_eval_tokens') or 0)} tokens\\n\\n")
        else:
            f.write("\\n")''',
            "成本两分渲染")

    _save(s)
    print("OK v1.23.32 补丁第 1 段（纯函数 + 计数 + α + 渲染）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    for _m in ("def krippendorff_alpha_ordinal(", "def weighted_kappa_pair(",
               "def rare_class_agreement(", "def alpha_verdict(",
               "def reading_scale(", "def scale_word_violations(",
               "def stop_cascade(", "def csd_indicators("):
        assert _m in s2, _m
    assert s2.count("self.total_calls += 1") == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
