# -*- coding: utf-8 -*-
"""答案门：答案是否**针对本题**、跨视角一致性是否够格。

为什么需要（实测，见 `docs/产物质量分析_20261028.md`）
------------------------------------------------------
现有就绪门只校验两件事：四层过程标准达标、事实卡 answered 且有官方证据 id。
它拦得住「空」，拦不住「偏」—— 实测三个反例都 `answer_ready=True`：

  · 「成年人正常心率是多少次每分钟」→ 答案给的是**定义**，coverage **1.00**
  · 「HTTP 503 表示什么」→ 答案讲的是 `Retry-After` 响应头，coverage 0.90
  · 「HTTP 301 表示什么」→ 答案讲「指定网址的方式」，coverage 0.50

⇒ `coverage` 是「研究层子问题被作答的加权比例」，**不是**「答案回答了问题」。
本模块补这条。

能力边界（必须如实，避免被当全量）
--------------------------------
`relevance` 用可复算的 token / 题型规则，只能抓「答案完全没提题目实体」。
**抓不到「提了实体但主句答错」** —— 例如 HTTP 401 的答案主句讲 100 状态码、
401 只在括号里，本模块会放行。那类需要语义判官。故 `suspect` 数是**下限**。

设计约束
--------
1. **纯函数、零依赖、可离线复算**：不调 LLM、不读文件。
2. **不确定就 `weak`，绝不硬判 `suspect`**：证据不足时放行（宁可漏报，
   不可把正确答案判死 —— 方向错的判据比没判据更危险，本模块第一版就
   因为「题目里任意数字当锚」把 11 个正确的 GDP 数值题全判成 suspect）。
3. **年份不是答案锚**：题面「2024年GDP增速是多少」里 2024 是限定条件，
   答案「5.0%」不含它依然正确。
4. **题型分叉**：数值题的答案本来就是纯数字，拿题干 token 比必然误判。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

# ── 识别用正则 ────────────────────────────────────────────
_NUM = re.compile(r"\d{2,5}")
_ABBR = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{1,}")
_CJK = re.compile(r"[\u4e00-\u9fa5]{2,}")
_DIGIT = re.compile(r"[0-9]|[一二三四五六七八九十百千万亿两]")
#: 数值型题的问法（问的是「多少」而不是「是什么」）
_NUMERIC_Q = re.compile(
    r"多少|几[个项种年月天条件次]|多大|多高|多长|多重|多快|百分之|几成|"
    r"占比|增速|涨幅|总量|总额|比例|排名|第几")
#: 明确要定义/解释的问法 —— 与上一条同时出现时以「问定义」为准
_DEF_Q = re.compile(r"表示什么|是什么|的定义|什么意思|含义|指的是")

#: 题干里不具标识性的高频词
_STOP = frozenset({
    "什么", "表示", "是否", "多少", "哪些", "如何", "为什么", "怎么", "怎样",
    "介绍", "解释", "说明", "作用", "意思", "含义", "状态", "代码", "状态码",
    "协议", "请问", "一下", "区别", "关系", "原因", "影响", "特点", "定义",
})

#: 英文里不具标识性的词
_STOP_EN = frozenset({"the", "a", "an", "is", "of", "in", "to", "and", "or",
                      "http", "https", "www", "com"})

#: 跨视角一致性下限（Krippendorff）：低于此值只能算「暂定」
ALPHA_ACCEPT = 0.667
ALPHA_STRONG = 0.800


def _year(tok: str) -> bool:
    return len(tok) == 4 and tok.isdigit() and 1900 <= int(tok) <= 2099


def key_tokens(question: str) -> Dict[str, list]:
    """从题面抽锚：数字（去年份）、英文缩写、中文词块。"""
    nums = [n for n in _NUM.findall(question or "") if not _year(n)]
    abbrs = [a for a in _ABBR.findall(question or "")
             if not a.isdigit() and a.lower() not in _STOP_EN]
    cj = [c for c in _CJK.findall(question or "")
          if c not in _STOP and len(c) >= 2]
    return {"nums": nums, "abbrs": abbrs, "cjk": cj}


def question_kind(question: str) -> str:
    """题型：numeric（问数值）/ entity（问定义或实体）/ unknown。

    ★ 「表示什么」优先于「多少」：像「HTTP 431 表示什么，最多几个头」这种
      混合问法，主问是定义 ⇒ 走实体判据。
    """
    q = question or ""
    if _DEF_Q.search(q):
        return "entity"
    if _NUMERIC_Q.search(q):
        return "numeric"
    return "unknown"


def relevance(question: str, answer: str) -> Dict[str, Any]:
    """答案是否针对本题。返回 {verdict, reason, anchor, kind}。

    verdict:
      · `ok`      —— 命中题目锚 / 数值题给出了数
      · `suspect` —— 明显没针对本题（可用作降级依据）
      · `weak`    —— 无法判断（证据不足，**必须放行**）
      · `empty`   —— 答案为空
    """
    ans = answer or ""
    kind = question_kind(question)
    if not ans.strip():
        return {"verdict": "empty", "reason": "答案为空", "anchor": "", "kind": kind}

    if kind == "numeric":
        ok = bool(_DIGIT.search(ans))
        return {"verdict": "ok" if ok else "suspect",
                "reason": "数值题：答案%s给出数值" % ("已" if ok else "未"),
                "anchor": "digit", "kind": kind}

    tokens = key_tokens(question)
    nums = tokens["nums"]
    if nums:
        anchor = max(nums, key=len)
        return {"verdict": "ok" if anchor in ans else "suspect",
                "reason": "数字锚 %r %s答案" % (anchor, "命中" if anchor in ans else "未命中"),
                "anchor": anchor, "kind": kind}

    abbrs = [a for a in tokens["abbrs"] if len(a) >= 3]
    if abbrs:
        anchor = abbrs[0]
        hit = anchor.lower() in ans.lower()
        return {"verdict": "ok" if hit else "suspect",
                "reason": "缩写锚 %r %s答案" % (anchor, "命中" if hit else "未命中"),
                "anchor": anchor, "kind": kind}

    cjk = tokens["cjk"]
    if cjk:
        anchor = max(cjk, key=len)[:4]
        hit = anchor in ans
        # 中文锚太弱：命不中只算 weak，不判 suspect
        return {"verdict": "ok" if hit else "weak",
                "reason": "中文锚 %r %s答案（弱判据，未命中不放行降级）"
                          % (anchor, "命中" if hit else "未命中"),
                "anchor": anchor, "kind": kind}

    return {"verdict": "weak", "reason": "题面无可用锚", "anchor": "", "kind": kind}


def agreement(tri_alpha: Optional[float]) -> Dict[str, Any]:
    """跨视角一致性够不够格。返回 {verdict, reason, alpha}。

    ★ 只做「够不够格」的判断，不解释 α 低的原因 —— 三层真实认知分歧
      本来就是这套系统要的东西，但**它必须影响「这条答案可不可信」**。
    """
    if tri_alpha is None:
        return {"verdict": "unknown", "reason": "无 α 读数", "alpha": None}
    try:
        a = float(tri_alpha)
    except (TypeError, ValueError):
        return {"verdict": "unknown", "reason": "α 非数值", "alpha": None}
    if a != a:                                  # NaN
        return {"verdict": "unknown", "reason": "α 为 NaN", "alpha": None}
    if a >= ALPHA_STRONG:
        return {"verdict": "ok", "reason": "α=%.3f ≥ %.3f" % (a, ALPHA_STRONG),
                "alpha": a}
    if a >= ALPHA_ACCEPT:
        return {"verdict": "tentative",
                "reason": "α=%.3f 在 [%.3f, %.3f)：只能算暂定"
                          % (a, ALPHA_ACCEPT, ALPHA_STRONG), "alpha": a}
    return {"verdict": "low",
            "reason": "α=%.3f < %.3f（低于 Krippendorff 下限）" % (a, ALPHA_ACCEPT),
            "alpha": a}


def evaluate(question: str, answer: str, tri_alpha: Optional[float] = None,
             qtype: str = "") -> Dict[str, Any]:
    """一次算完两道门。返回值直接进产物（`quality.answer_gates`）。

    ★★ 阻断权只有 `relevance` 有。`agreement`（α 低）**只做警示不阻断**：
       α 低是三层**真实认知分歧**（这套系统本来就要对撞），它不等于答案错。
       实测把 α 低直接算 blocked 会误杀 108 个正确答案（黄河长度 5464 千米、
       HTTP 404 Not Found 都对）。**拿不出来的证据不能当降级依据。**

    综合判定：
      · `blocked` —— relevance 明确不过（答案未针对本题 / 空）。有实证支撑。
      · `caveat`  —— 只有弱证据（答案未提中文锚、α 低、α 缺失）⇒ 放行但标记。
      · `pass`    —— 两道门都清楚通过。
    """
    rel = relevance(question, answer)
    agr = agreement(tri_alpha)
    if rel["verdict"] in ("suspect", "empty"):
        verdict = "blocked"
    elif rel["verdict"] == "weak" or agr["verdict"] in ("low", "tentative",
                                                        "unknown"):
        verdict = "caveat"
    else:
        verdict = "pass"
    return {
        "schema": "dgtf.answer_gates.v1",
        "verdict": verdict,
        "relevance": rel,
        "agreement": agr,
        "qtype": qtype or "",
    }


def should_block(gates: Dict[str, Any]) -> bool:
    """这门是否要求把 answer_ready 降级（调用方按配置决定要不要用）。"""
    return str((gates or {}).get("verdict")) == "blocked"


def block_reason(gates: Dict[str, Any]) -> str:
    """降级原因（写进 answer_ready_reason，便于审计）。"""
    g = gates or {}
    rel = (g.get("relevance") or {})
    agr = (g.get("agreement") or {})
    parts = []
    if rel.get("verdict") in ("suspect", "empty"):
        parts.append("答案未针对本题（%s）" % rel.get("reason", ""))
    if agr.get("verdict") == "low":
        parts.append("跨视角一致性不足（%s）" % agr.get("reason", ""))
    return "；".join(parts) or "答案门未通过"
