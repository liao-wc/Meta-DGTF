# -*- coding: utf-8 -*-
"""补丁 B：四层目标读数**并列进层末判定**（Q2 授权：可改 duty 语义）。

用户授权「允许改 duty 语义」。做法取**最保守的一种**：
  · `duty_short` 判定**一个字不改**（历史读数可比）；
  · 只在其后**并列追加**一行「本层目标：<读数>」—— 两路信号分开报
    （红线「自省是另一个视角，不可合并」）。
  · 目标读数**没有值时**（`goal_now` 空）⇒ 不写这一行 ⇒ 零行为差。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)'''

NEW = '''        # ★ [四层目标 · 并列报] 本层**目标读数**单独一行（不改 duty 判定）。
        #   依据：四层定位不同（修行=挖尽 / 研究=收敛 / 对撞=融合 / 元=结晶），
        #   duty 只问「对原始问题的贡献」，问不出「这层自己的目标达没达成」。
        #   ★ 没有读数 ⇒ 不写（`goal_now` 为空时零行为差）。
        try:
            _gn = dict(getattr(view, "goal_now", None) or {})
            if _gn:
                _gk = _LG_KEYS.get(str(entry)) or ""
                _gv = _gn.get(_gk)
                if _gv is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f" % (
                        {"0": "修行·挖尽", "1": "研究·收敛",
                         "both": "对撞·融合", "all": "元·结晶"}.get(str(entry),
                                                                   str(entry)),
                        _gk, float(_gv))
        except Exception:
            pass

        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)'''

# View 增 goal_verdict 字段
ANCHOR_2 = '''    duty_verdict: str = ""'''
NEW_2 = '''    duty_verdict: str = ""
    # ★ [四层目标] 本层目标达成读数的**独立**判定行（与 duty_verdict 并列，
    #   不合并 —— 两路信号问的不是同一件事）。
    goal_verdict: str = ""'''

# 渲染处并列（12249 附近）
ANCHOR_3 = '''            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]'''
NEW_3 = '''            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]
            if getattr(view, "goal_verdict", ""):
                lines += [f"【目标判定】{view.goal_verdict}"]'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    for name, old in (("B1 层末并列", ANCHOR), ("B2 View 字段", ANCHOR_2),
                      ("B3 渲染", ANCHOR_3)):
        n = s.count(old)
        if n != 1:
            print("X %s 锚点命中 %d 次" % (name, n)); sys.exit(1)
    s = s.replace(ANCHOR, NEW, 1)
    s = s.replace(ANCHOR_2, NEW_2, 1)
    s = s.replace(ANCHOR_3, NEW_3, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 补丁 B 已打：3 处锚点各命中 1 次")


if __name__ == "__main__":
    main()
