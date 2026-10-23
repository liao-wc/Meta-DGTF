#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 6 阶段：修署名块**时序**（冒烟 [走满] 抓出的真 bug）。

问题：署名纪律块跑在「体力耗尽」块**之前** ⇒ 当 `view.stop_reason` 尚空时
先被写上「职责未尽」，随后走满块见非空即跳过 ⇒ **走满文案被顶掉**
（「有推迟时如实报出」这条判据当场判红）。

通则：**读数可以早算，署名必须晚写** —— 谁负责写那句话，谁就必须在
所有「写这句话的人」都跑完之后再动。修法：把署名块拆两半：
  · 前半（原位）：只算读数（`_duty_fin`），不碰 stop_reason；
  · 后半（挪到「体力耗尽」块之后）：改署名 + 留痕 + carry 注入。
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


OLD_BLOCK = '''        # ★ [LDG 署名纪律] 最终职责读数 + **不许把职责未尽说成自然停止**。
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

'''

NEW_HEAD = '''        # ★ [LDG] 最终职责读数先算出来（**只算不写**：署名必须等其他
        #   写 stop_reason 的人跑完再动 —— 冒烟 [走满] 抓出的时序 bug）。
        try:
            _duty_fin = self._layer_duty_now(entry, view)
        except Exception:
            _duty_fin = {}

'''

NEW_TAIL = '''
        # ★ [LDG 署名纪律] **不许把职责未尽说成自然停止**。
        #   分寸：只改**署名**（追加一句），不删任何内容 —— 红线「悬置
        #   不打分」的延续：职责度是读数不是分数；但「说自己自然安住了」
        #   若与读数矛盾，那就是**不诚实**，必须改。
        #   ★ 时序：必须在「体力耗尽 / 未生质量」等**所有**写 stop_reason
        #     的块之后（否则会把它们顶掉）。
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
            # （对应 NAACL'25「core 子问题喂回生成器」；本仓库不重跑本层，
            #  只让下游带着「这几项没答」继续推 —— 不猜、不重跑、留痕）。
            try:
                _dc = getattr(self, "_duty_carry", None)
                if _dc is None:
                    _dc = []
                    self._duty_carry = _dc
                _n_r = int((self.config.get("duty") or {})
                           .get("remedy_rounds", _DUTY_REMEDY_ROUNDS) or 0)
                if _n_r > 0:
                    for _m in _miss:
                        if _m and _m not in _dc:
                            _dc.append(_m)
            except Exception:
                pass
            self.vp(f"   ⚖ 职责未尽（{_line}）")

'''

# 挪位锚点：走满块 + 修行层未生质量块之后
ANCHOR = '''            self.vp(f"   ⏹ {view.stop_reason}")

        #     · action_incomplete —— **模型没按 schema 产出 actions**'''


def main():
    s = _load()
    s = rep(s, OLD_BLOCK, NEW_HEAD, "署名块拆前半")
    s = rep(s, ANCHOR,
            '            self.vp(f"   ⏹ {view.stop_reason}")\n'
            + NEW_TAIL
            + '\n        #     · action_incomplete —— **模型没按 schema 产出 actions**',
            "署名块后半挪位", expect=1)

    _save(s)
    print("OK 第 6 阶段（署名时序修正）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    _i_head = s2.index("最终职责读数先算出来")
    _i_tail = s2.index("★ [LDG 署名纪律]")
    _i_walk = s2.index("体力耗尽（{_cap} 圈走满")
    assert _i_head < _i_walk < _i_tail, "署名仍在走满块之前（时序未修）"
    print("时序校验：算读数 %d < 走满 %d < 署名 %d ✓" % (_i_head, _i_walk, _i_tail))


if __name__ == "__main__":
    main()
