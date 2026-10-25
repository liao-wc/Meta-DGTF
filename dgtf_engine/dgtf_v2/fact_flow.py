# -*- coding: utf-8 -*-
"""事实题闭环（V2 参考实现，**纯确定性**）。

把「事实题怎么跑」拆成四步，全部可离线复现：

1. **分类**：题面是否事实型（与引擎 _has_decision_context 同源）→
   QuestionProfile（kind / orientation / landing / 信号）；
2. **排程**：**四层固定不砍层**（route 恒为 0/1/both/all）+
   每层圈数建议（事实短题只砍圈、不砍层；下限/上限按层钳制）；
3. **取证**：注入 search 检索 → evidence 层归一化/去重/预算/白名单/冲突/缺口 →
   FactCard（answered / no_record / conflict / unknown）；
4. **对账**：FactCard 结论 vs 推理结论 → consistency 层
   （match / partial / mismatch / not_comp）。

边界（红线）：

- 不调 LLM、不联网：search 由调用方注入（fake search 也走同一接口）；
- 不砍层：任何分类/预算/短题都不许把 route 变短——事实题只砍圈；
- 不编答案：FactCard.answer 只取已有证据原文；无证据就是 no_record/unknown。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .consistency import ConsistencyReport, compare_retrieval_vs_reasoning
from .evidence import (EvidenceBudget, EvidenceReport, answer_from_evidence,
                       collect_evidence, detect_conflicts, detect_gaps,
                       extract_numeric_claims, question_terms)

# ── 四层（唯一来源；与引擎 _ENTRIES / dgtf_v2.contracts 的四层同名）──────────
LAYER_ENTRIES: tuple[str, ...] = ("0", "1", "both", "all")

#: 事实题允许的 FactCard 状态（封闭集合）。
CARD_STATUSES: tuple[str, ...] = ("answered", "no_record", "conflict",
                                  "unknown")

#: 题面决策语汇 —— 与 元DGTF-V1.25.0.py 的 _DECISION_CUES **同源**。
#: 词表只增不减：加词只会让更多题走决策型，不会静默把决策题踢成事实题。
_DECISION_CUES: tuple[str, ...] = (
    "该不该", "要不要", "是否", "怎么办", "怎么选", "怎么建", "怎么改",
    "如何", "方案", "建议", "选哪个", "取舍", "优先", "值不值", "利弊",
    "可行", "落地", "规划", "部署", "决策", "权衡", "风险", "预算",
    "排期", "步骤", "流程", "设计",
)

#: 事实语汇：只用于**理由与信号**，不覆盖决策语汇（引擎口径：决策优先）。
_FACT_CUES: tuple[str, ...] = (
    "是什么", "是多少", "哪一年", "哪年", "什么时候", "哪里", "在哪",
    "是谁", "多少人", "多少", "多大", "多久", "哪些", "列举", "排名",
    "数据", "统计", "定义", "含义", "区别", "原因", "为什么", "几个",
    "几类", "占比", "总量", "金额", "日期", "名称",
)

_META_CUES: tuple[str, ...] = ("本身", "自身", "递归", "元", "整体", "到底")

# ── 圈数建议（镜像引擎 _auto_pick_rounds 的钳制口径）────────────────────────
MIN_LAYER_ROUNDS = 4
MAX_LAYER_ROUNDS = 6
MAX_ROUNDS_BY_LAYER = {"1": 5}
MIN_ROUNDS_BY_LAYER = {"all": 5}
BASE_ROUNDS = {"0": 4, "1": 4, "both": 5, "all": 6}

#: 一次事实题默认最多发几条检索 query（多了浪费预算，少了覆盖不足）。
MAX_QUERIES = 3


# ============================================================ 分类
@dataclass
class QuestionProfile:
    """题面的确定性分类结果（不调模型）。"""

    question: str = ""
    kind: str = "unknown"          # fact / decision / unknown
    is_fact: bool = False
    orientation: str = "boundary"  # boundary / decision（镜像引擎取向路由）
    landing: str = "boundary"      # boundary / decision（落地模板）
    signals: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"question": self.question, "kind": self.kind,
                "is_fact": bool(self.is_fact),
                "orientation": self.orientation,
                "landing": self.landing,
                "signals": dict(self.signals),
                "reasons": list(self.reasons)}


def classify_question(question: str) -> QuestionProfile:
    """事实题分类（纯规则）。

    判据与引擎 _has_decision_context 同源：**命中任一决策语汇 ⇒ 决策型**；
    否则 ⇒ 事实型（宁走边界模板，也不替提问者编执行方案）。
    空题面 ⇒ unknown（不分类、不发检索，但四层排程仍固定全给）。
    """
    q = str(question or "").strip()
    if not q:
        return QuestionProfile(
            question="", kind="unknown", is_fact=False,
            orientation="boundary", landing="boundary",
            signals={"len": 0, "blank": True, "short": False,
                     "decision_hits": [], "fact_hits": [],
                     "meta_hits": [], "has_question_mark": False},
            reasons=["题面为空：归 unknown（不分类、不发检索）；排程仍固定四层"])
    decision_hits = sorted({c for c in _DECISION_CUES if c in q})
    fact_hits = sorted({c for c in _FACT_CUES if c in q})
    meta_hits = sorted({c for c in _META_CUES if c in q})
    is_fact = not decision_hits
    kind = "fact" if is_fact else "decision"
    orientation = "boundary" if is_fact else "decision"
    reasons: list[str] = []
    if decision_hits:
        reasons.append("命中决策语汇：%s ⇒ 决策型（与引擎 "
                       "_has_decision_context 同源）" % "、".join(decision_hits[:5]))
    else:
        reasons.append("未命中决策语汇 ⇒ 事实型；事实语汇：%s"
                       % ("、".join(fact_hits[:5]) if fact_hits else "无（按边界模板）"))
    if meta_hits:
        reasons.append("含元层/过程提示：%s" % "、".join(meta_hits[:5]))
    return QuestionProfile(
        question=q, kind=kind, is_fact=is_fact,
        orientation=orientation, landing=orientation,
        signals={"len": len(q), "blank": False, "short": 0 < len(q) <= 40,
                 "decision_hits": decision_hits, "fact_hits": fact_hits,
                 "meta_hits": meta_hits,
                 "has_question_mark": ("？" in q or "?" in q)},
        reasons=reasons)


# ============================================================ 排程（四层固定 + 圈数建议）
def fixed_route() -> list:
    """四层固定不砍层：任何题都返回全部四层（顺序固定）。"""
    return list(LAYER_ENTRIES)


def _coerce_profile(profile) -> QuestionProfile:
    if isinstance(profile, QuestionProfile):
        return profile
    return classify_question(profile if isinstance(profile, str) else "")


def _layer_ceil(layer: str, hard: int, floor: int) -> int:
    return max(floor, min(MAX_ROUNDS_BY_LAYER.get(layer, MAX_LAYER_ROUNDS),
                          hard))


def _layer_floor(layer: str, hard: int, floor: int) -> int:
    return max(floor, min(MIN_ROUNDS_BY_LAYER.get(layer, floor), hard))


def suggest_rounds(profile, hard_max: int = 12,
                   rounds_max: int = 2) -> dict:
    """每层圈数建议（只是**种子上限**，不保证跑满）。

    口径镜像引擎 _auto_pick_rounds（含 v1.25.0 的 fact_flow 收紧）：

    - 事实短题（≤40 字）只收紧圈数 ⇒ 每层从下限起（不砍层）；
    - 再按层钳制：下限 max(MIN_LAYER_ROUNDS, MIN_ROUNDS_BY_LAYER)，
      上限 min(MAX_ROUNDS_BY_LAYER, hard_max)——研究层 5、元层下限 5；
    - **事实短题最后再钳一层** min(v, rounds_max)（引擎配置键
      auto.fact_flow.rounds_max，默认 2）：四层仍全跑，每层最多 N 圈。
    """
    prof = _coerce_profile(profile)
    hard = max(1, int(hard_max))
    floor = min(MIN_LAYER_ROUNDS, hard)
    tightened = bool(prof.is_fact and prof.signals.get("short"))
    cap = int(rounds_max) if str(rounds_max).lstrip("-").isdigit() else 2
    out: dict = {}
    for layer in LAYER_ENTRIES:
        base = floor if tightened else int(BASE_ROUNDS.get(layer, floor))
        lo = _layer_floor(layer, hard, floor)
        hi = _layer_ceil(layer, hard, floor)
        value = int(min(max(base, lo), hi))
        if tightened and cap > 0:
            value = min(value, max(1, cap))
        out[layer] = value
    return {layer: out[layer] for layer in LAYER_ENTRIES}


@dataclass
class FactRunPlan:
    """事实题排程建议（route 固定四层；rounds 为每层种子上限）。"""

    question: str = ""
    route: list = field(default_factory=lambda: list(LAYER_ENTRIES))
    rounds: dict = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return {"question": self.question, "route": list(self.route),
                "rounds": dict(self.rounds), "note": self.note}


def plan_fact_run(question: str, hard_max: int = 12,
                  profile: QuestionProfile | None = None,
                  rounds_max: int = 2) -> FactRunPlan:
    """产出排程：四层固定 + 每层圈数建议（不砍层，只调圈）。"""
    prof = _coerce_profile(profile if profile is not None else question)
    rounds = suggest_rounds(prof, hard_max=hard_max, rounds_max=rounds_max)
    return FactRunPlan(
        question=str(question or "").strip(),
        route=fixed_route(),
        rounds=rounds,
        note=("四层固定不砍层（route 恒为 0/1/both/all）；"
              "rounds 是每层种子上限建议（事实短题另受 auto.fact_flow."
              "rounds_max=%d 收紧），层内到点自然停。" % int(rounds_max)))


# ============================================================ 检索 query
_QUERY_PREFIX = ("请问", "请帮我", "帮我", "想知道", "想了解")
_QUERY_SUFFIX = ("？", "?", "吗", "呢")


def extract_queries(question: str, extra=None,
                    limit: int = MAX_QUERIES) -> list:
    """从题面派生检索 query（确定性、去重保序）。

    只做**字符级**清理（去「请问」前缀 / 去问号语气词），不改写语义；
    extra 里的 query 按给定顺序追加。空题面 ⇒ 空列表（不发检索）。
    """
    q = str(question or "").strip()
    out: list[str] = []

    def _add(value) -> None:
        s = str(value or "").strip()
        if s and s not in out:
            out.append(s)

    _add(q)
    cleaned = q
    for w in _QUERY_SUFFIX:
        if cleaned.endswith(w):
            cleaned = cleaned[:-len(w)].strip()
    for w in _QUERY_PREFIX:
        if cleaned.startswith(w):
            cleaned = cleaned[len(w):].strip()
    if cleaned and cleaned != q:
        _add(cleaned)
    # ★ [Round 35] 法定/现行类：补「现行 民法典」查询，避免检索池只有历史旧规；
    #   贸易口径类：补海关总署/外汇管理局查询，避免海关 vs 外管局口径混判。
    _subj = cleaned or q
    if any(k in _subj for k in ("法定", "现行", "民法典", "刑法", "条例",
                                "法律规定")):
        _add("%s 现行 民法典" % _subj)
    elif any(k in _subj for k in ("顺差", "逆差", "进出口", "贸易", "海关")):
        _add("%s 海关总署" % _subj)
        _add("%s 外汇管理局" % _subj)
    # ★ 4 位事实 token（如 1017）：加一条官方站内精确检索，避免通用 query
    #   只召回到其它版本的日期。
    import re as _re2
    _toks = _re2.findall(r"\d{4}", cleaned or q)
    if _toks and "deepseek" in (cleaned or q).lower():
        _add("%s site:api-docs.deepseek.com" % _toks[0])
    # 技术标准/官方文档类事实题：补一条官方站内查询，避免只召回博客/CTF。
    _low = (cleaned or q).lower()
    # ★ [Round 16] 数字被中文字符紧邻时 \b 不成立（「404状态码」中文是 word char）
    #   ⇒ 用数字前后非数字断言，保证「HTTP 404状态码」也能进入官方站内检索。
    _sc = _re2.search(r"(?<!\d)([1-5]\d\d)(?!\d)", _low)
    if _sc and ("http" in _low or "状态码" in _low):
        _add("site:developer.mozilla.org HTTP %s" % _sc.group(1))
        _add("site:rfc-editor.org RFC 9110 %s" % _sc.group(1))
    if "deepseek" in _low and ("base url" in _low or "base_url" in _low):
        _add("site:api-docs.deepseek.com base URL")
    for x in (extra or []):
        _add(x)
    return out[:max(1, int(limit))] if out else []


# ============================================================ FactCard
@dataclass
class FactCard:
    """一张事实卡：四态 + 证据 id + 缺口 + 冲突（全确定性）。"""

    question: str = ""
    status: str = "unknown"
    answer: str = ""
    queries: list = field(default_factory=list)
    evidence_ids: list = field(default_factory=list)
    official_evidence_ids: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    #: 已被「官方源优先」消解的原始冲突（保留可审计，不计入阻断项）
    resolved_conflicts: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    reason: str = ""

    @property
    def ok(self) -> bool:
        """answered 还不够：未覆盖题面/冲突/同题 token 不在证据里都不算闭环。"""
        if self.status != "answered" or self.conflicts:
            return False
        for g in (self.gaps or []):
            gs = str(g or "")
            if (gs.startswith("uncovered:") or gs in
                    ("conflict_unresolved", "insufficient_evidence",
                     "question_token_not_in_evidence", "no_query",
                     "search_error", "no_record")):
                return False
        return True

    def to_dict(self) -> dict:
        _display = _compact_numeric_answer(self.question, self.answer)
        return {"question": self.question, "status": self.status,
                "answer": self.answer,
                "answer_display": _display or self.answer,
                "queries": list(self.queries),
                "evidence_ids": list(self.evidence_ids),
                "official_evidence_ids": list(self.official_evidence_ids),
                "conflicts": [dict(c) if isinstance(c, dict) else c
                              for c in self.conflicts],
                "resolved_conflicts": [dict(c) if isinstance(c, dict) else c
                                       for c in self.resolved_conflicts],
                "gaps": list(self.gaps), "reason": self.reason,
                "ok": bool(self.ok)}


def _dedup(seq) -> list:
    out: list = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def _clean_card_answer(ans: str) -> str:
    """事实卡答案清洗：去行首时间戳/标题符号，压到 ≤200 字。"""
    s = str(ans or "").strip()
    s = re.sub(r"^(\[\d{4}-\d{2}-\d{2}\]|\d{4}-\d{2}-\d{2})[\s:：]*", "", s)
    s = re.sub(r"^#+\s*", "", s)
    s = re.sub(r"\s+#+\s*", " ", s)
    return s.strip()[:200]


#: 数值型问句的信号词（答案应收窄为 值+单位）
_NUM_Q_HINTS: tuple[str, ...] = (
    "多少", "几", "多大", "多长", "多高", "多重", "多远", "多深",
    "多宽", "多厚", "多快", "多慢", "百分比", "百分之", "比例",
    "千米", "公里", "米", "厘米", "毫米", "千米", "kg", "公斤", "吨",
    "%", "℃", "度", "年", "个月", "天", "小时", "分钟", "秒",
)


def _compact_numeric_answer(question: str, answer: str) -> str:
    """数值型题：从答案文本里抽「值+单位」，返回紧凑短答；抽不到则原样返回。"""
    q = str(question or "")
    ans = str(answer or "").strip()
    if not ans:
        return ans
    # ★ [Round 31] 日期问句（哪一年/何时）：展示收窄为「YYYY年」，优先「现行/通过/
    #   颁布」所在分句的年份（宪法题：现行宪法为1982年宪法 ⇒ 1982年）。
    if any(k in q for k in ("哪一年", "哪年", "何时", "什么时候", "年份",
                            "哪一天")):
        import re as _re2
        _parts = _re2.split(r"[。；;\n]", ans)
        _years = _re2.findall(r"(?:19|20)\d{2}年", ans)
        if _years:
            # 优先「现行…1982年」锚定（宪法题），其次「颁布/通过…年份」，最后取末个年份
            _m = _re2.search(r"现行[^。；;\n]{0,16}?((?:19|20)\d{2})年", ans)
            if _m:
                return _m.group(1) + "年"
            _m2 = _re2.search(r"(?:颁布|通过)[^。；;\n]{0,24}?((?:19|20)\d{2})年",
                              ans)
            if _m2:
                return _m2.group(1) + "年"
            return _years[-1]
    if not any(h in q for h in _NUM_Q_HINTS):
        return ans
    try:
        from .evidence import extract_numeric_claims
    except Exception:  # noqa: BLE001
        return ans
    # 量词噪声：9个/3条/2项 这类计数单位不是题面目标量（问的是长度/面积/…）
    _WEAK_UNITS = ("个", "条", "处", "项", "次", "种", "位", "名",
                   "份", "家", "所", "岁")
    _STRONG_UNITS = ("千米", "公里", "米", "厘米", "毫米", "%", "℃",
                     "吨", "公斤", "kg", "元", "万", "周岁", "岁",
                     "万人", "万辆", "亿美元")
    claims = []
    for c in extract_numeric_claims(ans):
        try:
            val = float(c.get("value"))
        except (TypeError, ValueError):
            continue
        unit = str(c.get("unit") or "").strip()
        raw = str(c.get("raw") or "").strip()
        if not unit:
            continue
        if any(unit == w for w in _WEAK_UNITS) and unit not in q:
            continue
        if not any(u in raw for u in _STRONG_UNITS) \
                and not any(u == unit or u in unit for u in _STRONG_UNITS):
            continue
        claims.append((val, unit, raw))
    if not claims:
        return ans
    # 单位命中题面的优先；其次数值在答案中出现更早的优先（保持原文顺序）
    q_units = [u for u in ("千米", "公里", "米", "厘米", "毫米", "%", "℃",
                           "年", "吨", "公斤", "kg", "小时", "分钟", "秒")
               if u in q or u.lower() in q.lower()]
    # ★ [Round 20] 目标量纲线索：增速/增长→%；长度/海拔→长度单位；重量；面积
    if any(k in q for k in ("增速", "增长", "率", "百分", "CPI", "PPI")):
        q_units = ["%"] + q_units
    if any(k in q for k in ("长度", "多长", "全长", "海拔", "多高", "多宽", "多深")):
        q_units = ["千米", "公里", "米"] + q_units
    if any(k in q for k in ("重量", "多重")):
        q_units = ["吨", "公斤", "kg"] + q_units
    if any(k in q for k in ("面积", "平方公里")):
        q_units = ["平方公里", "万平方"] + q_units

    def rank(c):
        val, unit, raw = c
        u_hit = 0 if any(u and (u in unit or unit in u) for u in q_units) else 1
        pos = ans.find(raw) if raw else 10 ** 6
        return (u_hit, pos if pos >= 0 else 10 ** 6, -abs(val))
    val, unit, raw = sorted(claims, key=rank)[0]
    if raw:
        return raw.strip()[:60]
    txt = ("%g" % val) + unit
    return txt[:60]


def _is_aux_date_conflict(c: dict) -> bool:
    """日期类辅助冲突（年份/月份/日期）——与题面目标量无关，可被官方源消解。"""
    if not isinstance(c, dict):
        return False
    # 只认「单位/锚点是日期类」或「数值全是年份」的冲突；
    # 不能因为 term 里出现「年」字就判辅助（如 "2023 年中国GDP增长" 含年字，
    # 但它是目标量冲突，必须保持 conflict —— 这是真实 GDP 反例给出的边界）。
    unit_anchor = (str(c.get("unit") or "") + " " + str(c.get("anchor") or ""))
    if any(k in unit_anchor for k in ("年", "月", "日", "date", "日期")):
        return True
    vals = []
    for v in (c.get("values") or []):
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            pass
    return len(vals) >= 2 and all(1000 <= v <= 2100 for v in vals)


def _official_precedence_answer(question: str, evs: list,
                                conflicts: list, official_ids: list):
    """官方源优先消解：返回 (answer, remaining_conflicts) 或 (None, conflicts)。

    只在「冲突不含官方源 && 官方源能给出题面相关答案」时消解；否则原样返回。
    """
    if not conflicts or not official_ids:
        return None, list(conflicts)
    off_set = {str(x) for x in official_ids if str(x)}
    off_evs = [e for e in evs if str(getattr(e, "evidence_id", "")) in off_set]
    if not off_evs:
        return None, list(conflicts)
    for c in conflicts:
        if not isinstance(c, dict):
            return None, list(conflicts)
        cids = {str(x) for x in (c.get("evidence_ids") or [])}
        if cids & off_set:          # 官方源自己参与冲突 ⇒ 不越权消解
            return None, list(conflicts)
        if not _is_aux_date_conflict(c):
            # 目标量冲突（如 GDP 增速 5.2 vs 6.8）不得被官方优先掩盖
            return None, list(conflicts)
    ans = _clean_card_answer(
        str(answer_from_evidence(off_evs, question, prefer_recent=True)
            or "").strip())
    if len(ans) < 2 or len(ans) > 200:
        return None, list(conflicts)
    return ans, []


def _numeric_claim_answer(question: str, evs: list) -> str:
    """数值题：从数值主张里选最贴合题面的原文句子（严格守卫，否则返回 ""）。"""
    q = str(question or "")
    q_units = []
    if any(k in q for k in ("增速", "增长", "率", "百分", "CPI", "PPI", "通胀")):
        q_units.append("%")
    if any(k in q for k in ("长度", "多长", "全长", "海拔", "高", "宽",
                            "深", "距离", "多远")):
        q_units.extend(["千米", "公里", "米"])
    if any(k in q for k in ("重量", "多重", "吨", "公斤")):
        q_units.extend(["吨", "公斤"])
    if any(k in q for k in ("面积", "平方公里")):
        q_units.extend(["平方公里", "万平方"])
    if any(k in q for k in ("元", "亿元", "万元", "美元", "金额", "总量")):
        q_units.extend(["亿元", "万元", "元", "美元"])
    # ★ [Round 33] 通用单位提及：题面出现「万人/万辆/亿…」等直接纳入单位类
    q_units.extend([u for u in ("万人", "万辆", "万", "亿", "吨", "公斤",
                                "千米", "公里", "米", "%", "℃", "岁",
                                "度", "小时", "分钟", "秒") if u in q])
    _asks_date = any(k in q for k in ("哪一年", "哪年", "何时", "什么时候",
                                      "年份", "哪一天"))
    # ★ [Round 33] 「分别」句序位：产量/生产→第1个数，销量/销售→第2个数
    _ord_pref = None
    if any(k in q for k in ("产量", "生产")):
        _ord_pref = 0
    elif any(k in q for k in ("销量", "销售")):
        _ord_pref = 1
    if _asks_date:
        q_units.append("年")
    if not _asks_date and not any(
            k in q for k in ("多少", "几", "多长", "多高", "多重", "多远",
                             "多深", "多宽", "多大", "多快", "增速", "增长",
                             "率", "海拔", "速度", "面积", "重量", "温度")):
        return ""
    # 繁简归一（官方繁体页常见）
    _T2S = str.maketrans({"國": "国", "長": "长", "內": "内", "產": "产",
                          "總": "总", "億": "亿", "萬": "万", "個": "个",
                          "數": "数", "據": "据", "區": "区", "門": "门",
                          "報": "报", "經": "经", "濟": "济", "發": "发",
                          "佈": "布", "網": "网", "點": "点"})

    def _norm(s):
        return str(s or "").translate(_T2S)
    _raw_toks = re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fa5]{2,}", _norm(q))
    tokens = []
    for _x in _raw_toks:
        if re.fullmatch(r"[A-Za-z]{2,}", _x):
            tokens.append(_x)
            continue
        for _y in re.split(r"[年的了是与和在为多少]", _x):
            _y = re.sub(r"(最新数据|数据|数值|是多少|多少|是什么|最新)$", "", _y)
            if len(_y) >= 2 and not _y.isdigit():
                tokens.append(_y)
    _ALIAS = {"GDP": ("国内生产总值", "GDP"), "CPI": ("居民消费价格", "CPI"),
              "增速": ("增长", "增速"), "增长": ("增长", "增速"),
              "长度": ("全长", "长度"), "海拔": ("海拔", "高程")}
    from .evidence import _text_date_score as _tds
    _recency = any(k in q for k in ("最新", "当前", "现在", "目前", "截至",
                                     "如今", "现行", "latest", "current"))
    _FINAL_MARK = ("最终核实", "最终数据", "修订后", "更新后", "final")
    _PRELIM_MARK = ("初步核算", "初步数据", "初步统计", "预计", "预估",
                    "初值", "prelim")
    _year_q = re.findall(r"(?:19|20)\d{2}", q)
    _annual_q = bool(re.search(r"(?:19|20)\d{2}年", q)) and any(
        k in q for k in ("涨幅", "增速", "增长", "总量", "全年", "年度"))
    _current_q = any(k in q for k in ("法定", "现行", "目前", "现在", "我国",
                                      "最新", "有效"))
    _CUR = ("现行", "民法典", "目前", "现在", "有效", "最新")
    _OLD = ("民国", "废止", "旧", "1931", "1930", "之前", "旧法")
    _PEN = ("上游", "中游", "下游", "河段", "分产业", "第一产业", "第二产业",
            "核心CPI", "核心", "扣除食品", "扣除", "分项",
            "第三产业", "人均", "居民", "占比", "比重", "研发", "投资",
            "出口", "进口", "消费", "其中", "合计中")
    _OV = ("全长", "总长", "总长度", "修正为", "现为", "调整为", "增长",
           "增速", "总量为", "同比")
    best = None
    for e in evs:
        snip = str(getattr(e, "snippet", "") or "")
        if not snip:
            continue
        nsnip = _norm(snip)
        concept = 0
        for _tk in tokens:
            if _tk in nsnip:
                concept += 1
            elif any(a in nsnip for a in _ALIAS.get(_tk, ())):
                concept += 1
        # ★ [Round 33] 概念兜底用「主张上下文」的题面 2-gram 命中数：
        #   同一 snippet 里「汽车产销3128.2」与「新能源汽车产销1288.8」的上下文不同，
        #   用 snip 会打平；用 context 才能区分目标（新能源产量）。
        _q_grams = [q[_i:_i + 2] for _i in range(len(q) - 1)
                    if "\u4e00" <= q[_i] <= "\u9fa5"
                    and "\u4e00" <= q[_i + 1] <= "\u9fa5"]
        for c in extract_numeric_claims(snip):
            unit = str(c.get("unit") or "")
            raw = str(c.get("raw") or "").strip()
            if not raw:
                continue
            # 无单位主张（如日期里的 12/8）不能作数值答案；空 unit 会让
            # `"" in "米"` 恒真 ⇒ 假 u_hit（recency 回归由此暴露）。
            if not unit or unit in ("年", "月", "日"):
                continue
            u_hit = 1 if any(u in unit or unit in u for u in q_units) else 0
            ctx = _norm(c.get("context") or "")
            pen = 1 if any(k in ctx for k in _PEN) else 0
            ov = 1 if any(k in ctx for k in _OV) else 0
            _rec = _tds(snip) if _recency else 0
            _nctx = _norm(ctx)
            _gh = sum(1 for _g in _q_grams if _g in _nctx)
            _concept = max(concept, min(_gh, 5))
            _curhit = 1 if (_current_q and any(
                k in snip for k in _CUR)) else 0
            _oldpen = 1 if (_current_q and any(
                k in snip for k in _OLD)) else 0
            _ord_hit = 0
            if _ord_pref is not None and "分别" in snip:
                if str(_ord_pref) in ctx:
                    _ord_hit = 1
            _ord_miss = 1 if (_ord_pref is not None and "分别" in snip
                              and not _ord_hit) else 0
            _final = 1 if any(k in snip for k in _FINAL_MARK) else 0
            _prelim = 1 if any(k in snip for k in _PRELIM_MARK) else 0
            _year_hit = 1 if any(y in snip for y in _year_q) else 0
            _year_miss = 1 if (_year_q and not _year_hit
                               and re.search(r"(?:19|20)\d{2}", snip)) else 0
            _annual = 1 if (_annual_q and "全年" in snip) else 0
            _month = 1 if (_annual_q and any(
                k in snip for k in ("月份", "月度", "环比"))) else 0
            # 修订期感知：最终核实 > 初步核算（对统计类事实题的「最新/最终」问法）
            score = (u_hit, _concept, _year_hit, -_year_miss, _ord_hit,
                     -_ord_miss, _curhit, -_oldpen, _final, _rec, _annual,
                     -_month, ov, -_prelim, -pen, -len(raw))
            if best is None or score > best[0]:
                best = (score, snip, raw)
    if best is None:
        return ""
    score, snip, raw = best
    # 严格门槛：单位类命中 + 题面概念命中 + 非分段语义，否则回退旧逻辑
    if not (score[0] and score[1] and not score[14]):
        return ""
    for part in re.split(r"[。；;\n]", snip):
        if raw and raw in part:
            return part.strip()[:240]
    return raw[:120]


def build_fact_card(question: str, report: EvidenceReport,
                    min_official: int = 1,
                    min_independent: int = 2) -> FactCard:
    """把证据报告判成 FactCard 四态（按序判定，互斥）：

    1. unknown   —— 没 query / 检索失败 / 或证据不足（无官方源且独立域名 <2）；
    2. no_record —— 真查了（searches≥1）但一条可用证据都没有；
    3. conflict  —— 查到了，但证据间有未消解的数值冲突；
    4. answered  —— 官方源 ≥ min_official，或独立域名 ≥ min_independent，
                    且无冲突。
    """
    evs = list(getattr(report, "items", None) or [])
    queries = list(getattr(report, "queries", None) or [])
    errors = list(getattr(report, "errors", None) or [])
    # 引擎侧会**直接构造** EvidenceReport（不等价于 collect_evidence）：
    # 没给 gaps/conflicts 时在这里就地补算，保证卡片的判据不依赖调用方
    # 是否跑过 detect_gaps / detect_conflicts。
    conflicts = list(getattr(report, "conflicts", None) or [])
    if evs and not conflicts:
        conflicts = detect_conflicts(evs)
    gaps = list(getattr(report, "gaps", None) or [])
    if evs and not gaps:
        gaps = detect_gaps(question, evs, conflicts=conflicts)
    evidence_ids = [str(getattr(e, "evidence_id", "")) for e in evs]
    official_ids = [str(getattr(e, "evidence_id", "")) for e in evs
                    if bool(getattr(e, "official", False))]
    base = dict(question=str(question or "").strip(), queries=queries,
                evidence_ids=evidence_ids,
                official_evidence_ids=official_ids)

    if not queries:
        return FactCard(status="unknown", gaps=_dedup(gaps + ["no_query"]),
                        reason="没有可执行的检索 query（题面为空）", **base)
    searches = int(getattr(report, "searches", 0) or 0)
    if errors and not evs:
        return FactCard(status="unknown", gaps=_dedup(gaps + ["search_error"]),
                        reason="检索失败：%s" % "；".join(errors[:2]), **base)
    if not evs:
        return FactCard(status="no_record",
                        gaps=_dedup(gaps + ["no_record"]),
                        reason="检索已执行 %d 次，但没有取到任何可用证据"
                        % searches, **base)
    if conflicts:
        # ★ [Round 33] 官方权威：官方证据单独能给出稳定数值答案时，以官方为准
        #   例外：若冲突发生在**两个及以上官方证据之间**（官方源互冲），不越权消解。
        _off_set = {str(x) for x in official_ids if str(x)}
        _off_conflict_many = any(
            len({str(i) for i in (c.get("evidence_ids") or [])} & _off_set) >= 2
            for c in conflicts if isinstance(c, dict))
        # 还需「期间错配」证据：冲突各值的来源年份不同（2023 vs 2024），
        # 才属于可被官方最新值消解的口径差；同年互冲仍是真冲突。
        _ev_year = {}
        for _e in evs:
            _eid = str(getattr(_e, "evidence_id", ""))
            _ys = re.findall(r"(?:19|20)\d{2}", str(
                getattr(_e, "snippet", "") or ""))
            _ev_year[_eid] = set(_ys)
        _period_mismatch = bool(conflicts) and all(
            len({_y for _i in (c.get("evidence_ids") or [])
                 for _y in _ev_year.get(str(_i), set())}) >= 2
            for c in conflicts if isinstance(c, dict))
        if official_ids and not _off_conflict_many and _period_mismatch:
            _off_evs = [e for e in evs if str(getattr(e, "evidence_id", ""))
                        in {str(x) for x in official_ids}]
            _off_ans = _clean_card_answer(
                _numeric_claim_answer(question, _off_evs) or "")
            if _off_ans and any(k in str(question or "")
                                for k in ("多少", "几", "多长", "多高", "多重",
                                          "多远", "多深", "多宽", "多大", "多快",
                                          "产量", "销量", "总量", "增速", "增长",
                                          "率", "面积", "重量", "温度", "价格")):
                _resolved = [dict(c) if isinstance(c, dict) else c
                             for c in conflicts]
                _gaps = [g for g in gaps if str(g) != "conflict_unresolved"]
                return FactCard(
                    status="answered", answer=_off_ans,
                    resolved_conflicts=_resolved,
                    gaps=_dedup(_gaps + ["conflict_resolved_official_authority"]),
                    reason=("证据间有 %d 处口径冲突，官方证据可稳定给出目标数值，"
                            "按官方权威消解" % len(conflicts)), **base)
        _ans, _left = _official_precedence_answer(question, evs, conflicts,
                                                  official_ids)
        if _ans and not _left:
            # 官方源优先：辅助冲突被消解，答案取官方源原文（可审计）
            _resolved = [dict(c) if isinstance(c, dict) else c
                         for c in conflicts]
            _gaps = [g for g in gaps if str(g) != "conflict_unresolved"]
            return FactCard(status="answered", answer=_ans,
                            resolved_conflicts=_resolved,
                            gaps=_dedup(_gaps + [
                                "conflict_resolved_official:official_precedence"]),
                            reason=("证据间有 %d 处冲突，但均不含官方源；"
                                    "按官方源优先消解并取官方原文作答"
                                    % len(conflicts)), **base)
        return FactCard(status="conflict", conflicts=conflicts,
                        gaps=_dedup(gaps + ["conflict_unresolved"]),
                        reason="证据之间有 %d 处未消解的数值冲突"
                        % len(conflicts), **base)
    official_n = len(official_ids)
    domains = sorted({str(getattr(e, "domain", "") or "") for e in evs} - {""})
    independent = len(domains)
    # ★ [Round 19] 数值题：答案优先取自「含值+单位」的证据，避免答案落到
    #   只有总述、没有目标数值的长网页正文（GDP 真实反例）。
    # ★ [Round 20] 再加「目标量纲」优先：增速/增长→%，长度/海拔→长度单位，…
    _cand_evs = evs
    if any(k in str(question or "") for k in _NUM_Q_HINTS):
        _vu = re.compile(r"\d+(?:\.\d+)?\s*(?:多|余|约|近)?\s*(?:千米|公里|"
                         r"米|厘米|毫米|%|℃|吨|公斤|kg|元|万|亿|岁|度)")
        _n = [e for e in evs
              if _vu.search(str(getattr(e, "snippet", "") or ""))]
        if _n:
            _q = str(question or "")
            _pct = any(k in _q for k in ("增速", "增长", "率", "百分", "CPI",
                                         "PPI", "通胀"))
            _len = any(k in _q for k in ("长度", "多长", "全长", "海拔", "高",
                                         "宽", "深", "距离", "多远"))
            _mass = any(k in _q for k in ("重量", "多重", "吨", "公斤"))
            _area = any(k in _q for k in ("面积", "平方公里"))
            _unit_re = None
            if _pct:
                _unit_re = re.compile(r"\d+(?:\.\d+)?\s*%")
            elif _len:
                _unit_re = re.compile(r"\d+(?:\.\d+)?\s*(?:多|余|约|近)?\s*"
                                      r"(?:千米|公里|米|厘米|毫米)")
            elif _mass:
                _unit_re = re.compile(r"\d+(?:\.\d+)?\s*(?:吨|公斤|kg)")
            elif _area:
                _unit_re = re.compile(r"\d+(?:\.\d+)?\s*(?:平方公里|万平方)")
            if _unit_re is not None:
                _m = [e for e in _n
                      if _unit_re.search(str(getattr(e, "snippet", "") or ""))]
                if _m:
                    _n = _m
            _cand_evs = _n
    answer = _clean_card_answer(
        _numeric_claim_answer(question, _cand_evs)
        or answer_from_evidence(_cand_evs, question, prefer_recent=True))
    # ★ [Round 34] 现行性问句（法定/现行/我国/最新）若答案只有历史旧规 → 拒答
    _curq = any(k in str(question or "") for k in (
        "法定", "现行", "目前", "现在", "最新", "有效", "我国"))
    _old_mark = ("民国", "废止", "旧法", "旧规", "1931", "1930", "1911")
    if _curq and answer and any(k in str(answer) for k in _old_mark):
        return FactCard(status="unknown",
                        gaps=_dedup(gaps + ["historical_answer_rejected"]),
                        reason=("现行性问句的答案只含历史旧规（%s），拒绝作为当前事实"
                                % "/".join([k for k in _old_mark
                                            if k in str(answer)][:2])), **base)
    # ★ [Round 32] 时间锚定问句：题面含明确年份、答案却只给「另一年份」时拒答
    #   （宁缺毋假；避免把 2023 的核心 CPI 当成 2024 的 CPI 涨幅 verified 出街）
    _yq = re.findall(r"(?:19|20)\d{2}", str(question or ""))
    if _yq and answer and not any(y in answer for y in _yq):
        if re.search(r"(?:19|20)\d{2}", answer):
            return FactCard(status="unknown",
                            gaps=_dedup(gaps + ["year_mismatch"]),
                            reason=("答案年份与题面不一致（题面 %s），拒绝输出"
                                    % "/".join(_yq[:2])), **base)
    if answer and (official_n >= int(min_official)
                   or independent >= int(min_independent)):
        return FactCard(status="answered", answer=answer,
                        gaps=_dedup(gaps),
                        reason=("证据充分：官方源 %d 条 / 独立域名 %d 个"
                                % (official_n, independent)), **base)
    return FactCard(status="unknown",
                    gaps=_dedup(gaps + ["insufficient_evidence"]),
                    reason=("有 %d 条证据，但官方源 %d 条、独立域名 %d 个，"
                            "不足以作为事实依据"
                            % (len(evs), official_n, independent)), **base)


# ============================================================ 总流程
@dataclass
class FactFlowResult:
    """一次事实题闭环的全部产物（可直接 to_dict 落 packed）。"""

    question: str = ""
    profile: QuestionProfile = field(default_factory=QuestionProfile)
    plan: FactRunPlan = field(default_factory=FactRunPlan)
    card: FactCard = field(default_factory=FactCard)
    evidence: EvidenceReport = field(default_factory=EvidenceReport)
    consistency: ConsistencyReport = field(default_factory=ConsistencyReport)
    gaps: list = field(default_factory=list)
    ok: bool = False

    def to_dict(self) -> dict:
        return {"question": self.question,
                "profile": self.profile.to_dict(),
                "plan": self.plan.to_dict(),
                "fact_card": self.card.to_dict(),
                "evidence": self.evidence.to_dict(),
                "consistency": self.consistency.to_dict(),
                "gaps": list(self.gaps), "ok": bool(self.ok)}


def run_fact_flow(question: str, search=None, *, reasoning=None,
                  extra_queries=None, budget: EvidenceBudget | None = None,
                  hard_max: int = 12, rounds_max: int = 2,
                  min_official: int = 1,
                  min_independent: int = 2) -> FactFlowResult:
    """事实题闭环（分类 → 固定四层排程 → 注入检索 → FactCard → 一致性）。

    search   : Callable[[str], list] | None。唯一外部入口（可注入 fake）；
               None ⇒ 不检索，FactCard=unknown（search_unavailable）。
    reasoning: 推理侧结论（str / dict / 带 answer 的对象）。None ⇒
               一致性判 not_comp（「未提供推理结论，无法比较」）。
    """
    q = str(question or "").strip()
    profile = classify_question(q)
    plan = plan_fact_run(q, hard_max=hard_max, profile=profile,
                         rounds_max=rounds_max)
    queries = extract_queries(q, extra=extra_queries)
    report = collect_evidence(queries, search, question=q, budget=budget)
    card = build_fact_card(q, report, min_official=min_official,
                           min_independent=min_independent)
    if reasoning is None:
        consistency = ConsistencyReport(
            verdict="not_comp", retrieval_answer=card.answer,
            reasons=["未提供推理结论，无法比较"])
    else:
        consistency = compare_retrieval_vs_reasoning(
            card, reasoning, evidence=getattr(report, "items", None))
    gaps = list(card.gaps)
    if consistency.verdict != "match":
        gaps.append("consistency:" + consistency.verdict)
    return FactFlowResult(question=q, profile=profile, plan=plan, card=card,
                          evidence=report, consistency=consistency,
                          gaps=_dedup(gaps),
                          ok=bool(card.ok and consistency.ok))


__all__ = [
    "LAYER_ENTRIES", "CARD_STATUSES", "MIN_LAYER_ROUNDS", "MAX_LAYER_ROUNDS",
    "MAX_ROUNDS_BY_LAYER", "MIN_ROUNDS_BY_LAYER", "BASE_ROUNDS",
    "MAX_QUERIES", "QuestionProfile", "FactRunPlan", "FactCard",
    "FactFlowResult", "classify_question", "fixed_route", "suggest_rounds",
    "plan_fact_run", "extract_queries", "build_fact_card", "run_fact_flow",
]
