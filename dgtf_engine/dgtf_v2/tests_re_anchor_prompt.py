# -*- coding: utf-8 -*-
"""re_anchor few-shot 判据（V2.2.14）：锚点重述的 prompt 形态。

为什么需要这条判据
------------------
本地 0.5B 底座在**旧 prompt**（只有模板行）下不出 JSON——纯文本复述即
EOS ⇒ touched/untouched 恒空 ⇒ aspect_units 永不登记 ⇒ 修行层目标读数
「零存量（未测出）」。V2.2.14 修法是 few-shot：prompt 里带两个完整示例。

★ 另一个实测陷阱（本判据的负向检查）：**模板行与示例不能共存**——
  共存时弱模型会照抄模板占位符「≤80字一句话」（2/2 次复现），
  占位符不在 _ANCHOR_PLACEHOLDERS 里 ⇒ 垃圾 anchor 直接进产物。
  ⇒ few-shot 版 prompt 必须**没有**模板行。

有牙设计：引擎文件动态发现（最高版）；prompt 块抽不到 ⇒ 红；
块不在 _re_anchor 里（锚到别的函数）⇒ 红；自带变异体。
零 torch / 零 API：引擎文件只当文本读。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def find_engine_file() -> Path:
    eng_dir = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
    best, best_ver = None, (0, 0, 0)
    for f in eng_dir.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)\.py$", f.name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.groups())
        if ver > best_ver:
            best, best_ver = f, ver
    return best


def extract_re_anchor_system(src: str):
    """抽出『你是【锚点重述者】』所在的 system = (...) 块文本。"""
    i = src.find("你是【锚点重述者】")
    if i < 0:
        return None
    start = src.rfind("system = (", 0, i)
    if start < 0:
        return None
    depth, j = 0, start + len("system = (") - 1
    while j < len(src):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
        j += 1
    return None


def check_prompt(block: str):
    """返回缺失项列表（空 = 合格）。纯函数，变异体也走它。"""
    miss = []
    if "示例1" not in block or "示例2" not in block:
        miss.append("缺 few-shot 示例（底座无示例不出 JSON）")
    if "≤80字一句话" in block:
        miss.append("模板行未去掉（弱模型照抄占位符，2/2 复现）")
    if '"touched"' not in block or '"untouched"' not in block:
        miss.append("示例不带 touched/untouched 键（抄不出目标 schema）")
    return miss


def main() -> int:
    # ── A 变异体（判据自己有牙）─────────────────────────
    ck("A1 变异体：无示例的旧 prompt 被报缺",
       check_prompt('"严格 JSON：\n{"anchor":"x","touched":[],"untouched":[]}\n')
       != [])
    ck("A2 变异体：带模板占位符的 prompt 被报缺",
       check_prompt("示例1 示例2 \"touched\" \"untouched\" ≤80字一句话")
       == ["模板行未去掉（弱模型照抄占位符，2/2 复现）"])
    ck("A3 变异体：合格 prompt 不误报",
       check_prompt("示例1 输入：x 输出：{\"anchor\":\"a\",\"touched\":[\"t\"],"
                    "\"untouched\":[\"u\"]} 示例2 输入：y") == [])

    # ── B 真实引擎 ────────────────────────────────────
    eng = find_engine_file()
    ck("B1 引擎文件动态发现成功（最高版）",
       eng is not None and eng.is_file(), str(eng))
    if eng is None:
        print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
        return 1
    src = eng.read_text(encoding="utf-8", errors="replace")
    block = extract_re_anchor_system(src)
    ck("B2 re_anchor 的 system 块抽取成功（抽不到 = 判据没牙）",
       block is not None)
    if block is None:
        print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
        return 1
    miss = check_prompt(block)
    ck("B3 ★ prompt 形态合格（有示例、无模板行、schema 键齐）",
       not miss, miss)
    ra_def = src.find("def _re_anchor")
    blk_at = src.find("你是【锚点重述者】")
    ck("B4 块确实在 _re_anchor 方法内（不是锚到别处）",
       0 < ra_def < blk_at, f"def@{ra_def} block@{blk_at}")

    print("引擎文件: %s" % eng.name)
    print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
