# -*- coding: utf-8 -*-
"""v1.23.53 接线：smoke 新判据 + 变异体 M104 + SRC 指向。"""
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


NEW_CHECK = '''def check_v12353_eml_dir_single():
    """[v1.23.53] 记忆库目录**一处解析**（bandit 不再偷偷写回仓库）。

    ★ 为什么必须有它：以前 episode/playbook 走 `playbook.dir`，bandit 却只看
      `auto.bandit.dir`、空则 `eml_dir()`（**恒指仓库**）⇒ 任何设了 `playbook.dir`
      的调用方（冒烟、A/B 脚本、想隔离库的人）都会让 bandit 偷偷写生产库。
      冒烟隔离因此要三个旋钮，漏一个就污染 —— 这类「漏一格」的事故本项目栽过。
    ★ 判据分两半：
      · 源码：唯一解析函数存在、三个点都走它、**没有残留的 eml_dir() 回落**；
      · 行为（真入口）：`MetaDGTF(cfg)` 的**载入**必须读到 `playbook.dir` 里那份，
        `_save_bandit` 也必须落在那儿，而 `eml_dir()` 那个点**一个字节都不许写**。
      负对照：显式 `auto.bandit.dir` 仍然优先（显式赢了才用显式的）。
    ★ 测试自身把 `mod.eml_dir` 指到临时目录 —— 判据**不看**生产 `dgtf_memory/`。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if src.count("def eml_store_dir(cfg=None) -> Path:") != 1:
        bad.append("[B1] 缺唯一解析 eml_store_dir")
    if src.count("eml_store_dir(self.config)") != 3:
        bad.append("[B1] 走统一解析的点应 3 处（实测 %d）"
                   % src.count("eml_store_dir(self.config)"))
    if '(cfg or {}).get("dir") or eml_dir()' in src:
        bad.append("[B1] 仍有地方直接回落 eml_dir()（两处解析没收敛）")

    _pdir = Path(_tf.mkdtemp(prefix="v53p_"))
    _fake = Path(_tf.mkdtemp(prefix="v53r_"))
    _orig = mod.eml_dir
    mod.eml_dir = lambda base=None: _fake
    try:
        def _cfg(pdir="", bdir=""):
            c = build_cfg(False)
            c["playbook"] = {"mode": "shadow", "dir": str(pdir)}
            c.setdefault("auto", {}).setdefault("bandit", {})
            c["auto"]["bandit"]["enabled"] = True
            c["auto"]["bandit"]["dir"] = str(bdir)
            c["all_on"] = False
            return c

        _k = len(mod._BANDIT_ARMS)
        (_pdir / mod._BANDIT_FILE).write_text(json.dumps(
            {"t": 1, "n": [9] + [0] * (_k - 1),
             "mean": [0.5] * _k, "cost": [1.0] * _k}), encoding="utf-8")
        _e = mod.MetaDGTF(_cfg(pdir=_pdir))
        if not _e._bandit or int(_e._bandit.n[0]) != 9:
            bad.append("[B2] 载入没走 playbook.dir（n[0]=%r）"
                       % (int(_e._bandit.n[0]) if _e._bandit else None,))
        _bb = mod._load_bandit(_e._bandit_cfg, mod.eml_store_dir(_e.config))
        _bb.n[1] = 7
        mod._save_bandit(_bb, _e._bandit_cfg, mod.eml_store_dir(_e.config))
        _f = _pdir / mod._BANDIT_FILE
        if not _f.is_file():
            bad.append("[B2] 落盘没进 playbook.dir")
        elif int(json.loads(_f.read_text(encoding="utf-8"))["n"][1]) != 7:
            bad.append("[B2] 落盘内容不是本次那份")
        if (_fake / mod._BANDIT_FILE).is_file():
            bad.append("[B2] 还是写了 eml_dir()（隔离仍靠第三个旋钮）")
        _b2 = Path(_tf.mkdtemp(prefix="v53b_"))
        _e2 = mod.MetaDGTF(_cfg(pdir=_pdir, bdir=_b2))
        if not _e2._bandit or int(_e2._bandit.n[0]) != 0:
            bad.append("[B3] 显式 auto.bandit.dir 没优先（读到了 pdir 那份）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[B2] 异常：%r" % (_ex,))
    finally:
        mod.eml_dir = _orig
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.53 记忆库目录一处解析（%d 项）" % len(bad))
        return False
    print("✓ v1.23.53 记忆库目录一处解析：bandit 跟着 playbook.dir · 显式 dir 仍优先")
    return True


'''

patch("smoke_test.py", [
    ("SRC 指 v1.23.53",
     'SRC = HERE / "元DGTF-V1.23.52.py"',
     'SRC = HERE / "元DGTF-V1.23.53.py"'),
    ("插新判据",
     "def check_v12352_paused_no_eml():",
     NEW_CHECK + "def check_v12352_paused_no_eml():"),
    ("main 接线",
     "    if not check_v12352_paused_no_eml():\n        return 1\n",
     "    if not check_v12352_paused_no_eml():\n        return 1\n"
     "    if not check_v12353_eml_dir_single():\n        return 1\n"),
])

M104 = ('    ("M104 bandit 目录不回退到 playbook.dir（隔离漏一格）",\n'
        '     \'        _d = Path(str((cfg or {}).get("dir") or fallback or eml_dir()))\\n\'\n'
        '     \'        _d.mkdir(parents=True, exist_ok=True)\',\n'
        '     \'        _d = Path(str((cfg or {}).get("dir") or eml_dir()))  # MUT\\n\'\n'
        '     \'        _d.mkdir(parents=True, exist_ok=True)\'),\n')

patch("_mut_v12332.py", [
    ("SRC 指 v1.23.53",
     'SRC = HERE / "元DGTF-V1.23.52.py"',
     'SRC = HERE / "元DGTF-V1.23.53.py"'),
    ("末尾插 M104",
     "     '        if False:  # MUT'),\n]",
     "     '        if False:  # MUT'),\n" + M104 + "]"),
    ("链上新判据",
     '             "st.check_v12352_paused_no_eml() and "',
     '             "st.check_v12352_paused_no_eml() and "\n'
     '             "st.check_v12353_eml_dir_single() and "'),
])
print("\n接线完成。")
