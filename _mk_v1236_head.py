#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6：版本号两处 + 顶部插入「v1.23.6 相对 v1.23.5」changelog 段。只动 docstring
与 __version__ 字面量。主文件纯 CRLF，走 read_bytes/write_bytes。"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.6.py"
BAK = HERE / "_bak_元DGTF-V1.23.6.py.pre_head"

SEC = """v1.23.6 相对 v1.23.5

【主题】代码正文不再留「版次批注」—— 变更记录统一由本 docstring 的 changelog
  承担；代码正文里的注释只解释「这段**当前**为什么长这样」。

【做什么】模块 docstring 之外，凡带版次标记的注释与文档串一律清理：
  · A 全行批注块：整行注释且含标记 → **连块删**（378 块 / 1476 行）
  · B 行尾批注：代码 + 同行注释含标记 → 只删注释部分（9 处）
  · C 文档串前导标记：函数/类 docstring **以**标记开头 → 只剥标记（66 处）
【两条保护，都因为「判据在读」】
  · P1 含 `[AUDIT-n]` 的注释行**不删**（冒烟按它数 pending_fix 条数）；行内的
    版次标记另行抹掉，所以保护行也不含标记（2 行）。
  · P2 **判据需要的片段**一个都不许消失：从 `smoke_test.py` + `_v122_verify.py`
    收集全部 `"X" in src` / `"X" not in src` 与 `src.count("X")` 的 X（156 个），做「最小代价
    保护」—— 某片段若**全部出现处**都在待删行里，只保住其中**最短的那一行**
    （实保 3 行），而不是整块。★ 本项目实踩：`assert "修行层不追求收敛" in src,
    "缺红线注释"` 只出现在一行带版次标签的**宪法红线注释**里 —— 盲目按标记
    删会直接打掉红线。

【版次标记的口径】`[v<数字>…]` 方括号短标签（如 [v122 P6 G6.2]）｜裸 v+数字
  （v1.21.59 / v1.19 / v59）；两侧用 `(?<![A-Za-z0-9_-])` / `(?![A-Za-z0-9_-])`
  挡掉 `deepseek-v4-pro` 这类假阳性。★ **必须按「块」量**：块内只有首行带标记，
  按行数会把规模低估到 28%（v1.23.5 定口径时据窄口径报 395 行，实为 1470 行）。

【零行为变化的机器证明】四条一起，等价于「只删注释 + 只剥 docstring 前导标记」：
  ① A+B 删完后 AST（抠掉模块 docstring + 归一化 `__version__`）**严格等价**；
  ② C 之后逐字符串常量比对：差异 **66 处**，每一处都恰好等于「剥掉一个前导
     版次标记」（`old == tag + new`），不多不少；
  ③ 把所有字符串常量的值抹空再比 AST —— **严格等价**，结构与非字符串常量
     一个都没动；
  ④ 判据需要的 156 个片段，**一个都没少**（全局断言）。

【规模】23237 → **21761 行**（-1476）；1296038 → **1169589 字节**（-123 KB）。
  被删内容**全文存档**在 `docs/版次批注存档-v1.23.5.md`（3092 行，带行号与最近的
  def/class 归属），配 git 历史可完全复原。

【明确不动】docstring **正文中段**的版本提及（40 个字符串常量 / 76 行）—— 例如
  「★ 兼容 v1.21.75 的布尔：True → evidence」。那是**文档行文**（在说这条规则
  何时定下来），不是「代码前面的修改描述」；要清它属于**编辑决策**而非机械操作，
  故留待需要时单独一批。

【未做】无功能改动 —— 阈值、常量、控制流、返回值一律未动。

"""


def main():
    raw = SRC.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    t = raw.decode("utf-8").replace("\r\n", "\n")

    # 1) docstring 标题
    n1 = t.count("元 DGTF · v1.23.5")
    assert n1 == 1, "标题命中 %d 次" % n1
    t = t.replace("元 DGTF · v1.23.5", "元 DGTF · v1.23.6", 1)

    # 2) __version__
    n2 = t.count('__version__ = "1.23.5"')
    assert n2 == 1, "__version__ 命中 %d 次" % n2
    t = t.replace('__version__ = "1.23.5"', '__version__ = "1.23.6"', 1)

    # 3) 插入 changelog 段（整行锚点）
    lines = t.split("\n")
    A = "v1.23.5 相对 v1.23.4"
    assert lines.count(A) == 1, "段标题锚点命中 %d 次" % lines.count(A)
    k = lines.index(A)
    assert lines[k - 1] == "", "段标题前不是空行"
    new = lines[:k] + SEC.rstrip("\n").split("\n") + [""] + lines[k:]
    t2 = "\n".join(new)

    if not BAK.exists():
        shutil.copy2(SRC, BAK)
        print("回滚点：%s" % BAK.name)

    out = t2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SRC.write_bytes(out)

    chk = SRC.read_bytes().decode("utf-8")
    print("标题:", re.findall(r"元 DGTF · (v[\d.]+)", chk)[0])
    print("__version__:", re.findall(r'__version__ = "([\d.]+)"', chk)[0])
    secs = re.findall(r"^v(1\.2\d\.\d+) 相对", chk.replace("\r\n", "\n"), re.M)
    print("版本段（前 5）:", secs[:5], "共 %d 段" % len(secs))
    ver = [tuple(int(x) for x in v.split(".")) for v in secs]
    assert all(ver[i] > ver[i + 1] for i in range(len(ver) - 1)), "段序被破坏"
    print("段序严格递减 ✓")
    print("行数:", chk.count("\n"))
    b = SRC.read_bytes()
    print("CRLF=%d 裸LF=%d CRCRLF=%d" % (b.count(b"\r\n"), b.count(b"\n") - b.count(b"\r\n"), b.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
