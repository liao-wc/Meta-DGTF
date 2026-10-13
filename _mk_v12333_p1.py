#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P1：剩余吸收项（纯函数层）。

机制级：
  ① **anytime-valid 置信序列 + 停止判据**（stitched Hoeffding CS，Howard et al. 2021）
     —— 本项目每圈边跑边判 = optional stopping，原本**无任何有效性保证**。
  ② **发散检测 + 回滚指针**（LoopGain：收敛/停滞/发散三态；发散时给「历史最佳」指针
     —— ★ 换指针不删数据，红线「失败留痕」）。
  ③ **预算感知 bandit**（LinUCB 的极简 UCB1-with-cost；**默认关**）。
读数/结构：
  ④ compact 内部面预算（率失真）+ ⑤ 锚点离线解析验证 + ⑥ 锚点内部批判（史学）
  + ⑦ 分级证明标准（法学）+ ⑧ 对撞裁决维度拆分 + ⑨ 信念 staleness 读数。
"""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"


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


BLOCK = '''# ============================================================
# 学科吸收 · 第三批（机制级）
# ============================================================

#: anytime-valid 停止的总开关默认值（"off" ⇒ 出厂零行为差）。
_ANYTIME_DEFAULT_ALPHA = 0.0
#: 发散检测的窗口（序列少于这个数不表态）。
_DIVERGE_MIN_N = 4


def stitched_hoeffding_lower(seq, delta: float = 0.05):
    """**anytime-valid 均值下界**（stitched Hoeffding，Howard et al. 2021）。

    ★ 为什么必须是 anytime-valid：本项目**每圈都要看**一致率/读数再决定停不停
      —— 这正是 optional stopping。用固定样本公式（如 p̂ ± 1.96·σ/√n）在
      「边跑边看」下**有效性不成立**（假阳率会暴涨）。
      stitched Hoeffding 给出对**任意停时**都成立的下界：
          p̂ − sqrt( (1/(2n)) · (1+1/n) · ln( sqrt(n+1)/δ ) )
      即 `E[φ_τ] ≤ α` 对任意停时 τ 成立（Doob 可选停时定理的落地形式）。

    `seq`：0/1 序列（如逐条「三票是否一致」）。
    返回 `{n, mean, lower, upper, delta}`；样本不足（n<2）⇒ None（不表态）。
    """
    try:
        xs = [1.0 if float(x) >= 0.5 else 0.0 for x in (seq or [])]
    except (TypeError, ValueError):
        return None
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / float(n)
    d = float(delta if (delta and 0 < delta < 1) else 0.05)
    rad = math.sqrt((1.0 / (2.0 * n)) * (1.0 + 1.0 / n)
                    * math.log(math.sqrt(n + 1) / d))
    return {"n": n, "mean": round(mean, 4),
            "lower": round(max(0.0, mean - rad), 4),
            "upper": round(min(1.0, mean + rad), 4),
            "delta": d}


def anytime_majority_decided(seq, delta: float = 0.05, thr: float = 0.5):
    """**anytime-valid 的「多数已确立」判据**：下界 > 阈值 ⇒ 可停（opt-in）。

    ★ 口径：这是「随时看随时停仍然有效」的判据，**不是**「跑得更久就更好」。
      阈值取 0.5 = 只判「证据已足以说『多数一致』」，不判质量高低。
    """
    lb = stitched_hoeffding_lower(seq, delta)
    if not lb:
        return False, {"why": "样本不足（n<2）"}
    return bool(lb["lower"] > float(thr)), lb


def divergence_state(series) -> Optional[dict]:
    """**三态判决**（吸收 LoopGain 的收敛/停滞/发散）。

    · 收敛：序列**趋于稳定**（后半段方差显著小于前半段）；
    · 停滞：整体方差极小（一直在同一水平）；
    · 发散：方差上升**且** lag-1 自相关为正（CSD 前兆）—— 再跑无益。
    ★ 与 CSD 读数同源但用途不同：CSD 只报读数；本函数给出**三态判决**供
      「回滚指针」与冒烟判据用（**仍不改停止行为**）。
    """
    try:
        xs = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    n = len(xs)
    if n < _DIVERGE_MIN_N:
        return None
    half = n // 2
    def _var(v):
        if len(v) < 2:
            return 0.0
        m = sum(v) / len(v)
        return sum((x - m) ** 2 for x in v) / len(v)
    v1, v2 = _var(xs[:half]), _var(xs[half:])
    m = sum(xs) / n
    den = sum((x - m) ** 2 for x in xs)
    ac1 = (sum((xs[i] - m) * (xs[i - 1] - m) for i in range(1, n)) / den
           if den > 1e-12 else 0.0)
    if v2 > 1.5 * v1 and ac1 > 0.2:
        state = "发散"
    elif max(v1, v2) <= 1e-9:
        state = "停滞"
    elif v2 < 0.7 * v1:
        state = "收敛"
    else:
        state = "平稳"
    return {"state": state, "var_first": round(v1, 4), "var_last": round(v2, 4),
            "ac1": round(ac1, 4), "n": n}


def best_round_index(series, higher_is_better: bool = True) -> Optional[int]:
    """**历史最佳圈的指针**（回滚指针；1-based）。

    ★ 依据 LoopGain：发散时回滚到「历史最佳」而不是继续跑。
    ★ 红线「失败留痕」⇒ 本函数**只给指针**：被回滚掉的那几圈**不删**，
      产物照旧全部保留，只是在指针处标「历史最佳」。
    """
    try:
        xs = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    if not xs:
        return None
    best = max(xs) if higher_is_better else min(xs)
    return xs.index(best) + 1


class BudgetBandit:
    """**预算感知 bandit**（极简 UCB1-with-cost）。

    ★ 吸收 AAAI'26 的 Budget-Aware LinUCB 的**思想**（成本进入收益项），
      但**不引入依赖、不上上下文特征**：这里只做「臂 = 圈数档，
      收益 = 职责度读数 − λ·成本」的 UCB1。
    ★ **默认关**（config `auto.bandit.enabled=false`）⇒ 出厂零行为差。
    ★ 探索的代价：会**故意选已知较差的档**。因此每次「探索选择」都在产物留痕
      （否则用户看到「这次为什么跑得差」会查无原因）。
    """

    def __init__(self, arms, c: float = 1.0, cost_w: float = 0.3):
        self.arms = [dict(a) if isinstance(a, dict) else {"v": a}
                     for a in (arms or [])]
        self.n = [0] * len(self.arms)
        self.mean = [0.0] * len(self.arms)
        self.cost = [0.0] * len(self.arms)
        self.c = float(c or 1.0)
        self.cost_w = float(cost_w if cost_w is not None else 0.3)
        self.t = 0

    def _score(self, i):
        if self.n[i] == 0:
            return float("inf")          # 未试过的臂优先（确定性探索）
        bonus = self.c * math.sqrt(2.0 * math.log(max(2, self.t)) / self.n[i])
        return self.mean[i] - self.cost_w * self.cost[i] + bonus

    def pick(self) -> dict:
        scores = [self._score(i) for i in range(len(self.arms))]
        i = max(range(len(scores)), key=lambda k: scores[k])
        exploit = all(v > 0 for v in self.n)
        return {"index": i, "arm": self.arms[i], "explore": not exploit,
                "scores": [None if s == float("inf") else round(s, 4)
                           for s in scores]}

    def update(self, i, reward, cost) -> None:
        if not (0 <= i < len(self.arms)):
            return
        self.t += 1
        self.n[i] += 1
        k = self.n[i]
        self.mean[i] += (float(reward or 0.0) - self.mean[i]) / k
        self.cost[i] += (float(cost or 0.0) - self.cost[i]) / k


# ── ④ compact 内部面预算（率失真）─────────────────────────
#: 内部面占全文的**目标上限**（超出 ⇒ 索引化，不删内容）。
_COMPACT_INNER_BUDGET = 0.60


def compact_plan(inner_chars: int, total_chars: int,
                 budget: float = _COMPACT_INNER_BUDGET) -> dict:
    """**率失真**式的内部面预算：给定位数下最优表示，而不是「越短越好」。

    ★ 依据：率失真理论（给定位率下的最优失真）+ ACE 的反面数据
      （把 1.8 万 token 压到 122 token ⇒ 准确率 66.7→57.1）。
      ⇒ 超预算时**索引化**（正文留摘要 + 指向 packed），**不删内容**。
    """
    t = max(1, int(total_chars or 0))
    i = max(0, int(inner_chars or 0))
    share = i / float(t)
    over = share > float(budget)
    return {"inner_share": round(share, 4), "budget": float(budget),
            "over": bool(over),
            "verdict": ("内部面超预算 ⇒ 本轮**索引化**（不删内容，正文回退到索引 + "
                        "指向 packed 全量）" if over else "内部面在预算内")}


# ── ⑤⑥⑦ 锚点三项：解析验证 / 内部批判 / 分级证明标准 ──────
_DOMAIN_INTEREST = (
    ("gov", "公权力方（利益：政策延续性 / 管辖边界）"),
    ("edu", "学术方（利益：可发表性 / 方法新颖）"),
    ("org", "非营利/行业组织（利益：成员共识 / 行业自律）"),
    ("com", "商业方（利益：产品与市场叙事）"),
    ("net", "基础设施/社群"),
    ("io", "技术社群/初创"),
)
_MEDIA_HINTS = ("blog", "medium", "substack", "zhihu", "weibo", "toutiao",
                "36kr", "sspai", "mp.weixin")


def anchor_offline_check(url: str) -> dict:
    """**离线解析验证**（吸收 refchecker 的「按可审计表面判」）。

    ★ 依据：引用要么解析得开、要么解析不开 —— 这比「判断言真假」可靠得多
      （refchecker：2025 NeurIPS/USENIX 约 1/20 论文含 ≥2 条疑似幻觉引用）。
      本函数只做**离线**部分（URL 形态 / 域名与协议 / 是否可解析），
      不发网络请求（零依赖 + 零成本），可达性留给联网通道。
    """
    u = str(url or "").strip()
    out = {"url": u[:200], "ok": False, "why": []}
    if not u:
        out["why"].append("空 URL（无法解析）")
        return out
    if not (u.startswith("http://") or u.startswith("https://")):
        out["why"].append("非 http(s) 形态")
    if " " in u:
        out["why"].append("含空格（形态异常）")
    host = ""
    try:
        rest = u.split("://", 1)[1] if "://" in u else u
        host = rest.split("/", 1)[0].split("?", 1)[0].lower()
    except Exception:
        host = ""
    if not host or "." not in host:
        out["why"].append("域名不完整")
    out["host"] = host[:120]
    out["ok"] = not out["why"]
    return out


def anchor_interest_hint(url: str) -> str:
    """**锚点内部批判**（史学 Quellenkritik 的「内部批判」）：

    ★ 外部批判（真伪/来源/年代）本项目已有 `tier`；**内部批判**（作者立场与
      利益倾向）此前缺失。这里用**域名类型**给一个**提示**（不是判词）：
      「这条 claim 出自谁，他/它可能有哪类利益倾向」。
      ⇒ 与红线一致：这是**提示**，不是给锚点打分。
    """
    host = ""
    try:
        rest = str(url or "").split("://", 1)[1] if "://" in str(url) else str(url or "")
        host = rest.split("/", 1)[0].split("?", 1)[0].lower()
    except Exception:
        host = ""
    for _h in _MEDIA_HINTS:
        if _h in host:
            return "媒体/自媒体（利益：流量与叙事张力）"
    for _tld, _hint in _DOMAIN_INTEREST:
        if host.endswith("." + _tld) or ("." + _tld + ".") in (host + "."):
            return _hint
    return "未识别来源类型（按最弱处理）"


def anchor_evidence_standard(claim_kind: str) -> dict:
    """**分级证明标准**（法学 burden of proof）+ **谁主张谁举证**。

    ★ 依据：法学把证明标准分级 —— `preponderance`（优势证据）/
      `clear and convincing`（明确且有力）/ `beyond reasonable doubt`（排除合理怀疑），
      且**主张方负举证责任**。本项目原本只有一刀切的 `tier_floor` gate。
    ★ 本函数**只给标准与举证方**，不改 gate 行为（gate 仍按 tier_floor）。
    """
    k = str(claim_kind or "").strip().lower()
    table = {
        # claim 的性质 → (标准, 谁举证)
        "causal": ("beyond_reasonable_doubt", "主张因果者举证"),
        "numerical": ("clear_and_convincing", "给出数字者举证（含口径与来源）"),
        "normative": ("preponderance", "主张规范者举证（偏好不可当证据）"),
        "factual": ("preponderance", "主张事实者举证"),
        "predictive": ("clear_and_convincing", "预测者举证（含基准与不确定度）"),
    }
    std, who = table.get(k, ("preponderance", "主张者举证"))
    return {"claim_kind": k or "unknown", "standard": std, "burden_on": who}


# ── ⑧ 对撞裁决维度拆分（言语行为论 / 多评委）─────────────
_ADJ_ASPECTS = (
    ("逻辑", ("矛盾", "不一致", "自相", "推导", "前提")),
    ("事实", ("事实", "数据", "证据", "实测", "引用")),
    ("边界", ("边界", "条件", "范围", "前提未定", "口径")),
    ("后果", ("后果", "风险", "代价", "副作用", "影响")),
)


def adjudication_aspect(tension: str, how: str) -> str:
    """给一条**裁决**判它的**依据维度**（逻辑/事实/边界/后果），判不出 ⇒ "未标注"。

    ★ 依据：多评委框架（逻辑/事实/修辞/策略/伦理…）+ 本项目红线
      「自省是另一个视角，不可合并」⇒ 裁决依据**拆维留痕**而不是合成一个 `how`。
    """
    blob = "%s %s" % (str(tension or ""), str(how or ""))
    hits = [name for name, keys in _ADJ_ASPECTS
            if any(k in blob for k in keys)]
    return "/".join(hits) if hits else "未标注"


# ── ⑨ 信念 staleness 读数（不改四态）────────────────────
def belief_staleness(item: dict, cur_round: int) -> dict:
    """**信念陈旧度**读数（吸收 ABES 的时间衰减 + ftl-beliefs 的 STALE 态）。

    ★ **不改四态**：加第五态会让历史 packed 的判据全部失准（红线级风险）
      ⇒ 本函数只出**读数**，另一个字段回填，不改 `status`。
    · `seen_at`（最后被确认的圈号）→ `age`（距现在多少圈未再确认）
    · `stale_hint`：age ≥ 3 且状态仍 active ⇒ 提示「可能已过期，需复确认」
    """
    it = item or {}
    last = it.get("last_confirmed_round")
    if last is None:
        last = (max(it.get("rounds_seen") or [0])
                if it.get("rounds_seen") else None)
    try:
        age = (int(cur_round or 0) - int(last)) if last is not None else None
    except (TypeError, ValueError):
        age = None
    return {"id": it.get("id", ""), "age": age,
            "stale_hint": bool(age is not None and age >= 3
                               and str(it.get("status", "")) == "active")}


'''


def main():
    s = _load()

    # 版本号两处
    s = rep(s, "元 DGTF · v1.23.32", "元 DGTF · v1.23.33", "docstring 标题")
    s = rep(s, '__version__ = "1.23.32"', '__version__ = "1.23.33"', "__version__")

    # 纯函数块（插在第二排块之前）
    _anch = "# ============================================================\n" \
            "# 学科吸收 · 第二批（读数与结构，不改行为）"
    s = rep(s, _anch, BLOCK + _anch, "第三批纯函数块")

    _save(s)
    print("OK P1（第三批纯函数）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    for _m in ("def stitched_hoeffding_lower(", "def anytime_majority_decided(",
               "def divergence_state(", "def best_round_index(",
               "class BudgetBandit:", "def compact_plan(",
               "def anchor_offline_check(", "def anchor_interest_hint(",
               "def anchor_evidence_standard(", "def adjudication_aspect(",
               "def belief_staleness("):
        assert _m in s2, _m
    print("复读校验通过")


if __name__ == "__main__":
    main()
