# -*- coding: utf-8 -*-
"""全流程帕累托基线 / 预算选档 / 三组件联动快照。

用法：
  python scripts/pareto_flow.py                     # 扫描 outputs 输出前沿
  python scripts/pareto_flow.py --budget-tokens 600000 --min-quality 0.9
  python scripts/pareto_flow.py --with-components   # 附加 App/BGE 端点读数
  python scripts/pareto_flow.py --dir outputs --json
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

from dgtf_v2.pareto_flow import (joint_snapshot, load_packed_runs, report,  # noqa: E402
                                 select_joint)


def _p50(url: str, token: str = "", n: int = 3) -> dict:
    ctx = ssl._create_unverified_context()
    lat = []
    for _ in range(n):
        t0 = time.perf_counter()
        u = url
        if token:
            u = url + ("&" if "?" in url else "?") + "t=" + token
        try:
            with urllib.request.urlopen(u, timeout=8, context=ctx) as r:
                r.read()
            lat.append((time.perf_counter() - t0) * 1000)
        except Exception:
            return {"error": "unreachable"}
    return {"p50_ms": round(statistics.median(lat), 1), "max_ms": round(max(lat), 1)}


def _components() -> dict:
    tok = ""
    tp = ROOT / "dgtf_memory" / ".access_token"
    try:
        tok = tp.read_text(encoding="utf-8").strip()
    except Exception:
        tok = ""
    app = {
        "health": _p50("https://127.0.0.1:8765/api/health", tok),
        "chats": _p50("https://127.0.0.1:8765/api/dsh/chats", tok),
    }
    # BGE 服务（HTTP，无 token）
    local = {"bge_health": _p50("http://127.0.0.1:8771/health", "", 3)}
    return {"app": app, "local": local}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="outputs")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--budget-tokens", type=int, default=None)
    ap.add_argument("--min-quality", type=float, default=None)
    ap.add_argument("--with-components", action="store_true")
    ap.add_argument("--snapshot", default="",
                    help="把本次联合快照写入 JSON 路径（便于跨轮次对比）")
    ap.add_argument("--joint-select", action="store_true",
                    help="三组件联动选档（引擎行 + App/BGE 读数）")
    ap.add_argument("--require-web", action="store_true")
    args = ap.parse_args()
    packs = sorted((ROOT / args.dir).glob("*.packed.json"),
                   key=lambda p: p.stat().st_mtime)
    rows = load_packed_runs(packs)
    rep = report(rows, budget_tokens=args.budget_tokens,
                 min_quality=args.min_quality)
    comp = _components() if args.with_components else None
    out = joint_snapshot(rep, app=(comp or {}).get("app"),
                         local=(comp or {}).get("local")) if comp else rep
    if args.joint_select:
        js = select_joint(rows, app=(comp or {}).get("app"),
                          local=(comp or {}).get("local"),
                          budget_tokens=args.budget_tokens,
                          min_quality=args.min_quality,
                          require_web=args.require_web)
        out = {"engine_report": rep, "joint_select": js,
               "app": (comp or {}).get("app"), "local": (comp or {}).get("local")}
    if args.snapshot:
        sp = ROOT / args.snapshot
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                      encoding="utf-8")
        if not args.json:
            print("snapshot -> %s" % sp)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print("全流程帕累托基线 · %d 次真跑 · %d 个非支配点"
          % (len(rows), len(rep["frontier"])))
    print("id\tquality\ttokens\tcalls\truns")
    for r in rep["rows"]:
        mark = "*" if r["id"] in rep["frontier"] else " "
        print("%s%s\t%.4f\t%d\t%d\troute=%s" % (
            mark, r["id"], r["quality"], r["tokens"], r["calls"],
            ",".join(r.get("route") or [])))
    rec = rep.get("recommend") or {}
    row = rec.get("row")
    if row:
        print("\n推荐档位（%s）：%s  quality=%.4f tokens=%d calls=%d"
              % (rec.get("reason"), row.get("id"), row.get("quality", 0),
                 row.get("tokens", 0), row.get("calls", 0)))
        print("配置：route=%s rounds=%s" % (row.get("route"), row.get("rounds")))
    if args.joint_select and isinstance(out, dict) and out.get("joint_select"):
        js = out["joint_select"]
        row = js.get("row") or {}
        print("\n联动选档（%s）：%s quality=%.4f tokens=%d calls=%d web=%s"
              % (js.get("reason"), row.get("id"), row.get("quality", 0),
                 row.get("tokens", 0), row.get("calls", 0),
                 "on" if row.get("web_enabled") else "off"))
    if comp:
        print("\n组件快照：App %s；BGE %s"
              % (json.dumps(comp["app"], ensure_ascii=False),
                 json.dumps(comp["local"], ensure_ascii=False)))
        print("说明：app/local 为单实例读数；联合前沿需同配置多轮 A/B 才能排序。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
