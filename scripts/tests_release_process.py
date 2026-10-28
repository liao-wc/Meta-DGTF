# -*- coding: utf-8 -*-
"""[V2.2.18] 发布流程门的构造性判据（临时假仓库 + 变异体，零真实项目依赖）。

每个变异体都从「完备假仓库」出发只改一处，断言 release_process_check 的对应检查
必须判红 —— 恒绿的门等于没有门。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import release_process_check as rp  # noqa: E402

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


NOW = time.time()
TODAY = time.strftime("%Y%m%d")
VER = "9.9.9"
APPVER = "2.0.37"
ENGINE_REL = "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V%s.py" % VER

FILES = {
    ENGINE_REL: '__version__ = "9.9.9"\n',
    "dgtf_app/engine_runner.py": (
        "from pathlib import Path\n"
        "_ROOT = Path(__file__).resolve().parent.parent\n"
        "def find_engine():\n"
        "    return (_ROOT / 'dgtf_engine' / 'dgtf_v2' / 'engine'\n"
        "            / 'Meta-DGTF-V" + VER + ".py')\n"),
    "dgtf_config.yaml": "# Meta-DGTF-道生三阶模型 · V%s 配置文件\n" % VER,
    "dgtf_engine/dgtf_v2/NAMING.md": "当前版本：**V%s**\n" % VER,
    "README.md": (
        "- **当前版本**：V%s（test）\n" % VER
        + "| fast_gate | **16 / 16 PASS**（test） |\n"
        + "| V2 tests_*.py | **70 / 70 PASS（1163 项检查，SKIP 0）** |\n"
        + "| App selftest | **PASS 455 / FAIL 0**（test） |\n"
        + "| 一键验收 | **PASS 25 / SKIP 0 / FAIL 0**（24 steps） |\n"
        + "| **四层目标探针** | **81 / 81 PASS**（test） |\n"),
    "PROJECT_MAP.md": "| V2 生产入口 | %s |\n" % ENGINE_REL,
    "PROJECT_LAYOUT.md": "- V2 生产入口：%s\n" % ENGINE_REL,
    "docs/index.html": '<span class="tag">V%s</span>\n' % VER,
    "docs/README.md": "| docs/releases/V%s.md | test |\n" % VER,
    "docs/releases/V%s.md" % VER: "# V%s\n" % VER,
    "V%s-发布报告.md" % VER: "# V%s 发布报告\n" % VER,
    "V%s-收束报告.md" % VER: "# V%s 收束报告\n" % VER,
    "CHANGELOG.md": "【V%s（2026-10-28，PATCH · test）】\n- test\n" % VER,
    "docs/项目状态快照_%s.md" % TODAY: "# 快照 V%s\n" % VER,
    "docs/fast_gate_latest.json": json.dumps({
        "ts": NOW, "iso": "x", "engine_version": VER, "total": 16,
        "passed": 16, "failed": 0, "ok": True}),
    "docs/v2_tests_latest.json": json.dumps({
        "ts": NOW, "files": 70, "passed": 70, "failed": 0, "skips": 0,
        "checks": 1163, "ok": True}),
    "docs/app_selftest_latest.json": json.dumps({
        "ts": NOW, "pass": 455, "fail": 0, "ok": True, "status": "pass"}),
    "docs/acceptance_latest.json": json.dumps({
        "ts": NOW, "passed": 25, "skipped": 0, "failed": 0, "ok": True}),
    "docs/app_version_latest.json": json.dumps({"ok": True, "version": APPVER}),
    "docs/file_integrity_latest.json": json.dumps({"bad": 0}),
    "outputs/_e2e_local/_layer_goals_probe_latest.json": json.dumps({
        "pass": 81, "fail": 0, "not_run": [],
        "meta": {"engine_version": "V" + VER}}),
}


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _git(root: Path, *args) -> int:
    return subprocess.run(["git", "-C", str(root)] + list(args),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace").returncode


def build_repo(root: Path, tags=True) -> Path:
    for rel, content in FILES.items():
        _write(root, rel, content)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    if tags:
        for t in ("V" + VER, "engine-V" + VER, "app-V" + APPVER):
            _git(root, "-c", "tag.gpgsign=false", "tag", "-a", t, "-m", t)
    return root


def check(root: Path, **kw):
    kw.setdefault("run_scripts", False)
    kw.setdefault("today", TODAY)
    return rp.run_checks(root, **kw)


TMP = Path(tempfile.mkdtemp(prefix="rp_test_"))
try:
    BASE = build_repo(TMP / "base")
    print("── A 完备假仓库：门必须全绿 ──")
    r = check(BASE)
    ck("A1 完备仓库 ⇒ ok=True 且 failed=0", r["ok"] and r["failed"] == 0,
       [(c["name"], c["status"], c["detail"]) for c in r["checks"]
        if c["status"] == "FAIL"][:3])
    ck("A2 发现版本 9.9.9", r["engine_version"] == VER, r["engine_version"])
    ck("A3 三标签在 post 模式全过", check(BASE, post_tag=True)["failed"] == 0)
    ck("A4 pre-tag 模式当前版标签记 N/A 而非红",
       check(BASE.with_name("base"), pre_tag=True)["ok"] is True)
    ck("A5 证据文件被写回 docs/release_process_latest.json",
       (BASE / "docs/release_process_latest.json").is_file())

    print("── B 变异体：改一处必须判红 ──")

    def mutate_dir(name, mutator):
        d = TMP / ("m_" + name)
        shutil.copytree(BASE, d)
        mutator(d)
        return d

    def mutate(name, mutator):
        return check(mutate_dir(name, mutator))

    def m_cfg(d):
        p = d / "dgtf_config.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "V" + VER, "V9.9.8"), encoding="utf-8")

    ck("B1 配置头版本不一致 ⇒ 判红", not mutate("cfg", m_cfg)["ok"])

    def m_report(d):
        (d / ("V%s-发布报告.md" % VER)).unlink()

    ck("B2 缺发布报告 ⇒ 判红", not mutate("report", m_report)["ok"])

    def m_stale(d):
        p = d / "docs/v2_tests_latest.json"
        e = json.loads(p.read_text(encoding="utf-8"))
        e["ts"] = NOW - 48 * 3600
        p.write_text(json.dumps(e), encoding="utf-8")

    ck("B3 证据过旧(>24h) ⇒ 判红", not mutate("stale", m_stale)["ok"])

    def m_num(d):
        p = d / "README.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "1163 项检查", "999 项检查"), encoding="utf-8")

    ck("B4 README 数字与证据不一致 ⇒ 判红", not mutate("num", m_num)["ok"])

    def m_no_tag(d):
        for t in ("V" + VER, "engine-V" + VER, "app-V" + APPVER):
            _git(d, "tag", "-d", t)

    ck("B5 post 模式缺标签 ⇒ 判红",
       not check(mutate_dir("notag", m_no_tag), post_tag=True)["ok"])
    ck("B6 pre 模式缺标签 ⇒ 仅 pending(N/A)，不判红",
       check(mutate_dir("notag2", m_no_tag), pre_tag=True)["ok"] is True)

    def m_probe(d):
        p = d / "outputs/_e2e_local/_layer_goals_probe_latest.json"
        e = json.loads(p.read_text(encoding="utf-8"))
        e["fail"] = 1
        p.write_text(json.dumps(e), encoding="utf-8")

    ck("B7 四层 probe 判红 ⇒ 判红", not mutate("probe", m_probe)["ok"])

    def m_appver(d):
        p = d / "docs/app_version_latest.json"
        p.write_text(json.dumps({"ok": False, "version": APPVER}), encoding="utf-8")

    ck("B8 App 版本证据 ok=false ⇒ 判红", not mutate("appver", m_appver)["ok"])

    def m_align(d):
        p = d / "dgtf_app/engine_runner.py"
        p.write_text(p.read_text(encoding="utf-8").replace(
            VER, "9.9.8"), encoding="utf-8")

    ck("B9 App 选版与最高版不一致 ⇒ 判红", not mutate("align", m_align)["ok"])

    def m_noengine(d):
        (d / ENGINE_REL).unlink()

    ck("B10 无引擎文件 ⇒ 判红", not mutate("noengine", m_noengine)["ok"])

    def m_changelog(d):
        p = d / "CHANGELOG.md"
        p.write_text("【V1.0.0】\n", encoding="utf-8")

    ck("B11 CHANGELOG 缺本版 ⇒ 判红", not mutate("changelog", m_changelog)["ok"])

    def m_index(d):
        p = d / "docs/README.md"
        p.write_text("| other | x |\n", encoding="utf-8")

    ck("B12 docs 索引未登记 ⇒ 判红", not mutate("index", m_index)["ok"])

    def m_snap(d):
        (d / ("docs/项目状态快照_%s.md" % TODAY)).unlink()

    ck("B13 缺当日状态快照 ⇒ 判红", not mutate("snap", m_snap)["ok"])

    print("── C dsh_loop_check FAIL 行分类（纯函数）──")
    ck("C1 证据陈旧 ⇒ N/A（不冒充红/绿）",
       rp.classify_dsh_fail("[FAIL] B. 最新真跑离线质量门预检 旧产物可能停在引擎修复前")[0] == rp.NA)
    ck("C2 App 实例超时 ⇒ N/A",
       rp.classify_dsh_fail("[FAIL] C. App 运行态 The read operation timed out")[0] == rp.NA)
    ck("C3 真失败 ⇒ FAIL", rp.classify_dsh_fail("[FAIL] E. 遥测崩溃 Traceback")[0] == rp.FAIL)
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
