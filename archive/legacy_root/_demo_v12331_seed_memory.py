#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 演示：用**最近一次真跑产物**给元DGTF 建首个记忆库。

做法：把上一版真跑的产物 dict 直接喂给 `_eml_finish` —— 即「历史跑次也能
补录成 episode」，这正是「储存记忆」的第一步：盘面上已有的跑次不该白跑。

产出：仓库根 `dgtf_memory/`（episodes.jsonl / playbook.jsonl / MEMORY.md）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"
PKS = [
    ("20261013_205109_如何利用AI来帮助人类实现财富自由甚至文.packed.json", "真跑"),
    ("20261013_155915_验证信念四态与语义熵是否真的落盘.packed.json", "真跑"),
    ("20261013_144044_验证信念四态与语义熵是否真的落盘.packed.json", "真跑"),
    ("20261013_131751_城市内涝频发排水系统改造应该优先做管网.packed.json", "真跑"),
    ("20261013_071430_普通人应该做些什么来迎接AI时代的到来.packed.json", "真跑"),
]

spec = importlib.util.spec_from_file_location("dgtf_v12331", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12331"] = m
spec.loader.exec_module(m)

cfg = dict(m.DEFAULT_CONFIG)
cfg["playbook"] = {"mode": "on", "dir": "", "top_k": 3,
                   "promote_n": 3, "halflife_days": 14.0}
eng = m.MetaDGTF(cfg)
eng._eml_mode = "on"
eng._duty_floor = float(cfg["duty"]["floor"])

n = 0
for name, tag in PKS:
    fp = HERE / "outputs" / name
    if not fp.is_file():
        continue
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        continue
    d.setdefault("id", name[:15])
    d.setdefault("question", "")
    blk = eng._eml_finish(d)
    n += 1
    print("补录 %-46s → 过闸新增 %d / 闸拒 %d / 升级 %d / 库 %d"
          % (name[:44], len(blk.get("merged") or []),
             len(blk.get("gated_out") or []),
             len(blk.get("promoted") or []), blk.get("n_playbook", 0)))

d = m.eml_dir()
print("\n记忆库目录：", d)
for f in ("episodes.jsonl", "playbook.jsonl", "MEMORY.md"):
    p = d / f
    print("  %-14s %s %d bytes" % (f, "OK" if p.is_file() else "缺失",
                                   p.stat().st_size if p.is_file() else 0))
print("\n=== MEMORY.md ===")
print((d / "MEMORY.md").read_text(encoding="utf-8"))
pb = m.eml_read_jsonl(d / "playbook.jsonl")
print("=== playbook 摘要（%d 条）===" % len(pb))
for e in pb:
    print(" %-6s %-9s %-9s n_ev=%d contra=%d action=%s"
          % (e.get("id"), e.get("kind"), e.get("status"),
             e.get("n_evidence", 0), e.get("contra", 0),
             json.dumps(e.get("action") or {}, ensure_ascii=False)[:60]))
print("\n补录跑次：%d" % n)
