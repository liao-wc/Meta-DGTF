# -*- coding: utf-8 -*-
"""v1.23.55 接线：smoke 新判据 + 变异体 M106 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12355_paused_gap():
    """[v1.23.55] `paused` 时的缺层是**待续**，不是缺陷（真缺陷不许被豁免）。

    ★ 为什么必须有它：A/B 真跑暂停时产物打了
        ❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的
        · 元：未记录原因（这是缺陷）
      可暂停时缺层是**设计**。这条提示会让人去查一个不存在的 bug，而且
      `layer_gap` 一写进产物，任何"缺层=缺陷"的下游判据都跟着误判。
    ★ 三臂（缺一不可）：
      P1 暂停 + 缺的层都在 `pending_layers` 里 ⇒ `paused_gap`，**没有** `layer_gap`
      P2 暂停 + 有一层既没产出也不在 pending 里 ⇒ 那层仍进 `layer_gap`（真缺陷）
      P3 不暂停 + 缺层 ⇒ 照旧进 `layer_gap`（旧行为逐字不变）
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('packed["paused_gap"] = list(_pause_gap)',
                "_real_gap = [e for e in missing if e not in _pause_gap]",
                '"missing": _real_gap'):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)

    def _pack(missing, paused, pend):
        return {"dispatch": {"missing": list(missing), "skipped": [],
                             "failed": {}, "requested": ["0", "1", "both", "all"]},
                "paused": bool(paused),
                "pending_layers": list(pend)}

    try:
        _eng = mod.MetaDGTF(build_cfg(False))
        # P1：暂停，缺的两层都在 pending 里 ⇒ 待续，不报缺陷
        _p = _pack(["both", "all"], True, ["both", "all"])
        _eng._layer_guard(_p)
        if _p.get("layer_gap"):
            bad.append("[P1] 暂停 + 缺层都在 pending ⇒ 仍写了 layer_gap（假警报）")
        if sorted(_p.get("paused_gap") or []) != ["all", "both"]:
            bad.append("[P1] 没记 paused_gap：%r" % (_p.get("paused_gap"),))
        # P2：暂停，但有一层既没产出也不在 pending 里 ⇒ 真缺陷仍要报
        _p2 = _pack(["both", "all"], True, ["all"])
        _eng._layer_guard(_p2)
        if sorted((_p2.get("layer_gap") or {}).get("missing") or []) != ["both"]:
            bad.append("[P2] 真缺陷被暂停豁免掉了：%r"
                       % ((_p2.get("layer_gap") or {}).get("missing"),))
        if sorted(_p2.get("paused_gap") or []) != ["all"]:
            bad.append("[P2] paused_gap 记错：%r" % (_p2.get("paused_gap"),))
        # P3：不暂停 ⇒ 旧行为（全部进 layer_gap）
        _p3 = _pack(["all"], False, [])
        _eng._layer_guard(_p3)
        if (_p3.get("layer_gap") or {}).get("missing") != ["all"]:
            bad.append("[P3] 非暂停路径的缺层没被记进 layer_gap（旧行为破了）")
        if _p3.get("paused_gap"):
            bad.append("[P3] 非暂停却记了 paused_gap")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P?] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.55 暂停待续（%d 项）" % len(bad))
        return False
    print("✓ v1.23.55 暂停待续：pending 里的缺层不报缺陷 · 真缺陷仍报红 · 旧路径不变")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.55",
     'SRC = HERE / "元DGTF-V1.23.54.py"',
     'SRC = HERE / "元DGTF-V1.23.55.py"'),
    ("插新判据",
     "def check_v12354_parallel_wall_clock():",
     NEW_CHECK + "def check_v12354_parallel_wall_clock():"),
    ("main 接线",
     "    if not check_v12354_parallel_wall_clock():\n        return 1\n",
     "    if not check_v12354_parallel_wall_clock():\n        return 1\n"
     "    if not check_v12355_paused_gap():\n        return 1\n"),
])

M106 = ('    ("M106 暂停时的缺层仍报成缺陷（假警报 / layer_gap 误写）",\n'
        '     \'                          if packed.get("paused") else [])\',\n'
        '     \'                          if False else [])  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.55",
     'SRC = HERE / "元DGTF-V1.23.54.py"',
     'SRC = HERE / "元DGTF-V1.23.55.py"'),
    ("末尾插 M106",
     "     '        if False:  # MUT'),\n]",
     "     '        if False:  # MUT'),\n" + M106 + "]"),
    ("链上新判据",
     '             "st.check_v12354_parallel_wall_clock() and "',
     '             "st.check_v12354_parallel_wall_clock() and "\n'
     '             "st.check_v12355_paused_gap() and "'),
])
print("\n接线完成。")
