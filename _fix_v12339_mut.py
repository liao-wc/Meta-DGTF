# -*- coding: utf-8 -*-
"""[修复] _mut_v12332.py：重写被我写坏的 M82 尾行 + M83/M84 两条。

★ 为什么用 chr(92)/chr(10) 构造：变异体锚点里含「反斜杠 + 换行」
  （行continuation），在「脚本 → 落盘 → Python 解析」三层里数反斜杠
  本轮已栽多次 ⇒ 这里**不用字面转义**，用拼接构造，零歧义。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"
BS = chr(92)
NL = chr(10)

raw = P.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "_mut 不是纯 CRLF"
s = raw.decode("utf-8").replace("\r\n", "\n")

lines = s.split("\n")

# ── 定位损坏块：从 M82 的名字行到 run_check 之前的 ']' ──
i82 = next(i for i, l in enumerate(lines) if l.strip().startswith('("M82'))
iend = next(i for i, l in enumerate(lines)
            if i > i82 and l.strip() == "]")
print("[info] 损坏块：行 %d..%d" % (i82 + 1, iend + 1))

# M83 的锚点值 = 主文件里那一行（含行尾续行反斜杠 + 换行）
A83 = "        if not on_demand " + BS + NL
B83 = "        if True or not on_demand " + BS + NL

block = [
    '    #   ★ M82 打在**放宽表的成员有效性**上：塞一个 `web_search.stages` 里',
    '    #     不存在的环节名 ⇒ 放宽了也不生效（死配置）⇒ 两向对账判据必判红。',
    '    ("M82 放宽表塞入不存在的环节名（死配置）",',
    '     \'                       "expand_pair", "expand_pair_merged_once")\',',
    '     \'                       "expand_pair", "expand_pair_merged_once",\\n\'',
    '     \'                       "__no_such_stage__")\'),',
    '    #   ★ M83 打在**按需四层一致**上：去掉 on_demand 豁免 ⇒ 修行层环节',
    '    #     即使声明了 ===WEB-NEED=== 也会被 stages 未授权挡掉',
    '    #     （= v1.23.38 的老问题；判据「修行层按需仍被拒」必判红）。',
    '    ("M83 按需不豁免逐环节授权（修行层声明也查不到）",',
    "     '" + A83 + "',",
    "     '" + B83 + "'),",
    '    #   ★ M84 打在**成本闸门**上：总闸检查被短路 ⇒ 按需路径在',
    '    #     web_search.enabled=False 时也放行（按需=无上限 ⇒ 成本失控）。',
    '    ("M84 按需短路总闸（关了也能查）",',
    '     \'        if not bool(self.cfg.get("enabled", False)):\'' + NL,
    '     \'            return False, "web_search 未启用（默认关）"\',',
    '     \'        if False:\'' + NL,
    '     \'            return False, "web_search 未启用（默认关）"\'),',
    ']',
]
new_lines = lines[:i82] + block + lines[iend + 1:]
s2 = "\n".join(new_lines)

out = s2.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out
P.write_bytes(out)

# ── 回读自检 ──
chk = P.read_bytes().decode("utf-8")
import ast
ast.parse(chk)
print("[ok] AST OK | CRLF==", P.read_bytes().count(b"\n") == P.read_bytes().count(b"\r\n"))
print("[ok] M82/M83/M84 在列：",
      all(x in chk for x in ("M82 放宽表塞入", "M83 按需不豁免", "M84 按需短路总闸")))
print("[ok] 判据清单含 v12339：", "check_v12339_ondemand()" in chk)
print("[ok] SRC 指向：",
      [l for l in chk.split("\n") if l.startswith("SRC = HERE")])