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


def _entry_quality(d: dict, entry: str) -> float:
    """按层计算质量代理：不同层不再共享整跑 quality。

    只用 packed 里已有的结构读数，不读答案正文：
      · 0/1：候选/子问题覆盖 + 质量 flag 惩罚；
      · both：裁决数相对线头数的收敛；
      · all：meta_closure 的 clean/decision/actions 完整度。
    """
    v = (d.get("views") or {}).get(str(entry))
    if not isinstance(v, dict):
        return 0.0
    flags = len(v.get("quality_flags") or [])
    flag_pen = max(0.0, 1.0 - min(flags, 10) * 0.1)
    content = 1.0 if any(v.get(k) for k in (
        "candidates", "amps", "sub_questions", "adjudications",
        "threads", "meta_closure")) else 0.0
    if entry == "1":
        subs = v.get("sub_questions") or []
        cov = (sum(1 for s in subs if isinstance(s, dict)
                   and s.get("status") == "answered") / len(subs)) if subs else 0.5
    elif entry == "both":
        n_thread = len(v.get("threads") or [])
        n_adj = len(v.get("adjudications") or [])
        cov = (n_adj / n_thread) if n_thread else (0.6 if n_adj else 0.0)
        cov = max(0.0, min(1.0, cov))
    elif entry == "all":
        mc = v.get("meta_closure") or {}
        cov = 0.0
        if isinstance(mc, dict):
            cov += 0.5 if mc.get("clean") else 0.0
            cov += 0.25 if mc.get("decision") else 0.0
            cov += 0.25 if mc.get("actions") else 0.0
        cov = max(0.0, min(1.0, cov))
    else:
        cands = len(v.get("candidates") or [])
        cov = min(1.0, cands / 6.0)
    return round(max(0.0, min(1.0, 0.5 * cov + 0.3 * content + 0.2 * flag_pen)), 4)


def replay(paths: list[str], limit: int = 20,
           memory_path: str | Path | None = None) -> dict:
    mem = MemoryLake(memory_path)
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
                quality=_entry_quality(d, entry), calls=max(1, calls // max(1, len(route))),
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
