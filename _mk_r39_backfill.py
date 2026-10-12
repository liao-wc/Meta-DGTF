#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 回填两件事：

① `style.css`：`.rl-files a` 的**基线**（= 完成态）改引用 `--st-done-*`
   —— 它原来自己写着 `color:#1E7A34 / border rgba(30,122,52,.38) / background rgba(30,122,52,.14)`，
   而徽章的 done 档 bg 是 `.10` ⇒ R34 说的「同一套绿」其实**底色一直差一点**。
   现在两边都 `var(--st-done-*)`，机制上保证一致。

② `selftest.py`：6 条 R38 期的 ⑤ 判据**随实现更新**（不是放宽）——
   它们原来比的是**字面色值**（`"#2F3AA8" in ...`），而两边改成同源变量后色值只剩
   一份（在 `.runlog-head` 的变量块里）⇒ 判据改成
   「两边都引用**同一个变量名** 且 该变量确实解析成那个色」。
   ★ 顺带补上 R38 **漏掉的背景一维** —— 用户报的正是「按钮背景颜色没和左边徽章一致」，
     而旧判据只比了文字色（所以两轮都是绿的）。

style.css 纯 LF / selftest.py 纯 CRLF —— 各自按自己的风格往返。

    python _mk_r39_backfill.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = HERE / "dgtf_app" / "static" / "style.css"
ST = HERE / "dgtf_app" / "selftest.py"

CSS_OLD = """  color:#1E7A34;
  font-weight:700;text-decoration:none;padding:3px 10px 3px 8px;border:1px solid rgba(30,122,52,.38);
  border-radius:20px;background:rgba(30,122,52,.14);"""

CSS_NEW = """  color:var(--st-done-c);
  font-weight:700;text-decoration:none;padding:3px 10px 3px 8px;border:1px solid var(--st-done-bd);
  border-radius:20px;background:var(--st-done-bg);"""

PAIRS = [
    ("""    check("⑤ `.rl-files.st-running` 与左徽章 `.runlog-head .badge.running` **同色**（#2F3AA8 紫）",
          "#2F3AA8" in _rule(css, ".rl-files.st-running a")
          and "#2F3AA8" in _rule(css, ".runlog-head .badge.running"),
          _rule(css, ".rl-files.st-running a").strip()[:64])""",
     """    # ★★ R39 口径升级（判据随实现更新，不是放宽）：两边改成**同源变量**后色值只剩一份
    #   （在 `.runlog-head` 的变量块里）⇒ 判据比「两边引用**同一个变量名** + 该变量解析成那个色」，
    #   并**补上背景一维** —— R38 只比文字色，所以「按钮背景没跟左边徽章一致」两轮都漏检。
    _hrule = _rule(css, ".runlog-head")

    def _stat_same(_st, _hex):
        _a = ".rl-files.st-%s a" % _st
        _b = ".runlog-head .badge.%s" % _st
        return (("var(--st-%s-c)" % _st) in _rule(css, _a)
                and ("var(--st-%s-c)" % _st) in _rule(css, _b)
                and ("var(--st-%s-bg)" % _st) in _rule(css, _a)
                and ("var(--st-%s-bg)" % _st) in _rule(css, _b)
                and ("--st-%s-c:%s" % (_st, _hex)) in _hrule.replace(" ", ""))

    check("⑤ `.rl-files.st-running` 与左徽章 `.runlog-head .badge.running` 同色**且同底**"
          "（同源 --st-running-c/-bg，其值 #2F3AA8 紫）",
          _stat_same("running", "#2F3AA8"),
          _rule(css, ".rl-files.st-running a").strip()[:64])"""),
    ("""    check("⑤ `.rl-files.st-queued` 与 `.runlog-head .badge.queued` **同色**（#8A6414 琥珀）",
          "#8A6414" in _rule(css, ".rl-files.st-queued a")
          and "#8A6414" in _rule(css, ".runlog-head .badge.queued"),
          "")""",
     """    check("⑤ `.rl-files.st-queued` 与左徽章 `.runlog-head .badge.queued` 同色**且同底**"
          "（同源 --st-queued-c/-bg，其值 #8A6414 琥珀）",
          _stat_same("queued", "#8A6414"),
          _rule(css, ".rl-files.st-queued a").strip()[:64])"""),
    ("""    check("⑤ `.rl-files.st-error` 与 `.runlog-head .badge.error` **同色**（#B42318 红）",
          "#B42318" in _rule(css, ".rl-files.st-error a")
          and "#B42318" in _rule(css, ".runlog-head .badge.error"),
          "")""",
     """    check("⑤ `.rl-files.st-error` 与左徽章 `.runlog-head .badge.error` 同色**且同底**"
          "（同源 --st-error-c/-bg，其值 #B42318 红）",
          _stat_same("error", "#B42318"),
          _rule(css, ".rl-files.st-error a").strip()[:64])"""),
    ("""    check("⑤ 取消 / 中断 / 已停 归到**同一档琥珀**（`.badge` 里也是这么归的）",
          ".rl-files.st-cancelled a" in css and ".rl-files.st-canceled a" in css
          and ".rl-files.st-interrupted a" in css
          and "#8A6414" in css[css.find(".rl-files.st-cancelled a"):
                               css.find(".rl-files.st-cancelled a") + 220],
          "")""",
     """    check("⑤ 取消 / 中断 / 已停 归到**同一档**（与 `.badge` 的归法一致：都走 --st-queued-*）",
          ".rl-files.st-cancelled a" in css and ".rl-files.st-canceled a" in css
          and ".rl-files.st-interrupted a" in css
          and "var(--st-queued-c)" in css[css.find(".rl-files.st-cancelled a"):
                                          css.find(".rl-files.st-cancelled a") + 240],
          "")"""),
    ("""    check("⑤ 三胶囊**完成态基线** = 左徽章同款绿（`.rl-files a` 与 `.runlog-head .badge.done` 同色）",
          "#1E7A34" in _rule(css, ".rl-files a")
          and "#1E7A34" in _rule(css, ".runlog-head .badge.done"),
          _rule(css, ".rl-files a").strip()[:64].replace("\\n", " "))""",
     """    check("⑤ 三胶囊**完成态基线** = 左徽章同款绿（`.rl-files a` 也走 --st-done-*）",
          "var(--st-done-c)" in _rule(css, ".rl-files a")
          and "var(--st-done-bg)" in _rule(css, ".rl-files a")
          and _stat_same("done", "#1E7A34"),
          _rule(css, ".rl-files a").strip()[:64].replace("\\n", " "))"""),
    ("""    check("⑤ `.rl-files.st-done` 与 `.runlog-head .badge.done` **同色**（#1E7A34 绿）",
          "#1E7A34" in _rule(css, ".rl-files.st-done a")
          and "#1E7A34" in _rule(css, ".runlog-head .badge.done"),
          _rule(css, ".rl-files.st-done a").strip()[:56] if ".rl-files.st-done a{" in css else "无该规则")""",
     """    check("⑤ `.rl-files.st-done` 与左徽章 `.runlog-head .badge.done` 同色**且同底**"
          "（同源 --st-done-c/-bg，其值 #1E7A34 绿）",
          _stat_same("done", "#1E7A34"),
          _rule(css, ".rl-files.st-done a").strip()[:56])"""),
    # ── 另外 3 条同族（R33/R34 期）也在比 `.rl-files a` 的**字面色值** ──────────
    #   基线改成 `var(--st-done-*)` 后字面没了 ⇒ 一并改到新语义（意图一字未改：
    #   「基线就是 done 档那一套绿」）。
    ("""          and "background:rgba(30,122,52,.14)" in _rule(css, ".rl-files a")
          and "color:#1E7A34" in _rule(css, ".rl-files a"),""",
     """          and "var(--st-done-bg)" in _rule(css, ".rl-files a")
          and "var(--st-done-c)" in _rule(css, ".rl-files a"),"""),
    ("""          and "width:32px;height:32px" in _rule(css, ".glyph.big")
          and "background:rgba(30,122,52,.14)" in _rule(css, ".rl-files a"),""",
     """          and "width:32px;height:32px" in _rule(css, ".glyph.big")
          and "var(--st-done-bg)" in _rule(css, ".rl-files a"),"""),
    ("""          and "border:1px solid rgba(30,122,52,.38)" in _rule(css, ".rl-files a")
          and _rule(css, ".rl-files a").strip().count('rgba(30,122,52') >= 2,""",
     """          and "border:1px solid var(--st-done-bd)" in _rule(css, ".rl-files a")
          and _rule(css, ".rl-files a").strip().count("var(--st-done-") >= 3,"""),
]


def main() -> int:
    # ① style.css（纯 LF）
    b = CSS.read_bytes()
    assert b.count(b"\r") == 0, "style.css 不是纯 LF"
    s = b.decode("utf-8")
    if CSS_NEW in s:
        print("  · ① `.rl-files a` 基线已是变量，跳过")
    else:
        assert s.count(CSS_OLD) == 1, "① 基线块命中 %d 次" % s.count(CSS_OLD)
        CSS.write_bytes(s.replace(CSS_OLD, CSS_NEW).encode("utf-8"))
        print("  ✓ ① `.rl-files a` 基线改引用 --st-done-*")

    # ② selftest.py（纯 CRLF）
    b = ST.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "selftest.py 不是纯 CRLF"
    t = b.decode("utf-8").replace("\r\n", "\n")
    n = 0
    for old, new in PAIRS:
        if new in t:
            print("  · ② 某条已是新版，跳过")
            continue
        assert t.count(old) == 1, "② 旧判据命中 %d 次：%s" % (t.count(old), old[:60])
        t = t.replace(old, new)
        n += 1
        print("  ✓ ② 更新一条 ⑤ 判据")
    ast.parse(t)
    ST.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))

    # ── 自检 ────────────────────────────────────────────────────────────────
    c2 = CSS.read_bytes().decode("utf-8")
    t2 = ST.read_bytes().decode("utf-8").replace("\r\n", "\n")
    ast.parse(t2)
    bad = []
    if "color:var(--st-done-c);" not in c2:
        bad.append("基线没接上变量")
    if "background:rgba(30,122,52,.14)" in c2:
        bad.append("基线的旧 .14 底色还在")
    if t2.count("_stat_same(") != 6:      # 1 定义 + 7 调用（4 档 + done 基线 + done + queued/error 各一）
        bad.append("_stat_same 出现 %d 次（期望 1 定义 + 5 调用）" % t2.count("_stat_same("))
    for dead in ('"#2F3AA8" in _rule(css, ".rl-files.st-running a")',
                 '"#8A6414" in _rule(css, ".rl-files.st-queued a")',
                 '"#B42318" in _rule(css, ".rl-files.st-error a")'):
        if dead in t2:
            bad.append("旧的字面比对还在：" + dead)
    if n != len(PAIRS):
        print("  · 本次实际更新 %d/%d 条（其余已是新版）" % (n, len(PAIRS)))
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：基线接变量 / AST 通过 / _stat_same 1+5 / 旧字面比对已清")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
