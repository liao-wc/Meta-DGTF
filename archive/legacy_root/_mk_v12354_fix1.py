# -*- coding: utf-8 -*-
"""v1.23.54：更新 `check_v12350_resume` 里那条「非 serial 必须拒绝」的负对照。

★ 判据随实现更新（不是放宽）：v1.23.54 起并行快照**允许续**（剩余层降级按
  serial 跑、产物记 `resumed_serial`）。旧断言 `mode=B ⇒ 必须拒绝且给理由`
  因此**必然红** —— 它编码的是旧语义。改法是把断言对准新语义：
      `mode=B ⇒ ok=True` 且 `src_mode` 记下了源模式。
  「题面不同 ⇒ 拒绝」那条不受影响，保留。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what):
    global s
    c = s.count(old)
    assert c == 1, "%s：命中 %d 次" % (what, c)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


rep('    ★ 负对照两条（判据要有牙）：题面不同 ⇒ **拒绝续跑**；模式非 serial ⇒ **拒绝**。',
    '    ★ 负对照：题面不同 ⇒ **拒绝续跑**（这条不变）。\n'
    '    ★ 非 serial 从 v1.23.54 起**允许**（剩余层降级按 serial 跑、产物记\n'
    '      `resumed_serial`）⇒ 原来的「mode=B 必须拒绝」改成「允许 + 记源模式」。',
    "docstring 负对照说明")

rep('        _rs_b = mod.load_resume_snapshot(str(_p), question=_q, mode="B")\n'
    '        if _rs_b.get("ok") or not _rs_b.get("why"):\n'
    '            bad.append("[RS-负对照] mode=B 竟允许续跑 / 没给理由：%r" % (_rs_b,))\n',
    '        # ★ [判据随实现更新] 旧断言是「mode=B 必须拒绝」—— 它编码的是\n'
    '        #   「并行不支持续跑」的旧语义。本版起并行快照允许续（降级跑剩余层），\n'
    '        #   所以改成「允许 + 必须记下源模式」。\n'
    '        _rs_b = mod.load_resume_snapshot(str(_p), question=_q, mode="B")\n'
    '        if not _rs_b.get("ok"):\n'
    '            bad.append("[RS-对照] mode=B 应允许续跑（并行降级 serial）/ "\n'
    '                       "实际拒绝：%r" % (_rs_b.get("why"),))\n'
    '        elif str(_rs_b.get("src_mode") or "") != "serial":\n'
    '            bad.append("[RS-对照] 没记下快照源模式：%r"\n'
    '                       % (_rs_b.get("src_mode"),))\n',
    "mode=B 断言改成允许+记源模式")

rep('          "逐字复用 + 池还原 + 只跑缺层；负对照：题面不同/mode 非 serial 拒绝；"',
    '          "逐字复用 + 池还原 + 只跑缺层；负对照：题面不同拒绝 / mode=B 允许降级；"',
    "收尾文案")

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("smoke_test.py：%d → %d 行" % (n0, s.count("\n")))
