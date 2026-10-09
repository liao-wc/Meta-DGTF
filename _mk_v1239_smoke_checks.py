#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.9：smoke_test.py 接线。
  1) SRC → 元DGTF-V1.23.9.py
  2) 新增 `check_v1239_orientation_guard`（取向分流守卫，自带负对照 + 接线断言）
  3) 在 main() 末尾接上守卫
幂等；smoke_test.py 必须保持纯 CRLF。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1239"
END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

NEW_CHECK = '''def check_v1239_orientation_guard():
    """[v1.23.9] 取向分流守卫：`auto` + 无决策语境 → boundary 模板。

    ★ 背景（真跑实证）：单点事实询问套 decision 模板，会替提问者编出一整套
      不存在的执行流程（行动清单 / 负责人 / 时限 / 验收）。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 事实题 auto → boundary；**决策题 auto → decision**（不许一刀切）；
      · **显式 `--orientation decision` 仍走 decision**（不许覆盖用户显式选择）；
      · `boundary` / 「关掉开关」两条老短路保持原样；
      · 空题面 / 缺 question 键 → boundary（不知道题面时不套决策模板）；
      · `_has_decision_context` 词表：3 例命中 + 3 例不命中；
      · 接线：`render_landing` 源码里真的调了它（防死代码）。
    """
    import inspect as _inspect
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \\u2717 [v1239] 命名空间里没有 mod")
        return False

    _FACT = "新中国的成立时间是什么时候"
    _DEC = "老城区暴雨内涝频发，排水系统重建还是局部修补，该不该统一规划"

    def _kind(orientation, question, landing_on=True, with_q=True):
        _r = {"orientation": orientation,
              "_config": {"actions": {"landing_decision": landing_on}},
              "views": {}, "decidability": {}}
        if with_q:
            _r["question"] = question
        return ("decision" if "落地层（decision 模式）" in m.render_landing(_r)
                else "boundary")

    _cases = [
        ("事实题 auto → boundary", _kind("auto", _FACT), "boundary"),
        ("决策题 auto → decision", _kind("auto", _DEC), "decision"),
        ("显式 decision + 事实题 → decision", _kind("decision", _FACT),
         "decision"),
        ("boundary + 决策题 → boundary", _kind("boundary", _DEC), "boundary"),
        ("空题面 auto → boundary", _kind("auto", ""), "boundary"),
        ("缺 question 键 auto → boundary",
         _kind("auto", "", with_q=False), "boundary"),
        ("关开关 + 决策题 → boundary", _kind("decision", _DEC, landing_on=False),
         "boundary"),
    ]
    for _name, _got, _want in _cases:
        if _got != _want:
            bad.append("%s：实测 %s（期望 %s）" % (_name, _got, _want))

    if not hasattr(m, "_has_decision_context"):
        bad.append("缺 _has_decision_context")
    else:
        for _q in ("新中国的成立时间是什么时候",
                   "1949年10月1日的开国大典有多少人参加",
                   "《共同纲领》是哪一年通过的"):
            if m._has_decision_context(_q):
                bad.append("负对照：事实题被判有决策语境：%r" % _q)
        for _q in ("这个方案怎么落地", "我要不要现在买", "三条路径的利弊取舍"):
            if not m._has_decision_context(_q):
                bad.append("决策题未被判有决策语境：%r" % _q)
        if m._has_decision_context(""):
            bad.append("空题面不该判为有决策语境")

    if "_has_decision_context(" not in _inspect.getsource(m.render_landing):
        bad.append("_has_decision_context 没被 render_landing 调用（死代码）")

    if bad:
        for _m in bad:
            print("  \\u2717 [v1239] %s" % _m)
        return False
    print("  \\u2713 [v1239] 取向分流：事实题→boundary / 决策题→decision / "
          "显式 decision 不被覆盖 / 空题面保守走 boundary；词表 3+3 例；接线在")
    return True


'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.9.py"', s, count=1)
    print("SRC → 元DGTF-V1.23.9.py")

    if "def check_v1239_orientation_guard" in s:
        print("[skip] v1239 判据已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + NEW_CHECK + s[k:]
        print("已插入 check_v1239_orientation_guard")

    if "if not check_v1239_orientation_guard():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 96, "守卫只有 %d 条（基线 96）" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v1239_orientation_guard():\n        return 1\n" + s[pos:]
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
    print("smoke_test.py：%d 字节 / %d 行；ast OK"
          % (len(c), c.count(b"\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
