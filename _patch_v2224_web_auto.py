# -*- coding: utf-8 -*-
"""动态配置微调：web=auto 时不落 opts（交给引擎自决），避免改变既有 apply_plan 语义。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    if not opts.get("web") and str(chosen["web"]) != str(web or "auto"):
        applied["web"] = chosen["web"]'''
new = '''    # web=auto 表示"交给引擎自决"：动态配置只记录 chosen，不写 opts
    # （否则会把 auto 落成具体值，改变 apply_plan 的既有语义）。
    if (not opts.get("web") and str(web) not in ("", "auto")
            and str(chosen["web"]) != str(web)):
        applied["web"] = chosen["web"]'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK web auto not applied")
