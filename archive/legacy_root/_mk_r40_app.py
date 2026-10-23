#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R40（用户 6 图 / 5 条）落点：

  ① 底栏几何：`.sheet-actions` 内边距对齐 `.sheet-body`（保存与上方内容同一中心轴）+
     恢复出厂设置**贴右**；★ 并修**「不该出现的页面出现了」的根因** ——
     `.hidden` 对 `.sheet-actions` 从来没有任何效果（文件里只有 `.sheet.hidden` 这类
     **双类**规则）⇒ `syncAdvBar()` 一直在给底栏加/摘一个**空转的类**。
  ② `json` 胶囊 → 打开 `<stamp>.packed.json`（`read_archive` 放行 + 美化 + 缺 packed 时回落 run.json）；
     产物 md 预览里**整块就是一个文件名**的代码框 → 渲染成可点链接。
  ③ 滚动圆点从「日志框内」提到**页面最右缘**（`#rl-bar` 移出 `#runlog` 挂到 body 下，
     `position:fixed` + 视口坐标），功能（跟滚动 / 可拖 / 限上下范围）不变。
  ④ `.rl-files a.pend` 不再降透明度 —— 运行中三胶囊与左徽章**逐项同色**（实测像素：
     hue 本来就对，是 `.pend` 的 `opacity:.55` 把它们冲淡了）。
  ⑤ 首屏欢迎语**随时段变**。

换行红线：`app.js` CRLF / `style.css`·`index.html`·`engine_runner.py` LF。

    python _mk_r40_app.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "dgtf_app" / "static" / "app.js"
CSS = HERE / "dgtf_app" / "static" / "style.css"
HTML = HERE / "dgtf_app" / "static" / "index.html"
RUNNER = HERE / "dgtf_app" / "engine_runner.py"


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


def rep(s: str, old: str, new: str, what: str) -> str:
    n = s.count(old)
    if n == 0:
        assert new in s, "%s：旧块没了、新块也没有" % what
        print("  · %s：已是新版，跳过" % what)
        return s
    assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
    print("  ✓ %s" % what)
    return s.replace(old, new)


def ins_before(s: str, anchor: str, block: str, what: str) -> str:
    """在 anchor **之前**插一段。★ 哨兵必须盯**插入的那段本身** ——
    盯 anchor 的话，第二次跑时 anchor 还在（就插在它前面）⇒ 再插一遍（本轮实测踩过：
    `WELCOME_SLOTS` 被声明两次，`node --check` 才暴露）。"""
    if block in s:
        print("  · %s：已插入，跳过" % what)
        return s
    assert s.count(anchor) == 1, "%s：锚点命中 %d 次（要求 1）" % (what, s.count(anchor))
    print("  ✓ %s" % what)
    return s.replace(anchor, block + anchor)


# ═══════════════════════════ style.css ═══════════════════════════════════════
CSS_ACTIONS_OLD = """.sheet-actions{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
  align-items:center;justify-content:center;
  gap:10px;flex:0 0 auto;padding:12px 18px;border-top:1px solid var(--hair-2)}"""

CSS_ACTIONS_NEW = """/* ★ R40：左右内边距**对齐 `.sheet-body`**（那边是 `padding:18px 22px 22px`）——
   不然「保存」的中心轴会比上方内容偏 4px，看着没对齐（用户要求「与上面的按钮居中对齐」）。 */
.sheet-actions{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
  align-items:center;justify-content:center;
  gap:10px;flex:0 0 auto;padding:12px 22px;border-top:1px solid var(--hair-2)}
/* ★★ R40：**「不该出现的页面出现了」的根因就在这一条** ——
   `syncAdvBar()` 一直老老实实在给底栏加/摘 `.hidden`，但这个文件里只有
   `.sheet.hidden` / `.search-overlay.hidden` / `.runlog.hidden` / `.detail.hidden`
   这类**双类**规则：`.hidden` 单独出现时**没有任何规则** ⇒ 那个类对 `.sheet-actions`
   完全是空转，底栏在「读数台 / 最近跑过 / 历史对话 / 产物库 …」上照样显示（用户实测）。
   ★ 判据教训：只查「html 里有 `sheet-actions hidden` 这个串」是**接线判据**，
     看不见「这条类根本不起作用」—— 必须查**生效**（层叠后 `display:none` 胜出）。 */
.sheet-actions.hidden{display:none}"""

CSS_RESET_OLD = ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:start}"
CSS_RESET_NEW = ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:end}"

CSS_BAR_OLD = """#rl-bar{position:absolute;right:1px;width:12px;height:12px;border-radius:50%;
  background:rgba(47,58,168,.55);pointer-events:auto;cursor:grab;opacity:0;
  touch-action:none;
  transition:opacity .15s var(--ease),background .15s var(--ease)}"""

CSS_BAR_NEW = """/* ★ R40：从「日志框自己的滚动条」改成**贴在页面最右缘的悬浮点** ——
   `#rl-bar` 已移出 `#runlog`、挂到 `<body>` 下（`main.stage` 带 `transition:transform`
   的让位动画，有 transform 的祖先会成为 `position:fixed` 的包含块，挂在里面就贴不到视口缘）
   ⇒ 这里用 `fixed` + **视口坐标**（见 app.js `rlTrack()`）。
   功能（跟滚动 / 可拖 / 限上下范围）一字未变，只有水平位置变了。
   `z-index:20`：在正文之上、`#sheet`(65) / `#detail`(90) 之下。 */
#rl-bar{position:fixed;right:2px;width:12px;height:12px;border-radius:50%;
  background:rgba(47,58,168,.55);pointer-events:auto;cursor:grab;opacity:0;
  touch-action:none;z-index:20;
  transition:opacity .15s var(--ease),background .15s var(--ease)}"""

CSS_PEND_OLD = ".rl-files a.pend{opacity:.55;pointer-events:none;cursor:default}"
CSS_PEND_NEW = """/* ★ R40：「待生成」**不再降透明度** —— 实测像素：三胶囊的色相本来就是对的（蓝），
   是这里的 `opacity:.55` 把字色/底色/描边一起冲淡，看着与左徽章「不同色」
   （用户报「运行中与左上角徽章字体颜色一致为蓝色，同理背景颜色也一致」）。
   「还点不动」这层语义由 `pointer-events:none` + `cursor:default` + `title` 承担。 */
.rl-files a.pend{pointer-events:none;cursor:default}"""

# ═══════════════════════════ index.html ══════════════════════════════════════
HTML_BAR_OLD = """    <div id="runlog-body" class="runlog-body scroll"></div>
    <!-- ★ R33：自绘的日志滚动指示（原生长条改成**短的椭圆点**，见 style.css #rl-bar） -->
    <div id="rl-bar" class="rl-bar" aria-hidden="true"></div>
  </div>"""

HTML_BAR_NEW = """    <div id="runlog-body" class="runlog-body scroll"></div>
  </div>"""

HTML_BAR_INSERT_ANCHOR = '<div id="drawer-mask" class="drawer-mask"></div>'
HTML_BAR_INSERT = """<!-- ★ R40：日志滚动指示从 `#runlog` 里**提出来**挂到 body 下 ——
     用户要求它贴在**页面最右缘**（原来受日志框 `max-width:1080px` 约束，落在内侧）。
     为什么挂 body 而不是 `main`：`main.stage` 有让位用的 `transform` 过渡，
     有 transform 的祖先会成为 `position:fixed` 的包含块 ⇒ 挂在里面贴不到视口缘。
     `z-index:20`：在正文之上、全屏面板（`#sheet` 65 / `#detail` 90）之下。 -->
<div id="rl-bar" class="rl-bar" aria-hidden="true"></div>

"""

HTML_WELCOME_OLD = "    欢迎回来，随时开始吧"
HTML_WELCOME_NEW = '    <span id="welcome-text">欢迎回来，随时开始吧</span>'

# ═══════════════════════════ app.js ══════════════════════════════════════════
JS_JSON_OLD = """      + `<a href="#" class="rl-file${pend}"${tip} ${stamp ? `data-archive="${esc(stamp + '.run.json')}"` : 'aria-disabled="true"'}><span>json</span></a>`;"""
JS_JSON_NEW = """      + `<a href="#" class="rl-file${pend}"${tip} ${stamp ? `data-archive="${esc(stamp + '.packed.json')}"` : 'aria-disabled="true"'}><span>json</span></a>`;"""

JS_TRACK_OLD = """function rlTrack() {
  const box = $('#runlog'), bd = $('#runlog-body');
  if (!box || !bd) return null;
  const over = bd.scrollHeight - bd.clientHeight;
  const base = Math.round(bd.getBoundingClientRect().top - box.getBoundingClientRect().top);
  const lo = Math.max(0, base);
  const hi = Math.max(lo, Math.min(base + bd.clientHeight, box.clientHeight) - RL_DOT);
  return { bd: bd, over: over, lo: lo, hi: hi };
}"""

JS_TRACK_NEW = """function rlTrack() {
  const box = $('#runlog'), bd = $('#runlog-body');
  if (!box || !bd) return null;
  const over = bd.scrollHeight - bd.clientHeight;
  const rb = bd.getBoundingClientRect(), rbox = box.getBoundingClientRect();
  /* ★ R40：圆点改成 `position:fixed`（贴页面最右缘，不再受日志框宽度约束）
     ⇒ 轨迹必须改用**视口坐标**：上端 = 正文区顶（头栏之下），
     下端 = min(正文区底, 日志框底) − 圆点直径。
     语义（只在这一个日志窗口的正文范围内滑动）与 R39 完全一致。 */
  const lo = Math.max(0, Math.round(rb.top));
  const hi = Math.max(lo, Math.round(Math.min(rb.bottom, rbox.bottom)) - RL_DOT);
  return { bd: bd, over: over, lo: lo, hi: hi };
}"""

JS_START_OLD = """    const rbox = box.getBoundingClientRect();
    startTop = parseFloat(bar.style.top || '0')
      || (bar.getBoundingClientRect().top - rbox.top);"""
JS_START_NEW = """    /* ★ R40：圆点是 `position:fixed` ⇒ 它的视口坐标就是 `top` 本身，不用再减去日志框顶。 */
    startTop = parseFloat(bar.style.top || '0') || bar.getBoundingClientRect().top;"""

JS_LISTEN_OLD = """  const _rlb = $('#runlog-body');
  if (_rlb) _rlb.addEventListener('scroll', updateRlBar);
  window.addEventListener('resize', updateRlBar);
  bindRlBarDrag();"""
JS_LISTEN_NEW = """  const _rlb = $('#runlog-body');
  if (_rlb) _rlb.addEventListener('scroll', updateRlBar);
  window.addEventListener('resize', updateRlBar);
  /* ★ R40：圆点改成 `position:fixed`（视口坐标）⇒ 页面滚动时它的落点也会变，
     补一个 window 的 scroll 监听（passive：绝不能拖慢滚动）。 */
  window.addEventListener('scroll', updateRlBar, { passive: true });
  bindRlBarDrag();"""

JS_ARC_OLD = """  try {
    const { body } = await api('/api/archive/' + encodeURIComponent(name));
    const MAX = 300000;                 // 超大文件只给头部，避免页面卡死
    const clip = body.length > MAX;
    const head = clip ? body.slice(0, MAX) : body;
    $('#detail-body').innerHTML =
      (clip ? `<p class="muted">（文件较大，仅显示前 ${Math.round(MAX / 1024)} KB；完整内容见 outputs/${esc(name)}）</p>` : '')
      + '<pre>' + esc(head) + '</pre>';
  } catch (e) { $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }"""

JS_ARC_NEW = """  try {
    const { body } = await api('/api/archive/' + encodeURIComponent(name));
    /* ★ R40：JSON 走**美化**（原来 3000+ 行挤成一行，等于打不开）——
       解析得动就 `stringify(…, 2)`；解析不动（截断/非 JSON）就按原文。 */
    let text = body;
    if (/\\.json$/.test(name)) {
      try { text = JSON.stringify(JSON.parse(body), null, 2); } catch (_) { /* 原文 */ }
    }
    const MAX = 300000;                 // 超大文件只给头部，避免页面卡死
    const clip = text.length > MAX;
    const head = clip ? text.slice(0, MAX) : text;
    $('#detail-body').innerHTML =
      (clip ? `<p class="muted">（文件较大，仅显示前 ${Math.round(MAX / 1024)} KB；完整内容见 outputs/${esc(name)}）</p>` : '')
      + '<pre>' + esc(head) + '</pre>';
  } catch (e) {
    /* ★ R40：`<stamp>.packed.json` 只有**真跑**才有（mock / 早期产物没有）⇒
       缺了就回落到老的那份 `<stamp>.run.json`，而不是给用户一句「出错」。 */
    if (/\\.packed\\.json$/.test(name)) {
      return openArchive(name.replace(/\\.packed\\.json$/, '.run.json'));
    }
    $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`;
  }"""

JS_MD_OLD = """    $('#detail-body').innerHTML = renderMd(body);
  } catch (e) { $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }"""

JS_MD_NEW = """    $('#detail-body').innerHTML = linkifyFileBlocks(renderMd(body));
  } catch (e) { $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }"""

JS_LINKIFY_ANCHOR = "/* ── 极简 Markdown 渲染（离线，无外部库）────────────────────────── */"

JS_LINKIFY = """/* ★ R40：产物 md 的「附录 · 全量字段」里，引擎把 packed 文件名**整块**放进一个代码框：
       ```text
       20261012_121240_….packed.json
       ```
   那不是代码，是**指路牌** —— 用户要求「点它可以直接打开」。只在
   「整块就是一个已知后缀的文件名」时生效（不碰正文里出现的文件名，避免误伤）。 */
const FILE_BLOCK_RE = /^[\\w\\u4e00-\\u9fa5（）()·.\\-]{4,120}\\.(?:packed\\.json|run\\.json|run\\.log|md)$/;
function linkifyFileBlocks(html) {
  return String(html).replace(/<pre>([\\s\\S]*?)<\\/pre>/g, (m, inner) => {
    const name = inner.trim();
    if (!name || name.indexOf('\\n') >= 0 || !FILE_BLOCK_RE.test(name)) return m;
    return '<pre class="file-block"><a href="#" data-archive="' + name + '">' + name + '</a></pre>';
  });
}

"""

JS_WELCOME_ANCHOR = "let whisperTimer = null, whisperIdx = 0;"

JS_WELCOME = """/* ★ R40：首屏欢迎语**随时段变**（用户要求「随时间变换打招呼等信息」）。
   分档按**本地小时**；同一档内随机取一句 —— 只在页面初始化时写一次，
   所以不会随日志渲染抖动。`pickWelcome(hour)` 是纯函数，便于探针逐小时驱动。 */
const WELCOME_SLOTS = [
  [[0, 3], ['夜深了，还在想什么？', '这个点还醒着的人，问题往往最好']],
  [[4, 6], ['天快亮了，聊聊吧', '凌晨的安静最适合想硬问题']],
  [[7, 10], ['早上好，今天想弄清什么？', '早，先把手里的困惑说给我听']],
  [[11, 13], ['上午好，随时开始吧', '快到中午了，来一个能想透的问题']],
  [[14, 17], ['下午好，想到什么就问吧', '下午适合把问题往下推一层']],
  [[18, 20], ['傍晚好，今天有什么想问的？', '忙完了，换个问题想想']],
  [[21, 22], ['晚上好，随时开始吧', '晚上的问题往往更深，开始吧']],
  [[23, 23], ['夜深了，最后一问？', '这个点的问题，通常不轻']],
];
function pickWelcome(hour) {
  const h = Number.isFinite(hour) ? hour : new Date().getHours();
  const slot = WELCOME_SLOTS.find(s => h >= s[0][0] && h <= s[0][1]);
  const pool = slot ? slot[1] : ['欢迎回来，随时开始吧'];
  return pool[Math.floor(Math.random() * pool.length)];
}
function paintWelcome() {
  const el = $('#welcome-text');
  if (el) el.textContent = pickWelcome(new Date().getHours());
}

"""

JS_INIT_ANCHOR = "  $('#run-btn').addEventListener('click', onRunBtn);"
JS_INIT_NEW = "  paintWelcome();                    // ★ R40：首屏欢迎语按时段写一次\n" + JS_INIT_ANCHOR


def main() -> int:
    # ── style.css ────────────────────────────────────────────────────────────
    css = rd(CSS, crlf=False)
    css = rep(css, CSS_ACTIONS_OLD, CSS_ACTIONS_NEW, "① style.css 底栏内边距对齐 + `.hidden` 生效规则")
    css = rep(css, CSS_RESET_OLD, CSS_RESET_NEW, "① style.css 恢复出厂设置贴右")
    css = rep(css, CSS_BAR_OLD, CSS_BAR_NEW, "③ style.css 圆点改 fixed 贴页面右缘")
    css = rep(css, CSS_PEND_OLD, CSS_PEND_NEW, "④ style.css `.pend` 不再降透明度")
    wr(CSS, css, crlf=False)

    # ── index.html ───────────────────────────────────────────────────────────
    html = rd(HTML, crlf=False)
    html = rep(html, HTML_BAR_OLD, HTML_BAR_NEW, "③ index.html 把 `#rl-bar` 移出 `#runlog`")
    if 'id="rl-bar"' in html:
        print("  · ③ index.html 已在 body 下，跳过")
    else:
        assert html.count(HTML_BAR_INSERT_ANCHOR) == 1, "body 锚点命中 %d 次" % html.count(HTML_BAR_INSERT_ANCHOR)
        html = html.replace(HTML_BAR_INSERT_ANCHOR, HTML_BAR_INSERT + HTML_BAR_INSERT_ANCHOR)
        print("  ✓ ③ index.html 挂到 body 下（`#drawer-mask` 之前）")
    html = rep(html, HTML_WELCOME_OLD, HTML_WELCOME_NEW, "⑤ index.html 欢迎语包一层 `#welcome-text`")
    wr(HTML, html, crlf=False)

    # ── app.js ───────────────────────────────────────────────────────────────
    js = rd(JS, crlf=True).replace("\r\n", "\n")
    js = rep(js, JS_JSON_OLD, JS_JSON_NEW, "② app.js json 胶囊 → `.packed.json`")
    js = rep(js, JS_TRACK_OLD, JS_TRACK_NEW, "③ app.js `rlTrack()` 改视口坐标")
    js = rep(js, JS_START_OLD, JS_START_NEW, "③ app.js 拖动起点（fixed ⇒ 不再减日志框顶）")
    js = rep(js, JS_LISTEN_OLD, JS_LISTEN_NEW, "③ app.js 补 window scroll 监听")
    js = rep(js, JS_ARC_OLD, JS_ARC_NEW, "② app.js `openArchive` JSON 美化 + packed→run 兜底")
    js = rep(js, JS_MD_OLD, JS_MD_NEW, "② app.js md 预览走 `linkifyFileBlocks`")
    js = ins_before(js, JS_LINKIFY_ANCHOR, JS_LINKIFY, "② app.js 新增 `linkifyFileBlocks`")
    js = ins_before(js, JS_WELCOME_ANCHOR, JS_WELCOME, "⑤ app.js 新增 `pickWelcome`/`paintWelcome`")
    js = ins_before(js, JS_INIT_ANCHOR, "  paintWelcome();                    // ★ R40：首屏欢迎语按时段写一次\n", "⑤ app.js `init()` 里写一次欢迎语")
    wr(JS, js, crlf=True)

    # ── engine_runner.py ─────────────────────────────────────────────────────
    rr = rd(RUNNER, crlf=False)
    rr = rep(rr,
             '    """读 outputs/ 下的归档文件（只允许 .run.log / .run.json）。"""\n'
             '    n = Path(name).name\n'
             "    if not (n.endswith(\".run.log\") or n.endswith(\".run.json\")):\n"
             "        return None",
             '    """读 outputs/ 下的归档文件（只允许 .run.log / .run.json / .packed.json）。"""\n'
             '    n = Path(name).name\n'
             '    # ★ R40：「json」胶囊要能直接打开 `<stamp>.packed.json`（引擎的 packed 原文）。\n'
             "    if not (n.endswith(\".run.log\") or n.endswith(\".run.json\")\n"
             '            or n.endswith(".packed.json")):\n'
             "        return None",
             "② engine_runner.py `read_archive` 放行 `.packed.json`")
    wr(RUNNER, rr, crlf=False)

    # ── 结构性自检（重新读盘）────────────────────────────────────────────────
    bad = []
    css2 = rd(CSS, crlf=False)
    html2 = rd(HTML, crlf=False)
    js2 = rd(JS, crlf=True)
    rr2 = rd(RUNNER, crlf=False)
    if ".sheet-actions.hidden{display:none}" not in css2:
        bad.append("底栏 .hidden 生效规则没落盘")
    if "justify-self:end}" not in css2.split(".sheet-actions #adv-reset")[1][:60]:
        bad.append("恢复出厂设置没贴右")
    if "#rl-bar{position:fixed;right:2px" not in css2:
        bad.append("#rl-bar 不是 fixed 贴右")
    _pend = re.search(r"\.rl-files a\.pend\{([^}]*)\}", css2)
    if _pend and "opacity" in _pend.group(1):
        bad.append(".pend 还在降透明度：%r" % _pend.group(1))
    if html2.count('id="rl-bar"') != 1:
        bad.append("#rl-bar 不是恰好 1 个")
    # ★ 判据别被自己的注释骗到：查「`#runlog` 区块里有没有 `#rl-bar`」，而不是比偏移量
    #   （我插进去的那段注释本身就写着 `#rl-bar`）。
    _a, _b = html2.index('<div id="runlog"'), html2.index('<div class="composer">')
    if 'id="rl-bar"' in html2[_a:_b]:
        bad.append("#rl-bar 还在 #runlog 里（应在 body 直下）")
    if 'id="welcome-text"' not in html2:
        bad.append("欢迎语没包 #welcome-text")
    for k in ("function linkifyFileBlocks(", "function pickWelcome(", "function paintWelcome(",
              "window.addEventListener('scroll', updateRlBar, { passive: true })",
              "const lo = Math.max(0, Math.round(rb.top));",
              ".packed.json", "paintWelcome();"):
        if k not in js2:
            bad.append("app.js 缺：" + k)
    if "data-archive=\"${esc(stamp + '.run.json')}\"" in js2:
        bad.append("json 胶囊还指向 run.json")
    if "packed.json" not in rr2:
        bad.append("read_archive 没放行 packed.json")
    r = subprocess.run(["node", "--check", str(JS)], capture_output=True)
    if r.returncode != 0:
        bad.append("node --check 失败：" + r.stderr.decode("utf-8", "replace")[:200])
    else:
        print("  ✓ node --check app.js 通过")
    r2 = subprocess.run([str(Path(r"C:/Users/18432/AppData/Local/Programs/Python/Python313/python.exe")),
                         "-c", "import ast,pathlib;ast.parse(pathlib.Path(r'%s').read_text(encoding='utf-8'))"
                         % str(RUNNER)], capture_output=True)
    if r2.returncode != 0:
        bad.append("engine_runner.py AST 失败：" + r2.stderr.decode("utf-8", "replace")[:160])
    if bad:
        print("★ 结构性自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("结构性自检：全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
