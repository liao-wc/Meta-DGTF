#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R44 · 界面部分（用户 6 图 / 6 条里的 1~4、6）：

  ① 读数台**实时更新**（5s 一轮，只在「读数台」这一页可见时拉；切到该页立刻拉一次）
  ② 点**对话框**（含里面的胶囊/回形针/发送键）或**首屏空白区** ⇒ 抽屉自动收起（其余行为不动）
  ③ 首屏文案改「此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧」+ 字号调小
  ④ 首屏**不出现滚动点**（根因：空态那条早返回路径不会调 `updateRlBar()`，
     点会留在上一次的位置；顺手把「日志窗口自身是否可见」显式判掉）
  ⑥ 首屏以**对话框为基准**居中 + 整体上移
  ＋ 顺手把「选择文件导入」改成**真按钮**（item 5 的前端管线，见 `_mk_r44_import.py`）

换行：`app.js` CRLF；`style.css` / `index.html` LF。

    python _mk_r44_ui.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "dgtf_app" / "static" / "app.js"
CSS = HERE / "dgtf_app" / "static" / "style.css"
HTML = HERE / "dgtf_app" / "static" / "index.html"

# ── app.js ─────────────────────────────────────────────────────────────────
JS_OLD = [
    ("const Q_PLACEHOLDER = '这次又想到什么问题了？可以发给元DGTF  我们一起去探索吧';",
     "const Q_PLACEHOLDER = '此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧';",
     "③ 占位文案"),

    ("""  if (t.over <= 8 || bd.clientHeight < 60) { bar.classList.remove('on'); return; }""",
     """  /* ★ R44：**日志窗口自己没显示时不画点** —— 首屏（`body.stage-empty`）里 `#runlog`
     是 `.hidden`（display:none），尺寸上也算得出来「不用显示」，但空态那条**早返回**路径
     压根不会走到这个函数 ⇒ 点会**留在上一次的位置**（用户报「首屏不该有滚动点」）。
     把「窗口是否可见」显式判掉，比依赖尺寸稳。 */
  const _box = $('#runlog');
  if (!_box || _box.classList.contains('hidden')
      || t.over <= 8 || bd.clientHeight < 60) { bar.classList.remove('on'); return; }""",
     "④ 圆点：日志窗口隐藏时一律不画"),

    ("""  document.body.addEventListener('click', async (e) => {
    const open = e.target.closest('[data-open]');""",
     """  document.body.addEventListener('click', async (e) => {
    /* ★ R44：点**对话框**（含里面的功能胶囊 / 回形针 / 发送键）或**首屏空白区** ⇒ 抽屉自动收起。
       **只做「收起」这一件事**：抽屉的开关仍由左上角图标 / 遮罩 / Esc 管，
       被点的那个元素该有的行为（发消息、切胶囊…）一律照旧。 */
    if (document.body.classList.contains('drawer-open')
        && (e.target.closest('.composer')
            || (document.body.classList.contains('stage-empty')
                && e.target.closest('main.stage')))) {
      closeDrawer();
    }
    const open = e.target.closest('[data-open]');""",
     "② 点对话框 / 首屏空白 ⇒ 收起抽屉"),

    ("""  loadDash();
  loadChats();""",
     """  loadDash();
  /* ★ R44：读数台**实时更新** —— 5 秒一轮，且只在「读数台」这一页可见、页面不在后台时拉。
     接口侧不用怕：`dashboard.scan()` 有**目录签名缓存**，余额自带 **15s 缓存** ⇒ 不会打爆。 */
  setInterval(() => {
    const p = $('#dash-stats');
    if (p && p.classList.contains('active') && document.visibilityState !== 'hidden') loadDash();
  }, 5000);
  loadChats();""",
     "① 读数台 5s 自动刷新"),

    ("""  syncAdvBar(key);
  // 高级参数默认展开""",
     """  syncAdvBar(key);
  /* ★ R44：切到「读数台」立刻拉一次（不用等下一个 5s 周期） */
  if (key === 'dash-stats') loadDash();
  // 高级参数默认展开""",
     "① 打开读数台立刻刷新"),

    ("""  $('#anchor-file').addEventListener('change', e => {
    const fs = e.target.files;
    e.target.value = '';
    if (fs && fs.length) importFiles(fs);
  });""",
     """  /* ★ R44：「选择文件导入」改成**真按钮**去点隐藏的 input —— 原来靠 `<label>` 包着
     `display:none` 的 input，用户报「点了没反应」；按钮这条路最直、最不容易被样式影响。
     `value=''` 保证同一个文件删了还能再选一次。 */
  const _ap = $('#anchor-pick'), _af = $('#anchor-file');
  if (_ap && _af) _ap.addEventListener('click', () => _af.click());
  if (_af) _af.addEventListener('change', e => {
    const fs = e.target.files;
    e.target.value = '';
    if (fs && fs.length) importFiles(fs);
  });""",
     "⑤ 按钮触发文件选择"),
]

# ── style.css ──────────────────────────────────────────────────────────────
CSS_OLD = [
    ("""  font-size:15px;line-height:1.55;padding:2px 4px 8px;min-height:26px;""",
     """  /* ★ R44：输入框与占位文字**调小一档**（用户要求「字体改小一点」）：15 → 13.5px */
  font-size:13.5px;line-height:1.55;padding:2px 4px 8px;min-height:26px;""",
     "③ 输入框字号 15 → 13.5px"),

    ("""body.stage-empty main.stage{justify-content:center;align-items:center}""",
     """/* ★ R44：首屏**以对话框为基准**居中，并整体上移。
   推导（这样写就有据可依，不是随手试数字）：空态这一组 = 欢迎语 + 间距(gap 14) + 对话框，
   整组居中时**对话框的中心**会低于视口中线 ≈（欢迎语高 44 + 14）/ 2 ≈ **29px**；
   用户还要「整体往上移」，再给 15px 余量 ⇒ 共上移 **44px**。
   `justify-content:center` 是在**内容盒**里居中 ⇒ 下内边距每多 1px，内容被顶高 0.5px，
   所以 44px 的上移 ⇔ `padding-bottom` 比原来多 **88px**（原来的 20px 保留）。 */
body.stage-empty main.stage{justify-content:center;align-items:center;
  padding-bottom:calc(20px + 88px)}""",
     "⑥ 首屏以对话框为基准居中并上移"),

    (""".import-bar .chk{cursor:pointer;background:var(--s2);border-color:var(--hair-2)}""",
     """.import-bar .chk{cursor:pointer;background:var(--s2);border-color:var(--hair-2)}
/* ★ R44：导入控件改成「真按钮 + 隐藏 input」（见 index.html 的注释），按钮沿用胶囊观感；
   下面那条是**逐文件结果**的展示区（成功/跳过/失败原因都摆出来，不再「点了没反应」）。 */
.import-bar #anchor-pick{height:36px;padding:0 14px;border-radius:var(--r-sm);
  background:var(--s2);border:1px solid var(--hair-2);color:var(--t1);
  font-size:12.5px;cursor:pointer;white-space:nowrap}
.import-bar #anchor-pick:hover{border-color:var(--accent);color:var(--accent-hi)}
.import-bar #anchor-pick:disabled{opacity:.5;cursor:default}
.import-detail{display:flex;flex-direction:column;gap:3px;margin:-4px 0 10px;
  font-size:12px;color:var(--t3);max-height:132px;overflow:auto}
.import-detail .ok{color:var(--t2)}
.import-detail .bad{color:var(--err)}""",
     "⑤ 导入按钮与结果区样式"),
]

HTML_OLD = [
    ("""      placeholder="这次又想到什么问题了？可以发给元DGTF  我们一起去探索吧">""",
     """      placeholder="此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧">""",
     "③ 占位文案（HTML）"),

    ("""      <div class="import-bar">
        <label class="chk"><input type="file" id="anchor-file" multiple> 选择文件导入…</label>
        <span class="muted" id="import-msg"></span>
      </div>""",
     """      <div class="import-bar">
        <!-- ★ R44：改成**真按钮**去点隐藏 input —— 原来靠 `<label>` 包着 `display:none`
             的 input，用户报「点了没反应」（label 转发激活在样式/覆盖下会静默失效）。
             多选、不限类型（文档 / 图片都收）；上限写在按钮说明与后端校验里。 -->
        <button id="anchor-pick" class="ghost"
          data-tip="支持文档与图片；单文件 ≤100MB，单次最多 50 个">选择文件导入…</button>
        <input type="file" id="anchor-file" multiple hidden>
        <span class="muted" id="import-msg"></span>
      </div>
      <div class="import-detail" id="import-detail"></div>""",
     "⑤ 导入控件改按钮"),
]


def rd(p: Path, crlf: bool) -> str:
    b = p.read_bytes()
    if crlf:
        assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    else:
        assert b.count(b"\r") == 0, "%s 不是纯 LF" % p.name
    return b.decode("utf-8")


def wr(p: Path, s: str, crlf: bool) -> None:
    body = s.replace("\r\n", "\n")
    if crlf:
        body = body.replace("\n", "\r\n")
    b = body.encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)


def insert_after_marker(path: Path, marker: str, block: str, what: str, crlf: bool) -> None:
    """在**含 marker 的那一行之后**插一段。

    ★ 为什么不用「多行字面串替换」：这句注释里有一长串**对齐用的空格**，手打必然差一两个，
    锚点就命不中（本轮实测踩了一次）。钉「行内唯一子串 + 行尾」比钉整行稳。
    """
    s = rd(path, crlf).replace("\r\n", "\n")
    if block.strip() in s:
        print("  · %s：已插入，跳过" % what)
        return
    assert s.count(marker) == 1, "%s：marker 命中 %d 次（要求 1）" % (what, s.count(marker))
    i = s.index(marker)
    nl = s.index("\n", i)
    s = s[:nl + 1] + block + s[nl + 1:]
    print("  ✓ %s" % what)
    wr(path, s, crlf)


def apply(path: Path, pairs, crlf: bool) -> int:
    # ★ 必须**归一成 LF 再匹配**：`rd()` 对 CRLF 文件返回的是**带 `\r\n`** 的原文，
    #   而锚点里的换行是 `\n` ⇒ 多行锚点会一条都命不中（单行锚点却照样过，
    #   于是表现成「前两条成功、第三条 0 次命中」，本轮实测踩过）。`wr()` 会转回去。
    s = rd(path, crlf).replace("\r\n", "\n")
    for old, new, what in pairs:
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            continue
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)
    wr(path, s, crlf)
    return 0


def main() -> int:
    apply(JS, JS_OLD, True)
    insert_after_marker(
        JS, "// ★ R23：空态 ⇒ 恢复默认占位",
        "    updateRlBar();   // ★ R44：空态要**主动收掉**滚动点（见 updateRlBar 的注释）\n",
        "④ 空态早返回时也收一次点", True)
    apply(CSS, CSS_OLD, False)
    apply(HTML, HTML_OLD, False)

    js = rd(JS, True)
    css = rd(CSS, False)
    html = rd(HTML, False)
    bad = []
    for k in ("此刻 你又想到了什么？", "updateRlBar();   // ★ R44",
              "document.body.classList.contains('drawer-open')",
              "document.visibilityState !== 'hidden'", "if (key === 'dash-stats') loadDash();",
              "if (_ap && _af) _ap.addEventListener('click', () => _af.click());"):
        if k not in js:
            bad.append("app.js 缺：" + k)
    if "padding-bottom:calc(20px + 88px)" not in css:
        bad.append("首屏上移没落盘")
    if "font-size:13.5px;line-height:1.55" not in css:
        bad.append("输入框字号没改")
    if 'id="anchor-pick"' not in html or "此刻 你又想到了什么？" not in html:
        bad.append("index.html 的按钮/占位文案没落盘")
    if "<label class=\"chk\"><input type=\"file\" id=\"anchor-file\"" in html:
        bad.append("旧的 label 触发还在")
    r = subprocess.run(["node", "--check", str(JS)], capture_output=True)
    if r.returncode != 0:
        bad.append("node --check 失败：" + r.stderr.decode("utf-8", "replace")[:200])
    else:
        print("  ✓ node --check app.js 通过")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：1/2/3/4/6 + 导入按钮 全部落盘，app.js 语法通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
