#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 变异体：证明 check_v1237_changelog_outside_code 有判别力。

做法同 `_probe_v1236_mutants.py`：读 smoke_test.py 原文，只替换 `SRC` 那一行指向
变异体文件，再 exec 成独立 module，让**原样的判据函数**去跑。

  M0 正对照：未改的 v1.23.7                                  → 必须绿
  M1 往代码里注入一个版本段标题 `v1.99.9 相对 v1.99.8`        → 必须红
  M2 往代码里注入一行 `# ★ v1.99.9 收束摘要`                  → 必须红
  M3 只在**模块 docstring** 里塞版本段（**不该**触发）         → 应仍绿
     —— 这一条是「判据确实抠掉了模块 docstring」的负对照
"""
import ast
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
S7 = HERE / "元DGTF-V1.23.7.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')


def load_judge(target: Path):
    txt = SMOKE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = len(SRC_RE.findall(txt))
    assert n == 1, "SRC 行命中 %d 次" % n
    txt = SRC_RE.sub(lambda m: 'SRC = Path(r"%s")' % str(target), txt, count=1)
    mod = types.ModuleType("mut")
    mod.__file__ = str(SMOKE)
    sys.modules["mut"] = mod
    exec(compile(txt, str(SMOKE), "exec"), mod.__dict__)
    return mod


def main():
    base = S7.read_bytes().decode("utf-8").replace("\r\n", "\n")
    i = base.index('"""')
    j = base.index('"""', i + 3)
    tmp = Path(tempfile.mkdtemp(prefix="_v1237mut_"))
    cases = [("M0 正对照（未改）", base, True)]

    # ★ 注入形态必须是**合法 Python**：版本段只能藏在三引号里（这正是「changelog
    #   藏在代码里」的真实形态）。行必须顶格，否则 `^vX.Y.Z 相对` 匹配不到。
    lines = base.split("\n")
    k = base[:j].count("\n")

    def _fn(name, inner):
        return ['def %s():' % name, '    """', inner, '"""', '    return None', '']

    m1 = "\n".join(lines[: k + 3] + _fn("_v1237_m1", "v1.99.9 相对 v1.99.8") + lines[k + 3:])
    cases.append(("M1 代码里插版本段标题", m1, False))

    m2 = "\n".join(lines[: k + 3] + _fn("_v1237_m2", "★ v1.99.9 收束摘要") + lines[k + 3:])
    cases.append(("M2 代码里插收束摘要", m2, False))

    # M3：只改模块 docstring（不该触发）
    m3 = base[:i + 3] + "\nv1.99.9 相对 v1.99.8\n★ v1.99.9 收束摘要\n" + base[i + 3:]
    cases.append(("M3 只在模块 docstring 里塞", m3, True))

    bad = 0
    for name, text, want_green in cases:
        p = tmp / (name.split()[0] + ".py")
        p.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        ast.parse(text)
        mod = load_judge(p)
        try:
            got = mod.check_v1237_changelog_outside_code()
        except Exception as e:
            got = "EXC:%s: %s" % (type(e).__name__, e)
        ok = (got is True) if want_green else (got is False)
        print("%-34s 期望 %-4s 实际 %-5s %s"
              % (name, "绿" if want_green else "红", got, "✓" if ok else "★ 不符"))
        if not ok:
            bad += 1
    print("\n变异体结果：%d 个不符（应 0）" % bad)
    print("临时目录：%s" % tmp)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
