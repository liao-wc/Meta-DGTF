# -*- coding: utf-8 -*-
"""回填 `<<MUT>>` 占位 → 变异体终值（98 判红 / 98）。

字节级替换：只动 token 自身，**不碰任何换行**（四个文件里 CHANGELOG.md 是
CRLF、其余 LF —— 都原样保持）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
jobs = [
    ("v12349_报告.md", "**<<MUT>>**",
     "**98 判红 / 98**（+M100；三片 1-33 / 34-65 / 66-98）"),
    ("CHANGELOG.md", "<<MUT>>", "98 判红 / 98"),
    ("_方案_v12342_成本与闭环优化.md", "<<MUT>>", "98/98"),
    ("_commitmsg_v12349.txt", "<<MUT>>", "98 判红 / 98"),
]
for f, old, new in jobs:
    p = HERE / f
    b = p.read_bytes()
    before = (b.count(b"\r\n"), b.count(b"\n"))
    old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
    c = b.count(old_b)
    print("%-36s 命中 %d" % (f, c))
    assert c == 1, "占位符命中数不对：%s" % f
    b = b.replace(old_b, new_b, 1)
    assert b.count(b"<<MUT>>") == 0, "还有残留占位符：%s" % f
    after = (b.count(b"\r\n"), b.count(b"\n"))
    assert before == after, "换行数被改动：%s" % f
    p.write_bytes(b)
print("OK：四处占位已回填。")
