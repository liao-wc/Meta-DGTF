# -*- coding: utf-8 -*-
"""诊断 2：settle / crystallize 的**原始来源**是否结构退化。

· settle      ← v["settlement"]  {answered, total}
· crystallize ← meta_closure / engagements / suspensions 四件事命中
只读产物，不改任何东西。
"""
import glob
import json
import os

files = sorted(glob.glob("outputs/*.packed.json"), key=os.path.getmtime, reverse=True)

print("=" * 84)
print("settle 来源 settlement{answered,total}  与  crystallize 四件事命中")
print("=" * 84)

from collections import Counter
settle_pairs = Counter()
crys_hits = Counter()
eng_len = Counter()
susp_len = Counter()
clo_present = Counter()

for f in files[:10]:
    d = json.load(open(f, encoding="utf-8"))
    for L in ("1", "all"):
        v = (d.get("views") or {}).get(L)
        if not v:
            continue
        if L == "1":
            s = v.get("settlement") or {}
            a, t = s.get("answered"), s.get("total")
            settle_pairs[(a, t)] += 1
            print("  settle  层1   answered=%s total=%s  → %.3f"
                  % (a, t, (a / t if (t and a is not None) else -1)))
        else:
            clo = v.get("meta_closure") or {}
            eng = v.get("engagements") or []
            sus = v.get("suspensions") or []
            h = 0
            if clo:
                h += 1
                if clo.get("total") is not None:
                    h += 1
            if eng:
                h += 1
            if sus:
                h += 1
            crys_hits[h] += 1
            eng_len[len(eng)] += 1
            susp_len[len(sus)] += 1
            clo_present[("总" if clo.get("total") is not None else "无总") if clo else "无clo"] += 1
            print("  crys  层all  clo=%s(total=%s) engagements=%d suspensions=%d → %d/4=%.3f"
                  % (bool(clo), clo.get("total"), len(eng), len(sus), h, h / 4))

print("\n" + "=" * 84)
print("汇总")
print("  settle (answered,total) 分布:", dict(settle_pairs))
print("  crystallize 命中数分布   :", dict(crys_hits))
print("  engagements 长度分布     :", dict(eng_len))
print("  suspensions 长度分布     :", dict(susp_len))
print("  meta_closure 形态        :", dict(clo_present))
