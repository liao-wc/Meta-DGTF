# -*- coding: utf-8 -*-
"""[第六期补 · 候选生成量化] 依据 ③（早期信号提前停掉低价值样本）。

## 为什么补这一处
用户点名的五处量化里，**候选生成**是本轮唯一没做的：
  「各层的锚点重述是否也要考虑量化，以及阴阳展开，**候选生成**，
    ing 的输出内容，还有 view 的输出重点等也要有相关依据」

## 依据 ③ 怎么落到「候选生成」
  · RASC / DeepConf / Think@n 的共性：**在花钱之前先算一个便宜的早期信号**，
    低价值就停。DeepConf 的关键点：**全局平均会掩盖局部塌陷**。
  · 候选生成这一站的「下一笔钱」= **对偶判断**（`_dual_judge`，逐条 candidate 一次调用）。
    若这一圈长出来的候选**全是上一圈说过的说法**（复述），
    那一笔对偶判断就是**在为无信息量付费**。
  · ⇒ 新增纯函数 `candidate_yield(cands, prev_texts) -> dict`：
    对每条候选，算它与「上一圈候选集合」的最大相似度；
    `new_ratio` = 相似度 < 阈值的条数占比 ⇒ **这一圈真的长了多少**。
    这是**读数与告警**，**不改流程**（红线：建议与执行分开）。

★ 零成本、可开关、有留痕、**不调 LLM**（与 L2~L4 同规格）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ── A1：模块级纯函数（插在 `def semantic_density(` 之后那段之末，
#          用 `_SD_FILLER` 那个块的结束位置作锚不稳定 ⇒ 改用 `def _sd_is_punct(` 前插）──
A1_ANCHOR = "def _sd_is_punct(ch: str) -> bool:"
A1_NEW = '''def candidate_yield(cands, prev_texts, thr: float = 0.72) -> dict:
    """[第六期 · 依据 ③] 候选生成的**产出率**（零成本纯函数，不调 LLM）。

    ★ 目的：给「下一笔钱」（对偶判断 = 逐条一次调用）一个**便宜的早期信号**。
      RASC / DeepConf / Think@n 的共性都是在花钱之前先算一个便宜的指标；
      DeepConf 还提醒「**全局平均会掩盖局部塌陷**」⇒ 这里同时报
      `max_sim`（最像的那一条）与 `collapsed`（是否整批塌陷）。

    口径：
      · 对每条候选，取它与**上一圈候选文本**的最大相似度（`_overlap_coef`
        与 `_similar` 两把尺子取大 —— 与 `yin_yang_divergence` 同一套）；
      · `new_ratio` = 相似度 **< thr** 的条数占比 ⇒ **真的长了多少**；
      · `max_sim` = 全批最大相似度（最高的一条有多像旧的）；
      · `collapsed` = `new_ratio < 0.34`（**整批基本是复述** ⇒ 提示，不拦）。

    ★ 缺输入（候选空 / 无历史）⇒ 全 `None` + `verdict=""`（**不表态**）。
      ——「这一圈是第一次跑」与「这一圈真没长」是两件事，不能混。
    """
    _c = [str(x) for x in (cands or []) if str(x or "").strip()]
    _p = [str(x) for x in (prev_texts or []) if str(x or "").strip()]
    if not _c or not _p:
        return {"n": len(_c), "n_new": None, "new_ratio": None,
                "max_sim": None, "collapsed": None, "verdict": ""}
    _sims = []
    for _x in _c:
        _mx = 0.0
        for _y in _p:
            _s = max(_overlap_coef(_x, _y), _similar(_x, _y, thr))
            if _s > _mx:
                _mx = _s
        _sims.append(_mx)
    _n_new = sum(1 for s in _sims if s < thr)
    _ratio = _n_new / float(len(_sims))
    _mx = max(_sims)
    _v = "collapsed" if _ratio < 0.34 else "ok"
    return {"n": len(_c), "n_new": _n_new, "new_ratio": round(_ratio, 4),
            "max_sim": round(_mx, 4), "collapsed": _ratio < 0.34,
            "verdict": _v}


def _sd_is_punct(ch: str) -> bool:'''

# ── A2：真实入口接线（`_drop_banned` 之后、`_dual_judge` 之前）──
#   位置语义：读数是「这一圈长出来的候选」，必须取在**对偶判断之前**
#   （否则读的是被改写过的集合），且**丢掉禁令之后**（禁令拦下的不算增长）。
A2_ANCHOR = '''        candidates = self._drop_banned(candidates, inp, view)
        self.vp(f"   📋 展开候选 {len(candidates)} 条"'''
A2_NEW = '''        candidates = self._drop_banned(candidates, inp, view)
        # ★ [第六期 · 依据 ③] 候选**产出率**（零成本纯函数）：
        #   给「下一笔钱」（逐条对偶判断）一个早期信号；只读数 + 告警，**不改流程**。
        try:
            _cy = candidate_yield([getattr(c, "desc", "") for c in candidates],
                                  getattr(view, "_prev_cand_descs", None))
            if _cy.get("verdict"):
                _quant_note(view, "candidate_yield", _cy)
                if _cy.get("verdict") == "collapsed":
                    self.vp("   ⚑ 候选产出率偏低 %.2f（最高相似 %.2f）"
                            "——这一圈基本是复述，"
                            "对偶判断可能在为无信息量付费"
                            % (_cy.get("new_ratio") or 0.0,
                               _cy.get("max_sim") or 0.0))
            view._prev_cand_descs = [getattr(c, "desc", "") for c in candidates]
        except Exception:
            pass
        self.vp(f"   📋 展开候选 {len(candidates)} 条"'''

PATCHES = [("A1 candidate_yield 纯函数", A1_ANCHOR, A1_NEW),
           ("A2 真实入口接线", A2_ANCHOR, A2_NEW)]


def main() -> int:
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    crlf = txt.count("\r\n")
    lf = txt.count("\n") - crlf
    assert lf == 0, "主文件非纯 CRLF（LF-only=%d）" % lf
    assert b"\r\r\n" not in raw
    s = txt.replace("\r\n", "\n")
    if "def candidate_yield(" in s:
        print("已是修后状态（幂等跳过）")
        return 0
    bak = HERE / "_bak_v12333_pre_candyield.py"
    if not bak.exists():
        bak.write_bytes(raw)
        print("备份 ->", bak.name)
    for name, a, b in PATCHES:
        n = s.count(a)
        assert n == 1, "[%s] 锚点命中 %d 次（应 1）" % (name, n)
        s = s.replace(a, b, 1)
        print("  ✓ %s" % name)
    assert s.count("def candidate_yield(") == 1
    assert s.count('_quant_note(view, "candidate_yield"') == 1
    assert s.count("candidate_yield([getattr(c,") == 1
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    SRC.write_bytes(out)
    back = SRC.read_bytes().decode("utf-8")
    assert back.count("\n") - back.count("\r\n") == 0
    print("OK 主文件已补候选生成量化（%d 行 / 纯 CRLF）" % (back.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
