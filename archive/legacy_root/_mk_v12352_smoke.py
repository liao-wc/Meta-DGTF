# -*- coding: utf-8 -*-
"""v1.23.52 接线：smoke 新判据 + 变异体 M103 + SRC 指向。

同前：每个替换先断言命中 1 次，CRLF 往返，AST 自检。
"""
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


NEW_CHECK = '''def check_v12352_paused_no_eml():
    """[v1.23.52] `paused` 跑次不写 EML 库（半程样本不是证据）。

    ★ 为什么必须有它：v1.23.51 只保证「不重复调用就不多写」。墙钟预算暂停的跑次
      仍会写一条**半程样本**；续跑跑完后同一个 `run_id` 又写一条完整样本（读数
      不同 ⇒ 幂等守卫按设计放行）⇒ **一个跑次两条证据**，`used_outcomes` 记两笔、
      weight 罚两遍。清账脚本收拾的正是这一类。
    ★ 判据走**真入口**：`run(max_minutes=极小)` 真的暂停一次，再看库。
      负对照（预算关的正常跑 ⇒ 照写）把「一律不写」这种假实现排除掉。
    ★ 位置也是判据：守卫必须在 `off` 之后、**取锁之前** —— 暂停的跑次连目录都
      不该建，更不该去抢锁。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('_blk["skipped_paused"] = True',
                'result.get("paused")',
                'result.get("pending_layers")'):
        if _tk not in src:
            bad.append("[P1] 源码缺：%s" % _tk)
    try:
        _i_off = src.index('        if _mode == "off":')
        _i_pz = src.index('_blk["skipped_paused"] = True')
        _i_lock = src.index("_lk = eml_lock(dirpath=_dir)")
        if not (_i_off < _i_pz < _i_lock):
            bad.append("[P1] 守卫位置不对（要求 off → paused → 取锁）")
    except Exception as _ex:
        bad.append("[P1] 定位失败：%r" % (_ex,))

    _mem = Path(_tf.mkdtemp(prefix="v52mem_"))
    _ck = Path(_tf.mkdtemp(prefix="v52ck_"))
    _orig_dir = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12352 暂停不写库判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v52out_")))
        c["playbook"] = {"mode": "on", "dir": str(_mem), "top_k": 3,
                         "promote_n": 3, "halflife_days": 14.0}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c["all_on"] = False
        return c

    def _n():
        _p = _mem / "episodes.jsonl"
        return len(mod.eml_read_jsonl(_p) or []) if _p.is_file() else 0

    try:
        _r1 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 1},
            parallel_mode="serial", run_id="PZ1", max_minutes=1e-6)
        if _r1.get("paused") is not True:
            bad.append("[P2] 预算到点却没标 paused（前提不成立）")
        if not (_r1.get("playbook") or {}).get("skipped_paused"):
            bad.append("[P2] paused 跑次没被跳过（会写半程样本）")
        if _n() != 0:
            bad.append("[P2] paused 跑次写了 %d 条 episode" % _n())
        _r2 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 1},
            parallel_mode="serial", run_id="PZ2")
        if (_r2.get("playbook") or {}).get("skipped_paused"):
            bad.append("[P3] 正常跑被当暂停跳过（写成了「一律不写」）")
        if _n() != 1:
            bad.append("[P3] 正常跑没写 episode（实测 %d）" % _n())
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig_dir
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.52 暂停不写库（%d 项）" % len(bad))
        return False
    print("✓ v1.23.52 暂停不写库：预算到点零写入 · 正常跑照写")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.52",
     'SRC = HERE / "元DGTF-V1.23.51.py"',
     'SRC = HERE / "元DGTF-V1.23.52.py"'),
    ("插新判据",
     "def check_v12351_eml_once_per_run():",
     NEW_CHECK + "def check_v12351_eml_once_per_run():"),
    ("main 接线",
     "    if not check_v12351_eml_once_per_run():\n        return 1\n",
     "    if not check_v12351_eml_once_per_run():\n        return 1\n"
     "    if not check_v12352_paused_no_eml():\n        return 1\n"),
])

M103 = ('    ("M103 暂停跑次照样写库（半程样本入库 / weight 罚两遍）",\n'
        '     \'        if isinstance(result, dict) and (result.get("paused")\\n\'\n'
        '     \'                                         or result.get("pending_layers")):\',\n'
        '     \'        if False:  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.52",
     'SRC = HERE / "元DGTF-V1.23.51.py"',
     'SRC = HERE / "元DGTF-V1.23.52.py"'),
    ("末尾插 M103",
     "     '                if False:  # MUT'),\n]",
     "     '                if False:  # MUT'),\n" + M103 + "]"),
    ("链上新判据",
     '             "st.check_v12351_eml_once_per_run() and "',
     '             "st.check_v12351_eml_once_per_run() and "\n'
     '             "st.check_v12352_paused_no_eml() and "'),
])
print("\n接线完成。")
