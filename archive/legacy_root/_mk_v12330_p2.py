#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 2 阶段：LDG 接线（停止/收敛处）。

· 新方法 `_layer_duty_now` / `_duty_marginal_streak`。
· 新停止判据「职责增益收敛」：ΔS<τ 连续 patience 圈 ⇒ 层可**因推不动而停**
  （直治「体力耗尽」截断）。`duty_streak` 默认 0 ⇒ 老调用点零行为差。
· 收尾**署名纪律**：职责未尽 ⇒ 不许只写「自然安住/自然停止」。
· 补救定向注入：缺失 core 问项进 `self._duty_carry`，由后续层 carry 带入。
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


DUTY_METHODS = '''    def _layer_duty_now(self, entry: str, view) -> dict:
        """[LDG] 在**停止/收敛处**算该层职责读数并记账（读数不是分数）。

        · 交付面 = `collision` + `decidable_product` 正文 + `meta_closure` 正文
          —— 只算**这层拿出来给问题的东西**，不算内部候选/属性堆。
        · 逐圈结果进 `view.duty_trace`（边际增益判据读它）。
        """
        if view is None:
            return {}
        _dp = view.decidable_product or {}
        _mc = view.meta_closure or {}
        _parts = [str(view.collision or "")]
        for _k in ("answer", "conclusion", "summary", "direct"):
            if _dp.get(_k):
                _parts.append(str(_dp.get(_k)))
        for _k in ("text", "reason", "summary", "closure"):
            if _mc.get(_k):
                _parts.append(str(_mc.get(_k)))
        deliver = "\\n".join(p for p in _parts if p)
        d = duty_of_layer(entry, self._question, deliver,
                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),
                          corpus=getattr(self, "_sim_corpus", None))
        d["round"] = int(getattr(view, "rounds_run", 0) or 0)
        try:
            view.duty_trace.append({"round": d["round"], "S": d["S"],
                                    "C": d["C"], "R": d["R"]})
        except Exception:
            pass
        view.duty = d
        return d

    def _duty_marginal_streak(self, view, state: dict) -> int:
        """[LDG] 连续多少圈边际职责增益 < τ（读 `view.duty_trace`）。

        ★ 依据：EMNLP'25 自纠收敛 —— 每轮只削掉剩余误差的固定比例 ⇒
          边际增益递减即「推不动了」。工程判据 = 连续 patience 次 Δ<τ。
        """
        _tr = list(getattr(view, "duty_trace", None) or [])
        if len(_tr) < 2:
            state["duty_stall"] = 0
            return 0
        _last = float(_tr[-1].get("S", 0.0))
        _prev = float(_tr[-2].get("S", 0.0))
        if abs(_last - _prev) < float(_DUTY_TAU):
            state["duty_stall"] = int(state.get("duty_stall", 0) or 0) + 1
        else:
            state["duty_stall"] = 0
        return int(state.get("duty_stall", 0) or 0)

'''


def main():
    s = _load()

    # 1) 新方法：插在 _stop_reasons 之前
    anchor = "    def _stop_reasons(self, *, entry, layer_no, rounds_n,"
    s = rep(s, anchor, DUTY_METHODS + anchor, "LDG 方法插入")

    # 2) _stop_reasons 签名加 duty_streak（默认 0 ⇒ 零行为差）
    old_sig = '''                      stall_is_sat: bool = False):'''
    new_sig = '''                      stall_is_sat: bool = False,
                      duty_streak: int = 0):'''
    s = rep(s, old_sig, new_sig, "_stop_reasons 签名")

    # 3) 新停止判据：插在「空转/自然安住」收尾之前
    old_tail = '''            if _rest:
                reasons.append(_rest)
            if not reasons and view.idle:
                idles += 1'''
    new_tail = '''            if _rest:
                reasons.append(_rest)
            # ★ [LDG 新停止判据] 职责增益收敛：连续 patience 圈
            #   ΔS < τ ⇒ 推不动了，允许停（哪怕没有别的判据成立）。
            #   ★ 与「自然安住」的区别：安住说的是**悬置决定稳**，
            #     这条说的是**对问题的贡献不再增长** —— 两件事分开报。
            if int(duty_streak or 0) >= int(_DUTY_PATIENCE):
                reasons.append(
                    f"职责增益收敛（连续 {int(duty_streak)} 圈 "
                    f"ΔS<{_DUTY_TAU}，对问题的贡献不再增长）")
            if not reasons and view.idle:
                idles += 1'''
    s = rep(s, old_tail, new_tail, "职责收敛停止判据")

    # 4) 串行调用点：算 duty + 传 duty_streak
    old_c1 = '''            stop_reasons: List[str] = []
            _mi_from_view = getattr(view, "_meta_idle_streak", 0)'''
    new_c1 = '''            # ★ [LDG] 停止/收敛处先算职责读数（交付面 vs 问项），
            #   再把「连续推不动几圈」喂给停止判据。
            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view, {
                "duty_stall": state.get("duty_stall", 0)})
            state["duty_stall"] = _duty_streak
            stop_reasons: List[str] = []
            _mi_from_view = getattr(view, "_meta_idle_streak", 0)'''
    s = rep(s, old_c1, new_c1, "串行调用点")

    old_c1b = '''                prev_product=prev_product,
                view=view, idles=idles, diag=False)'''
    new_c1b = '''                prev_product=prev_product,
                view=view, idles=idles, diag=False,
                duty_streak=_duty_streak)'''
    s = rep(s, old_c1b, new_c1b, "串行调用点传参")

    # 5) 公共通道调用点（_b_check_stop）
    old_c2 = '''        stop_reasons, state["idles"] = self._stop_reasons(
            entry=entry, layer_no=r, rounds_n=state["rounds_n"],'''
    new_c2 = '''        # ★ [LDG] 同上：先算职责读数，再把边际增益停滞圈数喂进判据。
        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view, state)
        stop_reasons, state["idles"] = self._stop_reasons(
            entry=entry, layer_no=r, rounds_n=state["rounds_n"],'''
    s = rep(s, old_c2, new_c2, "公共调用点")

    old_c2b = '''            prev_product=state["prev_product"], view=view,
            idles=state["idles"], defer_vp=True)'''
    new_c2b = '''            prev_product=state["prev_product"], view=view,
            idles=state["idles"], defer_vp=True,
            duty_streak=_duty_streak)'''
    s = rep(s, old_c2b, new_c2b, "公共调用点传参")

    # 6) 收尾：最终 duty + 署名纪律 + 补救注入
    old_fin = '''        if view is None:
            return
        r_actual = int(state.get("r") or 0)

        if not view.stop_reason:'''
    new_fin = '''        if view is None:
            return
        r_actual = int(state.get("r") or 0)

        # ★ [LDG 署名纪律] 最终职责读数 + **不许把职责未尽说成自然停止**。
        #   分寸：只改**署名**（措辞），不删任何内容 —— 红线「悬置不打分」
        #   的延续：职责度是读数，不是分数；但「说自己自然安住了」如果
        #   与读数矛盾，那就是**不诚实**，必须改。
        try:
            _duty_fin = self._layer_duty_now(entry, view)
        except Exception:
            _duty_fin = {}
        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)
            _old_stop = str(view.stop_reason or "")
            if "职责未尽" not in _old_stop:
                view.stop_reason = (
                    (_old_stop + "\\n" if _old_stop else "")
                    + f"  职责未尽：{_line}")
                view.quality_flags.append("duty_short")
            # 补救定向注入：缺失的 core 问项交给**后续层**的 carry 通道
            # （对应 NAACL'25「core 子问题喂回生成器」，本仓库不重跑本层，
            #  而是让下游带着「这几项没答」继续推 —— 不猜、不重跑、留痕）。
            try:
                _dc = getattr(self, "_duty_carry", None)
                if _dc is None:
                    _dc = []
                    self._duty_carry = _dc
                for _m in _miss:
                    if _m and _m not in _dc:
                        _dc.append(_m)
            except Exception:
                pass
            self.vp(f"   ⚖ 职责未尽（{_line}）")

        if not view.stop_reason:'''
    s = rep(s, old_fin, new_fin, "收尾署名纪律")

    _save(s)
    print("OK 第 2 阶段（LDG 接线）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("def _layer_duty_now(self, entry: str, view) -> dict:") == 1
    assert s2.count("duty_streak=_duty_streak") == 2
    assert s2.count("职责增益收敛") == 1
    assert s2.count("职责未尽：") == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
