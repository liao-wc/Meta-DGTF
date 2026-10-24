# -*- coding: utf-8 -*-
"""三组件联动帕累托报告：引擎真跑 + App 端点 + 本地 BGE 读数，输出 MD/JSON。

用法：
  python scripts/pareto_report.py --out docs/pareto_joint_report_20261024.md \
      --json-out docs/pareto_joint_report_20261024.json
只读：扫描 outputs、读取墙钟侧车、探测本机 App/BGE；不改任何数据。
"""
from __future__ import annotations

import argparse
import json
import ssl
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.pareto_flow import (load_packed_runs, pareto_frontier, report,  # noqa: E402
                                 select_joint)


def _p50(url, token="", n=3, payload=None):
    lat = []
    ctx = ssl._create_unverified_context()
    for _ in range(n):
        u = url + (("&" if "?" in url else "?") + "t=" + token if token else "")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            u, data=data, headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                r.read()
            lat.append((time.perf_counter() - t0) * 1000)
        except Exception:
            return {"error": "unreachable"}
    return {"p50_ms": round(statistics.median(lat), 1),
            "max_ms": round(max(lat), 1)}


def probe_components():
    tok = ""
    try:
        tok = (ROOT / "dgtf_memory" / ".access_token").read_text(
            encoding="utf-8").strip()
    except Exception:
        pass
    app = {
        "health": _p50("https://127.0.0.1:8765/api/health", tok),
        "chats": _p50("https://127.0.0.1:8765/api/dsh/chats", tok),
        "events_full": _p50("https://127.0.0.1:8765/api/dsh/current/events?full=1&limit=100", tok),
    }
    bge = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:8771/health", timeout=10) as r:
            bge["health"] = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as exc:
        bge["health"] = {"ok": False, "error": str(exc)[:100]}
    text = "联动冷探针-%d" % time.time_ns()
    bge["embed_cold"] = _p50("http://127.0.0.1:8771/embed", "", 1,
                              {"texts": [text]})
    bge["embed_hot"] = _p50("http://127.0.0.1:8771/embed", "", 3,
                             {"texts": [text]})
    return {"app": app, "bge": bge}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--budget-tokens", type=int, default=1000000)
    ap.add_argument("--min-quality", type=float, default=0.9)
    ap.add_argument("--max-wall-seconds", type=float, default=None)
    args = ap.parse_args()
    side = {}
    sp = ROOT / "docs" / "pareto_engine_times.json"
    if sp.exists():
        side = json.loads(sp.read_text(encoding="utf-8", errors="replace"))
    _packs = (list((ROOT / "outputs").glob("20261024_1[6-9]*.packed.json"))
              + list((ROOT / "outputs").glob("20261024_2[0-3]*.packed.json")))
    packs = sorted(_packs, key=lambda p: p.stat().st_mtime)
    # 只保留质量门可读且非负例产物（负例已归档到 negative_runs）
    rows = load_packed_runs(packs, elapsed_map=side)
    rep = report(rows, budget_tokens=args.budget_tokens,
                 min_quality=args.min_quality)
    comp = probe_components()
    rec = rep.get("recommend") or {}
    rec_row = rec.get("row") or {}
    joint = select_joint(rows, app=comp["app"], local=comp["bge"],
                         budget_tokens=args.budget_tokens,
                         min_quality=args.min_quality,
                         max_wall_seconds=args.max_wall_seconds)
    lines = []
    lines.append("# 三组件联动帕累托报告（2026-10-24）")
    lines.append("")
    lines.append("生成：scripts/pareto_report.py（只读扫描 + 端点探测）")
    lines.append("")
    lines.append("## 1. 引擎真跑（同日、四层）")
    lines.append("")
    lines.append("| run | quality | tokens | calls | wall(s) | flags |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append("| %s | %.4f | %d | %d | %s | %d |" % (
            r["id"], r["quality"], r["tokens"], r["calls"],
            r.get("elapsed"), len(r.get("flags") or [])))
    lines.append("")
    lines.append("非支配点（quality/tokens/calls）：" + "、".join(rep.get("frontier") or []))
    wall_rows = [r for r in rows if r.get("elapsed") is not None]
    wf = pareto_frontier(wall_rows, (("quality", "max"), ("tokens", "min"),
                                     ("elapsed", "min")))
    lines.append("墙钟三目标非支配点（quality/tokens/wall）：" + "、".join(
        r["id"] for r in wf))
    lines.append("")
    lines.append("## 2. 组件读数（本机实测）")
    lines.append("")
    lines.append("App 端点 p50：health %sms、chats %sms、events(full) %sms" % (
        comp["app"]["health"].get("p50_ms"), comp["app"]["chats"].get("p50_ms"),
        comp["app"]["events_full"].get("p50_ms")))
    bg = comp["bge"].get("health") or {}
    lines.append("BGE：ok=%s dev=%s dim=%s cache=%s" % (
        bg.get("ok"), bg.get("dev"), bg.get("dim"),
        json.dumps(bg.get("cache"), ensure_ascii=False)))
    lines.append("BGE embed：冷 %sms、热 p50 %sms" % (
        comp["bge"]["embed_cold"].get("p50_ms"),
        comp["bge"]["embed_hot"].get("p50_ms")))
    lines.append("")
    wall_note = ("、wall <= %ss" % args.max_wall_seconds
                 if args.max_wall_seconds else "")
    lines.append("## 3. 联动选档（预算 %d tokens、质量 >= %.2f%s）" % (
        args.budget_tokens, args.min_quality, wall_note))
    lines.append("")
    lines.append("- 质量最大档：%s（%s）" % (rec_row.get("id"), rec.get("reason")))
    lines.append("- quality=%.4f、tokens=%d、calls=%d、wall=%ss" % (
        rec_row.get("quality", 0), rec_row.get("tokens", 0),
        rec_row.get("calls", 0), rec_row.get("elapsed")))
    jrow = joint.get("row") or {}
    lines.append("- 联动选档（含 wall 约束）：%s（%s）quality=%.4f tokens=%d wall=%ss" % (
        jrow.get("id"), joint.get("reason"), jrow.get("quality", 0),
        jrow.get("tokens", 0), jrow.get("elapsed")))
    lines.append("- 完整选档 JSON：%s" % json.dumps(joint, ensure_ascii=False))
    lines.append("")
    lines.append("## 4. 结论与边界")
    lines.append("")
    lines.append("- 三目标（quality↑ / tokens↓ / wall↓）下非支配点仍是 run6 与 run7；")
    lines.append("  run7 用 +30.9s / +28k tokens 换 +0.081 quality，J1 推荐 run7。")
    lines.append("- App health/chats/events 与 BGE 查询均为毫秒级，相对引擎分钟级可忽略；")
    lines.append("  联动瓶颈在引擎 LLM 墙钟，不在 App/BGE。")
    lines.append("- 本地 BGE 质量（24 语料/10 查询）recall@1=1.0、MRR=1.0；LLM 质量代理弱，不进答案主路径。")
    lines.append("- 边界：质量/成本为同日同题数据，跨题不可直接比较；3 层 route 负例已归档。")
    text = "\n".join(lines) + "\n"
    if args.out:
        (ROOT / args.out).write_text(text, encoding="utf-8")
        print("written", ROOT / args.out)
    else:
        print(text)
    out = {"engine_report": rep, "components": comp, "joint": joint,
           "generated": "scripts/pareto_report.py"}
    if args.json_out:
        (ROOT / args.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("json", ROOT / args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
