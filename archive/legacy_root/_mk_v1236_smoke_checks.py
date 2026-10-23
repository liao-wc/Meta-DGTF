#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6：smoke_test.py 接线 —— SRC 指向新版 + 新增 check_v1236_no_version_tags。

幂等：哨兵盯**精确的注册串**（`def check_v1236_no_version_tags` / 那行守卫），
不是「符号名出现过」—— 后者会被自己插进去的注释误判（本项目踩过）。
守卫只增自己那条，并断言总数 +1（不许动别人的守卫）。
smoke_test.py 是纯 CRLF：read_bytes → 归一 → 改 → 转回 → write_bytes。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1236"

END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

# ---- 注入内容（raw 字符串：反斜杠与 \u 转义原样进文件）----
CONST = r'''# [v1.23.6] 版次标记：方括号短标签 `[v122 P6 G6.2]` ｜ 裸 v+数字 `v1.21.59`/`v59`
#   两侧的 lookbehind/lookahead 挡掉 `deepseek-v4-pro` 这类假阳性（实测）。
#   ★ 口径与 `_mk_v1236_strip.py` 里的 TAG 必须逐字一致 —— 判据与清理工具同一把尺子。
V1236_TAG = (r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")


def check_v1236_no_version_tags():
    """[v1.23.6] 代码正文（模块 docstring 之外）不留版次批注。

    抠掉模块 docstring 后：
      ① 注释里不得出现版次标记（含 `# [vX.Y.Z …]` 与行尾批注）；
      ② 不得有**以版次标记开头**的 docstring。
    ★ 负对照打在**上一版文件**上：v1.23.5 必须被判红 —— 这条负对照是本判据
      判别力的来源，缺了它「全绿」只说明判据没跑（本项目的经典假绿）。
    ★ 抠 docstring 前先归一化换行：`doc in raw` 在 CRLF 原文里是 False，
      会静默退化成「全文件扫描」。
    """
    TAG = re.compile(V1236_TAG)
    bad = []
    raw = SRC.read_bytes().decode("utf-8")
    src = raw.replace("\r\n", "\n")
    i = src.index('"""')
    j = src.index('"""', i + 3)
    body_len = len(src) - (j + 3)
    if not (0 < body_len < len(src) - 3):
        bad.append("抠模块 docstring 没生效（抠法自证失败）")
    de = src[:j].count("\n")
    lines = src.split("\n")
    hits = [k + 1 for k in range(de + 1, len(lines))
            if lines[k].lstrip().startswith("#") and TAG.search(lines[k])]
    trail = [k + 1 for k in range(de + 1, len(lines))
             if not lines[k].lstrip().startswith("#") and "#" in lines[k]
             and TAG.search(lines[k].split("#", 1)[1])]
    if hits or trail:
        bad.append("正文注释里仍有版次批注：%d 行成块 + %d 行行尾，前 5 个行号 %s"
                   % (len(hits), len(trail), (hits + trail)[:5]))
    leads = []
    import ast as _ast
    for node in _ast.walk(_ast.parse(src)):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            if node.lineno > de + 1 and re.match(r"\s*(?:" + V1236_TAG + r")", node.value):
                leads.append(node.lineno)
    if leads:
        bad.append("仍有以版次标记开头的 docstring %d 处，前 5 个行号 %s"
                   % (len(leads), leads[:5]))
    # ---- 负对照：上一版必须判红 ----
    prev = HERE / "元DGTF-V1.23.5.py"
    pn = 0
    if not prev.is_file():
        bad.append("负对照文件缺失 %s —— 判据判别力无法自证" % prev.name)
    else:
        psrc = prev.read_bytes().decode("utf-8").replace("\r\n", "\n")
        pi = psrc.index('"""')
        pj = psrc.index('"""', pi + 3)
        pde = psrc[:pj].count("\n")
        plines = psrc.split("\n")
        pn = sum(1 for k in range(pde + 1, len(plines))
                 if plines[k].lstrip().startswith("#") and TAG.search(plines[k]))
        if pn == 0:
            bad.append("负对照失效：上一版 %s 一条都没扫到 —— 判据没有判别力" % prev.name)
    if bad:
        for m in bad:
            print("  \u2717 [v1236] %s" % m)
        return False
    print("  \u2713 [v1236] 正文注释 0 处版次批注、docstring 0 处前导标记；"
          "负对照（v1.23.5）判红 %d 行成块批注" % pn)
    return True

'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0, "smoke 不是纯 CRLF"
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # 1) SRC
    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.6.py"', s, count=1)

    # 2) 常量 + check 函数（插在 end MARK 之前）
    if "def check_v1236_no_version_tags" in s:
        print("[skip] check_v1236 已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + CONST + s[k:]
        print("已插入 V1236_TAG + check_v1236_no_version_tags（在 end MARK 前）")

    # 3) 守卫（插在最后一条既有守卫之后；只增自己这条）
    if "if not check_v1236_no_version_tags():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 74, "既有守卫只有 %d 条（基线 74），先查是不是被清空了" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v1236_no_version_tags():\n        return 1\n" + s[pos:]
        n_after = len(GUARD_RE.findall(s))
        assert n_after == n_before + 1, "守卫数 %d -> %d（不是 +1）" % (n_before, n_after)
        print("守卫 %d -> %d" % (n_before, n_after))

    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)

    c = SK.read_bytes()
    t = c.decode("utf-8").replace("\r\n", "\n")
    print("smoke_test.py: %d 字节 / %d 行 / CRLF=%d 裸LF=%d CRCRLF=%d"
          % (len(c), c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    print("SRC 行:", [l for l in t.split("\n") if l.startswith("SRC")][0].strip())
    print("守卫总数:", len(GUARD_RE.findall(t)))
    ast.parse(t)
    print("ast.parse 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
