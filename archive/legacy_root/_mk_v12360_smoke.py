# -*- coding: utf-8 -*-
"""v1.23.60 接线：smoke 新判据 + 变异体 M111 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12360_layer_progress():
    """[v1.23.60] 快照记**层内进度**，且续跑行为一个字没变。

    ★ 为什么要有它：检查点原来只在**层完成**时才有该层状态 ⇒ 一层跑到第 5 圈被杀，
      快照里只知道"这层没完成"，**不知道死在第几圈**；估预算也只能按层不按圈
      （实测一层 4~7 圈，时长差 2 倍）。
    ★ 这一版只**记录**、不恢复：圈内恢复的等价性证不了（`seeds`/`carry` 由上一圈
      View 派生、不是纯函数 ⇒ 会得到另一条轨迹却挂着同一 run_id），见
      `docs/圈内检查点-设计.md` §三。所以判据里**专门有一条**钉"续跑侧没读它"。
    """
    import ast as _ast
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('"layer_progress": dict(getattr(engine, "_layer_progress", None) or {})',
                '"goal_hist": {str(_k): list(_v or [])',
                "self._layer_progress = {}"):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)
    # 抠函数体走 AST（字符串切会把类方法全吞进来 ⇒ 判据测的是整份文件）
    _tree = _ast.parse(src)
    _body = ""
    for _n in _ast.walk(_tree):
        if isinstance(_n, _ast.FunctionDef) and _n.name == "load_resume_snapshot":
            _body = _ast.get_source_segment(src, _n) or ""
            break
    if not _body:
        bad.append("[G1] 取不到 load_resume_snapshot 函数体")
    elif "layer_progress" in _body or "goal_hist" in _body:
        bad.append("[G1] 续跑侧读了层内进度 ⇒ 那就不是'只记不恢复'了")

    _ck = Path(_tf.mkdtemp(prefix="v60ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v60mem_"))
    _orig = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12360 层内进度判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v60out_")))
        c["playbook"] = {"mode": "off", "dir": str(_mem)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c.setdefault("runtime", {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    try:
        _rid = "CKSM60"
        mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 3}, parallel_mode="serial",
            run_id=_rid)
        _p = _ck / ("%s.json" % _rid)
        if not _p.is_file():
            bad.append("[G2] 快照没落盘")
            raise RuntimeError("no snapshot")
        _d = json.loads(_p.read_text(encoding="utf-8"))
        _v0 = (_d.get("views") or {}).get("0") or {}
        _rr = int(_v0.get("rounds_run") or 0)
        _lp = (_d.get("layer_progress") or {}).get("0") or {}
        if int(_lp.get("rounds_done") or -1) != _rr:
            bad.append("[G2] layer_progress.rounds_done=%r 与 rounds_run=%d 不一致"
                       % (_lp.get("rounds_done"), _rr))
        if _rr < 1:
            bad.append("[G2] 该层一圈都没跑（前提不成立）")
        _gh = (_d.get("goal_hist") or {}).get("0") or []
        if len(_gh) != _rr:
            bad.append("[G2] goal_hist=%d 条，应等于 rounds_run=%d"
                       % (len(_gh), _rr))
        _rs = mod.load_resume_snapshot(str(_p), str(_mem))
        if set(_rs) != {"ok", "why", "views", "pools", "llm_calls", "llm_tokens"}:
            bad.append("[G3] load_resume_snapshot 返回键变了：%r" % (sorted(_rs),))
        if _rs.get("ok") is not False:
            bad.append("[G3] 已完成的快照竟可续（既有行为被改坏）：ok=%r"
                       % (_rs.get("ok"),))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[G2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.60 层内进度（%d 项）" % len(bad))
        return False
    print("✓ v1.23.60 层内进度：rounds_done 可读 · goal_hist 进快照 · 续跑侧未读")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.60",
     'SRC = HERE / "元DGTF-V1.23.59.py"',
     'SRC = HERE / "元DGTF-V1.23.60.py"'),
    ("插新判据",
     "def check_v12359_gain_signal():",
     NEW_CHECK + "def check_v12359_gain_signal():"),
    ("main 接线",
     "    if not check_v12359_gain_signal():\n        return 1\n",
     "    if not check_v12359_gain_signal():\n        return 1\n"
     "    if not check_v12360_layer_progress():\n        return 1\n"),
])

M111 = ('    ("M111 快照不记层内进度（被杀后看不见死在第几圈）",\n'
        '     \'           "layer_progress": dict(getattr(engine, "_layer_progress", None) or {}),\',\n'
        '     \'           "layer_progress": {},  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.60",
     'SRC = HERE / "元DGTF-V1.23.59.py"',
     'SRC = HERE / "元DGTF-V1.23.60.py"'),
    ("末尾插 M111",
     "     '    if False:  # MUT\\n        _cn = _lg_num((goal or {}).get(\"n_aspects\"))'),\n]",
     "     '    if False:  # MUT\\n        _cn = _lg_num((goal or {}).get(\"n_aspects\"))'),\n"
     + M111 + "]"),
    ("链上新判据",
     '             "st.check_v12359_gain_signal() and "',
     '             "st.check_v12359_gain_signal() and "\n'
     '             "st.check_v12360_layer_progress() and "'),
])
print("\n接线完成。")
