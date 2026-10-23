# -*- coding: utf-8 -*-
"""v1.23.19 冒烟注入器：SRC 换版 + 新增「锚点真检索可达」判据 + 守卫。"""
import ast
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
raw = SMOKE.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def repl_block(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    print("%-38s 改 %d 处" % (what, len(hits)))


repl_block('SRC = HERE / "元DGTF-V1.23.18.py"',
           'SRC = HERE / "元DGTF-V1.23.19.py"', "SRC → v1.23.19")

NEW_FUNC = '''def check_v12319_anchor_retrieval_reachable():
    """[v1.23.19] 锚点「真检索」这条路必须**够得到**（默认路径不受影响）。

    ★ 改前现场：`_retrieve_anchors` 全篇只有 `_anchor_round` 里一处调用，
      而它在 `not self._anchors` 这道早退**之后** ⇒ 没挂快照文件时真检索
      **一次都不会被调用**（连「后端未实现」的留痕都发生不了，承诺够不到）。
      实测：`retriever="tavily"` + `_anchors` 空 ⇒ 检索调用 0 次。

    ① 出厂 `retriever` 仍是 `snapshot`（默认零调用不变）；
    ② 行为：tavily + `_anchors` 空 ⇒ 检索**被调用**（桩计数）、`_anchors` 被填、
       按 `per_round` 投池；
    ③ 负对照 A：snapshot + 空 ⇒ 检索**不许**被调用、池里 0 条；
    ④ 负对照 B（**不桩**）：未实现后端 ⇒ 真抛错留痕（`_anchor_err` 含「尚未实现」）、
       不崩、不投池；
    ⑤ `unconfigured`：snapshot+无 path ⇒ True；tavily+无 path ⇒ **False**
       （真检索模式不是「未挂文件」）；
    ⑥ 渲染两处（头部通道行 / 产物明细）都给**两条**接入方式。
    """
    import tempfile as _tf
    bad = []
    _ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
    if _ea.get("retriever") != "snapshot":
        bad.append("出厂 retriever 不是 snapshot（=%r）—— 默认零调用被改了"
                   % _ea.get("retriever"))

    def _mk(mode):
        _o = object.__new__(mod.MetaDGTF)
        _o.config = {"external_anchor": {
            "enabled": True, "path": "", "per_round": 2, "retriever": mode,
            "api_key_env": "TAVILY_API_KEY", "cache_ttl_hours": 24,
            "max_items": 12, "as_evidence": "off", "triage": False}}
        _o._anchors = []
        _o._anchor_err = ""
        _o._anchor_unconfigured = False
        _o.vp = lambda *a, **k: None
        _o.pools = {"0": mod.Pool()}
        return _o

    _rec = {"n": 0}
    _orig = mod.AnchorRetriever.search

    def _stub(self, queries, max_n=12):
        _rec["n"] += 1
        return [{"id": "R1", "claim": "真检索条目 1", "tier": 3},
                {"id": "R2", "claim": "真检索条目 2", "tier": 3}]

    mod.AnchorRetriever.search = _stub
    try:
        # ② tavily + 空锚点 ⇒ 必须真检索
        _rec["n"] = 0
        _o = _mk("tavily")
        _o._anchor_round("0", _o.pools["0"], 0)
        if _rec["n"] != 1:
            bad.append("[②] tavily + 空锚点：检索调用 %d 次（应 1）—— 死路没修好"
                       % _rec["n"])
        if len(_o._anchors) != 2:
            bad.append("[②] 检索结果没并进 `_anchors`（=%d）" % len(_o._anchors))
        if len(_o.pools["0"].anchors) != 2:
            bad.append("[②] 检索到的锚点没按 per_round 投池（=%d）"
                       % len(_o.pools["0"].anchors))
        # ③ 负对照 A：snapshot + 空 ⇒ 不许检索
        _rec["n"] = 0
        _o3 = _mk("snapshot")
        _o3._anchor_round("0", _o3.pools["0"], 0)
        if _rec["n"] != 0:
            bad.append("[③] snapshot 模式竟然调了检索（%d 次）—— 默认不再零调用"
                       % _rec["n"])
        if _o3.pools["0"].anchors:
            bad.append("[③] snapshot + 空锚点却往池里塞了东西")
    finally:
        mod.AnchorRetriever.search = _orig

    # ④ 负对照 B：未实现后端（不桩）⇒ 真抛错留痕、不崩、不投池
    try:
        _o4 = _mk("web_search")
        _o4._anchor_round("0", _o4.pools["0"], 0)
        if "尚未实现" not in (_o4._anchor_err or ""):
            bad.append("[④] 未实现后端没留痕（_anchor_err=%r）—— 静默降级了"
                       % (_o4._anchor_err or ""))
        if _o4.pools["0"].anchors:
            bad.append("[④] 检索失败后还往池里塞了东西")
    except Exception as _e:  # noqa: BLE001
        bad.append("[④] 未实现后端把异常抛到了外面：%s: %s"
                   % (type(_e).__name__, _e))

    # ⑤ unconfigured：只有 snapshot 模式才算「未挂文件」
    for _mode, _want in (("snapshot", True), ("tavily", False)):
        _c = build_cfg(False)
        _c["external_anchor"] = dict(_c.get("external_anchor") or {})
        _c["external_anchor"].update({"enabled": True, "path": "",
                                      "retriever": _mode})
        _oo = object.__new__(mod.MetaDGTF)
        _oo.config = _c
        _oo.vp = lambda *a, **k: None
        _oo._load_anchors()
        if bool(getattr(_oo, "_anchor_unconfigured", None)) != _want:
            bad.append("[⑤] %s + 无 path：unconfigured=%r（应 %r）"
                       % (_mode, getattr(_oo, "_anchor_unconfigured", None), _want))

    # ⑥ 渲染两处都给两条路
    _ln = [l for l in mod._anchor_lane_lines({"external_anchor": {
        "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}})
        if "文本" in l]
    if not _ln or "tavily" not in _ln[0] or "path" not in _ln[0]:
        bad.append("[⑥] 头部通道行没给两条接入方式")
    _res = {"question": "新中国的成立时间是什么时候", "route": ["1"],
            "keep": {"1": "all"}, "rounds": {"1": 1},
            "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                         "requested": ["1"], "skipped": []},
            "views": {"1": {}}, "pools": {"1": {
                "amps": [], "threads": [], "probes": [], "suspensions": [],
                "meta": [], "sub_questions": [], "deferrals": [],
                "escalations": [], "decidability_log": [],
                "duel_suspensions": [], "duel_alignment": [],
                "engagements": [], "refinements": [],
                "decidable_channel": [], "undecidable_channel": []}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "tri_state": [0, 0], "_config": {},
            "external_anchor": {"enabled": True, "unconfigured": True,
                                "anchors": 0, "error": ""}}
    with _tf.TemporaryDirectory() as td:
        _md = Path(mod.save_result(_res, save_dir=td)).read_text(encoding="utf-8")
    _seg = [l for l in _md.split("\\n") if "锚点对照" in l]
    if not _seg or "tavily" not in _seg[0]:
        bad.append("[⑥] 产物明细「未做」没给两条接入方式")

    if bad:
        for _x in bad:
            print("  ✗ [v12319] %s" % _x)
        return False
    print("  ✓ [v12319] 锚点真检索可达（tavily+空锚点 ⇒ 真调）；snapshot 仍零调用；"
          "未实现后端真抛错留痕；unconfigured 只在 snapshot；渲染给两条路")
    return True


'''

ANCHOR = "def check_p23_units():"
assert lines.count(ANCHOR) == 1
_i = lines.index(ANCHOR)
lines[_i:_i] = NEW_FUNC.split("\n")
print("%-38s 插入新判据" % "check_v12319_anchor_retrieval_reachable")

repl_block('''    if not check_v12318_anchor_default_on():
        return 1''',
           '''    if not check_v12318_anchor_default_on():
        return 1
    if not check_v12319_anchor_retrieval_reachable():
        return 1''',
           "注入守卫")

out = "\n".join(lines)
t = ast.parse(out)
_dead = []
for _n in ast.walk(t):
    if isinstance(_n, ast.FunctionDef):
        _seen, _d = False, 0
        for _s in _n.body:
            if _seen:
                _d += 1
            elif (isinstance(_s, ast.Return) and isinstance(_s.value, ast.Constant)):
                _seen = True
        if _d:
            _dead.append("%s(+%d)" % (_n.name, _d))
assert not _dead, "仍有死代码：%s" % _dead
assert out.count("def check_v12319_anchor_retrieval_reachable(") == 1
assert out.count("check_v12319_anchor_retrieval_reachable()") == 2
enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
SMOKE.write_bytes(enc)
print("死代码自检 0 处；行数 %d；CRLF %d" % (out.count("\n"), enc.count(b"\r\n")))
