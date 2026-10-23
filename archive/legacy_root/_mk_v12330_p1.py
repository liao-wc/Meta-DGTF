#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 1 阶段：层职责守卫（LDG）纯函数 + View 字段 + 缺省修真。

依据见 `_设计_层职责守卫_v12330.md`（LiveRAG/SIGIR'25 的 C×R 调和平均、
NAACL'25 的 core/background/followup 子问题覆盖、EMNLP'25 的边际增益收敛）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"


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


# ── 纯函数块：插在 `def sem_thr_relative(` 之前（D1 那片常量之后）──
LDG = '''# ============================================================
# 层职责守卫（Layer Duty Guard）—— 在**停止/收敛处**回答一句：
#   「这一层到底替原始问题干了什么」。零新增 LLM 调用（全规则）。
#
# 依据（2025）：
#   · LiveRAG / SIGIR 2025：Coverage 按权重加权 + Relatedness 惩罚无用断言
#     + 取两者**调和平均**（一项好一项差不给高分）。本处用规则判定替代
#     其 NLI 判定，把开销压到 0。
#   · NAACL 2025 sub-question coverage：子问题分 core/background/follow-up
#     分类别计覆盖；**未覆盖的 core 问项点名并喂回生成器**（实测胜率 74%）。
#   · EMNLP 2025 自纠收敛：每轮只削掉剩余误差的固定比例 ⇒ 边际增益递减
#     即「推不动了」。工程判据 = 连续 patience 次 Δ < τ 就停。
#
# ★ 红线自检：职责度是**读数不是分数** —— 不进 `_quality_verdict`，
#   不参与「谁优谁劣」。它只做两件事：① 不许把截断说成自然停止
#   （署名纪律）；② 让层能**因为推不动而停**（新停止判据）。
# ============================================================

#: [LDG] 问项类别权重（core / background / follow-up）。
#   ★ 与 NAACL'25 的分类一致：附加目标（「甚至…」）**不占核心权重**，
#     否则一句并列就把「主问没答」洗成高覆盖。
_DUTY_KIND_W = {"core": 0.70, "background": 0.30, "followup": 0.10}
_DUTY_FLOOR = 0.35          # 职责度下限：低于 ⇒ 不许署名自然停止 + 补一圈
_DUTY_TAU = 0.02            # 边际职责增益阈值（ΔS < τ 记一次「推不动」）
_DUTY_PATIENCE = 2          # 连续 N 圈推不动 ⇒ 记「职责增益收敛」停止理由
_DUTY_REMEDY_ROUNDS = 1     # 职责未尽的定向补救圈上限
_DUTY_DELIVERY_FLOOR = 0.10  # 交付面占全文比重告警线
_DUTY_HIT_SIM = 0.55        # 问项命中判据：词面包含 或 sim3 ≥ 此值

#: [LDG] 问项类别判据用的**附加目标引导词**（「甚至/乃至/以及」后的项
#:   是附加目标，不占核心权重）。
_DUTY_FOLLOWUP_LEAD = ("甚至", "乃至", "更甚至", "以至于", "以至")
#: [LDG] 主问引导词 —— 出现这些的项按 core 计。
_DUTY_CORE_LEAD = ("如何", "怎么", "怎样", "哪些", "为什么", "是否",
                   "能不能", "可不可以", "什么时候", "多少")
#: [LDG] 各层 objective 关键词（判 Relatedness 的 Useful 档）。
_DUTY_OBJ_WORDS = {
    "0": ("显形", "结构", "候选", "线头", "悬置", "属性", "位置", "&"),
    "1": ("回答", "证据", "可判定", "子问题", "锚点", "数据", "结论"),
    "both": ("第三者", "张力", "两端", "对撞", "反转", "裁决"),
    "all": ("清算", "闭环", "整体", "不可通约", "交代", "元"),
}


def question_aspects(question: str):
    """问项抽取（规则、零成本）：把问题切成带类别与权重的问项。

    ★ 为什么不用一次 LLM 调用抽：抽取是**每层每次评估都要跑**的读数，
      一次调用会把「守卫」变成新的开销源；而它要的是**稳定可比**，
      不是「抽得漂亮」。规则判据还能被变异体钉住（LLM 抽的钉不住）。
    ★ 分类规则（对应 NAACL'25 的三类）：
      · 带「甚至/乃至/以及」引导 ⇒ followup（附加目标，权重最低）；
      · 含主问引导词（如何/哪些/为什么…）⇒ core；
      · 长 ≥ 4 字的实体性短语 ⇒ core；短碎片 ⇒ background。
    """
    q = str(question or "").strip()
    if not q:
        return []
    # 切分：标点 + 并列连接词（先把连接词换成标点，再切）
    _sep = q
    for _w in ("甚至", "乃至", "以及", "并且", "同时", "还有", "及"):
        _sep = _sep.replace(_w, "，" + _w)
    _sep = _sep.replace("？", "，").replace("?", "，").replace("。", "，")
    for _w in ("；", ";", "、", "，", ",", "：", ":"):
        _sep = _sep.replace(_w, "\\n")
    raw = [x.strip() for x in _sep.split("\\n") if x.strip()]
    # 去掉纯引导词碎片
    _drop = {"如何", "怎么", "怎样", "为什么", "是否", "以及", "甚至", "乃至"}
    out = []
    for x in raw:
        if x in _drop or len(x) < 2:
            continue
        kind = "core"
        if any(x.startswith(w) or (w + x) in q for w in _DUTY_FOLLOWUP_LEAD):
            kind = "followup"
        elif any(w in x for w in _DUTY_CORE_LEAD):
            kind = "core"
        elif len(x) < 4:
            kind = "background"
        out.append({"text": x[:40], "kind": kind,
                    "weight": float(_DUTY_KIND_W.get(kind, 0.3))})
    # 去重（同文本保首个类别）
    seen, ded = set(), []
    for a in out:
        if a["text"] in seen:
            continue
        seen.add(a["text"])
        ded.append(a)
    return ded


def duty_components(aspects, deliver_text, objective_words=(),
                    corpus=None, hit_sim: float = _DUTY_HIT_SIM) -> dict:
    """算 (C 覆盖, R 相关, S 调和平均) 与点名缺失的 core 问项。

    ★ C（Coverage）：按类别权重加权 —— 与 LiveRAG 的 Direct/Useful 加权同构，
      这里的三档是 core/background/followup。
    ★ R（Relatedness）：`|Direct| / (|Direct| + |Useless|)` —— **专门惩罚
      无用断言**（本跑 86.5% 的正文是内部面，正是 Useless 的来源）。
      判定：断言命中任一问项 ⇒ Direct；命中该层 objective 词 ⇒ Useful；
      都不命中 ⇒ Useless。
    ★ S = 2CR/(C+R)（调和平均）：C 与 R 有一项塌了就整体塌 —— 这是刻意的，
      「覆盖高但全是废话」与「言之有物但没答问题」都不该拿高分。
    """
    _d = str(deliver_text or "").strip()
    _aw = [w for w in (objective_words or []) if w]
    _as = list(aspects or [])

    def _hit(asp_text, seg, require):
        if asp_text in seg:
            return True
        if require not in seg:
            return False
        try:
            return float(_sim3(asp_text, seg, corpus=corpus)) >= hit_sim
        except Exception:
            return False

    # ── C ──
    _tw = sum(float(a.get("weight", 0.3)) for a in _as) or 0.0
    _hw, missing = 0.0, []
    for a in _as:
        t = str(a.get("text", ""))
        if t and _hit(t, _d, t[:2]):
            _hw += float(a.get("weight", 0.3))
        elif str(a.get("kind", "core")) == "core":
            missing.append(t)
    C = (_hw / _tw) if _tw else 0.0

    # ── R ──
    segs = [x.strip() for x in
            re.split(r"[。！？\\n]+|(?<=[；;])\\s*", _d) if len(x.strip()) >= 6]
    direct = useful = useless = 0
    for sg in segs:
        if any(str(a.get("text", "")) and str(a["text"]) in sg for a in _as):
            direct += 1
        elif any(w in sg for w in _aw):
            useful += 1
        else:
            useless += 1
    R = (direct / (direct + useless)) if (direct + useless) else 0.0

    # ── S ──
    S = (2.0 * C * R / (C + R)) if (C + R) > 0 else 0.0
    return {"C": round(C, 4), "R": round(R, 4), "S": round(S, 4),
            "missing_core": missing[:6],
            "n_asp": len(_as), "n_seg": len(segs),
            "seg_direct": direct, "seg_useful": useful, "seg_useless": useless}


def duty_of_layer(entry, question, deliver_text, objective_words=(),
                  corpus=None) -> dict:
    """一层在**停止/收敛处**的职责读数（薄壳：抽问项 + 算三读数 + 定门）。"""
    asp = question_aspects(question)
    d = duty_components(asp, deliver_text, objective_words, corpus=corpus)
    d["entry"] = str(entry)
    d["core_total"] = len([a for a in asp if a.get("kind") == "core"])
    d["short"] = bool(float(d.get("S", 0.0)) < float(_DUTY_FLOOR))
    return d


def duty_short_line(d: dict) -> str:
    """职责读数的**一行文案**（产物头部与层尾共用，避免两处措辞分叉）。"""
    if not isinstance(d, dict) or not d:
        return "职责 —（未测）"
    _m = d.get("missing_core") or []
    _tail = ("；缺核心 %d 项：%s" % (len(_m), "、".join(_m[:3]))
             if _m else "")
    return ("职责 S=%.2f（覆盖 C=%.2f · 相关 R=%.2f；核心 %d/%d）%s"
            % (float(d.get("S", 0.0)), float(d.get("C", 0.0)),
               float(d.get("R", 0.0)),
               int(d.get("core_total", 0) or 0) - len(_m),
               int(d.get("core_total", 0) or 0), _tail))


'''

COPIED = "def sem_thr_relative(texts, corpus=None, lo=_SEM_REL_LO, hi=_SEM_REL_HI,"


def main():
    s = _load()

    # 0) 版本号（两处）
    s = rep(s, "元 DGTF · v1.23.29", "元 DGTF · v1.23.30", "docstring 标题")
    s = rep(s, '__version__ = "1.23.29"', '__version__ = "1.23.30"', "__version__")

    # 1) 纯函数块（含 re：本文件已 import re，确认过）
    s = rep(s, COPIED, LDG + COPIED, "LDG 纯函数块")

    # 2) View 新字段
    old_f = '''    quality_flags: List[str] = field(default_factory=list)
    quality_verdict: str = ""
    self_check: dict = field(default_factory=dict)'''
    new_f = '''    # ── [LDG 层职责守卫] 停止/收敛处的职责读数（读数不是分数）──
    #: `{C, R, S, missing_core, core_total, short, ...}`；空 dict = 未测。
    duty: dict = field(default_factory=dict)
    #: 逐圈 trace：`[{round, S, C, R}]` —— 边际增益判据读它。
    duty_trace: List[dict] = field(default_factory=list)
    #: 补救圈是否已用（每层最多用 `_DUTY_REMEDY_ROUNDS` 次）。
    duty_remedy_used: int = 0
    #: 交付面占全文比重（0-1；由渲染层回填）。
    delivery_share: Optional[float] = None

    quality_flags: List[str] = field(default_factory=list)
    quality_verdict: str = ""
    self_check: dict = field(default_factory=dict)'''
    s = rep(s, old_f, new_f, "View 新字段")

    # 3) distance_to_question 缺省 1.0 → None（缺省不许冒充读数）
    _o1 = ("            try:\n"
           "                view.distance_to_question = float(\n"
           "                    extra.get(\"distance_to_question\", 1.0))\n"
           "            except (TypeError, ValueError):\n"
           "                view.distance_to_question = 1.0")
    _n1 = ("            # ★ [LDG 修真] 缺省从 1.0 改 None：\n"
           "            #   「模型没报」不许冒充「离得最远」（与上一版修\n"
           "            #   touch_rate 同族：默认值不得冒充读数）。\n"
           "            _d2q_raw = extra.get(\"distance_to_question\")\n"
           "            try:\n"
           "                view.distance_to_question = (\n"
           "                    None if _d2q_raw is None else float(_d2q_raw))\n"
           "            except (TypeError, ValueError):\n"
           "                view.distance_to_question = None")
    s = rep(s, _o1, _n1, "distance_to_question 赋值处")

    _o2 = ("            try:\n"
           "                d2q = float(data.get(\"distance_to_question\", 1.0))\n"
           "            except (TypeError, ValueError):\n"
           "                d2q = 1.0")
    _n2 = ("            _d2q_v = data.get(\"distance_to_question\")\n"
           "            try:\n"
           "                d2q = None if _d2q_v is None else float(_d2q_v)\n"
           "            except (TypeError, ValueError):\n"
           "                d2q = None")
    s = rep(s, _o2, _n2, "distance 入口处缺省")

    _o3 = "                \"distance_to_question\": max(0.0, min(1.0, d2q)),"
    _n3 = ("                \"distance_to_question\": (None if d2q is None\n"
           "                                            else max(0.0, min(1.0, d2q))),")
    s = rep(s, _o3, _n3, "distance 装配处")

    s = rep(s, "    distance_to_question: float = 1.0",
            "    distance_to_question: Optional[float] = None",
            "distance 字段类型")

    _save(s)
    print("OK 第 1 阶段（LDG 纯函数 + 字段 + 缺省修真）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "def question_aspects(question: str):" in s2
    assert "def duty_of_layer(entry, question, deliver_text" in s2
    assert '__version__ = "1.23.30"' in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
