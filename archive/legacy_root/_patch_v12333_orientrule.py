# -*- coding: utf-8 -*-
"""v1.23.33 续（三）：给「规则命中」路径补**零成本取向规则**。

## 逮到的真问题
`auto_plan(llm=...)` 里 B1 规则命中（`mode_rule(q)` 有值）时，注释白纸黑字写
「命中即定案，**不花这次模式调用**」—— 但紧接着为了补 `orientation` 又调了
`plan_orientation(q, cfg)`，而 `plan_orientation` **内部自己 new 一个 `LLM(cfg)`**
（签名只有 `config`、没有 `llm=` 参数）⇒ **真花了一次 LLM 调用**。
实测：规则命中路径 `LLM.call` 次数 = **1**（本该 0）。

⇒ 「省调用」的设计意图被自己的补丁抵消 —— 用户点名诉求「减少 LLM 调用」的直接违背。
   ★ 这正是「有接线 ≠ 这跑走得到」的反向形态：**成本账目和代码注释不一致**，
     因为没人把「规则命中 ⇒ 0 次调用」当判据跑过。

## 修法
新增 `orientation_rule(question)`（模块级纯函数 · 零成本），复用仓库既有的
`_DECISION_CUES` 语汇：**命中决策语境 ⇒ decision；否则 ⇒ boundary**。
★ 只在 `auto_plan` 的规则命中分支使用；**拿不准才回落 `plan_orientation`**。
  这保持了「LLM 是兜底而非首选」的原始设计，并且规则与 `_has_decision_context`
  同源 —— 不会出现「打桩说 decision、渲染说 boundary」的双真相。

## 与既有判据的关系
- P5.2.b / P5.2.c（`_v122_verify.py`）：断言「打桩带出 boundary + 只调一次」。
  规则命中路径下这两条**结构性不成立**（规则优先是有意设计，判据注释自己写了）
  ⇒ 属**判据过时**，改为「规则命中 ⇒ 0 次调用 + 取向由本地规则给」。
- 新增冒烟判据 ㉝：`orientation_rule` 方向两向 + `auto_plan` 规则命中时
  **LLM 调用 == 0**（构造性证明）。
"""
import io, sys
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.33.py"

NEW_FN = '''def orientation_rule(question: str) -> dict:
    """[第六期 · 降本] 规则优先的**取向**判断（零成本纯函数，不调 LLM）。

    ★ 为什么需要它：`auto_plan` 的 B1 规则命中时注释写「不花这次模式调用」，
      但为补 orientation 又调了 `plan_orientation`（内部 new `LLM(cfg)`，
      签名里没有 `llm=` ⇒ 打桩也进不去）⇒ 实测**还是花 1 次调用**，
      把模式规则省下的钱又花掉了。

    ★ 判据来源与 `_has_decision_context` **同源**（同一个 `_DECISION_CUES`）：
      命中决策语境 ⇒ decision（要可落地方案）；
      否则 ⇒ boundary（要边界清单）。
      —— 同源是为了避免「打桩判 decision、渲染判 boundary」的双真相。

    ★ 与 `plan_orientation`（LLM 版）的关系：**这是快路径，那是兜底**。
      本函数只答「有没有决策语汇」这一个可规则化的问题；
      真正的语义细判仍可回落 `plan_orientation`。

    返回 {"orientation": "boundary|decision", "reason": ..., "confidence": 1.0}
    """
    _q = str(question or "")
    if _has_decision_context(_q):
        return {"orientation": "decision",
                "reason": "规则：题面含决策语汇（要与不要/怎么选/下一步）",
                "confidence": 1.0}
    return {"orientation": "boundary",
            "reason": "规则：题面无决策语汇（问边界/风险/说不清的部分）",
            "confidence": 1.0}


def mode_rule(question: str):'''

OLD_SNIP = '''        _rm, _rr = mode_rule(q)
        if _rm:
            _ori = ""
            try:
                _ori = str((plan_orientation(q, cfg) or {})
                           .get("orientation", "") or "")
            except Exception:
                _ori = ""
            return _assemble_plan(
                _rm, {}, cfg, orientation=_ori, confidence=0.9,
                reason=_rr + "（规则命中，未花调度调用）")'''

NEW_SNIP = '''        _rm, _rr = mode_rule(q)
        if _rm:
            # ★★ [第六期 · 降本] 原来这里调 `plan_orientation(q, cfg)` 补取向 ——
            #    但它内部自己 `new LLM(cfg)`（签名里没有 `llm=`），
            #    ⇒ **真花掉一次调用**，把上面规则省下的钱又花了。
            #    改为**零成本取向规则**（与 `_has_decision_context` 同源）；
            #    只有规则拿不准（空题面）才回落 LLM 版。
            _ori = ""
            try:
                _or = orientation_rule(q)
                _ori = str((_or or {}).get("orientation", "") or "")
                if not _ori:
                    raise ValueError("取向规则未定")
            except Exception:
                _ori = ""
            if not _ori:
                try:
                    _ori = str((plan_orientation(q, cfg) or {})
                               .get("orientation", "") or "")
                except Exception:
                    _ori = ""
            return _assemble_plan(
                _rm, {}, cfg, orientation=_ori, confidence=0.9,
                reason=_rr + "（规则命中，未花调度调用）")'''


def main():
    raw = P.read_bytes()
    n_lf = raw.count(b"\n")
    n_crlf = raw.count(b"\r\n")
    assert n_lf == n_crlf, "主文件应为纯 CRLF（LF %d / CRLF %d）" % (n_lf, n_crlf)
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # A1：插模块级纯函数（锚点 = `def mode_rule(question: str):` 整行，命中 == 1）
    a1 = "def mode_rule(question: str):"
    assert s.count(a1) == 1, "A1 锚点命中 %d 次" % s.count(a1)
    s = s.replace(a1, NEW_FN, 1)

    # A2：改规则命中分支（整块，含缩进；命中 == 1）
    assert s.count(OLD_SNIP) == 1, "A2 锚点命中 %d 次" % s.count(OLD_SNIP)
    s = s.replace(OLD_SNIP, NEW_SNIP, 1)

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    assert out.count(b"\n") == out.count(b"\r\n")
    P.write_bytes(out)
    print("OK 补丁已应用；行数 %d → %d" % (n_lf, out.count(b"\n")))


main()
