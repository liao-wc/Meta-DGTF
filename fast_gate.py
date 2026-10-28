# -*- coding: utf-8 -*-
"""快速门禁：并行跑关键语法/模块/审计检查，缩短反馈；完整门禁仍用 _run_gate。

★ 动态引擎发现（2026-10-28 起，task-3）—— 门禁不再钉死任何引擎版本：
  每次运行都把「生产引擎」直接交给 **App 的唯一选版真相源**
  `dgtf_app/engine_runner.py::find_engine()`（import 后调用，**不复制** glob/正则/
  排序/DGTF_APP_ENGINE 覆盖逻辑 —— 复制必漂移）。
  本脚本只额外负责三条「门禁自己的」不变量：
    1) 无候选 ⇒ **判红**：App 在候选 glob 全空时会回落到硬编码旧版；
       这里用一个不存在的假 PROJECT_ROOT 反推该兜底路径形态并识别回落，拒不接受
       （绝不静默检查旧引擎 —— 历史缺陷：compile/audit70 钉死 V2.2.3，
        从 V2.2.4 起 12/12 全绿其实是「旧引擎在绿灯」）。
    2) 选中的文件必须存在（is_file）。
    3) `engine_alignment`：本脚本最终检查的文件 == App find_engine() 现在选中的文件，
       且选版入口就是 App 的 find_engine 函数对象（函数对象同一性 / 注入委托判据，
       见 scripts/tests_acceptance_semantics.py 的 A7「把 App.find_engine 换成桩，
       本脚本必须跟着桩走」——若哪天有人把选版逻辑复制进来，该判据立刻红）。
  输出首行打印 `ENGINE <路径> (V<版本>, source=glob|env)`，让「门在检查哪个引擎」可审计。

零 GPU / 零真实服务；秒级。用法：
    python fast_gate.py                 # 并行跑全部门禁检查
    python fast_gate.py --print-engine  # 只打印解析到的生产引擎后退出（供脚本/CI 消费）
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "dgtf_app"

_APP_MOD = None


# ── App 唯一选版真相源（直接 import，不复制实现）────────────────────
def _app_module():
    """导入 dgtf_app/engine_runner.py（幂等）。失败 = App 域坏了，门禁应判红。"""
    global _APP_MOD
    if _APP_MOD is not None:
        return _APP_MOD
    app_str = str(APP_DIR)
    if app_str not in sys.path:
        sys.path.insert(0, app_str)
    import engine_runner  # noqa: PLC0415 —— 唯一真相源，必须在调用时导入
    _APP_MOD = engine_runner
    return engine_runner


def _app_find_engine_fn():
    """本脚本的选版入口 = App 的 find_engine 函数对象（测试做同一性/注入委托判据）。"""
    return _app_module().find_engine


def app_find_engine():
    """直接调用 App 的 find_engine()。"""
    return Path(_app_find_engine_fn()())


def _fallback_rel(app) -> Path | None:
    """反推 App「候选为空」时的兜底路径形态（不复制版本号常量、不复制 glob）。

    做法：把 App 模块的 PROJECT_ROOT 临时指向一个不存在的假根，调一次它的
    find_engine()；此时候选 glob 必然全空，返回值就是兜底路径。取相对路径即可在
    真实根上识别「本次是否发生了静默回落」。异常/环境覆盖时返回 None（跳过该判据）。
    """
    saved = app.PROJECT_ROOT
    probe_root = Path(saved) / "__dgtf_fast_gate_no_candidate_probe__"
    try:
        app.PROJECT_ROOT = probe_root
        try:
            fb = Path(app.find_engine())
        except Exception:  # noqa: BLE001
            return None
    finally:
        app.PROJECT_ROOT = saved
    try:
        return fb.relative_to(probe_root)
    except ValueError:
        return None   # 环境变量覆盖等非兜底返回 ⇒ 无法从兜底形态推断，跳过该判据


def resolve_engine():
    """解析生产引擎 → (Path|None, source, err)。source ∈ {"env", "glob"}。

    唯一真相源 = App find_engine()。本函数只加「门禁不变量」：
    无候选（检测到 App 兜底回落）/ 选中文件不存在 ⇒ 返回 None + 原因。
    """
    override = str(os.environ.get("DGTF_APP_ENGINE") or "").strip()
    source = "env" if override else "glob"
    try:
        app = _app_module()
        eng = Path(app.find_engine())
    except Exception as exc:  # noqa: BLE001
        return None, source, ("无法调用 App engine_runner.find_engine()：%s: %s"
                              % (type(exc).__name__, exc))
    if not override:
        rel = _fallback_rel(app)
        if rel is not None:
            try:
                fallback = (Path(app.PROJECT_ROOT) / rel).resolve()
                hit = os.path.normcase(str(eng.resolve())) == os.path.normcase(str(fallback))
            except OSError:
                hit = False
            if hit:
                return None, source, (
                    "App 候选引擎 glob 无命中，find_engine() 静默回落到硬编码旧版 %s；"
                    "门禁不接受回落（检查 dgtf_engine/dgtf_v2/engine/ 与 App glob）"
                    % eng.name)
    if not eng.is_file():
        return None, source, ("App find_engine() 选中的引擎文件不存在：%s（source=%s）"
                              % (eng, source))
    return eng, source, ""


def discover_engine():
    """动态发现的便捷入口 → Path|None（详细判红原因见 resolve_engine）。"""
    eng, _source, _err = resolve_engine()
    return eng


def engine_version_str() -> str:
    """引擎版本号 —— 走 App 自己的 engine_capabilities()，不复制版本正则。"""
    try:
        return str((_app_module().engine_capabilities() or {}).get("version") or "")
    except Exception:  # noqa: BLE001
        return ""


# ── 与 App 选版对齐（防再漂移的牙）─────────────────────────────────
def check_engine_alignment(engine=None):
    """本脚本的引擎 == App find_engine() 的引擎？返回 (ok, 原因)。"""
    try:
        app = _app_module()
    except Exception as exc:  # noqa: BLE001
        return False, "无法导入 dgtf_app.engine_runner：%s: %s" % (type(exc).__name__, exc)
    if engine is None:
        engine, source, err = resolve_engine()
        if engine is None:
            return False, "本脚本未解析出生产引擎：" + err
    else:
        source = "explicit"
    # 判据 1：选版入口必须是 App 的 find_engine 函数对象（复制实现 ⇒ 函数对象不同）
    fn = _app_find_engine_fn()
    if fn is not app.find_engine or getattr(fn, "__module__", "") != "engine_runner":
        return False, ("选版入口不是 dgtf_app.engine_runner.find_engine"
                       "（函数对象同一性判据失败：出现复制/替换实现）")
    # 判据 2：本脚本检查的文件 == App 现在选中的文件
    try:
        app_engine = Path(app.find_engine())
        mine_key = os.path.normcase(str(Path(engine).resolve()))
        app_key = os.path.normcase(str(app_engine.resolve()))
    except OSError as exc:  # noqa: BLE001
        return False, "路径解析失败：%s: %s" % (type(exc).__name__, exc)
    if mine_key != app_key:
        return False, ("引擎选版漂移：fast_gate=%s ≠ App=%s"
                       % (Path(engine).name, Path(app_engine).name))
    return True, ("与 App find_engine() 同一生产引擎：%s（source=%s）"
                  % (Path(engine).name, source))


# ── 子进程检查清单（由当前引擎动态拼装）────────────────────────────
_DISCOVERY_PROBE = (
    "import sys, fast_gate\n"
    "p, source, err = fast_gate.resolve_engine()\n"
    "if p is None:\n"
    "    print(err or '未解析出生产引擎')\n"
    "    sys.exit(1)\n"
    "print('engine=%s  source=%s' % (p, source))\n"
    "sys.exit(0)\n"
)
_ALIGN_PROBE = (
    "import sys, fast_gate\n"
    "ok, why = fast_gate.check_engine_alignment()\n"
    "print(why)\n"
    "sys.exit(0 if ok else 1)\n"
)


def _fail_cmd(msg: str) -> list:
    """一条「必然判红」的占位命令：用于应跑却没条件跑的检查（不许静默跳过）。"""
    return [sys.executable, "-c",
            "import sys;print(%r);sys.exit(1)" % str(msg)]


def build_checks(engine=None) -> list:
    """返回 [(name, cmd)]。engine=None ⇒ compile/audit70 用会判红的占位命令。"""
    checks = [
        # 动态发现本身也是一条判据：无候选 / 回落 / 文件不存在 ⇒ 判红
        ("engine_discovery", [sys.executable, "-c", _DISCOVERY_PROBE]),
        # 与 App find_engine() 对齐：函数对象同一性 + 选中文件相等
        ("engine_alignment", [sys.executable, "-c", _ALIGN_PROBE]),
    ]
    if engine is not None:
        checks.append(("compile", [sys.executable, "-c",
            "import py_compile,sys;py_compile.compile(sys.argv[1],doraise=True)",
            str(engine)]))
        probe = ROOT / "_probe_v1232_audit.py"
        if probe.is_file():
            checks.append(("audit70", [sys.executable, str(probe), str(engine)]))
        else:
            checks.append(("audit70", _fail_cmd("缺少审计探针 _probe_v1232_audit.py")))
    else:
        _msg = "未解析出生产引擎（动态发现为空），compile/audit70 未执行"
        checks.append(("compile", _fail_cmd(_msg)))
        checks.append(("audit70", _fail_cmd(_msg)))
    checks += [
        ("input_sanity", [sys.executable, "-c",
         "import dgtf_v2.tests_input_sanity as t;raise SystemExit(t.main())"]),
        ("facet", [sys.executable, "-c", "import dgtf_v2.tests_facet_ledger as t;raise SystemExit(t.main())"]),
        ("structural_diversity", [sys.executable, "-c",
         "import dgtf_v2.tests_structural_diversity as t;raise SystemExit(t.main())"]),
        ("self_feedback", [sys.executable, "-c", "import dgtf_v2.tests_self_feedback as t;raise SystemExit(t.test())"]),
        ("api_policy", [sys.executable, "-c", "import dgtf_v2.tests_api_policy as t;raise SystemExit(t.main())"]),
        ("vision", [sys.executable, "-c", "import dgtf_v2.tests_vision_input as t;raise SystemExit(t.main())"]),
        ("agent_bridge", [sys.executable, "-c", "import dgtf_v2.tests_agent_bridge as t;raise SystemExit(t.main())"]),
        ("agent_worker", [sys.executable, "-c", "import dgtf_v2.tests_agent_worker as t;raise SystemExit(t.main())"]),
        ("agent_repair", [sys.executable, "-c", "import dgtf_v2.tests_agent_repair as t;raise SystemExit(t.main())"]),
        ("agent_daemon", [sys.executable,
         str(ROOT / "dgtf_engine" / "dgtf_v2" / "tests_agent_daemon.py")]),
        # task-3 判据：快速门禁自身的语义（动态发现 + 对齐 + acceptance 三态）
        ("acceptance_semantics", [sys.executable,
         str(ROOT / "scripts" / "tests_acceptance_semantics.py")]),
        # [V2.2.18] 发布流程门自检：版本/文档/证据/标签/N-A 分类的构造性判据
        ("release_process_selftest", [sys.executable,
         str(ROOT / "scripts" / "tests_release_process.py")]),
    ]
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="快速门禁（App 同源动态选版，零 GPU）")
    ap.add_argument("--print-engine", action="store_true",
                    help="只打印解析到的生产引擎路径/版本后退出")
    args = ap.parse_args(argv)

    engine, source, engine_err = resolve_engine()
    if engine is None:
        print("ENGINE <未解析出生产引擎>  %s" % (engine_err or ""))
    else:
        print("ENGINE %s  (V%s, source=%s)"
              % (engine, engine_version_str(), source))
    if args.print_engine:
        return 0 if engine is not None else 1

    checks = build_checks(engine)
    bad = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        child_env = dict(os.environ)
        child_env["PYTHONUTF8"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONPATH"] = (str(ROOT) + os.pathsep
                                   + str(ROOT / "dgtf_engine")
                                   + os.pathsep + child_env.get("PYTHONPATH", ""))
        futs = {ex.submit(subprocess.run, cmd, cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=child_env, timeout=900): name
                for name, cmd in checks}
        for f in as_completed(futs):
            name = futs[f]
            try:
                r = f.result()
                ok = r.returncode == 0
            except Exception:  # noqa: BLE001
                ok = False
                r = None
            print(("PASS " if ok else "FAIL ") + name)
            if not ok:
                bad.append(name)
                if r is not None:
                    print((r.stdout or r.stderr or "")[-800:])
    print("\nFAST GATE PASS %d / FAIL %d" % (len(checks) - len(bad), len(bad)))
    # ★ [V2.2.18] 证据出口：release_process_check 用它校验「门有没有新鲜跑过」
    #   以及 README 的「当前版本实测」数字是否与真实结果一致（防文档漂移）。
    try:
        _now = time.time()
        _ev = {
            "schema": "dgtf.fast_gate.v1",
            "ts": _now,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now)),
            "engine": str(engine) if engine else "",
            "engine_name": Path(engine).name if engine else "",
            "engine_version": engine_version_str() if engine else "",
            "engine_source": source,
            "total": len(checks),
            "passed": len(checks) - len(bad),
            "failed": len(bad),
            "failed_names": list(bad),
            "ok": not bad,
        }
        _p = ROOT / "docs" / "fast_gate_latest.json"
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(json.dumps(_ev, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
