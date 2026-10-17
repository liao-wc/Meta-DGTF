# -*- coding: utf-8 -*-
"""v1.23.51 接线：smoke 新判据 + 变异体 M102 + 三处 SRC/版本指向。

改三个文件（全部走 read_bytes → LF → 改 → CRLF → write_bytes）：
  1) smoke_test.py   ：SRC 指 v1.23.51；插 check_v12351_eml_once_per_run；接进 main
  2) _mut_v12332.py  ：SRC 指 v1.23.51；末尾插 M102；链上新判据

幂等：每个替换都先断言「目标串命中 1 次」，重复跑会因命中 0 次而报错停手。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def patch(name, edits, crlf=True):
    p = HERE / name
    raw = p.read_bytes()
    if crlf:
        assert raw.count(b"\r\n") == raw.count(b"\n"), "%s 不是纯 CRLF" % name
        assert raw.count(b"\r\r\n") == 0, "%s 有 CRCRLF" % name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n0 = s.count("\n")
    for what, old, new in edits:
        c = s.count(old)
        assert c == 1, "%s / %s：命中 %d 次（要求 1）" % (name, what, c)
        s = s.replace(old, new)
        print("  [OK] %-10s %s" % (name, what))
    if name.endswith(".py"):
        ast.parse(s)
    out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
    if crlf:
        assert out.count(b"\r\n") == out.count(b"\n")
        assert out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("       %d → %d 行" % (n0, s.count("\n")))


# ── 新判据正文 ──────────────────────────────────────────────────────
NEW_CHECK = '''def check_v12351_eml_once_per_run():
    """[v1.23.51] 一个跑次只学一条 episode（`_eml_finish` 幂等守卫）。

    ★ 为什么必须有它：A/B 真跑把 `_eml_finish` 调了两次 ⇒ 每个跑次写出两条
      episode、`used_outcomes` 与 weight 被罚两遍，事后只能手工清账（见
      `_fix_eml_dup_20261016.py`）。只修调用方防不住**同类**（任何调用方都可能
      重调），所以守卫落在引擎里；本判据守的是「一个跑次一条证据」这个不变量。
    ★ 判据是**行为级、逐字节**的：同一份 result 连调两次 ⇒ 第二次**盘上一个
      字节都不许变**。三条对照把「一律跳过」这种假实现排除掉：
      换 run_id 照写 / 同 run_id 但读数不同照写（`paused` 后的完整样本必须能进库）。
    ★ 取材是四份文件**逐字节**比，不是数条数 —— 条数不变但内容被改也是错。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _tk in ('_blk["dup_skipped"] = True',
                "_old_eps = eml_read_jsonl(_dir / _EML_EPISODES)",
                '{k: v for k, v in _ep.items() if k != "t"}'):
        if _tk not in src:
            bad.append("[E1] 源码缺：%s" % _tk)
    try:
        _i_lk = src.index("_lk.__enter__()")
        _i_g = src.index('_blk["dup_skipped"] = True')
        _i_ap = src.index("eml_append_jsonl(_dir / _EML_EPISODES, _ep)")
        if not (_i_lk < _i_g < _i_ap):
            bad.append("[E1] 守卫位置不对（要求 锁 < 守卫 < 写 episode）")
    except Exception as _ex:
        bad.append("[E1] 定位失败：%r" % (_ex,))

    def _mkres(rid, cut=("1",)):
        return {"id": rid,
                "question": "如何利用AI来帮助人类实现财富自由",
                "route": ["0", "1", "both", "all"],
                "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
                "dispatch": {"_parallel_mode": "serial"},
                "views": {e: {"stop_reason": ("体力耗尽（3 圈走满）"
                                              if e in cut else "自然安住"),
                              "duty": {"S": 0.1 if e in ("0", "1") else 0.5}}
                          for e in ("0", "1", "both", "all")},
                "pools": {"1": {"anchors": [], "web_results": []}},
                "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
                "_auto_dispatch": {"_history": {}}}
    _d = Path(_tf.mkdtemp(prefix="v51eml_"))
    try:
        _cfg = dict(mod.DEFAULT_CONFIG)
        _cfg["playbook"] = {"mode": "on", "dir": str(_d), "top_k": 3,
                            "promote_n": 3, "halflife_days": 14.0}
        _eng = mod.MetaDGTF(_cfg)
        for _i in range(1, 5):
            _eng._eml_finish(_mkres("RUN%d" % _i))
        _n4 = len(mod.eml_read_jsonl(_d / "episodes.jsonl"))
        if _n4 != 4:
            bad.append("[E2] 4 跑应写 4 条 episode（实测 %d）" % _n4)
        _eng._eml_prepare("如何利用AI来帮助人类实现财富自由")
        _eng._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4})
        _r5 = _mkres("RUN5")
        _b1 = _eng._eml_finish(_r5)
        _f = ("episodes.jsonl", "nogoods.jsonl", "playbook.jsonl", "MEMORY.md")
        _s1 = {k: (_d / k).read_bytes() for k in _f if (_d / k).is_file()}
        _b2 = _eng._eml_finish(_r5)
        _s2 = {k: (_d / k).read_bytes() for k in _f if (_d / k).is_file()}
        if not (_b1.get("used") or []):
            bad.append("[E2] 第 5 跑没用上条目（该判据测不到 used_outcomes）")
        if _b2.get("dup_skipped") is not True:
            bad.append("[E2] 第二次调用没标 dup_skipped")
        if _s1 != _s2:
            bad.append("[E2] 第二次调用改了盘：%r"
                       % (sorted(k for k in _s1 if _s1[k] != _s2.get(k)),))
        _n5 = len(mod.eml_read_jsonl(_d / "episodes.jsonl"))
        if _n5 != 5:
            bad.append("[E2] 同一跑次写了两条 episode（5 跑实测 %d 条）" % _n5)
        # 对照一：换 run_id ⇒ 照写（否则「一律跳过」也能过）
        _b3 = _eng._eml_finish(_mkres("RUN6"))
        if _b3.get("dup_skipped"):
            bad.append("[E3] 换 run_id 被判成重复（守卫写成了「一律跳过」）")
        if len(mod.eml_read_jsonl(_d / "episodes.jsonl")) != 6:
            bad.append("[E3] RUN6 没写库")
        # 对照二：同 run_id 但读数不同 ⇒ 照写（paused 半程样本可被完整样本补上）
        _b4 = _eng._eml_finish(_mkres("RUN5", cut=("0", "1", "both", "all")))
        if _b4.get("dup_skipped"):
            bad.append("[E4] 读数不同的同 run_id 被挡掉（完整样本进不了库）")
        if len(mod.eml_read_jsonl(_d / "episodes.jsonl")) != 7:
            bad.append("[E4] 读数不同的 RUN5 没写库")
        # 对照三：used_outcomes 里每个 run 至多 1 条
        _dup = []
        for _e in (mod.eml_read_jsonl(_d / "playbook.jsonl") or []):
            _c = {}
            for _x in (_e.get("used_outcomes") or []):
                _r = str(_x.get("run") or "")
                _c[_r] = _c.get(_r, 0) + 1
            if any(v > 1 for v in _c.values()):
                _dup.append((_e.get("id"), _c))
        if _dup:
            bad.append("[E5] used_outcomes 有 run 记了两次：%r" % (_dup[:3],))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[E2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.51 EML 幂等（%d 项）" % len(bad))
        return False
    print("✓ v1.23.51 EML 幂等：同一跑次第二次调用零改动 · 换 run_id/换读数照写")
    return True


'''

# ── 1) smoke_test.py ────────────────────────────────────────────────
patch("smoke_test.py", [
    ("SRC 指 v1.23.51",
     'SRC = HERE / "元DGTF-V1.23.50.py"',
     'SRC = HERE / "元DGTF-V1.23.51.py"'),
    ("插新判据",
     "def check_v12350_resume():",
     NEW_CHECK + "def check_v12350_resume():"),
    ("main 接线",
     "    if not check_v12350_resume():\n        return 1\n",
     "    if not check_v12350_resume():\n        return 1\n"
     "    if not check_v12351_eml_once_per_run():\n        return 1\n"),
])

# ── 2) _mut_v12332.py ───────────────────────────────────────────────
M102 = ('    ("M102 幂等守卫失效（同跑次写两条 episode / weight 罚两遍）",\n'
        '     \'                if _sig_old == _sig_new:\',\n'
        '     \'                if False:  # MUT\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.51",
     'SRC = HERE / "元DGTF-V1.23.50.py"',
     'SRC = HERE / "元DGTF-V1.23.51.py"'),
    ("末尾插 M102",
     '     \'            if False:  # MUT\'),\n]',
     '     \'            if False:  # MUT\'),\n' + M102 + ']'),
    ("链上新判据",
     '             "st.check_v12350_resume() and "',
     '             "st.check_v12350_resume() and "\n'
     '             "st.check_v12351_eml_once_per_run() and "'),
])
print("\n接线完成。")
