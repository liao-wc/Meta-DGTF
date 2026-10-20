# -*- coding: utf-8 -*-
import json, io, sys
p = "outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json"
d = json.load(io.open(p, encoding="utf-8"))
print("TOP:", list(d.keys()))
print("input_sanity:", json.dumps(d.get("input_sanity"), ensure_ascii=False, indent=1)[:2000])
fc = d.get("fact_contract") or {}
print("fc keys:", list(fc.keys()))
print("fc ok_all:", fc.get("ok_all"), "ledger:", json.dumps(fc.get("ledger"), ensure_ascii=False)[:800])
for e, r in (fc.get("layers") or {}).items():
    print("fc layer", e, json.dumps(r, ensure_ascii=False)[:500])
pools = d.get("pools") or {}
print("pools:", list(pools.keys()))
for e, p0 in pools.items():
    if not isinstance(p0, dict):
        print(e, type(p0)); continue
    wr = p0.get("web_results") or []
    print("pool", e, "web_results n=", len(wr))
    for x in wr[:6]:
        if isinstance(x, dict):
            print("  ", {k: str(x.get(k))[:120] for k in ("title", "url", "official", "claim", "snippet", "date")})
