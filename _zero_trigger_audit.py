# -*- coding: utf-8 -*-
"""
零触发机制审计（长期任务 2）——“哪些机制从来没触发过”。

数据源：`outputs/*.md`（254 份真跑产物）。

★ 口径铁律（本项目反复踩的坑）：
  必须区分「**有这个渲染点，且值为 0**」和「**这份产物压根没这个渲染点**」。
  后者标 NA 不标 0 —— 否则"零触发占比"会把"没写"当成"触发了 0 次"，
  度量出来的对象是错的。所以每个机制都记三件事：
      have   = 有多少份产物能找到这个渲染点
      zeros  = 其中值为 0 的份数
      total  = 触发总次数
  零触发占比 = zeros / have（分母**不含** NA）。

用法：
  python _zero_trigger_audit.py            # 全部
  python _zero_trigger_audit.py --detail   # 附带逐份明细
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTS = HERE / "outputs"

# 机制名 -> (正则, 取第几组)
#   ★ 正则要能匹配"渲染点在但值为 0"的情形，不能只匹配"有内容"
PATTERNS = {
    "修行悬置": r"(\d+)\s*条修行悬置",
    "对撞张力悬置": r"(\d+)\s*条对撞张力悬置",
    "不可判定条目": r"不可判定条目\*\*：(\d+)\s*条",
    "无池内追溯的und": r"其中\s*(\d+)\s*条无池内追溯",
    "池级留痕": r"池级留痕\*\*：(\d+)\s*条",
    "自省回流未生效": r"自省回流未生效\s*(\d+)",
    "自省反馈": r"自省反馈\s*(\d+)",
    "风险登记": r"###\s*三、风险登记表\s*\n\s*\n?\s*（无登记风险）",
    "待办条目": r"^-\s*\[\s*\]\s*子问题",
    "答出的子问题": r"答出的子问题\*\*：([0-9、\d]+)",
}

# 这些机制是"计数型"：正则要抓数字
COUNTED = {"修行悬置", "对撞张力悬置", "不可判定条目",
           "无池内追溯的und", "池级留痕", "自省回流未生效",
           "自省反馈"}
# 这些是"有无型"：匹配到 = 触发了（风险登记匹配到的是"无登记"，要反着看）
NEGATIVE = {"风险登记"}      # 匹配到「（无登记风险）」= 没触发
# 这些是"逐条型"：数出现次数
LISTED = {"待办条目"}


def scan(txt: str) -> dict:
    r = {}
    for name, pat in PATTERNS.items():
        if name in COUNTED:
            m = re.search(pat, txt)
            r[name] = int(m.group(1)) if m else None
        elif name in NEGATIVE:
            hit = re.search(pat, txt) is not None
            # 「三、风险登记表」这个渲染点是否存在
            has = re.search(r"###\s*三、风险登记表", txt) is not None
            r[name] = (0 if hit else 1) if has else None
        elif name in LISTED:
            has = re.search(r"###\s*二、待办清单", txt) is not None
            r[name] = len(re.findall(pat, txt, re.M)) if has else None
        else:
            m = re.search(pat, txt)
            r[name] = len(m.group(1).split("、")) if m else None
    # 三态判决一致率
    m = re.search(r"三态判决一致率\*\*：([\d]+)/([\d]+)", txt)
    r["_一致性分子"] = int(m.group(1)) if m else None
    r["_一致性分母"] = int(m.group(2)) if m else None
    r["_外部锚点接入"] = 1 if re.search(
        r"\*\*外部锚点\*\*：已接入", txt) else (
        0 if re.search(r"\*\*外部锚点\*\*：无", txt) else None)
    return r


def main() -> int:
    files = sorted(OUTS.glob("*.md"))
    if not files:
        print("outputs/ 下没有 md")
        return 1
    print(f"扫描 {len(files)} 份产物\n")

    rows = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rows.append((f.name, scan(txt)))

    names = list(PATTERNS.keys()) + ["_外部锚点接入"]
    print("| 机制 | 有渲染点 | 零触发 | 零触发占比 | 触发总数 | 最大 | 均值 |")
    print("|---|---|---|---|---|---|---|")
    summary = {}
    for n in names:
        vals = [r.get(n) for _, r in rows if r.get(n) is not None]
        have = len(vals)
        zeros = sum(1 for v in vals if v == 0)
        total = sum(vals)
        mx = max(vals) if vals else None
        avg = round(total / have, 2) if have else None
        summary[n] = {"have": have, "zeros": zeros, "total": total,
                      "max": mx, "avg": avg}
        pct = f"{zeros / have * 100:.1f}%" if have else "—"
        flag = " ★" if have and zeros == have else ""
        print(f"| {n} | {have} | {zeros} | {pct} | {total} | "
              f"{mx if mx is not None else '—'} | "
              f"{avg if avg is not None else '—'} |{flag}")

    # 一致性
    cs = [(r["_一致性分子"], r["_一致性分母"]) for _, r in rows
          if r.get("_一致性分母") is not None]
    if cs:
        lows = sum(1 for a, b in cs if b and a / b < 0.33)
        print(f"\n三态判决一致率：{len(cs)} 份有读数，"
              f"低于 33%（分母不可当判据）的有 {lows} 份")

    print("\n★ = **全部**跑动都是 0 —— 这类机制要么真的没用，"
          "要么阈值/接线有问题，是要砍或改阈值的头号候选。")
    print("注意：`有渲染点` < 产物总数说明该标记是某个版本才加的，"
          "早期产物没有它（标 NA 而非 0）。")

    if "--detail" in sys.argv:
        print("\n### 逐份明细（前 20）\n")
        print("| 产物 | " + " | ".join(names) + " |")
        print("|---|" + "---|" * len(names))
        for fn, r in rows[:20]:
            print(f"| {fn[:30]} | " + " | ".join(
                "NA" if r.get(n) is None else str(r.get(n))
                for n in names) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
