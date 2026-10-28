# -*- coding: utf-8 -*-
"""[V2.2.18] 项目流程门 + 证据出口：从 V2.2.17 生成引擎版本（零行为差）。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.17.py"
DST = ENG / "Meta-DGTF-V2.2.18.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = [
    ("Meta-DGTF-道生三阶模型 · V2.2.17\n", "Meta-DGTF-道生三阶模型 · V2.2.18\n"),
    ('__version__ = "2.2.17"', '__version__ = "2.2.18"'),
    ("★ V2.2.17 补丁（本地 prompt 瘦身：行去重 + 噪声块截断 + 尾部保护）：",
     "★ V2.2.18 补丁（项目流程门；引擎侧零行为差）：\n"
     "     把「发版流程」本身变成可复跑的门：scripts/release_process_check.py 校验\n"
     "     引擎/App/配置/文档/标签/证据新鲜度/README 数字一致性；fast_gate、\n"
     "     run_v2_tests、final_acceptance、app_selftest_gate 各自写 latest 证据 JSON\n"
     "     （docs/*_latest.json，release_process_check 逐项核对）。\n"
     "     引擎源码除 __version__/docstring 外与 V2.2.17 逐字相同（可 diff 复核）。\n"
     "\n"
     "★ V2.2.17 补丁（本地 prompt 瘦身：行去重 + 噪声块截断 + 尾部保护）："),
]
for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次" % (i, n)
    text = text.replace(old, new)
out = text.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk))
