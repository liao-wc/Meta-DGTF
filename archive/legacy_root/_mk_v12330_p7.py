#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 7 阶段：职责判定与停止理由**分开**（红线）。

冒烟 [走满] 判红点破的真问题：把「职责未尽」追加进 `view.stop_reason`
= 把**职责判定混进停止理由** —— 正撞红线「停止与清算分开」。

改法（同样满足「不许把职责未尽写成自然安住」，但不混两个概念）：
  · `view.stop_reason` **保持纯停止原因**（不追加、不覆盖）；
  · 新增 `view.duty_verdict`：职责判定行；
  · 渲染时把判定行**紧跟**在【螺旋停止】之后 ⇒ 任何读者看到「自然安住」
    的同一屏必定看到「职责未尽」，诚实性由**同屏**保证，而不是靠改写。
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


def main():
    s = _load()

    # 1) View 新字段
    s = rep(s, '''    #: 补救圈是否已用（每层最多用 `_DUTY_REMEDY_ROUNDS` 次）。''',
            '''    #: [LDG] 职责判定行 —— **与停止理由分开**（红线「停止与清算分开」）：
    #:   停止理由答「为什么停」，职责判定答「这层替问题干了什么」。
    #:   渲染时两者同屏，读者不会只看到「自然安住」。
    duty_verdict: str = ""
    #: 补救圈是否已用（每层最多用 `_DUTY_REMEDY_ROUNDS` 次）。''',
            "View duty_verdict 字段")

    # 2) 收尾：改写署名 → 写独立判定行
    old = '''        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)
            _old_stop = str(view.stop_reason or "")
            if "职责未尽" not in _old_stop:
                view.stop_reason = (
                    (_old_stop + "\\n" if _old_stop else "")
                    + f"  职责未尽：{_line}")
                view.quality_flags.append("duty_short")'''
    new = '''        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)
            # ★ 写**独立判定行**，不动 `stop_reason`（红线「停止与清算分开」）。
            view.duty_verdict = f"职责未尽：{_line}"
            if "duty_short" not in (view.quality_flags or []):
                view.quality_flags.append("duty_short")'''
    s = rep(s, old, new, "改写→独立判定行")

    # 3) 渲染：判定行紧跟【螺旋停止】
    old_r = '''            lines += ["", f"【螺旋停止】{view.stop_reason}"]'''
    new_r = '''            lines += ["", f"【螺旋停止】{view.stop_reason}"]
            # ★ [LDG] 职责判定**紧接着**停止理由渲染：读者不可能只看到
            #   「自然安住」而看不到「职责未尽」（诚实性由同屏保证）。
            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]'''
    s = rep(s, old_r, new_r, "判定行渲染")

    _save(s)
    print("OK 第 7 阶段（职责判定与停止理由分开）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert 'view.duty_verdict = f"职责未尽：{_line}"' in s2
    assert '【职责判定】{view.duty_verdict}' in s2
    assert s2.count('f"  职责未尽：{_line}"') == 0
    print("复读校验通过")


if __name__ == "__main__":
    main()
