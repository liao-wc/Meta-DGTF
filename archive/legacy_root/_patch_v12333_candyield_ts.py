# -*- coding: utf-8 -*-
"""v1.23.33 续（四）：修「候选产出率」的**时序缺陷**（历史挂在每圈重建的对象上）。

## 真跑探针逮到（`_probe_v12333_candyield.py`，mock 真实入口，零花费）
  Q1 `candidate_yield` 被调 **2 次**（接线上）—— 但
  Q2/Q3 两次返回 `verdict=''`、`quant_readings` 里**没有** `candidate_yield` 键。
  ⇒ 调用点可达、纯函数正确、判据 ㉜ 全绿，但**读数永远不落盘**。

## 根因（本项目第 3 类失败：时序颠倒）
  `MetaDGTF` 的圈循环里每圈 `dg = DGTF(entry, self.llm, self.config)` +
  `view = dg.run(inp)` ⇒ **DGTF 实例与 view 都是每圈新建**。
  而我把「上一圈候选」写在了 `view._prev_cand_descs` 上 ⇒ **下一圈必然读不到**
  ⇒ 恒 `None` ⇒ `candidate_yield` 永久走「缺输入不表态」分支 ⇒ 不落盘。

## 修法（不动任何签名）
  `inp.pool` = `self.pools[entry]` —— **每层一个、跨圈复用**（圈循环里
  `pool = self.pools[entry]` 在 `for r` 之外），是天然的历史载体。
  把 `_prev_cand_descs` 改挂 `inp.pool`。

## 与既有机制的关系
  · `view._expanded_descs`（L8892）**不能**用：它每圈被本圈候选覆盖，
    且它的语义是「累积」而非「上一圈」（累积由 `MetaDGTF` 的
    `all_expanded_descs` 在圈末完成）。
  · 也不新造第三份机制 —— 只把「历史载体」从**每圈重建的 view**
    换成**跨圈复用的 pool**，语义不变。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.33.py"

OLD = '''        # ★ [第六期 · 依据 ③] 候选**产出率**（零成本纯函数）：
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
'''

NEW = '''        # ★ [第六期 · 依据 ③] 候选**产出率**（零成本纯函数）：
        #   给「下一笔钱」（逐条对偶判断）一个早期信号；只读数 + 告警，**不改流程**。
        #   ★★ [时序修正] 历史必须挂在**跨圈存活**的对象上：
        #      `MetaDGTF` 圈循环里每圈 `dg = DGTF(...)` + `view = dg.run(inp)`
        #      ⇒ **DGTF 实例与 view 都每圈新建**；凡状态存 `view` 上，
        #      **下一圈必然读不到** ⇒ 恒 None ⇒ 永久「缺输入不表态」（不落盘）。
        #      真跑探针实测：调用 2 次、两次 `verdict` 都是 `''`、
        #      `quant_readings` 里没有这个键 —— 接线上纯函数全绿**也照样不可达**。
        #      `inp.pool`（= `self.pools[entry]`）**每层一个、跨圈复用** ⇒ 挂它。
        #   ★ 不新造第三份机制：只换**历史载体**（每圈重建的 view → 跨圈复用的 pool），
        #     语义不变。也不是复用 `view._expanded_descs` —— 它每圈被本圈候选
        #     覆盖、且语义是「累积」（累积由 `MetaDGTF.all_expanded_descs` 做）。
        _cypool = getattr(inp, "pool", None)
        try:
            _cy = candidate_yield(
                [getattr(c, "desc", "") for c in candidates],
                getattr(_cypool, "_prev_cand_descs", None))
            if _cy.get("verdict"):
                _quant_note(view, "candidate_yield", _cy)
                if _cy.get("verdict") == "collapsed":
                    self.vp("   ⚑ 候选产出率偏低 %.2f（最高相似 %.2f）"
                            "——这一圈基本是复述，"
                            "对偶判断可能在为无信息量付费"
                            % (_cy.get("new_ratio") or 0.0,
                               _cy.get("max_sim") or 0.0))
            if _cypool is not None:
                _cypool._prev_cand_descs = [
                    str(getattr(c, "desc", "") or "").strip()
                    for c in candidates]
        except Exception:
            pass
'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
    s = s.replace(OLD, NEW, 1)
    assert s.count("_prev_cand_descs") == 2, \
        "`_prev_cand_descs` 应恰好 2 处（读 1 + 写 1），实得 %d" % s.count("_prev_cand_descs")
    assert "view._prev_cand_descs" not in s, "还有挂在每圈重建 view 上的历史"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 时序修正已应用；行数 %d" % out.count(b"\n"))


main()
