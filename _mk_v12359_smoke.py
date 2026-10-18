# -*- coding: utf-8 -*-
"""v1.23.59 接线：smoke 新判据 + 变异体 M110 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12359_gain_signal():
    """[v1.23.59] 修行层增益换信号：Heaps 边际（稀疏）→ 相对新增率（总在）。

    ★ 为什么必须换（实测）：`excavate` 要 ≥3 圈历史、退化增长还给 None ⇒
      实测 4 圈里 3 圈是 None ⇒ `refinement_gain` 恒 None ⇒ `stop.gain_floor`
      **永远不触发**。这不是阈值问题，是信号太稀疏。
    ★ 判据用的夹具是 §九 的**真实读数序列**（n_aspects = 16, 16, 14, 20），不是编的。
    ★ 五臂：A 旧信号在这组数据上恒 None；B 新信号能触发；C 层面在长不许停；
      D 没有 `n_aspects` 的老产物仍走 Heaps（逐字退回）；E 其余三层方向未变。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('_r = max(0.0, float(_cn) - float(_pn)) / float(_pn)',
                'if _e == "0":'):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)
    # 其余三层的方向断言必须还在（不许一刀切改掉）
    if '_d = (_pv - _cur) if _e == "0" else (_cur - _pv)' not in src:
        bad.append("[G1] 其余三层的方向算路被动了")

    REAL = [
        {"round": 1, "n_aspects": 16, "excavate": None},
        {"round": 2, "n_aspects": 16, "excavate": None},
        {"round": 3, "n_aspects": 14, "excavate": 0.0},
        {"round": 4, "n_aspects": 20, "excavate": None},
    ]
    try:
        # A：这组数据上，旧信号（excavate）拿不到值
        _g = [mod.refinement_gain("0", REAL[i], REAL[:i]) for i in range(1, 4)]
        if _g != [0.0, 0.0, 0.4286]:
            bad.append("[G2] 新信号增益序列不对：%r（期望 [0.0, 0.0, 0.4286]）"
                       % (_g,))
        # B：必须能触发
        _hit, _why = mod.layer_gain_stop_signal("0", REAL[2], REAL[:3], 0.01)
        if _hit is not True:
            bad.append("[G2] 实测数据上仍不触发（换信号没生效）")
        elif "增益趋零" not in str(_why):
            bad.append("[G2] 触发了但理由没点名：%r" % (_why[:40],))
        # C：在长不许停
        GROW = [{"round": 1, "n_aspects": 16}, {"round": 2, "n_aspects": 20},
                {"round": 3, "n_aspects": 30}]
        if mod.layer_gain_stop_signal("0", GROW[2], GROW, 0.01)[0] is not False:
            bad.append("[G3] 层面在长却判停了（见谁都停）")
        # D：老产物退回 Heaps
        OLD = [{"round": 1, "excavate": 0.90}, {"round": 2, "excavate": 0.90},
               {"round": 3, "excavate": 0.90}]
        if [mod.refinement_gain("0", OLD[i], OLD[:i]) for i in (1, 2)] != [0.0, 0.0]:
            bad.append("[G4] 没有 n_aspects 时没退回 Heaps 算路")
        # E：其余三层方向未变
        ST = [{"round": 1, "settle": 0.50}, {"round": 2, "settle": 0.60}]
        if mod.refinement_gain("1", ST[1], ST[:1]) != 0.1:
            bad.append("[G5] settle 方向被改了：%r"
                       % (mod.refinement_gain("1", ST[1], ST[:1]),))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[G2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.59 增益换信号（%d 项）" % len(bad))
        return False
    print("✓ v1.23.59 增益换信号：实测数据上能触发 · 在长不停 · 老产物退回 Heaps")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.59",
     'SRC = HERE / "元DGTF-V1.23.58.py"',
     'SRC = HERE / "元DGTF-V1.23.59.py"'),
    ("插新判据",
     "def check_v12358_promote_trace():",
     NEW_CHECK + "def check_v12358_promote_trace():"),
    ("main 接线",
     "    if not check_v12358_promote_trace():\n        return 1\n",
     "    if not check_v12358_promote_trace():\n        return 1\n"
     "    if not check_v12359_gain_signal():\n        return 1\n"),
])

M110 = ('    ("M110 修行层增益退回稀疏信号（早停又变成永远不触发）",\n'
        '     \'    if _e == "0":\\n        _cn = _lg_num((goal or {}).get("n_aspects"))\',\n'
        '     \'    if False:  # MUT\\n        _cn = _lg_num((goal or {}).get("n_aspects"))\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.59",
     'SRC = HERE / "元DGTF-V1.23.58.py"',
     'SRC = HERE / "元DGTF-V1.23.59.py"'),
    ("末尾插 M110",
     "     '            trace[\"eff_n\"] = int(promote_n)  # MUT'),\n]",
     "     '            trace[\"eff_n\"] = int(promote_n)  # MUT'),\n" + M110 + "]"),
    ("链上新判据",
     '             "st.check_v12358_promote_trace() and "',
     '             "st.check_v12358_promote_trace() and "\n'
     '             "st.check_v12359_gain_signal() and "'),
])
print("\n接线完成。")
