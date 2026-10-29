# -*- coding: utf-8 -*-
"""[V2.2.27] 引擎：route 依赖闭包（both⇒0/1，all⇒both/0/1）+ 版本。"""
from pathlib import Path
import py_compile

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.26.py"
DST = ENG / "Meta-DGTF-V2.2.27.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.26\n", "Meta-DGTF-道生三阶模型 · V2.2.27\n")
rep('__version__ = "2.2.26"', '__version__ = "2.2.27"')
rep("★ V2.2.26 补丁（route 子集感知动态成本模型；引擎侧零行为差）：",
"""★ V2.2.27 补丁（引擎侧 route 依赖闭包）：
      · 显式 --route 里出现 both 但缺 0/1、或 all 缺 both/0/1 时，自动补全依赖并告警；
      · 与 App 侧 route 安全门/依赖闭包同口径，防止直连 CLI 的依赖断链；
      · 未出现 both/all 的省层 route 不受影响（保持省层语义）。

★ V2.2.26 补丁（route 子集感知动态成本模型；引擎侧零行为差）：""")

# 1) 依赖表旁加闭包 helper（_ENTRY_DEPS 定义附近）
rep('''_ENTRY_DEPS = {"0": (), "1": (), "both": ("0", "1"), "all": ()}''',
'''_ENTRY_DEPS = {"0": (), "1": (), "both": ("0", "1"), "all": ()}
# ★ [V2.2.27] route 依赖闭包：both 需 0/1；all 需 both/0/1（顺序规范 0,1,both,all）
_ROUTE_ORDER = ("0", "1", "both", "all")
_ROUTE_CLOSURE_DEPS = {"both": ("0", "1"), "all": ("both", "0", "1")}


def _close_route_deps(route_list):
    """返回 (按顺序补全依赖后的 route, 新增条目)。纯函数，可单测。"""
    have = set(str(x) for x in (route_list or []) if str(x))
    added = []
    changed = True
    while changed:
        changed = False
        for entry in list(have):
            for dep in _ROUTE_CLOSURE_DEPS.get(entry, ()):
                if dep not in have:
                    have.add(dep)
                    added.append(dep)
                    changed = True
    ordered = [e for e in _ROUTE_ORDER if e in have]
    return ordered, added''')

# 2) main：route 解析后补依赖
rep('''    keep = {}
    if args.keep:''',
'''    # ★ [V2.2.27] 显式 route 的依赖闭包（both⇒0/1；all⇒both/0/1）
    _route_closed, _route_added = _close_route_deps(route)
    if _route_added:
        print(f"   · 层依赖闭包：补 {'、'.join(_route_added)}"
              "（both 需 0/1，all 需 both/0/1）")
        route = _route_closed
    keep = {}
    if args.keep:''')

out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))
