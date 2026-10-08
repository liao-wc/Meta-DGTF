#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 第三档] 落工作记忆 + 长期记忆 + 技能（全部带幂等守卫）。"""
from __future__ import annotations

import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)


def append_crlf(path: str, text: str, key: str) -> None:
    p = Path(path)
    t = p.read_bytes().decode("utf-8").replace(CR + LF, LF).rstrip(NL)
    if key in t:
        print("  · 已含该段（跳过）：" + path)
        return
    p.write_bytes((t + NL + text).replace(NL, CR + LF).encode("utf-8"))
    c = p.read_bytes()
    print("  ✓ " + path.split("/")[-1]
          + "（crr " + str(c.count(bytes([13, 13, 10]))) + "）")


DAILY = NL.join([
 "",
 "## v1.22.1 第三档 P7 + 全局收尾 F.2/F.3/F.4 —— **通过**（2026-10-05 上午）",
 "",
 "文件链终点：rc3（P5+P6）→ **`元DGTF-V1.22.1.py`**（定稿 = rc3 + 标题 + `__version__`",
 "+ changelog）。★ 用 difflib 逐块核对：定稿相对 rc3 的差异**只有三处** ——",
 "docstring 标题行、`__version__` 行、新增的 v1.22.1 changelog 段（109 行）。",
 "**引擎代码一行未动**（P7 就是「只出说明、不动代码」）。",
 "",
 "### 验收（对定稿 `元DGTF-V1.22.1.py`）",
 "```",
 "p1 20/0  p2 15/2（P2a 单档历史，按设计保留）  p2b 25/0  p3 12/0",
 "p4 14/0  p5 14/0  p6 14/0  p7 11/0",
 "--phase all：PASS 160 / FAIL 2（两条红就是 P2a 的历史记录）",
 "冒烟：443 行 / 165 ✓ / 0 ✗ / EXIT=0（守卫 80 条）",
 "```",
 "F.4 交付物核对：33 项（任务书 23 + 本轮实增 10），除 F.1 的 bench 报告外全在。",
 "",
 "### ★ 本轮最值得记的一条：**判据的锚不能是移动靶**",
 "`--phase all` 里 v122 的 `phase5` **每次验收都重跑** `_audit_v122_dead_mechanisms.py`，",
 "覆盖 `audit_v122_dead_mechanisms.md`（且用固定 src）。而语料会长大：",
 "**P3 时点判「仅源码」5 条 → 09:42 重跑审计（368 日志 / 317 产物）→ 13 条全「可达」、",
 "「仅源码」0 条**（机制被真跑走到了，这是好事）。",
 "我的 P3.4「与审计报告两向对账」因此**因为数据变大而翻红** —— 与「本版有没有删机制」",
 "毫无关系。正解：把那个集合**冻结**成 `_negctl_v1221_p3_frozen.json`（带 frozen_at /",
 "note 说明它会随语料缩小），P3.4 对**冻结快照**两向对账；当前审计集合只 `print` 不判红。",
 "★ 一般化：**依赖「会随时间变化的外部产物」的判据，必须钉在时点快照上**，",
 "否则它会因为数据长大而自己变红。",
 "",
 "### 其余新增的坑",
 "1. ★ **抠函数体必须带开括号**：`_body(name)` 用 `find(\"def \" + name)` 时，",
 "   `_adjudicate_sub_tristate` 是 `_adjudicate_sub_tristate_multi` 的**前缀** →",
 "   两条都命中 multi，探针于是把结果读成「单票路径也写了 stability」。",
 "   正解：`find(\"def \" + name + \"(\")`。修好后得到**代码级铁证**：",
 "   `multi 路径: 1 / single 路径: 0`。",
 "2. ★ **属性不存在时不要用非空哨兵串**：`getattr(obj, key, \"<无属性>\")` 让",
 "   「没这个字段」被读成「有内容」→ before 侧两格**假真**。改回 `None`，",
 "   再加一条单独的「属性存在」判据，才能区分「没这个字段」与「字段在但是空」。",
 "3. ★ **本机沙箱的 shell `>` 重定向不可靠**：实测偶发**写空/写旧**（p3/p4 的 after",
 "   文件停在上一版，导致「对照」是假的）。对策：让脚本自己 `write_bytes`，",
 "   或用 Python 驱动跑子进程、解析 stdout 后再落盘（`_run_probes_p3456.py`）。",
 "   自检：写完 `json.loads` 一遍，能解析成非空 dict 才算数。",
 "4. ★ **F.1 的降档会削弱 P1 的效果**（实测）：economy + `0:2,1:2,both:2,all:3` 下，",
 "   部分题研究层**答出 0 条**（6 条子问题全 undecidable）→ schema 无 actions 可产",
 "   → rubric 0。★ 关键区分：这是**「没有可产的动作」**，引擎**如实留痕**",
 "   （`action_incomplete` + errors 文案「schema 产出 0 条（< 3）」），**不是抽取失败**。",
 "   另：第三项「不做什么」全 0（`_not_do` 空）→ rubric 上限只有 2/3。",
 "   → 写 `_diag_v1221_rubric.py` 把「0 分的成因」逐题分开（三种口径）。",
 "",
])

MEM = NL.join([
 "- ★ **判据的锚不能是移动靶**：凡是判据读「会随时间变化的外部产物」（审计报告、",
 "  语料统计），语料长大就会让它**因为数据变大而翻红**。实测：v122 的 `phase5`",
 "  每次验收重跑审计 → 「仅源码」集合从 P3 时点 5 条缩到 0 条 → P3.4 两向对账翻红。",
 "  正解：把该集合**冻结成时点快照文件**（带 frozen_at + 会缩小的说明），判据对快照；",
 "  当前集合只 `print` 不判红。",
 "- ★ **抠函数体必须带开括号**：`find(\"def \" + name)` 会被**前缀同名**函数截走",
 "  （`_adjudicate_sub_tristate` 是 `..._multi` 的前缀）→ 读到错的函数体还浑然不觉。",
 "  一律 `find(\"def \" + name + \"(\")`。",
 "- ★ **属性不存在时别用非空哨兵串**：`getattr(o, k, \"<无属性>\")` 会把「没这个字段」",
 "  读成「有内容」（before 侧假真）。用 `None` + 单独一条「属性存在」判据。",
 "- ★ **本机 sandbox 的 shell `>` 重定向不可靠**（偶发写空/写旧，让 before/after 对照",
 "  变成假的）。脚本自己 `write_bytes`；写完 `json.loads` 校验非空 dict 才算数。",
 "- ★ **「0 分」要分因**：F.1 里 rubric 0 有两类 ——「没有可产的动作」（研究层答出 0 条，",
 "  引擎如实留痕）与「模型没按 schema 产出」。不分开就会把「诚实留痕」误判成「功能坏了」。",
 ""])

SKILL = NL.join([
 "## v1.22.1 追加：第三档（P7 + 收尾）与三条判据纪律",
 "",
 "1. **判据的锚不能是移动靶**。`--phase all` 里的 v122 `phase5` 会**重跑**审计脚本、",
 "   覆盖 `audit_v122_dead_mechanisms.md`；语料长大 → 「仅源码」集合从 5 条缩到 0 条",
 "   → P3.4（与审计报告两向对账）**因为数据变大而翻红**，与「有没有删机制」无关。",
 "   正解：`_negctl_v1221_p3_frozen.json` 冻结时点快照（带 frozen_at + 会缩小的说明），",
 "   判据对快照；活集合只 `print` 不判红。**通则：依赖会变的外部产物 → 钉时点快照。**",
 "2. **抠函数体带开括号**：`find(\"def \" + name)` 会被前缀同名函数截走",
 "   （`_adjudicate_sub_tristate` 是 `..._multi` 的前缀）→ 静默读到错的函数体。",
 "   一律 `find(\"def \" + name + \"(\")`。",
 "3. **属性缺失别用非空哨兵**：`getattr(o, k, \"<无属性>\")` 会把「没这个字段」读成",
 "   「有内容」。用 `None` + 独立的「属性存在」判据。",
 "",
 "## v1.22.1 追加：F.1 降档跑的两个观察",
 "",
 "- **降档会削弱 P1 的效果**：economy + `0:2,1:2,both:2,all:3` 下，部分题研究层",
 "  **答出 0 条**（子问题全 undecidable）→ schema 无 actions 可产 → rubric 0。",
 "  这是「没有可产的动作」，引擎**如实留痕**（`action_incomplete` + errors 文案），",
 "  **不是抽取失败**。写 `_diag_v1221_rubric.py` 把 0 分的成因按三种口径分开：",
 "  answered==0 且全 undecidable / answered>0 但 actions==0 / actions>0 但 rubric 低。",
 "- **rubric 的第三项「不做什么」需要 schema 也加一段**：`_not_do` 一直为空 →",
 "  rubric 上限只有 2/3。要拿满必须让研究层直接产出「不做什么」清单。",
 "",
 "## v1.22.1 追加：本机 sandbox 的两条工程坑",
 "",
 "- **shell `>` 重定向不可靠**：偶发写空/写旧 → before/after 对照会变成假的。",
 "  脚本自己 `write_bytes`，或 Python 驱动跑子进程再落盘；写完 `json.loads` 校验。",
 "- **单段 heredoc 偶发重复执行**：第一次已写盘、第二次 `assert count == 1` 报 0",
 "  → 看起来「失败了但其实改对了」。一次性改写脚本也加幂等守卫（哨兵串）。",
 ""])


def main() -> int:
    append_crlf(".workbuddy/memory/2026-10-05.md", DAILY,
                "## v1.22.1 第三档 P7 + 全局收尾")
    append_crlf(".workbuddy/memory/MEMORY.md", MEM,
                "判据的锚不能是移动靶")
    append_crlf("C:/Users/18432/.workbuddy/skills/dgtf-version-bump/SKILL.md",
                SKILL, "## v1.22.1 追加：第三档（P7 + 收尾）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
