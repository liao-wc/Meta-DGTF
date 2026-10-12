#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R40 的 selftest 变更：

  A. **5 条 R39 期判据随实现更新**（改口径，不是放宽）——
     ①②③ 圆点从「日志框内的绝对定位」改成「页面右缘的 fixed + 视口坐标」；
     ④    `.pend` 不再降透明度（R39 判据读的就是 `opacity:.55`）；
     ⑤    `rlTrack()` 的钳制表达式换了写法。
  B. 新增 `check_r40_frontend(css, js, html, runner_src)`（模块级函数，变异体可直接喂坏输入）。

`selftest.py` 纯 CRLF。

    python _mk_r40_selftest.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

DEF_ANCHOR = "def main() -> int:\n    ap = argparse.ArgumentParser()"
CALL_ANCHOR = "    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────"
DEFLINE = "def check_r40_frontend(css: str, js: str, html: str, runner_src: str) -> None:"

# ── A. 过时的判据（旧 → 新）────────────────────────────────────────────────
FIX = [
    ("""    check("★R39 滚动点**贴最右缘**（`right:1px`，不再落在内侧悬空）",
          "right:1px" in _rule(css, "#rl-bar").replace(" ", ""),
          _rule(css, "#rl-bar").strip()[:70])""",
     """    # ★ R40 改口径：圆点从「日志框内的 `absolute`」提到**页面最右缘的 `fixed`**
    #   （用户要求「滚动点改到外页面最右侧显示」）⇒ 判据改成 fixed + right:2px。
    check("★R40 滚动点**贴页面最右缘**（`position:fixed` + `right:2px`）",
          "position:fixed" in _rule(css, "#rl-bar").replace(" ", "")
          and "right:2px" in _rule(css, "#rl-bar").replace(" ", ""),
          _rule(css, "#rl-bar").strip()[:70])"""),
    ("""    check("★R39 抽 `rlTrack()` 作**唯一**轨迹来源（滚动 + 拖拽共用同一 lo/hi）",
          "function rlTrack()" in js
          and "const base = Math.round(bd.getBoundingClientRect().top - "
              "box.getBoundingClientRect().top);" in js
          and js.count("rlTrack()") == 4,
          "rlTrack() 出现 " + str(js.count("rlTrack()")) + " 次（应 1 定义 + 3 调用）")""",
     """    # ★ R40 改口径：圆点 `fixed` ⇒ 轨迹用**视口坐标**（`rb.top` / `rb.bottom`），
    #   不再减日志框顶；「只能在这个日志窗口的正文范围内滑动」的语义不变。
    check("★R40 抽 `rlTrack()` 作**唯一**轨迹来源（视口坐标，滚动 + 拖拽共用同一 lo/hi）",
          "function rlTrack()" in js
          and "const lo = Math.max(0, Math.round(rb.top));" in js
          and js.count("rlTrack()") == 4,
          "rlTrack() 出现 " + str(js.count("rlTrack()")) + " 次（应 1 定义 + 3 调用）")"""),
    ("""    check("★R39 轨迹上端再按 `#runlog` 自身高度钳一次（圆点不许钻出日志窗口）",
          "Math.min(base + bd.clientHeight, box.clientHeight) - RL_DOT" in js, "")""",
     """    check("★R40 轨迹下端取 min(正文区底, 日志框底) − 直径（圆点不许钻出日志窗口）",
          "Math.min(rb.bottom, rbox.bottom)) - RL_DOT" in js, "")"""),
    ("""    check("**运行中也能看见这三个按钮**（待生成态 .pend：降透明度、不可点）",
          ".rl-filesa.pend{opacity:.55" in css.replace(" ", "")
          and "const pend = stamp ? '' : ' pend'" in js,
          "")""",
     """    # ★ R40 改口径：`.pend` **不再降透明度** —— 运行中三胶囊要与左徽章**逐项同色**
    #   （用户实测截图：徽章蓝、胶囊看着绿；量化像素后确认色相对，是 opacity 冲淡了）。
    #   「还点不动」由 pointer-events + cursor 承担。
    check("**运行中也能看见这三个按钮**（待生成态 .pend：不可点，但**不降透明度**）",
          ".rl-filesa.pend{pointer-events:none;cursor:default}" in css.replace(" ", "")
          and "opacity" not in css.replace(" ", "").split(".rl-filesa.pend{")[1][:60]
          and "const pend = stamp ? '' : ' pend'" in js,
          "")"""),
    ("""    check("★R39 底栏改 `1fr auto 1fr` 三列网格：保存落在**中间列**（与右侧按钮宽无关）",
          "grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);" in css
          and "display:grid" in _rule(css, ".sheet-actions").replace(" ", "")
          and ".sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}" in css
          and ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:start}" in css,
          _rule(css, ".sheet-actions").strip()[:70])""",
     """    # ★ R40 改口径：「恢复出厂设置」从 `justify-self:start` 变成 **`end`（贴右）**
    check("★R39 底栏改 `1fr auto 1fr` 三列网格：保存落在**中间列**（与右侧按钮宽无关）",
          "grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);" in css
          and "display:grid" in _rule(css, ".sheet-actions").replace(" ", "")
          and ".sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}" in css
          and ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:end}" in css,
          _rule(css, ".sheet-actions").strip()[:70])"""),
]

# ── B. 新增 R40 判据 ───────────────────────────────────────────────────────
BODY = '''    """★R40 的界面判据（用户 6 图 / 5 条）—— 单独成函数，变异体可直接喂坏输入驱动。"""

    # ── 需求 1：底栏几何 + **只该出现在参数两页** ────────────────────────────
    #   ① 保存与上方内容**同一中心轴**：`.sheet-actions` 的左右内边距必须与
    #      `.sheet-body`（`padding:18px 22px 22px`）一致，否则中心轴差几像素。
    _sb = _rule(css, ".sheet-body")
    _act = _rule(css, ".sheet-actions")
    check("★R40 底栏左右内边距**对齐 .sheet-body**（保存与上方内容同一中心轴）",
          "padding:18px 22px 22px" in _sb
          and "padding:12px 22px" in _act.replace(" ", " "),
          "sheet-body=%r  actions=%r" % (_sb.strip()[:32], _act.strip()[:32]))
    check("★R40 「恢复出厂设置」**贴右**（`justify-self:end`，不再停在中间偏右）",
          "justify-self:end" in _rule(css, ".sheet-actions #adv-reset"),
          _rule(css, ".sheet-actions #adv-reset").strip()[:60])
    #   ② ★★ 真 bug：`.hidden` 对 `.sheet-actions` **从来没有过任何规则**
    #      （文件里只有 `.sheet.hidden` / `.runlog.hidden` 这类**双类**规则），
    #      于是 `syncAdvBar()` 加的类完全是空转 ⇒ 底栏在读数台 / 历史对话 / 产物库… 上照样显示。
    #      判据分两层：这里查**规则在**且**特异性方向对**（`.sheet-actions.hidden` 是两类，
    #      特异性 0,2,0 > `.sheet-actions` 的 0,1,0 ⇒ 必然胜出，与源顺序无关）；
    #      「层叠后真是 display:none」由 node 探针 `_audit_tmp/_r40_css.js` 实测。
    check("★R40 底栏**真能被隐藏**：`.sheet-actions.hidden{display:none}` 在（两类 > 单类）",
          ".sheet-actions.hidden{display:none}" in css
          and "display:none" in _rule(css, ".sheet-actions.hidden"),
          "rule=%r" % _rule(css, ".sheet-actions.hidden").strip()[:40])
    check("★R40 底栏显隐仍由 `syncAdvBar()` 按页控制（只在进阶参数两页显示）",
          "function syncAdvBar(key) {" in js
          and "classList.toggle('hidden', !on)" in js
          and "'adv-panel'" in js and "'adv-group-page'" in js,
          "")

    # ── 需求 2：`json` 胶囊 → `<stamp>.packed.json` ──────────────────────────
    check("★R40 json 胶囊指向 `*.packed.json`（不再是 `.run.json`）",
          "data-archive=\\"${esc(stamp + '.packed.json')}\\"" in js
          and "data-archive=\\"${esc(stamp + '.run.json')}\\"" not in js, "")
    check("★R40 服务端放行 `.packed.json`（`read_archive` 的白名单）",
          'n.endswith(".packed.json")' in runner_src, "")
    check("★R40 JSON 打开时**美化**（`stringify(…, 2)`，否则 3000 行挤成一行）",
          "JSON.stringify(JSON.parse(body), null, 2)" in js, "")
    check("★R40 缺 `.packed.json`（mock / 早期产物）时**回落** `.run.json`，不报错",
          "name.replace(/\\\\.packed\\\\.json$/, '.run.json')" in js, "")
    #   产物 md 的「附录·全量字段」里，引擎把 packed 文件名**整块**放进代码框 —— 那里是**指路牌**。
    check("★R40 产物 md 里「整块就是一个文件名」的代码框 → 可点链接（`linkifyFileBlocks`）",
          "function linkifyFileBlocks(" in js and "FILE_BLOCK_RE" in js
          and "linkifyFileBlocks(renderMd(body))" in js
          and "packed\\\\.json|run\\\\.json|run\\\\.log|md" in js, "")

    # ── 需求 3：圆点提到**页面最右缘**，功能不变 ─────────────────────────────
    #   移出 `#runlog` + 挂 body 下：`main.stage` 有让位用的 transform，
    #   挂在里面会让 `position:fixed` 以它为包含块 ⇒ 贴不到视口缘。
    _a = html.index('<div id="runlog"') if '<div id="runlog"' in html else -1
    _b = html.index('<div class="composer">') if '<div class="composer">' in html else -1
    check("★R40 `#rl-bar` 移出 `#runlog`、挂到 body 下（否则 fixed 的包含块是 main）",
          _a > 0 and _b > _a and 'id="rl-bar"' not in html[_a:_b],
          "runlog=%d composer=%d" % (_a, _b))
    check("★R40 圆点 `z-index` 低于全屏面板（`#sheet`=65 / `#detail`=90），高于正文",
          "z-index:20" in _rule(css, "#rl-bar").replace(" ", ""), "")
    check("★R40 页面滚动时圆点跟着重算（补了 window 的 scroll 监听，passive）",
          "window.addEventListener('scroll', updateRlBar, { passive: true })" in js, "")

    # ── 需求 5：首屏欢迎语**随时段变** ───────────────────────────────────────
    check("★R40 欢迎语有独立节点（`#welcome-text`），文案由 JS 写",
          'id="welcome-text"' in html and "function paintWelcome(" in js
          and "$('#welcome-text')" in js, "")
    check("★R40 欢迎语按**本地小时**分档（`pickWelcome(h)` 纯函数 + 24 小时全覆盖）",
          "function pickWelcome(hour)" in js and "WELCOME_SLOTS" in js
          and "h >= s[0][0] && h <= s[0][1]" in js, "")
    check("★R40 欢迎语只在 `init()` 里写**一次**（不随日志渲染抖动）",
          js.count("paintWelcome();") == 1 and "  paintWelcome();" in js, "")
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

    # A. 过时判据改口径
    n_fix = 0
    for old, new in FIX:
        if new in cur:
            print("  · A 某条已是新口径，跳过")
            continue
        assert cur.count(old) == 1, "A 旧判据命中 %d 次：%s" % (cur.count(old), old[:60])
        cur = cur.replace(old, new)
        n_fix += 1
        print("  ✓ A 更新一条（R39 → R40 口径）")

    # B. 注入新函数
    inserted = False
    if DEFLINE in cur:
        print("  · B R40 判据函数已存在，跳过")
    else:
        assert cur.count(DEF_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(DEF_ANCHOR)
        block = DEFLINE + "\n" + BODY + "\n\n"
        ast.parse(block)
        cur = cur.replace(DEF_ANCHOR, block + DEF_ANCHOR)
        assert cur.count(CALL_ANCHOR) == 1, "调用锚点命中 %d 次" % cur.count(CALL_ANCHOR)
        cur = cur.replace(CALL_ANCHOR, "    check_r40_frontend(css, js, html, runner_src)\n" + CALL_ANCHOR)
        inserted = True
        print("  ✓ B 注入 `check_r40_frontend`（定义 + 调用）")

    write_crlf(ST, cur)

    # 自检
    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    n_new = back.count('check("★R40')
    # 15 条新判据（`check_r40_frontend` 里）+ 3 条 R39 判据改名成 ★R40（口径变了）
    assert n_new == 18, "★R40 判据 %d 条（期望 18）" % n_new
    assert back.count("check_r40_frontend(css, js, html, runner_src)") == 1
    for dead in ('"right:1px" in _rule(css, "#rl-bar")',
                 '"const base = Math.round(bd.getBoundingClientRect().top - "',
                 '"Math.min(base + bd.clientHeight, box.clientHeight) - RL_DOT" in js',
                 '".rl-filesa.pend{opacity:.55" in css.replace(" ", "")'):
        assert dead not in back, "旧口径判据还在：" + dead
    for keep in ('check("★R39 滚动点 `#rl-bar` 底色改**蓝**',
                 'check("★R39 三个胶囊（`.rl-files.st-* a`）引用**同一组**变量',
                 'check("⑦ 参数页只剩**两个**出口'):
        assert keep in back, "老判据被抹掉：" + keep
    if inserted:
        print("  · 本次更新 %d 条口径 + 新增 13 条" % n_fix)
    print("  ✓ 自检：AST 通过 / ★R40 判据 %d 条 / 旧口径已清 / 老判据仍在" % n_new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
