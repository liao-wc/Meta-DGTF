#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 收束：① 修 CHANGELOG.md 里 v1.23.7 段的规模数字；
② 在该段末尾插入 `★ v1.23.7 收束摘要`（**落点是 CHANGELOG.md**，不是代码）。

★ 本版起「收束摘要」写在 `CHANGELOG.md` 的对应版本段尾 —— 代码里不再有 changelog，
  自然也不再有收束摘要。幂等。
"""
import re
import sys
from pathlib import Path

CL = Path(__file__).resolve().parent / "CHANGELOG.md"

FIX_OLD = "【规模】21841 → **16885 行**（-4956 行）。"
FIX_NEW = "【规模】21841 → **16894 行**（-4947 行；模块 docstring 从 4957 行降到 8 行）。"

TITLE = "★ v1.23.7 收束摘要"
BODY = """**交付物**：`元DGTF-V1.23.7.py`（16894 行 / 纯 CRLF）；`CHANGELOG.md`
  （4988 行 / 27 段，v1.23.6 及更早**原样搬迁**）；`_mk_v1237_extract.py`（搬移器，
  三条硬断言）；`_mk_v1237_smoke_checks.py`（取源改造 + 新判据 + 守卫 94→95）；
  `_probe_v1237_mutants.py`（4 个变异体）；`_mk_v1237_config_sync.py`；`v1237_报告.md`。

**做了什么**：模块 docstring 里的版本段（4954 行 / 188,747 字符 / 占原文件 22.7%）
  搬进仓库根 `CHANGELOG.md`；代码里的 docstring 换成 8 行短版（标题 + 一句话 +
  指向）。21841 → **16894 行**。

**零行为变化**：模块 docstring 不参与执行，且引擎**不读自己的 `__doc__`**（全文件
  仅 1 处，且在注释里）。硬断言：① 抠掉 docstring + 归一化 `__version__` 后
  **代码部分逐字相同**；② 抠 docstring + 归一化后 **AST 严格等价**；③ 搬出的段数
  == 原段数（26 → 27，新增本版段），段序仍严格递减。

**判据随实现更新（是位置变了，不是放宽）**：`check_v72_changelog_hygiene` 与
  `check_v76_changelog_wording` 的取源从「源码 / 模块 docstring」改到 `CHANGELOG.md`；
  前者另抽纯函数 `_changelog_lint()`，并把负对照从「切换 SRC 指向」（取源外移后
  失效）改成喂**合成坏样本**。新增 `check_v1237_changelog_outside_code`（两向对账：
  代码里 0 处版本段 + `CHANGELOG.md` 段数 ≥ 10，防「搬出去」变「删掉」）。

**验收**：冒烟 exit 0 / **0 个 ✗ / 202 ✓**（上一版 201 ✓ + 新增 1 条判据）；
  新判据 **4 个变异体全符合**（M1 版本段 / M2 收束摘要 必须判红；M3 只在**模块**
  docstring 里塞必须仍绿 —— 证明判据真的抠掉了模块 docstring）；
  `load_config` 前后**逐字差异 0 项**、缺键无；主文件纯 CRLF。

★ **判据补洞（变异体抓出来的）**：`check_v1237` 的段标题正则原来只认 `^v1\\.2\\d`，
  变异体 M1 注入 `v1.99.9 相对 v1.99.8` **竟没判红** ⇒ 已放宽成
  `^v\\d+(?:\\.\\d+)+ 相对`。**这就是「变异体必须打在判据读的那个东西上」的价值。**

**未做**：docstring 正文中段的版本提及（40 处 / 76 行）仍不动（同上一版口径）；
  本版不做真跑（零功能改动，且已证到 AST 级别）。
"""


def main():
    raw = CL.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    n0 = len(re.findall(r"^v(\d+(?:\.\d+)+) 相对", t, re.M))

    if FIX_OLD in t:
        t = t.replace(FIX_OLD, FIX_NEW, 1)
        print("已修规模数字")
    else:
        print("[skip] 规模数字已修")
    assert FIX_OLD not in t

    if TITLE in t:
        print("[skip] 收束摘要已存在")
    else:
        lines = t.split("\n")
        k = lines.index("v1.23.6 相对 v1.23.5")
        # 往前找该段前的 `---`
        j = k - 1
        while lines[j].strip() != "---":
            j -= 1
        assert lines[j].strip() == "---", "找不到段间分隔线"
        block = [""] + TITLE.split("\n") + [""] + BODY.strip("\n").split("\n") + [""]
        lines = lines[:j] + block + lines[j:]
        t = "\n".join(lines)
        print("已插入 ★ v1.23.7 收束摘要（在 CHANGELOG.md 里）")

    n1 = len(re.findall(r"^v(\d+(?:\.\d+)+) 相对", t, re.M))
    assert n1 == n0 == 27, "段数变了：%d -> %d" % (n0, n1)
    vlist = [tuple(int(x) for x in v.split("."))
             for v in re.findall(r"^v(\d+(?:\.\d+)+) 相对", t, re.M)]
    assert all(vlist[k] > vlist[k + 1] for k in range(len(vlist) - 1)), "段序被破坏"
    CL.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    c = CL.read_bytes()
    print("CHANGELOG.md：%d 字节 / %d 行 / %d 段（首段 v%s）/ CRLF=%d 裸LF=%d CRCRLF=%d"
          % (len(c), c.count(b"\n"), n1,
             ".".join(str(x) for x in vlist[0]), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
