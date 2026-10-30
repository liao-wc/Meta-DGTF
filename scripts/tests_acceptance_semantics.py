# -*- coding: utf-8 -*-
"""验收语义判据（2026-10-28 · task-3）：fast_gate 同源选版 + final_acceptance 三态。

零 GPU / 零本地服务 / 秒级。可独立运行：
    python scripts/tests_acceptance_semantics.py
也被 fast_gate.py 的 acceptance_semantics 检查调用（改坏这两个文件 ⇒ 快速门禁判红）。

为什么需要它
------------
两处「门禁信任缺口」：
  1) fast_gate 曾把 compile/audit70 钉死 V2.2.3 —— 生产引擎升到 V2.2.14 后
     12/12 全绿检查的仍是旧引擎（旧引擎在绿灯）。⇒ 选版必须**完全委托**
     dgtf_app/engine_runner.find_engine()（唯一真相源，不复制 glob/正则/排序），
     且「无候选回落旧版」必须判红（App 在候选为空时会静默回落）。
  2) final_acceptance 把「没跑」当「判红/假绿」：e2e 服务未起 exit=2 被当 FAIL；
     judge_fastfail/generate_batch/graph_decode 服务不可达 exit 0 + 输出 SKIP
     被当 PASS。⇒ 必须 PASS/SKIP/FAIL 三态，且只有「声明为服务型」的步骤才认 exit2。

判据全部是构造性的（临时项目树 / 函数对象注入 / 临时子进程），并带**变异体自检**：
把被测逻辑改坏（接受回落 / 复制选版逻辑 / 对齐漂移放行 / exit=2 当 PASS）后，
本文件的断言必须能抓到（见 B 组）—— 这是「有牙」的证据，不是抄常量。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

P, F = [], []
TMP_ROOT = Path(tempfile.mkdtemp(prefix="dgtf_accept_sem_"))
ENGINE_REL = Path("dgtf_engine") / "dgtf_v2" / "engine"


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if info and not ok else ""))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_mutated(src_path, replacements, name):
    """复制源码 → 文本替换（必须恰好命中一次）→ 加载为独立模块。"""
    try:
        src = Path(src_path).read_text(encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        return None, "读取源码失败：%s" % exc
    for old, new in replacements:
        if src.count(old) != 1:
            return None, "变异点不唯一/不存在（命中 %d 次）：%r" % (src.count(old), old[:60])
        src = src.replace(old, new)
    tmpf = TMP_ROOT / (name + ".py")
    try:
        tmpf.write_text(src, encoding="utf-8")
        return _load(tmpf, name), ""
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


def _mk_tree(files):
    """在临时根下造 App 同构的引擎目录（dgtf_engine/dgtf_v2/engine/）。"""
    root = TMP_ROOT / ("proj_%02d" % len(P))
    eng = root / ENGINE_REL
    eng.mkdir(parents=True, exist_ok=True)
    for f in files:
        (eng / f).write_text("# fake engine for discovery test\n", encoding="utf-8")
    return root, eng


def _with_app_root(root, fn):
    """把唯一真相源 App.find_engine 的 PROJECT_ROOT 指到临时树（不改判据本身）。

    同时清掉 DGTF_APP_ENGINE（否则 App 的显式覆盖优先于 PROJECT_ROOT，
    临时树构造判据会被环境变量短路 —— 这正是 App 的真实语义，测试要隔离它）。
    """
    app = FG._app_module()
    saved = app.PROJECT_ROOT
    saved_env = os.environ.pop("DGTF_APP_ENGINE", None)
    try:
        app.PROJECT_ROOT = Path(root)
        return fn()
    finally:
        app.PROJECT_ROOT = saved
        if saved_env is not None:
            os.environ["DGTF_APP_ENGINE"] = saved_env


def _spawn_exit(code):
    """真实子进程（不是 mock 函数）：构造 exit 0/1/2 供三态分类判据消费。"""
    r = subprocess.run([sys.executable, "-c", "raise SystemExit(%d)" % int(code)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    return r.returncode


FG = _load(ROOT / "fast_gate.py", "dgtf_fast_gate_under_test")
FA = _load(ROOT / "scripts" / "final_acceptance.py", "dgtf_final_acceptance_under_test")
APP = FG._app_module()


# ══════════════════════ A 组：同源动态选版（构造性 + 委托） ══════════════════════
def test_discovery():
    root, _eng = _mk_tree(["Meta-DGTF-V2.2.3.py", "Meta-DGTF-V2.2.9.py",
                           "Meta-DGTF-V2.2.10.py"])
    got = _with_app_root(root, lambda: FG.resolve_engine())
    ck("A1 选版取版本号最大（2.2.10 > 2.2.9，不是字典序；走 App 真实 find_engine）",
       got[0] is not None and got[0].name == "Meta-DGTF-V2.2.10.py", got)

    (_eng / "Meta-DGTF-V9.9.9.py").write_text("# fake\n", encoding="utf-8")
    got = _with_app_root(root, lambda: FG.resolve_engine())
    ck("A2 构造 V9.9.9 文件 ⇒ 选中它（门跟着最高版走）",
       got[0] is not None and got[0].name == "Meta-DGTF-V9.9.9.py", got)

    for f in list(_eng.glob("Meta-DGTF*-V*.py")):
        f.unlink()
    eng_none, src_none, err_none = _with_app_root(root, lambda: FG.resolve_engine())
    ck("A3 删掉全部候选 ⇒ 判红（识别 App 的静默回落，不拿旧引擎凑绿）",
       eng_none is None and "回落" in err_none, (eng_none, err_none))

    root2, _e2 = _mk_tree(["Meta-DGTF-V2.2.3.py"])
    (root2 / "元DGTF-V8.0.0.py").write_text("# legacy name\n", encoding="utf-8")
    got = _with_app_root(root2, lambda: FG.resolve_engine())
    ck("A4 兼容旧文件名 元DGTF-V8.0.0.py（App 同源 glob）且与新版一起比版本",
       got[0] is not None and got[0].name == "元DGTF-V8.0.0.py", got)

    # 真实仓库：动态发现 → compile/audit 检查命令绑定该引擎
    saved_env = os.environ.pop("DGTF_APP_ENGINE", None)
    try:
        real = FG.discover_engine()
        ck("A5a 真实仓库解析出生产引擎且文件存在",
           real is not None and Path(real).is_file(), real)
        ck("A5b 引擎版本号走 App engine_capabilities()（不复制版本正则）",
           bool(FG.engine_version_str()) and FG.engine_version_str().count(".") == 2,
           FG.engine_version_str())
        checks = dict(FG.build_checks(real))
        ck("A5c compile 检查命令指向动态解析的引擎（不是写成某个版本）",
           real is not None and str(real) in " ".join(checks["compile"]))
        ck("A5d audit70 检查命令指向同一引擎",
           real is not None and str(real) in " ".join(checks["audit70"]))
        expected = {"engine_discovery", "engine_alignment", "compile",
                    "audit70", "input_sanity", "facet", "structural_diversity",
                    "self_feedback", "api_policy", "vision", "agent_bridge",
                    "agent_worker", "agent_repair", "agent_daemon",
                    "acceptance_semantics", "release_process_selftest",
                    "readme_numbers", "stability_guard", "dynamic_matrix"}
        got_names = {n for n, _ in FG.build_checks(real)}
        ck("A5f 检查清单完整（19 项；防重构时静默丢检查项，如 agent_daemon/"
           "release_process_selftest/readme_numbers/stability_guard/dynamic_matrix）",
           got_names == expected, sorted(expected - got_names) or sorted(got_names - expected))
        none_checks = dict(FG.build_checks(None))
        rc = subprocess.run(none_checks["compile"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60).returncode
        ck("A5e 无候选时 compile 占位命令判红（不是静默跳过/假绿）", rc != 0, rc)

        app_path = Path(APP.find_engine())
        ok, why = FG.check_engine_alignment()
        ck("A6a engine_alignment：本脚本检查的文件 == App find_engine() 选中文件",
           ok is True and Path(real).name == app_path.name, why)
        ck("A6b 选版入口就是 App 的 find_engine 函数对象（无复制实现）",
           FG._app_find_engine_fn() is APP.find_engine,
           FG._app_find_engine_fn())
    finally:
        if saved_env is not None:
            os.environ["DGTF_APP_ENGINE"] = saved_env

    # A7 委托判据（有牙）：把 App.find_engine 换成桩 ⇒ 本脚本必须跟着桩走
    fake = TMP_ROOT / "Meta-DGTF-V42.0.0.py"
    fake.write_text("# injected stub engine\n", encoding="utf-8")
    orig = APP.find_engine
    try:
        APP.find_engine = lambda: fake
        got = FG.resolve_engine()
        ck("A7 ★ 函数对象注入：App.find_engine 换桩后本脚本跟着桩走"
           "（复制选版实现就会红）",
           got[0] == fake and FG._app_find_engine_fn() is APP.find_engine, got)
    finally:
        APP.find_engine = orig

    # A8 环境变量覆盖与 App 同源（App 自己也读 DGTF_APP_ENGINE）
    override = TMP_ROOT / "Meta-DGTF-V99.0.0.py"
    override.write_text("# override engine\n", encoding="utf-8")
    os.environ["DGTF_APP_ENGINE"] = str(override)
    try:
        eng_up, src_up, err_up = FG.resolve_engine()
        ck("A8a DGTF_APP_ENGINE 覆盖与 App 同源（source=env，不经过 glob）",
           eng_up == override and src_up == "env", (eng_up, src_up, err_up))
        ok, why = FG.check_engine_alignment()
        ck("A8b 覆盖态下 engine_alignment 仍为真（两边同源）", bool(ok), why)
    finally:
        os.environ.pop("DGTF_APP_ENGINE", None)


# ══════════════════════════ B 组：变异体自检（有牙证明） ══════════════════════════
def test_mutants():
    # M1：接受 App 的静默回落（把回落识别删掉）⇒ A3 必须能抓到
    root, _eng = _mk_tree(["Meta-DGTF-V2.2.3.py"])
    app = FG._app_module()
    fallback_path = root / ENGINE_REL / "Meta-DGTF-V2.2.3.py"
    orig_fn, orig_root = app.find_engine, app.PROJECT_ROOT

    def _fallback_stub():
        # 模拟「App 的候选 glob 判据失效，只能落到兜底」：每次按当前 PROJECT_ROOT 返回兜底路径
        return Path(app.PROJECT_ROOT) / ENGINE_REL / "Meta-DGTF-V2.2.3.py"

    m1, err1 = _load_mutated(ROOT / "fast_gate.py", [(
        "            if hit:", "            if False and hit:")], "mutant_accept_fallback")
    try:
        app.PROJECT_ROOT = root
        app.find_engine = _fallback_stub
        real_eng, _s, real_err = FG.resolve_engine()
        mut_eng = m1.resolve_engine()[0] if m1 is not None else None
        ck("M1 变异体「接受静默回落」在无候选树里返回旧引擎（A3 有牙）",
           m1 is not None and real_eng is None and "回落" in real_err
           and mut_eng == fallback_path, (err1, real_eng, mut_eng))
    finally:
        app.find_engine, app.PROJECT_ROOT = orig_fn, orig_root

    # M2：复制选版逻辑（不调用 App.find_engine）⇒ A7 委托判据必须抓到
    m2, err2 = _load_mutated(ROOT / "fast_gate.py", [(
        "        eng = Path(app.find_engine())",
        "        _copied = sorted((Path(app.PROJECT_ROOT)/\"dgtf_engine\"/\"dgtf_v2\""
        "/\"engine\").glob(\"Meta-DGTF*-V*.py\"))\n"
        "        _copied = [x for x in _copied if x.is_file()]\n"
        "        eng = (_copied[-1] if _copied else Path(app.PROJECT_ROOT)"
        "/\"dgtf_engine\"/\"dgtf_v2\"/\"engine\"/\"Meta-DGTF-V2.2.3.py\")")],
        "mutant_copied_selection")
    saved_env2 = os.environ.pop("DGTF_APP_ENGINE", None)
    orig2 = APP.find_engine
    try:
        APP.find_engine = lambda: fake_engine_for_m2()
        real_eng, _s, _e = FG.resolve_engine()
        mut_eng = m2.resolve_engine()[0] if m2 is not None else None
        ck("M2 变异体「复制选版逻辑」无视 App.find_engine 注入（A7 有牙）",
           m2 is not None and real_eng == fake_engine_for_m2()
           and mut_eng != fake_engine_for_m2(), (err2, real_eng, mut_eng))
    finally:
        APP.find_engine = orig2
        if saved_env2 is not None:
            os.environ["DGTF_APP_ENGINE"] = saved_env2

    # M3：对齐判据的第二比较被删掉 ⇒ 漂移放行的变异体必须被 A6 抓出
    m3, err3 = _load_mutated(ROOT / "fast_gate.py", [(
        "    if mine_key != app_key:",
        "    if False and mine_key != app_key:")], "mutant_skip_alignment")
    real_engine = FG.discover_engine()
    drift = TMP_ROOT / "Meta-DGTF-V77.0.0.py"
    drift.write_text("# drift engine\n", encoding="utf-8")
    stub = lambda: drift
    stub.__module__ = "engine_runner"      # 让「同一性」判据通过，只留漂移比较
    orig3 = APP.find_engine
    try:
        APP.find_engine = stub
        real_ok, real_why = FG.check_engine_alignment(engine=real_engine)
        mut_ok = m3.check_engine_alignment(engine=real_engine)[0] if m3 is not None else True
        ck("M3 变异体「对齐漂移放行」必须被判红（A6 有牙）",
           m3 is not None and real_ok is False and mut_ok is True,
           (err3, real_ok, real_why, mut_ok))
    finally:
        APP.find_engine = orig3

    # M4：acceptance 把 exit=2 当 PASS（假绿）⇒ C3 必须抓到
    m4, err4 = _load_mutated(ROOT / "scripts" / "final_acceptance.py", [(
        '        return SKIP, ("exit=2 前置服务未起/不可达（没跑）"',
        '        return PASS, ("exit=2 前置服务未起/不可达（没跑）"')],
        "mutant_exit2_pass")
    if m4 is not None:
        st, _ = m4.classify_step(2, "⚠ 服务未起", m4.POLICY_SERVICE)
        ck("M4 变异体「exit=2 当 PASS」被三态断言抓到（C3 有牙）",
           st == m4.PASS, st)
    else:
        ck("M4 变异体构建失败 ⇒ 判据脱节必须红", False, err4)


def fake_engine_for_m2():
    return TMP_ROOT / "Meta-DGTF-V42.0.0.py"


# ═════════════ E 组：audit 探针性能判据（AST 一次解析、复用） ═════════════════
PROBE_PATH = ROOT / "_probe_v1232_audit.py"
_FAKE_ENGINE_SRC = (
    "# -*- coding: utf-8 -*-\n"
    '"""Meta-DGTF · V9.9.9 fake engine（parse-frequency 判据用）"""\n'
    '__version__ = "9.9.9"\n'
    'DEFAULT_CONFIG = {"api": {"thinking": {"default": "x", "stages": {}}}}\n'
    '_AUDIT_DEAD_CLASSES = ("Amp", "Probe", "Thread")\n'
    "class Pool:\n"
    "    pass\n"
    "def _build_inp_duel(self):\n"
    '    return "no web here"\n'
    "def _ing(self):\n"
    '    return "no web here"\n'
    "def _research_round_no(self):\n"
    "    return 0\n"
    "def _normalize_judgment_ids(x, n):\n"
    "    return x\n"
)

#: 在子进程里 monkeypatch ast.parse 计数：target = 与目标引擎全文**逐字相同**的源码
_GUARD_HELPER = (
    "import ast, runpy, sys\n"
    "SRC, PROBE, GUARD = sys.argv[1], sys.argv[2], int(sys.argv[3])\n"
    'full = open(SRC, "rb").read().decode("utf-8").replace("\\r\\n", "\\n")\n'
    "orig = ast.parse\n"
    'st = {"target": 0, "other": 0}\n'
    "def counting(src, *a, **k):\n"
    "    if src == full:\n"
    '        st["target"] += 1\n'
    '        if GUARD and st["target"] > GUARD:\n'
    '            print("REPARSE_GUARD_HIT target=%d" % st["target"])\n'
    "            raise SystemExit(99)\n"
    "    else:\n"
    '        st["other"] += 1\n'
    "    return orig(src, *a, **k)\n"
    "ast.parse = counting\n"
    "sys.argv = [PROBE, SRC]\n"
    "rc = 0\n"
    "try:\n"
    '    runpy.run_path(PROBE, run_name="__main__")\n'
    "except SystemExit as e:\n"
    "    rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)\n"
    'print("PARSE_STATS target=%d other=%d probe_rc=%s"\n'
    '      % (st["target"], st["other"], rc))\n'
)


def _mutant_file(src_path, replacements, name):
    """把源码按文本替换写成新文件（返回 path, err）；替换点缺失 ⇒ 判据脱节必须红。"""
    try:
        src = Path(src_path).read_text(encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        return None, "读取源码失败：%s" % exc
    for old, new in replacements:
        if src.count(old) != 1:
            return None, "变异点不唯一/不存在（命中 %d 次）：%r" % (src.count(old), old[:60])
        src = src.replace(old, new)
    p = TMP_ROOT / (name + ".py")
    p.write_text(src, encoding="utf-8")
    return p, ""


def _run_probe_guard(probe_path, engine_path, guard):
    helper = TMP_ROOT / "probe_parse_guard.py"
    if not helper.exists():
        helper.write_text(_GUARD_HELPER, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(helper), str(engine_path), str(probe_path),
         str(guard)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    return (r.stdout or "") + "\n" + (r.stderr or "")


def test_probe_ast_reuse():
    src = PROBE_PATH.read_text(encoding="utf-8")
    ck("E1a 探针全文只解析一次（ast.parse(txt) 仅 1 处 = _AST）",
       src.count("ast.parse(txt)") == 1 and "_AST = ast.parse(txt)" in src,
       src.count("ast.parse(txt)"))
    _start = src.find("def body_of(name):")
    _end = src.find("\ndef ", _start + 5)
    _block = src[_start:_end if _end > 0 else len(src)]
    ck("E1b body_of 查表复用、不再逐次全文解析",
       "_FUNCS.get(name)" in _block and "ast.parse" not in _block, _block[:200])
    _cache_blk = src.split("def _parse_cached", 1)[1][:300] if "def _parse_cached" in src else ""
    ck("E1c _parse_cached：目标文本走 _AST，其余文本才真正解析",
       "src is txt else ast.parse(src)" in _cache_blk, _cache_blk[:200])

    # E2 ★ 真实审计主流程（当前生产引擎）：目标全文解析次数必须 == 1，且守卫未触发
    prod = FG.discover_engine()
    out = _run_probe_guard(PROBE_PATH, prod, 1)
    m = re.search(r"PARSE_STATS target=(\d+) other=(\d+) probe_rc=(\S+)", out)
    ck("E2 ★ 真实审计主流程：全文 AST 解析次数 == 1（原实现 body_of 逐次解析 = O(n²)）",
       m is not None and int(m.group(1)) == 1 and "REPARSE_GUARD_HIT" not in out,
       out[-500:])

    # E3 ★ 变异体：body_of 恢复逐次解析 ⇒ reparse 守卫必须判红（E2 有牙）
    fake = TMP_ROOT / "fake_engine_for_probe.py"
    fake.write_text(_FAKE_ENGINE_SRC, encoding="utf-8")
    mut, err = _mutant_file(PROBE_PATH, [(
        "    n = _FUNCS.get(name)",
        "    n = _index_ast(ast.parse(txt))[\"funcs\"].get(name)")],
        "probe_mutant_reparse")
    if mut is None:
        ck("E3 变异体构建失败 ⇒ 判据脱节必须红", False, err)
    else:
        out_m = _run_probe_guard(mut, fake, 1)
        ck("E3 ★ 变异体「body_of 逐次解析」被 reparse 守卫判红（E2 有牙）",
           "REPARSE_GUARD_HIT" in out_m, out_m[-400:])


# ══════════════════════════ C 组：final_acceptance 三态 ══════════════════════════
def _run_main(mod, argv):
    """调用主函数但**禁止写生产证据**（假 STEPS 会污染 docs/acceptance_latest.json）。"""
    import os
    buf = io.StringIO()
    old = os.environ.get("DGTF_ACCEPTANCE_NO_EVIDENCE")
    os.environ["DGTF_ACCEPTANCE_NO_EVIDENCE"] = "1"
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.main(list(argv))
    finally:
        if old is None:
            os.environ.pop("DGTF_ACCEPTANCE_NO_EVIDENCE", None)
        else:
            os.environ["DGTF_ACCEPTANCE_NO_EVIDENCE"] = old
    return rc, buf.getvalue()


def test_classifier():
    out2 = ("⚠ 本地推理服务 8772 未起，本判据无法执行（不是判红，是没跑）\n"
            "⚠ OpenAI 适配层 8773 未起，本判据无法执行（不是判红，是没跑）\n")
    ck("C1 exit 0 ⇒ PASS", FA.classify_step(0, "PASS 3 / FAIL 0") == (FA.PASS, ""))
    st, why = FA.classify_step(1, "Traceback ... boom")
    ck("C2 exit 1 ⇒ FAIL 且带原因", st == FA.FAIL and "exit=1" in why, (st, why))
    st, why = FA.classify_step(2, out2, FA.POLICY_SERVICE)
    ck("C3 服务型步骤 exit 2 ⇒ SKIP（没跑，不是判红）且原因显式",
       st == FA.SKIP and "没跑" in why, (st, why))
    st, _ = FA.classify_step(2, out2, FA.POLICY_STRICT)
    ck("C4 严格步骤 exit 2 ⇒ FAIL（不搞「所有 exit2 都算没跑」的全局豁免）",
       st == FA.FAIL)
    st, why = FA.classify_step(
        0, "SKIP: 服务不可达（Connection refused）", FA.POLICY_SERVICE)
    ck("C5 服务型步骤 exit 0 + 输出 SKIP 行 ⇒ SKIP（旧版当 PASS 的假绿）",
       st == FA.SKIP and "SKIP" in why, (st, why))
    st, why = FA.classify_step(
        0, "SKIP: 找不到外汇题 packed（历史包缺失）", FA.POLICY_DATA)
    ck("C6 数据型步骤 exit 0 + 输出 SKIP 行 ⇒ SKIP（历史包缺失=没跑）",
       st == FA.SKIP, (st, why))
    st, _ = FA.classify_step(0, "PASS 9 / FAIL 0", FA.POLICY_SERVICE)
    ck("C7 服务型步骤真跑了（无 SKIP 标记）⇒ PASS", st == FA.PASS)

    st, why = FA.apply_service_requirement(FA.SKIP, "服务未起", FA.POLICY_SERVICE, True)
    ck("C8 --with-service ⇒ 服务型 SKIP 升级 FAIL（服务缺失仍算 FAIL）",
       st == FA.FAIL and "--with-service" in why, (st, why))
    st, _ = FA.apply_service_requirement(FA.SKIP, "服务未起", FA.POLICY_SERVICE, False)
    ck("C9 无 --with-service ⇒ 保持 SKIP", st == FA.SKIP)
    st, _ = FA.apply_service_requirement(FA.SKIP, "缺包", FA.POLICY_DATA, True)
    ck("C10 数据型 SKIP 不因 --with-service 升级（服务与历史数据是两回事）",
       st == FA.SKIP)

    # 真实子进程 exit 0/1/2（构造性，不是 mock returncode）
    ck("C11 真实子进程 exit 0 ⇒ PASS",
       FA.classify_step(_spawn_exit(0), "", FA.POLICY_STRICT)[0] == FA.PASS)
    ck("C12 真实子进程 exit 1 ⇒ FAIL",
       FA.classify_step(_spawn_exit(1), "", FA.POLICY_STRICT)[0] == FA.FAIL)
    ck("C13 真实子进程 exit 2 + 服务型策略 ⇒ SKIP",
       FA.classify_step(_spawn_exit(2), out2, FA.POLICY_SERVICE)[0] == FA.SKIP)


def _mk_script(name, body):
    p = TMP_ROOT / name
    p.write_text("# -*- coding: utf-8 -*-\n" + body, encoding="utf-8")
    return str(p)


def test_acceptance_integration():
    pass_py = _mk_script("step_pass.py", "raise SystemExit(0)\n")
    fail_py = _mk_script("step_fail.py", "print('boom')\nraise SystemExit(1)\n")
    skip_py = _mk_script("step_skip2.py",
                         "print('⚠ 本地服务未起，没跑')\nraise SystemExit(2)\n")
    marker = TMP_ROOT / "service_step_ran.marker"
    svc_py = _mk_script("step_service.py",
                        "from pathlib import Path\n"
                        "Path(r'%s').write_text('ran', encoding='utf-8')\n"
                        "raise SystemExit(0)\n" % marker)

    old_steps, old_loc = FA.STEPS, FA.LOCAL_SERVICE_STEP
    try:
        # T1：PASS + FAIL + SKIP 三态同场 ⇒ 汇总单列 + 退出码 1
        FA.STEPS = [("fake_pass", [pass_py], FA.POLICY_STRICT),
                    ("fake_fail", [fail_py], FA.POLICY_STRICT),
                    ("fake_skip", [skip_py], FA.POLICY_SERVICE)]
        rc, out = _run_main(FA, [])
        ck("T1 端到端：exit0/1/2 三个真实子进程 ⇒ PASS/FAIL/SKIP 三态各自归类",
           rc == 1 and "PASS 1 / SKIP 1 / FAIL 1" in out
           and "SKIP  fake_skip" in out and "FAIL  fake_fail" in out,
           (rc, [ln for ln in out.splitlines() if "fake_" in ln]))
        ck("T2 SKIP 在汇总里单列并显式打印原因（没跑不被藏）",
           "SKIPPED" in out and "fake_skip" in out and "没跑" in out, out[-600:])

        # T3：只有 PASS + SKIP ⇒ 默认退出码 0，但 SKIP 单列不冒充全绿
        FA.STEPS = [("fake_pass", [pass_py], FA.POLICY_STRICT),
                    ("fake_skip", [skip_py], FA.POLICY_SERVICE)]
        rc, out = _run_main(FA, [])
        ck("T3 无 FAIL 时退出码 0（SKIP 不算失败），但 SKIP 必须单列",
           rc == 0 and "PASS 1 / SKIP 1 / FAIL 0" in out
           and "SKIP  fake_skip" in out, (rc, out[-400:]))

        # T4：--require-all ⇒ SKIP 判失败
        rc, out = _run_main(FA, ["--require-all"])
        ck("T4 --require-all ⇒ SKIP 按失败处理（严格模式）",
           rc == 1 and "STRICT FAIL" in out, (rc, out[-300:]))

        # T5：--with-service ⇒ 服务型 SKIP 升级 FAIL（含本地服务检查步骤）
        FA.LOCAL_SERVICE_STEP = ("fake_local_service", [skip_py], FA.POLICY_STRICT)
        rc, out = _run_main(FA, ["--with-service"])
        ck("T5 --with-service + 服务缺失 ⇒ FAIL（不是 SKIP/假绿）",
           rc == 1 and "FAIL  fake_skip" in out
           and "FAIL  fake_local_service" in out, (rc, out[-500:]))

        # T6：--skip-service ⇒ 服务型步骤真的没执行（哨兵文件为证），且记 SKIP
        marker.unlink(missing_ok=True)
        FA.STEPS = [("fake_service_exec", [svc_py], FA.POLICY_SERVICE),
                    ("fake_pass", [pass_py], FA.POLICY_STRICT)]
        rc, out = _run_main(FA, ["--skip-service"])
        ck("T6 --skip-service 显式跳过：服务型步骤未执行（哨兵不存在）+ SKIP",
           rc == 0 and not marker.exists() and "SKIP  fake_service_exec" in out
           and "未执行" in out, (rc, marker.exists(), out[-400:]))
        # 对照：不带 --skip-service 时同一脚本必须真的执行（证明 T6 不是恒绿）
        rc, out = _run_main(FA, [])
        ck("T7 对照：不带 --skip-service ⇒ 服务型步骤真的执行且 PASS",
           rc == 0 and marker.exists() and "PASS  fake_service_exec" in out,
           (rc, marker.exists()))

        # T8：--list-steps 可审计（不执行）
        rc, out = _run_main(FA, ["--list-steps"])
        ck("T8 --list-steps 打印步骤清单与三态策略",
           rc == 0 and "fake_service_exec" in out and "service" in out, out[:400])
    finally:
        FA.STEPS, FA.LOCAL_SERVICE_STEP = old_steps, old_loc


def main() -> int:
    print("── A 同源动态选版（构造临时项目树 + 函数对象注入）──")
    test_discovery()
    print("\n── B 变异体自检（有牙证明）──")
    test_mutants()
    print("\n── E audit 探针性能（AST 一次解析 + 变异体）──")
    test_probe_ast_reuse()
    print("\n── C final_acceptance 三态（构造 exit0/1/2 子进程）──")
    test_classifier()
    print("\n── D 端到端串跑（打补丁 STEPS）──")
    test_acceptance_integration()
    print("\nPASS %d / FAIL %d" % (len(P), len(F)))
    if F:
        print("FAILED:")
        for f in F:
            print("  - " + f)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
