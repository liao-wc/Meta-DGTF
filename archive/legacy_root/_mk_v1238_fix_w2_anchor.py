# -*- coding: utf-8 -*-
"""v1.23.8 顺手修：`_probe_v123_w2.py` 的 M3 变异体锚点过时。

v1.23.6 清掉代码正文里的版次批注后，M3 的锚点（含两行 `# [v1.23.0 W2] ...`
注释）在当前主文件里命中 0 次 ⇒ `--phase all` 长期带一条假红
（`C.M3 变异体可构造　锚点命中 0 次（应 2）`）。
这是**判据过时**，不是机制没了 —— 按项目纪律「判据随实现更新」把锚点改到新语义，
**变异意图一字未改**（仍然是「抠掉 prompt 里的摘要注入」）。
"""
from pathlib import Path

p = Path(__file__).resolve().parent / "_probe_v123_w2.py"
raw = p.read_bytes()
crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = (
    '    "M3 抠掉 prompt 里的摘要注入": (\n'
    "        '                # [v1.23.0 W2] 外部检索摘要（**参照**）。未开联网时\\n'\n"
    "        '                #   它是空串 ⇒ prompt 逐字不变（加性）。\\n'\n"
    "        '                + (getattr(self, \"_web_digest\", \"\") or \"\"))\\n',\n"
)
NEW = (
    "    # ★ [v1.23.8] 锚点去掉两行注释 —— v1.23.6 清掉代码正文的版次批注后，\n"
    "    #   含注释的锚点命中 0 次（判据过时，不是机制没了）。变异意图一字未改。\n"
    '    "M3 抠掉 prompt 里的摘要注入": (\n'
    "        '                + (getattr(self, \"_web_digest\", \"\") or \"\"))\\n',\n"
)

n = s.count(OLD)
assert n == 1, f"旧锚点块命中 {n} 次（要求 1）"
s = s.replace(OLD, NEW, 1)
out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
assert out.count(b"\r\r\n") == 0
p.write_bytes(out)

import ast  # noqa: E402
ast.parse(out.decode("utf-8").replace("\r\n", "\n"))
print(f"OK：{p.name}（CRLF={crlf}）M3 锚点已去掉注释行")
