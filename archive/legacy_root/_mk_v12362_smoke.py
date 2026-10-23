# -*- coding: utf-8 -*-
"""v1.23.62 接线：smoke 新判据 + 变异体 M113 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12362_contra_live():
    """[v1.23.62] `contra`（反向证据）**接活**：会累积、会拦晋升。

    ★ 为什么必须有它（死代码审计发现）：`contra` **唯一的写入点**是
      `eml_note_contra()`，而它**全项目没人调用** ⇒ `contra` 恒 0 ⇒
      `eml_promote` 里「反向证据够了不许升级」那条**永远不触发**。
      判据在、输入没人产出 —— 与"读数无出口"是同一类死法。
    ★ 关键是对照：`contra=3` 必须**拦住**升级，`contra=0` 必须**允许**升级
      —— 只有两向都测，才能证明闸是"按条件拦"而不是"见谁都拦/谁都不拦"。
    """
    import ast as _ast
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if src.count("eml_note_contra") < 2:
        bad.append("[K1] 全文仍只 1 次（没有调用点）")
    _body = ""
    for _n in _ast.walk(_ast.parse(src)):
        if isinstance(_n, _ast.FunctionDef) and _n.name == "_eml_note_use":
            _body = _ast.get_source_segment(src, _n) or ""
            break
    if "eml_note_contra(" not in _body:
        bad.append("[K1] `_eml_note_use` 里没调用它（负面证据仍不累积）")

    try:
        _pb = [{"id": "L1", "status": "active", "contra": 0}]
        for _ in range(3):
            mod.eml_note_contra(_pb, [{"id": "L1"}], why="used_but_duty_low")
        if _pb[0].get("contra") != 3:
            bad.append("[K2] 记 3 次后 contra=%r（应 3）" % (_pb[0].get("contra"),))
        if _pb[0].get("contra_last") != "used_but_duty_low":
            bad.append("[K2] 没留 contra_last 原因")

        def _mk(c):
            return [{"id": "S1", "status": "shadow", "n_evidence": 5,
                     "quality_delta": 0.2, "contra": c}]

        _b3 = _mk(3)
        if mod.eml_promote(_b3, promote_n=3) != []:
            bad.append("[K3] contra=3 仍升级了（闸不拦）")
        if _b3[0].get("status") != "shadow":
            bad.append("[K3] contra=3 状态被改：%r" % (_b3[0].get("status"),))
        _b0 = _mk(0)
        if [x.get("to") for x in mod.eml_promote(_b0, promote_n=3)] != ["active"]:
            bad.append("[K4] contra=0 也不升级（闸变成见谁都拦）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[K2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.62 反向证据接活（%d 项）" % len(bad))
        return False
    print("✓ v1.23.62 反向证据接活：contra 会累积 · contra=3 拦住 · contra=0 放行")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.62",
     'SRC = HERE / "元DGTF-V1.23.61.py"',
     'SRC = HERE / "元DGTF-V1.23.62.py"'),
    ("插新判据",
     "def check_v12361_empty_guard():",
     NEW_CHECK + "def check_v12361_empty_guard():"),
    ("main 接线",
     "    if not check_v12361_empty_guard(SRC.read_text(encoding=\"utf-8\")):\n        return 1\n"
     if False else
     "    if not check_v12361_empty_guard():\n        return 1\n",
     "    if not check_v12361_empty_guard():\n        return 1\n"
     "    if not check_v12362_contra_live():\n        return 1\n"),
])

M113 = ('    ("M113 负面证据不再累积（晋升闸的 contra 恒 0、永远不拦）",\n'
        '     \'                    eml_note_contra([_e], [_e], why="used_but_duty_low")\',\n'
        '     \'                    pass  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.62",
     'SRC = HERE / "元DGTF-V1.23.61.py"',
     'SRC = HERE / "元DGTF-V1.23.62.py"'),
    ("末尾插 M113",
     "     '        if False:  # MUT'),\n]",
     "     '        if False:  # MUT'),\n" + M113 + "]"),
    ("链上新判据",
     '             "st.check_v12361_empty_guard() and "',
     '             "st.check_v12361_empty_guard() and "\n'
     '             "st.check_v12362_contra_live() and "'),
])
print("\n接线完成。")
