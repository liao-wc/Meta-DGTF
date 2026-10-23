#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R41 的 selftest 判据：**分组行标题与底栏「保存」在同一根轴上**。

用户第二次报「保存按钮怎么没和上面的按钮对齐」。量像素后的结论：底栏本来就居中
（保存文字中心 958.5 ≈ 页面中心），偏的是**分组行的标题**（中心 ≈931）——
根因是行内左右预留不等（左 37 / 右 52）+ 标题自带的 24px 右内边距。

判据抽成模块级 `check_r41_frontend(css)`（变异体可直接喂坏 CSS 驱动），由 `main()` 调一次。

`selftest.py` 纯 CRLF。

    python _mk_r41_selftest.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

DEF_ANCHOR = "def main() -> int:\n    ap = argparse.ArgumentParser()"
CALL_ANCHOR = "    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────"
DEFLINE = "def check_r41_frontend(css: str) -> None:"

BODY = '''    """★R41 的界面判据：分组行标题要**真的居中**（于是和底栏居中的「保存」同轴）。"""

    def _val(body: str, prop: str):
        _m = re.search(r"(?:^|;|\\s)" + prop + r"\\s*:\\s*([^;}]+)", body)
        return _m.group(1).strip() if _m else None

    _row = _rule(css, ".adv-groups .nav-btn")
    _pl, _pr = _val(_row, "padding-left"), _val(_row, "padding-right")
    check("★R41 分组行**左右预留相等**（原来左 37 / 右 52 ⇒ 标题被推左）",
          _pl == "52px" and _pr == "52px", "left=%s right=%s" % (_pl, _pr))
    _nm = _rule(css, ".adv-groups .nav-btn .nb-name")
    check("★R41 标题**自己不带内边距**（那 24px 右内边距是抽屉那套用的）",
          _val(_nm, "padding-right") in ("0", "0px")
          and _val(_nm, "padding-left") in ("0", "0px"),
          "left=%s right=%s" % (_val(_nm, "padding-left"), _val(_nm, "padding-right")))
    check("★R41 图标 / 项数 / 「N 项待保存」小标都**离开文档流**（谁也推不动标题）",
          all(_val(_rule(css, s), "position") == "absolute" for s in (
              ".adv-groups .nav-btn svg", ".adv-groups .nav-btn em", ".nav-btn .adv-dirty")),
          "svg=%s em=%s pill=%s" % (
              _val(_rule(css, ".adv-groups .nav-btn svg"), "position"),
              _val(_rule(css, ".adv-groups .nav-btn em"), "position"),
              _val(_rule(css, ".nav-btn .adv-dirty"), "position")))
    # ★ **算出**两条中轴：行宽 W 时，标题盒 = [左预留, W − 右预留] ⇒ 中心 = (左 + W − 右)/2；
    #   底栏（左右各 22px、同宽）的中心 = (22 + W − 22)/2。左右预留相等 ⇒ 两者都是 W/2。
    _W = 1000.0
    _tc = ((float(_pl[:-2]) if _pl else 0) + (_W - (float(_pr[:-2]) if _pr else 0))) / 2
    _bc = 0.5 * _W
    check("★R41 **算出来**：标题盒中心 == 底栏中心（同一根轴）", abs(_tc - _bc) < 0.01,
          "标题 %.1f vs 底栏 %.1f" % (_tc, _bc))
'''


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0 and b.count(b"\r") == b.count(b"\r\n")
    p.write_bytes(b)


def main() -> int:
    cur = read_crlf(ST).replace("\r\n", "\n")
    if DEFLINE in cur:
        print("  · R41 判据函数已存在，跳过")
    else:
        assert cur.count(DEF_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(DEF_ANCHOR)
        block = DEFLINE + "\n" + BODY + "\n\n"
        ast.parse(block)
        cur = cur.replace(DEF_ANCHOR, block + DEF_ANCHOR)
        assert cur.count(CALL_ANCHOR) == 1, "调用锚点命中 %d 次" % cur.count(CALL_ANCHOR)
        cur = cur.replace(CALL_ANCHOR, "    check_r41_frontend(css)\n" + CALL_ANCHOR)
        print("  ✓ 注入 `check_r41_frontend`（定义 + 调用）")
    write_crlf(ST, cur)

    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    assert back.count('check("★R41') == 4, "★R41 判据 %d 条（期望 4）" % back.count('check("★R41')
    assert back.count("check_r41_frontend(css)") == 1
    assert 'check("★R40' in back and 'check("★R39' in back, "老判据不该被抹"
    print("  ✓ 自检：AST 通过 / ★R41 判据 4 条 / 调用 1 处 / R39+R40 判据仍在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
