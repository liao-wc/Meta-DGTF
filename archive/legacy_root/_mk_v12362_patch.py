# -*- coding: utf-8 -*-
"""v1.23.61 → v1.23.62：把 `contra`（反向证据）**接活**。

问题（死代码审计发现）：
  · `contra` 字段**唯一的写入点**在 `eml_note_contra()` 里；
  · 而 `eml_note_contra()` **全项目没人调用**（AST 审计：名字全文只出现 1 次）；
  · 于是 `contra` **恒为 0** ⇒ `eml_promote()` 里那条
      `if int(e.get("contra", 0)) >= int(promote_n): continue`
    **永远不触发** —— 判据写着"反向证据够了不许升级"，可反向证据从不累积。
  · `_eml_note_use()` 的负面分支只降 `weight`，不记 `contra`。

修法（**只在负面分支补一行调用**，不新增机制）：
  用了但本跑读数不达标 ⇒ 除了降 weight，再记一次 contra。
  这样 `contra` 才有来源，晋升闸才是活的。

★ 行为变化要说清：`playbook.mode` 默认是 shadow/off ⇒ 默认路径**零影响**；
  打开 EML 时，一个被反复证明"用了没用"的条目，会在 3 次负面后**不再被升级**。
  这正是 `eml_promote` 文档里写的语义（"反向证据够 ⇒ 降级"）。
★ 无新配置键。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.61.py"
DST = HERE / "元DGTF-V1.23.62.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


# ── 1) 负面分支补记 contra ─────────────────────────────────────────
rep('''            else:
                _e["weight"] = max(0.1, float(_e.get("weight", 1.0) or 1.0)
                                   - 0.05)
                _n_neg += 1''',
    '''            else:
                _e["weight"] = max(0.1, float(_e.get("weight", 1.0) or 1.0)
                                   - 0.05)
                # ★ [反向证据接活] 用了但本跑读数不达标 ⇒ 记一次 `contra`。
                #   原来这里只降 weight，而 `contra` **唯一的写入点**
                #   `eml_note_contra()` 全项目没人调 ⇒ `contra` 恒 0
                #   ⇒ `eml_promote` 里「反向证据够了不许升级」那条**永远不触发**
                #   （判据在、输入没人产出 —— 与"读数无出口"是同一类死法）。
                try:
                    eml_note_contra([_e], [_e], why="used_but_duty_low")
                except Exception:
                    pass
                _n_neg += 1''',
    "负面分支记 contra")

# ── 2) 版本号 ──────────────────────────────────────────────────────
rep("元 DGTF · v1.23.61\n", "元 DGTF · v1.23.62\n", "docstring 标题")
rep('__version__ = "1.23.61"\n', '__version__ = "1.23.62"\n', "__version__")

ast.parse(s)
assert s.count('eml_note_contra([_e], [_e], why="used_but_duty_low")') == 1
# 这次审计要变成 0：名字不再只出现 1 次
print("  [OK] 结构性自检：负面分支已调用 eml_note_contra")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
