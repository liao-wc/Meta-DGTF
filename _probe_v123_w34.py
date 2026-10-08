# -*- coding: utf-8 -*-
"""[v1.23.0 W3+W4] 探针：对撞层/元层接入 + 三票正交化 + 宪法 C3/C4（带变异体）。

用法：python _probe_v123_w34.py [元DGTF-V1.23.0.py]
"""
import ast
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.0.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mod = load(SRC, "dgtf_w34")
txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")


def body_of(name):
    """抠函数体。★ 带开括号 —— 前缀同名函数会被截走（本项目踩过）。"""
    tree = ast.parse(txt)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return "\n".join(txt.split("\n")[n.lineno - 1:n.end_lineno])
    return ""



def body_of_in(text, name):
    """在**任意文本**里抠函数体（变异体文本要用它，不能用全局 txt）。"""
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return "\n".join(text.split("\n")[n.lineno - 1:n.end_lineno])
    return ""

# ============================================================ A 结构
ck("A1 Pool 三池字段齐",
   all(hasattr(mod.Pool(), _k) for _k in
       ("web_results", "web_arbitration", "web_clean_check")), "")
ck("A2 两个 query 构造存在",
   all(hasattr(mod, _k) for _k in
       ("_duel_arbitration_queries", "_meta_clean_queries")), "")
ck("A3 两个接入方法存在",
   all(hasattr(mod.MetaDGTF, _k) for _k in
       ("_web_duel_arbitration", "_web_meta_clean_check")), "")
_fb = body_of("_finalize_layer_common")
ck("A4 接入点收在 _finalize_layer_common（both/all 各一处，"
   "且**都传真圈号** r_actual + 1）—— [v1.23.1 遗留3] 口径随实现更新",
   "_web_duel_arbitration(view, r_actual + 1)" in _fb
   and "_web_meta_clean_check(" in _fb
   and "or []), r_actual + 1)" in _fb, "")
ck("A5 W4 第三票替换（_sys_list[2]）",
   "_sys_list[2] = _TRI_VOTE_PROMPTS[2]" in txt
   and "只看" in txt, "")

# ============================================================ B 行为
Pool = mod.Pool


def _mkmeta(enabled=True, client=None):
    class _SC:
        def __init__(self):
            self.calls = 0
            self.cache_hits = 0

        def search(self, q, max_n=8):
            self.calls += 1
            return [{"claim": "桩：" + q, "url": "u", "source": "s",
                     "tier": 3}], ""

    cfg = {"web_search": dict(mod.DEFAULT_CONFIG["web_search"])}
    cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
    cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
    cfg["web_search"]["enabled"] = enabled
    o = object.__new__(mod.MetaDGTF)
    o.config = cfg
    o.pools = {"both": Pool(), "all": Pool(), "1": Pool()}
    o.vp = lambda *a, **k: None
    o._web_gate = mod.WebSearchGate(cfg)
    o._web_client = client or _SC()
    o._web_prep_seq = 0
    o.decidability_result = {}
    return o


_v = mod.View(entry="both")
_v.adjudications = [{"tension": "先改瓶颈段还是先全量提标"}]
_o = _mkmeta(True)
_r = _o._web_duel_arbitration(_v)
ck("B1.a 仲裁结果入 pool.web_arbitration",
   len(_o.pools["both"].web_arbitration) == len(_r) > 0, repr(len(_r)))
ck("B1.b used_as=arbitration",
   all(x["used_as"] == "arbitration" for x in _r), "")
ck("B1.c 池级留痕 [W-ARB]", any("[W-ARB]" in str(x) for x in _v.meta),
   repr(_v.meta[:2]))
ck("B1.d ★ 仲裁材料**没进** view.collision/adjudications 内容",
   all("桩：" not in str(a) for a in _v.adjudications), "")

_v2 = mod.View(entry="all")
_o2 = _mkmeta(True)
_r2 = _o2._web_meta_clean_check(_v2, ["未覆盖：运维责任划转"])
ck("B2.a 核对结果入 pool.web_clean_check",
   len(_o2.pools["all"].web_clean_check) == len(_r2) > 0, repr(len(_r2)))
ck("B2.b used_as=clean_check",
   all(x["used_as"] == "clean_check" for x in _r2), "")
ck("B2.c 池级留痕 [W-CHK]", any("[W-CHK]" in str(x) for x in _v2.meta), "")

# 负对照：无 tension / 无 uncovered → 一条都不发
_v3 = mod.View(entry="both")
_o3 = _mkmeta(True)
ck("B3 负对照：无张力 → 不检索",
   _o3._web_duel_arbitration(_v3) == [] and _o3._web_client.calls == 0, "")
_o4 = _mkmeta(True)
ck("B4 负对照：uncovered 空 → 不检索",
   _o4._web_meta_clean_check(mod.View(entry="all"), []) == []
   and _o4._web_client.calls == 0, "")
# 负对照：默认关 → 不检索
_o5 = _mkmeta(False)
ck("B5 负对照：默认关 → 不检索",
   _o5._web_duel_arbitration(_v) == [] and _o5._web_client.calls == 0, "")

ck("B6 query 构造：tension → 「哪个更合理？」",
   all("哪个更合理" in x
       for x in mod._duel_arbitration_queries(["甲还是乙"])), "")
ck("B7 query 构造负对照：空 → 空",
   mod._duel_arbitration_queries([]) == []
   and mod._duel_arbitration_queries([""]) == []
   and mod._meta_clean_queries(None) == [], "")

# ============================================================ C 宪法 C3 / C4
_ING_FORBID = ("web_results", "web_as_evidence", "web_arbitration",
               "web_clean_check", "_web_search", "_web_digest", "_web_client")
_bing = body_of("_ing")
ck("C3.a ★ C3 未对齐合法：_ing 体里没有任何联网符号",
   not any(_k in _bing for _k in _ING_FORBID),
   repr([_k for _k in _ING_FORBID if _k in _bing]))

_sd = body_of("settle_deferrals")
ck("C4.a ★ C4 停止与清算分开：settle_deferrals 体里没有任何联网符号",
   not any(_k in _sd for _k in _ING_FORBID + ("web_",)),
   repr([_k for _k in _ING_FORBID if _k in _sd]))

# `self._web_search(` 调用点白名单：必须落在 6 个接入方法里
_WHITE = ("_research_web_prep", "_web_evidence_hook", "_web_duel_arbitration",
          "_web_meta_clean_check", "_adjudicate_sub_tristate_multi")
_calls = txt.count("self._web_search(")
ck("C4.b `self._web_search(` 调用点 = 6"
   "（W2 三处：decompose/precedent/evidence；W3 两处；W4 一处）",
   _calls == 6, repr(_calls))
_tree = ast.parse(txt)
_bad = []
for _cls in [x for x in ast.walk(_tree) if isinstance(x, ast.ClassDef)]:
    for _fn in [x for x in _cls.body if isinstance(x, ast.FunctionDef)]:
        _b = "\n".join(txt.split("\n")[_fn.lineno - 1:_fn.end_lineno])
        if "self._web_search(" in _b and _fn.name not in _WHITE:
            _bad.append(_fn.name)
ck("C4.c ★ 调用点全在白名单方法里", not _bad, repr(_bad))
# 结算类函数一律不得出现
for _nm in ("_settle_meta", "settle_deferrals", "_finalize_layer_common"):
    _b = body_of(_nm)
    _hit = "self._web_search(" in _b or "self._web_client" in _b
    ck("C4.d %s 里没有直调检索" % _nm, not _hit, "")

# ---- [v1.23.1 遗留] C4 的锚必须覆盖**主路径**，不能只锚兜底 ----
_SETTLE_FNS = ("settle_deferrals", "_settle_research", "_settle_meta",
               "_refresh_settlement")
for _nm in _SETTLE_FNS:
    _b = body_of(_nm)
    ck("C4.e ★ 结算函数 %s 体内无任何 web 符号" % _nm,
       bool(_b) and not any(_k in _b for _k in _ING_FORBID)
       and "web_" not in _b,
       ("空体（符号不存在？）" if not _b
        else repr([_k for _k in _ING_FORBID if _k in _b])))
_b_main = body_of("_settle_research")
ck("C4.f ★ 主路径 `_settle_research` 确含「升级 → undecidable」写点"
   "（否则它就不是主路径，上面的锚白扩）",
   'sq["decidability"] = "undecidable"' in _b_main
   and 'escalated' in _b_main, "")

# ============================================================ D 变异测试
MUT = {
    "N1 往 _ing 的 user 掺 W#（C3 必须判红）": (
        '            f"【& 候选（属性≠位置）】\\n{amp_text}"\n'
        '        )\n',
        '            f"【& 候选（属性≠位置）】\\n{amp_text}"\n'
        '            + str(view.web_results)\n'
        '        )\n'),
    "N2 往 settle_deferrals 掺 W#（C4 必须判红）": (
        'def settle_deferrals(pool, layer: int) -> dict:\n'
        '    left = [d for d in pool.deferrals if d["status"] == "deferred"]\n',
        'def settle_deferrals(pool, layer: int) -> dict:\n'
        '    pool.web_results.append({"id": "WX", "claim": "清算时偷跑检索"})\n'
        '    left = [d for d in pool.deferrals if d["status"] == "deferred"]\n'),
}

_td = Path(tempfile.mkdtemp())
for _nm, (_o, _n) in MUT.items():
    if txt.count(_o) != 1:
        ck("D.%s 变异体可构造" % _nm[:2], False,
           "锚点 %d 次" % txt.count(_o))
        continue
    _mp = _td / ("mut34_%s.py" % _nm[:2])
    _mp.write_bytes(txt.replace(_o, _n).replace("\n", "\r\n").encode("utf-8"))
    try:
        _mm = load(_mp, "mut34_%s" % _nm[:2])
        _mt = _mp.read_text(encoding="utf-8").replace("\r\n", "\n")

        def _body_in(text, name):
            tr = ast.parse(text)
            for x in ast.walk(tr):
                if isinstance(x, ast.FunctionDef) and x.name == name:
                    return "\n".join(text.split("\n")[x.lineno - 1:x.end_lineno])
            return ""

        if _nm.startswith("N1"):
            _red = any(_k in _body_in(_mt, "_ing") for _k in _ING_FORBID)
        else:
            _red = any(_k in _body_in(_mt, "settle_deferrals") for _k in
                       _ING_FORBID + ("web_",))
    except Exception:  # noqa: BLE001
        _red = True
    ck("D.%s → 判据判红" % _nm[:2], _red, "")


def _inject_after_def(text, fn_name, stmt_line):
    """在函数体**第一条语句之前**插入一行（缩进取该语句的 col_offset）。

    ★ 不用字面锚点 —— 主路径里的行很多都不唯一；AST 定位天然唯一，
      且插入点缩进正确。
    """
    tree = ast.parse(text)
    for x in ast.walk(tree):
        if isinstance(x, ast.FunctionDef) and x.name == fn_name:
            _ind = " " * (x.body[0].col_offset if x.body else
                          (x.col_offset + 4))
            lines = text.split("\n")
            lines.insert(x.body[0].lineno - 1, _ind + stmt_line)
            return "\n".join(lines)
    return ""


_MUT2 = {
    "N3 往清算**主路径** `_settle_research` 掺 W#（C4.e 必须判红）":
        ("_settle_research",
         'pool.web_results.append({"id": "WX", "claim": "清算时偷跑检索"})'),
    "N4 往 `_settle_meta` 掺 W#（C4.e 必须判红）":
        ("_settle_meta",
         'pool.web_clean_check.append({"id": "WX", "claim": "元层清算偷跑"})'),
}
for _nm, (_fn, _stmt) in _MUT2.items():
    _mt = _inject_after_def(txt, _fn, _stmt)
    if not _mt or _mt == txt:
        ck("D.%s 变异体可构造" % _nm[:2], False, "AST 定位失败：" + _fn)
        continue
    _mb = body_of_in(_mt, _fn)
    _red = any(_k in _mb for _k in _ING_FORBID) or "web_" in _mb
    ck("D.%s → 判据判红" % _nm[:2], _red, "")
    if _nm.startswith("N3"):
        # ★★ 负对照：**旧判据**（只读 settle_deferrals）对主路径变异体
        #    **不判红** —— 这就是「锚错对象」的直接证据。
        _old = body_of_in(_mt, "settle_deferrals")
        _old_red = any(_k in _old for _k in _ING_FORBID) or "web_" in _old
        ck("D.N3 负对照：旧锚（只读 settle_deferrals）对主路径变异体**不判红**",
           _old_red is False,
           "旧锚也判红了 —— 说明它本来就覆盖主路径，本补丁是多余的")

print("═══ probe v123 W3+W4 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print("PASS %d / FAIL %d" % (sum(1 for _, o, _ in R if o),
                             sum(1 for _, o, _ in R if not o)))
sys.exit(0 if all(o for _, o, _ in R) else 1)
