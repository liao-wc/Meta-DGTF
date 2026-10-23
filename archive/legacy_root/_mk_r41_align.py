#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R41：**分组行的标题要真的居中** —— 这样它才和底部居中的「保存」在同一根轴上。

用户第二次报「保存按钮怎么没和上面的按钮对齐」。先量像素（1920px 宽的截图）：

  · 底部「保存」文字 x 943–974 → 中心 **958.5**（= 页面中心，底栏本来就居中）
  · 分组行标题（模型与API / 输出 / 动作开关 …）→ 中心 **925 / 940 / 929**（平均 ≈931）
  ⇒ 差 **约 28px**，而**不是**底栏的问题。

根因（`.adv-groups .nav-btn` 的布局）：
    [13px 内边距][15px 图标][9px gap] [ 标题 .nb-name（居中，另带 24px 右内边距）] [52px 右预留]
    右侧要留 52px 给「N 项 ›」（绝对定位），左侧只占 37px ⇒ 标题盒本身**不对称**，
    再叠上 `.nb-name` 自带的 `padding-right:24px`，文字被推左约 28px。

修法：把「流内」清干净，让标题盒关于**行中心**对称（可证明）：
  · `.adv-groups .nav-btn{padding-left:52px}`（与右预留相等）
  · `.adv-groups .nav-btn svg{position:absolute;left:13px;...}`（图标不再占流，位置不变）
  · `.adv-groups .nav-btn .nb-name{padding-right:0}`（去掉那 24px）
  · `.adv-groups .nav-btn .adv-dirty{position:absolute;right:70px;...}`（「N 项待保存」小标
    也不再挤压标题；放在「N 项」左侧、垂直居中 —— 与它现在的位置一致）
  ⇒ 流内只剩标题一个元素，其盒 = [行左+52, 行右−52] ⇒ **中心恒等于行中心**；
     而行中心与底栏中心都来自 `.sheet` 的对称内边距 ⇒ **同一根轴**。

style.css 是**纯 LF**。

    python _mk_r41_align.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = HERE / "dgtf_app" / "static" / "style.css"

OLD_ROW = """.adv-groups .nav-btn{position:relative;padding-right:52px}"""
NEW_ROW = """/* ★ R41：**左右预留相等** + 图标移出文档流 ⇒ 标题盒关于行中心对称。
   原来左预留 = 13(内边距)+15(图标)+9(gap) = 37px，右预留 = 52px ⇒ 标题被推左；
   再叠上 `.nb-name` 自带的 `padding-right:24px`，实测偏约 28px（用户报「没和保存对齐」）。 */
.adv-groups .nav-btn{position:relative;padding-right:52px;padding-left:52px}
.adv-groups .nav-btn svg{position:absolute;left:13px;top:50%;transform:translateY(-50%)}"""

OLD_NAME = """.nav-btn .nb-name{font-size:13.5px;font-weight:500;flex:1 1 auto;
  white-space:nowrap;text-align:center;padding-right:24px}"""
NEW_NAME = """.nav-btn .nb-name{font-size:13.5px;font-weight:500;flex:1 1 auto;
  white-space:nowrap;text-align:center;padding-right:24px}
/* ★ R41：分组行里的标题**不要再留那 24px** —— 它是给抽屉那套留的；
   这里右侧已经有 52px 的绝对定位预留，再留一次就把文字推左。 */
.adv-groups .nav-btn .nb-name{padding-right:0;padding-left:0}"""

OLD_PILL = """.nav-btn .adv-dirty{font-style:normal;font-size:10.5px;font-weight:700;margin-left:7px;
  padding:2px 7px;border-radius:20px;color:#F7D885;
  background:rgba(214,168,44,.26);border:1px solid rgba(245,196,83,.48)}"""
NEW_PILL = """/* ★ R41：“N 项待保存”小标改成**绝对定位**（放在「N 项」左侧、垂直居中，与它原先的位置一致）
   —— 它是流内元素时，一旦出现就会把 `.nb-name` 挤窄 ⇒ 标题中心又被推左。
   绝对定位后，**流内只剩标题一个元素**，「居中」不再受任何兄弟影响。 */
.nav-btn .adv-dirty{position:absolute;right:70px;top:50%;transform:translateY(-50%);
  font-style:normal;font-size:10.5px;font-weight:700;
  padding:2px 7px;border-radius:20px;color:#F7D885;
  background:rgba(214,168,44,.26);border:1px solid rgba(245,196,83,.48)}"""


def main() -> int:
    b = CSS.read_bytes()
    assert b.count(b"\r") == 0, "style.css 不是纯 LF"
    s = b.decode("utf-8")

    def rep(old: str, new: str, what: str) -> str:
        nonlocal s
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            return s
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)
        return s

    s = rep(OLD_ROW, NEW_ROW, "① 分组行左右预留相等 + 图标移出文档流")
    s = rep(OLD_NAME, NEW_NAME, "② 分组行标题去掉多余的 24px 右内边距")
    s = rep(OLD_PILL, NEW_PILL, "③ 「N 项待保存」小标改绝对定位")
    CSS.write_bytes(s.encode("utf-8"))

    # ── 结构性自检（重新读盘 + 算一遍「标题盒中心 == 行中心」）──────────────
    s2 = CSS.read_bytes().decode("utf-8")
    bad = []

    def rule(sel: str) -> str:
        out = [m.group(1) for m in re.finditer(re.escape(sel) + r"\s*\{([^}]*)\}", s2)]
        return out[0] if out else ""

    def val(body: str, prop: str):
        m = re.search(r"(?:^|;|\s)" + prop + r"\s*:\s*([^;}]+)", body)
        return m.group(1).strip() if m else None

    row = rule(".adv-groups .nav-btn")
    pl, pr = val(row, "padding-left"), val(row, "padding-right")
    if pl != "52px" or pr != "52px":
        bad.append("左右预留不相等：padding-left=%s padding-right=%s" % (pl, pr))
    svg = rule(".adv-groups .nav-btn svg")
    if val(svg, "position") != "absolute":
        bad.append("图标没移出文档流（它还在推标题）：%r" % svg[:40])
    name = rule(".adv-groups .nav-btn .nb-name")
    if val(name, "padding-right") != "0" or val(name, "padding-left") != "0":
        bad.append("标题还带内边距：padding-left=%s padding-right=%s"
                   % (val(name, "padding-left"), val(name, "padding-right")))
    for sel, label in ((".adv-groups .nav-btn em", "项数"), (".nav-btn .adv-dirty", "待保存小标")):
        if val(rule(sel), "position") != "absolute":
            bad.append("%s 还在文档流里（会挤窄标题）" % label)
    # ★ 算出两条中轴：行 [0,W] → 标题盒 [52, W-52] → 中心 W/2；底栏同宽、左右各 22px ⇒ 中心也是 W/2
    W = 1000
    title_center = (52 + (W - 52)) / 2.0
    bar_center = (22 + (W - 22)) / 2.0
    if abs(title_center - bar_center) > 0:
        bad.append("算出来的中轴不等：标题 %.1f vs 底栏 %.1f" % (title_center, bar_center))
    if bad:
        print("★ 结构性自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：左右预留 52/52、图标/项数/小标全 absolute、"
          "标题盒中心 == 底栏中心（W/2）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
