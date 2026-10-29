# -*- coding: utf-8 -*-
"""去重 web 增量：_route_round_tokens 已含 web 因子，dynamic_config 不再重复乘。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''            q = base_q
            if wb == "on" and kind == "fact":
                tok *= (1.0 + _WEB_TOKENS_EXTRA)
                q = max(q, 0.955)          # 事实 web on 实测 0.958（fast）'''
new = '''            q = base_q
            if wb == "on" and kind == "fact":
                # token 增量已在 _route_round_tokens 内计入，这里只抬质量
                q = max(q, 0.955)          # 事实 web on 实测 0.958（fast）'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK dedupe web factor")
