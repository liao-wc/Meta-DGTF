#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P2：第三批接线（读数/结构 + 两条 opt-in 机制）。"""
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


def main():
    s = _load()

    # ① View 三字段
    s = rep(s, "    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。",
            "    #: [发散三态 / 回滚指针] 收敛/停滞/发散 + 历史最佳圈的指针。\n"
            "    #:   ★ 指针只是**指向**：被回滚掉的圈不删（红线「失败留痕」）。\n"
            "    divergence: dict = field(default_factory=dict)\n"
            "    best_round: Optional[int] = None\n"
            "    #: [anytime-valid] 均值下界（随时看随时停仍然有效的判据）。\n"
            "    anytime: dict = field(default_factory=dict)\n"
            "    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。",
            "View 三字段")

    # ② _layer_csd_now 里补发散 + 回滚指针 + anytime 下界
    s = rep(s, '''        view.csd = d
        return d''',
            '''        view.csd = d
        # ★ [发散三态 + 回滚指针] 用同一序列判三态，并记下历史最佳圈的**指针**。
        #   依据 LoopGain：发散时该回滚到历史最佳 —— 但本项目**只给指针**，
        #   被回滚掉的圈照旧全部保留（红线「失败留痕」）。
        try:
            view.divergence = divergence_state(_s_new) or {}
            view.best_round = best_round_index(_s_new, higher_is_better=True)
        except Exception:
            view.divergence = {}
        # ★ [anytime-valid] 「结构仍在长」的 0/1 序列 → 均值下界。
        #   口径：下界 < 0.5 ⇒ 「仍在长」不再被证据支持 ⇒ 可停（opt-in）。
        try:
            _seq = [1 if x > 0 else 0 for x in _s_new]
            view.anytime = stitched_hoeffding_lower(
                _seq, delta=float(getattr(self, "_anytime_delta", 0.05) or 0.05)) or {}
        except Exception:
            view.anytime = {}
        return d''',
            "发散+指针+anytime")

    # ③ 层明细渲染：发散三态 / 历史最佳 / anytime 下界
    s = rep(s, '''            try:
                _cd = (view.csd or {}).get("new_amps")
                if _cd:
                    lines += [f"【早期预警】{csd_line(_cd)}"]
            except Exception:
                pass''',
            '''            try:
                _cd = (view.csd or {}).get("new_amps")
                if _cd:
                    lines += [f"【早期预警】{csd_line(_cd)}"]
            except Exception:
                pass
            # ★ [发散三态 + 回滚指针]（LoopGain）：三态 + 历史最佳圈的**指针**。
            try:
                _dv = view.divergence or {}
                if _dv:
                    _bp = ("第 %s 圈" % view.best_round
                           if view.best_round else "—")
                    lines += [f"【发散三态】{_dv.get('state')}"
                              f"（前半方差 {_dv.get('var_first')} → "
                              f"后半 {_dv.get('var_last')}，AC1 {_dv.get('ac1')}）"
                              f"｜历史最佳圈（回滚指针）：{_bp}"
                              f"　★ 只给指针，被回滚的圈不删"]
            except Exception:
                pass
            # ★ [anytime-valid] 均值下界（随时看随时停仍然有效）。
            try:
                _at = view.anytime or {}
                if _at.get("lower") is not None:
                    lines += [f"【anytime 下界】「仍在长」下界 "
                              f"{float(_at['lower']):.3f}"
                              f"（n={_at.get('n')}，δ={_at.get('delta')}）"
                              f"　★ 下界 < 0.5 才够说「不再长」"]
            except Exception:
                pass''',
            "层明细三行")

    # ④ anytime 停止判据（opt-in；默认 delta=0 ⇒ 不生效）
    s = rep(s, '''                      stall_is_sat: bool = False,
                      duty_streak: int = 0):''',
            '''                      stall_is_sat: bool = False,
                      duty_streak: int = 0,
                      anytime_ok: bool = False):''',
            "_stop_reasons 签名")
    s = rep(s, '''            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))''',
            '''            # ★ [anytime-valid 停止判据 · opt-in] 「结构仍在长」的下界已跌破
            #   0.5 ⇒ 在**随时看随时停仍然有效**的意义上可以说「不再长」。
            #   ★ 默认 `stop.anytime_alpha=0` ⇒ 该参数恒 False ⇒ 零行为差。
            if anytime_ok:
                reasons.append(
                    "结构增长已 anytime-valid 地判停（「仍在长」下界 < 0.5，"
                    "对任意停时有效）")
            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))''',
            "anytime 判据")

    # ⑤ 两个调用点：算 anytime_ok 并传入
    s = rep(s, '''            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view)
            stop_reasons: List[str] = []''',
            '''            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view)
            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。
            _any_ok = False
            try:
                _aa = float(getattr(self, "_anytime_delta", 0.0) or 0.0)
                if _aa > 0:
                    _any_ok = bool(anytime_majority_decided(
                        [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5)[0])
            except Exception:
                _any_ok = False
            stop_reasons: List[str] = []''',
            "串行调用点 anytime")
    s = rep(s, '''                view=view, idles=idles, diag=False,
                duty_streak=_duty_streak)''',
            '''                view=view, idles=idles, diag=False,
                duty_streak=_duty_streak, anytime_ok=_any_ok)''',
            "串行传参")

    s = rep(s, '''        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view)
        stop_reasons, state["idles"] = self._stop_reasons(''',
            '''        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view)
        _any_ok = False
        try:
            _aa = float(getattr(self, "_anytime_delta", 0.0) or 0.0)
            if _aa > 0:
                _any_ok = bool(anytime_majority_decided(
                    [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                     for r in (view.round_log or [])], delta=_aa, thr=0.5)[0])
        except Exception:
            _any_ok = False
        stop_reasons, state["idles"] = self._stop_reasons(''',
            "公共调用点 anytime")
    s = rep(s, '''            idles=state["idles"], defer_vp=True,
            duty_streak=_duty_streak)''',
            '''            idles=state["idles"], defer_vp=True,
            duty_streak=_duty_streak, anytime_ok=_any_ok)''',
            "公共传参")

    # ⑥ 实例阈值：读 stop.anytime_alpha（默认 0 = 关）
    s = rep(s, "        self._duty_carry: List[str] = []",
            "        self._duty_carry: List[str] = []\n"
            "        # [anytime-valid 可配] δ（0 = 关；>0 才启用该停止判据）。\n"
            "        try:\n"
            "            self._anytime_delta = float(\n"
            "                (config.get(\"stop\") or {}).get(\"anytime_alpha\", 0.0) or 0.0)\n"
            "        except (TypeError, ValueError):\n"
            "            self._anytime_delta = 0.0",
            "anytime 阈值")

    # ⑦ 裁决维度拆分（捕获处加 aspect）
    s = rep(s, "            view.adjudications.append({",
            "            view.adjudications.append({\n"
            "                # ★ [裁决维度拆分] 依据：多评委框架 + 红线「自省是另一个\n"
            "                #   视角，不可合并」⇒ 裁决依据**拆维留痕**，不合成一个 how。\n"
            "                \"aspect\": adjudication_aspect(\n"
            "                    str(data.get(\"tension\", \"\")), str(doc_how)),",
            "裁决维度")

    # ⑧ 锚点：离线解析验证 + 内部批判提示
    s = rep(s, "        _ar = self._anchor_report_for_pack(results)",
            "        _ar = self._anchor_report_for_pack(results)\n"
            "        # ★ [锚点 ⑤⑥] 离线解析验证（refchecker 思路）+ 内部批判提示\n"
            "        #   （史学 Quellenkritik：外部批判已有 tier，内部批判此前缺失）。\n"
            "        try:\n"
            "            if isinstance(_ar, dict):\n"
            "                for _it in (_ar.get(\"items\") or []):\n"
            "                    _u = str(_it.get(\"url\") or \"\")\n"
            "                    _it[\"offline_check\"] = anchor_offline_check(_u)\n"
            "                    _it[\"interest_hint\"] = anchor_interest_hint(_u)\n"
            "        except Exception:\n"
            "            pass",
            "锚点离线+内部批判")

    _save(s)
    print("OK P2（第三批接线）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("anytime_ok=anytime_ok") == 0
    assert s2.count("anytime_ok=_any_ok") == 2
    assert "def divergence_state(" in s2 and "offline_check" in s2
    assert "adjudication_aspect(" in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
