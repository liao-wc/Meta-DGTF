#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 修正：四档状态色变量里的 **背景** 取「左边徽章原本的值」，而不是三个胶囊的值。

为什么必须改：`git show HEAD:dgtf_app/static/style.css` 里两边的**背景**本来就不一样 ——

  · `.runlog-head .badge.done`   bg `rgba(30,122,52,.10)`
  · `.rl-files.st-done a`        bg `rgba(30,122,52,.14)`
  · `.runlog-head .badge.queued` bg `rgba(210,153,34,.14)`   ← 琥珀偏亮
  · `.rl-files.st-queued a`      bg `rgba(138,100,20,.10)`   ← 琥珀偏深
  · `.runlog-head .badge.error`  bg `rgba(248,81,73,.12)`
  · `.rl-files.st-error a`       bg `rgba(180,35,24,.10)`

**这正是用户报的「按钮背景颜色没和左边的徽章一致」** —— 而 R38 的判据只比了**文字色**
（都等于 `#2F3AA8` 之类），所以一直是绿的（判据只看了一维）。

取值口径：以**左边徽章**为准（它是状态的主信号、也是用户拿来对照的基准），
徽章因此**像素不变**，三个胶囊改为与它一致。四档的 bg 一律取徽章原值。

style.css 是**纯 LF**。

    python _mk_r39_statvar.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = HERE / "dgtf_app" / "static" / "style.css"

OLD = """  --st-done-c:#1E7A34;    --st-done-bd:rgba(30,122,52,.38);    --st-done-bg:rgba(30,122,52,.12);
  --st-running-c:#2F3AA8; --st-running-bd:rgba(47,58,168,.36); --st-running-bg:rgba(47,58,168,.12);
  --st-queued-c:#8A6414;  --st-queued-bd:rgba(138,100,20,.36); --st-queued-bg:rgba(138,100,20,.12);
  --st-error-c:#B42318;   --st-error-bd:rgba(180,35,24,.36);   --st-error-bg:rgba(180,35,24,.12)}"""

NEW = """  --st-done-c:#1E7A34;    --st-done-bd:rgba(30,122,52,.38);    --st-done-bg:rgba(30,122,52,.10);
  --st-running-c:#2F3AA8; --st-running-bd:rgba(47,58,168,.36); --st-running-bg:rgba(47,58,168,.10);
  --st-queued-c:#8A6414;  --st-queued-bd:rgba(138,100,20,.36); --st-queued-bg:rgba(210,153,34,.14);
  --st-error-c:#B42318;   --st-error-bd:rgba(180,35,24,.36);   --st-error-bg:rgba(248,81,73,.12)}"""

# 四档「左边徽章」的原始声明（git HEAD 逐字），用来钉住「徽章像素不变」
BADGE_HEAD = {
    "done": ('color:#1E7A34', 'border-color:rgba(30,122,52,.38)', 'background:rgba(30,122,52,.10)'),
    "running": ('color:#2F3AA8', 'border-color:rgba(47,58,168,.36)', 'background:rgba(47,58,168,.10)'),
    "queued": ('color:#8A6414', 'border-color:rgba(138,100,20,.36)', 'background:rgba(210,153,34,.14)'),
    "error": ('color:#B42318', 'border-color:rgba(180,35,24,.36)', 'background:rgba(248,81,73,.12)'),
}


def main() -> int:
    b = CSS.read_bytes()
    assert b.count(b"\r") == 0, "style.css 不是纯 LF"
    s = b.decode("utf-8")
    if NEW in s:
        print("  · 变量已取徽章原值，跳过")
    else:
        assert s.count(OLD) == 1, "变量块命中 %d 次" % s.count(OLD)
        s = s.replace(OLD, NEW)
        CSS.write_bytes(s.encode("utf-8"))
        print("  ✓ 四档 bg 改为「左边徽章原值」")

    s2 = CSS.read_bytes().decode("utf-8")
    bad = []
    # ① 变量块里四档 bg 必须是徽章原值
    blk = re.search(r"\.runlog-head\{(.*?)\}", s2, re.S)
    blk = blk.group(1) if blk else ""
    for k, (_c, _bd, _bg) in BADGE_HEAD.items():
        if ("--st-%s-bg:%s" % (k, _bg.split(":", 1)[1])) not in blk.replace(" ", ""):
            bad.append("--st-%s-bg 不是徽章原值" % k)
    # ② 徽章规则必须仍解析成同一组值（引用了变量）
    for k in BADGE_HEAD:
        rule = re.search(re.escape(".runlog-head .badge.%s" % k) + r"\s*\{([^}]*)\}", s2)
        body = rule.group(1) if rule else ""
        if ("var(--st-%s-c)" % k) not in body:
            bad.append(".badge.%s 文字色没引用变量" % k)
        if ("var(--st-%s-bd)" % k) not in body:
            bad.append(".badge.%s 边框色没引用变量" % k)
        if ("var(--st-%s-bg)" % k) not in body:
            bad.append(".badge.%s 背景色没引用变量" % k)
    # ③ 旧的光底浅绿 wash 值不该再出现（③ 判据在读它）
    if "rgba(30,122,52,.12)" in s2:
        bad.append("rgba(30,122,52,.12) 又出现在 css 里（③ 判据在读它）")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：四档变量 == 徽章原值；徽章三属性都引用变量；旧 wash 值已消失")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
