#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量化「锚点重述」与「探针设计」的合理性 —— 用引擎自己的尺子。

★ 关键纪律：相似度一律用**引擎实现本体**（`_similar` / `_overlap_coef` /
  `_sim_ratio`），不另造一把尺子 —— 否则读数不可与引擎内判据对照。

零 LLM，只读 packed.json。
"""
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "outputs"

# ---------- 载入引擎（拿它的尺子）----------
SRC = HERE / "元DGTF-V1.23.25.py"
_src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
mod = types.ModuleType("dg")
mod.__file__ = str(SRC)
sys.modules["dg"] = mod
exec(compile(_src, str(SRC), "exec"), mod.__dict__)

_similar = mod._similar
_overlap_coef = mod._overlap_coef
_sim_ratio = mod._sim_ratio
_kw = mod._kw
print(f"引擎 {mod.__version__}；尺子：_similar(0.75) / _overlap_coef(top_n=8) 阈值 0.3")


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def pick_latest(n=8):
    fs = sorted(OUT.glob("*.packed.json"), key=lambda x: x.stat().st_mtime)
    return fs[-n:]


rows = []

for p in pick_latest(8):
    d = load(p)
    q = str(d.get("question", ""))
    for layer in ("0", "1"):
        lv = (d.get("views") or {}).get(layer)
        if not isinstance(lv, dict):
            continue
        anchor = str(lv.get("anchor") or "").strip()
        at = [str(x.get("desc", "")).strip() for x in (lv.get("anchor_touched") or [])]
        at = [x for x in at if x]
        ut = [str(x.get("desc", "")).strip() for x in (lv.get("untouched") or [])]
        ut = [x for x in ut if x]
        pr = lv.get("probes") or []
        rl = lv.get("round_log") or []
        rows.append(dict(
            name=p.name.split("_", 2)[-1][:34], layer=layer, q=q,
            anchor=anchor, at=at, ut=ut, pr=pr, rl=rl,
            rounds=lv.get("rounds_run"), stop=str(lv.get("stop_reason") or "")[:50],
        ))

print("\n" + "=" * 104)
print("表 1 · 锚点重述：touched 证据链")
print("=" * 104)
print(f"{'产物/层':<40}{'圈':>3}{'touched':>8}{'untouch':>8}{'探针':>5}"
      f"{'anchor字数':>10}{'代词?':>7}{'touched空?':>10}")
tot_at = tot_ut = tot_pr = 0
n_empty_at = 0
n_pron = 0
for r in rows:
    a = r["anchor"]
    pron = any(t in a for t in ("它", "这", "那", "此"))
    tag = f"{r['name'][:32]}/{r['layer']}"
    print(f"{tag:<40}{r['rounds'] or 0:>3}{len(r['at']):>8}{len(r['ut']):>8}"
          f"{len(r['pr']):>5}{len(a):>10}{('有' if pron else '-'):>7}"
          f"{('空!' if not r['at'] else 'ok'):>10}")
    tot_at += len(r["at"]); tot_ut += len(r["ut"]); tot_pr += len(r["pr"])
    n_empty_at += (0 if r["at"] else 1)
    n_pron += (1 if pron else 0)

print("-" * 104)
print(f"合计：层×产物 = {len(rows)}；touched 共 {tot_at} 条 / untouched 共 {tot_ut} 条 / 探针共 {tot_pr} 条")
print(f"★ touched 为空的层：{n_empty_at} / {len(rows)}")
print(f"★ anchor 含指示代词（它/这/那/此）：{n_pron} / {len(rows)}")
