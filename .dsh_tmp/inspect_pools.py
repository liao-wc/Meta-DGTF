# -*- coding: utf-8 -*-
import json, io
p = "outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json"
d = json.load(io.open(p, encoding="utf-8"))
for e, p0 in (d.get("pools") or {}).items():
    print("POOL", e, "keys:", list(p0.keys()) if isinstance(p0, dict) else type(p0))
    if isinstance(p0, dict):
        for k, v in p0.items():
            if isinstance(v, list):
                print("   ", k, "list n=", len(v), "sample keys:", list(v[0].keys()) if v and isinstance(v[0], dict) else type(v[0]) if v else None)
            elif isinstance(v, dict):
                print("   ", k, "dict keys:", list(v.keys())[:12])
print("external_anchor:", json.dumps(d.get("external_anchor"), ensure_ascii=False)[:1200])
print("quality keys:", list((d.get("quality") or {}).keys()))
print("views keys:", list((d.get("views") or {}).keys()))
for e, v in (d.get("views") or {}).items():
    print("VIEW", e, "keys:", list(v.keys()) if isinstance(v, dict) else type(v))
