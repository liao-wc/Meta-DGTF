# -*- coding: utf-8 -*-
"""等 v1.23.18 真跑落盘，然后核四件事（并做与 v1.23.17 的成本对照）。

① 产物头部文本通道 = 「**开（未挂锚点文件）**」
② 产物**不含**「锚点异常」；**不含**五行零明细（`**锚点对照**：结论`）；
   含一行「**锚点对照**：未做」
③ packed 的 `external_anchor`：enabled True / unconfigured True / error 空
④ 成本：calls / tokens 与 v1.23.17 auto 组对照（不应因默认打开而增加）
"""
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}


def wait_packed(timeout=4200):
    t0 = time.time()
    d = HERE / "outputs" / "_v12318_auto"
    while time.time() - t0 < timeout:
        fs = sorted(d.glob("*.packed.json"), key=lambda p: p.stat().st_mtime)
        done = "完成" in (HERE / "_v12318_realrun_driver.log").read_text(
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

print("\n=== ① 头部文本通道 ===")
_head = t.split("\n## ")[0]
for l in _head.split("\n"):
    if "外部锚点" in l:
        print("   ", l[:120])
print("   头部含「开（未挂锚点文件）」:", "开（未挂锚点文件）" in _head)

print("\n=== ② 明细与异常 ===")
print("   含「锚点异常」:", "**锚点异常**" in t)
print("   含五行零明细「**锚点对照**：结论」:", "**锚点对照**：结论" in t)
print("   含「**锚点对照**：未做」:", "**锚点对照**：未做" in t)
print("   含「**锚点分级**」:", "**锚点分级**" in t)

print("\n=== ③ packed 的 external_anchor ===")
ea = d.get("external_anchor")
print("   类型:", type(ea).__name__)
if isinstance(ea, dict):
    print("   enabled=%r unconfigured=%r anchors=%r error=%r"
          % (ea.get("enabled"), ea.get("unconfigured"), ea.get("anchors"),
             ea.get("error")))

print("\n=== ④ 成本与停圈（v1.23.17 → v1.23.18）===")
p17 = sorted((HERE / "outputs" / "_v12317_auto").glob("*.packed.json"))[-1]
a = json.loads(p17.read_text(encoding="utf-8"))
print("   calls:  %s → %s" % (a.get("llm_calls"), d.get("llm_calls")))
print("   tokens: %s → %s" % (a.get("llm_tokens"), d.get("llm_tokens")))


def nat(x):
    n = 0
    for e in ("0", "1", "both", "all"):
        v = (x.get("views") or {}).get(e) or {}
        if "体力耗尽" not in str(v.get("stop_reason") or ""):
            n += 1
    return n


print("   自然停层数: %d/4 → %d/4" % (nat(a), nat(d)))
for e in ("0", "1", "both", "all"):
    va = (a.get("views") or {}).get(e) or {}
    vb = (d.get("views") or {}).get(e) or {}
    print("   %-3s %s: run %s/%s → run %s/%s"
          % (e, NAME[e], va.get("rounds_run"), va.get("rounds_cap"),
             vb.get("rounds_run"), vb.get("rounds_cap")))
json.dump({"v12317": {k: a.get(k) for k in ("llm_calls", "llm_tokens")},
           "v12318": {k: d.get(k) for k in ("llm_calls", "llm_tokens")},
           "ea": ea}, open(HERE / "_v12318_cmp.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n已写 _v12318_cmp.json")
