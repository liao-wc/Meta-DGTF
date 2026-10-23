# -*- coding: utf-8 -*-
"""P2 · **圈级心跳**：用「池增量」当本圈产出的代理，在 `_before_round` 一处搞定。

## 为什么这是最优路径
层级心跳（`_schedule_tick`）只在**层收尾**时能拿到 `view`；
圈级要读「上一圈」的读数，而 `view` **每圈新建**。
★ 若去两个圈循环调用点各存一次 `self._last_view = view`，就落进本项目
  反复踩的「**同一条逻辑两条通道各写一份**」⇒ 迟早分叉。

**⇒ 改用「池增量」**：`_before_round(entry, pool, layer_no)` **每圈都调**，
  在它里记下**本圈开始时的池规模**；下一圈开始时，`now - prev` 恰好等于
  **上一圈的产出**（新增的 & 与线头）。⇒ **只改一处、零额外计算**。

## 触发规则（与层级心跳同源，但用圈信号）
· 上一圈池**零增量**（复述/停滞）⇒ 放宽本圈对撞/探针类环节的联网；
· 全部经 `ControlSurface`（可追溯 + 可控）；**默认零行为差**
  （第一圈没有 prev ⇒ 不动；增量 > 0 ⇒ 不动）。

## 两处改动
① `_before_round`：记基线 + 判增量 + 调整；
② `_finalize_layer_common`：存 `self._last_view`（供 `trace` 落笔 —— 圈级
   调整发生在**本圈还没跑**时，没有 view 可挂，只能挂上一层的）。
"""
import io
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "元DGTF-V1.23.37.py"
SM = HERE / "smoke_test.py"
MU = HERE / "_mut_v12332.py"
DO_SM = os.environ.get("WB_SM") == "1"

# ── ① `_before_round` 里加圈级心跳 ──
OLD_BR = '''        # ★ [联网全接] 逐圈刷新上下文：环节里任何一次 `LLM.call` 都能据此
        #   知道「现在在哪一层哪一圈」（Gate 的 per_stage_round 配额靠它）。
        try:
            _llm_ctx_set(entry=str(entry), round=int(layer_no or 0))
        except Exception:
            pass'''
NEW_BR = '''        # ★ [联网全接] 逐圈刷新上下文：环节里任何一次 `LLM.call` 都能据此
        #   知道「现在在哪一层哪一圈」（Gate 的 per_stage_round 配额靠它）。
        try:
            _llm_ctx_set(entry=str(entry), round=int(layer_no or 0))
        except Exception:
            pass
        # ★ [圈级心跳] 用「**池增量**」当**上一圈产出**的代理 —— 只改这一处：
        #   本函数每圈都调，所以在这里记「本圈开始的基线」，
        #   下一圈开始时的增量 = 上一圈产出（新增的 & 与线头）。
        #   ★ 为什么不用 view：`view` 每圈新建，要跨圈就得在两个圈循环里
        #     各存一次 —— 那正是本项目反复踩的「同一条逻辑两处各写一份」。
        #   ★ 零行为差：第一圈没有基线 ⇒ 不动；增量为正 ⇒ 不动。
        try:
            _n_now = int(len(getattr(pool, "amps", None) or [])
                         + len(getattr(pool, "threads", None) or []))
            _n_prev = getattr(self, "_tick_prev_n", None)
            if _n_prev is not None and int(layer_no or 0) > 1:
                _grew = _n_now - int(_n_prev)
                if _grew <= 0:
                    _done = []
                    for _st in (self._TICK_WEB_RELAX or ()):
                        if self._control.write(
                                "web.allow.%s" % _st, True,
                                why="圈级心跳：第 %d 圈池零增量（复述/停滞）"
                                    "⇒ 放宽 %s 联网" % (int(layer_no) - 1, _st),
                                trace_ref="tick_round:%s:%d:%s"
                                          % (entry, layer_no, _st)):
                            _done.append(_st)
                    if _done:
                        try:
                            _trace_note(getattr(self, "_last_view", None),
                                        "tune",
                                        what="圈级心跳：放宽联网",
                                        layer=str(entry),
                                        round=int(layer_no),
                                        why="上一圈池零增量（新增 0 条）",
                                        adjusted=_done)
                        except Exception:
                            pass
            self._tick_prev_n = _n_now
        except Exception:
            pass'''

# ── ② `_finalize_layer_common` 存 view（供 trace 落笔）──
#   ★ 注意：读数行走的是 `logger.info`（P1 已从 `self.vp` 改过来）——
#     锚点必须对**当前**代码，不能凭记忆。
OLD_FIN = '''        try:
            logger.info(_readings_line(entry, view))
        except Exception:
            pass'''
NEW_FIN = '''        try:
            logger.info(_readings_line(entry, view))
        except Exception:
            pass
        # ★ [圈级心跳] 存一份 view 供 trace 落笔：圈级调整发生在**本圈还没跑**时
        #   （`_before_round`），那时没有 view 可挂 ⇒ 用**上一层**的（诚实标注层号）。
        try:
            self._last_view = view
        except Exception:
            pass'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    # ★ 幂等：① 可能已在上一次运行里替换成功
    if "_tick_prev_n" in s:
        print("① 圈级心跳已存在（跳过）")
    else:
        n = s.count(OLD_BR)
        assert n == 1, "① 锚点命中 %d 次（应为 1）" % n
        s = s.replace(OLD_BR, NEW_BR, 1)
    n2 = s.count(OLD_FIN)
    assert n2 == 1, "② 锚点命中 %d 次（应为 1）" % n2
    s = s.replace(OLD_FIN, NEW_FIN, 1)
    assert "_tick_prev_n" in s and "self._last_view = view" in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 副本：圈级心跳已加；行数 %d" % out.count(b"\n"))
    if not DO_SM:
        print("⏸ 判据与变异体：等验证跑完（WB_SM=1 再执行）")


main()
