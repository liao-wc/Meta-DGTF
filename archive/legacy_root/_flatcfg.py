# -*- coding: utf-8 -*-
"""[v1.23.4] 小工具：对读两份配置，打印差异项数。

用法：python _flatcfg.py <src.py> <cfgA> <cfgB>
"""
import importlib.util
import json
import sys
from pathlib import Path

src, ca, cb = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("m_flat", src)
m = importlib.util.module_from_spec(spec)
sys.modules["m_flat"] = m
spec.loader.exec_module(m)


def flat(d, pre=""):
    out = {}
    for k, v in (d or {}).items():
        key = ("%s.%s" % (pre, k)) if pre else str(k)
        if isinstance(v, dict):
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


a = m.load_config(ca)
b = m.load_config(cb)
fa, fb = flat(a), flat(b)
diff = [(k, fa.get(k, "<缺>"), fb.get(k, "<缺>"))
        for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
print("DIFF %d" % len(diff))
for k, x, y in diff:
    print("   %-46s %r -> %r" % (k, x, y))
print("JSON_EQUAL", json.dumps(a, sort_keys=True, ensure_ascii=False)
      == json.dumps(b, sort_keys=True, ensure_ascii=False))
