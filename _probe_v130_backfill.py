# -*- coding: utf-8 -*-
"""[v1.30.0] 候选回填留痕探针：验证「原因 + 来源 + 去重键」与去重/置信/评估。

只验证新增的纯函数与 `DGTF._record_backfill_diag` 接线，不跑 LLM。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.30.0.py"

spec = importlib.util.spec_from_file_location("dgtf_bf_probe", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_bf_probe"] = mod
spec.loader.exec_module(mod)

ok, bad = 0, []


def ck(name, cond, note=""):
    global ok
    if cond:
        ok += 1
    else:
        bad.append(f"{name}：{note}")


def cand(desc, source="阴", attribute="0", position="0"):
    return {"desc": desc, "source": source, "attribute": attribute,
            "position": position}


# ── 1. 去重键：规范化稳定、同文同键、异文异键 ──
k1 = mod._candidate_dedup_key("库存分片热点 SKU 的扣减承诺")
k2 = mod._candidate_dedup_key("  库存分片热点，SKU 的扣减承诺！ ")
k3 = mod._candidate_dedup_key("完全不同的另一条候选描述")
ck("去重键：忽略空白/标点", k1 == k2, f"{k1} != {k2}")
ck("去重键：不同文本不同键", k1 != k3, f"{k1} == {k3}")
ck("去重键：长度 12", len(k1) == 12, str(len(k1)))
ck("去重键：空文本为空", mod._candidate_dedup_key("  ") == "")

# ── 2. 逐条来源 / 原生判定 / 去重对 ──
expanded = ["原生候选一：分区期间少卖的计量单位", "原生候选二：r 受存储限制"]
cands = [
    cand("原生候选一：分区期间少卖的计量单位", "阴"),
    cand("原生候选二：r 受存储限制", "阳"),
    cand("后补候选甲：先测分片键分布再谈窗口", "阳"),
    cand("后补候选乙：恢复瞬间积压与迁移叠加", "阴"),
    cand("后补候选甲：先测分片键分布再谈窗口", "阳"),  # 与第 3 条重复
    cand("后补候选丙：心跳租约下界只保证不误判", "阳"),
]
d = mod._backfill_diagnose(
    cands, expanded, [2, 3, 3, 4, 5, 6, 99, "x"],
    trigger="self_check.suspicious_candidates",
    reason="self-check 判定为后补（非展开生长）",
    entry="both", round_no=2, threshold=5)
ck("来源层：entry/round 落账",
   d["source"]["layer"] == "both" and d["source"]["round"] == 2)
ck("无效下标被过滤", d["suspicious_total"] == 5, str(d["suspicious_total"]))
ck("无效下标单独入账", d["invalid_suspicious"] == [99, "x"],
   str(d["invalid_suspicious"]))
ck("重复下标只记一次",
   [r["index"] for r in d["rows"]] == [2, 3, 4, 5, 6], str(d["rows"]))
ck("原生判定：第 2 条命中展开", d["rows"][0]["native"] is True)
ck("原生判定：第 3 条不在展开", d["rows"][1]["native"] is False)
ck("逐条来源：阴/阳保留",
   {r["source"] for r in d["rows"]} == {"阴", "阳"})
ck("逐条原因：非原生写明「不在展开快照内」",
   "不在展开快照内" in d["rows"][1]["why"])
ck("逐条第 2 条原因：命中快照提示误报",
   "可能换说法/误报" in d["rows"][0]["why"])
ck("去重：发现重复对", d["dedup"]["dup_count"] >= 1,
   str(d["dedup"]["dup_pairs"]))
ck("去重：重复对含 3/5",
   any(set(p) == {3, 5} for p in d["dedup"]["dup_pairs"]),
   str(d["dedup"]["dup_pairs"]))
ck("去重键：第 3/5 条同键",
   d["rows"][1]["dedup_key"] == d["rows"][3]["dedup_key"])

# ── 3. 置信不被总数稀释：只看点名条目里的原生命中比例 ──
ck("置信：5 条中 1 条原生 → 0.8",
   abs(d["signal"]["confidence"] - 0.8) < 1e-9,
   str(d["signal"]))
ck("置信：>=0.6 判为可信", d["signal"]["confidence_ok"] is True)
expanded2 = [cands[0]["desc"], cands[1]["desc"], cands[3]["desc"]]
d2 = mod._backfill_diagnose(
    cands, expanded2, [1, 2, 3, 4, 5],
    trigger="self_check.suspicious_candidates", reason="x",
    entry="both", round_no=2, threshold=5)
ck("置信：3 原生 / 5 点名 → 0.4",
   abs(d2["signal"]["confidence"] - 0.4) < 1e-9,
   str(d2["signal"]))
ck("置信：0.4 判为被稀释", d2["signal"]["confidence_ok"] is False)

# ── 4. 候选不足 vs 阈值过严 ──
few = [cand(f"候选{i}：互不相同的描述内容{i}") for i in range(6)]
d3 = mod._backfill_diagnose(few, [], [1, 2, 3, 4, 5],
                            trigger="t", reason="r", threshold=5)
ck("评估：6 条候选点名 5 条 → 候选不足为主",
   d3["assessment"]["verdict"] == "候选不足为主",
   d3["assessment"])
many = [cand(f"候选{i}：互不相同的描述内容{i}") for i in range(15)]
d4 = mod._backfill_diagnose(many, [], [1, 2, 3, 4, 5],
                            trigger="t", reason="r", threshold=5)
ck("评估：15 条候选点名 5 条 → 阈值偏严",
   d4["assessment"]["verdict"] == "阈值偏严", d4["assessment"])
d5 = mod._backfill_diagnose(few, [], [1, 2, 3, 4, 5, 6],
                            trigger="t", reason="r", threshold=5)
ck("评估：全部点名 → 候选不足",
   d5["assessment"]["verdict"] == "候选不足", d5["assessment"])

# ── 5. 回填后去重：重复条目被收尾去重吃掉，异质条目保留 ──
before = len(cands)
kept = mod._cross_round_dedup(cands, overlap_thr=0.65, sim_thr=0.70,
                              max_n=60)
ck("回填后去重：重复被去掉", len(kept) < before,
   f"{before} -> {len(kept)}")
ck("回填后去重：异质条目保留", len(kept) == 5, f"{len(kept)}")
after = mod._backfill_diagnose(kept, expanded, list(range(1, len(kept) + 1)),
                               trigger="t", reason="r", threshold=5)
ck("回填后去重：去重后无重复对", after["dedup"]["dup_count"] == 0,
   str(after["dedup"]["dup_pairs"]))

# ── 6. 接线：view.backfill_diag 落账且同触发不重复刷 ──
dg = mod.DGTF.__new__(mod.DGTF)
dg.entry = "both"
dg.verbose = False
dg.config = {"spiral": {}}
dg.vp = lambda *a, **k: None
view = types.SimpleNamespace(candidates=list(cands), quality_flags=[])
view._expanded_descs = list(expanded)
r1 = dg._record_backfill_diag(
    view, [2, 3, 5, 6], trigger="self_check.suspicious_candidates",
    reason="self-check 判定为后补（非展开生长）", round_no=2,
    threshold=5, threshold_kind="count", phase="in_run")
dg._record_backfill_diag(
    view, [2, 3, 5, 6], trigger="self_check.suspicious_candidates",
    reason="self-check 判定为后补（非展开生长）", round_no=2,
    threshold=5, threshold_kind="count", phase="in_run")
ck("接线：返回诊断", bool(r1))
ck("接线：view.backfill_diag 落一条", len(view.backfill_diag) == 1,
   str(len(view.backfill_diag)))
ck("接线：同触发重复调用不刷屏", len(view.backfill_diag) == 1)
ck("接线：诊断含 trigger/reason/source/dedup_key",
   r1.get("trigger") and r1.get("reason")
   and r1["source"].get("layer") and r1["rows"][0].get("dedup_key"))

# ── 7. flag 文案不变，质量评价仍可识别 ──
v = dg._quality_verdict(["candidates_backfilled(sc:5)"])
ck("flag 文案不变：质量评价仍识别",
   v == "候选后补（candidates_backfilled(sc:5)）", v)

print(f"PASS {ok} / FAIL {len(bad)}")
for b in bad:
    print("  ✗", b)
raise SystemExit(0 if not bad else 1)
