#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[补丁] `_ALL_ON_ITEMS` 补上 `actions.merge_expand` + 新增 `_ALL_ON_EXEMPT`。

## 依据（用户口径）
「所有最终真跑验收默认都是配置开关全开或者针对性设置配置，不仅可以检验本次
 改动，还方便检查之前的改动有没有生效、**或者发现新问题**。」
⇒ 「全开」必须**真的全**，否则全开真跑会**静默验不到**某些能力。

## 缺陷（探针 `_probe_v12336_allon_cov.py` 对账所得，只读不猜）
- 引擎有 **16** 个 `_action_on(..., "x")` 能力开关；
- `DEFAULT_CONFIG['actions']` 里**默认 False 的恰好只有 1 个**：`merge_expand`
  （其余 15 个出厂即 True）⇒ 「全开」时**唯一该开而未开的**就是它；
- 而 `_ALL_ON_ITEMS` 自称「只列可切换的能力开关」，却没列它
  ⇒ 漏项**没有任何判据发现**（上一轮日志写「11 项全开含 actions.merge_expand」，
    实测 10 项）。

## 改动边界（红线：出厂零行为变化）
只改 **`_ALL_ON_ITEMS`（全开时才生效）**；`DEFAULT_CONFIG` 与出厂 yaml 的
`actions.merge_expand: false` **一律不动** ⇒ `all_on` 为假时逐字恒等。
`_ALL_ON_EXEMPT` 初始为空表（**当前无豁免项**），供判据两向对账用。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "元DGTF-V1.23.36.py"

# ── 改动 ①：全开清单补上 merge_expand ──
OLD1 = '    ("api.thinking.effort", "high", "思考强度 high"),\n)'
NEW1 = ('    ("api.thinking.effort", "high", "思考强度 high"),\n'
        '    ("actions.merge_expand", True,\n'
        '     "阴阳展开合并成一次调用（降本开关，出厂关）"),\n)')

# ── 改动 ②：紧跟清单之后加豁免表 ──
OLD2 = ')\n\n\ndef _apply_all_on(cfg: dict):'
NEW2 = (')\n\n'
        '#: [一键全开] **显式豁免表**：`{配置路径: 为什么不开}`。\n'
        '#: ★ 规则：`DEFAULT_CONFIG["actions"]` 里**默认关**的能力开关，必须要么在\n'
        '#:   `_ALL_ON_ITEMS` 里、要么在这里**显式登记 + 写原因**；两向对账判据\n'
        '#:   见 `smoke_test` 的 `check_v12336_allon_cov`（空表 = 当前无豁免项）。\n'
        '_ALL_ON_EXEMPT = {}\n\n\n'
        'def _apply_all_on(cfg: dict):')


def patch(txt, old, new, tag):
    n = txt.count(old)
    assert n == 1, "%s：锚点命中 %d 次（应为 1）" % (tag, n)
    return txt.replace(old, new, 1)


def main():
    b = SRC.read_bytes()
    crlf, lf = b.count(b"\r\n"), b.count(b"\n")
    assert crlf == lf, "源码不是纯 CRLF：CRLF=%d LF=%d" % (crlf, lf)
    txt = b.decode("utf-8").replace("\r\n", "\n")

    txt = patch(txt, OLD1, NEW1, "改动①merge_expand")
    txt = patch(txt, OLD2, NEW2, "改动②豁免表")

    out = txt.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "写回产生了 CR-CR-LF"
    SRC.write_bytes(out)

    chk = SRC.read_bytes()
    print("OK 已写入 元DGTF-V1.23.36.py：CRLF=%d LF=%d CRCRLF=%d"
          % (chk.count(b"\r\n"), chk.count(b"\n"), chk.count(b"\r\r\n")))
    tail = chk.decode("utf-8").split("\n")
    for i, l in enumerate(tail):
        if "actions.merge_expand" in l or "_ALL_ON_EXEMPT = " in l:
            print("   L%d: %s" % (i + 1, l.rstrip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
