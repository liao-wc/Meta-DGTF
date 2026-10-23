# -*- coding: utf-8 -*-
"""v1.23.58 接线：smoke 新判据 + 变异体 M109 + SRC 指向。"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def patch(name, edits):
    p = HERE / name
    raw = p.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "%s 不是纯 CRLF" % name
    assert raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n0 = s.count("\n")
    for what, old, new in edits:
        c = s.count(old)
        assert c == 1, "%s / %s：命中 %d 次" % (name, what, c)
        s = s.replace(old, new)
        print("  [OK] %-18s %s" % (name, what))
    if name.endswith(".py"):
        ast.parse(s)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("       %d → %d 行" % (n0, s.count("\n")))


NEW_CHECK = '''def check_v12358_promote_trace():
    """[v1.23.58] 晋升门槛 `_eff_n` 与 shadow 拦截原因**进产物**。

    ★ 为什么必须有它：`_eff_n`（自适应后的实际门槛）原来只活在 `eml_promote` 内部，
      产物里查不到 ⇒「库 11 < 冷启 20，门槛降到 1 但被质量闸挡下」只能**推断**。
      **"我推断它降到了 1" 与 "产物里写着 1" 是两件事。**
    ★ 五类 verdict 都要能区分：`n_short` / `contra` / `quality_down` / `cost_only` /
      `promoted` —— 否则「0 升级」到底是"没东西可升"还是"有但被挡住"看不出来。
    ★ 负对照：`adaptive=False` ⇒ `eff_n == promote_n`（逐字不变）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ("trace: dict = None", '_blk["promote_trace"] = _pt',
                "晋升门槛 ≥%d%s"):
        if _tk not in src:
            bad.append("[P1] 源码缺：%s" % _tk)

    def _pb():
        return [
            {"id": "S1", "status": "shadow", "n_evidence": 0},
            {"id": "S2", "status": "shadow", "n_evidence": 5, "contra": 3},
            {"id": "S3", "status": "shadow", "n_evidence": 5,
             "quality_delta": -0.2},
            {"id": "S4", "status": "shadow", "n_evidence": 5,
             "quality_delta": 0.0, "cost_delta": -1.0},
            {"id": "S5", "status": "shadow", "n_evidence": 4,
             "quality_delta": 0.1},
        ]

    try:
        _t = {}
        _ch = mod.eml_promote(_pb(), promote_n=3, adaptive=True, trace=_t)
        if _t.get("eff_n") != 1:
            bad.append("[P2] 自适应+小库没把 eff_n 降到 1：%r" % (_t.get("eff_n"),))
        _vd = _t.get("shadow_verdicts") or {}
        _want = {"n_short": 1, "contra": 1, "quality_down": 1,
                 "cost_only": 1, "promoted": 1}
        if dict(_vd) != _want:
            bad.append("[P3] 五类 verdict 不全：%r（期望 %r）" % (dict(_vd), _want))
        if [x.get("id") for x in _ch] != ["S4", "S5"]:
            bad.append("[P3] 变更列表不对：%r" % (_ch,))
        if _t.get("n_lib") != 5 or _t.get("promote_n") != 3:
            bad.append("[P3] n_lib/promote_n 记错：%r" % (_t,))
        # 负对照：不自适应 ⇒ 门槛不降
        _t2 = {}
        mod.eml_promote(_pb(), promote_n=3, adaptive=False, trace=_t2)
        if _t2.get("eff_n") != 3:
            bad.append("[P4] 不自适应却改了门槛：%r" % (_t2.get("eff_n"),))
        # 不传 trace ⇒ 不炸、返回值正常
        _c3 = mod.eml_promote(_pb(), promote_n=3, adaptive=True)
        if _c3 != _ch:
            bad.append("[P4] 传/不传 trace 的返回值不一致：%r vs %r" % (_c3, _ch))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.58 晋升门槛出口（%d 项）" % len(bad))
        return False
    print("✓ v1.23.58 晋升门槛出口：eff_n 可读 · 五类拦截分得清 · 不自适应逐字不变")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.58",
     'SRC = HERE / "元DGTF-V1.23.57.py"',
     'SRC = HERE / "元DGTF-V1.23.58.py"'),
    ("插新判据",
     "def check_v12357_goal_trace_carry():",
     NEW_CHECK + "def check_v12357_goal_trace_carry():"),
    ("main 接线",
     "    if not check_v12357_goal_trace_carry():\n        return 1\n",
     "    if not check_v12357_goal_trace_carry():\n        return 1\n"
     "    if not check_v12358_promote_trace():\n        return 1\n"),
])

M109 = ('    ("M109 晋升门槛记成名义值（自适应降门槛查不出来）",\n'
        '     \'            trace["eff_n"] = int(_eff_n)\',\n'
        '     \'            trace["eff_n"] = int(promote_n)  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.58",
     'SRC = HERE / "元DGTF-V1.23.57.py"',
     'SRC = HERE / "元DGTF-V1.23.58.py"'),
    ("末尾插 M109",
     "     \'            view.goal_trace = [_rec]  # MUT\'),\n]",
     "     \'            view.goal_trace = [_rec]  # MUT\'),\n" + M109 + "]"),
    ("链上新判据",
     '             "st.check_v12357_goal_trace_carry() and "',
     '             "st.check_v12357_goal_trace_carry() and "\n'
     '             "st.check_v12358_promote_trace() and "'),
])
print("\n接线完成。")
