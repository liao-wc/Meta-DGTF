#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[G] 真模型单点探针：`_re_anchor` 在**真实 API** 上会不会吐占位符。

为什么要它：G 只在"模型真吐了占位符"时才可观测。真跑产物里看到的是
**清洗之后**的列表，所以"产物里没有占位符"既可能是修复生效，也可能是模型没吐。
这里直接打**清洗前的原始 payload**，把两件事分开。
"""
import contextlib, io, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import importlib.util
spec = importlib.util.spec_from_file_location("d70", str(HERE / "元DGTF-V1.21.70.py"))
m = importlib.util.module_from_spec(spec); sys.modules["d70"] = m
spec.loader.exec_module(m)

# 载入 .env
env = HERE / ".env"
if env.exists():
    for ln in env.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            import os
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

PLACE = {"此处未生", "（此处未生）", "(此处未生)", "无", "（无）", "(无)",
         "暂无", "未知", "n/a", "N/A"}
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"

cfg = m.load_config(str(HERE / "__nonexistent__.yaml"))
dg = m.DGTF("0", m.LLM(cfg), cfg)
dg.verbose = False

raws, outs = [], []
for i in range(3):
    inp = m.Input(question=Q, round_role="摊开", round_no=1)
    inp.pool = m.Pool()
    cap = {}
    real_call = dg.llm.call
    def spy(system, user, *a, **k):
        r = real_call(system, user, *a, **k)
        cap["raw"] = r
        return r
    dg.llm.call = spy
    with contextlib.redirect_stdout(io.StringIO()):
        _a, t, u = dg._re_anchor(inp)
    dg.llm.call = real_call
    raw = cap.get("raw", "")
    try:
        rawp = json.loads(m.LLM(cfg).parse_json(raw) and json.dumps(
            json.loads(raw), ensure_ascii=False))
    except Exception:
        rawp = None
    rt = None; ru = None
    try:
        obj = json.loads(raw)
        rt = [str(x).strip() for x in (obj.get("touched") or [])]
        ru = [str(x).strip() for x in (obj.get("untouched") or [])]
    except Exception:
        pass
    ph_raw = [x for x in ((rt or []) + (ru or []))
              if x in PLACE or x.replace("（", "(").replace("）", ")") in PLACE]
    print(f"--- 第 {i+1} 次 ---")
    print(f"  原始 touched   = {rt}")
    print(f"  原始 untouched = {ru}")
    print(f"  原始里的占位符 = {ph_raw}")
    print(f"  清洗后 touched   = {t}")
    print(f"  清洗后 untouched = {u}")
    print(f"  ⇒ 这一跑 {'**用到了 G 的修复**' if ph_raw else '模型没吐占位符（对 G 是可证明的无操作）'}")
    raws.append(ph_raw); outs.append((t, u))

print()
print(f"3 次里模型吐占位符的次数：{sum(1 for x in raws if x)}/3")
