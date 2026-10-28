# -*- coding: utf-8 -*-
"""产物质量分析：读 outputs/*.packed.json，做多轴读数统计与短板定位。

只读，不改任何产物。输出 JSON + 控制台摘要。
"""
from __future__ import annotations

import glob
import json
import os
import statistics as st
from collections import Counter, defaultdict

ROWS = []


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None      # 排除 NaN
    except (TypeError, ValueError):
        return None


def _pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]


def load():
    for p in glob.glob("outputs/*.packed.json"):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        q = d.get("quality") or {}
        ROWS.append({
            "path": p,
            "mtime": os.path.getmtime(p),
            "q": q,
            "d": d,
            "cov": _num(q.get("coverage")),
            "alpha": _num(q.get("tri_alpha")),
            "aq": _num(q.get("answer_quality")),
            "depth": _num(q.get("depth")),
            "ready": bool(q.get("answer_ready")),
            "pready": bool(q.get("process_ready")),
            "flags": list(q.get("flags_normalized") or []),
            "reliable": bool(q.get("tri_reliable")),
            "calls": int(d.get("llm_calls") or 0),
            "tokens": int(d.get("llm_tokens") or 0),
            "question": str(d.get("question") or ""),
            "route": list(d.get("route") or []),
            "rounds": d.get("rounds") or {},
            "dist": q.get("tri_distribution") or {},
        })
    ROWS.sort(key=lambda r: r["mtime"])


def fmt(v, nd=3):
    return "—" if v is None else ("%.*f" % (nd, v))


def main():
    load()
    n = len(ROWS)
    print("=" * 72)
    print("产物质量分析 · %d 个 packed" % n)
    print("=" * 72)

    # ---- 1. 覆盖与就绪 ----
    cov = [r["cov"] for r in ROWS if r["cov"] is not None]
    aq = [r["aq"] for r in ROWS if r["aq"] is not None]
    dep = [r["depth"] for r in ROWS if r["depth"] is not None]
    alpha = [r["alpha"] for r in ROWS if r["alpha"] is not None]
    ready = sum(r["ready"] for r in ROWS)
    pready = sum(r["pready"] for r in ROWS)

    print("\n【1】核心读数")
    print("  coverage   n=%d  mean=%.3f  p10=%.2f  p50=%.2f  p90=%.2f  <1.0 占 %.0f%%"
          % (len(cov), st.mean(cov), _pct(cov, .1), _pct(cov, .5), _pct(cov, .9),
             100 * sum(1 for x in cov if x < 0.999) / max(1, len(cov))))
    print("  answer_q   n=%d  mean=%s  p10=%s  p50=%s  p90=%s"
          % (len(aq), fmt(st.mean(aq)) if aq else "—",
             fmt(_pct(aq, .1)), fmt(_pct(aq, .5)), fmt(_pct(aq, .9))))
    print("  depth      n=%d  mean=%s  p50=%s  max=%s"
          % (len(dep), fmt(st.mean(dep), 2) if dep else "—",
             fmt(_pct(dep, .5), 2), fmt(max(dep), 2) if dep else "—"))
    print("  answer_ready  %d/%d (%.0f%%)   process_ready  %d/%d (%.0f%%)"
          % (ready, n, 100 * ready / n, pready, n, 100 * pready / n))

    # ---- 2. 跨视角一致性（α）----
    print("\n【2】跨视角一致性 tri_alpha（Krippendorff）")
    if alpha:
        neg = sum(1 for x in alpha if x < 0)
        low = sum(1 for x in alpha if 0 <= x < 0.667)
        ok = sum(1 for x in alpha if x >= 0.667)
        print("  n=%d  mean=%.3f  p10=%.3f  p50=%.3f  p90=%.3f"
              % (len(alpha), st.mean(alpha), _pct(alpha, .1),
                 _pct(alpha, .5), _pct(alpha, .9)))
        print("  α<0（系统性分歧）%d (%.0f%%) ｜ 0≤α<0.667（不可靠）%d (%.0f%%) ｜ α≥0.667（可用）%d (%.0f%%)"
              % (neg, 100 * neg / len(alpha), low, 100 * low / len(alpha),
                 ok, 100 * ok / len(alpha)))
        ck = Counter(r["q"].get("tri_alpha_verdict") or "—" for r in ROWS
                     if r["alpha"] is not None)
        for k, v in ck.most_common(4):
            print("    · %-46s %d" % (str(k)[:46], v))

    # ---- 3. 质量旗标 ----
    print("\n【3】质量旗标（flags_normalized）")
    fc = Counter()
    for r in ROWS:
        for f in set(r["flags"]):
            fc[f] += 1
    noflag = sum(1 for r in ROWS if not r["flags"])
    print("  无任何旗标：%d/%d (%.0f%%)" % (noflag, n, 100 * noflag / n))
    for k, v in fc.most_common(12):
        print("    %-42s %3d (%.0f%%)" % (k[:42], v, 100 * v / n))

    # ---- 4. 判定分布 ----
    print("\n【4】三态判定分布（decidable / partial / undecidable 之和）")
    tot = Counter()
    for r in ROWS:
        for k, v in (r["dist"] or {}).items():
            try:
                tot[k] += int(v)
            except (TypeError, ValueError):
                pass
    s = sum(tot.values()) or 1
    for k, v in tot.most_common():
        print("    %-14s %5d (%.1f%%)" % (k, v, 100 * v / s))

    # ---- 5. 成本关联 ----
    print("\n【5】成本与质量的关系")
    buckets = defaultdict(list)
    for r in ROWS:
        c = r["calls"]
        b = "0-19" if c < 20 else "20-49" if c < 50 else "50-99" if c < 100 else "100+"
        if r["cov"] is not None:
            buckets[b].append(r["cov"])
    for b in ("0-19", "20-49", "50-99", "100+"):
        v = buckets.get(b) or []
        if v:
            print("    calls %-7s n=%3d  coverage 均值 %.3f" % (b, len(v), st.mean(v)))

    # ---- 6. 时间趋势（按日）----
    print("\n【6】时间趋势（按天，coverage 均值 / α<0 占比）")
    byday = defaultdict(list)
    import datetime as dt
    for r in ROWS:
        day = dt.datetime.fromtimestamp(r["mtime"]).strftime("%m-%d")
        byday[day].append(r)
    for day in sorted(byday)[-10:]:
        rs = byday[day]
        cv = [x["cov"] for x in rs if x["cov"] is not None]
        al = [x["alpha"] for x in rs if x["alpha"] is not None]
        negp = (100 * sum(1 for x in al if x < 0) / len(al)) if al else 0
        print("    %s  n=%3d  cov=%.3f  α<0 占 %3.0f%%"
              % (day, len(rs), st.mean(cv) if cv else 0, negp))

    # ---- 7. 短板样本 ----
    print("\n【7】最弱样本（coverage 最低且 answer_ready=False）")
    weak = [r for r in ROWS if r["cov"] is not None and not r["ready"]]
    weak.sort(key=lambda r: (r["cov"], -(r["calls"] or 0)))
    for r in weak[:8]:
        print("    cov=%.2f calls=%3d flags=%s ｜ %s"
              % (r["cov"], r["calls"], ",".join(r["flags"])[:40] or "-",
                 r["question"][:34]))

    out = {
        "n": n,
        "coverage": {"mean": st.mean(cov) if cov else None,
                     "p50": _pct(cov, .5), "n": len(cov),
                     "below_1": sum(1 for x in cov if x < 0.999)},
        "answer_quality": {"mean": st.mean(aq) if aq else None, "n": len(aq)},
        "depth": {"mean": st.mean(dep) if dep else None, "n": len(dep)},
        "alpha": {"mean": st.mean(alpha) if alpha else None, "n": len(alpha),
                  "neg": sum(1 for x in alpha if x < 0) if alpha else 0},
        "ready": ready, "pready": pready,
        "flags": dict(fc),
        "no_flag": noflag,
    }
    json.dump(out, open("docs/产物质量分析_20261028.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n写出 docs/产物质量分析_20261028.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
