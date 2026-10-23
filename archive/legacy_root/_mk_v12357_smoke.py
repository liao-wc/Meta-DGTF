# -*- coding: utf-8 -*-
"""v1.23.57 接线：smoke 新判据 + 变异体 M108 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12357_goal_trace_carry():
    """[v1.23.57] `goal_trace` 跨圈携带 ⇒ 早停单标量判据**走得到**。

    ★ 为什么必须有它（真缺陷）：引擎**每圈新建 view**（`view = dg.run(inp)`），
      而目标读数只 append 到当圈那个 view ⇒ 下一圈就丢。产物实测：跑 4~7 圈，
      `goal_trace` 每层只有 **1** 条。而 `layer_gain_stop_signal` 的第一道门是
      `len(prev) >= _LG_STOP_FLAT_N + 1`（=3）⇒ 门恒关 ⇒
      **`stop.gain_floor` 在任何取值下都不会触发**（通道断了，不是阈值严）。

    ★ 判据拆两段（只跑真入口会误判）：
      · 真入口：`goal_trace` 条数 == `rounds_run` 且 ≥2 ⇒ 历史真接上了；
      · 纯函数：喂 3 条低增益历史 ⇒ **必须触发** ⇒ 判据本体是活的。
      mock 的产物是固定文本，修行层第 2 圈就被"复述/空转"自然停了，走不到第 3 圈 ——
      所以"触发"这一支只能靠纯函数证，不能靠真入口。
    ★ 两条负对照：只给 1 条历史 ⇒ 不触发（门还在）；`gain_floor=0` ⇒ 不触发（零行为差）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ("self._goal_hist = _hist", "view.goal_trace = list(_h)",
                "self._goal_hist = {}"):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)

    _mem = Path(_tf.mkdtemp(prefix="v57mem_"))
    _q = "冒烟题面：这件事的边界在哪里（v12357 跨圈携带判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v57out_")))
        c["playbook"] = {"mode": "off", "dir": str(_mem)}
        c.setdefault("stop", {})["gain_floor"] = 0.0
        c.setdefault("runtime", {})["live_checkpoint"] = False
        c["all_on"] = False
        return c

    try:
        _r = mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 5}, parallel_mode="serial")
        _v = (_r.get("views") or {}).get("0") or {}
        _rr = int(_v.get("rounds_run") or 0)
        _tn = len(_v.get("goal_trace") or [])
        if _tn != _rr:
            bad.append("[G2] goal_trace=%d 与 rounds_run=%d 不一致"
                       "（历史没跨圈接上）" % (_tn, _rr))
        if _tn < 2:
            bad.append("[G2] goal_trace 只有 %d 条（应随圈数增长）" % _tn)
        # 纯函数：3 条「增益低于阈值」的历史必须触发
        _prev = [{"round": 1, "excavate": 0.90},
                 {"round": 2, "excavate": 0.90},
                 {"round": 3, "excavate": 0.90}]
        _hit, _why = mod.layer_gain_stop_signal("0", _prev[-1], _prev, 0.5)
        if _hit is not True:
            bad.append("[G3] 3 条低增益历史没触发早停（判据本体不灵）")
        elif "增益趋零" not in str(_why):
            bad.append("[G3] 触发了但理由没点名：%r" % (_why[:40],))
        # 负对照
        if mod.layer_gain_stop_signal("0", _prev[-1], _prev[-1:], 0.5)[0] is not False:
            bad.append("[G4] 只给 1 条历史竟触发了（len<3 那道门破了）")
        if mod.layer_gain_stop_signal("0", _prev[-1], _prev, 0.0)[0] is not False:
            bad.append("[G4] gain_floor=0（默认关）仍触发（零行为差破了）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[G2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.57 目标读数跨圈（%d 项）" % len(bad))
        return False
    print("✓ v1.23.57 目标读数跨圈：goal_trace 随圈数增长 · 早停判据真能触发")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.57",
     'SRC = HERE / "元DGTF-V1.23.56.py"',
     'SRC = HERE / "元DGTF-V1.23.57.py"'),
    ("插新判据",
     "def check_v12356_ckpt_cumulative():",
     NEW_CHECK + "def check_v12356_ckpt_cumulative():"),
    ("main 接线",
     "    if not check_v12356_ckpt_cumulative():\n        return 1\n",
     "    if not check_v12356_ckpt_cumulative():\n        return 1\n"
     "    if not check_v12357_goal_trace_carry():\n        return 1\n"),
])

M108 = ('    ("M108 目标读数不跨圈（早停单标量永远看不到 3 条历史）",\n'
        '     \'            view.goal_trace = list(_h)\',\n'
        '     \'            view.goal_trace = [_rec]  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.57",
     'SRC = HERE / "元DGTF-V1.23.56.py"',
     'SRC = HERE / "元DGTF-V1.23.57.py"'),
    ("末尾插 M108",
     "     '{\"llm_calls\": _w_calls,  # MUT'),\n]",
     "     '{\"llm_calls\": _w_calls,  # MUT'),\n" + M108 + "]"),
    ("链上新判据",
     '             "st.check_v12356_ckpt_cumulative() and "',
     '             "st.check_v12356_ckpt_cumulative() and "\n'
     '             "st.check_v12357_goal_trace_carry() and "'),
])
print("\n接线完成。")
