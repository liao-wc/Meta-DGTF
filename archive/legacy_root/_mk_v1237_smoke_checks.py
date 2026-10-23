#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7：smoke_test.py 接线。
  1) SRC → 元DGTF-V1.23.7.py
  2) 新增 `_changelog_text()`（读仓库根 CHANGELOG.md）
  3) `check_v72_changelog_hygiene` 取源改到 CHANGELOG.md，并抽成纯函数
     `_changelog_lint()` + **合成坏样本**做负对照（保判别力）
  4) `check_v76_changelog_wording` 取源改到 CHANGELOG.md
  5) 新增 `check_v1237_changelog_outside_code` + 守卫
幂等（哨兵盯精确注册串）；smoke_test.py 纯 CRLF。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1237"
END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

OLD_HYG = '''def check_v72_changelog_hygiene():
    """[v1.21.72 #20] changelog 不得有重复的「★ vX 收束摘要」段，
    版本段序必须按版本号**严格递减**。

    ★ 判别力来源（也是它的负对照）：把 `SRC` 指回 v1.21.71 时，
      改前实测是「`★ v1.21.63 收束摘要` ×2 + 段序 70→68→69」，
      这条必须判红（见 `_probe_v72_before.txt` [C]）。
    """
    bad = []
    eng, _exec = _v72_engine_src()
    i = eng.index('"""')
    j = eng.index('"""', i + 3)
    doc = eng[i:j + 3]
    sums = [ln.strip() for ln in doc.split("\\n")
            if "★ v1.21." in ln and "收束摘要" in ln]
    dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
    if dup:
        bad.append(f"[#20] 收束摘要标题重复：{dup}")
    secs = re.findall(r"^v(1\\.21\\.\\d+) 相对", doc, re.M)
    ver = [tuple(int(x) for x in v.split(".")) for v in secs]
    if not ver:
        bad.append("[#20] 一个版本段标题都没找到 —— 判据前提不成立")
    else:
        if len(secs) != len(set(secs)):
            bad.append(f"[#20] 版本段有重复：{secs}")
        for k in range(len(ver) - 1):
            if ver[k] <= ver[k + 1]:
                bad.append(f"[#20] 段序不是严格递减：{secs[k]} → {secs[k + 1]}")
                break
    if "_v72_engine_src" and not doc:
        bad.append("[#20] docstring 为空")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #20] {m}")
        return False
    print(f"  \\u2713 [v72 #20] {len(secs)} 个版本段严格递减、"
          f"{len(sums)} 个收束摘要标题无重复（首段 v{secs[0]}）")
    return True
'''

NEW_HYG = '''def _changelog_text() -> str:
    """changelog 正文。★ v1.23.7 起它在仓库根目录 `CHANGELOG.md`，不在代码里。"""
    p = HERE / "CHANGELOG.md"
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").replace("\\r\\n", "\\n")


def _changelog_lint(doc: str):
    """纯函数：返回（版本段标题, 收束摘要标题, 重复的收束摘要标题）。

    ★ 抽成纯函数是为了让**负对照可以喂合成坏样本** —— changelog 搬到外部文件后，
    「把 SRC 指回旧版」的旧负对照手法失效（取源不再是被测文件），
    没有新负对照的「全绿」只说明判据没跑。
    """
    sums = [ln.strip() for ln in doc.split("\\n")
            if "★ v1.2" in ln and "收束摘要" in ln]
    dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
    secs = re.findall(r"^v(1\\.2\\d(?:\\.\\d+)?) 相对", doc, re.M)
    return secs, sums, dup


def check_v72_changelog_hygiene():
    """[v1.21.72 #20 起；v1.23.7 改取源] changelog 不得有重复的「★ vX 收束摘要」
    段，版本段序必须按版本号**严格递减**。

    ★ v1.23.7：changelog 从模块 docstring 搬到了 `CHANGELOG.md` ⇒ 本判据的**取源**
      跟着改。**判据意图一字未改**（是位置变了，不是放宽）。
    ★ 判别力（负对照）：喂一份**合成坏样本**（重复的收束标题 + 段序 71→68→69），
      同一个 `_changelog_lint` 必须报出重复、且段序必须被判为**非**严格递减。
    """
    bad = []
    doc = _changelog_text()
    if not doc:
        bad.append("[#20] CHANGELOG.md 不存在或为空 —— 判据前提不成立")
        secs, sums = [], []
    else:
        secs, sums, dup = _changelog_lint(doc)
        if dup:
            bad.append(f"[#20] 收束摘要标题重复：{dup}")
        if not secs:
            bad.append("[#20] 一个版本段标题都没找到 —— 判据前提不成立")
        else:
            if len(secs) != len(set(secs)):
                bad.append(f"[#20] 版本段有重复：{secs}")
            ver = [tuple(int(x) for x in s.split(".")) for s in secs]
            for k in range(len(ver) - 1):
                if ver[k] <= ver[k + 1]:
                    bad.append(f"[#20] 段序不是严格递减：{secs[k]} → {secs[k + 1]}")
                    break
    # ---- 负对照：合成坏样本必须被判出来 ----
    _bad = ("v1.21.71 相对 v1.21.70\\n★ v1.21.63 收束摘要\\n"
            "v1.21.68 相对 v1.21.67\\n★ v1.21.63 收束摘要\\n"
            "v1.21.69 相对 v1.21.68\\n")
    _s, _sm, _d = _changelog_lint(_bad)
    _desc = all(tuple(int(x) for x in _s[k].split("."))
                > tuple(int(x) for x in _s[k + 1].split("."))
                for k in range(len(_s) - 1)) if len(_s) > 1 else True
    if not _d or _desc:
        bad.append("[#20] ★ 负对照失效：合成坏样本没被检出（重复=%r 递减=%r）"
                   % (bool(_d), _desc))
    if bad:
        for m in bad:
            print(f"  \\u2717 [v72 #20] {m}")
        return False
    print(f"  \\u2713 [v72 #20] CHANGELOG.md：{len(secs)} 个版本段严格递减、"
          f"{len(sums)} 个收束摘要标题无重复（首段 v{secs[0]}）；负对照判红")
    return True
'''


NEW_CHECK = '''def check_v1237_changelog_outside_code():
    """[v1.23.7] changelog 不得再写在代码文件里。

    抠掉模块 docstring 后的源码里：① 不得有版本段标题 `^vX.Y.Z 相对`；
    ② 不得出现「收束摘要」。
    **两向对账**：`CHANGELOG.md` 必须存在且版本段 ≥ 10（防「搬出去」变「删掉」）。
    ★ 变异体见 `_probe_v1237_mutants.py`（往源码注入一段版本段必须判红）。
    """
    bad = []
    raw = SRC.read_bytes().decode("utf-8").replace("\\r\\n", "\\n")
    i = raw.index('"""')
    j = raw.index('"""', i + 3)
    body = raw[j + 3:]
    assert 0 < len(body) < len(raw), "抠模块 docstring 没生效（抠法自证失败）"
    hits = [k + 1 for k, ln in enumerate(body.split("\\n"))
            if re.match(r"^v1\\.2\\d(?:\\.\\d+)? 相对", ln)]
    if hits:
        bad.append("代码里仍有版本段标题 %d 处，前 3 个行号 %s" % (len(hits), hits[:3]))
    if "收束摘要" in body:
        bad.append("代码里仍出现「收束摘要」")
    cl = _changelog_text()
    n = len(re.findall(r"^v1\\.2\\d(?:\\.\\d+)? 相对", cl, re.M))
    if n < 10:
        bad.append("CHANGELOG.md 版本段只有 %d 段 —— 像被删而不是被搬" % n)
    if bad:
        for m in bad:
            print("  \\u2717 [v1237] %s" % m)
        return False
    print("  \\u2713 [v1237] 代码里 0 处版本段 / 0 处收束摘要；"
          "CHANGELOG.md %d 段（两向对账）" % n)
    return True

'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.7.py"', s, count=1)

    if "def _changelog_text" in s:
        print("[skip] 取源函数已存在")
    else:
        assert s.count(OLD_HYG) == 1, "旧 hygiene 函数命中 %d 次" % s.count(OLD_HYG)
        s = s.replace(OLD_HYG, NEW_HYG, 1)
        print("已替换 check_v72_changelog_hygiene（取源 → CHANGELOG.md，含负对照）")

    if "raw = _changelog_text()" in s:
        print("[skip] v76 取源已改")
    else:
        old = "    raw = _v76_src()\n"
        assert s.count(old) == 1, "`raw = _v76_src()` 命中 %d 次" % s.count(old)
        s = s.replace(old, "    raw = _changelog_text()   # v1.23.7：changelog 已搬到 CHANGELOG.md\n", 1)
        print("已改 check_v76_changelog_wording 取源")

    if "def check_v1237_changelog_outside_code" in s:
        print("[skip] v1237 判据已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + NEW_CHECK + s[k:]
        print("已插入 check_v1237_changelog_outside_code")

    if "if not check_v1237_changelog_outside_code():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 94, "守卫只有 %d 条（基线 94）" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v1237_changelog_outside_code():\n        return 1\n" + s[pos:]
        n_after = len(GUARD_RE.findall(s))
        assert n_after == n_before + 1, "守卫 %d -> %d" % (n_before, n_after)
        print("守卫 %d -> %d" % (n_before, n_after))

    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)
    c = SK.read_bytes()
    ast.parse(c.decode("utf-8").replace("\r\n", "\n"))
    print("smoke_test.py：%d 字节 / %d 行 / CRLF=%d 裸LF=%d CRCRLF=%d；ast OK"
          % (len(c), c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
