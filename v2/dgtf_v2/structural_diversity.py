# -*- coding: utf-8 -*-
"""[v1.31] 立场/论据类型结构多样性检查（只读诊断，不参与判定）。

背景：`position_all_same_structural` 表示立场全同、但 `why_position` 的
**词面**多样。词面多样不等于结构多样 —— 模型可能用同一套论证模板换词
重写。本模块把「立场分布」与「论据类型分布」分开计数，并把「同一句式
套 N 遍」也记成模板重复；命中模板单一才建议重采样。

★ 只提供读数与 `homogeneous` 判据；是否重采样、是否采用重采样结果，
  由主流程决定（见 `DGTF._maybe_structural_resample`）。
★ 本模块不读写 View/Candidate，不调用 LLM，不做判定。
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List

#: 论据类型按**显式连接词/句式线索**归类，不追求语义精确。
#: 目的只是把「同一论证模板」与「不同论证路径」分开；顺序即优先级，
#: 取第一个命中的**主类型**（一条理由里混多种连接词时不叠成新类型，
#: 否则偶然多写一个「因为」就会被误判成「论据多样」）。
_ARGUMENT_PATTERNS = (
    ("因果", ("因为", "由于", "因此", "所以", "导致", "从而", "以致",
              "源于", "归因", "致使")),
    ("对比", ("相比", "相较", "对比", "相反", "反之", "不同于", "区别",
              "差异", "而另一端")),
    ("定义", ("指的是", "定义为", "所谓", "本质", "意味着", "也就是",
              "即是", "换言之")),
    ("例证", ("例如", "比如", "譬如", "举例", "案例", "实例", "以此为例")),
    ("数据", ("数据", "统计", "比例", "占比", "百分比", "百分之", "增长",
              "下降", "增幅", "降幅")),
    ("假设", ("如果", "假如", "假设", "倘若", "一旦", "若是")),
    ("让步", ("虽然", "尽管", "固然", "即使", "即便", "诚然")),
    ("权威", ("研究", "报告", "规定", "标准", "专家", "文献", "官方",
              "政策")),
)

_TYPE_OTHER = "其他"
_TYPE_EMPTY = "空"


def argument_type(text: str) -> str:
    """把一条 `why_position` 归到**一个**主论据类型（启发式）。"""
    t = str(text or "").strip()
    if not t:
        return _TYPE_EMPTY
    for name, kws in _ARGUMENT_PATTERNS:
        if any(k in t for k in kws):
            return name
    return _TYPE_OTHER


def _field(item, key: str, default=""):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _bigrams(text: str) -> set:
    t = re.sub(r"[\s\W_]+", "", str(text or ""))
    if len(t) < 2:
        return {t} if t else set()
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _text_sim(a: str, b: str) -> float:
    ka, kb = _bigrams(a), _bigrams(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / max(len(ka), len(kb))


def _ordered(counter: Counter) -> List[dict]:
    """稳定输出分布：先按条数降序，再按标签排序（便于跨跑对比）。"""
    return [{"value": k, "count": v}
            for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def analyze_structural_diversity(candidates: Iterable,
                                 template_sim: float = 0.8) -> dict:
    """统计立场/论据类型结构多样性。

    返回字段（全部只读）：
      · `n` / `positions` / `position_kinds`：立场分布与种类数；
      · `argument_types` / `argument_kinds`：论据主类型分布与种类数；
      · `template_repeat_ratio`：`why_position` 两两字符二元组相似度
        ≥ `template_sim` 的对数占比（越高越像同一句式换词）；
      · `same_position` / `single_argument_type` / `template_like`；
      · `homogeneous`：立场全同 **且**（论据类型单一 **或** 模板重复高），
        即「同构且多为模板单一」的命中条件；
      · `samples`：前 5 条样本（行号+立场+论据类型+理由），便于定位。
    """
    rows = []
    for i, c in enumerate(candidates or [], 1):
        pos = str(_field(c, "position", "") or "?")
        why = str(_field(c, "why_position", "") or "").strip()
        rows.append({"index": i, "position": pos, "why_position": why,
                     "argument_type": argument_type(why)})
    n = len(rows)
    positions = Counter(r["position"] for r in rows)
    argument_types = Counter(r["argument_type"] for r in rows)

    why_rows = [r for r in rows if r["why_position"]]
    pairs = 0
    repeats = 0
    for i in range(len(why_rows)):
        for j in range(i + 1, len(why_rows)):
            pairs += 1
            if _text_sim(why_rows[i]["why_position"],
                         why_rows[j]["why_position"]) >= template_sim:
                repeats += 1
    template_repeat_ratio = (repeats / pairs) if pairs else 0.0

    same_position = n >= 2 and len(positions) == 1
    # 空理由单独一类；只有当所有非空理由同属一个**真实**类型时才算单一。
    _real_types = {r["argument_type"] for r in why_rows
                   if r["argument_type"] not in (_TYPE_EMPTY,)}
    single_argument_type = bool(why_rows) and len(_real_types) <= 1
    template_like = template_repeat_ratio >= 0.8
    homogeneous = bool(same_position
                       and (single_argument_type or template_like))
    return {
        "n": n,
        "positions": _ordered(positions),
        "position_kinds": len(positions),
        "argument_types": _ordered(argument_types),
        "argument_kinds": len(argument_types),
        "why_present": len(why_rows),
        "template_repeat_ratio": round(template_repeat_ratio, 4),
        "same_position": same_position,
        "single_argument_type": single_argument_type,
        "template_like": template_like,
        "homogeneous": homogeneous,
        "template_sim": round(float(template_sim), 4),
        "samples": [
            {"index": r["index"], "position": r["position"],
             "argument_type": r["argument_type"],
             "why_position": r["why_position"][:80]}
            for r in rows[:5]
        ],
    }


def homogeneous_count(reports: Iterable[dict]) -> int:
    """回归口径：一组结构诊断里命中「同构且模板单一」的条数。"""
    return sum(1 for r in (reports or [])
               if isinstance(r, dict) and r.get("homogeneous"))
