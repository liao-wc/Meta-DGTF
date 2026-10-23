# -*- coding: utf-8 -*-
"""v1.23.34 第三期：`view`（显形）输出结构 —— 加一行「本层速览」。

## 用户诉求
「优化 ing 和 view 的输出结构」「让人类看得懂」。

## 现状
`DGTF._render` 的正文已经是**结构化**的（【锚点】【候选】【ing 对撞】【& 印记】
【悬空线头】【探针回归】【尚未触及的方面】【各环节量化】【质量评价】【自省】…），
但**读者要读到最后才知道这层有多大** —— 缺一句"全局"。

## 改什么
在标题之后、`【锚点】` 之前插一行**本层速览**：

> **本层速览**：跑了 N 圈 · 候选 X · & Y · 线头 Z （· 悬置 W）

## 不改什么（为什么安全）
- **只增一行**，不删不改任何既有行 ⇒ 判据里「某段存在」的断言全部仍成立；
- **不改 `View.to_dict()` 出口**（速览是**渲染态**，不进 packed）；
- app 的「层 md 共有头部」判据查的是 `### 修行层` **之前**的头部 ⇒ 不受正文影响；
- 字段取不到时**降级为空串**，绝不让 `_render` 抛错（一抛错整层正文都没了）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A(3-1)：模块级渲染辅助函数（放在表达规范常量之后）──
ANCHOR_FN = '''_BOILERPLATE = ('''
NEW_FN = '''def _render_layer_glance(view) -> str:
    """本层速览：一行给出全局，让读者先抓住这层干了什么。

    ★ 为什么在正文最前面给这一行：`_render` 的正文是**结构化**的（十来个小段），
      但读者要读到最末才知道"这层到底有多大" —— 缺一句总览。
    ★ 为什么安全：**只增一行**，不删不改任何既有行 ⇒ 判据里「某段存在」的断言
      全部仍成立；也不进 `View.to_dict()`（速览是**渲染态**，不是产物字段）。
    ★ 字段缺失一律降级（取不到就当 0 / 省略）—— `_render` 一旦抛错，
      整层正文都没了，代价远大于少显示一个数。
    """
    try:
        _runs = int(getattr(view, "rounds_run", 0) or 0)
        _n_cand = len(getattr(view, "candidates", None) or [])
        _n_amp = len(getattr(view, "amps", None) or [])
        _n_thr = len(getattr(view, "threads", None) or [])
        _n_sus = len([s for s in (getattr(view, "suspensions", None) or [])
                      if isinstance(s, dict)
                      and s.get("status") in ("active", "stable")])
        _bits = ["跑了 %d 圈" % _runs, "候选 %d" % _n_cand,
                 "& %d" % _n_amp, "线头 %d" % _n_thr]
        if _n_sus:
            _bits.append("悬置 %d" % _n_sus)
        return "> **本层速览**：" + " · ".join(_bits) + "\\n"
    except Exception:
        return ""


_BOILERPLATE = ('''

# ── A(3-2)：接进 `_render` 的正文列表 ──
ANCHOR_RENDER = '''        lines = [
            f"━━━ {section_label} · entry={view.entry} ━━━",
            "",
            f"【锚点】{view.anchor}",'''
NEW_RENDER = '''        lines = [
            f"━━━ {section_label} · entry={view.entry} ━━━",
            "",
            # ★ 本层速览：先给全局，再给细节（只增一行，不动既有结构）。
            _render_layer_glance(view),
            f"【锚点】{view.anchor}",'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_FN, NEW_FN, "3-1"),
                          (ANCHOR_RENDER, NEW_RENDER, "3-2")):
        n = s.count(old)
        assert n == 1, "锚点 %s 命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert s.count("_render_layer_glance") == 2, \
        "应为 1 定义 + 1 调用，实得 %d" % s.count("_render_layer_glance")
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    assert out.count(b"\n") == out.count(b"\r\n")
    P.write_bytes(out)
    print("OK 第三期已应用；行数 %d" % out.count(b"\n"))


main()
