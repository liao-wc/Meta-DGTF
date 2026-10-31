#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四层 probe 复跑一致性检查（V2.2.107）。

用途：把「连续两次逐项一致」固化为可复跑脚本。
- --runs N（默认 2）：顺序跑 N 次 probe（临时证据），逐 case 比较
  calls / status / main，并写 docs/probe_repeat_consistency_<date>.json；
- --compare A B：只比较已有两份 probe 证据 JSON（快速自检，零跑）。
退出码：0 = 全部一致；1 = 有差异/失败。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROBE = ROOT / "scripts" / "local_model" / "probe_layer_goals.py"
DOCS = ROOT / "docs"


def _rows(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    out = {"pass": d.get("pass"), "fail": d.get("fail"), "cases": {}}
    for c in d.get("cases") or []:
        L = (c.get("layers") or [{}])[0]
        out["cases"][str(c.get("case"))] = {
            "calls": c.get("llm_calls"),
            "status": L.get("target_status"),
            "main": L.get("main_value"),
        }
    return out


def _diff(a: dict, b: dict) -> tuple:
    """返回 (readings_diffs, cost_diffs)。

    readings = status/main + 汇总；cost = calls（LLM 调用数，允许随状态波动）。
    ★ V2.2.108：只有 readings 差异才算 MISMATCH；calls 差异降级为 WARN。
    """
    readings, costs = [], []
    for k in sorted(set(a["cases"]) | set(b["cases"])):
        ra = a["cases"].get(k) or {}
        rb = b["cases"].get(k) or {}
        for f in ("status", "main"):
            if ra.get(f) != rb.get(f):
                readings.append("%s.%s: %r != %r"
                                % (k, f, ra.get(f), rb.get(f)))
        if ra.get("calls") != rb.get("calls"):
            costs.append("%s.calls: %r != %r"
                         % (k, ra.get("calls"), rb.get("calls")))
    if (a["pass"], a["fail"]) != (b["pass"], b["fail"]):
        readings.append("summary: %r != %r"
                        % ((a["pass"], a["fail"]), (b["pass"], b["fail"])))
    return readings, costs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = ap.parse_args(argv)
    if args.compare:
        pa, pb = Path(args.compare[0]), Path(args.compare[1])
        a, b = _rows(pa), _rows(pb)
        readings, costs = _diff(a, b)
        for d in costs:
            print("WARN " + d)
        for d in readings:
            print("DIFF " + d)
        print("compare: %s（readings）%s"
              % ("CONSISTENT" if not readings else "MISMATCH",
                 "" if not costs else "；calls 有波动（WARN）"))
        return 0 if not readings else 1
    runs = max(2, int(args.runs or 2))
    tmp = ROOT / "_audit_tmp"
    tmp.mkdir(exist_ok=True)
    arts = []
    for i in range(1, runs + 1):
        ev = tmp / ("_probe_consistency_%d.json" % i)
        cmd = [sys.executable, str(PROBE), "--evidence", str(ev)]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        print("run %d rc=%s" % (i, r.returncode))
        if r.returncode != 0 or not ev.is_file():
            print((r.stdout or "")[-500:])
            return 1
        arts.append(ev)
    base = _rows(arts[0])
    bad, warns = [], []
    for i, ev in enumerate(arts[1:], 2):
        rd, cd = _diff(base, _rows(ev))
        bad += ["run%d %s" % (i, d) for d in rd]
        warns += ["run%d %s" % (i, d) for d in cd]
    out = {"schema": "metadgtf.probe_repeat_consistency.v1",
           "ts": "2026-10-31", "runs": runs,
           "consistent_readings": not bad, "diffs": bad,
           "cost_warnings": warns, "base": base}
    p = DOCS / "probe_repeat_consistency_20261031.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("consistency: %s（readings_diffs=%d；calls_warn=%d）"
          % ("CONSISTENT" if not bad else "MISMATCH", len(bad), len(warns)))
    for d in warns:
        print("WARN " + d)
    for d in bad:
        print("DIFF " + d)
    print("evidence -> %s" % p.relative_to(ROOT).as_posix())
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
