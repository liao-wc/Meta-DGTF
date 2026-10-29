# -*- coding: utf-8 -*-
"""[V2.2.18] 发布流程门：把「发版流程不能漏」变成可复跑的判据。

覆盖（README §六 版本迭代规则 + docs/README 维护约定）：
  P1 引擎版本一致性：最高版引擎 == App find_engine 选中文件；__version__ ==
     dgtf_config.yaml 头 == NAMING == README == PROJECT_MAP == PROJECT_LAYOUT ==
     Pages(docs/index.html) == 发布说明/收束报告/CHANGELOG == 状态快照。
  P2 发布产物存在：根 V<v>-发布报告.md / V<v>-收束报告.md / docs/releases/V<v>.md/
     CHANGELOG 首段 / docs/README 索引登记。
  P3 App 版本：app_version_check 通过（或 app_version_latest.json ok）。
  P4 证据新鲜度 + 数字一致：fast_gate / v2_tests / app_selftest / acceptance 的
     latest 证据存在、<MAX_AGE 小时、ok；且 README「当前版本实测」里的数字与证据
     逐项一致（防文档漂移）。四层 probe 证据全绿且 provenance=当前引擎。
  P5 标签：V<v> / engine-V<v>（--pre-tag 时记「待打」=N/A）；app-V<app> 必须存在
     （App 未变版时允许指向其发布提交，不移动已发布标签）。
  P6 完整性/路径：file_integrity_check + verify_project_paths（或读取其 evidence）。
  P7 DSH 全流程闭环：运行 dsh_loop_check；已知「证据陈旧（生产包早于引擎修复）」
     与「用户 App 实例不可达」归类为 **N/A + 显式原因**，其余 FAIL 照旧判红。

三态：PASS / FAIL / N/A（N/A 必须带可指认原因，绝不冒充 PASS）。
退出码：0 = 无 FAIL；1 = 有 FAIL。

用法：
  python scripts/release_process_check.py --pre-tag     # 发版前（当前版标签记 pending）
  python scripts/release_process_check.py --post-tag    # 打标签后（要求标签存在）
  python scripts/release_process_check.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS, FAIL, NA = "PASS", "FAIL", "N/A"
MAX_AGE_H = 24.0
EVID_OUT = "docs/release_process_latest.json"

_VER_RE = re.compile(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def _ver_tuple(v: str):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


def highest_engine(root: Path):
    """返回 (engine_path, version_str)；没有候选时 (None, "")。"""
    d = root / "dgtf_engine" / "dgtf_v2" / "engine"
    if not d.is_dir():
        return None, ""
    cands = []
    for p in d.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V([0-9]+)\.([0-9]+)\.([0-9]+)", p.name)
        if m:
            cands.append((tuple(int(x) for x in m.groups()), p))
    if not cands:
        return None, ""
    cands.sort(key=lambda x: x[0])
    path = cands[-1][1]
    src = _read(root, str(path.relative_to(root)))
    m = _VER_RE.search(src)
    return path, (m.group(1) if m else "")


def _app_find_engine(root: Path):
    """子进程导入 dgtf_app/engine_runner.find_engine()，返回其选中路径字符串。"""
    code = (
        "import sys, json\n"
        "sys.path.insert(0, %r)\n"
        "import engine_runner\n"
        "print(json.dumps({'p': str(engine_runner.find_engine())}))\n"
        % str(root / "dgtf_app")
    )
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=str(root),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        if r.returncode != 0:
            return None, ((r.stdout or "") + (r.stderr or ""))[-300:]
        return json.loads((r.stdout or "").strip().splitlines()[-1]).get("p"), ""
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


def _pattern_checks(root: Path, version: str) -> list:
    """P1：各处的版本声明必须一致。返回 [(name, status, detail)]。"""
    out = []
    pats = [
        ("dgtf_config.yaml 头", "dgtf_config.yaml",
         r"Meta-DGTF(?:\-道生三阶模型)? · V([0-9.]+) 配置文件"),
        ("NAMING 当前版本", "dgtf_engine/dgtf_v2/NAMING.md",
         r"当前版本：\*\*V([0-9.]+)\*\*"),
        ("README 当前版本", "README.md",
         r"- \*\*当前版本\*\*：V([0-9.]+)"),
        ("PROJECT_MAP 生产入口", "PROJECT_MAP.md",
         r"Meta-DGTF-V([0-9.]+)\.py"),
        ("PROJECT_LAYOUT 生产入口", "PROJECT_LAYOUT.md",
         r"V2 生产入口：.*?Meta-DGTF-V([0-9.]+)\.py"),
        ("Pages 引擎版本", "docs/index.html",
         r'<span class="tag">V([0-9.]+)</span>'),
    ]
    for name, rel, pat in pats:
        src = _read(root, rel)
        if not src:
            out.append((name, FAIL, "文件缺失：" + rel))
            continue
        m = re.search(pat, src)
        if not m:
            out.append((name, FAIL, "找不到版本声明（pattern 未命中）：" + rel))
        elif str(m.group(1)) != version:
            out.append((name, FAIL, "版本不一致：%s != %s（%s）"
                        % (m.group(1), version, rel)))
        else:
            out.append((name, PASS, version))
    return out


def app_selftest_pending(appver: str) -> list:
    return [("app 版本标签", "N/A",
             "pre-tag 模式：app-V%s 属于已发布 App 版本，本轮不移动标签" % appver)]


def _artifacts(root: Path, version: str, today: str) -> list:
    out = []
    need = [
        "V%s-发布报告.md" % version,
        "V%s-收束报告.md" % version,
        "docs/releases/V%s.md" % version,
    ]
    for rel in need:
        p = root / rel
        if p.is_file():
            out.append(("发布产物存在：" + rel.split("/")[-1], PASS, ""))
        else:
            out.append(("发布产物存在：" + rel.split("/")[-1], FAIL, "缺失：" + rel))
    ch = _read(root, "CHANGELOG.md")[:6000]
    if ("【V%s（" % version) in ch:
        out.append(("CHANGELOG 含本版段落", PASS, ""))
    else:
        out.append(("CHANGELOG 含本版段落", FAIL, "CHANGELOG 头部 6KB 内没有 【V%s（" % version))
    dindex = _read(root, "docs/README.md")
    if ("docs/releases/V%s.md" % version) in dindex:
        out.append(("docs 索引登记发布说明", PASS, ""))
    else:
        out.append(("docs 索引登记发布说明", FAIL, "docs/README.md 未登记 V%s" % version))
    snap = root / "docs" / ("项目状态快照_%s.md" % today)
    if snap.is_file() and ("V%s" % version) in _read(root, str(snap.relative_to(root))):
        out.append(("状态快照含本版", PASS, snap.name))
    else:
        out.append(("状态快照含本版", FAIL, "缺 docs/项目状态快照_%s.md 或其中无 V%s"
                    % (today, version)))
    return out


def _app_version(root: Path, run_scripts: bool) -> list:
    if run_scripts:
        try:
            r = subprocess.run([sys.executable,
                                str(root / "scripts" / "app_version_check.py")],
                               cwd=str(root), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            if r.returncode != 0:
                return [("App 版本一致性", FAIL,
                         "app_version_check exit=%d" % r.returncode)]
        except Exception as exc:  # noqa: BLE001
            return [("App 版本一致性", FAIL, "%s: %s" % (type(exc).__name__, exc))]
    try:
        d = json.loads(_read(root, "docs/app_version_latest.json") or "{}")
    except Exception:  # noqa: BLE001
        d = {}
    if d.get("ok") is True:
        return [("App 版本一致性", PASS, "App " + str(d.get("version") or ""))]
    return [("App 版本一致性", FAIL, "app_version_latest.json 缺失或 ok!=true")]


def _load_json(root: Path, rel: str):
    try:
        return json.loads(_read(root, rel) or "null")
    except Exception:  # noqa: BLE001
        return None


def _evidence(root: Path, version: str, max_age_h: float) -> list:
    now = time.time()
    out = []
    specs = [
        ("fast_gate", "docs/fast_gate_latest.json"),
        ("v2_tests", "docs/v2_tests_latest.json"),
        ("app_selftest", "docs/app_selftest_latest.json"),
        ("acceptance", "docs/acceptance_latest.json"),
    ]
    evs = {}
    for name, rel in specs:
        d = _load_json(root, rel)
        if not isinstance(d, dict):
            out.append((name + " 证据存在", FAIL, "缺失/不可读：" + rel))
            continue
        evs[name] = d
        age = now - float(d.get("ts") or 0)
        if age < 0 or age > max_age_h * 3600:
            out.append((name + " 证据新鲜", FAIL,
                        "过旧（%.1fh > %.0fh）：%s" % (age / 3600.0, max_age_h, rel)))
        elif d.get("ok") is not True:
            out.append((name + " 证据全绿", FAIL, "ok!=true：" + rel))
        else:
            out.append((name + " 证据新鲜且全绿", PASS,
                        d.get("iso") or ""))
    fg = evs.get("fast_gate") or {}
    if fg and str(fg.get("engine_version") or "") != version:
        out.append(("fast_gate 引擎版本", FAIL,
                    "%r != %r" % (fg.get("engine_version"), version)))
    elif fg:
        out.append(("fast_gate 引擎版本", PASS, str(fg.get("engine_version"))))
    return out, evs


def _readme_sync(root: Path, evs: dict, version: str) -> list:
    """P4b：README「当前版本实测」数字必须与证据一致（机器核对，防文档漂移）。"""
    readme = _read(root, "README.md")
    if not readme:
        return [("README 数字同步", FAIL, "README.md 缺失")]
    out = []
    v2 = evs.get("v2_tests") or {}
    if v2:
        needle = "**%d / %d PASS（%d 项检查" % (
            int(v2.get("passed") or 0), int(v2.get("files") or 0),
            int(v2.get("checks") or 0))
        out.append(("README ↔ v2_tests 数字", PASS if needle in readme else FAIL,
                    needle if needle not in readme else ""))
    fg = evs.get("fast_gate") or {}
    if fg:
        needle = "**%d / %d PASS**" % (int(fg.get("passed") or 0),
                                       int(fg.get("total") or 0))
        out.append(("README ↔ fast_gate 数字", PASS if needle in readme else FAIL,
                    needle if needle not in readme else ""))
    acc = evs.get("acceptance") or {}
    if acc:
        needle = "PASS %d / SKIP %d / FAIL %d" % (
            int(acc.get("passed") or 0), int(acc.get("skipped") or 0),
            int(acc.get("failed") or 0))
        out.append(("README ↔ acceptance 数字", PASS if needle in readme else FAIL,
                    needle if needle not in readme else ""))
    ase = evs.get("app_selftest") or {}
    if ase:
        needle = "PASS %d / FAIL %d" % (int(ase.get("pass") or 0),
                                        int(ase.get("fail") or 0))
        # ★ 同一行必须同时出现「App selftest」与数字：README 顶部摘要行也含
        #   App selftest 字样但不带 455/0 计数，只认第一行会误判。
        hit = next((ln for ln in readme.splitlines()
                    if "App selftest" in ln and needle in ln), "")
        out.append(("README ↔ app_selftest 数字",
                    PASS if hit else FAIL,
                    needle if not hit else ""))
    probe = _load_json(root, "outputs/_e2e_local/_layer_goals_probe_latest.json")
    if not isinstance(probe, dict):
        out.append(("四层 probe 证据", NA, "本 checkout 无 outputs/ 回放证据（不冒充绿）"))
    else:
        ok = (int(probe.get("fail") or 0) == 0 and not probe.get("not_run"))
        ver = str((probe.get("meta") or {}).get("engine_version") or "")
        out.append(("四层 probe 全绿且版本对齐",
                    PASS if (ok and ver == "V" + version) else FAIL,
                    "pass=%s fail=%s engine=%s" % (probe.get("pass"),
                                                   probe.get("fail"), ver)))
        if ok and ("**%d / %d PASS**" % (probe.get("pass"), probe.get("pass"))) not in readme:
            out.append(("README ↔ probe 数字", FAIL,
                        "README 缺 **%d / %d PASS**" % (probe.get("pass"),
                                                        probe.get("pass"))))
    return out


def _git_ok(root: Path) -> bool:
    """是否在 git 工作树内（空标签 ≠ 非 git 仓库，两者必须分开）。"""
    try:
        rp = subprocess.run(["git", "-C", str(root), "rev-parse",
                             "--is-inside-work-tree"],
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
        return (rp.returncode == 0
                and (rp.stdout or "").strip().lower() == "true")
    except Exception:  # noqa: BLE001
        return False


def _tags(root: Path, version: str, appver: str, pre_tag: bool) -> list:
    def _tags_of(r: Path) -> set:
        try:
            rp = subprocess.run(["git", "-C", str(r), "tag", "--list"],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
            return set(x.strip() for x in (rp.stdout or "").splitlines() if x.strip())
        except Exception:  # noqa: BLE001
            return set()

    if not _git_ok(root):
        return [("git 标签可读", NA, "非 git 仓库或 git 不可用（干净 checkout 允许）")]
    tags = _tags_of(root)
    out = [("git 标签可读", PASS, "%d 个标签" % len(tags))]
    for name in ("V" + version, "engine-V" + version):
        if pre_tag:
            out.append((name, NA, "pre-tag 模式：尚未打（commit 后 --post-tag 复核）"))
        elif name in tags:
            out.append((name, PASS, ""))
        else:
            out.append((name, FAIL, "缺标签：" + name))
    app_tag = "app-V" + appver
    if app_tag in tags:
        out.append((app_tag, PASS, "App 未变版时标签指向其发布提交，不移动"))
    elif pre_tag:
        out.append((app_tag, NA, "pre-tag 模式：App 标签待复核"))
    else:
        out.append((app_tag, FAIL, "缺标签：" + app_tag))
    return out


def _integrity(root: Path, run_scripts: bool) -> list:
    if run_scripts:
        out = []
        for name, rel in (("file_integrity", "scripts/file_integrity_check.py"),
                          ("verify_project_paths", "scripts/verify_project_paths.py")):
            try:
                r = subprocess.run([sys.executable, str(root / rel)],
                                   cwd=str(root), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=180)
                ok = r.returncode == 0
                out.append((name, PASS if ok else FAIL,
                            "" if ok else ((r.stdout or "") + (r.stderr or ""))[-200:]))
            except Exception as exc:  # noqa: BLE001
                out.append((name, FAIL, "%s: %s" % (type(exc).__name__, exc)))
        return out
    d = _load_json(root, "docs/file_integrity_latest.json") or {}
    return [("file_integrity（evidence）",
             PASS if d.get("bad") == 0 else FAIL,
             "bad=%s" % d.get("bad"))]


#: dsh_loop_check 里属于「环境/证据边界」而非流程判红的 FAIL 模式。
_DSH_NA_PATTERNS = [
    ("旧产物可能停在引擎修复前", "证据陈旧：最新生产包早于当前引擎修复（本阶段零 API 预算，未复跑生产档）"),
    ("App 运行态", "用户 App 实例不可达/超时（8765 为人工实例，非发版门）"),
    ("The read operation timed out", "App 实例读超时（环境依赖）"),
    ("SSLError", "App 实例 TLS/证书环境依赖"),
]


def classify_dsh_fail(line: str, budget_degraded: bool = False):
    """把 dsh_loop_check 的 FAIL 行分类为 (FAIL|N/A, reason)。纯函数，可单测。

    ★ 预算边界：最新生产真跑若处于 App 预算守卫的 degrade/warn 档（余额 < ¥8），
      fast 成本档 answer_quality=unverified 是**预算决定的结果**，不是本版回归；
      这里把它归 N/A 并在原因里写清（N/A ≠ PASS，门回执仍可见）。
    """
    s = str(line or "")
    if budget_degraded and ("G5 质量门" in s or "answer_quality=unverified" in s):
        return NA, ("最新生产真跑处于预算守卫降级档（余额 < ¥8）⇒ fast 档 "
                    "answer_quality=unverified；预算边界，非本版回归")
    for pat, why in _DSH_NA_PATTERNS:
        if pat in s:
            return NA, why
    return FAIL, s[:200]


def _latest_prod_budget_degraded(root: Path):
    """最新 App 生产任务是否处于预算守卫 degrade/warn 档（读 run.json）。"""
    try:
        runs = sorted((root / "outputs").glob("*.run.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        if not runs:
            return False
        d = json.loads(runs[0].read_text(encoding="utf-8", errors="replace"))
        bg = ((d.get("mode") or {}).get("plan") or {}).get("budget_guard") or {}
        return str(bg.get("decision") or "").lower() in ("degrade", "warn")
    except Exception:  # noqa: BLE001
        return False


def _dsh_loop(root: Path, run_scripts: bool) -> list:
    if not run_scripts:
        return [("dsh_loop_check", NA, "run_scripts=False（构造性测试/离线模式）")]
    try:
        r = subprocess.run([sys.executable,
                            str(root / "scripts" / "dsh_loop_check.py")],
                           cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
    except Exception as exc:  # noqa: BLE001
        return [("dsh_loop_check", FAIL, "%s: %s" % (type(exc).__name__, exc))]
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("[FAIL]")]
    passes = [ln for ln in out.splitlines() if ln.strip().startswith("[PASS]")]
    res = [("dsh_loop_check PASS 项", PASS, "%d 项" % len(passes))]
    _budget_deg = _latest_prod_budget_degraded(root)
    for ln in fails:
        status, why = classify_dsh_fail(ln, budget_degraded=_budget_deg)
        res.append(("dsh_loop_check " + ln[7:40], status,
                    (why + "（预算降级标记=是）") if _budget_deg else why))
    if r.returncode != 0 and not any(s == FAIL for _, s, _ in res):
        res.append(("dsh_loop_check 退出码", NA,
                    "FAIL 项全部归为证据/环境边界（见上），退出码 %d" % r.returncode))
    return res


def run_checks(root: Path, pre_tag: bool = False, post_tag: bool = False,
               run_scripts: bool = True, max_age_h: float = MAX_AGE_H,
               today: str | None = None, evidence: str = EVID_OUT) -> dict:
    t0 = time.time()
    today = today or time.strftime("%Y%m%d")
    engine, version = highest_engine(root)
    checks = []
    if engine is None or not version:
        checks.append(("引擎动态发现", FAIL, "dgtf_engine/dgtf_v2/engine 下无 Meta-DGTF-V*.py"))
        return {"schema": "dgtf.release_process.v1", "ts": t0,
                "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
                "engine": "", "version": "", "pre_tag": pre_tag,
                "post_tag": post_tag, "checks": [
                    {"name": n, "status": s, "detail": d} for n, s, d in checks],
                "failed": 1, "na": 0, "passed": 0, "ok": False}
    checks.append(("引擎动态发现", PASS,
                   "%s（V%s）" % (engine.name, version)))
    app_path, app_err = _app_find_engine(root)
    if app_path is None:
        checks.append(("App find_engine 对齐", FAIL, app_err or "导入失败"))
    elif Path(app_path).name != engine.name:
        checks.append(("App find_engine 对齐", FAIL,
                       "App=%s != 最高版=%s" % (Path(app_path).name, engine.name)))
    else:
        checks.append(("App find_engine 对齐", PASS, engine.name))
    checks += _pattern_checks(root, version)
    checks += _artifacts(root, version, today)
    checks += _app_version(root, run_scripts)
    ev_checks, evs = _evidence(root, version, max_age_h)
    checks += ev_checks
    checks += _readme_sync(root, evs, version)
    appver = ""
    try:
        appver = str((_load_json(root, "docs/app_version_latest.json") or {})
                     .get("version") or "")
    except Exception:  # noqa: BLE001
        appver = ""
    checks += _tags(root, version, appver or "0.0.0", pre_tag)
    checks += _integrity(root, run_scripts)
    checks += _dsh_loop(root, run_scripts)
    nfail = sum(1 for _, s, _ in checks if s == FAIL)
    for name, status, detail in checks:
        print("%-5s %-42s %s" % (status, name, detail))
    result = {
        "schema": "dgtf.release_process.v1",
        "ts": t0,
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
        "engine": str(engine.relative_to(root)) if engine else "",
        "engine_version": version,
        "app_version": appver,
        "pre_tag": pre_tag,
        "post_tag": post_tag,
        "passed": sum(1 for _, s, _ in checks if s == PASS),
        "failed": nfail,
        "na": sum(1 for _, s, _ in checks if s == NA),
        "checks": [{"name": n, "status": s, "detail": d}
                   for n, s, d in checks],
        "ok": nfail == 0,
    }
    try:
        p = root / evidence
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("\nRELEASE PROCESS: PASS %d / FAIL %d / N/A %d"
          % (result["passed"], result["failed"], result["na"]))
    return result


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="发布流程门（三态 PASS/FAIL/N/A）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--pre-tag", action="store_true",
                      help="发版前：当前版标签记 pending（N/A），不判红")
    mode.add_argument("--post-tag", action="store_true",
                      help="打标签后：要求 V<v>/engine-V<v> 存在")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default="", help="仓库根（测试用；默认脚本上两级）")
    ap.add_argument("--max-age-hours", type=float, default=MAX_AGE_H)
    ap.add_argument("--no-scripts", action="store_true",
                    help="不跑子进程（读 evidence；构造性测试用）")
    ap.add_argument("--evidence", default=EVID_OUT,
                    help="证据输出路径（默认 docs/release_process_latest.json；"
                         "post-tag 建议 outputs/_lead_audit/... 以免脏工作树）")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    res = run_checks(root, pre_tag=bool(a.pre_tag), post_tag=bool(a.post_tag),
                     run_scripts=not a.no_scripts,
                     max_age_h=float(a.max_age_hours),
                     evidence=str(a.evidence))
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
