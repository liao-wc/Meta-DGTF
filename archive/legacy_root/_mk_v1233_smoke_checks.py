# -*- coding: utf-8 -*-
"""[v1.23.3] 冒烟注入器扩展：SRC → v1.23.3，并加 1 档判据。

  · `check_v1233_vote_ids` —— 三票 id 归一化（受控实验抓到的真 bug）：
      纯函数四向 + 两条生产路径接线 + **端到端错位修正** + **真票号留痕**
      + 越界弃票 + 2 个变异体。

★ 注入的代码里**不用反斜杠**：换行一律 chr(10) 拼，断行用括号。
★ 必须排在 `_mk_v1232_smoke_checks.py` **之后**跑：那个脚本从
  `def check_v1232_audit` 换到 MARK，会把 MARK 之前新加的东西一起抹掉。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_mk_v1230_smoke_checks.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

NEW_CHECK = '''def check_v1233_vote_ids(SRC=None):
    """[v1.23.3 遗留1] 三票 id 归一化 + 产物记**真票号**。

    背景：受控投票实验实测某票返回 **0 起** id ⇒ 引擎按 1 起对齐
    ⇒ 该票**整票错位一格**（第 2 条拿到本该给第 1 条的标签），且无声。
    第二处：产物 `votes[].voter` 原先是**位置**，丢一张票就重编号
    ⇒ `agree13` 比的是别的 prompt 对。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)

        # 1 纯函数四向
        assert hasattr(m, "_normalize_judgment_ids"), "缺 _normalize_judgment_ids"
        _f = m._normalize_judgment_ids
        assert _f({1: "a", 2: "b"}, 2) == ({1: "a", 2: "b"}, "1起"), "1 起应原样"
        assert _f({0: "a", 1: "b"}, 2) == ({1: "a", 2: "b"}, "0起+1"), "0 起应 +1"
        assert _f({1: "a", 9: "b"}, 2)[0] is None, "越界应判 None"
        assert _f({}, 2)[0] is None, "空应判 None"
        assert _f({0: "a", 2: "b"}, 2)[0] is None, "混合应判 None"
        print("  ✓ v1.23.3 id 归一化：纯函数四向正确")

        # 2 两条生产路径都接了它（防死代码 / 防只改一处）
        #   ★ 抠函数体带**开括号**：`def 名` 会被前缀同名函数截走（老坑）。
        def _body(nm):
            import ast as _a
            i2 = src.find("def " + nm + "(")
            assert i2 >= 0, "找不到函数 " + nm
            ln2 = src[:i2].count(chr(10)) + 1
            L2 = src.split(chr(10))
            for n2 in _a.walk(_a.parse(src)):
                if isinstance(n2, _a.FunctionDef) and n2.lineno == ln2:
                    return chr(10).join(L2[n2.lineno - 1:n2.end_lineno])
            raise AssertionError("抠不出 " + nm + " 的体")

        for _fn in ("_adjudicate_sub_tristate_multi", "_adjudicate_sub_tristate"):
            assert "_normalize_judgment_ids(" in _body(_fn), (
                _fn + " 体里没有归一化调用")
        print("  ✓ v1.23.3 id 归一化：多票 / 单票两条路径都已接线")

        # 3 ★ 端到端：0 起票必须被 +1 归一（逐票逐条对齐）
        LAB = ("decidable", "partial", "undecidable")

        class _Stub:
            def __init__(self, shift=None, bad=None, n=3):
                self.i = -1
                self.shift = shift
                self.bad = bad
                self.n = n

            def call(self, sysp, user, t, mx, json_mode=False, stage=None,
                     **k):
                self.i += 1
                base = 0 if self.i == self.shift else 1
                if self.i == self.bad:
                    base = 50
                return _json.dumps({"judgments": [
                    {"id": base + j, "reason": "r",
                     "decidability": LAB[(j + self.i) % 3]}
                    for j in range(self.n)]})

            def parse_json(self, raw):
                return _json.loads(raw)

        def _run(stub):
            o = object.__new__(m.MetaDGTF)
            o.llm = stub
            o.config = dict(m.DEFAULT_CONFIG)
            o.config["actions"] = dict(o.config["actions"])
            o.config["actions"]["tri_multi_vote"] = True
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = None
            subs = [{"id": i + 1, "question": "q" + str(i + 1),
                     "decidability": "partial"} for i in range(3)]
            o._adjudicate_sub_tristate_multi(subs, "Q")
            return o, subs

        def _lab(subs):
            return [[(v["voter"], v["label"]) for v in sorted(
                (x.get("votes") or []), key=lambda y: y["voter"])]
                for x in subs]

        want = [[(v, LAB[(j + v) % 3]) for v in (0, 1, 2)] for j in range(3)]
        _o1, _s1 = _run(_Stub(shift=1))
        got = _lab(_s1)
        assert got == want, "0 起票未归一到正确位置：" + repr(got)
        # ★ 同时钉「产物记真票号」：三票都要在（0/1/2），不是重编号后的位置
        assert all(x == 3 for x in (len(g) for g in got)), "票数不为 3"
        assert any(("0 起→+1" in str(x)) for x in _o1.pools["1"].meta), (
            "0 起归一没留痕")
        print("  ✓ v1.23.3 端到端：0 起票被 +1 归一，逐票逐条对齐且留痕")

        # 4 负对照：正常票（1 起）结果与上面**逐条相同**，且不留异常痕
        _o2, _s2 = _run(_Stub(shift=None))
        assert _lab(_s2) == want, "正常票结果与归一后不一致（归一改坏了）"
        assert not any(("id 0 起" in str(x) or "越界" in str(x))
                       for x in _o2.pools["1"].meta), "正常票不该留异常痕"
        print("  ✓ v1.23.3 负对照：正常票行为与留痕都未变（加性）")

        # 5 ★ 越界票：弃票（剩**另外两票**，且 `voter` 是真票号）+ 留痕
        _o3, _s3 = _run(_Stub(bad=1))
        want3 = [[(0, LAB[j % 3]), (2, LAB[(j + 2) % 3])] for j in range(3)]
        assert _lab(_s3) == want3, "越界票没有按『弃票 + 真票号』处理：" + repr(
            _lab(_s3))
        assert any(("越界弃票" in str(x)) for x in _o3.pools["1"].meta), (
            "越界没留痕")
        assert any(("2/3" in str(x)) for x in _o3.pools["1"].meta), (
            "可用票数没扣掉弃票")
        print("  ✓ v1.23.3 越界票：弃票 + 真票号 + 可用票数已扣除")

        # 6 变异体：抠掉「0 起 +1」分支 ⇒ 端到端判据必须判红
        _O = ("    if _ks <= set(range(0, _hi)):" + NL
              + "        return {int(k) + 1: v for k, v in judged.items()}, "
              + chr(34) + "0起+1" + chr(34))
        assert src.count(_O) == 1, "变异体锚点命中 %d 次" % src.count(_O)
        _td = _P(_tf.mkdtemp())
        _mp = _td / "mut_voteids.py"
        _mp.write_bytes(src.replace(_O, "    if False:" + NL
                                    + "        return {int(k) + 1: v "
                                    + "for k, v in judged.items()}, "
                                    + chr(34) + "0起+1" + chr(34))
                        .replace(NL, chr(13) + NL).encode("utf-8"))
        _mm = _v1221_mod(_mp)
        _mo = object.__new__(_mm.MetaDGTF)
        _mo.llm = _Stub(shift=1)
        _mo.config = dict(_mm.DEFAULT_CONFIG)
        _mo.config["actions"] = dict(_mo.config["actions"])
        _mo.config["actions"]["tri_multi_vote"] = True
        _mo.pools = {"1": _mm.Pool()}
        _mo.vp = lambda *a, **k: None
        _mo._web_gate = None
        _ms = [{"id": i + 1, "question": "q", "decidability": "partial"}
               for i in range(3)]
        _mo._adjudicate_sub_tristate_multi(_ms, "Q")
        _mg = [[(v["voter"], v["label"]) for v in sorted(
            (x.get("votes") or []), key=lambda y: y["voter"])] for x in _ms]
        assert _mg != want, "变异体『抠掉 0 起 +1』竟然没判红"
        print("  ✓ v1.23.3 变异体：抠掉 0 起 +1 ⇒ 端到端判据判红")
        return True
    except Exception as e:
        print("  ✗ v1.23.3 三票 id 归一化失败：" + type(e).__name__ + ": "
              + str(e))
        import traceback
        traceback.print_exc()
        return False


'''

_HEAD = "def check_v1233_vote_ids"

if _HEAD in s:
    _i, _j = s.index(_HEAD), s.rindex("# <<<end v123 checks>>>")
    s = s[: _i] + NEW_CHECK + s[_j:]
    print("  · CHECKS 里的 v1233 档已**就地更新**")
else:
    O = "        return False\n\n# <<<end v123 checks>>>"
    # ★ 锚点必须带**空行**：v1.23.2 的注入器在 `return False` 与 MARK 之间留了一个空行。
    assert s.count(O) == 1, "CHECKS 尾锚点 %d 次" % s.count(O)
    s = s.replace(O, "        return False\n" + NEW_CHECK
                  + "# <<<end v123 checks>>>")
    print("  · CHECKS 已加 check_v1233_vote_ids")

O2 = 'NEW_SRC_NAME = "元DGTF-V1.23.2.py"'
if O2 in s:
    assert s.count(O2) == 1
    s = s.replace(O2, 'NEW_SRC_NAME = "元DGTF-V1.23.3.py"')
    print("  · SRC -> v1.23.3")

O3 = '               "    if not check_v1232_retry():\\n        return 1\\n")'
if "if not check_v1233_vote_ids()" in s:
    print("  · 守卫已含 vote_ids，跳过")
else:
    assert s.count(O3) == 1, "守卫块锚点 %d 次" % s.count(O3)
    s = s.replace(O3,
                  '               "    if not check_v1232_retry():\\n'
                  '        return 1\\n"\n'
                  '               "    if not check_v1233_vote_ids():\\n'
                  '        return 1\\n")')
    print("  · 守卫块 +check_v1233_vote_ids")

P.write_bytes(s.encode("utf-8"))
import ast  # noqa: E402
ast.parse(s)
print("[done] v1.23.3 冒烟注入器已扩展")
