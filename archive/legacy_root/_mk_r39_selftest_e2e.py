#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R39 需求 2 的**端到端**判据：日志共有头（`__head__`）必须随 `/layers` 到前端。

放在 selftest 里那条**真跑 mock 任务**的段落之后（已经有 `lyr`）——
比另起一支 e2e 更不容易腐烂（那条路本来就每轮真起服务 + 真跑任务）。

★ 三段一起判，缺一不可：
  ① 头部内容到得了前端（`head` 非空且含「载入调度配置」）；
  ② **负对照**：这几行**不在四层里任何一层** —— 否则前端从层文本里也能读到，
     「head 断链」就不会显形（用户实测：整段被丢掉就是因为桶名对不上）；
  ③ 前端**两条取值路径**都在（`r.head` 与 `r.layers['__head__']`），源码级锚住。

    python _mk_r39_selftest_e2e.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

ANCHOR = ('    check("[tok] 读数行不进卡片日志",\n'
          '          "[tok]" not in "".join(lyr["layers"].values()))')

BLOCK = '''    # ★R39 需求 2：日志**共有头**（`__head__`）必须随 /layers 到前端 ——
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
'''


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0 and b.count(b"\r") == b.count(b"\r\n")
    p.write_bytes(b)


def main() -> int:
    cur = read_crlf(ST).replace("\r\n", "\n")
    if "★R39 /layers 带**日志共有头**" in cur:
        print("  · 已注入，跳过")
    else:
        assert cur.count(ANCHOR) == 1, "锚点命中 %d 次" % cur.count(ANCHOR)
        ast.parse("if 1:\n" + BLOCK)
        cur = cur.replace(ANCHOR, ANCHOR + "\n" + BLOCK.rstrip("\n"))
        print("  ✓ 注入 2 条 /layers 端到端判据（含负对照）")
    write_crlf(ST, cur)

    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    assert back.count("★R39 /layers 带**日志共有头**") == 1
    assert back.count("★R39 负对照：这几行**不在四层里任何一层**") == 1
    assert back.count('check("★R39') == 22, "★R39 判据 %d 条（期望 22）" % back.count('check("★R39')
    print("  ✓ 自检：AST 通过 / ★R39 判据 22 条（20 前端 + 2 端到端）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
