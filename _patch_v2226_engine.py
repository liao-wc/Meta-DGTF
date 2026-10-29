# -*- coding: utf-8 -*-
"""[V2.2.26] 引擎零行为差版本。"""
from pathlib import Path
import py_compile
ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.25.py"
DST = ENG / "Meta-DGTF-V2.2.26.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")
def rep(a, b):
    global t
    c = t.count(a); assert c == 1, (c, a[:50]); t = t.replace(a, b)
rep("Meta-DGTF-道生三阶模型 · V2.2.25\n", "Meta-DGTF-道生三阶模型 · V2.2.26\n")
rep('__version__ = "2.2.25"', '__version__ = "2.2.26"')
rep("★ V2.2.25 补丁（动态配置细化：多圈档候选 + 缓存命中感知；引擎侧零行为差）：",
"""★ V2.2.26 补丁（route 子集感知动态成本模型；引擎侧零行为差）：
      本版为 App 发版：dynamic_config 的成本估算改为 层子集 × 圈数 的可加模型，
      用 3 臂有界云实测校准（docs/dynamic_cost_calibration_20261029.json）。

★ V2.2.25 补丁（动态配置细化：多圈档候选 + 缓存命中感知；引擎侧零行为差）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))
