# -*- coding: utf-8 -*-
"""
日志侧零触发审计 —— 引擎**会打**但真跑里**从没打出来过**的标记。

思路：源码里枚举引擎所有打印标记（emoji + 【】块），再到 251 份真跑
日志里数它出现过几份。**0 份 = 零触发**（接线没通，或条件永不成立）。

★ 与产物侧审计（`_zero_trigger_audit.py`）互补：
   产物记状态（终态字段），日志记过程（逐圈标记）。
   一个机制在产物里"0 条"可能是真的 0，也可能是压根没走到那步 ——
   只有日志侧能区分。

★ 口径：统计的是「出现在几份日志里」，不是「出现几次」。
   同一份日志里刷屏不等于机制健康；要的是**覆盖面**。
"""
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.75.py"


def load_src_marks() -> tuple:
    t = SRC.read_bytes().decode("utf-8").replace("\r\r\n", "\n")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # 只取**打印**相关的行（vp / logger / print / f.write），
    # 避免把 prompt 里的【】当成过程标记
    lines = [l for l in t.split("\n")
             if ("vp(" in l or "logger." in l or "print(" in l
                 or "f.write(" in l)]
    body = "\n".join(lines)
    emoji = set(re.findall(
        r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]", body))
    brackets = set(re.findall(r"【[^】\n]{1,24}】", body))
    return emoji, brackets


def main() -> int:
    logs = sorted(HERE.glob("*.log"))
    # 排除本脚本自己可能产生的日志
    logs = [p for p in logs if not p.name.startswith("_smoke")]
    if not logs:
        print("没有 log")
        return 1
    print(f"源码：{SRC.name}　日志：{len(logs)} 份\n")

    emoji, brackets = load_src_marks()
    # 逐份读，累计"出现在几份里"
    e_hit = Counter()
    b_hit = Counter()
    for i, p in enumerate(logs):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for e in emoji:
            if e in txt:
                e_hit[e] += 1
        for b in brackets:
            if b in txt:
                b_hit[b] += 1

    n = len(logs)

    def table(title: str, marks, hit: Counter) -> list:
        print(f"## {title}\n")
        print("| 标记 | 出现于几份日志 | 覆盖率 |")
        print("|---|---|---|")
        zero = []
        for m in sorted(marks, key=lambda x: -hit.get(x, 0)):
            c = hit.get(m, 0)
            print(f"| `{m}` | {c} | {c / n * 100:.1f}% |")
            if c == 0:
                zero.append(m)
        print()
        return zero

    z_e = table("emoji 标记", emoji, e_hit)
    z_b = table("【】块标记", brackets, b_hit)

    print("## 零触发（源码会打，但 " + str(n) + " 份真跑日志里一次都没出现）\n")
    if z_e:
        print("**emoji**：" + "、".join(f"`{m}`" for m in z_e))
    else:
        print("**emoji**：无（每个都至少出现过一次）")
    if z_b:
        print("\n**【】块**：")
        for m in z_b:
            print("  - " + m)
    else:
        print("\n**【】块**：无（每个都至少出现过一次）")

    print("\n★ 判读提醒：覆盖率低的标记**不一定**是坏机制 —— 可能它只在"
          "特定层/特定题型才成立（例如【螺旋停止】只在真停时打）。\n"
          "  要砍的是「条件写得永远不成立」的那类，判据是：源码里它的"
          "触发条件依赖的东西在真跑里从没出现过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
