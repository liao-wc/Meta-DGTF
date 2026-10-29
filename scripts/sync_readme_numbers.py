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
        "acc_pass": int(acc.get("passed") or 0),
        "acc_skip": int(acc.get("skipped") or 0),
        "acc_fail": int(acc.get("failed") or 0),
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
