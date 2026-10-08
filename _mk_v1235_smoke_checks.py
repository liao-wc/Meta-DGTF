# -*- coding: utf-8 -*-
"""v1.23.5 冒烟判据注入器：把 check_v1235_pending_fix 接进 smoke_test.py。

做四件事：
  1. 在 `# <<<end v123 checks>>>` 之前插入判据函数块（幂等）。
  2. `SRC` 改指 `元DGTF-V1.23.5.py`（不改就是全套假绿）。
  3. 在**最后一个** check_v123* 守卫之后插自己的守卫（不动别人的守卫）。
  4. 把新守卫名补进 `_mk_v1230_smoke_checks.py` 的 GUARD_BLOCK ——
     那个生成器会 `GUARD_RE.sub("")` 通删再重插，不补进去下次一跑就没了
     （skill §v1.23.2 #9：改别档判据要改那一档的注入器）。

纪律：smoke_test.py 是纯 CRLF → read_bytes / write_bytes + 双向断言；
注入前 `ast.parse` 自检生成物。
"""
import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
GEN1230 = HERE / "_mk_v1230_smoke_checks.py"
TARGET = "元DGTF-V1.23.5.py"
MARK = "# <<<end v123 checks>>>"

CHECKS = '''
def check_v1235_pending_fix():
    \'\'\'[v1.23.5] 三条 pending_fix 的可证伪判据（含归一化唯一实现）。

    #1（本版已收口）调度归一化
       · 唯一实现：_plan_conf / _normalize_plan_mode / _normalize_plan_rounds
         各只有 1 处 def
       · 接线：三处调用点都还在（不是死代码）
       · 行为：同一份 mock 喂「两段式」与「单调用」，mode/rounds 逐字相同
       · ★ 钉住**刻意保留**的差异：低置信时两段式 reason 不动、
         另两处 reason 被改写（这是有意差异，不是漏合并）
    #2（仍未删）单票实现仍在 + 登记表仍是 2 项（两向对账）
    #3（可观测化）布尔兼容走一次必留痕 warning；字符串档不留痕
    \'\'\'
    import ast as _ast
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    _i = src.index(chr(34) * 3)
    _j = src.index(chr(34) * 3, _i + 3)
    body = src[_j + 3:]
    tree = _ast.parse(src)

    def _defs(name):
        return sum(1 for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == name)

    def _calls(name):
        return sum(1 for n in _ast.walk(tree)
                   if isinstance(n, _ast.Call)
                   and isinstance(n.func, _ast.Name) and n.func.id == name)

    # ---- #1a 唯一实现 ----
    for _fn in ("_plan_conf", "_normalize_plan_mode",
                "_normalize_plan_rounds"):
        _d = _defs(_fn)
        if _d != 1:
            bad.append("[1a] %s 的 def 有 %d 处（应为 1）" % (_fn, _d))

    # ---- #1b 形态计数（抠掉模块 docstring 后）----
    for _pat, _want in (("conf = float(data.get(", 0),
                        ("if rnd and len(rnd) < 4:", 1),
                        ("_layer_floor(k, hard, _floor)", 1)):
        _got = body.count(_pat)
        if _got != _want:
            bad.append("[1b] 形态 %r 出现 %d 次（应为 %d）"
                       % (_pat, _got, _want))

    # ---- #1c 接线（含 def 行的同名 Name 不计入 Call，故期望=调用点数）----
    for _fn, _want in (("_normalize_plan_mode", 3), ("_plan_conf", 3),
                       ("_normalize_plan_rounds", 2)):
        _got = _calls(_fn)
        if _got != _want:
            bad.append("[1c] %s 被调用 %d 次（应为 %d）" % (_fn, _got, _want))

    # ---- #1d 三处行为对照（生产入口，不手造中间结构）----
    class _Stub:
        def __init__(self, payload):
            self.payload = payload

        def call(self, *a, **k):
            return json.dumps(self.payload, ensure_ascii=False)

        def parse_json(self, raw):
            return json.loads(raw)

    _cfg = build_cfg(False)
    _rounds_cases = {
        "四层齐": {"0": 3, "1": 7, "both": 4, "all": 6},
        "只给两层": {"0": 5, "1": 5},
        "越界值": {"0": 1, "1": 99, "both": 2, "all": 2},
        "空圈数": {},
    }
    for _m in ("G", "Z", "h", "serial"):
        for _tag, _rin in _rounds_cases.items():
            _pl = {"route": "full", "mode": _m, "rounds": dict(_rin),
                   "max_calls": 0, "reason": "probe", "confidence": 0.8,
                   "orientation": "decision"}
            _m1 = mod.MetaDGTF(_cfg)
            _m1.llm = _Stub(dict(_pl))
            _r1 = _m1._decide_parallel_mode("探针题：该怎么跑")
            _s2 = _Stub(dict(_pl))
            _oL = mod.LLM
            mod.LLM = lambda c: _s2
            try:
                _r2 = mod.plan_resources("探针题：该怎么跑", "decision", _cfg)
            finally:
                mod.LLM = _oL
            _m3 = mod.MetaDGTF(_cfg)
            _m3.llm = _Stub(dict(_pl))
            _r3 = _m3._auto_plan("探针题：该怎么跑")
            _r2r = {k: v for k, v in (_r2.get("rounds") or {}).items()
                    if k in (_r2.get("route") or [])}
            if _r1.get("mode") != _r3.get("mode"):
                bad.append("[1d] %s/%s 单目标 %s vs 单调用 %s"
                           % (_m, _tag, _r1.get("mode"), _r3.get("mode")))
            if _r2.get("mode") != _r3.get("mode") or _r2r != dict(
                    _r3.get("rounds") or {}):
                bad.append("[1d] %s/%s 两段式 %s/%s vs 单调用 %s/%s"
                           % (_m, _tag, _r2.get("mode"), _r2r,
                              _r3.get("mode"), dict(_r3.get("rounds") or {})))

    # ---- #1e 刻意保留的差异：低置信时 reason 的处置 ----
    _lo = {"route": "full", "mode": "G",
           "rounds": {"0": 3, "1": 5, "both": 4, "all": 6},
           "max_calls": 0, "reason": "probe", "confidence": 0.1,
           "orientation": "decision"}
    _m1 = mod.MetaDGTF(_cfg)
    _m1.llm = _Stub(dict(_lo))
    _r1 = _m1._decide_parallel_mode("探针题")
    if _r1.get("mode") != "serial":
        bad.append("[1e] 低置信：单目标决策没退 serial（%s）" % _r1.get("mode"))
    if not str(_r1.get("reason", "")).startswith("低置信"):
        bad.append("[1e] 低置信：单目标决策 reason 未改写（%r）"
                   % _r1.get("reason"))
    _s2 = _Stub(dict(_lo))
    _oL = mod.LLM
    mod.LLM = lambda c: _s2
    try:
        _r2 = mod.plan_resources("探针题", "decision", _cfg)
    finally:
        mod.LLM = _oL
    if _r2.get("mode") != "serial":
        bad.append("[1e] 低置信：两段式没退 serial（%s）" % _r2.get("mode"))
    if _r2.get("reason") != "probe":
        bad.append("[1e] 低置信：两段式 reason 被改写了（%r）—— "
                   "这是刻意保留的差异，不该变" % _r2.get("reason"))
    _m3 = mod.MetaDGTF(_cfg)
    _m3.llm = _Stub(dict(_lo))
    _r3 = _m3._auto_plan("探针题")
    if _r3.get("mode") != "serial":
        bad.append("[1e] 低置信：单调用没退 serial（%s）" % _r3.get("mode"))
    if not str(_r3.get("reason", "")).startswith("低置信"):
        bad.append("[1e] 低置信：单调用 reason 未改写（%r）" % _r3.get("reason"))

    # ---- #2 单票实现仍在 + 登记表两向对账 ----
    _sd = _defs("_adjudicate_sub_tristate")
    if _sd != 1:
        bad.append("[2] _adjudicate_sub_tristate 的 def 有 %d 处（应为 1）"
                   % _sd)
    _sd_calls = sum(
        1 for n in _ast.walk(tree) if isinstance(n, _ast.Call)
        and ((isinstance(n.func, _ast.Name)
              and n.func.id == "_adjudicate_sub_tristate")
             or (isinstance(n.func, _ast.Attribute)
                 and n.func.attr == "_adjudicate_sub_tristate")))
    if _sd_calls < 1:
        bad.append("[2] _adjudicate_sub_tristate 没有任何调用点（死代码？）")
    _n_pf = src.count("# [AUDIT-122] 标 pending_fix：")
    _c_pf = getattr(mod, "_AUDIT122_PENDING_FIX", None)
    if _n_pf != 2 or _c_pf != 2:
        bad.append("[2] 登记表对账失败：源码 %d 条 / 常量 %r（都应为 2）"
                   % (_n_pf, _c_pf))

    # ---- #3 布尔兼容留痕（可观测化）----
    import logging as _lg

    class _H(_lg.Handler):
        def __init__(self):
            _lg.Handler.__init__(self)
            self.msgs = []

        def emit(self, r):
            try:
                self.msgs.append(r.getMessage())
            except Exception:
                pass

    _lgw = _lg.getLogger("dgtf")
    _h = _H()
    _old = _lgw.level
    _lgw.addHandler(_h)
    _lgw.setLevel(_lg.WARNING)
    try:
        _t_true = mod._anchor_tier({"as_evidence": True})
        _n_true = len([m for m in _h.msgs if "布尔写法" in m])
        _h.msgs = []
        _t_off = mod._anchor_tier({"as_evidence": "off"})
        _n_off = len([m for m in _h.msgs if "布尔写法" in m])
        _h.msgs = []
        _t_bad = mod._anchor_tier({"as_evidence": "nonsense"})
        _n_bad = len([m for m in _h.msgs if "布尔写法" in m])
    finally:
        _lgw.removeHandler(_h)
        _lgw.setLevel(_old)
    if _t_true != "evidence":
        bad.append("[3] 布尔 True 应归一成 evidence，实际 %r" % _t_true)
    if _n_true != 1:
        bad.append("[3] 布尔兼容走了却没留痕（捕获 %d 条）" % _n_true)
    if _t_off != "off" or _n_off != 0:
        bad.append("[3] 字符串档 off 不该留痕（%r / %d 条）" % (_t_off, _n_off))
    if _t_bad != "off" or _n_bad != 0:
        bad.append("[3] 非法值应落 off 且不走布尔留痕（%r / %d 条）"
                   % (_t_bad, _n_bad))

    if bad:
        for _m in bad:
            print("  \\u2717 [v1235] %s" % _m)
        return False
    print("  \\u2713 [v1235] pending_fix：归一化唯一实现+三处接线+16 组逐字一致"
          "；低置信差异保留；单票仍在且登记 2 项；布尔兼容留痕/不误报")
    return True

'''

ast.parse(CHECKS)
print("[自检] CHECKS ast.parse 通过")


def read_lf(p):
    b = p.read_bytes()
    s = b.decode("utf-8")
    assert b.count(b"\r\r\n") == 0, "%s 已有 CRCRLF" % p.name
    assert s.count("\r\n") == s.count("\n"), "%s 非纯 CRLF" % p.name
    return s.replace("\r\n", "\n")


def write_crlf(p, s):
    assert "\r" not in s
    b = s.replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)
    chk = p.read_bytes()
    assert chk.count(b"\r\n") == chk.count(b"\n"), "落盘非纯 CRLF"
    assert chk.count(b"\r\r\n") == 0, "落盘含 CRCRLF"


# ---------------------------------------------------------------- 1) 判据块
s = read_lf(SMOKE)
n = s.count(MARK)
assert n == 1, "MARK 命中 %d 次" % n
if "def check_v1235_pending_fix(" in s:
    _bi = s.index("def check_v1235_pending_fix():")
    _bj = s.index(MARK)
    assert _bi < _bj, "判据块在 MARK 之后"
    s = s[:_bi] + CHECKS.lstrip("\n") + s[_bj:]
    print("[1] 判据块已整块替换（注入器是单一事实源）")
else:
    s = s.replace(MARK, CHECKS.lstrip("\n") + MARK)
    print("[1] 判据块已插入")

# ---------------------------------------------------------------- 2) SRC
_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
_n = len(_pat.findall(s))
assert _n == 1, "SRC 行命中 %d 次" % _n
s = _pat.sub('SRC = HERE / "%s"' % TARGET, s)
print("[2] SRC ->", TARGET)

# ---------------------------------------------------------------- 3) 守卫
_GUARD_RE = re.compile(r"^    if not (check_v123\d*_\w+)\(\):\n        return 1\n",
                       re.M)
_hits = list(_GUARD_RE.finditer(s))
assert len(_hits) >= 9, "守卫数 %d 少于基线 9（守卫被清了？）" % len(_hits)
if "if not check_v1235_pending_fix():" not in s:
    _p = _hits[-1].end()
    s = (s[:_p] + "    if not check_v1235_pending_fix():\n        return 1\n"
         + s[_p:])
    print("[3] 守卫已插入（接在最后一个 check_v123* 之后）")
else:
    print("[3] [skip] 守卫已存在")

write_crlf(SMOKE, s)
ast.parse(s)
print("    smoke_test.py ast.parse 通过；守卫数 =", len(_GUARD_RE.findall(s)))

# ---------------------------------------------------------------- 4) 上游生成器
# 生成器脚本是 LF（临时脚本，不要求 CRLF），单独按文本读写
g = GEN1230.read_text(encoding="utf-8")
assert "\r\r\n" not in g
_OLD = '''               "    if not check_v1234_runtime():\\n        return 1\\n")'''
_NEW = '''               "    if not check_v1234_runtime():\\n        return 1\\n"
               "    if not check_v1235_pending_fix():\\n        return 1\\n")'''
if "check_v1235_pending_fix" not in g:
    n = g.count(_OLD)
    assert n == 1, "GUARD_BLOCK 尾部命中 %d 次" % n
    g = g.replace(_OLD, _NEW)
    GEN1230.write_bytes(g.encode("utf-8"))
    print("[4] _mk_v1230_smoke_checks.py 的 GUARD_BLOCK 已补新守卫")
else:
    print("[4] [skip] GUARD_BLOCK 已含新守卫")
