# -*- coding: utf-8 -*-
"""给 smoke_test.py 打 v1.23.20 补丁：SRC 指向新版 + 新 check + main 接线。

新 check 用「打桩 dump_view_fields + 计数」做行为断言：
  dump_rounds=False ⇒ 守卫早退，桩**不被调用**（且完全静音）；
  dump_rounds=True  ⇒ 越过守卫，桩**被调用**（开关不是恒静音）。
这样不依赖 View 的字段是否齐全，也不真调 LLM。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

NEW_CHECK = '''def check_v12320_quiet_output():
    """[v1.23.20] 留痕从 verbose 拆出独立开关（默认关），进度不再被连坐。

    ① `DEFAULT_CONFIG.output.dump_rounds` 默认 False；
    ② `show_ing` / `show_manifest` 默认 False（不刷全文框）；
    ③ 行为：verbose=True + dump_rounds=False ⇒ `dump_round` 在守卫处早退，
       `dump_view_fields` **不被调用**、stdout 完全静音；
    ④ 负对照：dump_rounds=True ⇒ 越过守卫、桩**被调用**（开关不是恒静音）；
    ⑤ 接线：两个守卫都真读 `self.dump_rounds`；
    ⑥ 出厂 yaml 三键与默认一致（免得引擎关了、yaml 又开回来）。
    """
    import contextlib
    import inspect
    import io
    import types

    bad = []
    _o = mod.DEFAULT_CONFIG.get("output") or {}
    for _k in ("dump_rounds", "show_ing", "show_manifest"):
        if _o.get(_k) is not False:
            bad.append("[①/②] DEFAULT_CONFIG.output.%s=%r（应 False）" % (_k, _o.get(_k)))

    def _mk_dgtf(dump_on):
        _c = build_cfg(True)                     # verbose=True
        _c.setdefault("output", {})["dump_rounds"] = dump_on
        return mod.DGTF("0", None, _c)

    _view = types.SimpleNamespace()
    _inp = types.SimpleNamespace(round_no=1, round_role="摊开")

    _rec = {"n": 0}
    _orig_dvf = mod.dump_view_fields

    def _stub_dvf(view, emit, **kw):
        _rec["n"] += 1

    mod.dump_view_fields = _stub_dvf
    try:
        # ③ 关：守卫早退，桩不许被调，stdout 必须空
        _rec["n"] = 0
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _mk_dgtf(False).dump_round(_view, _inp)
        if _rec["n"] != 0:
            bad.append("[③] dump_rounds=False 仍往下走（桩被调 %d 次）" % _rec["n"])
        if _buf.getvalue().strip():
            bad.append("[③] dump_rounds=False 还有输出：%r" % _buf.getvalue()[:80])

        # ④ 负对照：开 ⇒ 越过守卫，桩被调 1 次
        _rec["n"] = 0
        with contextlib.redirect_stdout(io.StringIO()):
            _mk_dgtf(True).dump_round(_view, _inp)
        if _rec["n"] != 1:
            bad.append("[④] dump_rounds=True 没往下走（桩被调 %d 次，应 1）" % _rec["n"])
    finally:
        mod.dump_view_fields = _orig_dvf

    # ⑤ 两个守卫都读 self.dump_rounds
    _src = (inspect.getsource(mod.DGTF.dump_round)
            + inspect.getsource(mod.DGTF.dump_final))
    if _src.count("self.dump_rounds") != 2:
        bad.append("[⑤] 两个留痕守卫没都读 self.dump_rounds（命中 %d 次）"
                   % _src.count("self.dump_rounds"))

    # ⑥ 出厂 yaml 与默认一致
    try:
        _yl = [l.strip() for l in (HERE / "dgtf_config.yaml")
               .read_text(encoding="utf-8").splitlines()]
    except OSError:
        _yl = []
    for _k in ("show_ing: false", "show_manifest: false", "dump_rounds: false"):
        if _k not in _yl:
            bad.append("[⑥] 出厂 yaml 缺 %s" % _k)
    for _k in ("show_ing: true", "show_manifest: true"):
        if _k in _yl:
            bad.append("[⑥] 出厂 yaml 仍开着 %s" % _k)

    if bad:
        for _x in bad:
            print("  \u2717 [v12320] %s" % _x)
        return False
    print("  \u2713 [v12320] 留痕独立开关默认关：关时静音且不往下走、开时真打；"
          "show_ing/show_manifest 默认 false；yaml 与默认一致")
    return True


'''

ANCHOR_SRC = 'SRC = HERE / "元DGTF-V1.23.19.py"'
NEW_SRC = 'SRC = HERE / "元DGTF-V1.23.20.py"'
ANCHOR_INSERT = "\n\ndef check_p23_units():\n"
ANCHOR_MAIN = ("    if not check_v12319_anchor_retrieval_reachable():\n"
               "        return 1\n")
NEW_MAIN = ANCHOR_MAIN + ("    if not check_v12320_quiet_output():\n"
                          "        return 1\n")


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")

    if "check_v12320_quiet_output" in s:
        print("smoke_test 已打补丁，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[{tag}] 锚点命中 {n} 次（期望 1）"
        return s.replace(old, new)

    s = sub(ANCHOR_SRC, NEW_SRC, "SRC")
    s = sub(ANCHOR_INSERT, "\n\n" + NEW_CHECK + "def check_p23_units():\n", "插入 check")
    s = sub(ANCHOR_MAIN, NEW_MAIN, "main 接线")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("smoke_test.py OK：SRC + 新 check + 接线，共", len(out.encode("utf-8")), "字节")


if __name__ == "__main__":
    main()
