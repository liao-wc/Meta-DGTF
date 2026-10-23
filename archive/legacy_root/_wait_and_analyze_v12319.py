# -*- coding: utf-8 -*-
"""等 v1.23.19 真跑（retriever=tavily）落盘，然后核「那条路真的走通了」。"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def wait_packed(timeout=4200):
    t0 = time.time()
    d = HERE / "outputs" / "_v12319_tavily"
    while time.time() - t0 < timeout:
        fs = sorted(d.glob("*.packed.json"), key=lambda p: p.stat().st_mtime)
        done = "完成" in (HERE / "_v12319_realrun_driver.log").read_text(
            encoding="utf-8", errors="replace")
        if fs and done:
            return fs[-1]
        time.sleep(20)
    return None


pk = wait_packed()
if pk is None:
    print("超时：真跑没落盘")
    raise SystemExit(1)
print("packed:", pk.name)

d = json.loads(pk.read_text(encoding="utf-8"))
md = sorted(pk.parent.glob("*.md"))[-1]
t = md.read_text(encoding="utf-8")
head = t.split("\n## ")[0]

print("\n=== ① 头部文本通道（应为「开」+ 真检索后端）===")
for l in head.split("\n"):
    if "外部锚点" in l:
        print("   ", l[:150])

print("\n=== ② 明细（对照到底做了没）===")
for key in ("**锚点对照**", "**锚点分级**", "**triage 降级**", "**锚点入池**",
            "**冲突**", "**锚点异常**", "### 外部锚点 · 逐条对照"):
    print("   %-22s %s" % (key, key in t))
for l in t.split("\n"):
    if l.startswith("**锚点") or l.startswith("**triage") or l.startswith("**冲突"):
        print("   >>", l[:130])

print("\n=== ③ packed 的 external_anchor ===")
ea = d.get("external_anchor") or {}
for k in ("enabled", "unconfigured", "anchors", "retriever_mode", "anchor_calls",
          "pooled", "error"):
    print("   %-16s %r" % (k, ea.get(k)))
print("   summary:", ea.get("summary"))
print("   items 前 2 条：")
for it in (ea.get("items") or [])[:2]:
    print("     ", json.dumps(it, ensure_ascii=False)[:150])

print("\n=== ④ 日志里的检索/对照痕迹 ===")
lg = (HERE / "_v12319_run_tavily.log").read_text(encoding="utf-8",
                                                 errors="replace")
print("   「⚓ 锚点入池」行数:", lg.count("锚点入池"))
print("   「⚓ 外部锚点对照」行数:", lg.count("外部锚点对照"))
print("   缓存命中（cache/anchors）目录文件数:",
      len(list((HERE / "cache" / "anchors").glob("*.json"))))
for l in lg.split("\n"):
    if "⚓" in l:
        print("   >>", l.strip()[:130])

print("\n=== ⑤ 成本（v1.23.18 默认 → v1.23.19 tavily）===")
p18 = sorted((HERE / "outputs" / "_v12318_auto").glob("*.packed.json"))[-1]
a = json.loads(p18.read_text(encoding="utf-8"))
print("   calls:  %s → %s" % (a.get("llm_calls"), d.get("llm_calls")))
print("   tokens: %s → %s" % (a.get("llm_tokens"), d.get("llm_tokens")))
json.dump({"ea": ea, "calls": d.get("llm_calls"),
           "tokens": d.get("llm_tokens")},
          open(HERE / "_v12319_cmp.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n已写 _v12319_cmp.json")
