#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 收尾两件：
  ① 报告里的 __SMOKE_V__ 占位回填成实测 ✓ 数；
  ② 给主文件 docstring 的 v1.23.6 段尾加「★ v1.23.6 收束摘要」（只动 docstring）。
两条幂等。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.6.py"
BAK = HERE / "_bak_元DGTF-V1.23.6.py.pre_shoushu"
REP = HERE / "v1236_报告.md"
NMARK = "__SMOKE_V__"
NV = "201"

TITLE = "  ★ v1.23.6 收束摘要"
BODY = '''  **交付物**：元DGTF-V1.23.6.py（纯 CRLF，21761 行）；`_mk_v1236_strip.py`（剥离器：
    三类处置 + 两条保护 + 四条断言，`--dry` / `--go`）；`_mk_v1236_head.py` /
    `_mk_v1236_smoke_checks.py` / `_mk_v1236_config_sync.py`；三支 `_fix_v1236_*.py`
    （随实现更新的判据与夹具）；`_probe_v1236_mutants.py`（5 个变异体）；
    `v1236_报告.md`；`docs/版次批注存档-v1.23.5.md`（被删内容全文存档，3092 行）。

  **做了什么**：把代码正文（模块 docstring 之外）的版次批注清掉 —— A 全行批注块
    **378 块 / 1476 行**（连块删）、B 行尾批注 **9 处**（只删注释、代码不动）、
    C docstring 前导标记 **66 处**（只剥标记、正文保留）。23237 → **21761 行**。

  **两条保护（都因为「判据在读」）**：P1 含 `[AUDIT-n]` 的行不删（冒烟按它数
    pending_fix 条数）；P2 **判据需要的片段**（156 个）做**最小代价保护** —— 只在
    某片段会全部消失时保住最短那一行（只多保 3 行）。★ 实踩：`assert "修行层不追求
    收敛" in src` 只出现在一行带版次标签的**宪法红线注释**里。

  **零行为变化的机器证明（四条）**：① 删注释后 AST（抠模块 docstring + 归一化
    `__version__`）**严格等价**；② 剥 docstring 前导标记后逐字符串常量比对：差异
    **66 处**、每处都 `old == tag + new`；③ 抹空全部字符串常量后 AST 仍**严格等价**；
    ④ 156 个判据片段**一个都没少**。

  **验收**：冒烟 exit 0 / **0 个 ✗ / 201 ✓**（上一版 200 ✓ + 新增 1 条判据）；
    新判据的 **5 个变异体全部符合**（M0 绿 / M1~M3 判红 / M4 只在模块 docstring
    里塞标记仍绿 —— 证明判据真的抠掉了 docstring）；负对照（对上一版跑同一判据）
    扫到 **441 行**成块批注；`load_config` 前后**逐字差异 0 项**、缺键无。

  **判据随实现更新 2 处（是判据过时，不是放宽）**：`check_v72_bbarrier_semantics`
    的锚点 `[v1.21.72 #13]` → 换成同一段注释里的两条内容短语；变异体 M3 的锚点
    去掉注释、只锚代码行。两处的**判据意图一字未改**。

  **明确不动**：docstring 正文中段的版本提及（40 个字符串常量 / 76 行）—— 那是
    文档行文（在说规则何时定下来），不是「代码前面的修改描述」；要清它属于
    **编辑决策**，需另开一批并另配证法。

'''


def ex(t):
    i = t.index('"""'); j = t.index('"""', i + 3)
    return t[:i] + '"""X"""' + t[j + 3:]


def nv(t):
    o, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', t)
    assert n == 1
    return o


def main():
    # ① 报告回填
    r = REP.read_text(encoding="utf-8")
    if NMARK in r:
        r = r.replace(NMARK, NV)
        REP.write_text(r, encoding="utf-8")
        print("报告已回填 ✓ 数 = %s（%d 处）" % (NV, 4))
    else:
        print("[skip] 报告无占位（已回填过）")

    # ② 收束摘要
    raw = SRC.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    if TITLE in t:
        print("[skip] 收束摘要已存在")
        return 0

    lines = t.split("\n")
    A = "【未做】无功能改动 —— 阈值、常量、控制流、返回值一律未动。"
    assert lines.count(A) == 1, "锚点命中 %d 次" % lines.count(A)
    k = lines.index(A)
    assert lines[k + 1] == "" and lines[k + 2] == "v1.23.5 相对 v1.23.4", "锚点后不是 v1.23.5 段标题"
    sep = next(ln for ln in lines if re.fullmatch(r"  \u2500+", ln))
    print("分隔线宽度：2 空格 + %d 个 U+2500" % (len(sep) - 2))
    block = [sep, TITLE, sep, ""] + BODY.strip("\n").split("\n") + [""]
    new = lines[: k + 2] + block + lines[k + 2:]
    t2 = "\n".join(new)

    assert ex(t) == ex(t2), "★ 可执行部分变了（不只是 docstring）"
    print("断言① 抠掉 docstring 后逐字相同 ✓（%d 字符）" % len(ex(t2)))
    assert ast.dump(ast.parse(nv(ex(t)))) == ast.dump(ast.parse(nv(ex(t2)))), "★ AST 不等价"
    print("断言② AST 等价 ✓")
    secs = re.findall(r"^v(1\.2\d\.\d+) 相对", t2, re.M)
    ver = [tuple(int(x) for x in v.split(".")) for v in secs]
    assert all(ver[i] > ver[i + 1] for i in range(len(ver) - 1)), "段序被破坏"
    print("断言③ %d 个版本段严格递减 ✓（首段 v%s）" % (len(secs), secs[0]))

    if not BAK.exists():
        shutil.copy2(SRC, BAK)
        print("回滚点：%s" % BAK.name)
    out = t2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SRC.write_bytes(out)
    c = SRC.read_bytes()
    print("已写 %s：%d 行 / CRLF=%d 裸LF=%d CRCRLF=%d"
          % (SRC.name, c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
