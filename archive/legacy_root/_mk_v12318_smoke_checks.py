# -*- coding: utf-8 -*-
"""v1.23.18 冒烟注入器：SRC 换版 + 改两组旧判据（判据随实现更新）+ 新增一组判据。

★ 为什么旧判据要改：`external_anchor.enabled` 的**出厂默认**由 false 改成 true
  ⇒ 以前「靠默认关」就能测到的「关闭态」，现在必须**显式关**；
  且关闭态的文案由「无」改成「**关**」（与联网通道对称）。
  这是判据随实现更新，不是放宽。
"""
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
    print("%-36s 改 %d 处" % (what, len(hits)))


# ① SRC 换版
repl_block('SRC = HERE / "元DGTF-V1.23.17.py"',
           'SRC = HERE / "元DGTF-V1.23.18.py"', "SRC → v1.23.18")

# ② [A] 夹具显式关（默认已翻）
repl_block('''    cfg_off = build_cfg(False)
    cfg_off["output"]["save_dir"] = str(td / "off")
    off_sys = []''',
           '''    cfg_off = build_cfg(False)
    cfg_off["output"]["save_dir"] = str(td / "off")
    # ★ [v1.23.18 判据随实现更新] `external_anchor.enabled` 出厂默认由 false
    #   改成 true ⇒ 想测「关闭态」必须**显式关**（以前靠默认关就够了）。
    cfg_off["external_anchor"] = dict(cfg_off.get("external_anchor") or {})
    cfg_off["external_anchor"]["enabled"] = False
    off_sys = []''',
           "[A] 夹具显式关")

# ③ [A] 关闭态文案：无 → **关**
repl_block('''        chk("**外部锚点 · 文本**（锚点文件 `external_anchor`）：无" in t_off,
            "[A] 关闭时文本通道没写「无」")''',
           '''        # [v1.23.18 判据随实现更新] 关闭态文案由「无」改成「**关**」——
        #   与联网通道对称（缺席时两条通道都写「关」）。
        chk("**外部锚点 · 文本**（锚点文件 `external_anchor`）：**关**" in t_off,
            "[A] 关闭时文本通道没写「关」")''',
           "[A] 关闭态文案断言")

# ④ v12312 判据：case A 文案断言 + 新增「未挂文件」态
repl_block('''    if "无 ——" not in _j:
        bad.append("没有锚点文件时，文本通道没写「无」")''',
           '''    # [v1.23.18 判据随实现更新] 缺席态文案由「无」改成「**关**」（对称）。
    _tl0 = [l for l in _lanes if "文本" in l]
    if not _tl0 or "**关**" not in _tl0[0]:
        bad.append("没有锚点文件时，文本通道没写「关」（旧文案「无」已退役）")''',
           "v12312 case A 文案")

repl_block('''    # ── B · 三态：关 / 未记录 ─────────────────────────────────''',
           '''    # ── A2 · [v1.23.18] 新态：通道开着但**没挂文件** ────────────
    _unc = m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": False},
        "external_anchor": {"enabled": True, "unconfigured": True,
                            "anchors": 0, "error": ""}}))
    _utl = [l for l in _unc if "文本" in l]
    if not _utl or "开（未挂锚点文件）" not in _utl[0]:
        bad.append("v1.23.18：未挂文件态没写「开（未挂锚点文件）」")
    if any(("已接入" in l or "锚点异常" in l) for l in _unc):
        bad.append("未挂文件态混进了「已接入」/「锚点异常」")

    # ── B · 三态：关 / 未记录 ─────────────────────────────────''',
           "v12312 新增未挂文件态")

NEW_FUNC = '''def check_v12318_anchor_default_on():
    """[v1.23.18] 外部锚点默认打开；「未挂文件」是**独立干净态**。

    ① 出厂值：`DEFAULT_CONFIG` 与出厂 yaml 的 `enabled` 都是 True；yaml 不预置 path；
    ② 行为：`enabled=True` 但没给 path ⇒ **不记 error**、置 `unconfigured`；
       **负对照**：path 指到不存在的文件 ⇒ 必须仍记 error（失败不许被吞成「未挂文件」）；
    ③ 渲染四态（缺失 / 未挂文件 / 已接入 / 失败）各说各的，互不冒充；
    ④ 产物：未挂文件时**不写**「锚点对照 / 分级 / triage 降级 / 入池 / 冲突」五行零，
       只写一行「未做对照」，且**不出现**「锚点异常」。
    """
    import tempfile as _tf
    bad = []
    _ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
    if _ea.get("enabled") is not True:
        bad.append("出厂 DEFAULT_CONFIG enabled 不是 True（=%r）" % _ea.get("enabled"))
    try:
        _yc = mod.load_config(str(HERE / "dgtf_config.yaml"))
        _ye = (_yc.get("external_anchor") or {})
        if _ye.get("enabled") is not True:
            bad.append("出厂 yaml 的 enabled 不是 True（=%r）" % _ye.get("enabled"))
        if _ye.get("path"):
            bad.append("出厂 yaml 不该预置 path（=%r）" % _ye.get("path"))
    except Exception as _e:  # noqa: BLE001
        bad.append("读出厂 yaml 失败：%s" % _e)

    def _load(path):
        _c = build_cfg(False)
        _c["external_anchor"] = dict(_c.get("external_anchor") or {})
        _c["external_anchor"].update({"enabled": True, "path": path})
        _o = object.__new__(mod.MetaDGTF)
        _o.config = _c
        _o.vp = lambda *a, **k: None
        _o._load_anchors()
        return _o

    _o1 = _load("")
    if getattr(_o1, "_anchor_err", None):
        bad.append("没挂文件却记了 error：%r" % _o1._anchor_err)
    if getattr(_o1, "_anchor_unconfigured", None) is not True:
        bad.append("没挂文件却没置 unconfigured")
    _o2 = _load(str(HERE / "__nope_anchor__.json"))
    if not getattr(_o2, "_anchor_err", ""):
        bad.append("path 不存在却**没**记 error —— 失败被吞成「未挂文件」")
    if getattr(_o2, "_anchor_unconfigured", None):
        bad.append("path 不存在却置了 unconfigured")

    def _res(st):
        d = {"question": "新中国的成立时间是什么时候", "route": ["1"],
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
             "_runtime": {"web_enabled": False}}
        d.update(st)
        return d

    def _tline(st):
        _ls = mod._anchor_lane_lines(_res(st))
        _x = [l for l in _ls if "文本" in l]
        return _x[0] if _x else ""

    _sm = "**外部锚点 · 文本**（锚点文件 `external_anchor`）"
    if "**关**" not in _tline({}):
        bad.append("缺失态没写「关」")
    if "开（未挂锚点文件）" not in _tline({"external_anchor": {
            "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}}):
        bad.append("未挂文件态没写「开（未挂锚点文件）」")
    _ok = _tline({"external_anchor": {
        "enabled": True, "anchors": 3, "source_file": "a.json",
        "retrieved_at": "t0", "error": ""}})
    if "**开**" not in _ok or "已接入 3 条" not in _ok:
        bad.append("已接入态没写「开 + 已接入 3 条」：%r" % _ok[:60])
    _bad_t = _tline({"external_anchor": {
        "enabled": True, "anchors": 0, "error": "FileNotFoundError: x"}})
    if "接入失败" not in _bad_t:
        bad.append("失败态没写「接入失败」")

    with _tf.TemporaryDirectory() as td:
        _md = Path(mod.save_result(_res({"external_anchor": {
            "enabled": True, "unconfigured": True, "anchors": 0,
            "error": ""}}), save_dir=td)).read_text(encoding="utf-8")
    _head = _md.split("\\n## ")[0]
    if _sm not in _head or "开（未挂锚点文件）" not in _head:
        bad.append("未挂文件态的头部没写明状态")
    for _z in ("**锚点对照**：结论", "**锚点分级**", "**triage 降级**",
               "**锚点入池**"):
        if _z in _md:
            bad.append("未挂文件时仍写了零行明细：%s" % _z)
    if "**锚点对照**：未做" not in _md:
        bad.append("未挂文件时没写「锚点对照：未做」")
    if "**锚点异常**" in _md:
        bad.append("未挂文件被渲染成「锚点异常」")

    if bad:
        for _x in bad:
            print("  ✗ [v12318] %s" % _x)
        return False
    print("  ✓ [v12318] 锚点默认开（DEFAULT + yaml）；未挂文件=干净态（不记 error、"
          "负对照仍记）；渲染四态分明；产物不写五行零、不写「锚点异常」")
    return True


'''

# ⑤ 新增判据函数（接在 v12317 恢复的判据之后）
ANCHOR = "def check_p23_units():"
assert lines.count(ANCHOR) == 1, "锚点命中 %d 次" % lines.count(ANCHOR)
_i = lines.index(ANCHOR)
lines[_i:_i] = NEW_FUNC.split("\n")
print("%-36s 插入新判据" % "check_v12318_anchor_default_on")

# ⑥ 接线
repl_block('''    if not check_v12317_und_coverage_trace():
        return 1''',
           '''    if not check_v12317_und_coverage_trace():
        return 1
    if not check_v12318_anchor_default_on():
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
assert out.count("def check_v12318_anchor_default_on(") == 1
assert out.count("check_v12318_anchor_default_on()") == 2
enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
SMOKE.write_bytes(enc)
print("死代码自检 0 处；行数 %d；CRLF %d" % (out.count("\n"), enc.count(b"\r\n")))
