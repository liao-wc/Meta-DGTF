#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.22 -> v1.23.23：日志里「视图正文 / 候选 / 未判子问题」的回显不再按字符硬砍。

用户实测（应用工作台的日志窗口）：阴阳视角那一块最后一行被砍在半句上——
`- [concept] 纠缠熵面积律不能单`。查下来**不是前端裁的**，`.run.log` 里就是这行：
四处回显写死了字符上限，而模型返回的是**多行正文**：

  1. `_expand_view_once`        `raw[:200]`
  2. `_expand_pair_merged_once` `(raw or '')[:160]`
  3. `_judge_pair`              `c.desc[:50]`
  4. `_undecidable_sub_questions` `s['question'][:50]`

一类修复（不是四处补丁）：新增模块级纯函数 `_vp_preview(text, limit=4000)`，
**按整行截断**；真正截断时明说「另有 N 字未显示」，不静默丢内容。

铁律：主文件纯 CRLF。read_bytes -> 断言 -> 转 LF -> 逐块替换（每条断言命中 1 次）
-> 转回 CRLF -> write_bytes。脚本幂等：哨兵盯**旧块**（旧块在 = 还没打）。

    python _mk_v12323_echo.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.22.py"
DST = HERE / "元DGTF-V1.23.23.py"

HELPER_ANCHOR = "def _mode_timing_lines(mode: str, n_rounds: int = 3) -> List[str]:"

HELPER = r'''def _vp_preview(text, limit: int = 4000) -> str:
    """日志预览：**按整行截断**，不在行中间砍断。

    原来这几处回显写死 `raw[:200]` / `[:160]` / `[:50]`，而模型返回的是**多行正文**
    —— 字符数一到就停在某一行中间，读者看到的是半截话（实测
    `- [concept] 纠缠熵面积律不能单`），而完整正文又不在这一层的日志里
    （`view 全文` 折叠块只覆盖 view 条那一段），于是「内容没显示完全」。

    `limit` 默认 4000：对视图正文（4~8 行 / 200~600 字）等于不截断；真被截断时
    **明说**还剩多少字未显示 —— 不静默丢内容，与 `dump_round`「不挑字段、不截断」
    同一条纪律。
    """
    s = text if isinstance(text, str) else str(text or "")
    if len(s) <= limit:
        return s
    cut = s.rfind("\n", 0, limit + 1)
    if cut <= 0:
        cut = limit
    return s[:cut] + "\n   …（预览到此，另有 %d 字未显示）" % (len(s) - cut)


'''

# (说明, 旧块, 新块)
BLOCKS = [
    (
        "① 阴阳视角正文（单跑）",
        r'''            self.vp(f"\n💧 [{label}视角]")
            self.vp(f"   {raw[:200]}")''',
        r'''            self.vp(f"\n💧 [{label}视角]")
            self.vp(f"   {_vp_preview(raw)}")''',
    ),
    (
        "② 阴阳视角正文（合并）",
        r'''        self.vp(f"\n💧 [合并展开 {label0}+{label1}]")
        self.vp(f"   {(raw or '')[:160]}")''',
        r'''        self.vp(f"\n💧 [合并展开 {label0}+{label1}]")
        self.vp(f"   {_vp_preview(raw or '')}")''',
    ),
    (
        "③ 候选清单",
        r'''                self.vp(f"   [{i}] {c.desc[:50]}")''',
        r'''                self.vp(f"   [{i}] {_vp_preview(c.desc)}")''',
    ),
    (
        "④ 未判子问题清单",
        r'''            self.vp(f"      · [{s['decidability']}] {s['question'][:50]}"
                    f"  ← {s.get('source', '?')}")''',
        r'''            self.vp(f"      · [{s['decidability']}] {_vp_preview(s['question'])}"
                    f"  ← {s.get('source', '?')}")''',
    ),
    (
        "⑤ 回流硬执行拦下的重现候选",
        r'''                self.vp(f"   🗑 [回流硬执行] 拦下重现候选：{d[:40]}")''',
        r'''                self.vp(f"   🗑 [回流硬执行] 拦下重现候选：{_vp_preview(d)}")''',
    ),
    (
        "⑥ 子问题推进的目标",
        r'''            self.vp(f"   🤝 推进：子问题[{e['sub_id']}] {e['target'][:40]}（{e['how']}）")''',
        r'''            self.vp(f"   🤝 推进：子问题[{e['sub_id']}] {_vp_preview(e['target'])}（{e['how']}）")''',
    ),
]

N_HELPER_CALLS = 7          # 1 定义 + 6 处调用

VER_OLD_TITLE = "元 DGTF · v1.23.22"
VER_NEW_TITLE = "元 DGTF · v1.23.23"
VER_OLD_ATTR = '__version__ = "1.23.22"'
VER_NEW_ATTR = '__version__ = "1.23.23"'


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "%s 不是纯 CRLF" % p.name
    assert b.count(b"\r") == b.count(b"\r\n"), "%s 有游离 CR" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0, "写盘后出现 CRCRLF"
    assert b.count(b"\r\n") == b.count(b"\n"), "写盘后不是纯 CRLF"
    p.write_bytes(b)


def repl(s: str, old: str, new: str, what: str) -> str:
    n = s.count(old)
    if n == 0:
        assert s.count(new) >= 1, "%s：旧块没了、新块也没有（改到别处了？）" % what
        print("  · %s：已是新版，跳过" % what)
        return s
    assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
    print("  ✓ %s：替换 1 处" % what)
    return s.replace(old, new)


def main() -> int:
    src_text = read_crlf(SRC)
    print("源：%s（CRLF 校验通过）" % SRC.name)

    if DST.exists():
        cur = read_crlf(DST)
        print("目标已存在：%s（不覆盖源文件，就地打补丁）" % DST.name)
    else:
        cur = src_text
        print("目标不存在：从源复制")

    # ★ 所有替换都在 **LF** 上进行（块字面量用 \n 写的），最后 write_crlf 转回去。
    cur = cur.replace("\r\n", "\n")
    assert "\r" not in cur, "归一后仍有裸 CR"

    # ── 1) 插入模块级纯函数 ─────────────────────────────────────────────
    if "_vp_preview" in cur and "\ndef _vp_preview(" in cur:
        print("  · ① 纯函数 _vp_preview：已存在，跳过")
    else:
        assert cur.count(HELPER_ANCHOR) == 1, "插入锚点命中 %d 次" % cur.count(HELPER_ANCHOR)
        cur = cur.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR)
        print("  ✓ ① 纯函数 _vp_preview：插入 1 处")

    # ── 2) 四处回显统一走它 ─────────────────────────────────────────────
    for what, old, new in BLOCKS:
        cur = repl(cur, old, new, what)

    # ── 3) 版本号两处 ───────────────────────────────────────────────────
    assert cur.count(VER_OLD_TITLE) <= 1, "docstring 标题命中 %d 次" % cur.count(VER_OLD_TITLE)
    if VER_OLD_TITLE in cur:
        cur = cur.replace(VER_OLD_TITLE, VER_NEW_TITLE)
        print("  ✓ 版本号：docstring 标题 -> %s" % VER_NEW_TITLE)
    else:
        assert VER_NEW_TITLE in cur, "docstring 标题两个版本都没有"
        print("  · 版本号：docstring 标题已是 %s" % VER_NEW_TITLE)

    assert cur.count(VER_OLD_ATTR) <= 1
    if VER_OLD_ATTR in cur:
        cur = cur.replace(VER_OLD_ATTR, VER_NEW_ATTR)
        print("  ✓ 版本号：__version__ -> 1.23.23")
    else:
        assert VER_NEW_ATTR in cur, "__version__ 两个版本都没有"
        print("  · 版本号：__version__ 已是 1.23.23")

    write_crlf(DST, cur)

    # ── 4) 结构性自检（重新读盘，不信内存）────────────────────────────
    back = read_crlf(DST).replace("\r\n", "\n")
    # ★ 「旧上限」的检查要**剔掉刚插进去的 docstring** —— 它按纪律引述了旧写法，
    #   不剔掉就是恒红（判据自己的注释把自己判红）。
    body = back.replace(HELPER, "")
    assert body.count(HELPER) == 0 and "_vp_preview(text, limit" not in body
    bad = []
    if "def _vp_preview(" not in back:
        bad.append("_vp_preview 没落盘")
    for pat in ('self.vp(f"   {_vp_preview(raw)}")',
                'self.vp(f"   {_vp_preview(raw or \'\')}")',
                'self.vp(f"   [{i}] {_vp_preview(c.desc)}")'):
        if pat not in back:
            bad.append("回显点没接上：" + pat)
    if back.count("_vp_preview(") != N_HELPER_CALLS:
        bad.append("_vp_preview( 出现 %d 次（应为 1 定义 + %d 调用）"
                   % (back.count("_vp_preview("), N_HELPER_CALLS - 1))
    for dead in ("raw[:200]", "(raw or '')[:160]", "c.desc[:50]",
                 "s['question'][:50]", "d[:40]", "e['target'][:40]"):
        if dead in body:
            bad.append("旧上限还在：" + dead)
    if VER_NEW_TITLE not in back or VER_NEW_ATTR not in back:
        bad.append("版本号没升")
    import ast as _ast
    _ast.parse(back)
    print("  ✓ AST 解析通过")
    if bad:
        print("★ 结构性自检失败：")
        for x in bad:
            print("   - " + x)
        return 1

    print("结构性自检：全绿")
    print("落盘：%s（LF 行数 %d）" % (DST.name, back.count("\n")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
