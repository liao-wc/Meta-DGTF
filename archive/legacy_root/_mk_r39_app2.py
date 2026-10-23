#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 收尾两处（用户 16 图 / 9 条里的第 8、9 条）：

  ⑧ 保存按钮**底部居中** —— 现在靠 `.sa-spacer`（`padding:0 22px` 恒 44px，并不是
     「与右侧按钮等宽」）⇒ 保存只是「大致靠中、略偏左」。改成 `1fr auto 1fr` 三列网格：
     中间列恒为保存，两侧等宽 ⇒ **与右侧按钮宽度无关**，保存恒在正中央。
  ⑨ 滚动圆点的上下行程**两条路共用一个口径**：
     `updateRlBar()` 用「正文区顶 − 日志框顶」的偏移 + 比例×轨道；
     而拖拽的 `onMove` 却钳在 `[0, 轨道]`（**少了那个偏移**）⇒ 一按住拖动，
     圆点先跳上去约等于头栏（`.runlog-head`）那么高，看着像「跑出范围 / 不跟手」。
     现在抽 `rlTrack()` 作为唯一来源，并把上端再按 `#runlog` 自身高度钳一次
     ⇒ 圆点只在这**一个日志窗口**的正文范围内滑动。

换行红线：`app.js` **纯 CRLF**、`style.css` **纯 LF** —— 各自按自己的风格往返。

    python _mk_r39_app2.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "dgtf_app" / "static" / "app.js"
CSS = HERE / "dgtf_app" / "static" / "style.css"


def read_text(p: Path, crlf: bool) -> str:
    b = p.read_bytes()
    if crlf:
        assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    else:
        assert b.count(b"\r") == 0, "%s 不是纯 LF" % p.name
    return b.decode("utf-8")


def write_text(p: Path, s: str, crlf: bool) -> None:
    body = s.replace("\r\n", "\n")
    if crlf:
        body = body.replace("\n", "\r\n")
    b = body.encode("utf-8")
    assert b.count(b"\r\r\n") == 0, "CRCRLF"
    p.write_bytes(b)


def repl(s: str, old: str, new: str, what: str) -> str:
    n = s.count(old)
    if n == 0:
        assert new in s, "%s：旧块没了、新块也没有" % what
        print("  · %s：已是新版，跳过" % what)
        return s
    assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
    print("  ✓ %s" % what)
    return s.replace(old, new)


# ── ⑨ app.js ────────────────────────────────────────────────────────────────
JS_OLD_UPDATE = """function updateRlBar() {
  const box = $('#runlog'), bd = $('#runlog-body'), bar = $('#rl-bar');
  if (!box || !bd || !bar) return;
  if (rlDragging) return;          // 拖动中由 mousemove 主控，别被滚动事件抢
  const over = bd.scrollHeight - bd.clientHeight;
  if (over <= 8 || bd.clientHeight < 60) { bar.classList.remove('on'); return; }
  const rb = bd.getBoundingClientRect(), rbox = box.getBoundingClientRect();
  /* 圆点沿轨道滑动：轨道高 = 可视区高 − 圆点直径 */
  const track = Math.max(0, bd.clientHeight - RL_DOT);
  const top = (rb.top - rbox.top) + Math.round((bd.scrollTop / over) * track);
  bar.style.top = Math.round(top) + 'px';
  bar.classList.add('on');
}"""

JS_NEW_UPDATE = """/* ★ R39：轨迹的**唯一来源** —— 原来 `updateRlBar()` 把圆点放在
   「正文区相对 `#runlog` 的偏移 + 比例 × 轨道」上，而拖拽的 `onMove` 却钳在
   `[0, 轨道]`（**少了那个偏移**）⇒ 一按住圆点拖动，它先跳上去约等于头栏
   （`.runlog-head`）那么高 —— 表现就是「拖动不跟手 / 跑出范围」。
   现在两条路共用这一个口径：`top ∈ [lo, hi]`，`hi` 再按 `#runlog` 自身高度钳一次
   ⇒ 圆点**只在这一个日志窗口的正文范围内**滑动（用户要求「限定在指定页面上下范围内」）。 */
function rlTrack() {
  const box = $('#runlog'), bd = $('#runlog-body');
  if (!box || !bd) return null;
  const over = bd.scrollHeight - bd.clientHeight;
  const base = Math.round(bd.getBoundingClientRect().top - box.getBoundingClientRect().top);
  const lo = Math.max(0, base);
  const hi = Math.max(lo, Math.min(base + bd.clientHeight, box.clientHeight) - RL_DOT);
  return { bd: bd, over: over, lo: lo, hi: hi };
}

function updateRlBar() {
  const t = rlTrack(), bar = $('#rl-bar');
  if (!t || !bar) return;
  if (rlDragging) return;          // 拖动中由 pointermove 主控，别被滚动事件抢
  const bd = t.bd;
  if (t.over <= 8 || bd.clientHeight < 60) { bar.classList.remove('on'); return; }
  const r = t.hi > t.lo ? Math.min(1, Math.max(0, bd.scrollTop / t.over)) : 0;
  bar.style.top = Math.round(t.lo + r * (t.hi - t.lo)) + 'px';
  bar.classList.add('on');
}"""

JS_OLD_MOVE = """  const onMove = (ev) => {
    const track = Math.max(1, bd.clientHeight - RL_DOT);
    const over = bd.scrollHeight - bd.clientHeight;
    const dy = ev.clientY - startY;
    const top = Math.max(0, Math.min(track, startTop + dy));
    bar.style.top = Math.round(top) + 'px';
    bd.scrollTop = (top / track) * over;
  };"""

JS_NEW_MOVE = """  const onMove = (ev) => {
    const t = rlTrack();
    if (!t || t.hi <= t.lo) return;
    const dy = ev.clientY - startY;
    const top = Math.max(t.lo, Math.min(t.hi, startTop + dy));
    bar.style.top = Math.round(top) + 'px';
    t.bd.scrollTop = ((top - t.lo) / (t.hi - t.lo)) * t.over;
  };"""

JS_OLD_START = """    const rbox = box.getBoundingClientRect();
    startTop = parseFloat(bar.style.top || '0') || (bar.getBoundingClientRect().top - rbox.top);
    startY = ev.clientY;"""

JS_NEW_START = """    const rbox = box.getBoundingClientRect();
    startTop = parseFloat(bar.style.top || '0')
      || (bar.getBoundingClientRect().top - rbox.top);
    /* ★ R39：起点也钳进本窗口的轨迹区间 —— 否则首帧 `bar.style.top` 还没算过，
       就会从窗口外的位置开始跟手。 */
    const t0 = rlTrack();
    if (t0) startTop = Math.max(t0.lo, Math.min(t0.hi, startTop));
    startY = ev.clientY;"""

# ── ⑧ style.css ─────────────────────────────────────────────────────────────
CSS_OLD = """.sheet-actions{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;
  gap:10px;flex:0 0 auto;padding:12px 18px;border-top:1px solid var(--hair-2)}
/* 隐形占位：宽度随「恢复出厂设置」自动伸缩（flex-basis:auto 的分身），保证「保存」居中 */
.sheet-actions .sa-spacer{visibility:hidden;height:0;overflow:hidden;
  flex:0 0 auto;padding:0 22px;font-size:14px;font-weight:600}"""

CSS_NEW = """/* ★ R39：保存按钮**底部居中** —— 改成 `1fr auto 1fr` 三列网格（中间列恒为「保存」，
   两侧等宽）⇒ 保存的位置与右边「恢复出厂设置」的宽度**无关**，恒在正中央。
   原来靠 `.sa-spacer` 占位，但它的宽度是 `padding:0 22px`（恒 44px），**并不等于**
   右侧按钮宽 ⇒ 保存只是「大致靠中、略偏左」（用户报「保存按钮底部居中」）。 */
.sheet-actions{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
  align-items:center;justify-content:center;
  gap:10px;flex:0 0 auto;padding:12px 18px;border-top:1px solid var(--hair-2)}
/* 隐形占位（占第一列，`visibility:hidden`）—— 保留它让「保存」落在**第二列** */
.sheet-actions .sa-spacer{grid-column:1;grid-row:1;visibility:hidden;height:0;overflow:hidden;
  flex:0 0 auto;padding:0 22px;font-size:14px;font-weight:600}
.sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}
.sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:start}
/* 窄屏兜底：三列排不下时退回两列（居中让位给「两个按钮都完整」） */
@media (max-width:560px){
  .sheet-actions{grid-template-columns:auto minmax(0,1fr)}
  .sheet-actions .sa-spacer{display:none}
  .sheet-actions #adv-save{grid-column:1;justify-self:start}
  .sheet-actions #adv-reset{grid-column:2;justify-self:end}
}"""


def main() -> int:
    # ⑨ app.js
    js = read_text(JS, crlf=True).replace("\r\n", "\n")
    js = repl(js, JS_OLD_UPDATE, JS_NEW_UPDATE, "⑨ app.js：rlTrack() 统一轨迹 + updateRlBar 接上")
    js = repl(js, JS_OLD_MOVE, JS_NEW_MOVE, "⑨ app.js：onMove 用同一条轨迹钳制")
    js = repl(js, JS_OLD_START, JS_NEW_START, "⑨ app.js：拖动起点也钳进轨迹区间")
    write_text(JS, js, crlf=True)

    # ⑧ style.css
    css = read_text(CSS, crlf=False)
    css = repl(css, CSS_OLD, CSS_NEW, "⑧ style.css：底栏改 1fr auto 1fr（保存恒居中）")
    write_text(CSS, css, crlf=False)

    # ── 结构性自检（重新读盘）──────────────────────────────────────────────
    import subprocess
    bad = []
    js2 = read_text(JS, crlf=True)
    css2 = read_text(CSS, crlf=False)
    if "function rlTrack()" not in js2:
        bad.append("rlTrack 没落盘")
    if js2.count("rlTrack()") != 4:
        bad.append("rlTrack() 出现 %d 次（应 1 定义 + 3 调用）" % js2.count("rlTrack()"))
    for dead in ("const track = Math.max(0, bd.clientHeight - RL_DOT);",
                 "const track = Math.max(1, bd.clientHeight - RL_DOT);"):
        if dead in js2:
            bad.append("旧的「两套轨迹」还在：" + dead)
    if re.search(r"bd\.scrollTop = \(top / track\)", js2):
        bad.append("onMove 仍按旧口径写 scrollTop")
    _sa = re.search(r"\.sheet-actions\{([^}]*)\}", css2)
    _sa = _sa.group(1) if _sa else ""
    if "display:grid" not in _sa.replace(" ", ""):
        bad.append("底栏不是 grid：%r" % _sa[:60])
    if "grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);" not in css2:
        bad.append("底栏三列模板没落盘")
    for sel in (".sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}",
                ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:start}",
                ".sheet-actions .sa-spacer{grid-column:1;grid-row:1;visibility:hidden"):
        if sel not in css2:
            bad.append("缺少显式网格位：%s" % sel)
    r = subprocess.run(["node", "--check", str(JS)], capture_output=True)
    if r.returncode != 0:
        bad.append("node --check 失败：" + r.stderr.decode("utf-8", "replace")[:200])
    else:
        print("  ✓ node --check app.js 通过")
    if bad:
        print("★ 结构性自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("结构性自检：全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
