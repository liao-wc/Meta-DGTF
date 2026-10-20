# -*- coding: utf-8 -*-
import json, io
p = "outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json"
d = json.load(io.open(p, encoding="utf-8"))
wr = (d.get("pools") or {}).get("1", {}).get("web_results") or []
for i, x in enumerate(wr[:8]):
    print("---", i, type(x))
    print(json.dumps(x, ensure_ascii=False, indent=1)[:1500])
