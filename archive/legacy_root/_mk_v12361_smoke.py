# -*- coding: utf-8 -*-
"""v1.23.61 接线：smoke 新判据 + 变异体 M112 + SRC 指向。"""
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
    out = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("       %d → %d 行" % (n0, s.count("\n")))


NEW_CHECK = '''def check_v12361_empty_guard():
    """[v1.23.61] 空题**拒绝运行**（不凭空产出、不花钱）。

    ★ 为什么必须有它（健壮性探针发现）：退化输入 9 例没一个打挂引擎，但
      **`run("")` 照样跑了、产出 2 个候选** —— 空题没有可研究的东西，跑下去
      只会产出凭空编造的候选（违背「不假装」红线），而且白花一次调用。
      app 那边有挡（`server.py` 400），但**引擎是库**，任何脚本都能直接传空串。
    ★ 最关键的一条断言是 **零调用**：拒绝必须是免费的。
    ★ 负对照：单字题不许被拒（守卫不能变成"见谁都拒"）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('"reason": "empty_question"',
                'if not str(question or "").strip():'):
        if _tk not in src:
            bad.append("[Q1] 源码缺：%s" % _tk)

    _n = [0]
    _orig_call = mod.LLM.call

    def _counting(*a, **kw):
        _n[0] += 1
        return _orig_call(*a, **kw)

    mod.LLM.call = _counting

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="q61o_")))
        _m = Path(_tf.mkdtemp(prefix="q61m_"))
        c["playbook"] = {"mode": "off", "dir": str(_m)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_m)
        c.setdefault("runtime", {})["live_checkpoint"] = False
        c["all_on"] = False
        return c

    try:
        _n[0] = 0
        _r = mod.MetaDGTF(_cfg()).run(
            "", route=["0"], rounds={"0": 1}, parallel_mode="serial")
        if (_r.get("refused") or {}).get("reason") != "empty_question":
            bad.append("[Q2] 空题没被拒：refused=%r" % (_r.get("refused"),))
        if _r.get("views"):
            bad.append("[Q2] 空题仍产出了视图：%r" % (list(_r.get("views") or {}),))
        if _n[0] != 0:
            bad.append("[Q2] 拒绝时仍发生了 %d 次 LLM 调用（花冤枉钱）" % _n[0])
        if _r.get("llm_calls") != 0:
            bad.append("[Q2] 产物 llm_calls=%r（应 0）" % (_r.get("llm_calls"),))
        # 纯空白同样拒
        _n[0] = 0
        _r2 = mod.MetaDGTF(_cfg()).run(
            "   \\n\\t ", route=["0"], rounds={"0": 1}, parallel_mode="serial")
        if (_r2.get("refused") or {}).get("reason") != "empty_question":
            bad.append("[Q2] 纯空白没被拒：refused=%r" % (_r2.get("refused"),))
        # 负对照：单字题照常跑
        _r3 = mod.MetaDGTF(_cfg()).run(
            "熵", route=["0"], rounds={"0": 1}, parallel_mode="serial")
        if _r3.get("refused"):
            bad.append("[Q3] 单字题被误拒：%r" % (_r3.get("refused"),))
        if not _r3.get("views"):
            bad.append("[Q3] 单字题没产出视图")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[Q2] 异常：%r" % (_ex,))
    finally:
        mod.LLM.call = _orig_call
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.61 空题守卫（%d 项）" % len(bad))
        return False
    print("✓ v1.23.61 空题守卫：拒绝 + 零调用 + 非空题不受影响")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.61",
     'SRC = HERE / "元DGTF-V1.23.60.py"',
     'SRC = HERE / "元DGTF-V1.23.61.py"'),
    ("插新判据",
     "def check_v12360_layer_progress():",
     NEW_CHECK + "def check_v12360_layer_progress():"),
    ("main 接线",
     "    if not check_v12360_layer_progress():\n        return 1\n",
     "    if not check_v12360_layer_progress():\n        return 1\n"
     "    if not check_v12361_empty_guard():\n        return 1\n"),
])

M112 = ('    ("M112 空题守卫失效（空题照跑、凭空产出）",\n'
        '     \'        if not str(question or "").strip():\',\n'
        '     \'        if False:  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.61",
     'SRC = HERE / "元DGTF-V1.23.60.py"',
     'SRC = HERE / "元DGTF-V1.23.61.py"'),
    ("末尾插 M112",
     "     '           \"layer_progress\": {},  # MUT'),\n]",
     "     '           \"layer_progress\": {},  # MUT'),\n" + M112 + "]"),
    ("链上新判据",
     '             "st.check_v12360_layer_progress() and "',
     '             "st.check_v12360_layer_progress() and "\n'
     '             "st.check_v12361_empty_guard() and "'),
])
print("\n接线完成。")
