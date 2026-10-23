# -*- coding: utf-8 -*-
"""v1.23.25 真产物对照：结构覆盖率（自触及）vs 独立度 vs 旧结构覆盖率。

★ 判据落在**实现本体**上：逐圈调 `Pool.add_undecidable`（喂该圈的实际
  线头/探针/自报触及），不是自己复刻公式。
"""
import glob
import json
import os
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location(
    "dg25", str(HERE / "元DGTF-V1.23.25.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["dg25"] = mod
spec.loader.exec_module(mod)

print(f"引擎 {mod.__version__}")
print("=" * 104)
print(f"{'产物':<40}{'S':>3}{'旧struct':>10}{'新·sc':>9}"
      f"{'touched':>9}{'独立度':>9}  判定")
print("-" * 104)

rows = []
for fp in sorted(glob.glob(str(HERE / "outputs" / "*.packed.json")),
                 key=os.path.getmtime)[-8:]:
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    p1 = (d.get("pools") or {}).get("1") or {}
    uc = p1.get("undecidable_channel") or {}
    S = list(uc.get("structural_amps") or [])
    if not S:
        continue
    A = list(uc.get("und_aspects") or [])
    # 按实现本体重跑：把该产物的下游文本（线头/探针/自报触及）喂进去
    pool = mod.Pool()
    pool.add_undecidable(
        {"clarity": float(uc.get("last_clarity", 0.0) or 0.0),
         "structural_amps": S, "aligned_amps": list(uc.get("aligned_amps") or [])},
        und_aspects=A, layer=1, covered_aspects=[])
    # 补入该产物真实的下游文本
    for t in (p1.get("threads") or []):
        pool.threads.append(dict(t))
    for pb in (p1.get("probes") or []):
        pool.probes.append(dict(pb))
    _ca = []
    for _k, _v in (d.get("views") or {}).items():
        if isinstance(_v, dict) and _v.get("covered_aspects"):
            _ca += list(_v["covered_aspects"])
    if _ca:
        pool.add_undecidable(
            {"clarity": 0.0, "structural_amps": [], "aligned_amps": []},
            und_aspects=[], layer=2, covered_aspects=_ca)

    ch = pool.undecidable_channel
    sc = ch.get("last_sc_ratio")
    nsc = int(ch.get("last_sc_touched", 0) or 0)
    indep = ch.get("last_indep_ratio")
    old = uc.get("last_struct_coverage")
    same_old = (sc is not None and abs(sc - (old or 0)) < 1e-9)
    rows.append((old, sc, indep, nsc, len(S)))
    _sc = f"{sc:.3f}" if sc is not None else "None"
    _id = f"{indep:.3f}" if indep is not None else "None"
    verdict = "← 与旧值同!" if same_old else "ok（新旧不同）"
    print(f"{os.path.basename(fp)[:38]:<40}{len(S):>3}"
          f"{str(old):>10}{_sc:>9}{nsc:>9}{_id:>9}  {verdict}")

print("-" * 104)
print("判据：")
n_ok = sum(1 for r in rows if r[1] is not None
           and abs(r[1] - (r[0] or 0)) >= 1e-9)
print(f"  · 新旧不同的份数：{n_ok}/{len(rows)}（应 == 全部分母非空者）")
_scs = [r[1] for r in rows if r[1] is not None]
if _scs:
    print(f"  · 新值范围 [{min(_scs):.3f}, {max(_scs):.3f}]（应有跨度，不是恒 0/恒 1）")
_ids = [r[2] for r in rows if r[2] is not None]
if _ids:
    print(f"  · 独立度范围 [{min(_ids):.3f}, {max(_ids):.3f}]")
