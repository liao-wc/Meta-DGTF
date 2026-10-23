# -*- coding: utf-8 -*-
"""修 v1.23.63 判据：必须调 `LLM._real_call`（`LLM.call` 在 smoke 里已被换成桩）。

★ 第二次踩同一个坑（第一次在故障注入 v1 里）：**整体替换/调用外层包装
  = 把被测对象一起换掉**。smoke 第 265 行把 `mod.LLM.call` 换成了 `fake_call`，
  所以在判据里调 `.call(...)` 拿到的是桩的 `{}`，而不是真实现。
  smoke 已把真方法存在 `mod.LLM._real_call`，判据必须用它。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

PAIRS = [
    ('        _out = _l.call("sys", "usr", json_mode=True)',
     '        _out = mod.LLM._real_call(_l, "sys", "usr", json_mode=True)'),
    ('        _l2.call("sys", "usr", json_mode=True)',
     '        mod.LLM._real_call(_l2, "sys", "usr", json_mode=True)'),
    ('        _l3.call("sys", "usr", json_mode=False)',
     '        mod.LLM._real_call(_l3, "sys", "usr", json_mode=False)'),
    ('        _l4.call("sys", "usr", json_mode=True)',
     '        mod.LLM._real_call(_l4, "sys", "usr", json_mode=True)'),
    ('            _l5.call("sys", "usr")',
     '            mod.LLM._real_call(_l5, "sys", "usr")'),
]
for old, new in PAIRS:
    assert s.count(old) == 1, "锚点命中 %d 次：%s" % (s.count(old), old[:40])
    s = s.replace(old, new)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已改 5 处调用为 _real_call")
