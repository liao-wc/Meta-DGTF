#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6：把代码正文（模块 docstring 之外）里的**版次批注**清掉。

三类处置（口径写死，判据照抄）：
  A 全行批注：整行注释且含版次标记 → **连块删**（块 = 连续注释行）
  B 行尾批注：代码 + 同行 `# …` 且注释部分含标记 → 只删注释部分
  C 文档串  ：函数/类 docstring **以**版次标记开头 → 只剥前导标记，正文一字不动

版次标记 TAG = `[v<数字>…]` 方括号短标签 ｜ 裸 v+数字（v1.21.59 / v1.19 / v59）
  两侧 `(?<![A-Za-z0-9_-])` / `(?![A-Za-z0-9_-])` 挡掉 `deepseek-v4-pro` 这类假阳性。

两条保护（都因为「判据在读」）：
  · P1 含 `[AUDIT-<数字>]` 的注释行不删 —— 冒烟按它数 pending_fix 条数；
  · P2 **判据需要的片段**（冒烟 / 验收档里 `"X" in src` 与 `src.count("X")` 的 X）
    一个都不许消失。做法是「最小代价保护」：某片段若**全部出现处**都在待删行里，
    就只保住其中最短的那一行（而不是整块），保证片段留存、删除量最小。
    本项目实踩：`assert "修行层不追求收敛" in src, "缺红线注释"` 只出现在一行
    带版次标签的宪法红线注释里。

证明「零行为变化」三连（注释不进 AST，所以前两条是硬证明）：
  ① A+B+保护行剥标记之后，AST（抠掉模块 docstring + 归一化 __version__）**严格等价**；
  ② C 之后逐字符串常量比对：差异数 == C 类数，且每处都恰好等于「剥掉一个前导标记」；
  ③ 把所有字符串常量抹空再比 AST —— **严格等价**。
  ④ 判据需要的片段一个都没少（全局断言）。

用法：python _mk_v1236_strip.py --dry    # 只打印数字与断言
      python _mk_v1236_strip.py --go     # 落地（含写存档）
"""
import ast
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC5 = HERE / "元DGTF-V1.23.5.py"
SRC6 = HERE / "元DGTF-V1.23.6.py"
BAK = HERE / "_bak_元DGTF-V1.23.6.py.pre_strip"
ARCHIVE = HERE / "docs" / "版次批注存档-v1.23.5.md"

TAG = re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
PROTECT = re.compile(r"\[AUDIT-\d+\]")
LIT = r'(["\'])((?:(?!\1).){3,120}?)\1'


def read_lf(p):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "%s 不是纯 CRLF" % p.name
    assert b.count(b"\r\r\n") == 0, "%s 有 CRCRLF" % p.name
    return b.decode("utf-8").replace("\r\n", "\n")


def is_comment(ln):
    return ln.lstrip().startswith("#")


def doc_end_line(lf):
    i = lf.index('"""')
    j = lf.index('"""', i + 3)
    return lf[:j].count("\n")


def collect_needed(*files):
    need = set()
    for f in files:
        if not f.is_file():
            continue
        t = f.read_bytes().decode("utf-8").replace("\r\n", "\n")
        for m in re.finditer(LIT + r'\s+(?:not\s+)?in\s+(?:_?src|_?code|_?eng|body|raw|t|txt|s)\b', t):
            need.add(m.group(2))
        for m in re.finditer(r'\.count\(\s*' + LIT + r'\s*\)', t):
            need.add(m.group(2))
    return need


def blocks_of(L, de):
    """所有「含版次标记的全行注释」所在的连续注释块（不排除 AUDIT 行）。"""
    cand = [k for k in range(de + 1, len(L)) if is_comment(L[k]) and TAG.search(L[k])]
    blocks, seen = [], set()
    for k in cand:
        if k in seen:
            continue
        a = k
        while a - 1 > de and is_comment(L[a - 1]) and (a - 1) not in seen:
            a -= 1
        b = k
        while b + 1 < len(L) and is_comment(L[b + 1]):
            b += 1
        for x in range(a, b + 1):
            seen.add(x)
        blocks.append((a, b))
    return blocks


def ex(t):
    a = t.index('"""'); b = t.index('"""', a + 3)
    return t[:a] + '"""X"""' + t[b + 3:]


def nv(t):
    o, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', t)
    assert n == 1, "__version__ 出现 %d 次" % n
    return o


def blank_strs(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return tree


def const_list(tree):
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def main():
    mode = "--go" if "--go" in sys.argv else "--dry"
    lf5 = read_lf(SRC5)
    lf = lf5 if mode == "--dry" else read_lf(SRC6)
    L = lf.split("\n")
    de = doc_end_line(lf)
    NEED = collect_needed(HERE / "smoke_test.py", HERE / "_v122_verify.py")
    print("模块 docstring: 1 ~ %d 行；判据需要的片段 = %d 个" % (de + 1, len(NEED)))

    # ---------- 计划：A 块删除 ----------
    bl = blocks_of(L, de)
    audit_keep = set(k for k in range(de + 1, len(L))
                     if is_comment(L[k]) and PROTECT.search(L[k]))
    DEL = set()
    for a, b in bl:
        DEL |= set(range(a, b + 1))
    DEL -= audit_keep
    n_blocks_all, n_del_raw = len(bl), len(DEL)

    # ---------- P2 最小代价保护 ----------
    prot_extra = set()
    for n in sorted(NEED):
        occ = [k for k in range(de + 1, len(L)) if n in L[k]]
        if not occ:
            continue
        if any(k not in DEL for k in occ):
            continue
        best = min((k for k in occ if k in DEL), key=lambda k: len(L[k]))
        prot_extra.add(best)
        DEL.discard(best)
    print("A 块 %d 个 / 原可删 %d 行 → 判据保护再保 %d 行 → 实删 %d 行"
          % (n_blocks_all, n_del_raw, len(prot_extra), len(DEL)))

    # ---------- B 行尾批注 ----------
    trail = [k for k in range(de + 1, len(L))
             if not is_comment(L[k]) and "#" in L[k]
             and TAG.search(L[k].split("#", 1)[1])]
    no_strip = set()
    for k in trail:
        pos = L[k].find("#")
        for n in NEED:
            if n in L[k][pos:]:
                others = [j for j in range(de + 1, len(L)) if j != k and n in L[j] and j not in DEL]
                others += [k] if n in L[k][:pos] else []
                if not others:
                    no_strip.add(k)
                    print("     行 %d 的行尾批注被保护（判据需要片段 %r）" % (k + 1, n))
    trail = [k for k in trail if k not in no_strip]

    # ---------- 生产 L2 ----------
    prot_lines = sorted(audit_keep | prot_extra)
    L2 = list(L)
    for k in trail:
        pos = L2[k].find("#")
        L2[k] = L2[k][:pos].rstrip()
    for k in prot_lines:
        if TAG.search(L2[k]):
            L2[k] = re.sub(r"  +", " ", TAG.sub("", L2[k]))
    L2 = [ln for k, ln in enumerate(L2) if k not in DEL]

    # ---------- 断言① ----------
    a5 = ast.dump(ast.parse(nv(ex(lf5))))
    a2 = ast.dump(ast.parse(nv(ex("\n".join(L2)))))
    print("[断言①] A+B+保护行剥标记后 AST 严格等价 =", a5 == a2)
    assert a5 == a2, "★ 注释层面的处置改变了 AST"

    # ---------- C 文档串前导标记 ----------
    t2 = "\n".join(L2)
    hits_c = []
    for node in ast.walk(ast.parse(t2)):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if node.lineno <= de + 1:
            continue
        if not re.match(r"\s*(?:" + TAG.pattern + r")", node.value):
            continue
        lines = t2.split("\n")
        start = sum(len(x) + 1 for x in lines[:node.lineno - 1]) + node.col_offset
        assert t2[start:start + 3] in ('"""', "'''")
        cstart = start + 3
        sm = re.match(r"\s*(" + TAG.pattern + r")", t2[cstart:])
        assert sm, "源码里锚不到前导标记"
        hits_c.append((cstart, sm.end(1), node.value, node.lineno))
    print("[C] 以前导版次标记开头的 docstring = %d 处" % len(hits_c))
    assert hits_c, "C 类为空 —— 定位逻辑坏了"
    t3 = t2
    for cstart, lead_len, _v, _ln in sorted(hits_c, key=lambda x: -x[0]):
        t3 = t3[:cstart] + t3[cstart + lead_len:]

    # ---------- 断言②③④ ----------
    v5, v3 = const_list(ast.parse(ex(lf5))), const_list(ast.parse(ex(t3)))
    assert len(v5) == len(v3), "字符串常量个数变了"
    diffs = [(i, a, b) for i, (a, b) in enumerate(zip(v5, v3)) if a != b]
    for i, o, n in diffs:
        g = re.match(r"\s*(" + TAG.pattern + r")", o)
        assert g and o == g.group(1) + n, "差异不是「剥掉前导标记」：#%d" % i
    assert len(diffs) == len(hits_c), "差异 %d != C 类 %d" % (len(diffs), len(hits_c))
    print("[断言②] 字符串常量差异 = %d 处，且全部 == 「剥掉前导标记」" % len(diffs))
    d5 = ast.dump(blank_strs(ast.parse(ex(lf5))))
    d3 = ast.dump(blank_strs(ast.parse(ex(t3))))
    print("[断言③] 抹掉全部字符串后 AST 严格等价 =", d5 == d3)
    assert d5 == d3
    miss = sorted(n for n in NEED if n in lf5 and n not in t3)
    print("[断言④] 判据需要、却在删改后消失的片段 = %d 个" % len(miss))
    for n in miss[:12]:
        print("     ★ %r" % n)
    assert not miss, "★ 删掉了判据需要的片段"

    # ---------- 残留 ----------
    L3 = t3.split("\n")
    de3 = doc_end_line(t3)
    res = [k for k in range(de3 + 1, len(L3)) if is_comment(L3[k]) and TAG.search(L3[k])]
    print("\n[残留] 正文注释里仍含版次标记 = %d 行" % len(res))
    print("[残留] 正文里（含字符串）含版次标记 = %d 行"
          % sum(1 for k in range(de3 + 1, len(L3)) if TAG.search(L3[k])))
    print("行数 %d -> %d（-%d）" % (len(L), len(L3), len(L) - len(L3)))
    if mode == "--dry":
        print("\n[dry] 未落盘")
        return 0

    # ---------- 存档 ----------
    own = {}
    for node in ast.walk(ast.parse(lf5)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for k in range(node.lineno - 1, node.end_lineno or node.lineno):
                own.setdefault(k, node.name)
    out = ["# 代码正文版次批注 · 存档（源：元DGTF-V1.23.5.py）", "",
           "这是 v1.23.6「清掉代码正文版次批注」时**被删内容的原文存档**。",
           "删除只动注释与 docstring 前导标记，**可执行语句零改动**（AST 逐节点证明，",
           "见 `v1236_报告.md` 与 `_mk_v1236_strip.py` 的断言①~④）。行号是 v1.23.5 的，",
           "便于用 `git show` 对照。", "", "## 统计", "", "| 项 | 数量 |", "|---|---|",
           "| A 全行批注块 | %d 块 / %d 行（原可删 %d 行，判据保护 %d 行）|"
           % (n_blocks_all, len(DEL), n_del_raw, len(prot_extra)),
           "| B 行尾批注 | %d 行（判据保护 %d 行不剥）|" % (len(trail) + len(no_strip), len(no_strip)),
           "| C docstring 前导标记 | %d 处 |" % len(hits_c),
           "| 合计减少行 | %d |" % (len(L) - len(L3)), ""]
    for a, b in bl:
        alive = [k for k in range(a, b + 1) if k not in DEL]
        if not alive:
            out.append("### 行 %d-%d（%d 行）· %s" % (a + 1, b + 1, b - a + 1, own.get(a, "<module>")))
        else:
            out.append("### 行 %d-%d（%d 行，其中 %d 行因判据需要而保留）· %s"
                       % (a + 1, b + 1, b - a + 1, len(alive), own.get(a, "<module>")))
        out.append("```python")
        out.extend(L[a:b + 1])
        out.append("```")
        out.append("")
    out += ["## B 行尾批注", ""]
    for k in sorted(set(trail) | no_strip):
        out.append("- 行 %d：`%s`" % (k + 1, L[k].strip()))
    out += ["", "## C docstring 前导标记（只剥标记，其余正文保留）", ""]
    for cstart, lead_len, v, ln in hits_c:
        out.append("- 行 %d：剥掉 `%s`" % (ln, re.match(r"\s*(" + TAG.pattern + r")", v).group(1)))
    out.append("")
    ARCHIVE.write_bytes("\n".join(out).replace("\n", "\r\n").encode("utf-8"))
    print("\n存档已写：%s（%d 行）" % (ARCHIVE.name, len(out)))

    if not BAK.exists():
        shutil.copy2(SRC6, BAK)
        print("回滚点：%s" % BAK.name)
    body = t3.replace("\n", "\r\n").encode("utf-8")
    assert body.count(b"\r\r\n") == 0 and body.count(b"\r\n") == body.count(b"\n")
    SRC6.write_bytes(body)
    chk = SRC6.read_bytes()
    print("已写 %s：%d 字节 / %d 行 / CRLF=%d 裸LF=%d CRCRLF=%d"
          % (SRC6.name, len(chk), chk.count(b"\n"), chk.count(b"\r\n"),
             chk.count(b"\n") - chk.count(b"\r\n"), chk.count(b"\r\r\n")))
    ast.parse(chk.decode("utf-8").replace("\r\n", "\n"))
    print("ast.parse 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
