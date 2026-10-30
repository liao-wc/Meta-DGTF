# -*- coding: utf-8 -*-
"""[V2.2.54] README 实测数字自动同步（从 evidence JSON 回写，--check 校验）。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def _load(rel: str) -> dict:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return {}


def _facts() -> dict:
    sel = _load("docs/app_selftest_latest.json")
    probe = _load("outputs/_e2e_local/_layer_goals_probe_latest.json")
    v2 = _load("docs/v2_tests_latest.json")
    fg = _load("docs/fast_gate_latest.json")
    acc = _load("docs/acceptance_latest.json")
    pv = _load("docs/probe_variance_20261030.json")
    eng = ""
    try:
        av = _load("docs/app_version_latest.json")
        eng = str(av.get("version") or "")
    except Exception:  # noqa: BLE001
        pass
    ver = ""
    try:
        files = list((ROOT / "dgtf_engine" / "dgtf_v2" / "engine").glob(
            "Meta-DGTF-V*.py"))

        def _vkey(p):
            m = re.search(r"V(\d+)\.(\d+)\.(\d+)\.py$", p.name)
            return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

        files.sort(key=_vkey)
        if files:
            ver = "%d.%d.%d" % _vkey(files[-1])
    except Exception:  # noqa: BLE001
        pass
    return {
        "engine": ver,
        "app": eng,
        "selftest_pass": int(sel.get("pass") or 0),
        "selftest_fail": int(sel.get("fail") or 0),
        "probe_pass": int(probe.get("pass") or 0),
        "probe_calls": sum(int(c.get("llm_calls") or 0)
                           for c in (probe.get("cases") or [])),
        "probe_wall": ((probe.get("meta") or {}).get("wall_sec") or 0.0),
        "v2_pass": int(v2.get("passed") or 0),
        "v2_total": int(v2.get("files") or 0),
        "fg_pass": int(fg.get("passed") or 0),
        "fg_total": int(fg.get("total") or 0),
        "acc_pass": int(acc.get("passed") or 0),
        "acc_skip": int(acc.get("skipped") or 0),
        "acc_fail": int(acc.get("failed") or 0),
        "pv": (pv.get("cases") or {}),
        "pv_path": "docs/probe_variance_20261030.json",
    }


def _patched(text: str, f: dict) -> tuple[str, list[str]]:
    notes: list[str] = []
    text2 = text
    pat = r"(\| App selftest \| \*\*PASS )(\d+)( / FAIL )(\d+)(\*\*)"

    def _r1(m):
        if (int(m.group(2)) != f["selftest_pass"]
                or int(m.group(4)) != f["selftest_fail"]):
            notes.append("App selftest %s/%s -> %s/%s"
                         % (m.group(2), m.group(4), f["selftest_pass"],
                            f["selftest_fail"]))
        return "%s%d%s%d%s" % (m.group(1), f["selftest_pass"], m.group(3),
                               f["selftest_fail"], m.group(5))

    text2 = re.sub(pat, _r1, text2, count=1)
    pat2 = (r"\*\*(?P<p>\d+) / (?P<m>\d+) PASS\*\*（V(?P<v>[\d.]+) 复跑："
            r"4 case 共 (?P<c>\d+) calls，墙钟 (?P<w>[\d.]+)s")

    def _r2(m):
        if (int(m.group("p")) != f["probe_pass"]
                or int(m.group("c")) != f["probe_calls"]
                or abs(float(m.group("w")) - float(f["probe_wall"])) > 0.2):
            notes.append("probe %s/%s calls=%s wall=%s -> %s calls=%s wall=%s"
                         % (m.group("p"), m.group("m"), m.group("c"),
                            m.group("w"), f["probe_pass"], f["probe_calls"],
                            f["probe_wall"]))
        return ("**%d / %d PASS**（V%s 复跑：4 case 共 %d calls，墙钟 %ss"
                % (f["probe_pass"], f["probe_pass"],
                   f["engine"] or m.group("v"), f["probe_calls"],
                   f["probe_wall"]))

    text2 = re.sub(pat2, _r2, text2, count=1)
    pat3 = r"(App selftest \*\*)(\d+)(/0\*\*)"

    def _r3(m):
        if int(m.group(2)) != f["selftest_pass"]:
            notes.append("App selftest 顶部 %s -> %s"
                         % (m.group(2), f["selftest_pass"]))
        return "%s%d%s" % (m.group(1), f["selftest_pass"], m.group(3))

    text2 = re.sub(pat3, _r3, text2, count=1)
    # fast_gate 数字（顶部/摘要行：fast_gate **N/M**）
    pat4 = r"(fast_gate \*\*)(\d+)(/)(\d+)(\*\*)"

    def _r4(m):
        if (int(m.group(2)) != f["fg_pass"]
                or int(m.group(4)) != f["fg_total"]):
            notes.append("fast_gate %s/%s -> %s/%s"
                         % (m.group(2), m.group(4), f["fg_pass"],
                            f["fg_total"]))
        return "%s%d%s%d%s" % (m.group(1), f["fg_pass"], m.group(3),
                               f["fg_total"], m.group(5))

    text2 = re.sub(pat4, _r4, text2, count=1)
    # 表格行：| fast_gate | **N / M PASS**
    pat5 = r"(\| fast_gate \| \*\*)(\d+)( / )(\d+)( PASS\*\*)"

    def _r5(m):
        if (int(m.group(2)) != f["fg_pass"]
                or int(m.group(4)) != f["fg_total"]):
            notes.append("fast_gate 表格 %s/%s -> %s/%s"
                         % (m.group(2), m.group(4), f["fg_pass"],
                            f["fg_total"]))
        return "%s%d%s%d%s" % (m.group(1), f["fg_pass"], m.group(3),
                               f["fg_total"], m.group(5))

    text2 = re.sub(pat5, _r5, text2, count=1)
    # 四层读数方差行（顶部摘要 + 明细行）按前缀整行重写
    _pv_cases = f.get("pv") or {}

    def _fm(x):
        return ("%g" % x) if isinstance(x, (int, float)) else "?"

    _c0 = _pv_cases.get("0") or {}
    _cb = _pv_cases.get("both") or {}
    _ca = _pv_cases.get("all") or {}
    _row_main = ("| **四层读数方差（刷新）** | %s 次历史复跑：case0 均值 **%s**"
                 "（%s–%s）/ both **%s**（%s–%s）/ all **%s**（%s–%s，从未到 1.0）"
                 "| %s |"
                 % (_c0.get("n", 0), _fm(_c0.get("mean")), _fm(_c0.get("min")),
                    _fm(_c0.get("max")), _fm(_cb.get("mean")),
                    _fm(_cb.get("min")), _fm(_cb.get("max")),
                    _fm(_ca.get("mean")), _fm(_ca.get("min")),
                    _fm(_ca.get("max")), f.get("pv_path")))
    _row_sum = ("| 读数方差统计（刷新） | %s 次历史：case0 均值 %s / both %s / all %s |"
                % (_c0.get("n", 0), _fm(_c0.get("mean")),
                   _fm(_cb.get("mean")), _fm(_ca.get("mean"))))
    _lines = text2.splitlines()
    _changed = 0
    for _i, _ln in enumerate(_lines):
        if _ln.startswith("| **四层读数方差"):
            if _ln != _row_main:
                _lines[_i] = _row_main
                _changed += 1
        elif _ln.startswith("| 读数方差统计"):
            if _ln != _row_sum:
                _lines[_i] = _row_sum
                _changed += 1
    if _changed:
        notes.append("variance rows updated x%d" % _changed)
    text2 = "\n".join(_lines) + "\n"
    return text2, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="README 实测数字同步/校验")
    ap.add_argument("--write", action="store_true", help="写回 README")
    ap.add_argument("--check", action="store_true", help="只校验（默认）")
    a = ap.parse_args(argv)
    f = _facts()
    text = README.read_text(encoding="utf-8")
    new, notes = _patched(text, f)
    print(json.dumps(f, ensure_ascii=False))
    if notes:
        print("mismatch:", json.dumps(notes, ensure_ascii=False))
    else:
        print("README numbers OK")
    if a.write:
        if new != text:
            README.write_text(new, encoding="utf-8")
            print("README updated")
        return 0
    return 1 if notes else 0


if __name__ == "__main__":
    sys.exit(main())
