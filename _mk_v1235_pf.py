# -*- coding: utf-8 -*-
"""v1.23.5 补丁 S7：pending_fix #1 已收口 → 登记表从 3 项改成 2 项。

★ 这是「两向对账」的另一半：代码改完了，登记表必须跟着改，否则
  `check_v122_phase5` 的 5.7（常量 == 源码 `# [AUDIT-122] 标 pending_fix：`
  条数）立刻翻红 —— 那条判据就是为这类漂移准备的。

计数口径（见 `_v122_verify.py` 5.7）：
    src.count("# [AUDIT-122] 标 pending_fix：") 必须 == _AUDIT122_PENDING_FIX
所以「已收口」的那条注释要**保留 `# [AUDIT-122]` 前缀**（仍可检索），
但把「标 pending_fix：」改成「v1.23.5 已收口」，它就退出计数了。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
DST = HERE / "元DGTF-V1.23.5.py"


def read_lf(p):
    b = p.read_bytes()
    s = b.decode("utf-8")
    assert b.count(b"\r\r\n") == 0
    assert s.count("\r\n") == s.count("\n"), "非纯 CRLF"
    return s.replace("\r\n", "\n")


def write_crlf(p, s):
    assert "\r" not in s
    b = s.replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)
    chk = p.read_bytes()
    assert chk.count(b"\r\n") == chk.count(b"\n")
    assert chk.count(b"\r\r\n") == 0


def rep1(s, old, new, tag):
    n = s.count(old)
    assert n == 1, "%s：命中 %d 次" % (tag, n)
    return s.replace(old, new)


s = read_lf(DST)

# ---- S7a 已收口的注释退出 pending 计数 ----
OLD_MARK = '''    # [AUDIT-122] 标 pending_fix：与模块级 `auto_plan()` 的**归一化规则**
    #   仍是两份（模式白名单 + 逐层圈数钳位 + 中位数补漏 + 低置信退 serial）。
    #   v1.22 先把「同一个函数」收口（本方法退薄壳），再谈合并归一化 ——
    #   后者要贯通 plan_orientation / plan_resources 的签名，属架构批。'''
NEW_MARK = '''    # [AUDIT-122] v1.23.5 **已收口**（原 pending_fix #1）：归一化抽成
    #   `_plan_conf` / `_normalize_plan_mode` / `_normalize_plan_rounds`
    #   三个**唯一实现**，三处调用点各留一行。
    #   ★ 实测重复面比文档记的更大：模式白名单 3 处、conf 解析 3 处、
    #     圈数归一化 2 处（文档只写了「两份」）。
    #   ★ 刻意保留的差异（低置信退 serial 时 reason 处不处置）由冒烟
    #     `check_v1235_pending_fix` 钉住 —— 是有意差异，不是漏合并。'''
if OLD_MARK in s:
    s = rep1(s, OLD_MARK, NEW_MARK, "S7a pending_fix #1 标记改已收口")
else:
    print("  [skip] S7a 已改")

# ---- S7b 常量 3 -> 2 ----
OLD_C = '''_AUDIT122_PENDING_FIX = 3
_AUDIT122_DUAL_IMPL = 2'''
NEW_C = '''# [v1.23.5] 3 -> 2：pending_fix #1（归一化两份）已收口，见上方注释。
_AUDIT122_PENDING_FIX = 2
_AUDIT122_DUAL_IMPL = 2'''
if "_AUDIT122_PENDING_FIX = 3" in s:
    s = rep1(s, OLD_C, NEW_C, "S7b 常量 3 -> 2")
else:
    print("  [skip] S7b 已改")

# ---- S7c docstring 里的「3 项」同步 ----
OLD_D = '''    · docs/机制审计-v122.md：## pending_fix 3 项（与源码 # [AUDIT-122]
      注释**两向对账**）+ ## 双实现清单 + ## resolved'''
NEW_D = '''    · docs/机制审计-v122.md：## pending_fix **2 项**（v1.23.5：#1 归一化
      已收口并移入 ## resolved；与源码 `# [AUDIT-122]` 注释**两向对账**）
      + ## 双实现清单 + ## resolved'''
if OLD_D in s:
    s = rep1(s, OLD_D, NEW_D, "S7c docstring 项数同步")
else:
    print("  [skip] S7c 已改")

write_crlf(DST, s)
ast.parse(s)
print("S7 完成")
_n = s.count("# [AUDIT-122] 标 pending_fix：")
_c = 2
print("  [自检] 源码 pending_fix 标记 %d 条，常量 %d → %s"
      % (_n, _c, "对得上" if _n == _c else "★ 对不上"))
