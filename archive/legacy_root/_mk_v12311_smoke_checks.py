#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.11：smoke_test.py 接线。
  1) SRC → 元DGTF-V1.23.11.py
  2) 新增 `check_v12311_writeback_and_web`（自省回写 + 事实题自动联网，自带负对照）
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
BAK = HERE / "_bak_smoke_test.pre_v12311"
END_MARK = "# <<<end v123 checks>>>"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
GUARD_RE = re.compile(r'^    if not check_[A-Za-z0-9_]+\(\):\n        return 1\n', re.M)

NEW_CHECK = '''def check_v12311_writeback_and_web():
    """[v1.23.11] 两件挂账一次做完：自省回写（R1 后半）+ 事实题自动联网（R10 后半）。

    ★ 负对照全部内置：
      · 自省回写：**无**高置信诊断时不许渲染（防「无条件加一段动作」）；
        `unsaid_is_escape=True` 与 `quality_flags=unsaid_overused(n)` 各测一次；
        回写块必须落在形态声明**之后**（顺序：模板声明 → 诊断动作）。
      · 事实题自动联网：`_web_auto_for_facts` 事实题 True / 决策题 False；
        源码里必须真接线（`_web_auto_for_facts(" ".join(args.question))` 与
        `"web": _web` 都在）——否则是死代码。
    """
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \\u2717 [v12311] 命名空间里没有 mod")
        return False

    _base = {"orientation": "decision",
             "_config": {"actions": {"landing_decision": True}},
             "decidability": {}, "question": "这份方案怎么落地"}

    # ── A 自省回写 ────────────────────────────────────────────
    _clean = dict(_base, views={"all": {"self_check": {"unsaid_is_escape": False},
                                        "quality_flags": []}})
    if "**自省回写**" in m.render_landing(_clean):
        bad.append("无高置信诊断时不该渲染「自省回写」")

    _esc = dict(_base, views={"all": {"self_check": {
        "unsaid_is_escape": True, "unsaid_where": "用未生收尾"},
        "quality_flags": []}})
    _t1 = m.render_landing(_esc)
    if "**自省回写**" not in _t1:
        bad.append("unsaid_is_escape=True 时该渲染「自省回写」")
    if "⇒ 动作" not in _t1:
        bad.append("「自省回写」里没有可执行动作")

    _flag = dict(_base, views={"all": {"self_check": {},
                                       "quality_flags": ["unsaid_overused(8)"]}})
    if "**自省回写**" not in m.render_landing(_flag):
        bad.append("quality_flags=unsaid_overused(n) 时该渲染「自省回写」")
    _hard = dict(_base, views={"1": {"self_check": {},
                                     "quality_flags": ["action_incomplete"]}})
    if "**自省回写**" not in m.render_landing(_hard):
        bad.append("action_incomplete 时该渲染「自省回写」")

    # 顺序：模板声明在前、诊断动作在后
    if "**形态声明**" in _t1 and "**自省回写**" in _t1:
        if _t1.index("**形态声明**") > _t1.index("**自省回写**"):
            bad.append("「自省回写」跑到「形态声明」前面了（顺序反了）")

    # ── B 事实题自动联网 ──────────────────────────────────────
    if not hasattr(m, "_web_auto_for_facts"):
        bad.append("缺 _web_auto_for_facts")
    else:
        if not m._web_auto_for_facts("新中国的成立时间是什么时候"):
            bad.append("事实题应自动接入外部校验")
        if m._web_auto_for_facts("这份方案怎么落地"):
            bad.append("决策题不该自动接入外部校验")
    _src = SRC.read_text(encoding="utf-8")
    if '_web_auto_for_facts(" ".join(args.question))' not in _src:
        bad.append("main 里没调 _web_auto_for_facts（死代码）")
    if '"web": _web' not in _src:
        bad.append("main 里没把 _web 交给 _apply_runtime（接线断了）")

    if bad:
        for _m in bad:
            print("  \\u2717 [v12311] %s" % _m)
        return False
    print("  \\u2713 [v12311] 自省回写(逃避/质量线索/硬约束 三触发 + 无诊断不渲染 + 顺序) / "
          "事实题自动联网(事实 True·决策 False + 源码接线在)")
    return True


'''


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = len(SRC_RE.findall(s))
    assert n == 1, "SRC 行命中 %d 次" % n
    s = SRC_RE.sub('SRC = HERE / "元DGTF-V1.23.11.py"', s, count=1)
    print("SRC → 元DGTF-V1.23.11.py")

    if "def check_v12311_writeback_and_web" in s:
        print("[skip] v12311 判据已存在")
    else:
        k = s.rindex(END_MARK)
        s = s[:k] + NEW_CHECK + s[k:]
        print("已插入 check_v12311_writeback_and_web")

    if "if not check_v12311_writeback_and_web():" in s:
        print("[skip] 守卫已存在")
    else:
        hits = list(GUARD_RE.finditer(s))
        n_before = len(hits)
        assert n_before >= 98, "守卫只有 %d 条（基线 98）" % n_before
        pos = hits[-1].end()
        s = s[:pos] + "    if not check_v12311_writeback_and_web():\n        return 1\n" + s[pos:]
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
    print("smoke_test.py：%d 字节 / %d 行；ast OK" % (len(c), c.count(b"\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
