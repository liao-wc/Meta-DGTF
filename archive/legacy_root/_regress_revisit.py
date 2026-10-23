# -*- coding: utf-8 -*-
"""[_regress_revisit.py] revisit_condition 白名单的全库回归。

用途：每次动 `_valid_revisit` / `_REVISIT_*` 之后跑一遍，防止"判据越改越窄、
真实数据被静默丢掉"。**只读**：读 outputs/*.md 抽真实条件，不写任何东西。

跑法：
    python _regress_revisit.py                 # 默认读 outputs/、比对当前版本
    python _regress_revisit.py --src X.py      # 指定版本文件
    python _regress_revisit.py --abs           # 附带"旧 6 条 pattern"对照

抽取口径（与产物渲染严格对齐，别凭印象写正则）：
    · `      回访条件：X`            （pool 段的延迟债务）
    · `原本的回访条件：X。最终状态：Y` （逐层明细里的延迟债务）
    · `（回访：X）`                  （View.shape_of）
    并在 `｜` / `。最终状态` / `（` / `；` / `，最终` 处截断，
    取 4~60 字、去重后的条目。
"""
from __future__ import annotations
import argparse
import glob
import importlib.util
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PATTERNS = (
    re.compile(r"^\s*回访条件：(.+)$"),
    re.compile(r"原本的回访条件：(.+)$"),
    re.compile(r"（回访：(.+?)）"),
)
CUT = re.compile(r"(｜|。最终状态|（|\(|；|;|，最终)")

# 旧口径（v1.21.62 初版的 6 条 pattern），只用于 --abs 对照
_OLD = (r"当.{1,30}(出现|发生|完成|解决|给出|成立|失败|超过|达到)",
        r"若.{1,30}(出现|发生|完成|解决|给出|成立|失败|超过|达到)",
        r"第\s*\d+\s*圈后", r"覆盖率.{0,10}(超过|达到|>|≥)",
        r"有.{1,20}证据(时|后)",
        r"[A-Za-z0-9]{2,}\s*(出现|变为|大于|小于|达到)")
_OLD_BAD = ("以后", "适当时机", "待定", "稍后", "再说", "看情况")


def load(src: str):
    spec = importlib.util.spec_from_file_location("dgtf_regress", str(HERE / src))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_regress"] = mod
    spec.loader.exec_module(mod)
    return mod


def harvest(out_dir: Path):
    seen, vals = set(), []
    for p in sorted(glob.glob(str(out_dir / "*.md"))):
        try:
            t = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for ln in t.replace("\r\n", "\n").split("\n"):
            for pat in PATTERNS:
                m = pat.search(ln)
                if not m:
                    continue
                v = CUT.split(m.group(1))[0].strip().strip("。，,；; ")
                if 4 <= len(v) <= 60 and v not in seen:
                    seen.add(v)
                    vals.append(v)
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.21.62.py")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--abs", action="store_true", help="附带旧口径对照")
    ap.add_argument("--show", type=int, default=20)
    a = ap.parse_args()

    mod = load(a.src)
    vals = harvest(HERE / a.out)
    n = len(vals)
    if not n:
        print("没有抽到任何 revisit_condition（outputs/ 空？）")
        return 1

    acc = [v for v in vals if mod._valid_revisit(v)]
    rej = [v for v in vals if not mod._valid_revisit(v)]
    rate = 100.0 * len(acc) / n

    print("源文件： %s" % a.src)
    print("样本：   %d 条真实 revisit_condition（从 %s/*.md 抽取）"
          % (n, a.out))
    print("放行：   %d 条（%.1f%%）" % (len(acc), rate))
    print("拦下：   %d 条（%.1f%%）" % (len(rej), 100.0 - rate))
    print("判据线： 放行率 ≥ 96%%  →  %s"
          % ("✅ 达标" if rate >= 96.0 else "❌ 未达标（记录拦下样本，别再放宽判据，交下一轮决定）"))

    if a.abs:
        def old_ok(c):
            c = c.strip()
            return (len(c) >= 4 and not any(b in c for b in _OLD_BAD)
                    and any(re.search(p, c) for p in _OLD))
        o = sum(1 for v in vals if old_ok(v))
        print("对照：   旧 6 条 pattern 口径放行 %d 条（%.1f%%）"
              % (o, 100.0 * o / n))

    if rej:
        print("\n被拦样本（前 %d 条，供人工判断是否真该拦）：" % a.show)
        for v in rej[:a.show]:
            print("   %s" % v)
    else:
        print("\n没有条被拦。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
