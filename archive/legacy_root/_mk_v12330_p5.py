#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 5 阶段：修两个探针抓出的真 bug。

① 问项命中判据过严：原来要求「问项首 2 字 + 整段子串」，导致
   **相关文本也判 0 覆盖**（探针 T2 全红）。改成**分词重叠**：
   问项去引导词 → 2 字滑窗 gram → 该问项 gram 命中率 ≥ 0.5 即算命中。
   ★ 这是判据口径错（判据读的东西不对），不是「阈值调松」。
② `duty_short` 被收尾清洗覆盖：`view.quality_flags = _keep_selfcheck_flags(...)`
   在署名块之后**整表覆盖** ⇒ 标记静默丢失。在覆盖点之后按读数补回
   （本项目「静默丢失」老坑）。
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


OLD_HIT = '''    def _hit(asp_text, seg, require):
        if asp_text in seg:
            return True
        if require not in seg:
            return False
        try:
            return float(_sim3(asp_text, seg, corpus=corpus)) >= hit_sim
        except Exception:
            return False
'''
NEW_HIT = '''    def _grams(t):
        """问项核心 gram：去引导词后取 2 字滑窗（中文词面命中的最小单位）。"""
        _t = str(t or "")
        for _w in _DUTY_CORE_LEAD:
            if _t.startswith(_w):
                _t = _t[len(_w):]
                break
        for _w in _DUTY_FOLLOWUP_LEAD:
            if _t.startswith(_w):
                _t = _t[len(_w):]
                break
        _t = _t.strip("的了吗呢吧")
        if len(_t) <= 2:
            return [_t] if _t else []
        return [_t[_i:_i + 2] for _i in range(len(_t) - 1)]

    def _hit(asp_text, seg):
        """命中判据：gram 命中率 ≥ 0.5（或 sim3 兜底）。

        ★ 旧口径要求「问项首 2 字 + 整段子串」，实测**相关文本也判 0**
          （探针 T2 全红）—— 判据读错了东西。改用 gram 重叠：
          问项是长短语、交付面是自然句，词面必然只有部分重合。
        """
        if str(asp_text) in seg:
            return True
        _g = _grams(asp_text)
        if not _g:
            return False
        _n_hit = sum(1 for x in _g if x and x in seg)
        if _n_hit / float(len(_g)) >= 0.5:
            return True
        # sim3 兜底（换说法命中）；短文本噪声大 ⇒ 只在够长时用
        if len(str(asp_text)) >= 6 and len(seg) >= 12:
            try:
                return float(_sim3(str(asp_text), seg,
                                   corpus=corpus)) >= hit_sim
            except Exception:
                return False
        return False
'''
OLD_C = '''    _tw = sum(float(a.get("weight", 0.3)) for a in _as) or 0.0
    _hw, missing = 0.0, []
    for a in _as:
        t = str(a.get("text", ""))
        if t and _hit(t, _d, t[:2]):
            _hw += float(a.get("weight", 0.3))
        elif str(a.get("kind", "core")) == "core":
            missing.append(t)
    C = (_hw / _tw) if _tw else 0.0'''
NEW_C = '''    _tw = sum(float(a.get("weight", 0.3)) for a in _as) or 0.0
    _hw, missing = 0.0, []
    for a in _as:
        t = str(a.get("text", ""))
        if t and _hit(t, _d):
            _hw += float(a.get("weight", 0.3))
        elif str(a.get("kind", "core")) == "core":
            missing.append(t)
    C = (_hw / _tw) if _tw else 0.0'''
OLD_R = '''    for sg in segs:
        if any(str(a.get("text", "")) and str(a["text"]) in sg for a in _as):
            direct += 1'''
NEW_R = '''    for sg in segs:
        # ★ 与 C 同口径（都走 `_hit`）：两处口径分叉会让「覆盖高、相关低」
        #   变成算法噪声而不是事实。
        if any(_hit(str(a.get("text", "")), sg) for a in _as):
            direct += 1'''


def main():
    s = _load()
    s = rep(s, OLD_HIT, NEW_HIT, "命中判据（gram 重叠）")
    s = rep(s, OLD_C, NEW_C, "C 计算调用点")
    s = rep(s, OLD_R, NEW_R, "R 计算调用点")

    # ② duty_short 补回（紧跟收尾清洗之后、算 verdict 之前）
    _k2 = s.index("        view.quality_verdict = _dg._quality_verdict(")
    s = (s[:_k2]
         + "        # ★ [LDG] 职责未尽是**读数**，不许被收尾清洗整表覆盖吞掉\n"
           "        #   （本项目「静默丢失」老坑：改了、判据却是绿的）。\n"
           "        if (view.duty or {}).get(\"short\") \\\n"
           "                and \"duty_short\" not in view.quality_flags:\n"
           "            view.quality_flags.append(\"duty_short\")\n"
         + s[_k2:])

    _save(s)
    print("OK 第 5 阶段（命中口径 + duty_short 补回）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "gram 命中率 ≥ 0.5" in s2
    assert s2.count("_hit(str(a.get(\"text\", \"\")), sg)") == 1
    assert s2.count('view.quality_flags.append("duty_short")') == 2
    print("复读校验通过")


if __name__ == "__main__":
    main()
