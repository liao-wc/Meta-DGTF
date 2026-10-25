# -*- coding: utf-8 -*-
"""V2.2.3 确定性自省核（fine_check）—— 纯函数、零 LLM、零 IO。

设计定位
--------
`self_check` 在 V2.2.2 及以前是「一次 LLM 调用换一段自省」，其中：

  · **决策字段**：`unsaid_count` / `unsaid_is_escape` / `ing_rephrased` /
    `suspicious_candidates`（回填主触发源）—— 会生成本圈质量旗、
    下一圈 carry 硬约束、idle 判定；
  · **仅叙述字段**：`flow_verdict` / `view_verdict` / `amp_ratio_verdict` /
    `honest_about_empty` / `notes` / `unsaid_where` —— 只进 md 与 packed。

本模块把这套自省先**确定性**地算一遍（可复核、可离线回放），让
`self_check_mode="auto"` 能：
  1. 叙述字段完全本地化（不再为一段话付一次 LLM 调用）；
  2. 决策字段里**确定可算的**（unsaid 计数/双源闸、ing 复述比、
     suspicious_amps 结构规则）直接落地；
  3. 只有触发器命中时才把**收窄后的上下文**交给 LLM 复核
     `suspicious_candidates`（回填判定），见 `triggers.llm_needed`。

红线
----
· 自省是**另一个视角**，不可并入 content。auto 模式仍原样产出
  `views.*.self_check` 独立段（本模块只提供其中字段）。
· 纯函数：不读文件、不调网络、不 import 引擎；输入输出都是可 JSON
  序列化的 dict，能直接吃 `outputs/*.packed.json` 的 `views[entry]`。

`audit(view_dict, cfg=None)` 返回字段契约见模块末尾 `_AUDIT_KEYS`。
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = "dgtf.fine_check.v1"

#: 引擎在同一口径下使用的「诚实未生」标记（与主引擎 `_UNSAID_MARK` 同值）。
UNSAID_MARK = "此处未生"

#: 判定「可疑候选」时不算展开证据的句长下限（与引擎复述检测同一口径）。
_SENT_MIN_LEN = 12

#: 叙述判定允许出现的理由（固定枚举，别处按此开关）。
TRIGGER_REASONS = (
    "new_candidates",   # 新增候选数达到 k
    "candidates_suspect",  # 确定性核点出可疑候选（回填判定歧义区）
    "rephrase",         # ing 复述比超阈
    "structural",       # 结构异常质量旗
    "silent",           # 静默圈（无候选/无 &/ing 未生）
    "amps_suspect",     # 可疑 & 达到阈值（只影响池注释，不触发 LLM）
)

#: 默认阈值。全部可被 cfg 覆盖；改动默认值 = 改行为，需同步门禁。
DEFAULT_CFG: Dict[str, Any] = {
    # 字符 n-gram 长度（任务指定字符 n-gram Jaccard；2 在中文上最稳）
    "ngram_n": 2,
    # 句级复述判定阈值：单句与上游某句的 n-gram Jaccard >= 此值算复述
    "rephrase_sent_threshold": 0.35,
    # 整段复述判定阈值：复述句占比 >= 此值 → ing_rephrased=True
    "rephrase_threshold": 0.5,
    # 候选 desc 与展开/ing 文本的相似度「低」线：低于它 = 找不到展开出处
    "sim_low": 0.12,
    # 候选 desc 与 view/manifest/upstream 的相似度「高」线：高于它 = 复述/回填
    "sim_high": 0.45,
    # 尾部窗口（按候选总数比例，至少 2 条）——「后补」通常排在末尾
    "susp_tail_frac": 0.25,
    "susp_min_tail": 2,
    # 尾部窗口起点（相对位置）——不到这个位置不算尾部
    "susp_tail_rel": 0.6,
    # 这类 kind 的候选更常被判「框架性后补」（LLM 标签实测：event 9% ~
    # question/thread 24-25%）；只在尾部窗口内叠加，不做全局规则。
    "susp_kinds": ("question", "thread", "other", "startpoint"),
    "susp_kind_rel": 0.6,
    # 可疑 &：与候选/其他 & 的 n-gram Jaccard 高于此值 → 像「复述凑数」
    "amp_restate_sim": 0.6,
    # & 候选比例上限（与引擎 _AMP_RATIO_MAX_BY_ENTRY 同量级，仅用于结构异常）
    "amp_ratio_max": 0.75,
    # 「此处未生」逃逸阈值（spiral.unsaid_escape_limit 的默认值）
    "unsaid_limit": 3,
    # 双源闸的强源计数倍数（与引擎 _unsaid_flag_gate 同式）
    "unsaid_strong_extra": 2,
    "unsaid_strong_frac": 1.5,
    # 触发器：新增候选数达到多少才值得复核
    "min_new_candidates": 6,
    # 可疑候选数落在 [min_llm, max_llm] 之间 = 决策歧义区 → 值得一次 LLM 复核
    "susp_llm_min": 2,
    "susp_llm_max": 8,
    # 回填旗门槛（与引擎 _BACKFILL_SC_MIN / _sc_need 同式）
    "backfill_min": 5,
    "backfill_need": 8,
    # 安全阀：候选/句子数上限，避免大产物把回放拖死
    "max_candidates": 60,
    "max_sentences": 240,
    # trace 上限（Lead 独立复核用）
    "trace_limit": 60,
}


# ============================================================
# 基础：归一化 / n-gram / 句子切分
# ============================================================
_PUNCT_RE = re.compile(
    r"[\s，。！？、；：“”‘’（）【】《》〈〉\-—－…·,.!?;:\"'()\[\]{}<>/\\|]+")
_SENT_SPLIT_RE = re.compile(r"[。！？；\n]+")


def normalize_text(text: Any) -> str:
    """去掉空白与标点，只留下可比的字（对齐时两侧同一把尺子）。"""
    return _PUNCT_RE.sub("", str(text or ""))


def ngrams(text: Any, n: int = 2) -> frozenset:
    """字符 n-gram 集合（去标点后）。长度不足返回空集。"""
    s = normalize_text(text)
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 2
    n = max(1, n)
    if len(s) < n:
        return frozenset()
    return frozenset(s[i:i + n] for i in range(len(s) - n + 1))


def jaccard(a: Any, b: Any, n: int = 2) -> float:
    """字符 n-gram 对称 Jaccard：|A∩B| / |A∪B|。"""
    A, B = (a if isinstance(a, frozenset) else ngrams(a, n)), \
        (b if isinstance(b, frozenset) else ngrams(b, n))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    if not inter:
        return 0.0
    return inter / len(A | B)


def sentences(text: Any, min_len: int = _SENT_MIN_LEN,
              drop_unsaid: bool = True) -> List[str]:
    """按中英文句读切句，去掉过短句与「此处未生」（诚实姿态不算复述源）。"""
    out = []
    for raw in _SENT_SPLIT_RE.split(str(text or "")):
        s = raw.strip()
        if len(s) < int(min_len or 0):
            continue
        if drop_unsaid and UNSAID_MARK in s:
            continue
        out.append(s)
    return out


def _grams_of_sentences(sents: Sequence[str], n: int) -> List[frozenset]:
    """把句子批量转成 n-gram 集合（一次编译，避免 O(对) 重复归一化）。"""
    return [ngrams(s, n) for s in sents]


def _max_sim(grams: frozenset, corpus_grams: Sequence[frozenset]) -> float:
    """单个 n-gram 集合对语料内所有句子的最大 Jaccard。"""
    if not grams or not corpus_grams:
        return 0.0
    best = 0.0
    for other in corpus_grams:
        if not other:
            continue
        inter = len(grams & other)
        if not inter:
            continue
        v = inter / len(grams | other)
        if v > best:
            best = v
            if best >= 0.999:
                break
    return best


# ============================================================
# 确定性证据：unsaid / 复述 / 可疑候选 / 可疑 & / 诚实未生
# ============================================================
def count_unsaid(view_dict: Dict[str, Any],
                 include_candidates: bool = False) -> Tuple[int, str]:
    """数「此处未生」出现的处数与分布（与引擎 `_count_unsaid` 同口径）。

    口径：ing 对撞 / view / 线头 / & / 不可判定通道五处文本里逐字计数。
    `include_candidates=True` 时**额外**数候选 desc 里的标记 —— 引擎
    `_count_unsaid` 不数候选，但模型自报时常常数的是候选里的标记（真跑
    标签实测：视图五个桶为 0 而 LLM 报 3，差额全在候选 desc）。这个宽口径
    只用于「防漏」的保守读数，默认不改变引擎口径。
    """
    v = view_dict or {}
    buckets = [
        ("ing", str(v.get("collision") or "")),
        ("view", str(v.get("manifest") or "")),
        ("线头", "\n".join(str(t.get("desc", ""))
                          for t in (v.get("threads") or [])
                          if isinstance(t, dict))),
        ("&", "\n".join(str(a.get("desc", ""))
                       for a in (v.get("amps") or [])
                       if isinstance(a, dict))),
        ("不可判定通道", str(
            (v.get("undecidable_product") or {}).get(
                "why_undecidable", "") or "")),
    ]
    if include_candidates:
        buckets.append(("候选", "\n".join(
            str(c.get("desc", "")) for c in (v.get("candidates") or [])
            if isinstance(c, dict))))
    total = 0
    where = []
    for name, text in buckets:
        if not text:
            continue
        n = text.count(UNSAID_MARK)
        if n:
            total += n
            where.append("%s×%d" % (name, n))
    return total, "、".join(where)


def ngram_rephrase_ratio(collision: Any, upstream_texts: Any,
                         cfg: Optional[Dict[str, Any]] = None
                         ) -> Optional[float]:
    """ing 输出里「与上游逐句高重合」的句子占比（字符 n-gram Jaccard）。

    与引擎 V2.2.2 的 `view.rephrase_ratio`（关键词/BM25 尺子）**不是同一个
    尺子**：本函数是任务指定的字符 n-gram 口径，离线可复现。两者都可当
    「复述」的证据，本模块不复用引擎的 BM25（保持纯函数、零依赖）。

    返回 None 表示「无判定条件」（无上游 / 上游或 ing 有效句不足 3 句）——
    与引擎同口径：缺输入不给读数，不冒充 0。
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    coll = str(collision or "")
    if not coll.strip() or coll.strip() in ("", "（%s）" % UNSAID_MARK):
        return None
    n = int(c.get("ngram_n") or 2)
    ing_sents = sentences(coll, _SENT_MIN_LEN)
    if len(ing_sents) < 3:
        return None
    upstream_sents: List[str] = []
    for t in (upstream_texts or []):
        upstream_sents.extend(sentences(t, _SENT_MIN_LEN))
    upstream_sents = upstream_sents[:int(c.get("max_sentences") or 240)]
    if not upstream_sents:
        return None
    ing_grams = _grams_of_sentences(ing_sents, n)
    up_grams = _grams_of_sentences(upstream_sents, n)
    sent_thr = float(c.get("rephrase_sent_threshold") or 0.35)
    hits = 0
    for g in ing_grams:
        if _max_sim(g, up_grams) >= sent_thr:
            hits += 1
    return hits / len(ing_grams)


_STRUCTURAL_FLAG_MARKERS = (
    "position_all_same", "too_many_amp_candidates", "judge_mostly_both",
    "no_amp_candidates", "no_amp_at_all", "polarity_all_same",
    "expand_imbalanced",
)


def has_structural_anomaly(view_dict: Dict[str, Any]) -> bool:
    """质量旗里是否有「结构异常」族（触发自省复核的触发器之一）。"""
    for f in (view_dict or {}).get("quality_flags") or []:
        s = str(f)
        if any(m in s for m in _STRUCTURAL_FLAG_MARKERS):
            return True
    return False


def _candidate_sentences(view_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """预先算好逐候选的相似度证据（只算一次，audit/trace 共用）。"""
    v = view_dict or {}
    c = dict(DEFAULT_CFG)
    n = int(c.get("ngram_n") or 2)
    coll_sents = sentences(v.get("collision") or "", _SENT_MIN_LEN,
                           drop_unsaid=False)
    man_sents = sentences(v.get("manifest") or "", _SENT_MIN_LEN,
                          drop_unsaid=False)
    up_sents: List[str] = []
    for t in (v.get("upstream_texts") or []):
        up_sents.extend(sentences(t, _SENT_MIN_LEN))
    cap = int(c.get("max_sentences") or 240)
    coll_g = _grams_of_sentences(coll_sents[:cap], n)
    man_g = _grams_of_sentences(man_sents[:cap], n)
    up_g = _grams_of_sentences(up_sents[:cap], n)
    cands = [c0 for c0 in (v.get("candidates") or [])
             if isinstance(c0, dict)]
    out = []
    for i, cand in enumerate(cands[:int(c.get("max_candidates") or 60)], 1):
        desc = str(cand.get("desc") or "")
        g = ngrams(desc, n)
        row = {
            "idx": i,
            "kind": str(cand.get("kind") or ""),
            "source": str(cand.get("source") or ""),
            "desc": desc,
            "n": len(cands),
            "sim_ing": _max_sim(g, coll_g),
            "sim_view": _max_sim(g, man_g),
            "sim_upstream": _max_sim(g, up_g),
        }
        out.append(row)
    return out


def detect_suspicious_candidates(view_dict: Dict[str, Any],
                                 cfg: Optional[Dict[str, Any]] = None
                                 ) -> Tuple[List[int], List[Dict[str, Any]]]:
    """确定性「可疑候选」判定（回填/复述/后补的代理判据）。

    判据（任一命中即可疑；设计目标是**宁可多报**——决策方向保守）：

    1. **空展开**：ing 为空/未生但存在候选 ⇒ 无展开证据，全部可疑；
    2. **复述 view**：候选与 manifest 的相似度 >= sim_high 且高于与 ing 的
       相似度 ⇒ 像是从 view 回填的（LLM 高频理由「与 view 重复」）；
    3. **复述上游**：候选与上游 view 文本相似度 >= sim_high；
    4. **尾部 + 框架 kind**：候选位于尾部窗口（相对位置 >= susp_tail_rel）
       且 kind ∈ {question,thread,other,startpoint} —— LLM 标签实测这类
       组合被判「框架性后补」的比例最高；
    5. **尾部无出处**：位于尾部窗口且与 ing 的相似度 < sim_low（找不到
       展开出处）——对应 LLM 理由「未在 ing 输出中出现，疑为搬旧料」。

    返回 `(indices_1based, rows)`；rows 供 `trace` 与阈值调参。
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    rows = _candidate_sentences(view_dict)
    v = view_dict or {}
    coll = str(v.get("collision") or "").strip()
    empty_expansion = (not coll) or coll in ("", "（%s）" % UNSAID_MARK)
    sim_low = float(c.get("sim_low") or 0.12)
    sim_high = float(c.get("sim_high") or 0.45)
    tail_frac = float(c.get("susp_tail_frac") or 0.25)
    min_tail = int(c.get("susp_min_tail") or 2)
    tail_rel = float(c.get("susp_tail_rel") or 0.6)
    kinds = tuple(c.get("susp_kinds") or ())
    kind_rel = float(c.get("susp_kind_rel") or 0.6)
    susp: List[int] = []
    for r in rows:
        n = max(1, int(r["n"]))
        rel = (r["idx"] - 1) / n if n > 1 else 0.0
        tail_n = max(min_tail, int(math.ceil(tail_frac * n)))
        in_tail = (r["idx"] > n - tail_n) and rel >= tail_rel
        reasons = []
        if empty_expansion:
            reasons.append("empty_expansion")
        if r["sim_view"] >= sim_high and r["sim_view"] > r["sim_ing"]:
            reasons.append("restates_view")
        if r["sim_upstream"] >= sim_high:
            reasons.append("restates_upstream")
        if in_tail and r["kind"] in kinds:
            reasons.append("tail_kind")
        if in_tail and r["sim_ing"] < sim_low:
            reasons.append("tail_no_origin")
        r["reasons"] = reasons
        r["suspicious"] = bool(reasons)
        if reasons:
            susp.append(r["idx"])
    return susp, rows


def detect_suspicious_amps(view_dict: Dict[str, Any],
                           cfg: Optional[Dict[str, Any]] = None
                           ) -> Tuple[List[int], List[Dict[str, Any]]]:
    """确定性「可疑 &」判定：与候选或彼此高度重合 = 复述凑数。

    另附结构规则：amp 候选占比超上限时，把「与候选最像」的那几条点出来。
    该字段在引擎里**只写池注释**（不挂旗、不进 carry），所以这里的
    精度要求低于 suspicious_candidates。
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    v = view_dict or {}
    n = int(c.get("ngram_n") or 2)
    thr = float(c.get("amp_restate_sim") or 0.6)
    amps = [a for a in (v.get("amps") or []) if isinstance(a, dict)]
    cand_g = [ngrams(str(x.get("desc") or ""), n)
              for x in (v.get("candidates") or []) if isinstance(x, dict)]
    amp_g = [ngrams(str(a.get("desc") or ""), n) for a in amps]
    rows = []
    susp: List[int] = []
    for i, (amp, g) in enumerate(zip(amps, amp_g), 1):
        best_c = _max_sim(g, cand_g)
        best_a = max((jaccard(g, g2) for j, g2 in enumerate(amp_g, 1)
                      if j != i and g2), default=0.0)
        reasons = []
        if best_c >= thr:
            reasons.append("restates_candidate")
        if best_a >= thr:
            reasons.append("restates_amp")
        rows.append({"idx": i, "sim_candidate": best_c,
                     "sim_amp": best_a, "reasons": reasons})
        if reasons:
            susp.append(i)
    return susp, rows


def detect_honest_about_empty(view_dict: Dict[str, Any],
                              cfg: Optional[Dict[str, Any]] = None) -> bool:
    """确定性「诚实未生」读数（无决策消费者，仅叙述/回放对齐用）。

    口径：
      · 无候选无 & ⇒ True（本来就没什么可生）；
      · ing 与 view 都没有正文（或只有「此处未生」）⇒ True；
      · 有候选但 ing 未生且 view 未生 ⇒ False（有东西没说清 = 不诚实）。
    """
    v = view_dict or {}
    cands = [x for x in (v.get("candidates") or []) if isinstance(x, dict)]
    amps = [x for x in (v.get("amps") or []) if isinstance(x, dict)]
    coll = str(v.get("collision") or "").strip()
    man = str(v.get("manifest") or "").strip()
    unsaid_only = ("（%s）" % UNSAID_MARK, UNSAID_MARK)
    coll_empty = (not coll) or coll in unsaid_only
    man_empty = (not man) or man in unsaid_only
    if not cands and not amps:
        return True
    if coll_empty and man_empty:
        return False
    return True


def _new_candidate_count(rows: Sequence[Dict[str, Any]],
                         expanded_descs: Optional[Sequence[str]],
                         cfg: Dict[str, Any]) -> int:
    """「新增候选」数：有展开快照时 = 找不到展开出处的候选数；否则全量。"""
    if not expanded_descs:
        return len(rows)
    n = int(cfg.get("ngram_n") or 2)
    high = float(cfg.get("sim_high") or 0.45)
    exp_g = [ngrams(x, n) for x in expanded_descs]
    new = 0
    for r in rows:
        g = ngrams(r["desc"], n)
        if _max_sim(g, exp_g) < high:
            new += 1
    return new


def _unsaid_gate(n: int, lim: int, model_escape: bool,
                 cfg: Dict[str, Any]) -> str:
    """与引擎 `_unsaid_flag_gate` 同式：返回 flag / note / off。"""
    if lim <= 0 or n <= lim:
        return "off"
    strong = bool(model_escape) or (
        n > max(lim + int(cfg.get("unsaid_strong_extra") or 2),
                int(round(lim * float(cfg.get("unsaid_strong_frac") or 1.5)))))
    return "flag" if strong else "note"


def _count_existing_backfill(view_dict: Dict[str, Any], cfg: Dict[str, Any]) -> bool:
    """本圈质量检查是否**已经**挂过 candidates_backfilled（双源闸的第二源）。"""
    for f in (view_dict or {}).get("quality_flags") or []:
        if "candidates_backfilled" in str(f):
            return True
    return False


def audit(view_dict: Dict[str, Any],
          cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """确定性自省核：一次算齐 self_check 的全部字段 + 决策投影 + 触发理由。

    参数
    ----
    view_dict : packed 的 `views[entry]`（或引擎内的等价 dict）。允许缺字段：
        `entry / candidates / amps / collision / manifest / upstream_texts /
         quality_flags / rephrase_ratio / threads / undecidable_product /
         expanded_descs(可选，运行时展开快照)`
    cfg : 阈值覆盖（键见 `DEFAULT_CFG`）；None = 默认。

    返回：JSON 可序列化 dict，键见 `_AUDIT_KEYS`。**不抛异常**（防御式）。
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    v = view_dict or {}
    entry = str(v.get("entry") or "")
    out: Dict[str, Any] = {
        "schema": SCHEMA,
        "entry": entry,
    }
    # ---- 1. unsaid（确定可算，与引擎同口径）----
    unsaid_n, unsaid_where = count_unsaid(v)
    unsaid_n_all, unsaid_where_all = count_unsaid(v, include_candidates=True)
    lim = int(c.get("unsaid_limit") or 3)
    gate = _unsaid_gate(unsaid_n, lim, False, c)
    out.update({
        "unsaid_count": unsaid_n,
        "unsaid_where": unsaid_where,
        "unsaid_count_all": unsaid_n_all,
        "unsaid_where_all": unsaid_where_all,
        "unsaid_is_escape": bool(lim > 0 and unsaid_n > lim),
    })
    # ---- 2. ing 复述（字符 n-gram Jaccard；已有引擎读数时同时给出）----
    ratio = ngram_rephrase_ratio(v.get("collision") or "",
                                 v.get("upstream_texts") or [], c)
    engine_ratio = v.get("rephrase_ratio")
    rephrase_thr = float(c.get("rephrase_threshold") or 0.5)
    rephrased = bool(ratio is not None and ratio >= rephrase_thr)
    out.update({
        "ing_rephrase_ratio": (round(float(ratio), 6)
                               if ratio is not None else None),
        "ing_rephrased": rephrased,
        "engine_rephrase_ratio": (float(engine_ratio)
                                  if isinstance(engine_ratio, (int, float))
                                  else None),
    })
    # ---- 3. 可疑候选 / 可疑 & / 诚实未生 ----
    susp, rows = detect_suspicious_candidates(v, c)
    amp_susp, amp_rows = detect_suspicious_amps(v, c)
    honest = detect_honest_about_empty(v, c)
    n_cand = len(rows)
    out.update({
        "suspicious_candidates": susp,
        "suspicious_candidate_ratio": (round(len(susp) / n_cand, 6)
                                       if n_cand else 0.0),
        "suspicious_amps": amp_susp,
        "honest_about_empty": honest,
        "candidate_total": n_cand,
        "amp_total": len(amp_rows),
    })
    # ---- 4. 触发器（只有这里为 True 才值得花一次 LLM）----
    # ★ 回放态没有逐圈 provenance（`expanded_descs` 不在 packed 里），
    #   `new_candidates` 只能在**运行时**算：拿不到展开快照时**不**据此
    #   触发（否则回放态恒 100% 触发，证明不了任何调用下降）。
    _has_provenance = v.get("expanded_descs") is not None
    new_n = _new_candidate_count(rows, v.get("expanded_descs"), c)
    min_new = int(c.get("min_new_candidates") or 6)
    llm_min = int(c.get("susp_llm_min") or 2)
    llm_max = int(c.get("susp_llm_max") or 8)
    existing_bf = _count_existing_backfill(v, c)
    reasons: List[str] = []
    if _has_provenance and new_n >= min_new:
        reasons.append("new_candidates")
    # 决策歧义区：可疑数落在门槛附近才复核（>=5 才可能挂旗；>=8 已是强源）
    if (llm_min <= len(susp) <= llm_max) and (n_cand or existing_bf):
        reasons.append("candidates_suspect")
    if rephrased:
        reasons.append("rephrase")
    if has_structural_anomaly(v):
        reasons.append("structural")
    coll = str(v.get("collision") or "").strip()
    silent = ((not rows) and (not amp_rows)) or (
        (not coll or coll in ("", "（%s）" % UNSAID_MARK)) and bool(rows))
    if silent:
        reasons.append("silent")
    if len(amp_susp) >= 2:
        reasons.append("amps_suspect")
    # LLM 复核只服务「回填判定」这一个决策字段；amps_suspect 只写池注释，
    # 不单独触发调用（省的是调用，不是判断）。
    llm_needed = any(r in ("new_candidates", "candidates_suspect",
                           "rephrase", "structural", "silent")
                     for r in reasons)
    out["triggers"] = {"llm_needed": bool(llm_needed), "reasons": reasons}
    # ---- 5. 决策投影（与引擎决策字段一一对应，供回放比对）----
    bf_min = int(c.get("backfill_min") or 5)
    bf_need = int(c.get("backfill_need") or 8)
    backfill_flag = bool(len(susp) >= bf_min
                         and (existing_bf or len(susp) >= bf_need))
    carry_kinds: List[str] = []
    if susp:
        carry_kinds.append("candidate")
    if rephrased:
        carry_kinds.append("ing")
    if bool(lim > 0 and unsaid_n > lim):
        carry_kinds.append("any")
    bq = v.get("both_quota") or {}
    if isinstance(bq, dict):
        items = [i for i in (bq.get("items") or [])
                 if isinstance(i, dict) and str(i.get("missing") or "").strip()]
        if items:
            carry_kinds.append("dual")
    out["decision"] = {
        "backfill_flag": backfill_flag,
        "backfill_count": len(susp),
        "carry_kinds": carry_kinds,
        "unsaid_flag": gate == "flag",
        "unsaid_note": gate == "note",
        "idle_signal": bool(rephrased),
        "honest_about_empty": honest,
    }
    # ---- 6. 论证 trace（Lead 独立复核用；不影响决策）----
    trace_limit = int(c.get("trace_limit") or 60)
    out["trace"] = [
        {
            "idx": int(r["idx"]),
            "sim_ing": round(float(r["sim_ing"]), 6),
            "sim_view": round(float(r["sim_view"]), 6),
            "sim_upstream": round(float(r["sim_upstream"]), 6),
            "grown_from_upstream": bool(r["sim_upstream"] >= float(
                c.get("sim_high") or 0.45)),
            "source": r.get("source") or "",
            "kind": r.get("kind") or "",
            "reason": ",".join(r.get("reasons") or []) or "ok",
        }
        for r in rows[:trace_limit]
    ]
    out["cfg_used"] = {k: (list(c[k]) if isinstance(c[k], tuple) else c[k])
                       for k in DEFAULT_CFG}
    out["notes"] = _audit_notes(out, rows, c)
    return out


def _audit_notes(out: Dict[str, Any], rows: Sequence[Dict[str, Any]],
                 cfg: Dict[str, Any]) -> List[str]:
    """人读的一行结论（auto 模式会写进 self_check.notes）。"""
    notes: List[str] = []
    if not rows and not out.get("amp_total"):
        notes.append("本圈无候选无 &：仅记未生计数 %d" % out["unsaid_count"])
    if out.get("suspicious_candidates"):
        notes.append("可疑候选 %d 条（截尾/框架 kind/复述 view 代理判据）"
                     % len(out["suspicious_candidates"]))
    if out.get("suspicious_amps"):
        notes.append("可疑 & %d 条（与候选/彼此高重合）"
                     % len(out["suspicious_amps"]))
    if out.get("ing_rephrased"):
        notes.append("ing 复述比 %.0f%%（字符 %d-gram Jaccard 口径）"
                     % (100 * float(out.get("ing_rephrase_ratio") or 0),
                        int(cfg.get("ngram_n") or 2)))
    if out.get("unsaid_is_escape"):
        notes.append("「%s」%d 处，超阈值 %d"
                     % (UNSAID_MARK, out["unsaid_count"],
                        int(cfg.get("unsaid_limit") or 3)))
    return notes


#: `audit` 顶层返回键（契约；新增字段请同步此处与 docs）。
_AUDIT_KEYS = (
    "schema", "entry",
    "unsaid_count", "unsaid_where", "unsaid_is_escape",
    "ing_rephrase_ratio", "ing_rephrased", "engine_rephrase_ratio",
    "suspicious_candidates", "suspicious_candidate_ratio",
    "suspicious_amps", "honest_about_empty",
    "candidate_total", "amp_total",
    "triggers", "decision", "trace", "cfg_used", "notes",
)


def audit_notes_line(result: Dict[str, Any]) -> str:
    """把 audit 结果压成一行（供渲染/日志；不制造新结论）。"""
    notes = list((result or {}).get("notes") or [])
    if notes:
        return "；".join(notes)
    return "确定性自省核：未发现可疑项"


# ============================================================
# local / auto 模式：确定性核与语义判定的**一致性校验**
# ============================================================
def consistency_check(audit_result: Dict[str, Any],
                      semantic: Optional[Dict[str, Any]],
                      cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """比较「确定性核」与「语义判定」（本地模型或收窄 LLM）是否一致。

    用途（引擎 `self_check_mode="local"`）：
      · 一致 → 采信语义判定（它是真正的判断，核只做计数/复述校验）；
      · 不一致 → **升级云 LLM**（本地模型不可靠时不许静默放行）。

    返回 `{"agree": bool, "escalate": bool, "diffs": [str]}`；
    `semantic` 为 None（本地模型失败/超时）时 `escalate=True`。
    """
    c = dict(DEFAULT_CFG)
    c.update(cfg or {})
    a = audit_result or {}
    if not isinstance(semantic, dict) or not semantic:
        return {"agree": False, "escalate": True,
                "diffs": ["semantic_missing"]}
    diffs: List[str] = []
    # 1) 可疑候选：核报了而语义一条没报 = 漏；语义报得过多 = 不可信
    det_susp = list(a.get("suspicious_candidates") or [])
    sem_susp = [int(x) for x in (semantic.get("suspicious_candidates") or [])
                if str(x).isdigit()]
    n_cand = int(a.get("candidate_total") or 0)
    if det_susp and not sem_susp:
        diffs.append("missing_suspicious")
    max_reasonable = max(int(c.get("susp_llm_max") or 8),
                         int(round(0.6 * max(1, n_cand))))
    if sem_susp and len(sem_susp) > max_reasonable:
        diffs.append("too_many_suspicious")
    # 2) ing 复述：核有比值而语义说否 / 语义说是而核比值为空=无上游，都不一致
    det_ratio = a.get("ing_rephrase_ratio")
    sem_rephrased = bool(semantic.get("ing_rephrased"))
    if bool(a.get("ing_rephrased")) != sem_rephrased:
        if sem_rephrased and det_ratio is None:
            # 真的复述但核没有上游文本可比 —— 不是语义的错，采信语义
            pass
        elif abs((det_ratio or 0.0) - (c.get("rephrase_threshold") or 0.5)) > 0.25:
            diffs.append("rephrase_disagree")
    return {"agree": not diffs, "escalate": bool(diffs), "diffs": diffs}
