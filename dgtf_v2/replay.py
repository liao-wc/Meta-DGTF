# -*- coding: utf-8 -*-
"""用真实 outputs/*.packed.json 回放 EML v2 与调度 v2。

它只读历史产物，不调 API、不改生产引擎：
  · 把每次完成跑次当作一条 procedural outcome 写入 EML；
  · 从真实跑次提取 coverage/三态/轮数/成本，形成调度先验；
  · 用这些先验在 mock 层上跑一遍 V2 调度，观察它是否按契约选层。
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

from .memory import MemoryLake
from .orchestrator import Orchestrator


def _coverage(pool: dict) -> float:
    subs = list((pool or {}).get("sub_questions") or [])
    if not subs:
        return 0.0
    ans = sum(1 for s in subs if s.get("status") == "answered")
    return ans / len(subs)


def _tri_ratio(d: dict) -> float:
    t = d.get("tri_state") or [0, 0]
    try:
        a, b = int(t[0]), int(t[1])
        return a / b if b else 0.0
    except (TypeError, ValueError, IndexError):
        return 0.0


def _quality(d: dict) -> float:
    cov = _coverage((d.get("pools") or {}).get("1") or {})
    tri = _tri_ratio(d)
    return round(0.55 * cov + 0.45 * tri, 4)


def replay(paths: list[str], limit: int = 20) -> dict:
    mem = MemoryLake()
    used = 0
    routes: Counter = Counter()
    qualities: list[float] = []
    for path in paths[:limit]:
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get("views"):
            continue
        route = [str(x) for x in (d.get("route") or [])]
        rounds = d.get("rounds") or {}
        calls = int(d.get("llm_calls") or 0)
        tokens = int(d.get("llm_tokens") or 0)
        q = _quality(d)
        qualities.append(q)
        routes[",".join(route)] += 1
        used += 1
        # 每层一条 outcome：把整跑成本按层均摊，只学「层-圈数」的先验。
        for entry in route:
            r = int(rounds.get(entry, 1) or 1)
            mem.record_outcome(
                run_id=Path(path).stem, template="%s:r%d" % (entry, r),
                quality=q, calls=max(1, calls // max(1, len(route))),
                tokens=max(1, tokens // max(1, len(route))),
                success=("失败" not in str((d.get("layer_contribution") or {})
                                           .get(entry, {}).get("stop", ""))),
            )
        # 语义层只放「结构读数」，不放答案正文。
        for entry, v in (d.get("views") or {}).items():
            if not isinstance(v, dict):
                continue
            mem.append(
                run_id=Path(path).stem, plane="semantic", layer=str(entry),
                kind="structure", key="structure:%s" % entry,
                payload={"candidates": len(v.get("candidates") or []),
                         "amps": len(v.get("amps") or []),
                         "threads": len(v.get("threads") or []),
                         "suspensions": len(v.get("suspensions") or []),
                         "tier": 3},
                provenance=[Path(path).name],
                confidence=0.6,
            )

    priors = mem.scheduler_priors()
    # 用回放先验跑一次 V2 调度（mock 层，不调 API）
    orch = Orchestrator(mem)
    # 回放用真实量级的预算（V1 的 max_tokens=2M；留一点余量看完整策略）。
    rep = orch.run("回放：如何把不确定性变成可执行动作？",
                   max_tokens=4000000, max_calls=240, max_rounds=40)
    return {
        "runs": used,
        "routes": dict(routes),
        "quality_mean": round(sum(qualities) / max(1, len(qualities)), 4),
        "priors": priors,
        "trace": rep.trace.to_dict(),
        "closure": rep.closure,
        "memory": mem.stats(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="EML/Scheduler v2 真实 packed 回放")
    ap.add_argument("--glob", default="outputs/*.packed.json")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    paths = sorted(glob.glob(args.glob))[-max(1, args.limit):]
    out = replay(paths, limit=len(paths))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
