#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 R39（用户 16 图 / 9 条）的界面判据注入 `dgtf_app/selftest.py`。

★ 形态：抽成**模块级函数** `check_r39_frontend(css, js, html)`，由 `main()` 调一次 ——
  这样变异体可以直接喂「被改坏的 css / js / html」调用它，不必起服务（判别力证明成本≈0）。

`selftest.py` 是**纯 CRLF**：read_bytes -> 断言 -> 转 LF -> 插 -> 转回 -> write_bytes。
幂等：哨兵盯**函数定义行**。

    python _mk_r39_selftest.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

FUNC_ANCHOR = "def main() -> int:\n    ap = argparse.ArgumentParser()"
CALL_ANCHOR = "    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────"
CALL = "    check_r39_frontend(css, js, html)\n"
DEFLINE = "def check_r39_frontend(css: str, js: str, html: str) -> None:"

BODY = '''    """★R39 的界面判据（用户 16 图 / 9 条）—— 单独成函数，变异体可直接喂「改坏的」输入驱动。"""

    # ── 需求 1/3：`**一、…**` 这类 markdown 粗体标题 ⇒ **蓝标题**、且不露 `**` ──
    #   ★ 为什么不能用 `<b>` 当粗体：`.runlog-body b` 把 `<b>` 统一压成「数字黑」
    #     （`color:var(--log-num)`）⇒ 拿它做粗体会把文字染黑。正解是**剥掉星号**，
    #     再走 `.rl-title`（本身已经是蓝 + 700）。
    check("★R39 `RL_STAR`：`**…**` 整行归 title（原来整行绿、`**` 原样露出）",
          "const RL_STAR" in js and "if (RL_STAR.test(s)) return 'title';" in js, "")
    check("★R39 `RL_SUBQ`：`子问题[5]` 这类带框序号小标题归 title",
          "const RL_SUBQ" in js and "if (RL_SUBQ.test(s)) return 'title';" in js, "")
    check("★R39 有 `deStar()`，且 title / rlInline / rlPlain 三处都调它（星号不许露出）",
          "function deStar(" in js
          and "hlNums(esc(deStar(lab.replace(" in js
          and "esc(deStar(txt))" in js
          and "esc(deStar(s.replace(" in js, "")
    check("★R39 标题 / 步骤 / 轮次那一档是**蓝**（--log-blue + 700）",
          "color:var(--log-blue)" in _rule(css, ".rl-round,.rl-title,.rl-step,.rl-summary")
          and "font-weight:700" in _rule(css, ".rl-round,.rl-title,.rl-step,.rl-summary"),
          _rule(css, ".rl-round,.rl-title,.rl-step,.rl-summary").strip()[:60])

    # ── 需求 7：印记 / 带框头部统一**蓝**（`.rl-mark`）────────────────────────
    #   真实日志里的行首标记（在 outputs/*.run.log 上按 `行首 + 可选 & + [..]` 计数）：
    #     `[?→0]` 150 / `& [结构性]` 109 / `[?→1]` 103 / `& [1]` 80 / `& [0]` 32 /
    #     `· [candidate]` / `· [any]` / `· [ing]`
    #   原来只有「行首**就是** `[`」才走 bracket ⇒ 带 `&` / 列表点 / `子问题` 前缀的整行绿。
    check("★R39 有 `rlMarked()` + `RL_MARK_HEAD`，`content` 分支改走它",
          "function rlMarked(" in js and "const RL_MARK_HEAD" in js
          and "out.push(rlMarked(s))" in js, "")
    check("★R39 `RL_MARK_HEAD` = 可选 `&` + 可选列表点 + 可选前缀词 + `[框]`",
          "RL_MARK_PRE" in js and "(?:子问题|问题|候选|条目|编号|序号)" in js
          and "' + RL_MARK_PRE +" in js, "")
    check("★R39 `.rl-mark` 也是**蓝**（与 `.rl-lab` 同源变量 --log-blue）",
          "color:var(--log-blue)" in _rule(css, ".rl-mark"), _rule(css, ".rl-mark").strip()[:48])

    # ── 需求 4：滚动点改**蓝** + 贴到日志区最右缘 ────────────────────────────
    check("★R39 滚动点 `#rl-bar` 底色改**蓝**（不再是 rgba(0,0,0,.34) 黑点）",
          "rgba(47,58,168" in _rule(css, "#rl-bar").replace(" ", "")
          and "rgba(0,0,0,.34)" not in css.replace(" ", ""),
          _rule(css, "#rl-bar").strip()[:70])
    check("★R39 滚动点**贴最右缘**（`right:1px`，不再落在内侧悬空）",
          "right:1px" in _rule(css, "#rl-bar").replace(" ", ""),
          _rule(css, "#rl-bar").strip()[:70])

    # ── 需求 4：左边徽章与右边「产物/运行日志/json」三胶囊**同色** ──────────
    #   ★★ 用户连报两轮「两边不一致」 ⇒ 改成**同源 CSS 变量**：色值只写一次，
    #     左右都 `var(...)` 引用 ⇒ 机制上不可能再不一致（不是「这次改齐了」）。
    _hr = _rule(css, ".runlog-head").replace(" ", "")
    check("★R39 `.runlog-head` 上定义四档状态色变量 --st-*-c/-bd/-bg",
          all(k in _hr for k in ("--st-done-c:#1E7A34", "--st-done-bd:", "--st-done-bg:",
                                 "--st-running-c:#2F3AA8", "--st-queued-c:#8A6414",
                                 "--st-error-c:#B42318")),
          "缺：" + "".join(k for k in ("--st-done-c:#1E7A34", "--st-running-c:#2F3AA8",
                                      "--st-queued-c:#8A6414", "--st-error-c:#B42318")
                          if k not in _hr))
    check("★R39 徽章四档**引用**这组变量（不再各写一份硬编码色）",
          all(("var(--st-%s-c)" % _k) in _rule(css, ".runlog-head .badge.%s" % _k)
              and ("var(--st-%s-bg)" % _k) in _rule(css, ".runlog-head .badge.%s" % _k)
              for _k in ("done", "running", "queued", "error")),
          _rule(css, ".runlog-head .badge.running").strip()[:56])
    check("★R39 三个胶囊（`.rl-files.st-* a`）引用**同一组**变量 ⇒ 左右同色",
          all(("var(--st-%s-c)" % _k) in _rule(css, ".rl-files.st-%s a" % _k)
              for _k in ("done", "running", "queued", "error")),
          _rule(css, ".rl-files.st-running a").strip()[:56])

    # ── 需求 5/6：阴阳视角「内容没显示完全」 ───────────────────────────────
    #   ★ 根因有**两层**，两层都要钉：
    #     ① 引擎侧 `raw[:200]` 把多行正文砍在行中间（见 `v12323_报告.md`）；
    #     ② 前端 `.rl-fold{overflow:hidden}` 把小折叠块里溢出的行裁掉。
    check("★R39 `.rl-fold` **不再** overflow:hidden（折叠块里的行不许被裁）",
          "overflow:hidden" not in _rule(css, ".rl-fold"),
          _rule(css, ".rl-fold").strip()[:64])

    # ── 需求 8：保存按钮**底部居中** ────────────────────────────────────────
    check("★R39 底栏改 `1fr auto 1fr` 三列网格：保存落在**中间列**（与右侧按钮宽无关）",
          "grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);" in css
          and "display:grid" in _rule(css, ".sheet-actions").replace(" ", "")
          and ".sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}" in css
          and ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:start}" in css,
          _rule(css, ".sheet-actions").strip()[:70])

    # ── 需求 9：滚动圆点的上下行程 —— 两条路共用一条轨迹、且限在本窗口内 ────
    #   ★★ 这是个**真 bug**：`updateRlBar()` 的 `top` 带「正文区顶 − 日志框顶」的偏移
    #     （= 头栏高度），而拖拽的 `onMove` 钳在 `[0, 轨道]`（**少了那个偏移**）⇒
    #     一按住圆点拖动它就往上跳约一个头栏，看着像「拖动不跟手 / 跑出范围」。
    check("★R39 抽 `rlTrack()` 作**唯一**轨迹来源（滚动 + 拖拽共用同一 lo/hi）",
          "function rlTrack()" in js
          and "const base = Math.round(bd.getBoundingClientRect().top - "
              "box.getBoundingClientRect().top);" in js
          and js.count("rlTrack()") == 4,
          "rlTrack() 出现 " + str(js.count("rlTrack()")) + " 次（应 1 定义 + 3 调用）")
    check("★R39 拖拽改用 `[t.lo, t.hi]`，旧口径 `[0, track]` 已消失",
          "Math.max(t.lo, Math.min(t.hi, startTop + dy))" in js
          and "Math.max(0, Math.min(track, startTop + dy))" not in js
          and "bd.scrollTop = (top / track) * over" not in js, "")
    check("★R39 轨迹上端再按 `#runlog` 自身高度钳一次（圆点不许钻出日志窗口）",
          "Math.min(base + bd.clientHeight, box.clientHeight) - RL_DOT" in js, "")

    # ── 需求 2：日志头部（`__head__`）**真能**渲染出来 ───────────────────────
    #   ★★ 根因是**字段断链**（R37 的判据只查了 `"src.head" in js` ——
    #     字符串在、值**永远取不到**）：后端 `read_layers()` 一直返回 `"head"`，
    #     但 `pollLanes()` 只读 `r.layers`（桶名是 `__head__`）⇒ `lanes.head` 恒
    #     undefined ⇒ 开头块从来没渲染过。接线断言看不见「取不到值」，所以这里
    #     把**两条取值路径**都钉住。
    check("★R39 `pollLanes()` 把 `r.head` 并 `r.layers['__head__']` 接进 `lanes.head`",
          "lanes.head = r.head || (r.layers || {})['__head__'] || '';" in js, "")
    check("★R39 渲染侧再兜一次（`src.head || src['__head__']`），老后端也能出开头块",
          "src.head || src['__head__']" in js, "")

    # ── 需求 9b：首屏对话框文案（两处必须同步）──────────────────────────────
    _ph = "这次又想到什么问题了？可以发给元DGTF  我们一起去探索吧"
    check("★R39 首屏提示语**两处同步**（index.html 的 placeholder + app.js 的 Q_PLACEHOLDER）",
          _ph in html and _ph in js, "html=" + str(_ph in html) + " js=" + str(_ph in js))
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
    n_before = cur.count('\n    check("★R39')          # 注入前：0
    inserted = False

    if DEFLINE in cur:
        print("  · R39 判据函数已存在，跳过")
    else:
        assert cur.count(FUNC_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(FUNC_ANCHOR)
        block = DEFLINE + "\n" + BODY + "\n\n"
        ast.parse(block)                       # 预检：注入的块自己得先能解析
        cur = cur.replace(FUNC_ANCHOR, block + FUNC_ANCHOR)
        assert cur.count(CALL_ANCHOR) == 1, "调用锚点命中 %d 次" % cur.count(CALL_ANCHOR)
        cur = cur.replace(CALL_ANCHOR, CALL + CALL_ANCHOR)
        inserted = True
        print("  ✓ 注入 `check_r39_frontend`（定义 + 调用）")

    write_crlf(ST, cur)

    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    n_after = back.count('\n    check("★R39')
    assert n_after == 20, "★R39 判据注入后 %d 条（期望 20）" % n_after
    assert back.count('check("★R39') == 20, "★R39 判据 %d 条（期望 20）" % back.count('check("★R39')
    assert back.count("check_r39_frontend(css, js, html)") == 1, "调用点不是 1 处"
    if inserted:
        assert n_after - n_before == 20, "新增 check 数 %d（期望 20）" % (n_after - n_before)
    for keep in ('check("⑦ 参数页只剩**两个**出口',
                 'check("④ ★R38 平移**放慢到 .6s**'):
        assert keep in back, "老判据被抹掉：" + keep
    print("  ✓ 自检：AST 通过 / 20 条 ★R39 判据 / 调用点 1 处 / 老判据仍在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
