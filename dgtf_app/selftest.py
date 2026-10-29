# -*- coding: utf-8 -*-
"""Meta-DGTF 应用层 · 端到端自检（需先启动 server.py）。

用法：
    python dgtf_app/server.py            # 另开一个终端
    python dgtf_app/selftest.py [--base https://127.0.0.1:8765]  # HTTP 请显式传 --base

走完「提交 → 实时日志 → 完成 → 取产物 → 历史检索」全链路（mock，零花费），
并在结束时删掉它自己产生的 mock 产物 —— 自检无副作用。
"""

from __future__ import annotations

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import json
import re
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
import ssl
ssl._create_default_https_context = ssl._create_unverified_context  # 本机自签名测试
from pathlib import Path

import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dgtf_engine"))
import dashboard  # noqa: E402
import daosheng_mode  # noqa: E402  ★ T3 道生专属模式（离线计划/回退链/记忆注入）
import engine_runner as runner  # noqa: E402
import library  # noqa: E402
import outputs_index as oi  # noqa: E402
import params as prm  # noqa: E402
import local_chain as lchain  # noqa: E402  ★ 本地链路判据（8772 推理 + 8773 适配）

PASS: list[str] = []
FAIL: list[str] = []
_ACCESS_TOKEN = os.environ.get("DGTF_ACCESS_TOKEN", "").strip()
_AUTH_HEADERS = ({"Cookie": "dgtf_token=" + _ACCESS_TOKEN}
                 if _ACCESS_TOKEN else {})


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  \u2713 " if cond else "  \u2717 ") + name + (("  \u2014 " + detail) if detail else ""))


def _get(base: str, path: str):
    req = urllib.request.Request(base + path, headers=dict(_AUTH_HEADERS))
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _post(base: str, path: str, obj: dict):
    req = urllib.request.Request(
        base + path, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json", **_AUTH_HEADERS}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _raw(base: str, path: str) -> str:
    req = urllib.request.Request(base + path, headers=dict(_AUTH_HEADERS))
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def _rule(css: str, sel: str) -> str:
    """取某条 CSS 规则的声明体（第一条匹配）。"""
    m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else ""


def _rules(css: str, sel: str) -> list[str]:
    """同名选择器的**全部**规则体（.tasks 在媒体查询里还有一份，别被它命中）。"""
    return [m.group(1) for m in re.finditer(re.escape(sel) + r"\s*\{([^}]*)\}", css)]


def check_r39_frontend(css: str, js: str, html: str) -> None:
    """★R39 的界面判据（用户 16 图 / 9 条）—— 单独成函数，变异体可直接喂「改坏的」输入驱动。"""

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
    # ★ R40 改口径：圆点从「日志框内的 `absolute`」提到**页面最右缘的 `fixed`**
    #   （用户要求「滚动点改到外页面最右侧显示」）⇒ 判据改成 fixed + right:2px。
    check("★R40 滚动点**贴页面最右缘**（`position:fixed` + `right:2px`）",
          "position:fixed" in _rule(css, "#rl-bar").replace(" ", "")
          and "right:2px" in _rule(css, "#rl-bar").replace(" ", ""),
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
    # ★ R40 改口径：「恢复出厂设置」从 `justify-self:start` 变成 **`end`（贴右）**
    check("★R39 底栏改 `1fr auto 1fr` 三列网格：保存落在**中间列**（与右侧按钮宽无关）",
          "grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);" in css
          and "display:grid" in _rule(css, ".sheet-actions").replace(" ", "")
          and ".sheet-actions #adv-save{grid-column:2;grid-row:1;justify-self:center}" in css
          and ".sheet-actions #adv-reset{grid-column:3;grid-row:1;justify-self:end}" in css,
          _rule(css, ".sheet-actions").strip()[:70])

    # ── 需求 9：滚动圆点的上下行程 —— 两条路共用一条轨迹、且限在本窗口内 ────
    #   ★★ 这是个**真 bug**：`updateRlBar()` 的 `top` 带「正文区顶 − 日志框顶」的偏移
    #     （= 头栏高度），而拖拽的 `onMove` 钳在 `[0, 轨道]`（**少了那个偏移**）⇒
    #     一按住圆点拖动它就往上跳约一个头栏，看着像「拖动不跟手 / 跑出范围」。
    # ★ R40 改口径：圆点 `fixed` ⇒ 轨迹用**视口坐标**（`rb.top` / `rb.bottom`），
    #   不再减日志框顶；「只能在这个日志窗口的正文范围内滑动」的语义不变。
    check("★R40 抽 `rlTrack()` 作**唯一**轨迹来源（视口坐标，滚动 + 拖拽共用同一 lo/hi）",
          "function rlTrack()" in js
          and "const lo = Math.max(0, Math.round(rb.top));" in js
          and js.count("rlTrack()") == 4,
          "rlTrack() 出现 " + str(js.count("rlTrack()")) + " 次（应 1 定义 + 3 调用）")
    check("★R39 拖拽改用 `[t.lo, t.hi]`，旧口径 `[0, track]` 已消失",
          "Math.max(t.lo, Math.min(t.hi, startTop + dy))" in js
          and "Math.max(0, Math.min(track, startTop + dy))" not in js
          and "bd.scrollTop = (top / track) * over" not in js, "")
    check("★R40 轨迹下端取 min(正文区底, 日志框底) − 直径（圆点不许钻出日志窗口）",
          "Math.min(rb.bottom, rbox.bottom)) - RL_DOT" in js, "")

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
    # ★ R44 改口径：文案本身换了（用户给定新文案），判据的**意图不变**
    #   —— 仍然是「两处必须同步」，只是字面跟着新版走。
    _ph = "发给Meta-DGTF 一起去探索吧 ..."
    check("★R39 首屏提示语**两处同步**（index.html 的 placeholder + app.js 的 Q_PLACEHOLDER）",
          _ph in html and _ph in js, "html=" + str(_ph in html) + " js=" + str(_ph in js))


def check_r40_frontend(css: str, js: str, html: str, runner_src: str) -> None:
    """★R40 的界面判据（用户 6 图 / 5 条）—— 单独成函数，变异体可直接喂坏输入驱动。"""

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
          "data-archive=\"${esc(stamp + '.packed.json')}\"" in js
          and "data-archive=\"${esc(stamp + '.run.json')}\"" not in js, "")
    check("★R40 服务端放行 `.packed.json`（`read_archive` 的白名单）",
          'n.endswith(".packed.json")' in runner_src, "")
    check("★R40 JSON 打开时**美化**（`stringify(…, 2)`，否则 3000 行挤成一行）",
          "JSON.stringify(JSON.parse(body), null, 2)" in js, "")
    check("★R40 缺 `.packed.json`（mock / 早期产物）时**回落** `.run.json`，不报错",
          "name.replace(/\\.packed\\.json$/, '.run.json')" in js, "")
    #   产物 md 的「附录·全量字段」里，引擎把 packed 文件名**整块**放进代码框 —— 那里是**指路牌**。
    check("★R40 产物 md 里「整块就是一个文件名」的代码框 → 可点链接（`linkifyFileBlocks`）",
          "function linkifyFileBlocks(" in js and "FILE_BLOCK_RE" in js
          and "linkifyFileBlocks(renderMd(body))" in js
          and "packed\\.json|run\\.json|run\\.log|md" in js, "")

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


def check_r41_frontend(css: str) -> None:
    """★R41 的界面判据：分组行标题要**真的居中**（于是和底栏居中的「保存」同轴）。"""

    def _val(body: str, prop: str):
        _m = re.search(r"(?:^|;|\s)" + prop + r"\s*:\s*([^;}]+)", body)
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


def check_r42_server(srv_src: str) -> None:
    """★R42：局域网访问（`--lan`）与访问口令（`--token`）—— 默认必须**不暴露**。"""

    check("★R42 默认仍**只监听 127.0.0.1**（`--host` 的默认值没被改掉）",
          'ap.add_argument("--host", default="127.0.0.1"' in srv_src, "")
    check("★R42 `--lan` ⇒ 绑 `0.0.0.0`（语义化写法，不是让用户自己记 IP）",
          'ap.add_argument("--lan", action="store_true"' in srv_src
          and 'host = "0.0.0.0" if args.lan else args.host' in srv_src, "")
    check("★R42 启动时**打印局域网网址**（自己探本机内网 IP，省得去 ipconfig）",
          "def lan_ipv4()" in srv_src and "局域网已打开" in srv_src
          and "socket.AF_INET" in srv_src, "")
    check("★R42 口令闸在 `do_GET` / `do_POST` **各一处**（两处都不漏）",
          srv_src.count("self._guard(") >= 2
          and "def _guard(self, mutate" in srv_src, "")
    check("★R42 口令**默认为空即全放行** ⇒ 不改默认行为（只在 `--token` 时生效）",
          '_TOKEN = ""' in srv_src
          and 'if not _TOKEN:\n            return True' in srv_src, "")
    check("★R42 首次带 `?t=` 进来就**种 cookie**（手机上存书签即可，不用做登录页）",
          "dgtf_token=" in srv_src and "SameSite=Strict" in srv_src
          and "HttpOnly" in srv_src and "_send_cookies" in srv_src
          , "send_cookies 出现 " + str(srv_src.count("_send_cookies")) + " 次")
    check("★R42 口令太短**拒绝启动**（不留一个没保护的监听）",
          "口令太短" in srv_src and "return 2" in srv_src, "")
    check("★R42 抽 `make_server()`：验收能在**同一个进程**里起服务（sandbox 会清子进程）",
          "def make_server(" in srv_src
          and "srv = make_server(host, args.port, token=token" in srv_src, "")


def check_r44_frontend(css: str, js: str, html: str, srv_src: str,
                       lib_src: str, dp_src: str) -> None:
    """★R44 的界面 / 导入判据（用户 6 图 / 6 条）。"""

    _lib, _dp = lib_src or "", dp_src or ""

    # ── ① 读数台实时更新 ────────────────────────────────────────────────────
    check("★R44 读数台**自动刷新**（5s 一轮，且只在「读数台」这页可见时拉）",
          "setInterval(() => {" in js and "classList.contains('active')" in js
          and "loadDash();" in js and "5000" in js, "")
    check("★R44 切到「读数台」时**立刻**拉一次（不等下一个周期）",
          "if (key === 'dash-stats') loadDash();" in js, "")

    # ── ② 点对话框 / 发送键 / 首屏空白 ⇒ 抽屉自动收起 ──────────────────────
    # ★ 钉**判断行本身**：变异体「if (false && …contains('drawer-open'))」串还在、
    #   行为没了 —— 只查「串在不在」会被它穿过去（M39 实测）。
    # ★ 锚点要钉「判断行」，但**换行必须归一**：selftest 的 `js` 是 HTTP 原文（CRLF），
    #   带 `\n` 的锚点在 CRLF 上永远不命中（收紧后本轮实测翻红过一次）。
    _js_n = js.replace("\r\n", "\n")
    check("★R44 点**对话框**（含胶囊 / 回形针 / 发送键）⇒ 收起抽屉",
          "if (document.body.classList.contains('drawer-open')\n" in _js_n
          and "e.target.closest('.composer')" in js and "closeDrawer();" in js, "")
    check("★R44 点**首屏空白区**也收起（只在空态判定，不动运行态）",
          "stage-empty" in js and "e.target.closest('main.stage')" in js, "")

    # ── ③ 首屏文案 + 字号 ───────────────────────────────────────────────────
    _ph = "发给Meta-DGTF 一起去探索吧 ..."
    check("★R44 首屏文案两处同步（index.html 的 placeholder + app.js 的 Q_PLACEHOLDER）",
          _ph in html and _ph in js, "")
    check("★R44 输入框字号**调小一档**（≤14px）",
          re.search(r"font-size:\s*(1[0-4](\.\d+)?)px", _rule(css, "textarea#question")) is not None,
          (_rule(css, "textarea#question") or "").strip()[:48])

    # ── ④ 首屏不出现滚动点 ──────────────────────────────────────────────────
    check("★R44 `updateRlBar()` 里判「日志窗口自己是否可见」（隐藏就一律不画点）",
          "_box.classList.contains('hidden')" in js
          and "const _box = $('#runlog');" in js, "")
    check("★R44 空态那条**早返回**路径也会收一次点（否则点会留在上次的位置）",
          "updateRlBar();   // ★ R44" in js, "")

    # ── ⑥ 首屏以对话框为基准居中 + 上移 ────────────────────────────────────
    check("★R44 首屏以**欢迎语/输入框空隙中心**为基准上下左右居中",
          "centerHomeHero" in js and "--home-shift" in js
          and "top:var(--home-shift,0px)" in css
          and "padding-bottom:0" in css, "")

    # ── ⑤ 导入：前端管线 ────────────────────────────────────────────────────
    check("★R44 导入控件是**真按钮**点隐藏 input（不再靠 label 转发）",
          'id="anchor-pick"' in html
          and "if (_ap && _af) _ap.addEventListener('click', () => _af.click());" in js
          and '<label class="chk"><input type="file"' not in html, "")
    check("★R44 前端按**字节**读（`ArrayBuffer` + base64），不再 `File.text()`",
          "function fileToB64(" in js and "readAsArrayBuffer" in js and "btoa(s)" in js
          and "content: await f.text()" not in js, "")
    check("★R44 前端有上限与分批（50 个 / 单文件 100MB / 每批 48MB）",
          "LIB_MAX_FILES = 50, LIB_MAX_MB = 100" in js and "LIB_BATCH_MB = 48" in js
          and "超过单文件上限" in js, "")
    check("★R44 逐文件结果摆出来（成功 / 失败原因），不再「点了没反应」",
          "function importPaint(" in js and ".import-detail" in css
          and "r.results" in js and "importRows" in js, "")

    # ── ⑤ 导入：服务端上限 + 解析 + 留档 ────────────────────────────────────
    check("★R44 服务端上限：单次 50 个 / 单文件 100MB",
          "MAX_FILES = 50" in _lib and "MAX_FILE_BYTES = 100 * 1024 * 1024" in _lib, "")
    # ★ 同样钉**判断行**：常量定义还在文件里 ⇒ 只查名字的话「把 if 删掉」也能绿（M50 实测）。
    check("★R44 上传体积闸（超过就 413，别把内存吃光）",
          "if _n > MAX_UPLOAD_BYTES:" in srv_src and "413)" in srv_src, "")
    check("★R44 入参**双形态**：`{name,b64}`（二进制）与 `{name,content}`（老的文本）都收",
          "def _decode_entry(" in _lib and 'f.get("b64")' in _lib
          and 'f.get("content")' in _lib, "")
    check("★R44 原始文件留档 `anchors/_raw/`（解析失败也不丢原件）",
          "RAW_DIR = ANCHORS_DIR" in _lib and "(RAW_DIR / n).write_bytes(data)" in _lib, "")
    check("★R44 删除时**原件一起删**（不留孤儿）",
          "_extras = [RAW_DIR / n]" in _lib, "")
    check("★R44 长文档**分块**进锚点（原来只取前 2000 字）",
          "CHUNK_CHARS = 2000" in _lib and '"part": k,' in _lib
          and "chunks[:MAX_CHUNKS_PER_FILE]" in _lib, "")
    check("★R44 解析器只依赖标准库（本机没有 pypdf/python-docx/PIL/tesseract）",
          _dp != "" and "import zipfile" in _dp and "import zlib" in _dp
          and not re.search(r"^import (pypdf|PyPDF2|docx|openpyxl|pptx|fitz|PIL|pytesseract)",
                            _dp, re.M), "")
    check("★R44 解析器覆盖 docx/xlsx/pptx/pdf/图片/OLE/纯文本",
          all(k in _dp for k in ("def parse_docx", "def parse_xlsx", "def parse_pptx",
                                 "def parse_pdf", "def parse_image", "def parse_ole")), "")
    check("★R44 解析失败**不静默**：返回 ok=False + 原因（不抛异常）",
          '"ok": False' in _dp and 'return {"ok": False' in _dp, "")


def check_r45_frontend(css: str, js: str, html: str, srv_src: str,
                       lib_src: str) -> None:
    """★R45 的界面 / 归类判据（用户 3 图 / 3 条）。

    ★ 与 R44 第 4 条重复的那条（首屏滚动点）**在这里收紧** ——
      用户**第二次**报同一件事 ⇒ 光靠「调用点」不够，必须改成**状态驱动**。
    """

    _lib = lib_src or ""

    # ── ① 导入的文件要**显示出来** ──────────────────────────────────────────
    # ★★ R48-3（用户图3「回形针不要有上标」）：R45 那两条「回形针上要有计数气泡」
    #   **语义反转** —— 现在是「**不许有**」（判据在下面 `★R48-3` 段）。
    #   ★ 判据守的**行为**没变：仍然是「导入的文件数量要能被看到」，
    #     只是载体从「回形针角标」换成了「小窗标题 + 悬停提示」。
    #     所以不是删掉判据，而是把它挪到新载体上。

    check("★R45 有**可展开的已导入清单** `#attach-panel`",
          'id="attach-panel"' in html and "attach-panel hidden" in html, "")
    check("★R45 清单里每行有**文件名 + 大小 + 删除**",
          "data-apname" in js and "data-apdel" in js, "")
    check("★R45 清单有**关闭**键，且绑了收起",
          'id="ap-close"' in html and "_apx.addEventListener('click'" in js, "")
    # ★★ R48-3：原来这条判「点**徽章**展开清单」—— 徽章已移除，
    #   点击分派改成「点**回形针本身**」：有已导入文件 ⇒ 开关小窗；没有 ⇒ 开选择框。
    #   ★ 判据守的**行为**没变（「看一眼清单」仍然只点一下），换的是那个可点的目标。
    check("★R49 点**回形针**统一开文件选择框（不再按是否有导入分派小窗）",
          "_at.addEventListener('click', () => {" in js
          and "const f = $('#anchor-file');" in js
          and "if (f) f.click();" in js, "")

    check("★R49 文件选择/粘贴统一显示 composer 缩略图",
          "attachAppPastedFiles" in js and "attachDshPastedFiles" in js
          and "dsh-paste-preview" in js, "")
    check("★R45 删除走真实接口 `/api/library/delete`",
          "async function removeImported" in js
          and "/api/library/delete" in js, "")
    check("★R45 `loadLocal()` 同步刷徽章与清单（切页 / 删除后不残留旧数）",
          "paintAttach();" in js, "")

    # ── ② 同一任务的子问题**归类在最初的问题里** ─────────────────────────────
    check("★R45 服务端按「任务」聚类（`cluster_groups`），不只是按 query 平铺",
          "def cluster_groups(" in _lib and '"clusters": lib.cluster_groups(_flat)' in srv_src, "")
    check("★R45 派生判据用**引擎自己的形态**（不硬编码业务词）",
          '_DERIVED_RE = re.compile' in _lib
          and "是否存在.*的官方指引" in _lib, "")
    check("★R45 子问题**就近挂到根问题**（时间不晚于它、最近的那个）",
          "cands = [r for r in roots if (r.get(\"latest\") or 0) <= t]" in _lib, "")
    check("★R45 全是子问题（无根）时不丢组（原样返回）",
          "return sorted(derived, key=lambda x: x.get(\"latest\") or 0, reverse=True)" in _lib, "")
    check("★R45 前端渲染成**树**（`.web-cluster` > 根 + `.wg-kids` > 子）",
          "web-cluster" in js and "wg-kids" in js and "wg-sub" in js, "")
    check("★R45 前端有**同形兜底** `clusterLocal`（旧后端也不降级）",
          "function clusterLocal(" in js and "WEB_DERIVED_RE" in js, "")
    check("★R45 CSS 用**缩进 + 竖线**表达从属（.wg-kids 的声明体非空）",
          (lambda: (lambda m: bool(m) and "border-left" in m.group(1))(
              re.search(r"\.web-cluster\s+\.wg-kids\{([^}]*)\}",
                        re.sub(r"/\*[\s\S]*?\*/", "", css))))(), "")

    # ── ③ 首屏**不许**看见滚动点（R44 第 4 条的彻底修法）──────────────────────
    check("★R45 `updateRlBar()` 把「页面状态」也当判据（stage-empty / panel-open）",
          "document.body.classList.contains('stage-empty')" in js
          and "document.body.classList.contains('panel-open')" in js, "")
    check("★R45 CSS **状态兜底**：首屏 / 面板态下强制 `#rl-bar` 不可见（不依赖 JS）",
          re.search(r"body\.stage-empty\s+#rl-bar", css) is not None
          and re.search(r"body\.panel-open\s+#rl-bar", css) is not None, "")
    check("★R45 兜底规则**压得过** `.on`（带 !important 的 opacity:0）",
          (lambda: (lambda m: bool(m) and "!important" in m.group(1))(
              re.search(r"body\.stage-empty\s+#rl-bar[^{]*\{([^}]*)\}",
                        re.sub(r"/\*[\s\S]*?\*/", "", css))))(), "")
    check("★R45 兜底规则排在 `#rl-bar.on` **之后**（同特异性下靠源顺序覆盖）",
          (lambda: (lambda c: c.find("#rl-bar.on") >= 0
                    and c.find("body.stage-empty #rl-bar") > c.find("#rl-bar.on"))(
              re.sub(r"/\*[\s\S]*?\*/", "", css)))(), "")
    check("★R45 另一条早退路径（空白新会话）也收点",
          js.count("updateRlBar();") >= 3, "")


def _r47_func_body(src: str, fn: str) -> str:
    """抠出 `def <fn>(` 到下一个顶层 `def` 之间的函数体（用于「函数内不许出现 X」类判据）。

    ★ 为什么要有这个辅助函数：把这段逻辑塞进 `check(..., <lambda 嵌套三层的表达式>)`
      里，括号一多就写错（本轮实测直接 `SyntaxError: unmatched ')'`，而且报错行
      离真正的错处很远）。抽成**有名函数**后既能被自证脚本单独喂样本，也不会写错。
    """
    key = "def " + fn + "("
    if key not in src:
        return ""
    t = src[src.index(key):]
    # ★★ 必须取**第一个**顶层分隔 —— 写成 `rfind`（最后一个）会把后面**所有**
    #   函数一起吃进来：实测 `read_local` 的函数体被撑到文件末尾，里面混进别的
    #   函数的 `read_text` ⇒ 判据对本函数完全失效（「读别人的代码下自己的结论」）。
    j = t.find("\n\n\ndef ")
    return t if j < 0 else t[:j]


def _r47_no_bare_read(src: str) -> bool:
    """`read_local()` 的函数体里不许出现**裸 `read_text`**（读盘必须走 `_safe_read`），
    且必须真的调了 `_safe_read`。

    ★ 这条判据的价值在于**防未来的退化**：我上一版补丁就在函数尾部留了一段
      「不可达的旧读法」——它 `return None` 之后还 `read_text`，今天无害，
      但只要有人删掉上面那个看似多余的 `return None`，**安全白名单就被静默绕过**。
    """
    seg = _r47_func_body(src, "read_local")
    return bool(seg) and "read_text" not in seg and "_safe_read(p)" in seg


def _r47_dead_after_return(src: str) -> bool:
    """**任何函数体内**是否在 `return None`（或任何 `return`）之后还有语句。

    这是「死代码」的**结构性定义** —— 比找某个标记串更本质。用 `ast` 判：
    若某个 `Return` 语句之后、在**同一个 block** 里还有非 `Return`/非 docstring
    语句，那就是不可达代码（Python 的 `return` 之后同层语句永远不执行）。

    ★ 为什么要**全文**扫而不是只看 `read_local`：本轮实测同一颗雷先后出现在
      **三个位置**（`read_local` 尾部两次、`_safe_read` 里一次）。只扫一个函数
      会让其余位置漏网 —— 而那处恰是最危险的（引用了不存在的 `base`）。
    """
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return True                       # 解析不了 ⇒ 当有问题处理（别静默放行）

    def _always_returns(st) -> bool:
        """该语句是否**必然**返回（用于判「它之后是死代码」）。

        ★ 第一版只认裸 `return`，于是漏掉了本轮的真形态：
              try:      return p.read_text()
              except:   return None
              # ↓ 这一行是死的（但它在 FunctionDef.body 里、前一条是 `Try` 不是 `Return`）
              return (ANCHORS_DIR / base).read_text(...)
          实测 `FunctionDef.body = [Try, Return]`、`Try.body=[Return]`、
          `handlers[0].body=[Return]` ⇒ **每个分支都 return** ⇒ 后面的 `Return` 不可达。
        """
        if isinstance(st, ast.Return):
            return True
        if isinstance(st, ast.Raise):
            return True
        if isinstance(st, ast.If):
            return (bool(st.body) and bool(st.orelse)
                    and all(_always_returns(x) for x in st.body)
                    and all(_always_returns(x) for x in st.orelse))
        if isinstance(st, ast.Try):
            bodies = [st.body] + [h.body for h in st.handlers]
            if st.finalbody and all(_always_returns(x) for x in st.finalbody):
                return True
            return all(b and all(_always_returns(x) for x in b) for b in bodies)
        if isinstance(st, (ast.With, ast.AsyncWith)):
            return bool(st.body) and all(_always_returns(x) for x in st.body)
        return False

    def _blocks(node):
        out = []
        for fld in ("body", "orelse", "finalbody"):
            b = getattr(node, fld, None)
            if isinstance(b, list):
                out.append(b)
        for h in getattr(node, "handlers", []) or []:
            if isinstance(h, ast.ExceptHandler) and isinstance(h.body, list):
                out.append(h.body)
        return out

    for node in ast.walk(tree):
        for blk in _blocks(node):
            for i, st in enumerate(blk):
                if _always_returns(st) and i + 1 < len(blk):
                    rest = blk[i + 1:]
                    # 只允许「裸字符串常量」（老式 docstring）；其余都是真语句。
                    if any(not (isinstance(x, ast.Expr)
                                and isinstance(x.value, ast.Constant))
                           for x in rest):
                        return True
    return False


def check_r47_frontend(css: str, js: str, html: str, srv_src: str,
                       lib_src: str) -> None:
    """R47 的界面判据（用户 3 图）。

    A) 「点开导入的文件没显示内容」—— `read_local()` 查找链漏了 `ANCHORS_DIR`。
    B) 「不要在下面对话框展开，保持原界面一致」—— 清单改成**回形针右侧小窗**，
       窗内是**小图标**、每个图标**右上角 ×** 点一下删掉该文件。
    C) 顺带堵住 `read_local()` 读任意文件（`.env` 泄露 API Key）。
    """
    _lib = lib_src or ""
    _css = re.sub(r"/\*[\s\S]*?\*/", "", css)      # 去注释再判（否则注释里的字会干扰）
    # ★★ JS 也必须**去注释再判**（本轮踩到）：`_css` 去了注释、`_jsnc` 没去，
    #   于是「我为了解释『别再用老类名』而在注释里写下老类名」反而把判据顶红
    #   —— 判据读到的不是实现，而是我的说明文字。
    #   去注释用与 `_css` 同源的手法（块注释 + 行注释），并保留字符串字面量
    #   之外的内容不动（JS 里正则/字符串含 `//` 会误删，故只删**行首**的 `//`
    #   与整块 `/* */`，这覆盖本仓库全部真实注释）。
    _jsnc = re.sub(r"/\*[\s\S]*?\*/", "", js)
    _jsnc = re.sub(r"(?m)^\s*//[^\n]*$", "", _jsnc)

    # ── A/C：读文件（服务端）─────────────────────────────────────────────
    check("★R47 `read_local()` 查找链含导入目录 `ANCHORS_DIR`（否则点开必 not found）",
          "roots = (ANCHORS_DIR, ANCHORS_DIR / \"_raw\"," in _lib, "")
    # ★★ 「无死代码」判据必须**全文扫**，别只扫一个函数。
    #   本轮实测：同一颗雷先后出现在**三个位置**（`read_local` 尾部两次、
    #   `_safe_read` 里一次）。上一版判据写的是「在 `read_local` 函数体里找」，
    #   于是 `_safe_read` 里那处**漏网**，判据照样绿 —— 而它恰好最危险
    #   （那段不可达代码引用了 `_safe_read` 里不存在的 `base`）。
    #   标记串 `# ★ 富格式文件：原名存的是` 足够特殊，全文扫不会误报。
    #   再加一条**结构性**判据：**任何函数体内**都不许出现「`return None` 之后
    #   还有语句」—— 那才是「死代码」的定义，比找标记串更本质。
    check("★R47 全文件**没有死代码尾巴**（`return None` 之后不留语句）"
          "—— 判据此前只扫 `read_local`，漏掉了 `_safe_read` 里的同一颗雷",
          "    return None\n    # ★ 富格式文件：原名存的是" not in _lib
          and not _r47_dead_after_return(_lib), "")
    check("★R47 `read_local()` 的读盘**全部经 `_safe_read`**（无裸 read_text 绕过白名单）",
          _r47_no_bare_read(_lib), "")
    check("★R47 `_safe_read()` **自身**也不含裸 read_text 之外的读盘"
          "（它只该有那一条 `p.read_text` 实现本体）",
          _r47_func_body(_lib, "_safe_read").count("read_text") == 1, "")
    check("★R47 富格式解析稿 `<原名>.txt` 也能读到（docx/pdf 点开不该 404）",
          'base + ".txt"' in _lib, "")
    check("★R47 只读**文本类白名单**扩展名（`.env` 天然被挡，不靠黑名单列不全）",
          "_READABLE_EXT" in _lib and ".json" in _lib, "")
    check("★R47 点开头文件名一律不读（`.env` / `.netrc` / `.gitignore`）",
          'base.startswith(".")' in _lib, "")
    check("★R47 落盘前**再挡一次**扩展名（防别处绕过白名单）",
          "p.suffix.lower() not in _READABLE_EXT" in _lib, "")
    check("★R47 详情接口的 `name` 是**解码后**的文件名（不是 %E8 编码串）",
          "_nm = unquote(m.group(1))" in (srv_src or ""), "")

    # ── B：小窗 / 图标 / 角标 ────────────────────────────────────────────
    # ★★ 判据**不许写死 `absolute`**：实现从 `absolute` 改成 `fixed` 是**正确的
    #   改进**（`fixed` 同样脱离文档流，且不会被带 `transform` 的祖先当包含块）。
    #   写死 `absolute` 会把改进判成回归 —— 本轮实测 `pos=fixed` 被误判 FAIL。
    #   要守的是「**脱离文档流**」这个行为，不是某一个具体取值。
    check("★R47 小窗**脱离文档流**（`absolute` / `fixed` 皆可，不许 `static`/`relative`）",
          (lambda: (lambda m: bool(m) and ("absolute" in m.group(1)
                                           or "fixed" in m.group(1)))(
              re.search(r"(?m)^\.attach-panel\{([^}]*)\}", _css)))(), "")

    check("★R47 定位基准 `.composer` 有 `position:relative`",
          (lambda: (lambda m: bool(m) and "relative" in m.group(1))(
              re.search(r"(?m)^\.composer\{([^}]*)\}", _css)))(), "")
    check("★R47 小窗**不再**在输入框下方撑开（老写法 margin:8px 4px 2px 已去）",
          "margin:8px 4px 2px" not in _css, "")
    check("★R47 列表渲染成**图标格** `.ap-tile`（不再是 `.ap-row` 整行）",
          "ap-tile" in _jsnc and "ap-row" not in _jsnc, "")
    check("★R47 每个图标里有删除键（`data-apdel` 复用原删除链路）",
          re.search(r'class="ap-tile"[\s\S]{0,400}?data-apdel=', _jsnc) is not None, "")
    check("★R47 删除键的字面是 **×** 且带无障碍标签",
          "\u00d7</button>" in _jsnc and "aria-label=" in _jsnc, "")
    # ★★ 判据守**行为**（「贴在图标的右上角」），不写死偏移量。
    #   原来写死 `top:-5px`/`right:-5px`，R48-2 把角标跟着图标一起缩到 -4px
    #   （**正确改进**，比例才不失衡）时被判成回归 —— 与「不许把 absolute 改成 fixed」
    #   是同一种错：把取值当行为。改成：偏移量**是负的**（即向内收、压在角上）且
    #   水平/垂直偏移**同号等量**（真正的「右上角」而不是某个边角混搭）。
    check("★R47/R48-2 角标 × 贴在图标的**右上角**（偏移量为负、左右等量 —— "
          "不写死具体 px，R48-2 已按比例缩到 14px）",
          (lambda: (lambda m: bool(m)
                    and (lambda t, r: t.startswith("-") and r.startswith("-")
                         and t == r.replace("right", "top").replace("top", "top"))(
                        re.search(r"top:(-?\d+px)", m.group(1)).group(1),
                        re.search(r"right:(-?\d+px)", m.group(1)).group(1)))(
              re.search(r"\.ap-tile \.rm\{([^}]*)\}", _css)))(), "")

    check("★R47 角标 × **常显**（`opacity:1`）—— 用户原话「右上角标一个 x 按钮」，"
          "做成悬停才显等于没实现（第一版就是这么错的，截图里整个 × 看不见）",
          (lambda: (lambda m: bool(m) and "opacity:1" in m.group(1))(
              re.search(r"\.ap-tile \.rm\{([^}]*)\}", _css)))(), "")
    check("★R47/R48 小窗定位**交给 JS 现算**（`position:fixed` + `placeAttachPanel()`）"
          "—— 落点按回形针的真实坐标算；纯 CSS 做不到（回形针在输入框内部，"
          "而它的 x 是 flex 排出来的、随胶囊文字长度变）",
          (lambda: (lambda m: bool(m) and "position:fixed" in m.group(1))(
              re.search(r"(?m)^\.attach-panel\{([^}]*)\}", _css)))()
          and "function placeAttachPanel(" in js
          and "placeAttachPanel()" in js,
          "")
    # ★ 老写法只在**主规则**里算违规：`.attach-panel{top:88px}` + 窄屏 `@media`
    #   兜底里的 `bottom:calc(100% + 8px)` 是**有意的降级方案**（JS 没跑到时才用），
    #   拿全文 `in _css` 判会把它一起判红（实测误红）。只有**主规则**里出现
    #   才说明「又回退成贴输入框上沿」。
    check("★R47 小窗**不许**再贴输入框上沿（老写法 `bottom:calc(100% +` 已去）"
          "—— 窄屏 `@media` 的兜底不算（那是有意的降级）",
          (lambda: (lambda m: bool(m) and "bottom:calc(100%" not in m.group(1))(
              re.search(r"(?m)^\.attach-panel\{([^}]*)\}", _css)))(), "")
    # ★★ R48-2（用户图2 的红箭头）：落点**改回「回形针右侧、输入框内部」**。
    #   R47 那版落点是「输入框正上方右对齐」（我为「零遮挡」自己挑的），
    #   用户这次**明确否掉**了它 ⇒ 旧判据（`cr.right + M` / `cRight - w` /
    #   `cTop - M - h` / `#welcome`）在新实现里**全部不存在**。
    #   ★ 这不是「放宽阈值」，是**判据随实现更新**：要守的行为没变
    #     （小窗要贴在回形针旁边、且不许压住任何**控件**），
    #     变的是「哪一档是主路径」。
    #   新降级链：① 回形针**右侧**（用户要的）⇒ ② 回形针**正上方**
    #              ⇒ ③ 夹进视口兜底。
    check("★R48 定位**主路径 = 回形针右侧**（用户图2 的要求，不再是输入框正上方）",
          "r.right + M" in js and "const fitsRight" in js, "")
    check("★R48 有**降级链**：右侧放不下 ⇒ 回形针正上方（`r.top - M - h`）",
          "r.top - M - h" in js, "")
    # ★★ 「不许压**发送键**」是这条需求真正的**行为**约束：
    #   用户要小窗落在输入框内部，输入框里唯一「压住就出事」的是发送键
    #   （压住就没法发消息）。⇒ 实现必须**取发送键的左缘当右墙**。
    check("★R48 取**发送键的左缘**当右墙（压住发送键 = 没法发消息，是硬约束）",
          "$('#run-btn')" in js and "sr.left - M" in js and "wallRight" in js, "")
    check("★R48 与回形针**垂直居中**（视觉上是「从回形针旁边长出来」）",
          "r.top + r.height / 2" in js and "cy - h / 2" in js, "")

    check("★R47 定位取的是**回形针按钮**的真实坐标（`#attach-btn`）",
          "$('#attach-btn')" in js, "")
    # ★★ R48-2：图标格**变小**（用户图2「文件图形可以适当小一点」）。
    #   守的是**行为**（「比原来小」），不是某个具体像素 —— 所以判「≤ 44×48」
    #   而不是「== 40×44」（写死取值会把以后再微调判成回归）。
    #   原来 52×56 ⇒ 判据上界取 44/48，既证明确实小了、又不锁死。
    check("★R48-2 图标格**变小**了（≤ 44×48，原来是 52×56）"
          "—— 判据守「比原来小」，不写死具体 px",
          (lambda: (lambda m: bool(m)
                    and (lambda w, h: 0 < w <= 44 and 0 < h <= 48)(
                        int(re.search(r"width:(\d+)px", m.group(1)).group(1)),
                        int(re.search(r"height:(\d+)px", m.group(1)).group(1))))(
              re.search(r"\.ap-tile\{([^}]*)\}", _css)))(), "")
    check("★R48-2 角标 × 也跟着缩（≤ 14px，跟图标比例不失衡）",
          (lambda: (lambda m: bool(m)
                    and int(re.search(r"width:(\d+)px", m.group(1)).group(1)) <= 14)(
              re.search(r"\.ap-tile \.rm\{([^}]*)\}", _css)))(), "")
    check("★R48-2 小窗**收窄**（≤ 280px）—— 要落进输入框内部，宽了必撞发送键",
          (lambda: (lambda m: bool(m)
                    and int(re.search(r"width:min\((\d+)px", m.group(1)).group(1)) <= 280)(
              re.search(r"(?m)^\.attach-panel\{([^}]*)\}", _css)))(), "")

    check("★R47 图标按扩展名给字形（零依赖，不引图标库）",
          "function fileGlyph(" in _jsnc and "'pdf'" in _jsnc, "")
    check("★R47 图标下标签过长时保留头尾（这些文件名前缀高度相同，必须能分辨）",
          "function shortName(" in _jsnc and "\u2026" in _jsnc, "")

    # ── ★★ R48（用户 3 图）────────────────────────────────────────────────
    #   R48-1 输入框里那行「完成 · 成功 N 个」不再显示；
    #   R48-2 小窗移进输入框、贴回形针右侧（几何判据在上方）+ 图标变小；
    #   R48-3 回形针不再有数字气泡（角标）。

    # ── R48-1 ───────────────────────────────────────────────────────────
    # ★★ 判据必须**去注释**后再查 token：我自己在注释里解释「不再写这一行」
    #   时若要写出那个赋值语句，就会把判据顶红（R47 原形）。`_jsnc` 已去注释。
    # ★★ 判据必须**限定在 `importFiles` 函数体内** —— 第一次写的是
    #   `"am.textContent" not in _jsnc`（全文），结果把 `newChat()` 里
    #   **有意保留**的那句清空（开新对话把这行清掉）也判红了。
    #   用户要求的是「**导入完成**那行不要显示」，不是「任何地方都不许碰这个元素」。
    #   ⇒ 范围收紧（不是放宽）：只在 `importFiles` 的源码区间里查这个 token。
    #   ★ 同时**去注释**后再查（`_jsnc`）：否则我在注释里解释这件事的文字会顶红。
    check("★R48-1 `importFiles()` 内**不再写**那行提示（用户图1「这里不要显示」）"
          "—— 判据限定在该函数体内，且读的是**去注释后**的源码",
          (lambda: (lambda a, b: a >= 0 and b > a
                    and "am.textContent" not in _jsnc[a:b])(
              _jsnc.find("async function importFiles"),
              _jsnc.find("async function openLocal")))(), "")
    # ★ 新需求：新会话保留对话内容与 DSH 会话，只新建Meta-DGTF会话 id。
    check("新会话回首屏：清当前视图、保留历史/DSH 附加数据、不显示输入框提示",
          "已新建会话，回到首屏" not in _jsnc
          and "document.body.classList.add('stage-empty')" in _jsnc
          and "localStorage.getItem('dgtf_task_dsh')" in _jsnc, "")

    check("★R49 回形针/粘贴结果改由 **composer 缩略图**承载",
          "dsh-paste-preview" in _jsnc and "attachAppPastedFiles" in _jsnc
          and "attachDshPastedFiles" in _jsnc, "")
    # ★ 那行元素**保留**（CSS 用 `:empty` 让它空着就不占位），这比删元素安全：
    #   既有结构引用不断，且「导入中」等其它瞬时文案未来还能复用。
    check("★R48-1 那行元素本身保留、且**空着不占位**（`.attach-msg:empty{display:none}`）",
          'id="attach-msg"' in html
          and re.search(r"\.attach-msg:empty\{([^}]*)\}", _css) is not None, "")

    # ── R48-3 ───────────────────────────────────────────────────────────
    # ★★ 三处来源都要查（页面 / 样式表 / 脚本），且**含注释**：
    #   留着注释里那个标识符，后来人会以为角标还在（R47 的 `ap-row` 原形）。
    check("★R48-3 回形针**不再有数字气泡**"
          "—— 页面 / 样式表 / 脚本三处都搜不到那个标识符（含注释）",
          "attach-n" not in html and "pill-n" not in html
          and "attach-n" not in css and "pill-n" not in css
          and "attach-n" not in js and "pill-n" not in js, "")
    # ★ 判据的**行为**没变：数量仍要能被看到 ⇒ 挪到小窗标题 + 悬停提示。
    check("★R48-3 数量改由**小窗标题 + 回形针悬停提示**表达（角标没了但数量没丢）",
          'id="ap-count"' in html and "已导入 ${n} 个" in _jsnc, "")
    # ★ 点回形针 = 统一开文件选择框
    check("★R49 点**回形针本身**统一开文件选择框",
          "if (f) f.click();" in _jsnc, "")



def check_r46_frontend(js: str) -> None:
    """★R46：文件选择的 `change` 处理器**不许**把 `FileList` 活引用先存下来再清 value。

    ★★ 真事故（用户第二次报同一句「导入不了 / 没显示」）：
       `#anchor-file` 的处理器原写成
           const fs = e.target.files;
           e.target.value = '';
           if (fs && fs.length) importFiles(fs);
       而 `HTMLInputElement.files` 返回的是一个 **FileList 活引用**
       （实测 `fs === af.files` 为 `true`）—— 清 `value` 会**连带把 fs 清空**，
       于是 `fs.length` 恒为 0，`importFiles()` **永远不会被调用**。
       症状：点「选择文件导入…」选完文件**毫无反应**、面板页不显示任何东西；
       而服务端接口**完全正常** ⇒ 极易被误判成后端问题。

    ★ 为什么 R44/R45 两轮验收都没抓到：验收探针是**直接调 `importFiles()`**，
      **绕开了这条真实路径**。判据必须落在「文件选择 → change」这条链上。
    """
    # ★ 取段：精确落在**文件选择的 change 处理器**那一段。
    #   注意 `#anchor-file` 在文件里出现 3 次（注释 / 回形针复用 / 这里），
    #   所以锚点取 `if (_af) _af.addEventListener('change'` 那一行 —— 唯一。
    seg = ""
    _lines = js.split("\n")
    for _i, _ln in enumerate(_lines):
        if "_af.addEventListener('change'" in _ln:
            _buf = [_ln]
            for _nxt in _lines[_i + 1:_i + 16]:
                _buf.append(_nxt)
                if _nxt.strip() == "});":
                    break
            seg = "\n".join(_buf)
            break

    check("★R46 找得到 `#anchor-file` 的 change 处理器", bool(seg), "")
    # ★ 核心判据：取 files 时必须**当场拷成数组**（快照），不能留活引用
    check("★R46 取 files **先拷成数组**（`[...e.target.files]`）—— 否则清 value 会连带清空",
          "[...e.target.files]" in seg, "")
    check("★R46 **不许**出现「先存活引用再清 value」的致命组合",
          # ★ 只在**真代码行**上判：注释行（以 * 开头或整行是 /* … */）不算 ——
          #   本函数 docstring 里就写了这个反例，否则判据会被自己的文档骗红。
          not any(re.match(r"\s*const\s+fs\s*=\s*e\.target\.files\s*;", ln)
                  for ln in seg.split("\n")
                  if not ln.strip().startswith("*")
                  and not ln.strip().startswith("/*")
                  and not ln.strip().startswith("//")), "")
    check("★R46 清 value（保证同一文件能再选一次）仍在，且判据用**快照后的长度**",
          "e.target.value = ''" in seg and "if (fs.length)" in seg, "")


def check_t3_daosheng(base: str, srv_src: str, runner_src: str,
                      js: str, html: str) -> None:
    """★T3「道生专属模式」+ 三体动态最优：离线单测 + mock HTTP 端到端判据。

    覆盖：预设契约、mode 解析、plan 结构/可审计字段、预算守卫三档、
    daosheng_fast 便宜档、apply_plan 只补不改、本地模型三级回退链
    （fake 8772 HTTP → 不可达 → 规则）、记忆注入门控/缓存/上限、
    引擎能力门控、后端/runner/前端源码接线、mock 201 端到端、resume/重试不丢 mode。
    """
    import threading
    import urllib.error
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    dm = daosheng_mode
    q_prj = "Meta-DGTF 道生三阶模型的项目当前状态如何？"

    def _preset_has_key(text, key):
        """YAML 里是否**真的定义了**该键（忽略注释；嵌套也查）。"""
        try:
            data = yaml.safe_load(text) or {}
        except Exception:  # noqa: BLE001
            return True                      # 解析不了 ⇒ 保守判「有」（判红）

        def _walk(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if str(k) == key:
                        return True
                    if _walk(v):
                        return True
            elif isinstance(d, list):
                return any(_walk(x) for x in d)
            return False

        return _walk(data)

    # ── ① 预设契约（configs/道生专属模式.yaml）──────────────────
    pth = dm.preset_path()
    raw = ""
    try:
        raw = pth.read_text(encoding="utf-8")
    except OSError:
        pass
    ds = dm.load_preset(force=True)
    check("★T3 预设 configs/道生专属模式.yaml 存在且可解析",
          pth.is_file() and ds.get("schema") == "metadgtf.app_daosheng.v1",
          "%d 字节 · schema=%s" % (len(raw.encode("utf-8")), ds.get("schema")))
    check("★T3 预设：route 四层全开 + rounds=auto（不硬编码高圈）",
          dm._norm_route(ds.get("route")) == ["0", "1", "both", "all"]
          and ds.get("rounds") == "auto",
          "route=%s rounds=%s" % (ds.get("route"), ds.get("rounds")))
    check("★T3 预设：质量档/便宜档圈数齐备（rounds_quality / rounds_fast）",
          bool(dm._norm_rounds(ds.get("rounds_quality")))
          and bool(dm._norm_rounds(ds.get("rounds_fast"))),
          "%s / %s" % (ds.get("rounds_quality"), ds.get("rounds_fast")))
    _SCM_OK = ("llm", "auto_narr", "auto", "local", "off")
    _DJM_OK = ("llm", "cache", "auto")
    check("★T3 预设：parallel=B；web/thinking/history_fusion=auto；"
          "self_check_mode/dual_judge_mode 为合法枚举（默认 llm，实验档 opt-in）",
          str(ds.get("parallel")) == "B"
          and all(str(ds.get(k)) == "auto" for k in
                  ("web", "thinking", "history_fusion"))
          and str(ds.get("self_check_mode")) in _SCM_OK
          and str(ds.get("dual_judge_mode")) in _DJM_OK,
          json.dumps({k: ds.get(k) for k in
                      ("parallel", "web", "thinking", "self_check_mode",
                       "dual_judge_mode", "history_fusion")},
                     ensure_ascii=False))
    check("★T3 预设：l0_v2 / merge_expand 等既有开关刻意不写（保持出厂默认）",
          not _preset_has_key(raw, "l0_v2")
          and not _preset_has_key(raw, "l0_v2_curate")
          and not _preset_has_key(raw, "merge_expand"),
          "注释里可以提到，但**键**不能出现")
    check("★T3 预设含引擎可识别子集（runtime / actions.parallel_mode / output.*_mode）",
          "runtime:" in raw and 'parallel_mode: "B"' in raw
          and re.search(r"self_check_mode:\s*(llm|auto_narr|auto|local|off)", raw)
          and re.search(r"dual_judge_mode:\s*(llm|cache|auto)", raw),
          "parallel_mode=%r" % ('parallel_mode: "B"' in raw))
    check("★T3 预设 budget_guard 阈值可审计（<8 降级 / <4 告警）",
          float(ds["budget"]["degrade_below_cny"]) == 8.0
          and float(ds["budget"]["warn_below_cny"]) == 4.0,
          "degrade=%s warn=%s" % (ds["budget"].get("degrade_below_cny"),
                                  ds["budget"].get("warn_below_cny")))

    # ── ② mode 解析 ─────────────────────────────────────────
    m_auto_prj = dm.resolve_mode("auto", q_prj)
    m_auto_gen = dm.resolve_mode("auto", "1+1等于几？")
    # ★ [V2.2.21 融合] 道生模式 = 标准模式：auto 一律解析为 daosheng
    check("★T3 mode=auto：统一解析为 daosheng（融合后道生=标准模式）",
          m_auto_prj["id"] == "daosheng" and m_auto_prj["source"] == "auto-fused"
          and m_auto_gen["id"] == "daosheng"
          and m_auto_gen.get("fused") is True,
          m_auto_gen.get("reason"))
    check("★T3 mode=auto：project_related 只决定背景注入，不改链路",
          m_auto_prj.get("project_related") is True
          and m_auto_gen.get("project_related") is False
          and "非项目题不注入" in str(m_auto_gen.get("reason")),
          m_auto_gen.get("reason"))
    check("★T3 显式 mode：daosheng/daosheng_fast 保持，standard 融合为 daosheng",
          dm.resolve_mode("daosheng", q_prj)["id"] == "daosheng"
          and dm.resolve_mode("daosheng_fast", q_prj)["id"] == "daosheng_fast"
          and (lambda r: r["id"] == "daosheng"
               and r.get("requested") == "standard"
               and r.get("fused") is True)(dm.resolve_mode("standard", q_prj)),
          "")
    check("★T3 mode 白名单准确（auto/daosheng/daosheng_fast/standard）",
          set(dm.VALID_MODES) == {"auto", "daosheng", "daosheng_fast",
                                  "standard"}, str(dm.VALID_MODES))
    _bad_mode = False
    try:
        dm.resolve_mode("bogus", "x")
    except ValueError:
        _bad_mode = True
    check("★T3 非法 mode 抛 ValueError（HTTP 层转 400）", _bad_mode, "")

    # ── ③ plan 结构（mock；免余额查询 ⇒ 不碰网络/API）─────────
    plan = dm.build_plan(q_prj, requested="daosheng", is_mock=True)
    _need = ("policy", "mode_id", "tier", "engine_mode", "route", "rounds",
             "parallel", "web", "thinking", "quality_policy",
             "project_related", "project_context", "context_injected",
             "memory", "local_llm", "m4", "history", "cache",
             "budget_guard", "engine", "reason", "warnings", "applied_opts")
    _miss = [k for k in _need if k not in plan]
    check("★T3 plan 结构完整（policy/plan/reason 可审计字段齐）",
          not _miss, "缺：" + ",".join(_miss))
    check("★T3 plan：policy=daosheng.v1 / tier=quality / engine_mode∈{B,serial}",
          plan["policy"] == "daosheng.v1" and plan["mode_id"] == "daosheng"
          and plan["tier"] == "quality"
          and plan["engine_mode"] in ("B", "serial"),
          "engine_mode=%s" % plan["engine_mode"])
    check("★T3 plan：route 四层 + rounds=auto + parallel=B + quality=auto:verified",
          plan["route"] == "0,1,both,all" and plan["rounds"] == "auto"
          and plan["parallel"] == "B"
          and plan["quality_policy"] == "auto:verified",
          "route=%s rounds=%s parallel=%s qp=%s"
          % (plan["route"], plan["rounds"], plan["parallel"],
             plan["quality_policy"]))
    check("★T3 plan.context_injected 记录真实注入（项目背景 + EML 记忆，各一次）",
          "project_context:RAG" in plan["context_injected"]
          and sum(1 for x in plan["context_injected"]
                  if x.startswith("memory:EML")) == 1,
          "、".join(plan["context_injected"]))
    check("★T3 plan.memory 有界（≤1600 字）且带来源清单",
          0 < int(plan["memory"]["chars"]) <= 1600
          and plan["memory"]["injected"]
          and bool(plan["memory"]["sources"]),
          "%s 字 · %s" % (plan["memory"]["chars"],
                          "/".join(plan["memory"]["sources"])))
    check("★T3 plan.local_llm 记录回退链（mock 跳过 → rules）",
          plan["local_llm"]["source"] == "rules"
          and isinstance(plan["local_llm"].get("attempts"), list),
          str([a.get("source") for a in plan["local_llm"]["attempts"]]))
    check("★T3 plan.m4 字段存在且 fail-open 可控（enabled/ok）",
          plan["m4"].get("enabled") is True and "ok" in plan["m4"], str(plan["m4"].get("ok")))
    check("★T3 plan.history 带 episodes 读数（n/中位/砍层率）",
          isinstance(plan["history"], dict)
          and ("n" in plan["history"] and "tokens_med" in plan["history"]),
          "n=%s tokens_med=%s" % (plan["history"].get("n"),
                                  plan["history"].get("tokens_med")))
    check("★T3 plan.cache 有精确/语义缓存命中预判",
          "exact" in plan["cache"] and "semantic_capable" in plan["cache"],
          plan["cache"].get("note"))
    check("★T3 plan.reason 非空（可审计的选择理由）",
          len(plan.get("reason") or "") > 20, (plan.get("reason") or "")[:80])
    check("★T3 plan.budget_guard 字段齐（balance/est_tokens/est_cost/decision/reason）",
          set(("balance_cny", "est_tokens", "est_cost_cny",
               "decision", "reason")) <= set(plan["budget_guard"]),
          "decision=%s est=%s/¥%s" % (plan["budget_guard"].get("decision"),
                                      plan["budget_guard"].get("est_tokens"),
                                      plan["budget_guard"].get("est_cost_cny")))
    check("★T3 plan.engine 带能力探测（版本 + 新机制 flag 支持表）",
          bool(plan["engine"].get("version"))
          and "self_check_mode" in (plan["engine"].get("supports") or {}),
          "%s supports=%s" % (plan["engine"].get("version"),
                              json.dumps(plan["engine"].get("supports"),
                                         ensure_ascii=False)))

    # ── ④ 预算守卫三档（Lead 决策 3）+ daosheng_fast ─────────
    p_ok = dm.build_plan(q_prj, requested="daosheng", is_mock=True,
                         balance_cny=10)
    p_deg = dm.build_plan(q_prj, requested="daosheng", is_mock=True,
                          balance_cny=6)
    p_warn = dm.build_plan(q_prj, requested="daosheng", is_mock=True,
                           balance_cny=3)
    check("★T3 预算守卫：余额 ¥10 ≥8 → ok + 质量档",
          p_ok["budget_guard"]["decision"] == "ok"
          and p_ok["tier"] == "quality", p_ok["budget_guard"].get("reason"))
    check("★T3 预算守卫：余额 ¥6 <8 → degrade + 自动降级 fast 档",
          p_deg["budget_guard"]["decision"] == "degrade"
          and p_deg["tier"] == "fast" and p_deg["engine_mode"] == "fast",
          p_deg["mode_reason"])
    # [V2.2.20 方案 A] 道生降级档接入统一模式配置：parallel 取 MODE_CONFIGS[fast]
    # （实测 fast = B 并行 + thinking off）；低圈/thinking off 的语义保持不变。
    check("★T3 预算守卫：降级后落统一模式配置（parallel=MODE_CONFIGS/thinking off/低圈）",
          p_deg["parallel"] == (p_deg.get("unified_config") or {}).get("parallel")
          and p_deg["thinking"] == "off"
          and dm._norm_rounds(p_deg["rounds"]) == dm._norm_rounds(ds["rounds_fast"]),
          "parallel=%s thinking=%s rounds=%s unified=%s"
          % (p_deg["parallel"], p_deg["thinking"], p_deg["rounds"],
             (p_deg.get("unified_config") or {}).get("parallel")))
    check("★T3 预算守卫：余额 ¥3 <4 → warn，但任务仍可创建（不拒绝）",
          p_warn["budget_guard"]["decision"] == "warn"
          and p_warn["tier"] == "fast"
          and "仍可创建" in str(p_warn["budget_guard"].get("reason")),
          p_warn["budget_guard"].get("reason"))
    check("★T3 预算守卫 fail-open：余额未知不拒绝任务（decision=ok）",
          plan["budget_guard"].get("fail_open") is True
          and plan["budget_guard"]["decision"] == "ok",
          plan["budget_guard"].get("reason"))
    check("★T3 预算守卫：est_tokens 用历史中位并受 raw_max_tokens 约束",
          0 < int(plan["budget_guard"]["est_tokens"])
          <= int(plan["budget_guard"]["raw_max_tokens"]),
          "%s ≤ %s" % (plan["budget_guard"]["est_tokens"],
                       plan["budget_guard"]["raw_max_tokens"]))
    p_fast = dm.build_plan(q_prj, requested="daosheng_fast", is_mock=True,
                           balance_cny=10)
    check("★T3 daosheng_fast 便宜档：tier=fast / 低圈 / thinking off",
          p_fast["mode_id"] == "daosheng_fast" and p_fast["tier"] == "fast"
          and dm._norm_rounds(p_fast["rounds"]) == dm._norm_rounds(ds["rounds_fast"])
          and p_fast["thinking"] == "off",
          "rounds=%s" % p_fast["rounds"])

    # ── ⑤ apply_plan：只补不改（显式 opts 优先）──────────────
    o_new = {}
    _ap = dm.apply_plan(dict(p_ok), o_new)
    check("★T3 apply_plan：空 opts 落 route/parallel/预设 profile",
          o_new.get("route") == "0,1,both,all" and o_new.get("parallel") == "B"
          and o_new.get("profile") == dm.PRESET_NAME,
          json.dumps(o_new, ensure_ascii=False))
    o_user = {"route": "0,1", "rounds": "0:1,1:1,both:1,all:1", "parallel": "serial"}
    dm.apply_plan(dict(p_ok), o_user)
    check("★T3 apply_plan：用户显式 opts 永不被覆盖",
          o_user.get("route") == "0,1" and o_user.get("parallel") == "serial"
          and o_user.get("rounds") == "0:1,1:1,both:1,all:1",
          json.dumps(o_user, ensure_ascii=False))
    check("★T3 apply_plan：auto 值不落 opts（web/thinking 交给引擎自决）",
          "web" not in o_new and "thinking" not in o_new,
          "web=%r thinking=%r" % (o_new.get("web"), o_new.get("thinking")))
    check("★T3 inject_prefix：项目背景 → EML 记忆 → 用户问题（只出现一次）",
          dm.inject_prefix("【项目背景】", "【记忆】").count("【用户问题】") == 1
          and dm.inject_prefix("【项目背景】", "【记忆】").index("【项目背景】")
          < dm.inject_prefix("【项目背景】", "【记忆】").index("【记忆】"),
          "")

    # ── ⑥ 本地模型：HTTP 8772 客户端 + 三级回退链（fake 服务）──
    class _FakeLLM(BaseHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401 静音
            pass

        def _send(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/health"):
                self._send({"ok": True, "stage": "route"})
            else:
                self._send({"ok": False, "error": "not found"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                req = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except ValueError:
                req = {}
            self.last_req = req
            # 契约（local-smith）：{ok, text} —— text 内是 route/rounds JSON。
            self._send({"ok": True,
                        "text": json.dumps({"route": ["0", "1"],
                                            "rounds": {"0": 2}}),
                        "stage": req.get("stage")})

    fake = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLLM)
    fake_port = fake.server_address[1]
    th = threading.Thread(target=fake.serve_forever, daemon=True)
    th.start()
    _old_url = os.environ.get("DGTF_LOCAL_LLM_URL")
    os.environ["DGTF_LOCAL_LLM_URL"] = "http://127.0.0.1:%d" % fake_port
    try:
        hr = dm.local_llm_health(force=True)
        rr = dm.local_llm_route("Meta-DGTF 项目下一步怎么优化？")
        pr_http = dm.predict_route_rounds("Meta-DGTF 项目下一步怎么优化？",
                                          is_mock=False)
        check("★T3 本地模型 HTTP：/health 可探测（ok=True）",
              hr.get("ok") is True, str(hr.get("error") or ""))
        check("★T3 本地模型 HTTP：/generate(stage=route) 解析出 route/rounds",
              rr.get("ok") and rr.get("route") == ["0", "1"]
              and (rr.get("rounds") or {}).get("0") == 2,
              json.dumps({k: rr.get(k) for k in ("route", "rounds", "how")},
                         ensure_ascii=False))
        check("★T3 本地模型优先：HTTP 可用时 source=http（不回退规则）",
              pr_http.get("ok") and pr_http.get("source") == "http", "")
    finally:
        fake.shutdown()
        fake.server_close()
        if _old_url is None:
            os.environ.pop("DGTF_LOCAL_LLM_URL", None)
        else:
            os.environ["DGTF_LOCAL_LLM_URL"] = _old_url
    # 8772 未就绪（必然连不上的端口）→ 子进程缺失 → 规则回退，全程 fail-open
    os.environ["DGTF_LOCAL_LLM_URL"] = "http://127.0.0.1:9"
    try:
        t_fb = time.time()
        fb = dm.predict_route_rounds("Meta-DGTF 项目下一步怎么优化？",
                                     is_mock=False)
        fb_dt = time.time() - t_fb
        check("★T3 本地模型不可达 → 规则回退（fail-open，总耗时 <3s）",
              fb.get("ok") and fb.get("source") == "rules" and fb_dt < 3.0,
              "%.2fs · route=%s" % (fb_dt, fb.get("route")))
        _sub_exists = (Path(dm.PROJECT_ROOT) / "llm_predict.py").is_file()
        _expect_chain = (["http", "subprocess", "rules"] if _sub_exists
                         else ["http", "rules"])
        check("★T3 回退链留痕：http 失败 →（子进程缺失则跳过）→ rules",
              [a.get("source") for a in (fb.get("attempts") or [])]
              == _expect_chain,
              str([a.get("source") for a in (fb.get("attempts") or [])]))
        t_nc = time.time()
        fb2 = dm.predict_route_rounds("Meta-DGTF 项目下一步怎么优化？",
                                      is_mock=False)
        nc_dt = time.time() - t_nc
        check("★T3 本地模型健康探测负缓存（第二次不再等超时，<0.5s）",
              fb2.get("source") == "rules" and nc_dt < 0.5,
              "%.3fs" % nc_dt)
    finally:
        if _old_url is None:
            os.environ.pop("DGTF_LOCAL_LLM_URL", None)
        else:
            os.environ["DGTF_LOCAL_LLM_URL"] = _old_url
    _mres = dm.predict_route_rounds(q_prj, is_mock=True)
    check("★T3 mock 任务跳过本地模型探测（不阻塞建任务）",
          _mres.get("source") == "rules"
          and "skipped" in json.dumps(_mres.get("attempts") or [],
                                      ensure_ascii=False), "")

    # ── ⑦ 记忆注入：门控 / 缓存 / 上限（Lead：不得注入无关内容）──
    mem_off = dm.memory_summary(q_prj, project_related=False)
    mem_on = dm.memory_summary(q_prj, project_related=True, force=True)
    mem_hit = dm.memory_summary(q_prj, project_related=True)
    check("★T3 记忆注入门控：非项目题不注入（text 为空）",
          mem_off["injected"] is False and mem_off["chars"] == 0,
          mem_off.get("reason"))
    check("★T3 记忆注入：项目题注入 EML 摘要（≤max_chars 上限）",
          mem_on["injected"] and 0 < mem_on["chars"] <= int(ds["memory"]["max_chars"])
          and "EML" in mem_on["text"],
          "%s 字 / 上限 %s" % (mem_on["chars"], ds["memory"]["max_chars"]))
    check("★T3 记忆注入缓存：同问题第二次 cache=hit",
          mem_hit.get("cache") == "hit", mem_hit.get("cache"))

    # ── ⑧ 引擎能力探测 + CLI 透传门控 ────────────────────────
    caps = dm.engine_capabilities()
    check("★T3 引擎能力探测：路径/版本/flag 支持表可用",
          caps.get("ok") and bool(caps.get("version")),
          "%s · %s" % (caps.get("version"), caps.get("path")))
    _cap_cfg = caps.get("supports_config") or {}
    check("★T3 引擎能力：config 键通道单独探测（V2.2.3 的 output.*_mode）",
          "self_check_mode" in _cap_cfg and "dual_judge_mode" in _cap_cfg,
          json.dumps(_cap_cfg, ensure_ascii=False))
    check("★T3 plan：新机制键标注生效通道（cli / config / engine-default）",
          "self_check_mode_via" in plan and "dual_judge_mode_via" in plan
          and "supports_config" in (plan["engine"] or {})
          and (str(plan["self_check_mode"]) in
               ("llm", "auto_narr", "auto", "local", "off")
               if plan["self_check_mode_via"] in ("cli", "config")
               else plan["self_check_mode"] is None)
          and (plan.get("history_fusion") == "auto"
               and plan.get("history_fusion_via") == "engine-default"),
          "scm=%s/%s · djm=%s/%s · hf=%s/%s"
          % (plan.get("self_check_mode"), plan.get("self_check_mode_via"),
             plan.get("dual_judge_mode"), plan.get("dual_judge_mode_via"),
             plan.get("history_fusion"), plan.get("history_fusion_via")))
    check("★T3 能力门控：新机制 CLI 透传与引擎能力严格一致（能力探测门控）",
          ("--self-check-mode" in runner.build_cmd(
              "q", {"self_check_mode": "off"}))
          == bool((caps.get("supports") or {}).get("self_check_mode"))
          and ("--dual-judge-mode" in runner.build_cmd(
              "q", {"dual_judge_mode": "cache"}))
          == bool((caps.get("supports") or {}).get("dual_judge_mode")),
          "cli_support=" + json.dumps(caps.get("supports"), ensure_ascii=False))
    check("★T3 能力门控：引擎已支持的 --history-fusion 照常透传",
          "--history-fusion" in runner.build_cmd("q", {"history_fusion": "off"}),
          "")
    check("★T3 runner._ARG_SPEC 注册三个新机制键",
          all(k in runner._ARG_SPEC for k in
              ("self_check_mode", "dual_judge_mode", "history_fusion")),
          str([k for k in ("self_check_mode", "dual_judge_mode",
                           "history_fusion") if k in runner._ARG_SPEC]))

    # ── ⑨ 源码接线：server / runner / 前端（最小改动）─────────
    check("★T3 server：mode 判定先于 quality_policy / 背景注入（不二次注入）",
          "import daosheng_mode" in srv_src
          and "mode 判定必须在 quality_policy / 项目背景注入之前" in srv_src
          and "daosheng_mode.build_plan(" in srv_src
          and "daosheng_mode.apply_plan(" in srv_src,
          "")
    check("★T3 server：POST /api/tasks 回显 mode（含 plan/reason/context/budget）",
          '"mode": _mode_info' in srv_src
          and '"plan": _ds_plan' in srv_src
          and '"context_injected": _ds_plan.get("context_injected")' in srv_src
          and '"budget_guard": _ds_plan.get("budget_guard")' in srv_src,
          "")
    check("★T3 server：resume/重试保留 mode（retry 透传 mode_info + opts 记档位）",
          'mode_info=_t.get("mode") or None' in srv_src
          and 'opts["_mode_request"] = _mode_req' in srv_src
          and "mode_info=_mode_info" in srv_src,
          "")
    check("★T3 runner：任务/活痕迹/归档/list 都带 mode（resume 不丢）",
          '"mode": dict(mode_info)' in runner_src
          and runner_src.count('"mode": task.get("mode") or {}') >= 2
          and '"has_plan"' in runner_src,
          "")
    check("★T3 runner：engine_capabilities / _GATED_FLAGS 接线",
          "def engine_capabilities(" in runner_src
          and "_GATED_FLAGS" in runner_src
          and "engine_supports_flag(" in runner_src, "")
    check("★T3 前端：最小改动展示「模式 · 策略」（只读标签，无新按钮）",
          "created.mode" in js and "rl-mode" in js and "模式 · " in js
          and "data-mode=" in js and "renderMeta" in js,
          "rl-mode=%d" % js.count("rl-mode"))
    check("★V2.2.48 前端：创建前预期（quality_forecast）只读展示",
          "quality_forecast" in js and "rl-qf" in js
          and "expected_verified_pct" in js and "safe_runs" in js
          and "tier_advice" in js,
          "rl-qf=%d" % js.count("rl-qf"))
    check("★V2.2.53 预期 vs 实测：任务 GET 带 quality_actual 且前端展示",
          "quality_actual" in js and "quality_actual" in srv_src
          and "quality_expected" in js,
          "quality_actual js=%s srv=%s" % ("quality_actual" in js,
                                           "quality_actual" in srv_src))

    # ★ [V2.2.63] 历史会话/归档视图的 quality 联动（零成本护栏）
    _chats_rows = []
    try:
        _chats_rows = dashboard.list_chats(10)
    except Exception:  # noqa: BLE001
        _chats_rows = []
    check("★V2.2.63 历史会话：list_chats 每行带 quality_expected/quality_actual",
          (not _chats_rows)
          or all("quality_expected" in r and "quality_actual" in r
                 for r in _chats_rows),
          "rows=%d" % len(_chats_rows))
    check("★V2.2.63 归档视图：archivedTask 携带 quality_expected/quality_actual",
          "quality_expected: c.quality_expected" in js
          and "quality_actual: c.quality_actual" in js,
          "")

    # ── ⑩ mock HTTP 端到端（201 + plan + 可审计 + resume）─────
    def _post_status(path, obj):
        try:
            return _post(base, path, obj)
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                body = {}
            return int(exc.code), body

    def _cancel_wait(tid, timeout=12.0):
        try:
            _post_status("/api/tasks/%s/cancel" % tid, {})
        except Exception:  # noqa: BLE001
            pass
        end = time.time() + timeout
        last = {}
        while time.time() < end:
            try:
                _s, t = _get(base, "/api/tasks/" + tid)
                last = t
                if str(t.get("status")) in ("cancelled", "error", "done"):
                    return t
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.2)
        return last

    def _cleanup_tid(tid):
        try:
            _s, t = _get(base, "/api/tasks/" + tid)
        except Exception:  # noqa: BLE001
            return 0
        names = []
        for _k in ("output_name", "archive_log", "archive_json"):
            if t.get(_k):
                names.append(str(t[_k]))
        nm = str(t.get("output_name") or "")
        if nm.endswith(".md"):
            stamp = nm[:-3]
            for _lay in ("修行", "研究", "对撞", "元"):
                names += [f"{stamp}.{_lay}.md", f"{stamp}.{_lay}.json",
                          f"{stamp}.{_lay}.run.log"]
        trash = oi.OUTPUTS_DIR.parent / "_audit_tmp" / "_selftest_trash"
        left = 0
        for n in sorted(set(names)):
            if not n or "/" in n or "\\" in n:
                continue
            p = oi.OUTPUTS_DIR / n
            try:
                p.unlink()
            except OSError:
                pass
            if p.exists():
                try:
                    trash.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(trash / n))
                except OSError:
                    left += 1
        return left

    _tids = []
    s_ds, r_ds = _post_status("/api/tasks", {
        "question": q_prj, "mode": "daosheng", "opts": {"mock": True}})
    tid_ds = str(r_ds.get("id") or "")
    if tid_ds:
        _tids.append(tid_ds)
    _m = r_ds.get("mode") or {}
    _p = _m.get("plan") or {}
    check("★T3 mock 端到端：POST /api/tasks mode=daosheng 返回 201",
          s_ds == 201 and bool(tid_ds), "status=%s id=%s" % (s_ds, tid_ds))
    check("★T3 响应回显 mode 对象（id/requested/tier/policy/reason）",
          _m.get("id") == "daosheng" and _m.get("requested") == "daosheng"
          and _m.get("tier") in ("quality", "fast")
          and bool(_m.get("policy")) and bool(_m.get("reason")),
          json.dumps({k: _m.get(k) for k in
                      ("id", "requested", "tier", "policy")},
                     ensure_ascii=False))
    check("★T3 响应回显完整 plan（policy/route/rounds/quality_policy/预算）",
          _p.get("policy") == "daosheng.v1"
          and _p.get("route") == "0,1,both,all"
          and "rounds" in _p and "quality_policy" in _p
          and "budget_guard" in _p and "applied_opts" in _p,
          "route=%s rounds=%s" % (_p.get("route"), _p.get("rounds")))
    check("★T3 响应回显可审计清单（context_injected + budget_guard.decision）",
          isinstance(_m.get("context_injected"), list)
          and bool(_m.get("context_injected"))
          and (_m.get("budget_guard") or {}).get("decision") in
          ("ok", "degrade", "warn"),
          "、".join(_m.get("context_injected") or []))
    check("★T3 mock 端到端不触发真实引擎/API（mock 任务 + mock_engine + 零余额查询）",
          bool(r_ds.get("id"))
          and bool((r_ds.get("mode") or {}).get("plan")),
          "plan.local_llm=%s" % (r_ds.get("mode", {}).get("plan", {})
                                 .get("local_llm", {}).get("source")))
    if tid_ds:
        _s_t, _t_ds = _get(base, "/api/tasks/" + tid_ds)
        _tm = _t_ds.get("mode") or {}
        check("★T3 GET 单任务带完整 mode（轮询/resume 不丢）",
              (_tm.get("id") == "daosheng"
               and ((_tm.get("plan") or {}).get("policy") == "daosheng.v1")),
              "id=%s" % _tm.get("id"))
        check("★T3 任务 opts 保存 _mode_request/_mode_id（重试可复原档位）",
              (_t_ds.get("opts") or {}).get("_mode_request") == "daosheng"
              and (_t_ds.get("opts") or {}).get("_mode_id") == "daosheng", "")
        # Lead 必交：GET /api/tasks（列表）也要回显 mode（摘要形态，has_plan 标记完整度）
        _s_ls, _ls = _get(base, "/api/tasks")
        _row = next((x for x in (_ls.get("tasks") or [])
                     if str(x.get("id")) == tid_ds), {})
        _lm = _row.get("mode") or {}
        check("★T3 GET /api/tasks 列表回显 mode 摘要（id/has_plan）",
              _s_ls == 200 and _lm.get("id") == "daosheng"
              and _lm.get("has_plan") is True
              and _lm.get("policy") == "daosheng.v1",
              json.dumps(_lm, ensure_ascii=False)[:160])
        check("★T3 mock 任务确认走 mock_engine（不触发真实 API）",
              bool(_t_ds.get("mock"))
              and any("mock_engine" in str(x) for x in (_t_ds.get("cmd") or [])),
              "mock=%s" % _t_ds.get("mock"))
        check("★T3 项目背景不重复注入（_prompt_prefix 里两个头各一次）",
              str((_t_ds.get("opts") or {}).get("_prompt_prefix") or "")
              .count("项目权威背景") == 1
              and str((_t_ds.get("opts") or {}).get("_prompt_prefix") or "")
              .count("【项目自进化记忆") == 1,
              "%d 字" % len(str((_t_ds.get("opts") or {})
                                .get("_prompt_prefix") or "")))
        _cancel_wait(tid_ds)

    s_bad, b_bad = _post_status("/api/tasks",
                                {"question": "x", "mode": "bogus",
                                 "opts": {"mock": True}})
    check("★T3 非法 mode → HTTP 400（带 allowed 白名单）",
          s_bad == 400 and bool(b_bad.get("allowed")),
          "status=%s" % s_bad)

    s_gen, r_gen = _post_status("/api/tasks", {
        "question": "1+1等于几？", "mode": "auto", "opts": {"mock": True}})
    _mg = r_gen.get("mode") or {}
    check("★T3 mode=auto 非项目题 → 也走道生模式（融合后单一链路）",
          s_gen == 201 and _mg.get("id") == "daosheng"
          and (_mg.get("plan") or {}).get("policy") == "daosheng.v1"
          and _mg.get("fused") is True,
          "id=%s fused=%s" % (_mg.get("id"), _mg.get("fused")))
    if r_gen.get("id"):
        _tids.append(str(r_gen["id"]))
        _cancel_wait(str(r_gen["id"]))

    s_sd, r_sd = _post_status("/api/tasks", {
        "question": q_prj, "mode": "standard", "opts": {"mock": True}})
    _m_sd = r_sd.get("mode") or {}
    check("★T3 显式 mode=standard：融合为道生 plan（id=daosheng/fused=True）",
          s_sd == 201 and _m_sd.get("id") == "daosheng"
          and _m_sd.get("fused") is True
          and ((_m_sd.get("plan") or {}).get("policy") == "daosheng.v1"),
          "id=%s requested=%s" % (_m_sd.get("id"), _m_sd.get("requested")))
    if r_sd.get("id"):
        _tids.append(str(r_sd["id"]))
        _cancel_wait(str(r_sd["id"]))

    # ★ Lead 验收项：真实链路 resume / 重试时 mode 字段不丢
    s_rt0, r_rt0 = _post_status("/api/tasks", {
        "question": q_prj + "（重试档位验证）", "mode": "daosheng",
        "opts": {"mock": True}})
    tid_rt0 = str(r_rt0.get("id") or "")
    if tid_rt0:
        _tids.append(tid_rt0)
        _cancel_wait(tid_rt0)
        s_rt1, r_rt1 = _post_status("/api/tasks/%s/retry" % tid_rt0, {})
        _rt1 = r_rt1.get("task") or {}
        _m_retry = _rt1.get("mode") or {}
        check("★T3 resume/重试：retry 响应带 mode（不丢档位）",
              s_rt1 == 200 and _m_retry.get("id") in ("daosheng", "daosheng_fast"),
              "status=%s mode=%s" % (s_rt1, _m_retry.get("id")))
        if r_rt1.get("id"):
            _tids.append(str(r_rt1["id"]))
            _s_rt2, _t_rt2 = _get(base, "/api/tasks/" + str(r_rt1["id"]))
            _m_rt2 = _t_rt2.get("mode") or {}
            check("★T3 resume/重试：新任务 GET 带完整 mode.plan（可审计）",
                  _m_rt2.get("id") == "daosheng"
                  and ((_m_rt2.get("plan") or {}).get("policy")
                       == "daosheng.v1"),
                  "id=%s" % _m_rt2.get("id"))
            check("★T3 resume/重试：新任务 opts 仍记 _mode_request（可再次恢复）",
                  (_t_rt2.get("opts") or {}).get("_mode_request") == "daosheng",
                  "")
    _left = 0
    for _tid in sorted(set(_tids)):
        _cancel_wait(_tid)
        _left += _cleanup_tid(_tid)
    print("  · 已清理 T3 端到端自检任务 %d 条%s"
          % (len(set(_tids)), ("（%d 个未删净）" % _left) if _left else ""))


def check_local_chain(base: str, srv_src: str, runner_src: str) -> None:
    """★ 本地链路（8772 推理服务 + 8773 OpenAI 适配层）判据。

    根因：旧 App 只 watch 8772；8773 死掉后整条本地链断路（引擎 CB 全开、
    llm_calls=0），而 /api/health 与侧栏都还显示正常。本段判三件事：
      A. /api/health 里真有 local_chain 动态读数（字段齐全，null 必带原因）；
      B. 读数与**直接探针**不矛盾（掉线不许报绿、假读数会当场红）；
      C. 「本地模型-全链路」预设能通过 App **既有** preview/profile 通道被选中。
    """
    try:
        _, health = _get(base, "/api/health")
    except Exception as exc:  # noqa: BLE001
        check("★本地链路 /api/health 可读", False, str(exc))
        return
    snap = (health or {}).get("local_chain") or {}
    req = ("endpoint_kind", "ok", "service_ok", "shim_ok", "service_status",
           "service_queue_depth", "service_gpu_mem_mb", "shim_stage_channel",
           "engine_path", "engine_version", "checked_at", "reasons",
           "watchdog", "preset")
    miss = [k for k in req if k not in snap]
    check("★本地链路 A1 /api/health 带 local_chain 动态读数（字段齐全）",
          bool(snap) and not miss, "missing=%r" % (miss,))
    wd = snap.get("watchdog") or {}
    check("★本地链路 A2 读数含守护状态（mode/失败计数/重启次数/指数退避/日志路径）",
          wd.get("mode") in ("auto", "on", "off")
          and isinstance(wd.get("failures"), dict)
          and isinstance(wd.get("restarts"), dict)
          and isinstance(wd.get("backoff_seconds"), list)
          and bool(wd.get("log")),
          json.dumps({k: wd.get(k) for k in ("mode", "failures", "restarts",
                                             "backoff_seconds")},
                     ensure_ascii=False)[:240])
    check("★本地链路 A3 引擎读数透传（engine_path 指向 runner.find_engine()）",
          bool(snap.get("engine_path"))
          and str(snap.get("engine_path")).endswith(runner.find_engine().name)
          and bool(snap.get("engine_version")),
          "path=%r version=%r" % (snap.get("engine_path"),
                                  snap.get("engine_version")))
    reasons = snap.get("reasons") or {}
    no_reason = [name for name, key in (("service", "service_ok"),
                                        ("shim", "shim_ok"))
                 if snap.get(key) is not True
                 and not str(reasons.get(name) or "").strip()]
    check("★本地链路 A4 非就绪段都点名原因（「没有读数就不假装有」）",
          not no_reason, "缺原因=%r · reasons=%r"
          % (no_reason, json.dumps(reasons, ensure_ascii=False)[:200]))
    # ── B. 与直接探针一致性（只判「不矛盾」：读数允许滞后，但不许反向）──
    p_svc = lchain.probe(lchain.service_url(), "/health", 1.2)
    p_shim = lchain.probe(lchain.shim_url(), "/health", 1.2)
    problems = []
    if not p_svc.get("ok") and not p_svc.get("reachable"):
        if snap.get("service_ok") is True:
            problems.append("8772 直探硬掉线，读数却报 service_ok=True")
    elif snap.get("service_ok") not in (True, False):
        problems.append("8772 直探可达，读数却是 null（未测出）")
    if not p_shim.get("ok") and not p_shim.get("reachable"):
        if snap.get("shim_ok") is True:
            problems.append("8773 直探硬掉线，读数却报 shim_ok=True")
    elif snap.get("shim_ok") not in (True, False):
        problems.append("8773 直探可达，读数却是 null（未测出）")
    check("★本地链路 B1 读数与直接探针不矛盾（掉线不许报绿 / 可达不许报未测）",
          not problems,
          "；".join(problems) or "直探 svc_ok=%r/%r shim_ok=%r/%r 读数 svc=%r shim=%r"
          % (p_svc.get("ok"), p_svc.get("reachable"),
             p_shim.get("ok"), p_shim.get("reachable"),
             snap.get("service_ok"), snap.get("shim_ok")))
    # ── C. 「本地模型-全链路」预设：既有 profile/preview 通道 ──
    pfile = lchain.PRESET_PATH
    pflat = lchain.read_preset_flat()
    bad = [k for k in lchain.PRESET_REQUIRED
           if pflat.get(k) != lchain.LOCAL_PRESET_OVERRIDES[k]]
    check("★本地链路 C1 「本地模型-全链路」预设文件存在且覆盖值正确",
          pfile.is_file() and not bad,
          "path=%r bad=%r" % (str(pfile), bad))
    try:
        _, prev = _post(base, "/api/schedule/preview",
                        {"question": "本地链路预设判据",
                         "profile": lchain.PRESET_NAME})
    except Exception as exc:  # noqa: BLE001
        prev = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    _cli = prev.get("cli") or []
    _hit_cfg = "--config" in _cli and any(
        str(lchain.PRESET_NAME) in str(x) for x in _cli)
    check("★本地链路 C2 App 既有 profile→_config 通道能选中本地全链路档"
          "（/api/schedule/preview 拼出 --config <预设>）",
          bool(prev.get("ok")) and _hit_cfg,
          "ok=%r cli=%r err=%r" % (prev.get("ok"), _cli[:6], prev.get("error")))
    check("★本地链路 C3 预设经 preview 通道解析后仍是本地端点（没被云档覆盖）",
          bool(prev.get("ok"))
          and "127.0.0.1:8773" in pfile.read_text(encoding="utf-8",
                                                  errors="replace")
          and "local-shim" in pfile.read_text(encoding="utf-8",
                                              errors="replace"),
          "profile=%r" % (prev.get("profile"),))
    try:
        _, side = _get(base, "/api/status/sidebar")
        llm = (side or {}).get("llm") or {}
        chain = llm.get("chain") or {}
        check("★本地链路 C4 侧栏 llm 读数升级为两段链路（保留旧键 watchdog_ok）",
              isinstance(chain, dict)
              and "service_ok" in chain and "shim_ok" in chain
              and isinstance(llm.get("watchdog_ok"), bool),
              "chain_keys=%r" % (sorted(chain.keys())[:8],))
    except Exception as exc:  # noqa: BLE001
        check("★本地链路 C4 侧栏 llm 读数升级为两段链路", False, str(exc))
    # ── D. 接线静态对账（server.py 真接到 local_chain，而不是只有新文件）──
    lc_src = ""
    try:
        lc_src = (Path(__file__).resolve().parent / "local_chain.py").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        lc_src = ""
    check("★本地链路 D1 server.py 真接线（import local_chain + health/守护调用 + 显式开关）",
          "local_chain as lchain" in srv_src
          and "lchain.health_snapshot" in srv_src
          and "lchain.ensure_watchdog" in srv_src
          and "--local-chain-watchdog" in srv_src
          and "DGTF_APP_LOCAL_CHAIN_WATCHDOG" in lc_src,
          "srv 命中=%r" % ([x in srv_src for x in
                            ("local_chain as lchain", "lchain.health_snapshot",
                             "lchain.ensure_watchdog", "--local-chain-watchdog")],))
    check("★本地链路 D2 守护状态机在两段上都可重启（8772 服务 + 8773 适配层）",
          "dgtf_local_llm.service" in lc_src
          and "openai_shim.py" in lc_src
          and "def default_targets" in lc_src,
          "见 local_chain.py default_targets/service_start_cmd/shim_start_cmd")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get(
        "DGTF_APP", "https://127.0.0.1:8765"))
    base = ap.parse_args().base

    try:
        _rq = urllib.request.Request(base + "/", headers=dict(_AUTH_HEADERS))
        with urllib.request.urlopen(_rq, timeout=10) as r:
            html = r.read().decode("utf-8")
        check("首页可访问且含标题", r.status == 200 and "Meta-DGTF" in html)
        check("首页引用静态资源", "/static/app.js" in html and "/static/style.css" in html)
    except Exception as e:  # noqa: BLE001
        print("服务不可达：", e)
        return 2

    # ── 页面契约：四条改动必须落在真正被服务出去的静态资源上 ──────
    #（文本判据只能证「接线在」，视觉最终由浏览器实拍确认）
    css = _raw(base, "/static/style.css")
    js = _raw(base, "/static/app.js")
    _app = Path(__file__).resolve().parent
    runner_src = (_app / "engine_runner.py").read_text(encoding="utf-8")
    oi_src = (_app / "outputs_index.py").read_text(encoding="utf-8")
    params_src = (_app / "params.py").read_text(encoding="utf-8")
    dash_src = (_app / "dashboard.py").read_text(encoding="utf-8")
    srv_src = (_app / "server.py").read_text(encoding="utf-8")

    # ★ R44：本地资料库导入的两份源码（library 的导入管线 + docparse 的各格式解析）。
    #   读不到就给空串 —— 判据会如实翻红，而不是把整个自检炸掉。
    def _r44_read(name: str) -> str:
        try:
            return (_app / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    lib_src = _r44_read("library.py")
    dp_src = _r44_read("docparse.py")
    _, params_data = _get(base, "/api/params")
    _, chats_data = _get(base, "/api/chats")
    _rl = _rule(css, ".runlog-body")
    check("运行日志：解掉 .log 的 264px 上限（否则日志区下半截留空）",
          "max-height:none" in _rl, _rl.strip()[:64])
    _run = _rule(css, ".runlog")
    check("运行日志：面板在「深究」区撑满剩余高度",
          "flex:1 1 auto" in _run, _run.strip()[:64])
    check("运行日志：默认隐藏、点「开始深究」后才出现（四张层卡已从页面移除）",
          'class="runlog hidden"' in html
          and ".runlog.hidden{display:none}" in css.replace(" ", "")
          and 'class="lane' not in html and 'id="tasks"' not in html,
          "")
    # 骨架：极简首屏 + 左侧抽屉（面板平时不占位）
    check("极简首屏：面板收进左侧抽屉（默认移出屏外 + **淡出**，.open 才拉进来）",
          "translateX(-102%)" in _rule(css, ".drawer")
          and "opacity:0" in _rule(css, ".drawer")
          and ".drawer.open{transform:none" in css
          and 'id="drawer-btn"' in html,
          _rule(css, ".drawer").strip()[:56])
    check("极简首屏：空态居中、运行态日志占主位（body 上的 stage-* 切换）",
          "body.stage-empty main.stage{justify-content:center" in css
          and "body.stage-run .runlog{flex:1 1 auto" in css
          and 'class="stage-empty"' in html,
          "")
    check("输入框为对话式（DSH/附件/演练模式 + 圆形发送键；首屏不再放深度思考/智能搜索）",
          'id="pill-thinking"' not in html and 'id="pill-web"' not in html
          and 'id="run-btn"' in html and "composer-actions" not in html)
    check("首屏三个入口都在（抽屉 / 搜索对话产物 / 开启新对话），描述走**悬停气泡**",
          all(k in html for k in ('id="drawer-btn"', 'id="search-btn"', 'id="newchat-btn"'))
          and 'data-tip=' in html and 'class="btn-desc"' not in html,
          "data-tip=" + str(html.count('data-tip=')))
    check("搜索浮层 + 文件导入入口都在（浮层默认隐藏）",
          'id="search-overlay" class="search-overlay hidden"' in html
          and 'id="search-input"' in html and 'id="attach-btn"' in html,
          "")
    check("抽屉里是**八个**按钮（含历史对话与 Agent 面板）、各自指向一个面板",
          html.count('class="nav-btn"') == 8
          and 'data-sheet="adv-panel"' in html and 'data-sheet="view-lib"' in html,
          f"nav-btn={html.count('nav-btn')}")
    # ★ 参数页出口：R36 起口径是「出厂 `dgtf_config.yaml` **只读**，用户改动写
    #   **用户配置** `dgtf_config.user.yaml`；『恢复出厂设置』删用户配置 ⇒ 回落出厂」。
    #   ★ R37：只保留两个出口（保存 + 恢复出厂设置），「仅本次任务生效」从界面移除。
    #   ★ R38：底栏从 `#adv-group-page` **提出来**、改挂 `.sheet`（参数两页共用、恒在底部）：
    #     用户报「恢复出厂设置后按钮不见了」——根因是首页 `#adv-panel` 里根本没有这条栏。
    check("⑦ 参数页只剩**两个**出口：保存 + 恢复出厂设置（`adv-once` 已从界面删掉）",
          'id="adv-save"' in html and 'id="adv-reset"' in html
          and 'id="adv-once"' not in html
          and ".sheet-actions{" in css
          and "justify-content:center" in _rule(css, ".sheet-actions")
          and 'class="sa-spacer"' in html,
          "adv-once=" + str('id="adv-once"' in html))
    _ai = html.find('id="adv-actions"')
    _bi = html.find('class="sheet-body"')
    _si = html.find('id="search-overlay"')
    # ★★ R38 判据加强（变异体 M9 实测漏检）：只比「第一个 sheet-body 在底栏之前」
    #    是不够的 —— 在底栏前再插一个 `class="sheet-body"` 也能满足，但它其实是**别的
    #    元素**。真正的语义是「底栏排在**那唯一的** sheet-body 之后」，所以数**之前出现
    #    的 sheet-body 个数必须恰好 1**（多一个就说明有元素被排到了底栏前）。
    _sb_before = html.count('class="sheet-body"', 0, _ai) if _ai > 0 else -1
    check("⑦ 底栏是 `.sheet` 的**直接子项**（参数两页共用 ⇒ 首页也有恢复出厂设置）",
          _ai > 0 and _bi > 0 and _ai > _bi and (_si < 0 or _ai < _si)
          and _sb_before == 1
          and "sheet-actions hidden" in html,
          f"adv-actions={_ai} sheet-body={_bi} search-overlay={_si} "
          f"底栏前的 sheet-body 个数={_sb_before}")
    # ★ 陷阱：「syncAdvBar」在**定义行** `function syncAdvBar(key) {` 就已出现 ⇒
    #   只查这个名字，把调用点删掉也照样绿（本轮变异体 M11 实测漏检）。**必须查调用点**。
    check("⑦ 底栏显隐由 JS 按当前页控制（`syncAdvBar` 在参数两页显示）",
          "function syncAdvBar(key) {" in js
          and "  syncAdvBar(key);" in js          # ← 调用点（带缩进 + 分号）
          and "'adv-panel'" in js and "'adv-group-page'" in js
          and "classList.toggle('hidden', !on)" in js,
          "调用点=" + str("  syncAdvBar(key);" in js))
    check("⑦ 「恢复出厂设置」文案到位（不再是「恢复默认配置」）",
          "恢复出厂设置" in html and "恢复默认配置" not in html,
          "")
    check("⑦ 保存按钮**居中**：左有 `.sa-spacer` 隐形占位（与右侧「恢复」等宽）",
          'class="sa-spacer"' in html
          and "visibility:hidden" in _rule(css, ".sa-spacer"),
          _rule(css, ".sa-spacer").strip()[:60])
    # ★ R38：「保存」= 保存**所有**参数改动（跨分组 + CLM）并**退出**（用户明确要求）。
    check("「保存」写**用户配置**（不是出厂 yaml、也不只写内存）",
          "saveAdvToFile" in js
          and "await api('/api/params'" in js
          and "method: 'POST'" in js
          and "advSaved[k] = advOverrides[k]" in js
          and "dgtf_config.user.yaml" in js
          and "写回 dgtf_config.yaml" not in js,
          "")
    check("「保存」提交的是**全部**待保存键（跨分组 + CLM），不是只有当前一组",
          "function advDirtyAll" in js and "advDirtyAll()" in js
          and "const dirty = advDirtyAll()" in js
          and "const dirty = advDirtyOfGroup(g)" not in js,
          "")
    # ★ 陷阱：`"closeSheet();" in js` 太宽 —— 文件里别处也调它（点关闭 / Esc），
    #   把保存函数里那句删掉照样绿（变异体 M25 实测漏检）。必须查**保存函数体内**那段。
    #   ★ 换行：`js` 是 **CRLF** 文本 ⇒ 截断按 `\r?\n}`（函数闭合在**行首**）。
    _i0 = js.find("async function saveAdvToFile")
    _m = re.search(r"\r?\n}\r?\n", js[_i0:]) if _i0 >= 0 else None
    _svf = js[_i0:_i0 + _m.start()] if _m else js[_i0:]
    check("「保存」= 保存**并退出**（用户要求「保存参数改动设置并退出」）",
          _i0 >= 0
          and "advToast(msg, miss || skip ? 'warn' : 'ok');" in _svf
          and "closeSheet();" in _svf,
          f"函数体 {len(_svf)} 字符")
    # ── ★ R38 前端 CLM 三段接线（变异体 M21/M22 实测：改坏这一段，翻红的却是**后端**
    #    判据 ⇒ 说明前端本身没有判据兜住。这里补齐，且各查**那段代码本体**。）
    check("★R38 CLI 输入框**带 value 回显**（原 bug 就是只给 placeholder ⇒ 切走再回来值没了）",
          'field = `<input data-adv="${esc(it.key)}" value="${esc(v)}" placeholder='
          in js,
          "")
    check("★R38 CLI 输入框用 `data-adv`（**不是** `data-cfg` —— 它不属于 yaml 配置）",
          'field = `<input data-adv=' in js
          and "data-cfg" not in js[js.find("field = `<input data-adv="):
                                    js.find("field = `<input data-adv=") + 120],
          "")
    check("★R38 事件委托**同时认** `[data-cfg]` 和 `[data-adv]`（CLM 改动才记得住）",
          "closest('[data-cfg],[data-adv]')" in js,
          "")
    check("★R38 `rememberAdv` 认 `dataset.adv`（否则 CLM 键进不了 advOverrides）",
          "el.dataset.cfg || el.dataset.adv" in js,
          "")
    check("★R38 `collectOpts` 把 CLM 键**分流到 opts 顶层**（不能混进 overrides 写进临时 config）",
          "const cliKeys = new Set(ADV.map(([k]) => k))" in js
          and "if (cliKeys.has(k)) {" in js
          and "opts[k] = s" in js,
          "")
    # ★ R38：CLM 键**清空**时必须「删掉这个键」而不是「下发空串」—— 变异体 M27 实测：
    #   少了 `else delete …` 就把「清空」变成「传个空值」，引擎会当它是个 flag 传下去。
    check("★R38 CLM 键**清空 ⇒ 从 opts 删掉**（不是下发空串）",
          "if (s) opts[el.dataset.adv] = s; else delete opts[el.dataset.adv];" in js
          and "if (s) opts[k] = s; else delete opts[k];" in js,
          "")
    check("★R38 前端从 `/api/params` 的 `cli` 字段取已保存值（advCliSaved）",
          "advCliSaved = (r.cli && typeof r.cli === 'object') ? r.cli : {};" in js
          and "const savedCli = advCliSaved || {};" in js
          and "savedCli[k] || ''" in js,
          "")
    check("「恢复出厂设置」按钮存在且打 `/api/params/reset`（删用户配置 ⇒ 回落出厂）",
          "resetAdv" in js and "api('/api/params/reset'" in js
          and "reset_params" in params_src
          and 'p == "/api/params/reset"' in srv_src
          and "恢复出厂设置" in html,
          "")
    check("改了但没保存的项**看得见**（分组按钮「N 项待保存」+ 保存键置灰/点亮）",
          "advDirtyCount" in js and "advDirtyOfGroup" in js
          and "项待保存" in js and "updateAdvActions" in js
          and ".nav-btn .adv-dirty{" in css and "has-dirty" in css,
          "")
    check("保存结果有**可见反馈**（toast 挂 #sheet 上 ⇒ 切页不丢）",
          "advToast" in js and "'.adv-toast.show'" not in js
          and "#adv-toast" not in html          # 动态造，不写死在 HTML 里
          and ".adv-toast{" in css and "position:fixed" in _rule(css, ".adv-toast"),
          "")
    # ★★ R36 的结构性判据：**出厂 yaml 一个字节都不动**。
    #   这是「恢复默认配置」之所以成立的唯一理由 —— 基线没了就无从恢复。
    #   判据落在实现本体（`save_params` 里不出现对 CFG 的写入），不是「文档这么说的」。
    #   ★ 正则必须排除 `USER_CFG.` —— 否则 `USER_CFG.write_text(...)` 会被
    #     `CFG\.write_text` **子串命中**，判据当场自欺（本轮第一版正是这么翻红的）。
    check("参数写回**只写用户配置**（出厂 dgtf_config.yaml 全程只读）",
          "USER_CFG" in params_src and "dgtf_config.user.yaml" in params_src
          and "def save_params" in params_src and "def reset_params" in params_src
          # save_params 的函数体里不许出现对 CFG 的写（只允许读它取原类型）
          and not re.search(r"(?<!USER_)CFG\s*\.\s*(write_bytes|write_text|unlink|touch)\s*\(",
                            params_src.split("def save_params")[1]
                            .split("def reset_params")[0]),
          "")
    # ★ 早期版本用「逐行文本替换」保 yaml 注释；现在写的是**我们自己生成的**用户配置
    #   （无注释要保），所以允许 safe_dump —— 但**只允许 dump 用户配置**，不许 dump 出厂 yaml。
    check("用户配置由本模块自己 dump（出厂 yaml 那 1600+ 行注释不再有被抹的风险）",
          "def _dump_user_cfg" in params_src
          and "def _set_flat_in_text" in params_src        # 仍留着：逐行替换的通用工具
          and "_dump_user_cfg(merged)" in params_src,
          "")
    check("高级参数页只列分组按钮，点一个进新页看该组参数",
          'id="adv-groups"' in html and 'id="adv-group-page"' in html
          and 'id="adv-grid"' in html and "openAdvGroup" in js,
          "")
    # ★★ R36 ②：异常终止的任务必须**留痕**（用户报「服务崩了任务数据没了、没痕迹」）——
    #   根因是任务表在进程内存里，崩溃时与未归档的进度一起消失，outputs/ 里什么都没有。
    #   这三处必须同时成立：起跑就落「活痕迹」/ 收尾必归档（含异常路径）/ 启动回填孤儿。
    check("★ 任务**起跑就落活痕迹**（`outputs/<tid>.run.json`，服务被强杀也留得下）",
          "def _write_live_run" in runner_src and "def _clear_live_run" in runner_src
          and "def sync_live_log" in runner_src and "def recover_orphans" in runner_src
          and "_write_live_run(task)" in runner_src
          and "sync_live_log(task)" in runner_src,
          "")
    check("★ 收尾**必归档**：异常分支也走 `_finalize`（原来直接 return ⇒ 三处都查不到）",
          "def _finalize" in runner_src
          and "_finalize(task, \"error\")" in runner_src
          and runner_src.count("_finalize(task,") >= 2   # 正常收尾 + 异常收尾
          and "先落盘归档，再改 status" in runner_src,
          "")
    check("★ 服务启动时**回填孤儿任务**（有活痕迹但没跑完 ⇒ 标 interrupted + 原因）",
          "recover_orphans()" in srv_src and "回填中断任务" in srv_src
          and '"interrupted"' in runner_src
          and "服务中断（进程异常退出 / 重启）" in runner_src,
          "")
    check("★ 前端认识 `interrupted` 并把**原因**显示出来（历史对话 / 最近跑过）",
          "interrupted: '已中断'" in js
          and "chipState" in js and "已中断 · 服务异常" in js
          and "class=\"why\"" in js and ".hist .m .why{" in css
          and ".hist .st.interrupted{" in css,
          "")
    check("★ 中断痕迹能被**产物库**收录（带 status/error，题目从元信息取）",
          '"error": err' in oi_src and '"run_question": q_from_run' in oi_src
          and 'q_from_run' in oi_src,
          "")
    check("按钮描述改成**悬停气泡**：背景透明 + **文字灰色**（.tip，挂 body 的 fixed 气泡）",
          ".tip{" in css and "background:transparent" in _rule(css, ".tip")
          and "color:#6B7280" in _rule(css, ".tip")
          and "initTips" in js and "position:fixed" in _rule(css, ".tip")
          and 'class="btn-desc"' not in html,
          "data-tip=" + str(html.count('data-tip=')))
    check("侧边栏按钮只留名字 ⇒ **高度自适应**（不再被描述撑成两行）",
          ".nav-btn .nb-name" in css and ".nav-btn .btn-desc" not in css
          and html.count('class="nb-name"') >= 6,
          "nb-name=" + str(html.count('class="nb-name"')))
    check("运行日志：层标题蓝粗、**名称与内容同一行**、正文只改绿",
          "text-align:center" in _rule(css, ".rl-lane-head")
          and "color:var(--log-blue)" in _rule(css, ".rl-lane-head")
          and "font-weight:700" in _rule(css, ".rl-lane-head")
          and "display:flex" in _rule(css, ".rl-line")
          and "color:var(--log-blue)" in _rule(css, ".rl-lab")
          and "color:var(--log-green)" in _rule(css, ".rl-txt")
          and "pre-wrap" in _rule(css, ".rl-txt")
          and "hlNums" in js,
          "")
    # ★ R21：日志**语义排版**（轮次/步骤/小标题蓝粗、噪声过滤、[N] 合并、view 默认展开）
    check("日志语义排版：轮次/步骤/小标题**蓝粗**；噪声过滤；view 全文**默认展开**",
          "function renderLogBody" in js and "function rlClass" in js
          and ".rl-round" in css and ".rl-step" in css and ".rl-title" in css
          and ".rl-summary" in css and ".rl-seq" in css
          and ".rl-fold>summary" in css.replace(" ", "")
          and 'class="rl-fold" open' in js
          and "RL_NOISE" in js and "RL_BANNER" in js and "RL_VIEWBAR" in js
          and "function rlSuspNames" in js,
          "")
    check("日志排版细则：`##` 去掉 / `🔥 │` 前缀去掉 / `[N]` 属性插在**序号与内容之间** / 悬置还原",
          "replace(/^#{1,6}" in js
          and "🔥\\s*│" in js
          and ".rl-attr" in css and 'class="rl-line rl-seq"' in js
          and ".rl-susp" in css and "原悬置" in js,
          "")
    check("日志头：题目**蓝色 + 与元信息同档字号**、与元信息**同栏居中**（`.rl-head-c`）+ 链接深绿/深蓝",
          "color:var(--log-blue)" in _rule(css, "#rl-question")
          and "clamp(13px,1.85vh,16.5px)" in _rule(css, "#rl-question")
          and "clamp(13px,1.85vh,16.5px)" in _rule(css, ".rl-meta")
          and "justify-content:center" in _rule(css, ".rl-head-c")
          and "gap:clamp(" in _rule(css, ".rl-head-c")
          and 'class="rl-head-c"' in html
          and '<span id="rl-question"></span><span id="rl-meta"' in html
          and "var(--st-done-bg)" in _rule(css, ".rl-files a")
          and "var(--st-done-c)" in _rule(css, ".rl-files a"),
          "")
    check("详情卡片背景 **20% 不透明**（同类：搜索框 / 结果框一起，R24 统一）",
          "rgba(22,23,28,.20)" in _rule(css, ".detail .md")
          and "rgba(22,23,28,.20)" in _rule(css, ".search-box")
          and "rgba(22,23,28,.20)" in _rule(css, ".search-results"),
          "")
    check("按钮**只留图标**（说明走 data-tip）+ 入口钮 34px + 发送键渐变 + 箭头 22px 加粗",
          'class="btn-name"' not in html and 'class="p-name">导入锚点' not in html
          and "height:34px" in _rule(css, ".icon-btn")
          and "linear-gradient" in _rule(css, "#run-btn.send")
          and "width:14px" in _rule(css, "#run-btn.send svg")
          and "flex:0 0 auto" in _rule(css, "#run-btn.send svg")
          and "stroke-width:3.2" in css,
          "")
    check("发送的**星光动画**：粒子 + 问题残影 + **落点后才露日志并点亮**",
          'id="fx"' in html and ".spark{" in css and "@keyframes sparkfly" in css
          and ".runlog.lit" in css and "function playSendFx" in js
          and "playSendFx(question, ()" in js and "onDone" in js,
          "")
    check("侧边栏：头部/环境**居中**、按钮**图标贴左 + 文字居中**；环境白字、状态点按是否配置着色",
          "justify-content:center" in _rule(css, ".drawer-head")
          and "text-align:left" in _rule(css, ".env")
          and "justify-content:flex-start" in _rule(css, ".nav-btn")
          and "text-align:center" in _rule(css, ".nav-btn .nb-name")
          and "color:var(--t1)" in _rule(css, ".env")
          and ".dot.no{background:var(--t3)" in css.replace(" ", ""),
          "")
    check("元信息：**除数字外一律蓝 + 加大加粗**（含「秒/tokens」单位）、整栏居中、含「终止」时间",
          "color:var(--log-blue)" in _rule(css, ".rl-meta")
          and "font-weight:700" in _rule(css, ".rl-meta")
          and "justify-content:center" in _rule(css, ".rl-meta")
          and "color:var(--log-num)" in _rule(css, ".rl-meta b")
          and "终止" in js and "ended_at || Date.now()" in js,
          "")
    check("参数面板：标签统一**居中**、行列自适应、保存按钮调大",
          "text-align:center" in _rule(css, ".grid label,.grid .field")
          and "height:38px" in _rule(css, ".sheet-actions button.ghost"),
          "")
    check("输入框：基础提示左对齐、轮询问题居中并右移 12px，用户输入内容左对齐",
          "textarea#question::placeholder{color:var(--t3);text-align:left}" in css.replace(" ", "")
          and "textarea#question.ph-question{padding-left:28px}" in css.replace(" ", "")
          and "textarea#question.ph-question::placeholder{text-align:center}" in css.replace(" ", "")
          and "textarea#question{text-align:left}" in css.replace(" ", "")
          and "--mx" in css and "var(--mx)" in css
          and "34%" in css and "'--mx'" in js,
          "")
    check("内嵌图形（品牌/欢迎语方块标）**放大加粗**；文件链接**默认绿、悬停蓝**且贴右",
          "width:18px;height:18px" in _rule(css, ".glyph")
          and "width:32px;height:32px" in _rule(css, ".glyph.big")
          and "var(--st-done-bg)" in _rule(css, ".rl-files a"),
          "")
    check("mock（演练/验收）产物**不入产物库** + 5 分钟自动回收 + 导出接口齐备",
          "if rec.get(\"mock\"):" in oi_src and "def reap_mock" in oi_src
          and "/api/export/output" in srv_src and "/api/export/outputs" in srv_src
          and "/api/export/web" in srv_src and "_download" in srv_src,
          "")
    # ★ 行为级（喂合成样本）：真踩过 `status, partial, mock = "", False, False` 整行把
    #   「看内容判 mock」抹掉 ⇒ 逐层产物（X.<层>.md，只有 X.<层>.json、**没有** .run.json）
    #   漏进产物库。这里直接造两份样本扫一遍，别只验源码里有没有那句话。
    import tempfile as _tf
    _bak_dir = oi.OUTPUTS_DIR
    _tmp_dir = Path(_tf.mkdtemp(prefix="oi_mock_"))
    try:
        oi.OUTPUTS_DIR = _tmp_dir
        _mm = "20260101_000000_验收样例"
        (_tmp_dir / (_mm + ".md")).write_text(
            "# 元 DGTF · 验收样例\n**状态**: 已终止（部分 · 手动停止）\n（mock）修行层第 1 圈\n",
            encoding="utf-8")
        (_tmp_dir / (_mm + ".run.json")).write_text(
            json.dumps({"status": "cancelled", "partial": True, "mock": True}), encoding="utf-8")
        (_tmp_dir / (_mm + ".修行.md")).write_text(
            "# 元 DGTF · 验收样例\n（mock）修行层第 1 圈\n", encoding="utf-8")
        (_tmp_dir / (_mm + ".修行.json")).write_text(
            json.dumps({"layer": "修行", "status": "cancelled", "output_name": _mm + ".md"}),
            encoding="utf-8")
        _rr = "20260101_000001_真跑样例"
        (_tmp_dir / (_rr + ".md")).write_text("# 元 DGTF · 真跑样例\n真结论。\n", encoding="utf-8")
        (_tmp_dir / (_rr + ".run.json")).write_text(
            json.dumps({"status": "done", "partial": False, "mock": False}), encoding="utf-8")
        _names = {x["name"] for x in oi.scan(force=True)}
        check("mock 识别**行为级**：逐层产物（无 .run.json）也拦得住；真跑产物照常入库",
              (_mm + ".md") not in _names and (_mm + ".修行.md") not in _names
              and (_rr + ".md") in _names,
              "扫到=" + str(sorted(_names)))
    finally:
        oi.OUTPUTS_DIR = _bak_dir
        oi.invalidate()
        shutil.rmtree(_tmp_dir, ignore_errors=True)
    # ★★ 真跑日志的「层界」有两代，**都要认**：老式 `━━━ 修行 · 第 r/N 圈 …` 进度条，
    #    与现行（实测 V1.23.22 已取消进度条）的 `【0】修行 DGTF（螺旋上限 4 圈）` 层横幅。
    #    不认后者 ⇒ 真跑日志整段落进「共有头」、四层全空（应用里只显示占位）。
    import layers as _LY
    _bar = "═" * 12
    _log_old = ("头\n━━━ 修行 · 第 1/3 圈 · 摊开 · view ━━━\nA\n"
                "━━━ 研究 · 第 1/3 圈 · 摊开 · view ━━━\nB\n")
    _log_new = ("头\n" + _bar + "\n【0】修行 DGTF（螺旋上限 4 圈）\n" + _bar + "\n"
                "   ↻ 第 1/4 圈 · 摊开\nA\n" + _bar + "\n【both】对撞 DGTF（螺旋上限 5 圈）\n"
                + _bar + "\nB\n")
    _so, _sn = _LY.split_log(_log_old), _LY.split_log(_log_new)
    check("日志层界**两代都认**（老式 `━━━ 层 ·` + 现行 `【N】层 DGTF`），四层不再全空",
          "A" in _so.get("修行", "") and "B" in _so.get("研究", "")
          and "A" in _sn.get("修行", "") and "B" in _sn.get("对撞", "")
          and _sn.get("研究", "") == "" and "头" in _sn.get("__head__", "")
          and "【0】" not in _sn.get("__head__", ""),
          "old[修行=%d,研究=%d] new[修行=%d,对撞=%d,研究=%d]"
          % (len(_so.get("修行", "")), len(_so.get("研究", "")),
             len(_sn.get("修行", "")), len(_sn.get("对撞", "")), len(_sn.get("研究", ""))))
    # ★★ 「同类项一起改」：前端 `buildArchiveLanes` 是**第二份**切分器，必须与后端同口径，
    #    否则归档会话（历史对话）仍然四层全空。
    check("前端归档分层器**与后端同口径**（也认 `【N】层 DGTF` 横幅）",
          "【\\s*(?:0|1|both|all)\\s*】" in js or "【\\s*(0|1|both|all)\\s*】" in js,
          "")
    # ★ R22：参数网格「控件竖直对齐」/ 头条与读数台居中 / 导出改两步勾选 /
    #        日志·json 入产物 + 分类标签 / `[标志]` 蓝 + `属性=` 绿
    check("参数面板：标签**定高两行** + 控件贴底 ⇒ 同一行的输入框/下拉**竖直对齐**",
          "justify-content:flex-end" in _rule(css, ".grid label,.grid .field")
          and "min-height:30px" in _rule(css, ".grid .lb")
          and 'class="lb"' in js,
          "")
    check("日志头**三段自适应**（左：状态徽章 / 中：题目+元信息**同栏居中** / 右：三个链接）；读数台每行**居中自适应**",
          "display:flex" in _rule(css, ".runlog-head")
          and "flex:0 1 auto" in _rule(css, ".rl-head-c")
          and "justify-content:center" in _rule(css, ".rl-head-c")
          and "justify-content:center" in _rule(css, ".stat-row")
          and "margin-left:auto" not in _rule(css, ".stat-v"),
          "")
    # ★ R23：日志页背景全透明 / 读数台 30% 不透明 + 放大居中 / 数字缩小 / 圆按钮加粗 /
    #        逐字裂解 + 输入框寄语
    check("日志页背景 **全透明** + 日志色板**加深**（深蓝/深绿/纯黑数字，白画布上读得清）",
          "background:transparent;backdrop-filter:none;" in css
          and "--log-blue:#232F9E" in css and "--log-green:#0E5A22" in css
          and "--log-num:#000000" in css and "--log-hair:rgba(0,0,0,.12)" in css,
          "")
    # ★ R37：字号仍**自适应**（clamp 随窗口高度伸缩）——但层标题 / 小标题改从
    #   `--rl-h1` / `--rl-h2` **变量**取（那两个变量本身就是 clamp）⇒ 判据要认变量。
    check("日志字号**自适应**（clamp：正文字号随窗口高度伸缩；层标题走 --rl-h1 变量）",
          "clamp(" in _rule(css, ".rl-txt")
          and "font-size:var(--rl-h2)" in _rule(css, ".rl-lab")
          and "font-size:var(--rl-h1)" in _rule(css, ".rl-lane-head")
          and "clamp(" in _rule(css, "#rl-question")
          and "--rl-h1:clamp(" in css and "--rl-h2:clamp(" in css,
          _rule(css, ".rl-txt").strip()[:60])
    # ★ R27：画布转**纯白** / 面板页改「本页内容」+ 浅色档
    check("**画布底色**改成纯白（`--canvas`），暗面（抽屉/代码块）仍用 `--ground`",
          "--canvas:#FFFFFF" in css
          and "background:var(--canvas);   /* ★ R27" in css
          and "background:var(--ground)" in _rule(css, ".drawer"),
          "")
    check("日志里的**数字统一墨黑**（原来白，在灰画布上不可见）",
          "color:var(--log-num)}" in css
          and ".rl-meta b{color:var(--log-num)" in css
          and ".rl-lane-head b{color:var(--log-num)}" in css,
          "")
    check("抽屉：**环境信息贴顶**、七个按钮在剩余空间里**上下居中**、落款仍在最底",
          'class="drawer-foot"' in html and "个人工作台" in html
          and "margin-top:auto;margin-bottom:auto" in _rule(css, ".drawer-nav")
          and ".drawer-body::before" not in css,
          "")
    check("画布变浅 ⇒ 落在画布上的前景改深：左上三个圆钮 + 欢迎语",
          "color:#24272F" in _rule(css, ".corner-actions .icon-btn")
          and "color:#1F2229" in _rule(css, ".welcome"),
          "")
    check("读数台：面板**不自己铺色**（整页那层 10% 就是背景）+ 内容**放大**（clamp）+ **竖向居中**",
          "background:transparent" in _rule(css, "#dash-stats")
          and "justify-content:center" in _rule(css, ".stats-body")
          and "clamp(" in _rule(css, ".stat-v"),
          "")
    check("日志**数字统一缩小一档**（`.92em`）且**不加粗**（400）+ 行内 em 间距自适应",
          ".runlog-body b,.rl-meta b{font-size:.92em;font-weight:400;" in css
          and ".rl-num{color:var(--log-blue);font-weight:400" in css
          and ".rl-line{gap:.42em" in css,
          "")
    # ★ R24：面板 20% / 滚动条半透明 / 文本域无滚动条 / 时长单位「秒」为蓝 / 参数标签单行
    check("滚动条滑块是**中性灰**（纯白画布与暗抽屉上都看得见）",
          "*::-webkit-scrollbar-track{background:transparent}" in css
          and "rgba(128,132,140,.36)" in _rule(css, "*::-webkit-scrollbar-thumb"),
          "")
    check("输入框**不出滚动条**（textarea#question 的 webkit 滚动条已隐藏）",
          "display:none" in _rule(css, "textarea#question::-webkit-scrollbar")
          and "scrollbar-width:none;-ms-overflow-style:none" in css,
          "")
    check("时长单位「秒/分/时」**在 `<b>` 之外**（数字墨黑、单位蓝）",
          "function fmtDurHtml" in js and "<b>${fmtDur(secs)}</b>" not in js
          and "' 秒'" in js,
          "")
    check("参数标签**单行**（超长省略号）+ 完整文本挂 `title`",
          "white-space:nowrap" in _rule(css, ".grid .lb")
          and "text-overflow:ellipsis" in _rule(css, ".grid .lb")
          and 'class="lb" title=' in js,
          "")
    check("三个圆按钮**加粗高亮**（笔画 2.1 / 图标 17px）",
          ".icon-btn svg *{stroke-width:2.1}" in css
          and "width:17px" in _rule(css, ".icon-btn svg"),
          "")
    check("发送：问题**逐字裂解成星光** + 输入框换上「引擎已启动」寄语（随进度轮换）",
          ".q-char" in css and "@keyframes qchar" in css
          and "RUN_WHISPER" in js and "function startWhisper" in js
          and "function paintWhisper" in js and "Meta-DGTF 引擎已启动" in js,
          "")
    check("批量导出改**两步勾选**：产物库与检索库都先进入选择模式、再导出选中的",
          "let libExpOn = false" in js and "const libSel = new Set()" in js
          and "let webExpOn = false" in js and "const webSel = new Set()" in js
          and "导出选中 (${n})" in js
          and "p2.append('names', n)" in js
          and "p2.append('qs', x)" in js,
          "")
    check("导出按钮不再压住内容（条目 / 组头右侧让位）",
          "74px" in _rule(css, ".web-group .wg-head")
          and "9px 74px 9px 16px" in _rule(css, ".item"),
          "")
    check("日志 / json **也入产物库**，并带 `kind`(md/log/json) 与 `layer`(总/层) 分类标签",
          "def kind_of" in oi_src and "def layer_of" in oi_src
          and 'glob("*.run.log")' in oi_src and '".packed.json"' in oi_src
          and "chipKind" in js and "chipLayer" in js
          and 'id="lib-kind"' in html and 'id="lib-layer"' in html,
          "")
    check("日志产物的详情用**与日志页同一套**渲染（过滤 + 语义排版）",
          "buildArchiveLanes(body, { created_at: null })" in js
          and "renderLogBody(lines, rlSuspNames(lines))" in js,
          "")
    check("`[标志]` 统一蓝（标志蓝 + 内容绿）；`属性=/位置=` 归正文绿",
          "RL_BRACKET" in js and "return 'bracket'" in js
          and "color:var(--log-green)" in _rule(css, ".rl-attr"),
          "")
    check("会话**独立并行**：新对话不清空别的会话；点会话直接进会话（面板/抽屉都让位）",
          "let followLatest = false" in js and "if (!followLatest) return" in js
          and "taskData = {};" not in js.split("function newChat")[1][:400]
          and "sheetFromDrawer = false;      // 选了会话就直接进会话" in js,
          "")
    check("历史对话：`/api/chats` 可用 + 面板页/按钮/打开逻辑都在（会话各自成页）",
          'id="view-chats"' in html and 'id="chats-list"' in html
          and 'data-sheet="view-chats"' in html
          and "function openChat" in js and "function buildArchiveLanes" in js
          and "def list_chats" in dash_src and isinstance(chats_data.get("chats"), list)
          and all(("started_at" in c) for c in (chats_data.get("chats") or [])),
          "会话 " + str(len(chats_data.get("chats") or [])) + " 条")
    check("重发时**先收起日志**（只变透明、保留占位 ⇒ 输入框不跳位）+ 动画落点后再露",
          "fxPending = true;" in js and "_lg.classList.add('fading')" in js
          and "if (fxPending) return;" in js
          and ".runlog.fading{opacity:0" in css.replace(" ", ""),
          "")
    # ★ [可诊断性] 失败时**报出缺标签的键**（原来只报总数 ⇒ 要自己遍历找）。
    _nolit = [it.get("key") for g in (params_data.get("groups") or [])
              for it in g.get("items", [])
              if "（" not in (it.get("label") or "")]
    check("参数标签统一成「键（中文说明）」（和 CLI 参数同格式）",
          "KEY_CN" in params_src and "def label_for" in params_src
          and not _nolit,
          "参数项 " + str(sum(len(g.get("items", [])) for g in (params_data.get("groups") or [])))
          + " 项，全带中文说明"
          + (("；❌ 缺标签：%r" % (_nolit,)) if _nolit else ""))
    check("模型下拉只给服务端支持的 ID（deepseek-flash / deepseek-v4-pro）",
          set(prm.OPTIONS.get("api.default_model") or [])
          == {"deepseek-flash", "deepseek-v4-pro"},
          repr(prm.OPTIONS.get("api.default_model")))
    check("effort 下拉不含引擎不认的 medium",
          "medium" not in (prm.OPTIONS.get("runtime.effort") or []),
          repr(prm.OPTIONS.get("runtime.effort")))
    check("外链只允许 http(s)（挡 javascript:/私网链接注入）",
          "const safeUrl" in js and ("safeUrl(h.url)" in js or "publicUrl(h.url)" in js)
          and "function publicUrl" in js,
          "")
    check("发送键可切成**终止键**（同一按钮两形态 + 调 /cancel 终止）",
          "setRunBtn" in js and "_SVG_STOP" in js and "/cancel" in js
          and "function stopRun" in js,
          "")
    check("手动终止：按日志重建**部分产物**并标注状态（cancelled / partial）",
          "_build_partial_md" in runner_src and "已终止（部分" in runner_src
          and '"partial": bool(task.get("partial"))' in runner_src
          and 'final = "cancelled"' in runner_src
          and '"status": status' in oi_src and '"partial": partial' in oi_src,
          "")
    check("六个面板都在同一个面板页容器里（点按钮切换页）",
          all(k in html for k in ('id="dash-stats"', 'id="dash-history"', 'id="view-lib"',
                                  'id="view-local"', 'id="view-web"', 'id="adv-panel"'))
          and 'id="sheet"' in html)
    # ★ R37：面板层仍是「固定覆盖 + 85% 透明」，但底色从**白**翻成**漆黑**
    #   （用户：「背景改成漆黑透明，透明度不变」）。
    check("③ 面板层 = **固定覆盖 + 85% 透明**（主视图不隐藏 ⇒ 背景仍隐约可见）",
          "position:fixed" in _rule(css, ".sheet")
          and "inset:0" in _rule(css, ".sheet")
          and "background:rgba(8,9,10,.85)" in _rule(css, ".sheet").replace(" ", "")
          and "body.panel-open main.stage{display:none}" not in css
          and ".sheet-page.active{display:flex" in css.replace(" ", ""),
          _rule(css, ".sheet").strip()[:70])
    check("**开面板把抽屉收回、关面板把抽屉弹回**（面板即本页内容，抽屉让位）",
          "if (sheetFromDrawer) closeDrawer();" in js
          and "if (sheetFromDrawer) { sheetFromDrawer = false; openDrawer(); }" in js
          and "document.body.classList.add('panel-open')" in js
          and "body.panel-open .corner-actions{display:none}" in css,
          "")
    check("③ 面板页就地覆盖成**暗面浅字档**（--t1 近白 / --hair 白 10% / --s1 深底）",
          "--t1:#F5F7FA" in _rule(css, ".sheet")
          and "--hair:rgba(255,255,255,.10)" in _rule(css, ".sheet")
          and "--s1:#111214" in _rule(css, ".sheet")
          and "color:var(--t1)" in _rule(css, ".sheet"),
          "")
    _cmp = html.split('class="composer-row"', 1)
    check("演练模式已挪到输入框那一排（胶囊，与 DSH/附件同排）",
          len(_cmp) == 2 and 'id="mock-row"' in _cmp[1].split("</div>", 1)[0]
          and 'class="pill mock-pill"' in html,
          "")
    check("③ 面板**一层到底 85% 透明**（卡片不再自己铺色）+ 语义色换暗面亮档",
          "background:rgba(8,9,10,.85)" in _rule(css, ".sheet").replace(" ", "")
          and "background:transparent" in _rule(css, ".sheet .panel")
          and "background:transparent" in _rule(css, ".sheet .advanced")
          and "background:transparent" in _rule(css, ".web-group")
          and "--ok:#4ADE80" in _rule(css, ".sheet")
          and "--err:#FF6B6B" in _rule(css, ".sheet")
          and "--warn:#F5C453" in _rule(css, ".sheet"),
          _rule(css, ".sheet").strip()[:56])
    check("③ 列表行悬停改成**暗面淡白洗**（85% 暗底上不再用近黑 .06 洗底）",
          "rgba(255,255,255,.07)" in _rule(
              css, ".sheet .hist:hover,.sheet .item:hover,.sheet .web-group .wg-head:hover")
          or "rgba(255,255,255,.07)" in css,
          "")
    check("③ 面板内容字体**整档翻白 + 加粗**（--t2/--t3 都是浅灰，标题纯白 700）",
          "--t2:#CFD5DE" in _rule(css, ".sheet")
          and "--t3:#8C95A2" in _rule(css, ".sheet")
          and "--accent-hi:#A5B0F5" in _rule(css, ".sheet")
          and "color:#FFFFFF" in _rule(css, ".sheet-title")
          and "font-weight:700" in _rule(css, ".sheet-title"),
          "")
    check("层标题里的 token 单位**写全**（`tokens`，不再是 `tok`）",
          ".toLocaleString()} tokens`" in js and "} tok`" not in js,
          "")
    check("**刷新页面回到首屏**（`followLatest` 初值 false ⇒ 不自动铺出上一条任务）",
          "let followLatest = false" in js
          and "★ R29：刷新页面**回到首屏**" in js,
          "")
    check("面板里**不再重复一条标题行**：计数/时间/说明挪到 sheet-head 当描述",
          html.count('class="panel-head"') == 1          # 只剩「高级参数分组页」那一处
          and html.count('class="panel-title"') == 1
          and 'id="sheet-desc"' in html
          and html.count('class="sd" data-for=') == 7
          and "s.dataset.for === key" in js
          and "flex:0 0 auto" in _rule(css, ".sheet-title"),
          "panel-head=" + str(html.count('class="panel-head"'))
          + " sd=" + str(html.count('class="sd" data-for=')))
    check("抽屉顶部的按钮图形与左上角「面板」键**一致**（R30）",
          html.count('<rect x="3" y="4" width="18" height="16" rx="2.5"') >= 2
          and html.count('<path d="M9.5 4v16"') >= 2,
          "面板图形出现 " + str(html.count('<rect x="3" y="4" width="18" height="16" rx="2.5"')) + " 次")
    check("发送键：图标（箭头 / 终止方块）占**按钮的 25%**（32px 钮 → 14px 图标）+ 整个按钮高亮",
          "width:14px" in _rule(css, "#run-btn.send svg")
          and "flex:0 0 auto" in _rule(css, "#run-btn.send svg")
          and "padding:0" in _rule(css, "#run-btn.send")
          and "0 0 0 3px rgba(94,106,210,.20)" in _rule(css, "#run-btn.send"),
          "")
    check("三个链接与「运行状态」徽章**同一套绿**（字色/底色/描边都对齐）+ 前面一个灯",
          "display:inline-flex" in _rule(css, ".rl-files a")
          and "background:currentColor" in _rule(css, ".rl-files a::before")
          and "border:1px solid var(--st-done-bd)" in _rule(css, ".rl-files a")
          and _rule(css, ".rl-files a").strip().count("var(--st-done-") >= 3,
          "")
    # ★ R40 改口径：`.pend` **不再降透明度** —— 运行中三胶囊要与左徽章**逐项同色**
    #   （用户实测截图：徽章蓝、胶囊看着绿；量化像素后确认色相对，是 opacity 冲淡了）。
    #   「还点不动」由 pointer-events + cursor 承担。
    check("**运行中也能看见这三个按钮**（待生成态 .pend：不可点，但**不降透明度**）",
          ".rl-filesa.pend{pointer-events:none;cursor:default}" in css.replace(" ", "")
          and "opacity" not in css.replace(" ", "").split(".rl-filesa.pend{")[1][:60]
          and "const pend = stamp ? '' : ' pend'" in js,
          "")
    check("列表行：**时间/大小挪到标题同一行**、且上下边距收紧",
          "9px 74px 9px 16px" in _rule(css, ".item")
          and ".item .t .t-r" in css and ".hist .q .q-r" in css
          and "padding:5px 14px" in _rule(css, ".hist")
          and 'class="q-r"' in js and 'class="t-r"' in js,
          "")
    check("参数控件**内容居中**（输入框 / 下拉当前值）",
          "text-align:center" in _rule(css, ".grid input")
          and "text-align:center" in _rule(css, ".dd-cur"),
          "")
    check("下拉悬停背景＝**85% 透明的淡洗**（不再是近黑的 --ground）",
          "rgba(22,23,28,.15)" in _rule(css, ".dd-btn:hover")
          and "var(--ground)" not in _rule(css, ".dd-btn:hover"),
          "")
    check("日志**收官/结论句**（停止 / 产物已落盘 / 完成）改**蓝色加深**（不跟正文绿）",
          "RL_MARK" in js and "rl-mark" in css
          and "color:var(--log-blue)" in _rule(css, ".rl-mark")
          and "RL_MARK.test(rest) ? 'rl-txt rl-mark'" in js,
          "")
    # ★ R37：滚动条从「26px 长胶囊」缩成**12px 圆点**，并且**可拖**（R33 是纯指示器）。
    check("⑥ 日志滚动条＝**可拖的圆点**（隐藏原生、自绘 #rl-bar 跟滚动走 / 可拖）",
          'id="rl-bar"' in html and "function updateRlBar" in js
          and "scrollbar-width:none" in _rule(css, "#runlog-body")
          and "display:none" in _rule(css, "#runlog-body::-webkit-scrollbar")
          and "border-radius:50%" in _rule(css, "#rl-bar")
          and "width:12px;height:12px" in _rule(css, "#rl-bar").replace(" ", "")
          and "pointer-events:auto" in _rule(css, "#rl-bar")
          and "function bindRlBarDrag" in js,
          "")
    check("抽屉按钮组居中后**整体上移一段**（transform:translateY(clamp(…))）",
          "transform:translateY(clamp(" in _rule(css, ".drawer-nav")
          and "margin-top:auto;margin-bottom:auto" in _rule(css, ".drawer-nav"),
          _rule(css, ".drawer-nav").strip()[:60])
    _flat = css.replace(" ", "").replace("\n", "")
    check("面板内容区可滚（flex:1 + min-height:0，否则长列表被撑破裁掉）",
          ".sheet.panel>.lib-list,.sheet.panel>.stats-body,.sheet.panel>.hist-list,"
          ".sheet.panel>.adv-group-body{flex:11auto;min-height:0;overflow:auto}" in _flat,
          "")
    check("层级链正确：详情浮层 90 > 下拉菜单 80（面板已在本页流内，不再压浮层）",
          "z-index:90" in _rule(css, ".detail")
          and "z-index:80" in _rule(css, ".dd-menu"),
          _rule(css, ".detail").strip()[:44])
    check("参数**值**默认灰（标签深色 / 值灰，读起来分层）",
          "color:var(--t2)" in _rule(css, ".grid input")
          and "color:var(--t2)" in _rule(css, ".dd-cur"),
          "")
    check("下拉菜单是 **fixed 且层级 80**（跳出面板裁剪 / 不会被盖住）",
          "position:fixed" in _rule(css, ".dd-menu")
          and "z-index:80" in _rule(css, ".dd-menu"),
          _rule(css, ".dd-menu").strip()[:48])
    check("参数标签 / 读数台标签**默认白色**",
          "color:var(--t1)" in _rule(css, ".grid label,.grid .field")
          and "color:var(--t1)" in _rule(css, ".stat-k"),
          "")
    check("信息行：**只有时间日期**推到右边（.ms-right），其余一律靠左",
          ".ms-right{margin-left:auto}" in _flat
          and "justify-content:flex-end" not in _rule(css, ".item .m"),
          "")
    check("圆按钮统一：34px、背景透明、图标白色（只留图标）",
          "width:34px" in _rule(css, ".icon-btn")
          and "background:transparent" in _rule(css, ".icon-btn"),
          _rule(css, ".icon-btn").strip()[:52])
    #   ★ R38 改口径：平移量从**整幅抽屉宽**改成**半量**（`--shift-half`）—— 用户要求
    #     「右边页面内容始终居中自适应」。几何：内容中心先随 padding 落在
    #     `(shift-w + 100vw)/2`，要让**平移后**仍落在该点 ⇒ 平移量 = `shift-w / 2`。
    check("抽屉打开时首屏让位：主区**纯 translate 平移**（width 恒 100%，不再改宽度）",
          "transform:translateX(var(--shift-half))" in _rule(css, "body.drawer-open main.stage")
          and "width:" not in _rule(css, "body.drawer-open main.stage")
          and "margin-left:" not in _rule(css, "body.drawer-open main.stage")
          and "--shift-w:" in css and "--shift-half:calc(var(--shift-w)/2)"
          in css.replace(" ", ""),
          _rule(css, "body.drawer-open main.stage").strip()[:56])
    check("④ 让位量**封顶为视口一半**（窄视口下右侧恒留一半可见 ⇒「展开右边看不见」修掉）",
          "--shift-w:min(var(--drawer-w),50vw)" in css.replace(" ", ""),
          "")
    #   ★ R38：原来是「右缘补偿」（只加右 padding）⇒ 内容整体偏右。改成**左右对称**，
    #     这样被让出的半幅里内容才是真居中（用户报「始终居中自适应调整大小边距」）。
    check("④ ★R38 让位时给主区**左右对称**补偿内边距（内容在被让出的半幅里居中）",
          "padding-left:calc(18px+var(--shift-half))"
          in css.replace(" ", "").replace("\n", "")
          and "padding-right:calc(18px+var(--shift-half))"
          in css.replace(" ", "").replace("\n", ""),
          "")
    check("④ 运行态内容宽度在让位时**同步收窄**（否则右缘仍被顶出视口）",
          "body.drawer-open.stage-run .runlog" in css
          and "body.drawer-open.stage-run .composer" in css
          and "max-width:min(1080px,calc(100vw-var(--shift-w)-36px))"
          in css.replace(" ", "").replace("\n", ""),
          "")
    check("④ ★R38 平移**放慢到 .6s**（主区 + 抽屉都慢，用户要求「平移速度慢一点」）",
          "transition:transform .6s var(--ease)"
          in _rule(css, "main.stage").replace(" ", " ")
          and "transition:transform .6s var(--ease)" in _rule(css, ".drawer")
          and "margin-left" not in _rule(css, "main.stage"),
          _rule(css, "main.stage").strip()[:64])
    check("④ ★R38 抽屉让位时**淡出**（opacity 也进过渡，不是硬切）",
          "opacity .6s var(--ease)" in _rule(css, ".drawer"),
          _rule(css, ".drawer").strip()[:64])
    check("④ ★R38 抽屉打开时透明度**复原到 1**（否则展开后是半透明的一层灰膜）",
          ".drawer.open{transform:none;opacity:1}" in css.replace("\n", ""),
          css[css.find(".drawer.open{"):css.find(".drawer.open{") + 48])
    # ══ ★ R37 一揽子（用户 10 图 / 7 条）══════════════════════════════════════
    # ① 后端把日志共有头（`__head__`）随 /layers 一起下发 -------------------------
    #   引擎（`Meta-DGTF-V1.23.22.py`）本来就在进层循环前打这一段（`调度：` / `螺旋上限`
    #   / `并行模式` / `回来通道` / `运行期总控`），它落在 `layers.split_log()` 的
    #   `__head__` 桶里；前端以前**只渲染 LANE_NAMES**，整段被丢掉 ⇒ 用户看不到。
    #   ★★ 变异体教训：早先把这条写成 `... and "_LAYER" in runner_src or "split_log"
    #      in runner_src` —— `or` 让整个表达式**恒真**，把「head 不下发」的变异体
    #      放过去了（方向错的断言比没断言更危险）。现在只认**下发 head 那一行**。
    check("① 后端把日志共有头（`__head__`）随 /layers 一起下发",
          '"head": parts.get("__head__", "")' in runner_src,
          "")
    check("① 前端把 head 渲成**日志开头块**（`.rl-lane.rl-boot`），不再整段丢掉",
          "rl-lane rl-boot" in js and "src.head" in js,
          "")
    check("① 开头块有样式（与层块区分：一道轻下边分隔）",
          "border-bottom:1px solid var(--log-hair)" in _rule(css, ".rl-boot"),
          _rule(css, ".rl-boot").strip()[:64])
    # ★★ 变异体教训：早先写 `"载入调度配置" in 源文本` —— 而**注释里也有这个词**
    #   （就是本行上面那句说明），于是「把真正的 log(...) 删掉」照样全绿。
    #   判据必须落在**可执行的那句**上，不能落在注释上。
    _mock_src = (_app / "mock_engine.py").read_text(encoding="utf-8")
    check("① mock 引擎也在开头打同样的启动信息（演示 / 自检能看到）",
          'log("载入调度配置：' in _mock_src and 'log("螺旋上限（每层圈数）：' in _mock_src
          and 'log("运行期总控：' in _mock_src,
          "")
    # ② 层标题（`↻ 第 N/M 圈 · 摊开`）与内容**同一套排版规范**，自适应 ---------
    check("② 日志区字号**收敛成两个变量**（--rl-h1 / --rl-h2，一处改全齐）",
          "--rl-h1:clamp(14px,2vh,18px)" in css.replace(" ", "")
          and "--rl-h2:clamp(13.5px,1.9vh,17px)" in css.replace(" ", ""),
          "")
    check("② 层标题与「第 N/M 圈」**共用 --rl-h1**（字号 / 行高一致 ⇒ 观感齐）",
          "font-size:var(--rl-h1)" in _rule(css, ".rl-lane-head")
          and "font-size:var(--rl-h1)" in _rule(css, ".rl-round")
          and "font-size:var(--rl-h1)" in _rule(css, ".rl-title")
          and "line-height:1.35" in _rule(css, ".rl-round"),
          _rule(css, ".rl-round").strip()[:64])
    check("② 小标题 / 步骤 / 名称标签 / 属性**共用 --rl-h2**（规范统一 + 自适应）",
          "font-size:var(--rl-h2)" in _rule(css, ".rl-lab")
          and "font-size:var(--rl-h2)" in _rule(css, ".rl-step")
          and "font-size:var(--rl-h2)" in _rule(css, ".rl-attr")
          and "font-size:var(--rl-h2)" in _rule(css, ".rl-fold>summary"),
          "")
    # ③ 面板背景**漆黑透明**（透明度不变 = 85%）+ 白字加粗高亮 -------------------
    check("③ 面板背景**漆黑透明**（rgba(8,9,10,.85)，仍 85% 透明度）",
          "background:rgba(8,9,10,.85)" in _rule(css, ".sheet").replace(" ", ""),
          _rule(css, ".sheet").strip()[:60])
    check("③ 面板内字色翻成**浅档**（--t1 近白 / 全局加粗）",
          "--t1:#F5F7FA" in _rule(css, ".sheet")
          and "font-weight:500" in _rule(css, ".sheet"),
          "")
    check("③ 面板标题**纯白 + 700**（加粗高亮）",
          "color:#FFFFFF" in _rule(css, ".sheet-title")
          and "font-weight:700" in _rule(css, ".sheet-title"),
          _rule(css, ".sheet-title").strip()[:60])
    check("③ 参数标签在暗面上**白字加粗**",
          "color:var(--t1)" in _rule(css, ".adv-group-body .lb,.adv-group-body .grid label")
          and "font-weight:600" in _rule(
              css, ".adv-group-body .lb,.adv-group-body .grid label"),
          "")
    # ★ 残留的「浅底深字」必须一起翻（用户说「类似的一起改」）——
    #   这几条是本轮真正踩到的漏网：保存反馈浮层 / 待保存小标 / 只读密钥胶囊 / 危险键 hover。
    check("③ 保存反馈浮层翻成**暗面**（不再是 rgba(255,255,255,.96) 白底黑字）",
          "background:rgba(12,14,17,.96)" in _rule(css, ".adv-toast").replace(" ", "")
          and "rgba(255,255,255,.96)" not in css.replace(" ", ""),
          _rule(css, ".adv-toast").strip()[:60])
    check("③ 浮层三态（ok/warn/err）同步翻成**暗底亮字**",
          "background:rgba(10,20,13,.96)" in _rule(css, ".adv-toast.ok").replace(" ", "")
          and "background:rgba(22,19,10,.96)" in _rule(css, ".adv-toast.warn").replace(" ", "")
          and "background:rgba(24,12,12,.96)" in _rule(css, ".adv-toast.err").replace(" ", ""),
          "")
    check("③ 「N 项待保存」小标 / 只读密钥胶囊翻成**暗面亮字**",
          "color:#F5C453" in _rule(css, ".nav-btn em.dirty")
          and "color:#7EE6A0" in _rule(css, ".grid .ro.ro-key")
          and "rgba(30,122,52,.12)" not in css.replace(" ", ""),
          "")
    check("③ 危险键（恢复出厂设置）hover 翻成**亮红字 + 淡红底**",
          "color:#FFB4AA" in _rule(css, ".sheet-actions button.ghost.danger:hover")
          and "color:#8A1A12" not in css,
          _rule(css, ".sheet-actions button.ghost.danger:hover").strip()[:60])
    check("③ 禁用态 hover 用**主题字色**（不再写死 #1F2229 深字）",
          "color:var(--t3)" in _rule(css, ".sheet-actions button.ghost:disabled:hover")
          and "#1F2229}" not in css.replace(" ", "").replace("\n", ""),
          "")
    # ⑤ 三个状态胶囊与「运行中」**字体大小粗细一致** + 前面的点改**实心高亮灯** ----
    _chip = _rule(css, ".chip")
    _kinds = _rule(css, ".chip.k-md")
    check("⑤ 状态胶囊 `.chip`：字号**上调到 clamp 档**（原 11px 比旁边 12~14.5 小）",
          "font-size:clamp(11.5px,1.6vh,13.5px)" in _chip.replace(" ", ""),
          _chip.strip()[:64])
    check("⑤ `.chip` **加粗 600**（与右侧链接 700 同观感）",
          "font-weight:600" in _chip,
          "")
    check("⑤ `.chip` 圆角改成**胶囊 20px**（原来 4px 方角，与被对齐的链接不一致）",
          "border-radius:20px" in _chip,
          "")
    check("⑤ 运行状态徽章 `.badge` 与三个链接 `.rl-files a` **字号 / 粗细完全一致**",
          "font-size:clamp(12px,1.7vh,14.5px)" in _rule(css, ".badge").replace(" ", "")
          and "font-size:clamp(12px,1.7vh,14.5px)"
          in _rule(css, ".rl-files a").replace(" ", "")
          and "font-weight:700" in _rule(css, ".badge")
          and "font-weight:700" in _rule(css, ".rl-files a"),
          "")
    check("⑤ 前面的点改成**实心高亮灯**：6px + currentColor + 同色光晕（三处一致）",
          "width:6px;height:6px" in _rule(css, ".badge::before").replace(" ", "")
          and "box-shadow:0 0 5px currentColor" in _rule(css, ".badge::before")
          and "width:6px;height:6px" in _rule(css, ".rl-files a::before").replace(" ", "")
          and "box-shadow:0 0 5px currentColor" in _rule(css, ".rl-files a::before"),
          "")
    # ⑥ 日志滚动条改成**可拖圆点**（R33 因 drag 抖动设过 pointer-events:none）-----
    # ══ ★ R38 ④：时间 / 导出字体改白（用户 5/6 图：「时间和导出字体显示白色类似的一并改」）
    #   ★ 缺口说明：本轮变异体 M29/M30 实测「能红」是**误打误撞**（改 CSS 时碰红了别的
    #     判据）—— 这一段此前**根本没有判据**。补上，且查的是「颜色档位」而不是「有没有这行」。
    check("④ 产物导出键 `.item .exp` / `.wg-exp` 字色 = **亮档 --t1**（原来灰 --t3）",
          "color:var(--t1)" in _rule(css, ".item .exp,.wg-exp")
          and "color:var(--t3)" not in _rule(css, ".item .exp,.wg-exp"),
          _rule(css, ".item .exp,.wg-exp").strip()[:64])
    check("④ 导出键悬停翻**纯白**（在深色条目上要看得见）",
          "color:#FFFFFF" in _rule(css, ".item:hover .exp,.web-group:hover .wg-exp"),
          _rule(css, ".item:hover .exp,.web-group:hover .wg-exp").strip()[:64])
    check("④ 联网库时间行 `.wg-meta` = **亮档 --t1 + 500**（图 5 那一栏）",
          "color:var(--t1)" in _rule(css, ".wg-meta")
          and "font-weight:500" in _rule(css, ".wg-meta"),
          _rule(css, ".wg-meta").strip()[:64])
    check("④ 产物条目时间 `.item .t .t-r` = **亮档 --t1 + 500**",
          "color:var(--t1)" in _rule(css, ".item .t .t-r")
          and "font-weight:500" in _rule(css, ".item .t .t-r"),
          _rule(css, ".item .t .t-r").strip()[:64])
    check("④ 历史对话时间 `.hist .m` / `.q-r` = **亮档 --t1 + 500**（与上面同一套）",
          "color:var(--t1)" in _rule(css, ".hist .m")
          and "font-weight:500" in _rule(css, ".hist .m")
          and "color:var(--t1)" in _rule(css, ".hist .q .q-r"),
          _rule(css, ".hist .m").strip()[:56])
    check("④ 「为什么这么判」保持**次级灰 --t3**（不能整片刷白 ⇒ 就没了层次）",
          "color:var(--t3)" in _rule(css, ".hist .m .why"),
          _rule(css, ".hist .m .why").strip()[:56])
    # ── ★ R38 ⑤：右侧三胶囊随任务状态变色（用户 7 图：「右边三个按钮和左边按钮运行状态
    #   一致，灯和字体颜色变化一致」）—— 原来 `.rl-files a` 颜色**硬编码绿**、与左徽章不同步。
    check("⑤ 三胶囊按任务状态挂 `st-*` 容器类（前端从 t.status 拼）",
          "files.className = 'rl-files st-' + st" in js,
          "")
    # ★ 陷阱：`.badge.running` 的**第一条**同名规则是 `.badge.running{color:var(--accent)}`
    #   （浅底档），日志页那套在 `.runlog-head .badge.running`（#2F3AA8）。
    #   三胶囊对齐的**是日志页那套**（同一个 `.runlog-head` 里并排显示）⇒ 判据要读它。
    # ★★ R39 口径升级（判据随实现更新，不是放宽）：两边改成**同源变量**后色值只剩一份
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
          _rule(css, ".rl-files.st-running a").strip()[:64])
    check("⑤ `.rl-files.st-queued` 与左徽章 `.runlog-head .badge.queued` 同色**且同底**"
          "（同源 --st-queued-c/-bg，其值 #8A6414 琥珀）",
          _stat_same("queued", "#8A6414"),
          _rule(css, ".rl-files.st-queued a").strip()[:64])
    check("⑤ `.rl-files.st-error` 与左徽章 `.runlog-head .badge.error` 同色**且同底**"
          "（同源 --st-error-c/-bg，其值 #B42318 红）",
          _stat_same("error", "#B42318"),
          _rule(css, ".rl-files.st-error a").strip()[:64])
    check("⑤ 取消 / 中断 / 已停 归到**同一档**（与 `.badge` 的归法一致：都走 --st-queued-*）",
          ".rl-files.st-cancelled a" in css and ".rl-files.st-canceled a" in css
          and ".rl-files.st-interrupted a" in css
          and "var(--st-queued-c)" in css[css.find(".rl-files.st-cancelled a"):
                                          css.find(".rl-files.st-cancelled a") + 240],
          "")
    check("⑤ running 态的胶囊**灯在脉动**（与左徽章同一套 pulse，不是静态绿点）",
          "animation:pulse" in _rule(css, ".rl-files.st-running a::before"),
          _rule(css, ".rl-files.st-running a::before").strip()[:56])
    # ★ 注意口径：`.rl-files a` 基线的绿**是故意留的**（= `.badge.done` 同一套，
    #   done 态就该是绿的）。要证的是「**非 done 档都被 `st-*` 压过**」——
    #   所以查的是四档 `st-*` 齐备，而不是「基线不含绿」。
    check("⑤ 三胶囊**四档齐备**：running / queued / error / done 各有一条 `st-*`",
          all((".rl-files.st-" + s) in css
              for s in ("running", "queued", "error", "done")),
          "缺=" + str([s for s in ("running", "queued", "error", "done")
                       if (".rl-files.st-" + s) not in css]))
    # ★ R38 补：既然「基线的绿是故意的」，就把它**锚起来** —— 基线的绿必须与左徽章
    #   done 档同色（R34 语义）。此前没有判据 ⇒ M39（把基线改成别的色）全绿漏检。
    check("⑤ 三胶囊**完成态基线** = 左徽章同款绿（`.rl-files a` 也走 --st-done-*）",
          "var(--st-done-c)" in _rule(css, ".rl-files a")
          and "var(--st-done-bg)" in _rule(css, ".rl-files a")
          and _stat_same("done", "#1E7A34"),
          _rule(css, ".rl-files a").strip()[:64].replace("\n", " "))
    check("⑤ `.rl-files.st-done` 与左徽章 `.runlog-head .badge.done` 同色**且同底**"
          "（同源 --st-done-c/-bg，其值 #1E7A34 绿）",
          _stat_same("done", "#1E7A34"),
          _rule(css, ".rl-files.st-done a").strip()[:56])
    check("⑥ 原生细长滚动条**隐藏**（scrollbar-width:none + ::-webkit-scrollbar 宽 0）",
          "scrollbar-width:none" in _rule(css, "#runlog-body")
          and "width:0;height:0;display:none" in _rule(css, "#runlog-body::-webkit-scrollbar").replace(" ", ""),
          "")
    check("⑥ 自绘滚动条 = **圆形点**（border-radius:50% + 12px 见方）",
          "border-radius:50%" in _rule(css, "#rl-bar")
          and "width:12px;height:12px" in _rule(css, "#rl-bar").replace(" ", ""),
          _rule(css, "#rl-bar").strip()[:64])
    # ★ 注意：`#rl-bar.drag` 有**两条**规则（一条与 `:hover` 合并写背景、一条单给
    #   cursor）—— `_rule()` 取**第一条**，取不到 cursor:grabbing。这里直接对扁平
    #   后的全文断言（够用且更稳，不依赖规则顺序）。
    _flat_bar = css.replace(" ", "").replace("\n", "")
    check("⑥ 圆点**可点可拖**（pointer-events:auto + cursor:grab / grabbing）",
          "pointer-events:auto" in _rule(css, "#rl-bar")
          and "cursor:grab" in _rule(css, "#rl-bar")
          and "cursor:grabbing" in _flat_bar
          and "pointer-events:none" not in _rule(css, "#rl-bar"),
          "")
    check("⑥ 拖拽**真的接线**（bindRlBarDrag：pointerdown/move/up + setPointerCapture）",
          "function bindRlBarDrag" in js and "setPointerCapture" in js
          and "pointerdown" in js and "bindRlBarDrag();" in js,
          "")
    check("⑥ 拖动时**禁止滚动事件回写位置**（rlDragging 闸，避免与 scroll 抢 ⇒ 抖）",
          "rlDragging" in js and "if (rlDragging) return" in js,
          "")
    # ── 本地资料库的「现成锚点快照」默认展开
    check("本地资料库的「现成锚点快照」默认展开",
          '<details class="cand" open>' in html)
    check("联网检索结果库有聚合/过滤控件",
          'id="web-q"' in html and 'id="web-mode"' in html)
    check("高级参数下拉改自绘（原生 select + data-cfg 已不存在）",
          "ddField" in js and "openDD" in js and "<select data-cfg=" not in js)

    s, cfg = _get(base, "/api/config")
    check("config 返回引擎名", s == 200 and str(cfg.get("engine", "")).endswith(".py"),
          str(cfg.get("engine")))
    check("config 不泄露密钥值", "DGTF_API_KEY" not in json.dumps(cfg))

    s, ol = _get(base, "/api/outputs")
    check("产物列表非空", s == 200 and ol.get("count", 0) > 0, f"共 {ol.get('count')} 份")
    s, sl = _get(base, "/api/outputs?q=" + urllib.parse.quote("数字IC"))
    check("关键词检索命中", s == 200 and sl.get("count", 0) >= 1, f"命中 {sl.get('count')}")
    s, fc = _get(base, "/api/outputs?facets=1")
    check("facets 含四个维度",
          set(fc.keys()) == {"decidability", "orientation", "parallel", "stop"})

    # ── 个人工作台读数（/api/dashboard）────────────────────────────
    s, db = _get(base, "/api/dashboard")
    _c, _p, _st = db.get("counts") or {}, db.get("packed") or {}, db.get("stop") or {}
    check("工作台读数接口可用（轮次 / 累计 / 跑完浅跑 / 历史）",
          s == 200 and _c.get("main", 0) > 0
          and _c.get("total_files", 0) >= _c.get("main", 0)
          and isinstance(db.get("history"), list) and "covered" in _p,
          f"轮次 {_c.get('main')} / 文件 {_c.get('total_files')} / 有读数 {_p.get('covered')}")
    check("读数台报覆盖率（不把「有读数的几轮」当全体）",
          _p.get("covered", 0) <= _c.get("main", 0)
          and _st.get("known", 0) <= _c.get("main", 0),
          f"packed {_p.get('covered')} · 停止可判 {_st.get('known')}")

    # 下面三条是**合成样本**：不依赖真实 outputs 里恰好长什么样，
    # 且每条都带「换个字段结论必须变」的对照（判别力，不是跑通就算过）
    _m, _l = dashboard.classify(
        ["20261010_125123_A.md", "20261010_125123_A.元.md", "readme.md"])
    check("层产物不重复计入「深究轮次」（合成样本）",
          _m == ["20261010_125123_A.md"] and _l == ["20261010_125123_A.元.md"],
          f"主 {_m} / 层 {_l}")
    _s1 = dashboard.parse_stop("**停止**：自然 4 层 / 被截断（体力耗尽）0 层")
    _s2 = dashboard.parse_stop("**停止**：自然 2 层 / 被截断（体力耗尽）2 层")
    _s3 = dashboard.parse_stop("**停止**: 自然 1 层 / 被截断（体力耗尽）1 层")  # 半角冒号
    _s0 = dashboard.parse_stop("# Meta-DGTF · 没有停止那一行")
    check("浅跑判据：被截断 N>0 才算浅跑，半角/全角冒号都认（合成样本）",
          _s1["natural"] == 4 and _s1["cut"] == 0 and not _s1["shallow"] and _s1["known"]
          and _s2["cut"] == 2 and _s2["shallow"] and _s3["shallow"] and not _s0["known"],
          f"全角 {_s1['natural']}/{_s1['cut']} · 截断 {_s2['cut']} · 半角 {_s3['cut']}")
    _sp = dashboard.sum_packed([
        {"llm_calls": 3, "llm_tokens": 100},
        {"llm_calls": None, "llm_tokens": None},
    ])
    check("累计 token 只累加有读数的轮次（合成样本：覆盖率 1/2）",
          _sp["calls"] == 3 and _sp["tokens"] == 100 and _sp["covered"] == 1, str(_sp))

    check_r39_frontend(css, js, html)
    check_r40_frontend(css, js, html, runner_src)
    check_r41_frontend(css)
    check_r42_server(srv_src)
    check_r44_frontend(css, js, html, srv_src, lib_src, dp_src)
    check_r45_frontend(css, js, html, srv_src, lib_src)
    check_r46_frontend(js)
    check_r47_frontend(css, js, html, srv_src, lib_src)
    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────
    # ★ 这是「通过工作台发起的真跑全部 2–7 秒即崩」的根因：
    #   memory.channels 出厂是列表，经参数面板往返后变字符串 ⇒ 引擎
    #   `for c in m` 逐字符迭代 ⇒ ValueError: 未知通道 'c'。
    #   用**构造性**判据证明修好（不是「看起来对」，是产物里类型确实是列表）。
    _tmpy = oi.PROJECT_ROOT / "_audit_tmp" / "_selftest_params.yaml"
    _p1 = prm.build_temp_config(
        {"memory.channels": "content,context,self",
         "web_search.domain_tier_rules": "前端只会给字符串",
         "runtime.effort": "high"}, _tmpy)
    _d1 = yaml.safe_load(Path(_p1).read_text(encoding="utf-8"))
    _ch = (_d1.get("memory") or {}).get("channels")
    _ru = (_d1.get("web_search") or {}).get("domain_tier_rules")
    check("参数往返：列表型键回写成列表、嵌套结构保持原样（真跑崩因）",
          isinstance(_ch, list) and _ch == ["content", "context", "self"]
          and isinstance(_ru, list) and bool(_ru) and isinstance(_ru[0], list),
          f"channels={_ch!r}")
    # 判别力对照：单值必须还原成 ['self']；若实现是「原样写字符串」，这里会拿到 'self'
    _p2 = prm.build_temp_config({"memory.channels": "self"}, _tmpy)
    _ch2 = yaml.safe_load(Path(_p2).read_text(encoding="utf-8"))["memory"]["channels"]
    check("参数往返有判别力（单值 → ['self']，不是字符串 'self'）",
          _ch2 == ["self"] and not isinstance(_ch2, str), repr(_ch2))

    # ── ★ 参数**持久化写回**（用户报「参数填了保存不了」的根因）──────────
    #   判据分三层，且**不碰真配置**（把 prm.CFG 指到副本上再跑）：
    #     ① 值确实变了（语义）
    #     ② 注释一行不少（保真 —— 这份 yaml 的注释就是配置说明书）
    #     ③ 没点名的键一个不变（无污染）
    # ── 参数「保存」写回**用户配置**（R36 口径：出厂 yaml 只读，永不改）───────────
    #   ★ 测试隔离：把 `USER_CFG` 指到 _audit_tmp 下的一份临时文件 —— 别动用户真配置。
    _save_dir = oi.PROJECT_ROOT / "_audit_tmp"
    _save_dir.mkdir(parents=True, exist_ok=True)
    _real_user = prm.USER_CFG
    _real_cfg = prm.CFG
    _uf = _save_dir / "_selftest_user_cfg.yaml"
    if _uf.exists():
        _uf.unlink()
    _cfg_bytes0 = _real_cfg.read_bytes()          # 出厂 yaml 的原始字节（全程要比对）
    _flat0 = prm._load_yaml_flat(_real_cfg)
    try:
        prm.USER_CFG = _uf
        _res = prm.save_params({"api.default_model": "deepseek-chat",
                                "api.timeout": "333"})
        _flat1 = prm._load_yaml_flat(_uf)
    finally:
        prm.USER_CFG = _real_user
    check("参数「保存」真的写回用户配置文件（值变了）",
          sorted(_res["saved"]) == ["api.default_model", "api.timeout"]
          and _flat1["api.default_model"] == "deepseek-chat"
          and _flat1["api.timeout"] == 333,
          f"saved={_res['saved']}")
    check("写回按原类型还原（数字仍 int，不是字符串）",
          isinstance(_flat1["api.timeout"], int),
          f"timeout={_flat1['api.timeout']!r}")
    check("★ 出厂 dgtf_config.yaml **一个字节都没动**（这是「恢复默认」能成立的前提）",
          _real_cfg.read_bytes() == _cfg_bytes0,
          f"{len(_cfg_bytes0)} 字节")
    check("★ 写回文件是**用户配置**（用户配置里有 → 出厂配置里没有）",
          _uf.exists()
          and prm._load_yaml_flat(_uf).get("api.timeout") == 333
          and _flat0.get("api.timeout") != 333,
          f"{_uf.name}: timeout={prm._load_yaml_flat(_uf).get('api.timeout')!r}")
    # 生效值 = 用户配置覆盖出厂
    _eff = prm.effective_flat() if _real_user == prm.USER_CFG else None
    try:
        prm.USER_CFG = _uf
        _eff = prm.effective_flat()
    finally:
        prm.USER_CFG = _real_user
    check("生效值 = **用户配置优先 + 出厂兜底**（改了的是用户值，没改的仍是出厂值）",
          _eff["api.default_model"] == "deepseek-chat"
          and _eff["api.timeout"] == 333
          and _eff["auto.enabled"] == _flat0["auto.enabled"],
          f"model={_eff['api.default_model']}")
    # 幂等：同样覆盖再跑一次 ⇒ 第二次必须全 unchanged
    _res2 = None
    try:
        prm.USER_CFG = _uf
        _res2 = prm.save_params({"api.default_model": "deepseek-chat",
                                 "api.timeout": "333"})
    finally:
        prm.USER_CFG = _real_user
    check("写回**幂等**（同样覆盖连跑两次，第二次全 unchanged）",
          not _res2["saved"]
          and sorted(_res2["unchanged"]) == ["api.default_model", "api.timeout"],
          f"saved={_res2['saved']} unchanged={_res2['unchanged']}")
    # ★★ 「恢复默认」= 删用户配置 ⇒ 值回落出厂。这是用户明确要的按钮。
    try:
        prm.USER_CFG = _uf
        _rr = prm.reset_params()
        _eff2 = prm.effective_flat()
    finally:
        prm.USER_CFG = _real_user
        if _uf.exists():
            _uf.unlink()
    check("★「恢复默认配置」删掉用户配置后，值**回落到出厂**",
          _rr["ok"] and _rr["removed"] and not _uf.exists()
          and _eff2["api.default_model"] == _flat0["api.default_model"]
          and _eff2["api.timeout"] == _flat0["api.timeout"],
          f"model 回到 {_eff2['api.default_model']}")
    check("★ 恢复默认**只删用户配置、绝不动出厂 yaml**（否则就没有「默认」可言了）",
          _real_cfg.read_bytes() == _cfg_bytes0,
          f"{len(_cfg_bytes0)} 字节")
    # 幂等 2：本来就没有用户配置时，再恢复一次也必须 ok 且不报错
    try:
        prm.USER_CFG = _uf
        _rr2 = prm.reset_params()
    finally:
        prm.USER_CFG = _real_user
    check("「恢复默认」对**已无用户配置**的情况幂等（ok 且 removed=False）",
          _rr2["ok"] and not _rr2["removed"] and not _rr2["error"],
          str(_rr2))
    # 密钥键：后端也必须拒（前端不给 data-cfg 是第一道，这里是第二道）
    try:
        prm.USER_CFG = _uf
        _res3 = prm.save_params({"api.key": "sk-恶意值", "web_search.api_key_env": "X"})
        _uf_txt = _uf.read_text(encoding="utf-8") if _uf.exists() else ""
    finally:
        prm.USER_CFG = _real_user
        if _uf.exists():
            _uf.unlink()
    check("密钥键**拒绝写回**（前端不给 data-cfg + 后端再挡一层）",
          set(_res3["skipped"]) == {"api.key", "web_search.api_key_env"}
          and not _res3["saved"] and not _uf_txt,
          f"skipped={_res3['skipped']}")
    # 面板只读渲染：密钥项必须带 ro-key 标记（用户看得出是密钥类）
    check("密钥键在 /api/params 里标成只读且**不回传值**",
          all(it.get("type") == "readonly" and it.get("readonly_key")
              for g in (params_data.get("groups") or [])
              for it in (g.get("items") or []) if it.get("key") in prm.READONLY_KEYS)
          and not any(str(it.get("value") or "").startswith("sk-")
                      for g in (params_data.get("groups") or [])
                      for it in (g.get("items") or [])),
          f"只读键 {len([it for g in (params_data.get('groups') or []) for it in (g.get('items') or []) if it.get('readonly_key')])} 个")

    # ══ ★ R38：CLM（CLI 级）参数持久化 —— 用户报「CLM 参数设置了保存不了」的根因链 ══
    #   12 个键**不在出厂 yaml 里**（它们是引擎 CLI flag），所以要单独一条路：
    #     存 → 用户配置的 `cli:` 段；读回 → `load_cli_saved()`；每任务跑完 → `clear_cli_saved()`
    #   ★ 隔离同上：把 `USER_CFG` 指到 _audit_tmp 下的临时文件，绝不动用户真配置。
    _cf = _save_dir / "_selftest_cli_cfg.yaml"
    if _cf.exists():
        _cf.unlink()
    # ★★ 先钉住**名单本身**（变异体 M13 实测漏检：把名单里 `thinking` 改成 `thinking_`，
    #    后面所有「存取」判据都只喂 route/rounds，照样全绿 ⇒ 名单被改坏了没人管）。
    #    「N 个来源投票」必须报可用来源数 —— 这里两个来源：后端元组 + 前端 ADV 表。
    check("★R38 CLM 键**名单本身**正确（12 个，与引擎 CLI flag 逐字对齐）",
          tuple(prm.CLI_KEYS) == ("route", "rounds", "channels", "parallel", "web",
                                  "thinking", "effort", "orientation", "landing",
                                  "decidability", "appendix", "keep"),
          f"CLI_KEYS={tuple(prm.CLI_KEYS)}")
    check("★R38 前端 ADV 表的键与后端 CLI_KEYS **同集合**（两条来源对账，防空表式假绿）",
          all(("'" + k + "'") in js for k in prm.CLI_KEYS),
          "前端缺=" + str([k for k in prm.CLI_KEYS if ("'" + k + "'") not in js]))
    try:
        prm.USER_CFG = _cf
        _c_res = prm.save_params({"cli.route": "1", "cli.rounds": "3",
                                  "api.default_model": "deepseek-reasoner"})
        _c_flat = prm._load_yaml_flat(_cf)
        _c_txt = _cf.read_text(encoding="utf-8") if _cf.exists() else ""
        _c_back = prm.load_cli_saved()
    finally:
        prm.USER_CFG = _real_user
    check("★R38 CLM 参数能保存进用户配置的 `cli:` 段",
          set(_c_res["saved"]) == {"cli.route", "cli.rounds", "api.default_model"}
          and not _c_res["missing"] and not _c_res["skipped"]
          and _c_flat.get("cli.route") == "1" and _c_flat.get("cli.rounds") == "3",
          f"saved={_c_res['saved']} missing={_c_res['missing']}")
    check("★R38 `cli:` 段在文件里**真是分段**（不是把 `cli.route` 写成扁平键名）",
          "\ncli:\n" in _c_txt and "cli.route" not in _c_txt,
          f"含 cli: 段={chr(10) + 'cli:' + chr(10) in _c_txt}")
    check("★R38 CLM 参数能**读回**（前端回显用户上次保存的值靠它）",
          _c_back == {"route": "1", "rounds": "3"},
          f"load_cli_saved()={_c_back}")
    check("★R38 CLM 参数保存**不影响**同一次提交里的普通 yaml 键（两条路互不干扰）",
          _c_res["saved"].count("api.default_model") == 1
          and _c_flat.get("api.default_model") == "deepseek-reasoner",
          f"model={_c_flat.get('api.default_model')!r}")
    check("★R38 出厂 dgtf_config.yaml 在 CLM 保存后仍**逐字节未动**",
          _real_cfg.read_bytes() == _cfg_bytes0, f"{len(_cfg_bytes0)} 字节")
    # 非法叶子键：`cli.` 前缀但叶子不在 12 个里 ⇒ missing（不是 saved）
    try:
        prm.USER_CFG = _cf
        _c_bad = prm.save_params({"cli.not_a_real_flag": "x"})
    finally:
        prm.USER_CFG = _real_user
    check("★R38 `cli.<不在 12 个里>` 被判 missing（不能靠前缀蒙混写进去）",
          _c_bad["missing"] == ["cli.not_a_real_flag"] and not _c_bad["saved"],
          f"missing={_c_bad['missing']} saved={_c_bad['saved']}")
    # 每任务跑完清零：只清 cli 段，其余用户键一字不动
    try:
        prm.USER_CFG = _cf
        _c_clr = prm.clear_cli_saved()
        _c_flat2 = prm._load_yaml_flat(_cf)
        _c_back2 = prm.load_cli_saved()
    finally:
        prm.USER_CFG = _real_user
    check("★R38 `clear_cli_saved()` 清掉 cli 段（CLM 参数「每执行一次任务清零」）",
          _c_clr["ok"] and _c_clr["removed"] == 2 and _c_back2 == {},
          f"removed={_c_clr['removed']} 剩余={_c_back2}")
    check("★R38 清零**只动 cli 段**，同文件里用户保存的普通键一字不动",
          _c_flat2.get("api.default_model") == "deepseek-reasoner"
          and "cli.route" not in _c_flat2 and "cli.rounds" not in _c_flat2,
          f"model={_c_flat2.get('api.default_model')!r} "
          f"cli残留={[k for k in _c_flat2 if k.startswith('cli.')]}")
    # 幂等：已无 cli 段时再清一次 ⇒ ok 且 removed=0（不重写文件、不报错）
    _c_mtime = _cf.stat().st_mtime_ns if _cf.exists() else 0
    try:
        prm.USER_CFG = _cf
        _c_clr2 = prm.clear_cli_saved()
    finally:
        prm.USER_CFG = _real_user
    check("★R38 清零**幂等**（已无 cli 段 ⇒ ok / removed=0 / 文件不重写）",
          _c_clr2["ok"] and _c_clr2["removed"] == 0 and not _c_clr2["error"]
          and (_cf.stat().st_mtime_ns if _cf.exists() else 0) == _c_mtime,
          str(_c_clr2))
    check("★R38 清零后出厂 yaml 仍**逐字节未动**",
          _real_cfg.read_bytes() == _cfg_bytes0, f"{len(_cfg_bytes0)} 字节")
    # 只读渲染：`cli` 键**不在** groups 里（它们不是 yaml 配置），但 `/api/params` 要下发
    check("★R38 `/api/params` 下发 `cli` 字段（前端 buildAdv 回显用），且不在 groups 里",
          isinstance(params_data.get("cli"), dict)
          and not any(it.get("key", "").startswith("cli.")
                      for g in (params_data.get("groups") or [])
                      for it in (g.get("items") or [])),
          f"cli={params_data.get('cli')}")
    # ★★ 构造性：判据要**先造出 CLI 键**再看 `/api/params` —— 变异体 M20 实测漏检，
    #    根因是 `params_data` 是**测前快照**（那时用户配置里没有 CLI 键，
    #    排不排除都一样 ⇒ 判据恒真）。必须自己把 CLI 键写进去，再取一次接口。
    #    ★ 且必须**走 HTTP**：`prm.USER_CFG` 是**测试进程**里的模块变量，改它影响不到
    #    服务进程（服务读的是真的 `dgtf_config.user.yaml`）—— 这是 R38 新踩的坑。
    #    ★ 保护真用户配置：先备份字节，测完原样还原。
    _uc = prm.PROJECT_ROOT / "dgtf_config.user.yaml" if hasattr(prm, "PROJECT_ROOT") \
        else prm.USER_CFG
    _uc_bak = _uc.read_bytes() if _uc.exists() else None
    _pd_cli = None
    try:
        _post(base, "/api/params", {"overrides": {"cli.route": "7"}})
        _, _pd_cli = _get(base, "/api/params")
    finally:
        if _uc_bak is None:
            if _uc.exists():
                _uc.unlink()
        else:
            _uc.write_bytes(_uc_bak)
        # 服务写盘时留的 `.bak` 也要清（否则下一轮自检/变异体的基线多一份脏数据）
        _ucb = Path(str(_uc) + ".bak")
        if _ucb.exists() and _uc_bak is None:
            _ucb.unlink()
    check("★R38 反向对账：走 HTTP 存 `cli.route=7` 后，`/api/params` 的 `cli` 真有它（不是空表）",
          isinstance(_pd_cli, dict) and (_pd_cli.get("cli") or {}) == {"route": "7"},
          f"cli={(_pd_cli or {}).get('cli')}")
    check("★R38 `cli` 键**不算**「用户改过的 yaml 键」（user_keys 里不能混进 CLI 键）",
          isinstance(_pd_cli, dict)
          and not any(str(k).startswith("cli.") or k in prm.CLI_KEYS
                      for k in (_pd_cli.get("user_keys") or [])),
          f"user_keys={(_pd_cli or {}).get('user_keys')}")
    # ★ 反向对账：先写一个**普通 yaml 键**进去，user_keys 必须**有它**；同时 CLM 键
    #   必须**没有**它 —— 两向都验，才不是「空表式的假绿」。
    try:
        _post(base, "/api/params", {"overrides": {"cli.route": "7",
                                                  "api.timeout": "321"}})
        _, _pd_both = _get(base, "/api/params")
    finally:
        if _uc_bak is None:
            if _uc.exists():
                _uc.unlink()
        else:
            _uc.write_bytes(_uc_bak)
        if _uc_bak is None and _ucb.exists():
            _ucb.unlink()
    check("★R38 两向对账：`user_keys` **有**普通键 `api.timeout`、**没有** CLM 键 `cli.route`",
          "api.timeout" in (_pd_both.get("user_keys") or [])
          and not any(str(k).startswith("cli.")
                      for k in (_pd_both.get("user_keys") or [])),
          f"user_keys={(_pd_both or {}).get('user_keys')}")
    if _cf.exists():
        _cf.unlink()

    # ★ R38（端到端补漏）：`_finalize` 收尾时**真调**清零 —— 此前该路径**没有源码级判据**，
    #   全套 selftest 全绿也照不出「清零没发生」（第一次端到端跑出来的真事）。
    _i_fz = runner_src.find("def _finalize(")
    _i_cc = runner_src.find("def _clear_cli_after_run(")
    _fz_body = runner_src[_i_fz:_i_cc] if 0 <= _i_fz < _i_cc else ""
    check("★R38 `_finalize()` 收尾时真调 `_clear_cli_after_run(task)`（跑完任务清零这条路）",
          "_clear_cli_after_run(task)" in _fz_body, f"函数体 {len(_fz_body)} 字符")
    check("★R38 清零失败**留痕不静默**：结果写进 task（cli_cleared / cli_clear_error）",
          'task["cli_cleared"] = bool(out.get("ok"))' in runner_src
          and 'task["cli_clear_error"] = str(out.get("error"))' in runner_src, "")

    # ── R36 ②：异常终止留痕的**行为级**验证（喂合成样本，不靠「源码里有这句话」）──
    #   ★ 隔离：把 `oi.OUTPUTS_DIR` 指到临时目录 —— 绝不能在真 outputs/ 里造垃圾。
    _orph = _save_dir / "_selftest_orphans"
    if _orph.exists():
        shutil.rmtree(_orph, ignore_errors=True)
    _orph.mkdir(parents=True, exist_ok=True)
    _real_out = oi.OUTPUTS_DIR
    _t0 = 1700000000.0
    # ① 活痕迹（服务崩了留下）：live=True + status=running ⇒ 应被回填成 interrupted
    (_orph / "20261012_010101_aaaaaa.run.json").write_text(json.dumps({
        "id": "20261012_010101_aaaaaa", "question": "崩溃前正在跑的题",
        "status": "running", "live": True, "mock": False,
        "created_at": _t0, "started_at": _t0 + 3, "ended_at": None,
        "error": "", "output_name": None, "cmd": ["python", "x.py"],
    }, ensure_ascii=False), encoding="utf-8")
    # ② 正常归档（live=False）：**不许**被动到（对照臂 —— 证明判据有区分力）
    (_orph / "20261012_020202_bbbbbb.run.json").write_text(json.dumps({
        "id": "20261012_020202_bbbbbb", "question": "正常跑完的题",
        "status": "done", "live": False, "mock": False,
        "created_at": _t0, "started_at": _t0, "ended_at": _t0 + 60,
        "error": "", "output_name": "20261012_020202_正常跑完的题.md",
    }, ensure_ascii=False), encoding="utf-8")
    # ③ 已被回填过的（idempotent 对照）：不许再改、也不许报第二次
    (_orph / "20261012_030303_cccccc.run.json").write_text(json.dumps({
        "id": "20261012_030303_cccccc", "question": "早就中断过的",
        "status": "interrupted", "live": False, "mock": False,
        "created_at": _t0, "started_at": _t0, "ended_at": _t0 + 10,
        "error": "服务中断（进程异常退出 / 重启），本任务未正常收尾",
    }, ensure_ascii=False), encoding="utf-8")
    # ④ ★ 让 `live` 这道闸**单独可判**的对照样本：`status=running` 但 `live=False`。
    #   —— 它不是「活痕迹」（活痕迹必须 live=True），只是一份**历史遗留**的 running 记录，
    #      按语义**不该**被本次回填碰。为什么非要有它：上面 ② 那份（done）在「去掉了
    #      live 闸」之后**依然不动**（被 status 闸拦住），所以单靠 ② 证明不了 live 闸起作用；
    #      只有这个样本能证明「live 闸确实在拦人」（去掉它 ⇒ 这条会被误改 ⇒ 判据翻红）。
    (_orph / "20261012_040404_dddddd.run.json").write_text(json.dumps({
        "id": "20261012_040404_dddddd", "question": "历史遗留的 running（非活痕迹）",
        "status": "running", "live": False, "mock": False,
        "created_at": _t0, "started_at": _t0, "ended_at": None,
        "error": "", "output_name": None,
    }, ensure_ascii=False), encoding="utf-8")
    try:
        oi.OUTPUTS_DIR = _orph
        _rec = runner.recover_orphans()
        _after = {p.name: json.loads(p.read_text(encoding="utf-8"))
                  for p in _orph.glob("*.run.json")}
    finally:
        oi.OUTPUTS_DIR = _real_out
        shutil.rmtree(_orph, ignore_errors=True)
    _m1 = _after["20261012_010101_aaaaaa.run.json"]
    _m2 = _after["20261012_020202_bbbbbb.run.json"]
    _m3 = _after["20261012_030303_cccccc.run.json"]
    _m4 = _after["20261012_040404_dddddd.run.json"]
    check("★ 孤儿任务被回填成 `interrupted` 并**写明原因**（崩溃的任务不再凭空消失）",
          len(_rec) == 1 and _rec[0]["id"] == "20261012_010101_aaaaaa"
          and _m1["status"] == "interrupted" and _m1["live"] is False
          and "服务中断" in _m1["error"]
          and _m1["ended_at"] and _m1["duration_sec"] is not None,
          f"回填 {len(_rec)} 条 → {_m1['status']}")
    check("★ 回填**只认活痕迹**：正常归档（done）一条不动（对照臂）",
          _m2["status"] == "done" and _m2["live"] is False
          and _m2["output_name"] == "20261012_020202_正常跑完的题.md",
          _m2["status"])
    # ★ 关键对照臂：live 闸**单独可判** —— 这份 status=running 但 live=False，
    #   去掉 live 闸就会被误改成 interrupted（② 那份 done 拦不住这个变异）。
    check("★ `live` 闸单独可判：status=running 但 live=False 的**历史遗留**不许被回填",
          _m4["status"] == "running" and _m4["live"] is False
          and not _m4.get("error"),
          _m4["status"])
    check("★ 回填**幂等**：已 interrupted 的不会二次改写",
          _m3["status"] == "interrupted"
          and "服务中断" in _m3["error"],
          _m3["status"])
    # 留痕落盘的**文件名口径**：无产物时 stamp 取任务 id（与活痕迹同名 ⇒ 就地覆盖、
    # 不会多出一份永远 running 的孤儿）
    check("★ 无产物时归档 stamp = 任务 id（就地覆盖活痕迹，不留 running 孤儿）",
          'stamp = name[:-3] if name.endswith(".md") else (name or str(task["id"]))'
          in runner_src
          and "def live_stamp" in runner_src,
          "")
    check("★ 收尾清活痕迹时**不会误删刚归档的那份**（同名即留，防自噬）",
          'Path(task["archive_json"]).name == jp.name' in runner_src
          and "归档就地覆盖了活痕迹，别删" in runner_src,
          "")
    check("★ dashboard 的「历史对话」带出 `error`（中断/失败能显示原因）",
          '"error": str(meta.get("error") or "")' in dash_src
          and '"error": str(t.get("error") or "")' in dash_src,
          "")
    # ★★ 产物库要能**收录孤儿痕迹并显示原因**（用户要求：中断任务在「产物库」也看得到）。
    #   喂一份合成 `<tid>.run.json`（非 mock）到隔离目录，验证 `_parse_one` 真读得到
    #   自身那份的 status/error/question —— 而不是只显示一个光秃秃的戳。
    #   （踩过的坑：`path.with_suffix(".run.json")` 对已是 .run.json 的路径会算成
    #     `X.run.run.json` ⇒ 自身元信息永远读不到。）
    _orph2 = _save_dir / "_selftest_orphan_trace"
    if _orph2.exists():
        shutil.rmtree(_orph2, ignore_errors=True)
    _orph2.mkdir(parents=True, exist_ok=True)
    (_orph2 / "20261012_050505_eeff00.run.json").write_text(json.dumps({
        "id": "20261012_050505_eeff00", "question": "产物库中断痕迹样本",
        "status": "interrupted", "live": False, "mock": False,
        "created_at": _t0, "started_at": _t0, "ended_at": _t0 + 42,
        "duration_sec": 42.0, "output_name": None,
        "error": "服务中断（进程异常退出 / 重启），本任务未正常收尾",
    }, ensure_ascii=False), encoding="utf-8")
    _real_out2 = oi.OUTPUTS_DIR
    try:
        oi.OUTPUTS_DIR = _orph2
        _one = oi._parse_one(_orph2 / "20261012_050505_eeff00.run.json")
    finally:
        oi.OUTPUTS_DIR = _real_out2
        shutil.rmtree(_orph2, ignore_errors=True)
    check("★ 孤儿痕迹被产物库收录时**带出原因与题目**（不是光秃秃一个戳）",
          _one.get("status") == "interrupted"
          and "服务中断" in (_one.get("error") or "")
          and _one.get("run_question") == "产物库中断痕迹样本"
          and _one.get("question") == "产物库中断痕迹样本",
          f"status={_one.get('status')} q={_one.get('question')!r}")

    s, lo = _get(base, "/api/library/local")
    check("本地资料库接口可用（导入列表 + 锚点候选）",
          s == 200 and isinstance(lo.get("items"), list)
          and isinstance(lo.get("candidates"), list),
          f"导入 {len(lo.get('items') or [])} / 候选 {len(lo.get('candidates') or [])}")
    s, wb = _get(base, "/api/library/web")
    check("联网检索库接口可用（历史命中汇总）",
          s == 200 and isinstance(wb.get("items"), list),
          f"{len(wb.get('items') or [])} 份产物")
    if wb.get("items"):
        # ★ [判据数据自洽化] 原来只看 `items[0]`：最新一份若是**没开 --web** 的跑次
        #   （detail 写的是「本次未接入联网检索」），这条判据**必然红** ——
        #   那是数据依赖的**假回归**，不是解析坏了。
        #   正解：在**全部** items 里找联网跑次；找不到就改成验证「未接入」这条
        #   兜底文案被正确解析（两种情况都证明「detail 解析出了内容」）。
        _linked = [it for it in wb["items"] if "收" in (it.get("detail") or "")]
        _unlinked = [it for it in wb["items"]
                     if "未接入联网" in (it.get("detail") or "")]
        check("联网读数解析出了条数/环节（全量样本里找联网跑次）",
              bool(_linked) or bool(_unlinked),
              ("样本 %d 份；联网跑次 %d 份%s"
               % (len(wb["items"]), len(_linked),
                  ("，例：" + (_linked[0].get("detail") or "")[:40]) if _linked
                  else "（当前样本没有 --web 跑次 ⇒ 以「未接入」兜底文案验证解析）")))
    _hits = wb.get("hits") or []
    if _hits:
        check("联网命中条目带内容与链接",
              bool(_hits[0].get("claim")) and bool(_hits[0].get("url")),
              f"{len(_hits)} 条 · {str(_hits[0].get('url'))[:36]}")
    _grp = wb.get("groups") or []
    if _grp:
        _g0 = _grp[0]
        check("联网命中按问题聚合（结果库接口）",
              bool(_g0.get("query")) and _g0.get("uniq", 0) >= 1
              and _g0.get("uniq", 0) <= _g0.get("total", 0),
              f"{len(_grp)} 组 · 首组 {_g0.get('uniq')}/{_g0.get('total')} 条")

    # 聚合去重的**判据自带样本**（不依赖真实 jsonl 里是否真有重复）：
    #   Q1 有 3 条、其中 2 条同 url → 去重后 2；同一条 url 落在 Q2 里，
    #   不能被 Q1「跨组吃掉」（否则就是全局去重，不是按问题聚合）。
    _demo = library.group_hits([
        {"ts": 1, "query": "Q1", "url": "u1", "claim": "a"},
        {"ts": 2, "query": "Q1", "url": "u1", "claim": "a"},
        {"ts": 3, "query": "Q1", "url": "u2", "claim": "b"},
        {"ts": 4, "query": "Q2", "url": "u2", "claim": "c"},
    ])
    _m = {g["query"]: g for g in _demo}
    check("聚合去重判据（合成样本：同问题同链接只留一条、跨组不吃）",
          len(_demo) == 2 and _m["Q1"]["uniq"] == 2 and _m["Q1"]["total"] == 3
          and _m["Q2"]["uniq"] == 1 and _m["Q2"]["total"] == 1,
          "/".join(f"{g['query']}:{g['uniq']}of{g['total']}" for g in _demo))
    # 同一份样本去掉重复那条 → 去重数必须变，否则说明「去重」是假的（变异对照）
    _demo2 = library.group_hits([
        {"ts": 1, "query": "Q1", "url": "u1", "claim": "a"},
        {"ts": 2, "query": "Q1", "url": "u1x", "claim": "a"},
        {"ts": 3, "query": "Q1", "url": "u2", "claim": "b"},
    ])
    check("聚合去重有判别力（换掉 url 后去重数必须变）",
          _demo2[0]["uniq"] == 3 and _demo2[0]["total"] == 3,
          f"{_demo2[0]['uniq']}of{_demo2[0]['total']}")

    # 本地资料库：导入 → 出现在列表 → 删除（用后即清，不留痕迹）
    _s, _imp = _post(base, "/api/library/import",
                     {"files": [{"name": "_selftest_anchor.md",
                                 "content": "自检用锚点内容"}]})
    check("本地资料库可导入文件",
          _s == 200 and _imp.get("saved") == ["_selftest_anchor.md"],
          str(_imp.get("saved")))
    _s, _lo2 = _get(base, "/api/library/local")
    check("导入后进了列表、锚点快照跟着重建",
          any(i["name"] == "_selftest_anchor.md" for i in (_lo2.get("items") or []))
          and _lo2.get("anchor_items", 0) >= 1,
          f"锚点 {_lo2.get('anchor_items')} 条")
    _s, _dl = _post(base, "/api/library/delete", {"name": "_selftest_anchor.md"})
    check("本地资料库可删除导入", _s == 200 and bool(_dl.get("ok")), str(_dl))

    s, t = _post(base, "/api/tasks", {"question": "应用端到端自检 mock", "opts": {"mock": True}})
    check("创建任务返回 id", s == 201 and bool(t.get("id")), str(t.get("id")))
    tid = t["id"]

    off, text, st, folded = 0, "", None, 0
    deadline = time.time() + 60
    while time.time() < deadline:
        _, st = _get(base, f"/api/tasks/{tid}")
        running = st["status"] in ("running", "queued")
        mode = "raw" if running else "filtered"
        if not running and off != 0:        # 跑完 → 重拉整段折叠版
            off = 0
        _, lg = _get(base, f"/api/tasks/{tid}/log?offset={off}&mode={mode}")
        off = lg["offset"]
        if running:
            text += lg["text"]              # 运行中：原始（含留痕）
        else:
            text, folded = lg["text"], lg.get("hidden", 0)
            break
        time.sleep(0.4)

    check("任务跑完", bool(st) and st["status"] == "done",
          (st or {}).get("error") or str((st or {}).get("status")))
    check("实时日志有分层输出", "━━━ 修行" in text and "━━━ 元" in text, f"{len(text)} 字节")
    _, lyr = _get(base, f"/api/tasks/{tid}/layers")
    check("分层接口：四层齐、且各层只落自己那段",
          set(lyr["layers"].keys()) == {"修行", "研究", "对撞", "元"}
          and "━━━ 修行" in lyr["layers"]["修行"]
          and "━━━ 元" in lyr["layers"]["元"]
          and "━━━ 元" not in lyr["layers"]["修行"],
          "、".join(f"{k}:{len(v)}" for k, v in lyr["layers"].items()))
    _tok = lyr.get("tok") or {}
    check("分层接口带实时 token 读数",
          _tok.get("tokens", 0) > 0 and _tok.get("calls", 0) > 0,
          f"calls={_tok.get('calls')} tokens={_tok.get('tokens')}")
    check("[tok] 读数行不进卡片日志",
          "[tok]" not in "".join(lyr["layers"].values()))
    # ★R39 需求 2：日志**共有头**（`__head__`）必须随 /layers 到前端 ——
    #   用户报「日志头部不显示载入信息（调度配置等）」。★ 根因是**字段断链**：
    #   桶名是 `__head__`，而前端 `pollLanes()` 只读 `r.layers` ⇒ `lanes.head` 恒
    #   undefined ⇒ 开头块从来没渲染过（R37 的判据只查了 `"src.head" in js`，看不见「取不到值」）。
    _rlhead = lyr.get("head") or ""
    check("★R39 /layers 带**日志共有头**（载入调度配置 / 调度 / 并行模式 …）",
          "载入调度配置" in _rlhead and "调度：" in _rlhead,
          "%d 字符" % len(_rlhead))
    check("★R39 负对照：这几行**不在四层里任何一层**（所以前端只能靠 `head` 那一条路拿到）",
          all("载入调度配置" not in _v for _v in lyr["layers"].values()),
          "")
    _sx = (lyr.get("stats") or {}).get("修行") or {}
    check("每层带自己的起始时间与 token 消耗",
          _sx.get("since") is not None and _sx.get("tokens", 0) > 0,
          f"since={_sx.get('since')} tokens={_sx.get('tokens')}")
    _sum = sum(((lyr.get("stats") or {}).get(n) or {}).get("tokens", 0)
               for n in ("修行", "研究", "对撞", "元"))
    check("四层 token 之和 ≤ 全局读数",
          _sum <= (lyr.get("tok") or {}).get("tokens", 0) + 1,
          f"层和={_sum} 全局={(lyr.get('tok') or {}).get('tokens')}")
    check("跑完后日志已折叠留痕/全文框",
          folded > 0 and "留痕" not in text and "【ing 全文】" not in text
          and "【view 全文】" not in text and "不应出现在后台" not in text,
          f"折叠 {folded} 行")
    _, lgr = _get(base, f"/api/tasks/{tid}/log?offset=0&mode=raw")
    check("原始模式保留完整内容（运行中用它）",
          "全量留痕" in lgr["text"], f"{len(lgr['text'])} 字节")
    check("任务定位到产物", bool(st and st.get("output_name")), str((st or {}).get("output_name")))

    if st and st.get("output_name"):
        s, res = _get(base, "/api/tasks/" + tid + "/result")
        check("取回产物正文", s == 200 and len(res["body"]) > 0, f"{len(res['body'])} 字节")
        check("运行归档已生成（log + json）",
              bool(st.get("archive_log")) and bool(st.get("archive_json")),
              f"{st.get('archive_log')} / {st.get('archive_json')}")
        if st.get("archive_log"):
            s, a = _get(base, "/api/archive/" + urllib.parse.quote(st["archive_log"]))
            check("归档 log 可读且保留留痕原文",
                  s == 200 and "全量留痕" in a["body"], f"{len(a['body'])} 字节")
        s, d = _get(base, "/api/outputs/" + urllib.parse.quote(st["output_name"]))
        check("产物详情接口可用", s == 200 and d["name"] == st["output_name"])

        stamp = st["output_name"][:-3] if st["output_name"].endswith(".md") else st["output_name"]
        made = [n for n in ("修行", "研究", "对撞", "元")
                if (oi.OUTPUTS_DIR / f"{stamp}.{n}.md").exists()
                and (oi.OUTPUTS_DIR / f"{stamp}.{n}.json").exists()
                and (oi.OUTPUTS_DIR / f"{stamp}.{n}.run.log").exists()]
        check("每层产物已落盘（md / run.log / json）", len(made) == 4,
              "、".join(made) if made else "无")
        _lp = oi.OUTPUTS_DIR / f"{stamp}.修行.md"
        _tot = (oi.OUTPUTS_DIR / st["output_name"]).read_text(encoding="utf-8", errors="replace")
        _head = _tot[: _tot.find("### 修行层")] if "### 修行层" in _tot else ""
        check("层 md 的共有头部与原总产物一致",
              bool(_head) and _lp.exists()
              and _lp.read_text(encoding="utf-8", errors="replace").startswith(_head),
              f"头部 {len(_head)} 字符")
        # ★ [第六期 · 防漂移] mock 的量化格式必须与**真引擎**对齐（两向对账）。
        #   背景：`mock_engine.py` 的注释承诺「格式**照抄真引擎**」，但真引擎
        #   新增【各环节量化】段时 mock 没跟 ⇒ 承诺失效。本条把「承诺」变成
        #   **可执行判据**：任一方新增读数而另一方没跟 ⇒ 立刻判红。
        #   为什么值得单独一条：mock 是**应用链路的验收集**，它跟丢格式 =
        #   新增渲染路径在验收台里**永远覆盖不到**（假绿）。
        try:
            _eng = runner.find_engine()
            _eng_src = _eng.read_text(encoding="utf-8", errors="replace")
        except Exception:
            _eng_src = ""
        _mock_src = (Path(__file__).resolve().parent / "mock_engine.py").read_text(
            encoding="utf-8", errors="replace")
        _both_seg = ("【各环节量化】" in _eng_src) and ("【各环节量化】" in _mock_src)
        _mock_keys = sorted(set(re.findall(r"（(\w+)）：", _mock_src)))
        _miss_keys = [k for k in _mock_keys if k and k not in _eng_src]
        _has_label_tbl = "_QUANT_LABELS" in _eng_src
        check("mock 的量化格式与真引擎对齐（两向对账 · 防漂移）",
              _both_seg and _has_label_tbl and not _miss_keys,
              "两边均有【各环节量化】段=%r；真引擎有 _QUANT_LABELS=%r；"
              "mock 用到的键在真引擎里找不到=%r（mock 键 %d 个）"
              % (_both_seg, _has_label_tbl, _miss_keys, len(_mock_keys)))
        _victims = [st["output_name"], st.get("archive_log"), st.get("archive_json")]
        for _n in ("修行", "研究", "对撞", "元"):
            _victims += [f"{stamp}.{_n}.md", f"{stamp}.{_n}.json", f"{stamp}.{_n}.run.log"]
        # ★ 清理必须「既删又移」：隔离环境里 unlink 会被重定向到 overlay ——
        #   脚本以为删了，真实盘上文件还在，于是**每跑一次自检，产物库就多一批垃圾**。
        #   删不掉就移出 outputs/（移到 _audit_tmp/_selftest_trash/，可逆）。
        _trash = oi.OUTPUTS_DIR.parent / "_audit_tmp" / "_selftest_trash"
        _left = 0
        for _n in _victims:
            if not _n:
                continue
            _p = oi.OUTPUTS_DIR / _n
            try:
                _p.unlink()
            except OSError:
                pass
            if _p.exists():                     # 还在 → 上一步被拦了，改走「移走」
                try:
                    _trash.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(_p), str(_trash / _n))
                except OSError:
                    _left += 1
        # 参数往返判据留下的临时 config 也一并清掉（同一条「删不掉就移走」的路子）
        try:
            _tmpy.unlink()
        except OSError:
            pass
        if _tmpy.exists():
            try:
                _trash.mkdir(parents=True, exist_ok=True)
                shutil.move(str(_tmpy), str(_trash / _tmpy.name))
            except OSError:
                pass
        print("  \u00b7 已清理自检产物与归档：" + st["output_name"]
              + (f"（{_left} 个未删净）" if _left else ""))

    # ★ T3 道生专属模式 + 三体动态最优（离线单测 + mock HTTP 端到端）
    try:
        check_t3_daosheng(base, srv_src, runner_src, js, html)
    except Exception as _t3_exc:  # noqa: BLE001  T3 段异常必须显式翻红
        check("★T3 自检段执行未抛异常", False,
              "%s: %s" % (type(_t3_exc).__name__, _t3_exc))

    # ★ 本地链路（8772 推理服务 + 8773 OpenAI 适配层）：动态读数 + 预设通道判据
    try:
        check_local_chain(base, srv_src, runner_src)
    except Exception as _lc_exc:  # noqa: BLE001  本段异常必须显式翻红
        check("★本地链路自检段执行未抛异常", False,
              "%s: %s" % (type(_lc_exc).__name__, _lc_exc))

    print(f"\n结果：PASS {len(PASS)} / FAIL {len(FAIL)}")
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
