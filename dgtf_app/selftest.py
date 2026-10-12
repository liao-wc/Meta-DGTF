# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 端到端自检（需先启动 server.py）。

用法：
    python dgtf_app/server.py            # 另开一个终端
    python dgtf_app/selftest.py [--base http://127.0.0.1:8765]

走完「提交 → 实时日志 → 完成 → 取产物 → 历史检索」全链路（mock，零花费），
并在结束时删掉它自己产生的 mock 产物 —— 自检无副作用。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard  # noqa: E402
import engine_runner as runner  # noqa: E402
import library  # noqa: E402
import outputs_index as oi  # noqa: E402
import params as prm  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  \u2713 " if cond else "  \u2717 ") + name + (("  \u2014 " + detail) if detail else ""))


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _post(base: str, path: str, obj: dict):
    req = urllib.request.Request(
        base + path, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _raw(base: str, path: str) -> str:
    with urllib.request.urlopen(base + path, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def _rule(css: str, sel: str) -> str:
    """取某条 CSS 规则的声明体（第一条匹配）。"""
    m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else ""


def _rules(css: str, sel: str) -> list[str]:
    """同名选择器的**全部**规则体（.tasks 在媒体查询里还有一份，别被它命中）。"""
    return [m.group(1) for m in re.finditer(re.escape(sel) + r"\s*\{([^}]*)\}", css)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    base = ap.parse_args().base

    try:
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            html = r.read().decode("utf-8")
        check("首页可访问且含标题", r.status == 200 and "元DGTF" in html)
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
    check("极简首屏：面板收进左侧抽屉（默认移出屏外，.open 才拉进来）",
          "translateX(-102%)" in _rule(css, ".drawer")
          and ".drawer.open{transform:none}" in css
          and 'id="drawer-btn"' in html,
          _rule(css, ".drawer").strip()[:56])
    check("极简首屏：空态居中、运行态日志占主位（body 上的 stage-* 切换）",
          "body.stage-empty main.stage{justify-content:center" in css
          and "body.stage-run .runlog{flex:1 1 auto" in css
          and 'class="stage-empty"' in html,
          "")
    check("输入框为对话式（功能胶囊 + 圆形发送键；旧的 composer-actions 已移除）",
          'id="pill-thinking"' in html and 'id="pill-web"' in html
          and 'id="run-btn"' in html and "composer-actions" not in html)
    check("首屏三个入口都在（抽屉 / 搜索对话产物 / 开启新对话），描述走**悬停气泡**",
          all(k in html for k in ('id="drawer-btn"', 'id="search-btn"', 'id="newchat-btn"'))
          and 'data-tip=' in html and 'class="btn-desc"' not in html,
          "data-tip=" + str(html.count('data-tip=')))
    check("搜索浮层 + 文件导入入口都在（浮层默认隐藏）",
          'id="search-overlay" class="search-overlay hidden"' in html
          and 'id="search-input"' in html and 'id="attach-btn"' in html,
          "")
    check("抽屉里是**七个**按钮（含历史对话）、各自指向一个面板",
          html.count('class="nav-btn"') == 7
          and 'data-sheet="adv-panel"' in html and 'data-sheet="view-lib"' in html,
          f"nav-btn={html.count('nav-btn')}")
    # ★ 参数页出口：R36 起口径是「出厂 `dgtf_config.yaml` **只读**，用户改动写
    #   **用户配置** `dgtf_config.user.yaml`；『恢复出厂设置』删用户配置 ⇒ 回落出厂」。
    #   ★ R37：用户要求**只保留两个**出口（保存 + 恢复出厂设置），「仅本次任务生效」
    #   已从界面移除（它那条路 `saveAdvForRun` 保留在代码里，供程序化调用）。
    check("⑦ 参数页只剩**两个**出口：保存 + 恢复出厂设置（`adv-once` 已从界面删掉）",
          'id="adv-save"' in html and 'id="adv-reset"' in html
          and 'id="adv-once"' not in html
          and ".sheet-actions{" in css
          and "justify-content:center" in _rule(css, ".sheet-actions")
          and 'class="sa-spacer"' in html,
          "adv-once=" + str('id="adv-once"' in html))
    check("⑦ 「恢复出厂设置」文案到位（不再是「恢复默认配置」）",
          "恢复出厂设置" in html and "恢复默认配置" not in html,
          "")
    check("⑦ 保存按钮**居中**：左有 `.sa-spacer` 隐形占位（与右侧两按钮等宽）",
          'class="sa-spacer"' in html
          and "visibility:hidden" in _rule(css, ".sa-spacer"),
          _rule(css, ".sa-spacer").strip()[:60])
    check("「保存」写**用户配置**（不是出厂 yaml、也不只写内存）",
          "saveAdvToFile" in js and "saveAdvForRun" in js
          and "await api('/api/params'" in js
          and "method: 'POST'" in js
          and "advSaved[k] = advOverrides[k]" in js
          and "dgtf_config.user.yaml" in js
          and "写回 dgtf_config.yaml" not in js,
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
          and "background:rgba(30,122,52,.14)" in _rule(css, ".rl-files a")
          and "color:#1E7A34" in _rule(css, ".rl-files a"),
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
          and "text-align:center" in _rule(css, ".env")
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
    check("输入框：内容与占位**居中**，发送时问题先在框内散成星光再飞走（三段动画）",
          "textarea#question{text-align:center}" in css.replace(" ", "")
          and "--mx" in css and "var(--mx)" in css
          and "34%" in css and "'--mx'" in js,
          "")
    check("内嵌图形（品牌/欢迎语方块标）**放大加粗**；文件链接**默认绿、悬停蓝**且贴右",
          "width:18px;height:18px" in _rule(css, ".glyph")
          and "width:32px;height:32px" in _rule(css, ".glyph.big")
          and "background:rgba(30,122,52,.14)" in _rule(css, ".rl-files a"),
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
          and "function paintWhisper" in js and "元DGTF 引擎已启动" in js,
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
    check("参数标签统一成「键（中文说明）」（和 CLI 参数同格式）",
          "KEY_CN" in params_src and "def label_for" in params_src
          and all(("（" in (it.get("label") or "")) for g in (params_data.get("groups") or [])
                  for it in g.get("items", [])),
          "参数项 " + str(sum(len(g.get("items", [])) for g in (params_data.get("groups") or [])))
          + " 项，全带中文说明")
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
    check("演练模式已挪到输入框那一排（胶囊，与深度思考/智能搜索同排）",
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
          and html.count('class="sd" data-for=') == 6
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
          and "border:1px solid rgba(30,122,52,.38)" in _rule(css, ".rl-files a")
          and _rule(css, ".rl-files a").strip().count('rgba(30,122,52') >= 2,
          "")
    check("**运行中也能看见这三个按钮**（待生成态 .pend：降透明度、不可点）",
          ".rl-filesa.pend{opacity:.55" in css.replace(" ", "")
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
    check("抽屉打开时首屏让位：主区**纯 translate 平移**（width 恒 100%，不再改宽度）",
          "transform:translateX(var(--shift-w))" in _rule(css, "body.drawer-open main.stage")
          and "width:" not in _rule(css, "body.drawer-open main.stage")
          and "margin-left:" not in _rule(css, "body.drawer-open main.stage")
          and "--shift-w:" in css,
          _rule(css, "body.drawer-open main.stage").strip()[:56])
    check("④ 让位量**封顶为视口一半**（窄视口下右侧恒留一半可见 ⇒「展开右边看不见」修掉）",
          "--shift-w:min(var(--drawer-w),50vw)" in css.replace(" ", ""),
          "")
    check("④ 让位时给主区右缘**补偿内边距**（自适应边距，内容不贴边）",
          "padding-right:calc(18px+min(var(--shift-w),6vw))"
          in css.replace(" ", "").replace("\n", ""),
          "")
    check("④ 运行态内容宽度在让位时**同步收窄**（否则右缘仍被顶出视口）",
          "body.drawer-open.stage-run .runlog" in css
          and "max-width:min(1080px,calc(100vw-var(--shift-w)-48px))"
          in css.replace(" ", "").replace("\n", ""),
          "")
    check("④ 平移**放慢**（主区 + 抽屉都 .42s，用户要求「慢一点」）",
          "transition:transform .42s var(--ease)" in _rule(css, "main.stage")
          and "transition:transform .42s var(--ease)" in _rule(css, ".drawer")
          and "margin-left" not in _rule(css, "main.stage"),
          _rule(css, "main.stage").strip()[:64])
    # ══ ★ R37 一揽子（用户 10 图 / 7 条）══════════════════════════════════════
    # ① 后端把日志共有头（`__head__`）随 /layers 一起下发 -------------------------
    #   引擎（`元DGTF-V1.23.22.py`）本来就在进层循环前打这一段（`调度：` / `螺旋上限`
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
    _s0 = dashboard.parse_stop("# 元DGTF · 没有停止那一行")
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
        _w = wb["items"][0]
        check("联网读数解析出了条数/环节",
              "收" in (_w.get("detail") or ""),
              (_w.get("detail") or "")[:46])
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

    print(f"\n结果：PASS {len(PASS)} / FAIL {len(FAIL)}")
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
