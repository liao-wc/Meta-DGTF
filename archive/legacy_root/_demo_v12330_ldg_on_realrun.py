#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 效果演示：把层职责守卫（LDG）**回溯**跑在上一版真跑产物上。

产物：`outputs/20261013_205109_如何利用AI来帮助人类实现财富自由甚至文.packed.json`
      （v1.23.29 引擎跑出，98.85 min，四层，167 calls）

问的是：如果当时有守卫，它会在**停止/收敛处**报什么？
输出进 `outputs/_ldg_v12330_回溯_20261013_205109.md`。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"
PK = (HERE / "outputs" /
      "20261013_205109_如何利用AI来帮助人类实现财富自由甚至文.packed.json")

spec = importlib.util.spec_from_file_location("dgtf_v12330", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12330"] = m
spec.loader.exec_module(m)

d = json.loads(PK.read_text(encoding="utf-8"))
q = d["question"]
asp = m.question_aspects(q)

LINES = []
LINES.append("# LDG 回溯：守卫跑在上一版真跑产物上\n")
LINES.append(f"> 产物：`{PK.name}`（引擎 v1.23.29，98.85 min，四层）\n")
LINES.append(f"> 问题：**{q}**\n")
LINES.append("## 问项抽取（规则，零调用）\n")
for a in asp:
    LINES.append(f"- `{a['kind']:>10s}` w={a['weight']:.2f}  {a['text']}")
LINES.append("")
LINES.append("## 各层职责读数（停止处实算）\n")
LINES.append("| 层 | 停止性质 | C 覆盖 | R 相关 | **S 职责** | 直接/无用句 | 缺的 core 问项 |")
LINES.append("|---|---|---|---|---|---|---|")

_for_view = {}
for e in ("0", "1", "both", "all"):
    v = (d.get("views") or {}).get(e) or {}
    st = str(v.get("stop_reason") or "")
    kind = "截断（体力耗尽）" if "体力耗尽" in st else "自然停止"
    dp = v.get("decidable_product") or {}
    mc = v.get("meta_closure") or {}
    parts = [str(v.get("collision") or "")]
    for k in ("answer", "conclusion", "summary", "direct"):
        if dp.get(k):
            parts.append(str(dp[k]))
    for k in ("text", "reason", "summary", "closure"):
        if mc.get(k):
            parts.append(str(mc[k]))
    deliver = "\n".join(p for p in parts if p)
    r = m.duty_of_layer(e, q, deliver,
                        objective_words=m._DUTY_OBJ_WORDS.get(e, ()))
    _for_view[e] = r
    miss = "、".join(r["missing_core"][:2]) or "—"
    LINES.append("| %s | %s | %.2f | %.2f | **%.2f** | %d/%d | %s |"
                 % (e, kind, r["C"], r["R"], r["S"],
                    r["seg_direct"], r["seg_useless"], miss))
LINES.append("")
_short = [e for e in ("0", "1", "both", "all")
          if (_for_view[e] or {}).get("short")]
LINES.append("## 守卫会做的动作\n")
LINES.append(f"- **职责未尽（S<{m._DUTY_FLOOR}）的层：{len(_short)}/4** "
             f"→ {_short if _short else '无'}")
LINES.append("- ⇒ 这些层**不许**署「自然安住」（原产物里 3 层署了自然停止存在）；")
LINES.append("- ⇒ 落地层会多一节「**未答的核心问项**」点名；")
LINES.append("- ⇒ 缺失 core 问项并入后续层 carry（定向提醒）。")
LINES.append("")
LINES.append("## 原始产物的四层自评读数（对照）\n")
LINES.append("| 层 | distance_to_question | 对齐覆盖率 | stop_reason |")
LINES.append("|---|---|---|---|")
p_old = d.get("pools") or {}
for e in ("0", "1", "both", "all"):
    v = (d.get("views") or {}).get(e) or {}
    uch = (p_old.get(e) or {}).get("undecidable_channel") or {}
    ac = uch.get("last_aligned_coverage")
    LINES.append("| %s | %s | %s | %s |"
                 % (e, v.get("distance_to_question"),
                    "—" if ac is None else "%.2f" % float(ac),
                    str(v.get("stop_reason") or "")[:34]))
LINES.append("")
LINES.append("> 注：`distance_to_question` 列里的 `1.0` 在旧口径下是"
             "「模型没报」的缺省顶格（3/4 层如此）—— 这正是本版修掉的"
             "「缺省冒充读数」。")

out = HERE / "outputs" / "_ldg_v12330_回溯_20261013_205109.md"
out.write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\n".join(LINES))
print("\n[落盘]", out)
