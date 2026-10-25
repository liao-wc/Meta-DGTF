# -*- coding: utf-8 -*-
"""从真跑记录自动汇总「场景 × 模式」实测矩阵（Round 6，学习闭环）。

背景：`mode_fusion.MEASURED_SCENARIOS` 是人工写入的实测锚点。每轮 A/B 跑完后
新增数据不会自动进来。本脚本把 `docs/ab_results.jsonl` 里**有效真跑**按
「题型场景 × 引擎模式」聚合，输出 `docs/scenario_matrix_live.json` 并与人工矩阵
做对照，供下一轮人工/CI 更新锚点（不直接改代码，避免悄悄改变选档行为）。

用法：
  python scripts/update_scenario_matrix.py            # 打印 + 写 JSON
  python scripts/update_scenario_matrix.py --json     # 只打印 JSON
  python scripts/update_scenario_matrix.py --since 2026-10-25
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.mode_fusion import MEASURED_SCENARIOS, kind_of_question  # noqa: E402

AB = ROOT / "docs" / "ab_results.jsonl"
OUT = ROOT / "docs" / "scenario_matrix_live.json"


def mode_of(tag: str) -> str:
    t = str(tag or "").lower()
    if "serial" in t:
        return "serial"
    if "fast" in t:
        return "fast"
    if "daosheng" in t or "preset" in t:
        return "auto"
    return "other"


def web_of(tag: str, row: dict) -> bool:
    if "web" in str(tag or "").lower():
        return True
    fp = row.get("fingerprint") or {}
    return bool(fp.get("web_enabled"))


def load_rows(since: str = "") -> list[dict]:
    rows = []
    if not AB.is_file():
        return rows
    for ln in AB.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if r.get("valid") is not True:
            continue
        ts = str(r.get("ts") or "")
        if since and ts < since:
            continue
        q = str(r.get("question") or "")
        rows.append({
            "tag": str(r.get("tag") or ""),
            "ts": ts,
            "question": q,
            "kind": kind_of_question(q),
            "mode": mode_of(r.get("tag")),
            "web": web_of(r.get("tag"), r),
            "quality": r.get("quality"),
            "tokens": r.get("tokens"),
            "calls": r.get("calls"),
            "wall": r.get("wall_s"),
            "answer_quality": r.get("answer_quality"),
            "answer_ready": r.get("answer_ready"),
        })
    return rows


def _agg(vals: list, nd: int = 3):
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return round(m, nd)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return round(m, nd) if var < 1e-12 else round(m, nd)


def aggregate(rows: list[dict]) -> dict:
    groups: dict[tuple, list] = {}
    for r in rows:
        if r["mode"] == "other":
            continue
        key = (r["kind"], r["mode"], bool(r["web"]))
        groups.setdefault(key, []).append(r)
    matrix = {}
    for (kind, mode, web), rs in groups.items():
        rs_sorted = sorted(rs, key=lambda x: x["ts"])
        latest = rs_sorted[-1]
        verified = [x for x in rs if x["answer_ready"] and
                    x["answer_quality"] == "verified"]
        # 质量锚点只取 verified 真跑：B1（auto_narr）/D1（thinking off）等
        # 负结果机制实验虽然 valid=True，但属于「被削弱的变体」，不能进入
        # 场景质量锚点（否则 reasoning auto 会被拉低到 0.726，实测于本轮）。
        anchor = verified or rs
        matrix.setdefault(kind, {})[mode + ("+web" if web else "")] = {
            "n_runs": len(rs),
            "n_verified": len(verified),
            "quality_mean": _agg([x["quality"] for x in anchor]),
            "quality_mean_all": _agg([x["quality"] for x in rs]),
            "tokens_mean": int(_agg([x["tokens"] for x in anchor], 0) or 0),
            "wall_mean": _agg([x["wall"] for x in anchor], 1),
            "verified_ratio": round(len(verified) / len(rs), 3),
            "latest_tag": latest["tag"],
            "latest_quality": latest["quality"],
            "samples": [{"tag": x["tag"], "quality": x["quality"],
                         "tokens": x["tokens"], "wall": x["wall"],
                         "verified": bool(x["answer_ready"] and
                                          x["answer_quality"] == "verified")}
                        for x in rs_sorted],
        }
    return matrix


def compare(matrix: dict) -> list[dict]:
    """人工锚点 vs 自动汇总：给出差异（供人工更新判断）。"""
    out = []
    for kind, cfg in MEASURED_SCENARIOS.items():
        for mode, run in (cfg.get("runs") or {}).items():
            key = mode + ("+web" if ("web_on" in mode) else "")
            auto = (matrix.get(kind) or {}).get(key) or \
                (matrix.get(kind) or {}).get(mode)
            # web_on_* / web_off_* 对齐到 <mode>+web / <mode>
            if auto is None and mode.startswith("web_on_"):
                base = mode.replace("web_on_", "")
                auto = (matrix.get(kind) or {}).get(base + "+web")
                if auto is None:
                    import re as _re
                    base2 = _re.sub(r"\d+$", "", base)
                    auto = (matrix.get(kind) or {}).get(base2 + "+web")
            if auto is None and mode.startswith("web_off_"):
                base = mode.replace("web_off_", "")
                auto = (matrix.get(kind) or {}).get(base)
            # fast_domainN / fastN 都是 fast 档的重复实测 ⇒ 归并对照
            if auto is None and (mode.startswith("fast_domain")
                                 or (mode.startswith("fast")
                                     and mode[4:].isdigit())):
                auto = (matrix.get(kind) or {}).get("fast")
            if not auto:
                out.append({"scenario": kind, "mode": mode,
                            "human_quality": run.get("quality"),
                            "live_quality": None, "delta": None,
                            "note": "无对应有效真跑"})
                continue
            hq = run.get("quality")
            lq = auto.get("quality_mean")
            out.append({"scenario": kind, "mode": mode,
                        "human_quality": hq, "live_quality": lq,
                        "delta": (round(float(lq) - float(hq), 3)
                                  if hq is not None and lq is not None else None),
                        "n_runs": auto.get("n_runs"),
                        "verified_ratio": auto.get("verified_ratio")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = load_rows(args.since)
    matrix = aggregate(rows)
    diffs = compare(matrix)
    payload = {"n_valid_runs": len(rows), "since": args.since,
               "matrix": matrix, "diff_vs_manual": diffs}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    print("有效真跑 %d 条 → %s" % (len(rows), OUT))
    for kind, modes in sorted(matrix.items()):
        print("\n[%s]" % kind)
        for mode, m in sorted(modes.items()):
            print("  %-12s n=%-2d quality=%.3f tokens=%-8d wall=%-7.1fs verified=%.0f%%  (latest %s)"
                  % (mode, m["n_runs"], m["quality_mean"] or 0,
                     m["tokens_mean"], m["wall_mean"] or 0,
                     100 * m["verified_ratio"], m["latest_tag"]))
    print("\n对照人工锚点：")
    for d in diffs:
        if d["live_quality"] is None:
            print("  %-10s %-18s 人工=%.3f 实测=—（%s）"
                  % (d["scenario"], d["mode"], d["human_quality"], d["note"]))
        else:
            print("  %-10s %-18s 人工=%.3f 实测=%.3f Δ=%+.3f（n=%d）"
                  % (d["scenario"], d["mode"], d["human_quality"],
                     d["live_quality"], d["delta"], d["n_runs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
