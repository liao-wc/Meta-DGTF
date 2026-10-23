#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7：把 changelog 从代码里搬出去，落到仓库根目录 `CHANGELOG.md`。

做法：
  1) 复制 v1.23.6 → v1.23.7；
  2) 把模块 docstring 里的**版本段**（`v1.23.6 相对 v1.23.5` 起，含各版收束摘要）
     原样搬进 `CHANGELOG.md`，并在文件头写清「这是什么 / 约定 / 判据」；
  3) 在 CHANGELOG.md 顶部插入本版段 `v1.23.7 相对 v1.23.6`；
  4) 代码里的模块 docstring 换成**短版**（标题 + 一句话 + 指向 CHANGELOG.md），
     标题与 `__version__` 升到 v1.23.7。

硬断言：
  ① 抠掉模块 docstring 后，代码部分逐字相同（只允许 `__version__` 那一处变）；
  ② 抠 docstring + 归一化 `__version__` 后 AST 严格等价；
  ③ 搬出来的版本段数 == 原 docstring 里的段数（不丢不重）。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S6 = HERE / "元DGTF-V1.23.6.py"
S7 = HERE / "元DGTF-V1.23.7.py"
CL = HERE / "CHANGELOG.md"

SHORT = '''
元 DGTF · v1.23.7

单文件多模并行推理引擎：四层 0/1/both/all × 螺旋跑圈，三通道 content/context/self。

★ 变更记录（各版 changelog 与收束摘要）**不在代码里** —— 见仓库根目录 `CHANGELOG.md`。
  代码正文只解释「这段**当前**为什么长这样」，不留版次批注。
'''

CL_HEAD = """# 元 DGTF · 变更记录（CHANGELOG）

> 本文件是单文件引擎 `元DGTF-V1.23.x.py` 的**变更记录**。
> 2026-10-09（v1.23.7）把它从模块 docstring 里搬出来 —— 代码文件从此只剩代码。
> **v1.23.6 及更早的段落是原样搬迁，一字未改**（搬移只动位置，不动内容）。
>
> **约定**：每版一段，**最新在最前**；每段 = 【主题】+ 改动说明 + （定稿时）
> `★ vX.Y.Z 收束摘要`（交付物 / 改了哪几处 / 验收数字 / 未做）。
> **判据**（`smoke_test.py`）：段序按版本号**严格递减**、收束摘要标题**不重复**
> （`check_v72_changelog_hygiene`）；代码文件里**不得**再出现版本段
> （`check_v1237_changelog_outside_code`）。

---

v1.23.7 相对 v1.23.6

【主题】把 changelog 从代码里搬出去 —— 代码文件只剩代码。

【为什么】v1.23.6 清掉了代码正文里的版次批注，但模块 docstring 里还留着 **4957 行 /
  22.7%** 的 changelog（含各版收束摘要）。它和代码混在一个文件里：读代码要滚过
  近 5000 行历史；而任何「在源码上数形态」的判据都必须先记得抠掉它。

【做什么】
  · 模块 docstring 里的版本段（`v1.23.6 相对 v1.23.5` 起）**原样**搬进仓库根目录
    `CHANGELOG.md`；本版段（本节）写在最前。
  · 代码里的模块 docstring 换成**短版**：标题 `元 DGTF · v1.23.7` + 一句话说明 +
    指向 `CHANGELOG.md`。★ 标题必须留在前 4000 字符内 ——
    `_probe_v1232_audit.py` 的 C1「docstring 标题版本 == __version__」按这个范围取。
  · 判据随实现更新 2 处（是**位置变了**，不是放宽）：
    `check_v72_changelog_hygiene` 与 `check_v76_changelog_wording` 原来读
    `SRC`/模块 docstring，现改读 `CHANGELOG.md`。

【零行为变化】模块 docstring **不参与执行**，且引擎自己**不读自己的 `__doc__`**
  （全文件仅 1 处 `__doc__`，且在注释里）。硬断言：抠掉 docstring 后代码部分逐字
  相同 + AST 严格等价。

【规模】21841 → **16885 行**（-4956 行）。

"""


def ex(t):
    i = t.index('"""'); j = t.index('"""', i + 3)
    return t[:i] + '"""X"""' + t[j + 3:]


def nv(t):
    o, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', t)
    assert n == 1
    return o


def main():
    raw6 = S6.read_bytes()
    assert raw6.count(b"\r\n") == raw6.count(b"\n") and raw6.count(b"\r\r\n") == 0
    t6 = raw6.decode("utf-8").replace("\r\n", "\n")
    i = t6.index('"""'); j = t6.index('"""', i + 3)
    doc = t6[i + 3:j]

    # 找「版本段」的起点：CHANGELOG 说明行之后
    m = re.search(r"^CHANGELOG（按版本分段[^\n]*\n", doc, re.M)
    assert m, "找不到 docstring 里的 CHANGELOG 说明行"
    secs = doc[m.end():].lstrip("\n")
    n_before = len(re.findall(r"^v1\.2\d(?:\.\d+)? 相对", secs, re.M))
    print("原 docstring 里的版本段 = %d" % n_before)
    assert n_before >= 25, "版本段数异常：%d" % n_before

    # 写 CHANGELOG.md（本版段在最前）
    md = CL_HEAD + "---\n\n" + secs.rstrip("\n") + "\n"
    n_after = len(re.findall(r"^v1\.2\d(?:\.\d+)? 相对", md, re.M))
    assert n_after == n_before + 1, "搬移后段数 %d != %d+1" % (n_after, n_before)
    vlist = [tuple(int(x) for x in v.split("."))
             for v in re.findall(r"^v(1\.2\d(?:\.\d+)?) 相对", md, re.M)]
    assert all(vlist[k] > vlist[k + 1] for k in range(len(vlist) - 1)), "段序没保持递减"
    print("CHANGELOG.md 版本段 = %d，段序严格递减 ✓" % n_after)
    CL.write_bytes(md.replace("\n", "\r\n").encode("utf-8"))
    print("已写 CHANGELOG.md：%d 行" % md.count("\n"))

    # 代码：换短 docstring + 升版本号
    if not S7.exists():
        shutil.copy2(S6, S7)
        print("已复制 v1.23.6 → v1.23.7")
    t7 = t6[:i] + '"""' + SHORT + '"""' + t6[j + 3:]
    t7 = t7.replace("元 DGTF · v1.23.6", "元 DGTF · v1.23.7", 1)
    t7 = t7.replace('__version__ = "1.23.6"', '__version__ = "1.23.7"', 1)

    assert nv(ex(t6)) == nv(ex(t7)), "★ 可执行部分变了（不只是 docstring/版本号）"
    print("断言① 抠 docstring + 归一化 __version__ 后逐字相同 ✓（%d 字符）" % len(ex(t7)))
    assert ast.dump(ast.parse(nv(ex(t6)))) == ast.dump(ast.parse(nv(ex(t7)))), "★ AST 不等价"
    print("断言② AST 严格等价 ✓")
    i2 = t7.index('"""')
    assert len(t7[:i2 + 3]) < 4000, "标题不在前 4000 字符内（C1 判据要求）"
    print("断言③ 标题在前 %d 字符内 ✓（C1 判据要求 <4000）" % len(t7[:i2 + 3]))

    body = t7.replace("\n", "\r\n").encode("utf-8")
    assert body.count(b"\r\r\n") == 0 and body.count(b"\r\n") == body.count(b"\n")
    S7.write_bytes(body)
    c = S7.read_bytes()
    print("已写 %s：%d 行 / CRLF=%d 裸LF=%d CRCRLF=%d"
          % (S7.name, c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    ast.parse(c.decode("utf-8").replace("\r\n", "\n"))
    print("ast.parse 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
