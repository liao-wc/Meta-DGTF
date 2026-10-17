# -*- coding: utf-8 -*-
"""修正 `check_v12350_resume` 里那条**静态字面量**断言。

旧断言（v1.23.50 写的）：
    '"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),'
它把"快照带记账"钉在**一行源码的字面量**上。v1.23.56 把那行改成
`int(_base.get("calls") or 0) + _w_calls`（累计口径）⇒ 字面量失配 ⇒ 判据假红。

★ 处理方式：**登记式更新**（把断言改成新事实），不是删掉也不是放宽成子串匹配 ——
  这条 check 里本来就有**行为级**断言（快照 `llm_calls > 0` / `llm_tokens > 0`），
  静态那条只是顺带的指纹；留着它（更新后）能继续挡住"记账字段被删"。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = '                \'"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),\','
NEW = '                \'"llm_calls": int(_base.get("calls") or 0) + _w_calls,\','

assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已把 check_v12350_resume 的记账指纹更新为累计口径")
