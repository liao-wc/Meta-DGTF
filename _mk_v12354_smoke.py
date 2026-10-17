# -*- coding: utf-8 -*-
"""v1.23.54 接线：smoke 新判据 + 变异体 M105 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12354_parallel_wall_clock():
    """[v1.23.54] 并行跑次也能被**墙钟预算**截住，并且能**续跑**。

    ★ 为什么必须有它：`max_minutes` 原来只挂在 `_run_serial` 的**层间** ⇒ 并行模式
      （A/B/C + D~H）设了预算也照跑到天亮，宿主一回收就全丢；而 `load_resume_snapshot`
      又硬拒非 serial ⇒ 强杀后连续都续不了。**预算保护对并行是空的。**
    ★ 判据走真入口，且覆盖那条最容易假修的链：
        圈边界判墙钟 → 标记**盖到 view** → 续跑按标记**摘层** → 只重跑被摘的层
      第一版实现把标记只写在 `_budget_stop_note` 上，而 `stop_reason` 是**逐圈在
      循环体末尾**拼的、圈首 break 会跳过 ⇒ 摘层恒空 ⇒ **续跑什么都不重跑**。
      本判据当场逮到了它，所以 P2/P3 缺一不可。
    ★ 负对照：预算关 ⇒ 不 paused（否则"每到点就停"也能过）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk, _n in (("def _wall_clock_over(self) -> bool:", 1),
                    ("self._wall_clock_over()", 4),
                    ('"墙钟预算到点（第 %d 圈截断', 3),
                    ('"truncated"', 1),
                    ("_resume_serial", 3)):
        _c = src.count(_tk)
        if _c != _n:
            bad.append("[P1] 源码 %r 应出现 %d 次（实测 %d）" % (_tk, _n, _c))
    if 'if _mx > 0 and (time.time()' in src:
        bad.append("[P1] serial 还留着内联的墙钟判据（会有两份实现）")
    if '"墙钟预算" in str(getattr(_v, "stop_reason"' not in src:
        bad.append("[P1] 续跑侧没按标记摘层（截断层会被当完成复用）")

    _ck = Path(_tf.mkdtemp(prefix="v54ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v54mem_"))
    _orig_dir = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12354 并行墙钟判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v54out_")))
        c["playbook"] = {"mode": "on", "dir": str(_mem)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c.setdefault("runtime", {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    def _neps():
        _p = _mem / "episodes.jsonl"
        return len(mod.eml_read_jsonl(_p) or []) if _p.is_file() else 0

    try:
        _r1 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 2},
            parallel_mode="A", run_id="PA1", max_minutes=1e-6)
        if _r1.get("paused") is not True:
            bad.append("[P2] 并行模式到点却没标 paused（预算对并行仍无效）")
        _tr = [e for e, v in (_r1.get("views") or {}).items()
               if "墙钟预算" in str((v or {}).get("stop_reason") or "")]
        if not _tr:
            bad.append("[P2] 截断层的 stop_reason 没带标记（续跑会认不出）")
        if sorted(_tr) != sorted(_r1.get("pending_layers") or []):
            bad.append("[P2] 带标记的层 ≠ pending_layers（%r vs %r）"
                       % (sorted(_tr), sorted(_r1.get("pending_layers") or [])))
        if _neps() != 0:
            bad.append("[P2] 暂停的并行跑次写了 %d 条 episode" % _neps())
        _snap = _ck / "PA1.json"
        if not _snap.is_file():
            bad.append("[P2] 暂停快照没落盘")
            raise RuntimeError("no snapshot")
        _ran = []
        _ol = mod.MetaDGTF._run_layer

        def _spy(self, entry, n):
            _ran.append(entry)
            return _ol(self, entry, n)

        mod.MetaDGTF._run_layer = _spy
        try:
            _r2 = mod.MetaDGTF(_cfg()).run(
                _q, route=["0", "1"], rounds={"0": 1, "1": 2},
                parallel_mode="A", run_id="PA2", resume_ckpt=str(_snap))
        finally:
            mod.MetaDGTF._run_layer = _ol
        if _r2.get("resumed_serial") != "A":
            bad.append("[P3] 并行续跑没降级 / 没记 resumed_serial（%r）"
                       % (_r2.get("resumed_serial"),))
        if "0" in _ran:
            bad.append("[P3] 已完成的层 0 被重跑（白烧钱）：%r" % (_ran,))
        if "1" not in _ran:
            bad.append("[P3] 截断层 1 没重跑（分片跑永远跑不完整）：%r" % (_ran,))
        _r3 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 1},
            parallel_mode="A", run_id="PA3")
        if _r3.get("paused"):
            bad.append("[P4] 预算关的并行跑次也被标 paused（假实现）")
        if "resumed_serial" in _r3:
            bad.append("[P4] 没续跑却记了 resumed_serial")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig_dir
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.54 并行墙钟/续跑（%d 项）" % len(bad))
        return False
    print("✓ v1.23.54 并行墙钟：到点截断并留标记 · 续跑降级 serial 只重跑截断层")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.54",
     'SRC = HERE / "元DGTF-V1.23.53.py"',
     'SRC = HERE / "元DGTF-V1.23.54.py"'),
    ("插新判据",
     "def check_v12353_eml_dir_single():",
     NEW_CHECK + "def check_v12353_eml_dir_single():"),
    ("main 接线",
     "    if not check_v12353_eml_dir_single():\n        return 1\n",
     "    if not check_v12353_eml_dir_single():\n        return 1\n"
     "    if not check_v12354_parallel_wall_clock():\n        return 1\n"),
])

M105 = ('    ("M105 截断层不摘（续跑把它当完成 ⇒ 分片跑永远跑不完整）",\n'
        '     \'        if "墙钟预算" in str(getattr(_v, "stop_reason", "") or ""):\',\n'
        '     \'        if False:  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.54",
     'SRC = HERE / "元DGTF-V1.23.53.py"',
     'SRC = HERE / "元DGTF-V1.23.54.py"'),
    ("末尾插 M105",
     "     '        _d.mkdir(parents=True, exist_ok=True)'),\n]",
     "     '        _d.mkdir(parents=True, exist_ok=True)'),\n" + M105 + "]"),
    ("链上新判据",
     '             "st.check_v12353_eml_dir_single() and "',
     '             "st.check_v12353_eml_dir_single() and "\n'
     '             "st.check_v12354_parallel_wall_clock() and "'),
])
print("\n接线完成。")
