#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留1] 三票 id 归一化探针（改前/改后同一支；含变异体）。

判据：
  A1 纯函数：1 起原样 / 0 起 +1 / 越界 None / 空 None / 混合 None
  A2 生产接线：两条路径体内都出现 `_normalize_judgment_ids(`
  B1 ★ 端到端：第 2 票返回 **0 起** id ⇒ 归一后**逐条**拿到该票本该给的标签
  B2 负对照：第 2 票返回 1 起 ⇒ 结果与 B1 的归一后**逐条相同**
  B3 ★ 越界票 ⇒ **弃票**（只剩另外两票）+ 留痕；可用票数不含它
  C1 变异体：把「0 起 +1」分支抠掉 ⇒ B1 必须判红

★ 桩必须给**逐票不同**的标签（`LABELS[(j+v)%3]`）：三票同标签时，
  错位与否**看不出来**（第一版就因此把「修好了」验成了「没修」）。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.3.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
_txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")

LABELS = ("decidable", "partial", "undecidable")
_P = _F = 0


def ck(name, ok, detail=""):
    global _P, _F
    if ok:
        _P += 1
        print("  ✓ " + name)
    else:
        _F += 1
        print("  ✗ " + name + ("   " + detail if detail else ""))


def load(p, name):
    spec = importlib.util.spec_from_file_location(name, str(p))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC, "dgtf_voteids")

# ---------------------------------------------------------- 0 改前兼容门
# 跑改前版本（v1.23.2）时这些符号本来就不存在 —— 直接崩在中间会把
# 「改前读数」变成一条 traceback。缺一个就整篇报红退出，读数可记录。
if not hasattr(mod, "_normalize_judgment_ids"):
    ck("A0 兼容门：`_normalize_judgment_ids` 存在（改前版本不存在 → 整篇判红）",
       False, "改前版本：id 归一化尚未实现")
    for _n2 in ("A1 纯函数", "A2 生产接线", "B1/B2/B3 端到端", "C1 变异体"):
        ck("（跳过）" + _n2, False, "前置符号缺失")
    print("\nPASS %d / FAIL %d" % (_P, _F))
    sys.exit(1)

print("── A 纯函数 ──")
f = mod._normalize_judgment_ids
ck("A1.a 1 起原样",
   f({1: "a", 2: "b", 3: "c"}, 3) == ({1: "a", 2: "b", 3: "c"}, "1起"),
   repr(f({1: "a"}, 3)))
ck("A1.b 0 起整体 +1",
   f({0: "a", 1: "b", 2: "c"}, 3) == ({1: "a", 2: "b", 3: "c"}, "0起+1"),
   repr(f({0: "a"}, 3)))
ck("A1.c 越界 → None", f({1: "a", 9: "b"}, 3)[0] is None,
   repr(f({1: "a", 9: "b"}, 3)))
ck("A1.d 空 → None", f({}, 3)[0] is None, repr(f({}, 3)))
ck("A1.e 混合（0 与 n 同时出现）→ None",
   f({0: "a", 3: "b"}, 3)[0] is None, repr(f({0: "a", 3: "b"}, 3)))

print("── A2 生产接线 ──")


def _body(name):
    for n in ast.walk(ast.parse(_txt)):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return "\n".join(_txt.split("\n")[n.lineno - 1:n.end_lineno])
    return ""


for fn in ("_adjudicate_sub_tristate_multi", "_adjudicate_sub_tristate"):
    ck("A2 %s 体里有 `_normalize_judgment_ids(`" % fn,
       "_normalize_judgment_ids(" in _body(fn), "")


class _Stub:
    """桩 llm：逐票标签不同（`LABELS[(j+v)%3]`）—— 否则错位看不出来。"""

    def __init__(self, shift=None, bad=None, n=3):
        self.i = -1
        self.shift = shift
        self.bad = bad
        self.n = n

    def call(self, sysp, user, t, mx, json_mode=False, stage=None, **k):
        self.i += 1
        base = 0 if self.i == self.shift else 1
        if self.i == self.bad:
            base = 50
        return json.dumps({"judgments": [
            {"id": base + j, "reason": "r",
             "decidability": LABELS[(j + self.i) % 3]}
            for j in range(self.n)]})

    def parse_json(self, raw):
        return json.loads(raw)


def _run(stub, n=3):
    o = object.__new__(mod.MetaDGTF)
    o.llm = stub
    o.config = dict(mod.DEFAULT_CONFIG)
    o.config["actions"] = dict(o.config["actions"])
    o.config["actions"]["tri_multi_vote"] = True
    o.pools = {"1": mod.Pool()}
    o.vp = lambda *a, **k: None
    o._web_gate = None
    subs = [{"id": i + 1, "question": "q%d" % (i + 1),
             "decidability": "partial"} for i in range(n)]
    o._adjudicate_sub_tristate_multi(subs, "Q")
    return o, subs


def _labels(subs):
    """每条子问题的 `[[voter, label], ...]`，按 voter 排序。"""
    return [[(v["voter"], v["label"]) for v in sorted(
        (s.get("votes") or []), key=lambda x: x["voter"])] for s in subs]


print("── B 端到端 ──")
_o1, _s1 = _run(_Stub(shift=1))          # 第 2 票（index 1）返回 0 起
_want = [[(v, LABELS[(j + v) % 3]) for v in (0, 1, 2)] for j in range(3)]
_got = _labels(_s1)
ck("B1 ★ 0 起票被 +1 归一：**逐票逐条**都拿到该票本该给的标签",
   _got == _want, repr(_got))
ck("B1.b ★ 三票齐（0 起票错位时，第 1 条会退化成「少一票」）",
   all(len(x) == 3 for x in _got), repr([len(x) for x in _got]))
ck("B1.c 池级留痕写明「id 0 起→+1 归一」",
   any(("0 起→+1" in str(x)) for x in _o1.pools["1"].meta),
   repr(_o1.pools["1"].meta[-2:]))

_o2, _s2 = _run(_Stub(shift=None))       # 三票都 1 起（负对照）
ck("B2 负对照：正常票（1 起）结果与 B1 的归一后**逐条相同**",
   _labels(_s2) == _want, repr(_labels(_s2)))
ck("B2.b 负对照：正常票**不留** id 异常痕（加性）",
   not any(("id 0 起" in str(x) or "越界" in str(x))
           for x in _o2.pools["1"].meta), repr(_o2.pools["1"].meta))

_o3, _s3 = _run(_Stub(bad=1))            # 第 2 票 id 越界
_g3 = _labels(_s3)
ck("B3 ★ 越界票**弃票**（不是硬塞）：每条只剩**另外两票**，且标签对得上",
   _g3 == [[(0, LABELS[j % 3]), (2, LABELS[(j + 2) % 3])] for j in range(3)],
   repr(_g3))
ck("B3.b 越界留痕写明「id 越界弃票」",
   any(("越界弃票" in str(x)) for x in _o3.pools["1"].meta),
   repr(_o3.pools["1"].meta[-2:]))
ck("B3.c 可用票数已扣掉弃票（不印「3/3」）",
   any(("2/3" in str(x)) for x in _o3.pools["1"].meta),
   repr(_o3.pools["1"].meta[-2:]))

print("── C 变异体 ──")
_td = Path(tempfile.mkdtemp())
_MUT = (
    ("C1 ★ 抠掉「0 起 +1」分支 → B1 必须判红",
     '    if _ks <= set(range(0, _hi)):\n'
     '        return {int(k) + 1: v for k, v in judged.items()}, "0起+1"',
     '    if False:\n'
     '        return {int(k) + 1: v for k, v in judged.items()}, "0起+1"'),
)
for _nm, _o, _n in _MUT:
    if _txt.count(_o) != 1:
        ck(_nm, False, "锚点命中 %d 次" % _txt.count(_o))
        continue
    _mp = _td / "mut_voteids.py"
    _mp.write_bytes(_txt.replace(_o, _n).replace("\n", "\r\n").encode("utf-8"))
    try:
        _mm = load(_mp, "mut_voteids")
        _mo = object.__new__(_mm.MetaDGTF)
        _mo.llm = _Stub(shift=1)
        _mo.config = dict(_mm.DEFAULT_CONFIG)
        _mo.config["actions"] = dict(_mo.config["actions"])
        _mo.config["actions"]["tri_multi_vote"] = True
        _mo.pools = {"1": _mm.Pool()}
        _mo.vp = lambda *a, **k: None
        _mo._web_gate = None
        _ms = [{"id": i + 1, "question": "q", "decidability": "partial"}
               for i in range(3)]
        _mo._adjudicate_sub_tristate_multi(_ms, "Q")
        ck(_nm, _labels(_ms) != _want, "变异体下结果竟与 B1 相同")
    except Exception:  # noqa: BLE001
        ck(_nm, True, "")

print("\nPASS %d / FAIL %d" % (_P, _F))
sys.exit(0 if _F == 0 else 1)
