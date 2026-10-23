# -*- coding: utf-8 -*-
"""v1.23.56 接线：smoke 新判据 + 变异体 M107 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12356_ckpt_cumulative():
    """[v1.23.56] 快照记账**跨窗口累计**（否则"被杀跑次也能结算成本"是假的）。

    ★ 为什么必须有它：`llm_calls` 取自 `self.llm.total_calls`，那是**按实例**的
      计数器；续跑新建实例就归零 ⇒ 第二个窗口的快照只记本窗口。
      实测（A/B 真跑）：这条 run_id 实际花了 230 calls，快照里写的是 97。
      按这个数结算成本，前面那个窗口的钱**查不到**。
    ★ 判据走真入口（两窗口，都极小预算 ⇒ 都 paused），并拆两个口径：
        `llm_calls` = 基线 + 本窗口（结算用）
        `window_calls` = 本窗口（分析用）
      负对照：第二窗口 `window_calls` 必须**严格小于** `llm_calls`
      —— 否则两个字段写的是同一个东西，等于没拆。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('"window_calls": _w_calls,',
                '"llm_calls": int(_base.get("calls") or 0) + _w_calls,',
                "self._ck_base = {",
                '_out["llm_calls"] = int(_d.get("llm_calls") or 0)'):
        if _tk not in src:
            bad.append("[C1] 源码缺：%s" % _tk)

    _ck = Path(_tf.mkdtemp(prefix="v56ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v56mem_"))
    _orig = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12356 记账累计判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v56out_")))
        c["playbook"] = {"mode": "off", "dir": str(_mem)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c.setdefault("runtime", {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    try:
        _rid = "CKSM56"
        mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=_rid, max_minutes=1e-6)
        _p = _ck / ("%s.json" % _rid)
        if not _p.is_file():
            bad.append("[C2] 第一窗口没落快照")
            raise RuntimeError("no snapshot")
        _d1 = json.loads(_p.read_text(encoding="utf-8"))
        _c1 = int(_d1.get("llm_calls") or 0)
        if _c1 <= 0:
            bad.append("[C2] 第一窗口 llm_calls 为 0（前提不成立）")
        if int(_d1.get("window_calls") or -1) != _c1:
            bad.append("[C2] 首窗口 window_calls(%r) != llm_calls(%r)"
                       % (_d1.get("window_calls"), _c1))
        mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=_rid, resume_ckpt=str(_p), max_minutes=1e-6)
        _d2 = json.loads(_p.read_text(encoding="utf-8"))
        _c2 = int(_d2.get("llm_calls") or 0)
        _w2 = int(_d2.get("window_calls") or 0)
        if _c2 != _c1 + _w2:
            bad.append("[C3] 第二窗口不是累计：llm_calls=%d，基线%d+本窗口%d=%d"
                       % (_c2, _c1, _w2, _c1 + _w2))
        if not (_w2 < _c2):
            bad.append("[C3] window_calls(%d) 没比 llm_calls(%d) 小"
                       "（两个口径没分开）" % (_w2, _c2))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[C2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.56 记账累计（%d 项）" % len(bad))
        return False
    print("✓ v1.23.56 记账累计：第二窗口 = 基线 + 本窗口 · window_calls 单独可读")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.56",
     'SRC = HERE / "元DGTF-V1.23.55.py"',
     'SRC = HERE / "元DGTF-V1.23.56.py"'),
    ("插新判据",
     "def check_v12355_paused_gap():",
     NEW_CHECK + "def check_v12355_paused_gap():"),
    ("main 接线",
     "    if not check_v12355_paused_gap():\n        return 1\n",
     "    if not check_v12355_paused_gap():\n        return 1\n"
     "    if not check_v12356_ckpt_cumulative():\n        return 1\n"),
])

M107 = ('    ("M107 快照记账不累计（续跑把前面的钱抹掉）",\n'
        '     \'                 "llm_calls": int(_base.get("calls") or 0) + _w_calls,\',\n'
        '     \'                 "llm_calls": _w_calls,  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.56",
     'SRC = HERE / "元DGTF-V1.23.55.py"',
     'SRC = HERE / "元DGTF-V1.23.56.py"'),
    ("末尾插 M107",
     "     '                          if False else [])  # MUT'),\n]",
     "     '                          if False else [])  # MUT'),\n" + M107 + "]"),
    ("链上新判据",
     '             "st.check_v12355_paused_gap() and "',
     '             "st.check_v12355_paused_gap() and "\n'
     '             "st.check_v12356_ckpt_cumulative() and "'),
])
print("\n接线完成。")
