#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 收尾：当日记忆 + MEMORY.md（形态/固定动作/新节/验收现状）+ SKILL.md。
三处都幂等、CRLF 往返。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAILY = HERE / ".workbuddy" / "memory" / "2026-10-09.md"
MEM = HERE / ".workbuddy" / "memory" / "MEMORY.md"
SK = Path(r"C:\Users\18432\.workbuddy\skills\dgtf-version-bump\SKILL.md")

DAILY_ADD = """
---

## v1.23.7：把 changelog 搬出代码，落到 `CHANGELOG.md`

### 结果
- 模块 docstring 里的版本段（**4954 行 / 188,747 字符 / 占原文件 22.7%**）原样搬进
  仓库根 `CHANGELOG.md`（5023 行 / 27 段）；代码里的 docstring 换成 **8 行**短版。
- `元DGTF-V1.23.7.py`：21841 → **16894 行**（-4947）。冒烟 **exit 0 / 0 ✗ / 202 ✓**；
  配置 `load_config` 差异 **0 项**；纯 CRLF。
- v1.23.6 及更早段落**原样搬迁、一字未改**（搬移只动位置）。

### 零行为变化的证明
模块 docstring **不参与执行**，且引擎**不读自己的 `__doc__`**（全文件仅 1 处，在注释里）。
硬断言：① 抠 docstring + 归一化 `__version__` 后**代码部分逐字相同**；
② 抠 docstring 后 **AST 严格等价**；③ 搬出段数 == 原段数（26 → 27，新增本版段）+ 段序递减。

### ★ 判据取源外移的三条教训
1. **先量「谁会断」，再动手**：侦察出 9 个「只活在 docstring 里」的判据片段，
   逐个看**取源变量**后只有 **2 个**真读 docstring/源码；其余 7 个读的是
   `getsource(方法)` / 产物文件 / 审计文档 —— **不逐个核就会去改一堆不必改的判据**。
2. **取源外移后，旧负对照手法会一起失效**：`check_v72_changelog_hygiene` 原来靠
   「把 SRC 指回 v1.21.71」制造坏样本；changelog 不在 SRC 里以后这招是空的 ⇒
   抽纯函数 `_changelog_lint(text)` + 喂**合成坏样本**（重复收束标题 + 段序 71→68→69）。
3. ★★ **判据正则别只认见得多的那种形态**：`check_v1237` 的段标题正则原写成
   `^v1\\.2\\d`，变异体 M1 注入 `v1.99.9 相对 v1.99.8` **竟没判红** ⇒ 改成
   `^v\\d+(?:\\.\\d+)+ 相对`。**变异体打在判据读的那个东西上，当场就抓出来了。**

### 外部隐含前提要显式断言
`_probe_v1232_audit.py` 的 C1「docstring 标题版本 == `__version__`」是按
**`txt[:4000]`** 取标题的 —— 所以短 docstring 必须把标题留在前 4000 字符内。
已在搬移脚本里显式 `assert`，否则下次有人把 docstring 写长，C1 会**静默失效**。

### 落点变了（重要）
「收束摘要」现在写在 **`CHANGELOG.md` 的对应版本段尾**，不再写进 docstring ——
代码里既然没有 changelog，自然也没有收束摘要。判据 `check_v1237_changelog_outside_code`
两向对账：代码里 0 处版本段 + `CHANGELOG.md` 段数 ≥ 10（防「搬出去」变「删掉」）。
"""

MEM_PAIRS = [
    ("- 单文件 `元DGTF-V1.2X.N.py`（v1.23.5 = 23237 行，**纯 CRLF**，无包 / 无测试框架）。",
     "- 单文件 `元DGTF-V1.2X.N.py`（v1.23.7 = 16894 行，**纯 CRLF**，无包 / 无测试框架）。\n"
     "- ★ **变更记录不在代码里** —— 在仓库根 `CHANGELOG.md`（v1.23.7 起）。"),
    ("2. changelog 在 docstring、最新在最前；**定稿时在该版段尾加 `★ vX.Y.Z 收束摘要`**\n"
     "   （`────` U+2500×60 包夹，宽度**从文件里量**）。只动 docstring → 硬断言\n"
     "   「抠 docstring 后逐字相同 + AST 等价」。",
     "2. changelog 在仓库根 **`CHANGELOG.md`**（v1.23.7 起；此前在 docstring），每版一段、\n"
     "   最新在最前；**定稿时在该版段尾加 `★ vX.Y.Z 收束摘要`**（落点也在 CHANGELOG.md）。\n"
     "   ★ 代码里的模块 docstring 只留 8 行（标题 + 一句话 + 指向），且**标题必须在前\n"
     "     4000 字符内** —— `_probe_v1232_audit.py` 的 C1 按 `txt[:4000]` 取标题。"),
    ("- 验收现状（v1.23.5）：冒烟 exit 0 / 0 ✗ / **200 ✓**",
     "- 验收现状（v1.23.7）：冒烟 exit 0 / 0 ✗ / **202 ✓**"),
]

MEM_NEW_SEC = """
## ★ v1.23.7：变更记录搬出代码
- 模块 docstring 的版本段 → 仓库根 `CHANGELOG.md`；代码 docstring 8 行。
  21841 → **16894 行**。引擎**不读自己的 `__doc__`** ⇒ 零功能改动，硬断言 =
  「抠 docstring 后代码逐字相同 + AST 等价」+「搬出段数 == 原段数」。
- ★ 判据**取源外移**时旧的「切换 SRC 指向」负对照会**一起失效** ⇒ 抽纯函数
  `_changelog_lint()` + 喂**合成坏样本**（判别力不再依赖被测文件的位置）。
- ★ 判据正则**别只认见得多的形态**：变异体注入 `v1.99.9 相对` 竟没判红 ⇒ 用
  `^v\\d+(?:\\.\\d+)+ 相对`。变异体的价值就在这。
- 前向守卫 `check_v1237_changelog_outside_code` 两向对账：代码里 0 处版本段 +
  `CHANGELOG.md` 段数 ≥ 10（防「搬出去」变「删掉」）。
"""

SK_ANC = ("且写盘后**换一条命令回读**（沙箱 overlay 会吞写入，本轮主文件头部被吞过一次）。")
SK_ADD = """

### v1.23.7 落地实测：把 changelog 搬出代码（判据取源外移怎么办）

**改了什么**：模块 docstring 里的版本段（4954 行 / 占原文件 22.7%）→ 仓库根
`CHANGELOG.md`；代码里的 docstring 只剩 8 行。21841 → **16894 行**。零功能改动 ——
**引擎不读自己的 `__doc__`**（全文件仅 1 处，且在注释里）。

**★★ 判据取源外移时，旧负对照会一起失效。**
`check_v72_changelog_hygiene` 原来的判别力来自「把 `SRC` 指回 v1.21.71」；
changelog 一旦不在 `SRC` 里，这招就是空的。正解：把检查抽成**纯函数**
（`_changelog_lint(text)`），负对照喂**合成坏样本**（重复收束标题 + 段序 71→68→69）。
**通则：负对照不要吊在被测文件的位置上。**

**★★ 先量「谁会因这次搬家而断」，再动手。** 侦察出 9 个「只活在 docstring 里」的
判据片段，逐个看**取源变量**后只有 **2 个**真读 docstring / 源码；其余 7 个读的是
`getsource(方法)`（查函数源码）、产物文件、审计文档 —— **不逐个核，就会去改一堆
不必改的判据**。

**★ 判据正则别只认「见得多的那种形态」。** 新判据 `check_v1237_changelog_outside_code`
的段标题正则原写成 `^v1\\.2\\d`，变异体注入 `v1.99.9 相对 v1.99.8` **竟没判红**
⇒ 改成 `^v\\d+(?:\\.\\d+)+ 相对`。**变异体必须打在判据读的那个东西上，当场就抓出来。**

**★ 外部隐含前提要写进断言。** `_probe_v1232_audit.py` 的 C1「docstring 标题版本 ==
`__version__`」是按 **`txt[:4000]`** 取标题的 ⇒ 短 docstring 必须把标题留在前 4000
字符内，搬移脚本里显式 `assert`。否则下次有人把 docstring 写长，C1 会**静默失效**。

**落点变了**：「收束摘要」写在 `CHANGELOG.md` 的对应版本段尾，**不再写进 docstring**。
判据两向对账：代码里 0 处版本段 + `CHANGELOG.md` 段数 ≥ 10。

**搬移类改动的最强证明**：抠掉被搬的东西后**剩下逐字相同** + AST 等价 +
「搬出段数 == 原段数」。比任何采样都硬。"""


def patch(path: Path, pairs, label: str):
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n") > 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in pairs:
        if new in t:
            print("  [skip] %s 已改" % label)
            continue
        n = t.count(old)
        assert n == 1, "%s 锚点命中 %d 次：%r" % (label, n, old[:56])
        t = t.replace(old, new, 1)
        print("  [ok] %s ← %r" % (label, old[:40]))
    out = t.replace("\n", "\r\n").encode("utf-8") if crlf else t.encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    path.write_bytes(out)


# ① 当日记忆
raw = DAILY.read_bytes()
t = raw.decode("utf-8").replace("\r\n", "\n")
if "v1.23.7：把 changelog 搬出代码" in t:
    print("[skip] 当日记忆")
else:
    DAILY.write_bytes((t.rstrip("\n") + "\n" + DAILY_ADD).encode("utf-8"))
    print("已追加当日记忆")

# ② MEMORY.md
patch(MEM, MEM_PAIRS, "MEMORY")
mem = MEM.read_bytes().decode("utf-8").replace("\r\n", "\n")
if "## ★ v1.23.7：变更记录搬出代码" not in mem:
    anchor = "\n## 写文件铁律（主文件纯 CRLF）"
    assert mem.count(anchor) == 1, "MEMORY 写文件铁律锚点 %d 次" % mem.count(anchor)
    mem = mem.replace(anchor, MEM_NEW_SEC + anchor, 1)
    MEM.write_bytes(mem.replace("\n", "\r\n").encode("utf-8"))
    print("已插入 MEMORY v1.23.7 节")
else:
    print("[skip] MEMORY v1.23.7 节")

# ③ SKILL.md
patch(SK, [(SK_ANC, SK_ANC + SK_ADD)], "SKILL v1.23.7")
patch(SK, [("- 惯例历史：v1.21.56~71 每版都带收束摘要，v1.22 / v1.23.0~4 断了，v1.23.5 恢复。",
            "- 惯例历史：v1.21.56~71 每版都带收束摘要，v1.22 / v1.23.0~4 断了，v1.23.5 恢复。\n"
            "- ★ **v1.23.7 起落点改了**：收束摘要写在**仓库根 `CHANGELOG.md`** 的对应版本\n"
            "  段尾，**不再写进 docstring**（代码里既然没有 changelog，自然也没有收束摘要）。")],
      "SKILL 收束落点")

for p in (DAILY, MEM, SK):
    b = p.read_bytes()
    print("%-14s %d 字节 字符=%d 行=%d CRLF=%d 裸LF=%d CRCRLF=%d"
          % (p.name, len(b), len(b.decode("utf-8")), b.count(b"\n"), b.count(b"\r\n"),
             b.count(b"\n") - b.count(b"\r\n"), b.count(b"\r\r\n")))
