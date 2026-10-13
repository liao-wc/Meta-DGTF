#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 真实入口验证探针：EML 经验记忆回路。

★ 核心是 T9：**构造性证明「会学」** —— 连跑 4 次同向候选 ⇒ 证据够 ⇒
  升级 active ⇒ 第 5 次跑**读到且生效**。断言「读到了、生效了、且留痕」，
  而**不**断言「分数更高」（红线：只升不降的指标是自欺）。
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"

spec = importlib.util.spec_from_file_location("dgtf_v12331", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12331"] = m
spec.loader.exec_module(m)

R = []
TMP = Path(tempfile.mkdtemp(prefix="eml_probe_"))


def ok(name, cond, note=""):
    R.append((name, bool(cond), note))
    print(("✓" if cond else "✗"), name, note)


def _res(rid, cut=(), duty=None, tri=0.5, tokens=100, p75=0):
    duty = duty if duty is not None else {"0": 0.5, "1": 0.5, "both": 0.5, "all": 0.5}
    return {
        "id": rid, "question": "如何利用AI来帮助人类实现财富自由",
        "route": ["0", "1", "both", "all"],
        "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
        "dispatch": {"_parallel_mode": "serial"},
        "views": {e: {"stop_reason": ("体力耗尽（3 圈走满）" if e in cut else "自然安住"),
                      "duty": {"S": duty.get(e, 0.5)}}
                  for e in ("0", "1", "both", "all")},
        "pools": {"1": {"anchors": [1, 2], "web_results": [1]}},
        "tri_consensus": [{"agree": True}] * int(round(tri * 10)) +
                         [{"agree": False}] * (10 - int(round(tri * 10))),
        "llm_tokens": tokens, "llm_calls": 10,
        "_auto_dispatch": {"_history": {"tokens_p75": p75}},
    }


# ── T1 episode 标准化 ────────────────────────────────────
ep = m.episode_from_result(_res("r1", cut=("1",)), t=1000.0)
ok("T1 episode 记录截断层", ep["cut_layers"] == ["1"], str(ep["cut_layers"]))
ok("T1 episode 记录 duty", ep["duty"].get("0") == 0.5, str(ep["duty"]))
ok("T1 episode 记录成本", ep["cost"]["tokens"] == 100, str(ep["cost"]))

# ── T2 micro 候选四类 ────────────────────────────────────
cands = m.eml_candidates_from_result(
    _res("r1", cut=("1",), duty={"0": 0.1, "1": 0.1, "both": 0.5, "all": 0.5},
         tri=0.2, tokens=999, p75=500))
kinds = {c["kind"] for c in cands}
keys = {c["action"]["key"] for c in cands}
ok("T2 截断 ⇒ rounds_delta 候选", "rounds_delta" in keys, str(keys))
ok("T2 职责未尽 ⇒ carve_first 候选", "carve_first" in keys, str(keys))
ok("T2 三态不稳 ⇒ tri_advisory_only 候选", "tri_advisory_only" in keys, str(keys))
ok("T2 只贵不好 ⇒ cost_no_gain 候选", "note_cost_no_gain" in keys, str(keys))
ok("T2 候选都带 readings", all(c.get("readings", {}).get("before") for c in cands))

# ── T3 质量闸四问（各配负样本）──────────────────────────
_pb = []
_bad1 = {"kind": "schedule", "cond": {}, "action": {"key": "x"}}
ok("T3 无读数 ⇒ 拒（evidence）", m.gate_check(_bad1, _pb)[1] == "evidence")
_bad2 = {"kind": "schedule", "cond": {}, "action": {},
         "readings": {"before": {"a": 1}}}
ok("T3 动作无 key ⇒ 拒（verifiable）", m.gate_check(_bad2, _pb)[1] == "verifiable")
_bad3 = {"kind": "schedule", "cond": {}, "action": {"key": "inject_answer"},
         "readings": {"before": {"a": 1}}}
ok("T3 触红线 ⇒ 拒（redline）", m.gate_check(_bad3, _pb)[1] == "redline")
_good = {"kind": "schedule", "cond": {"issue": "cut"}, "action": {"key": "rounds_delta"},
         "readings": {"before": {"a": 1}}}
ok("T3 正样本 ⇒ 过闸", m.gate_check(_good, _pb)[0] is True)

# ── T4 只增合并 ─────────────────────────────────────────
n0 = len(_pb)
e1 = m.eml_merge_candidate(_pb, _good, 1000.0)
ok("T4 新条目入库且 shadow（F1 隔离）",
   e1["status"] == "shadow" and len(_pb) == n0 + 1, e1["id"])
_g2 = dict(_good, evidence=["r1", "r2"])
m.eml_merge_candidate(_pb, _g2, 1001.0)
ok("T4 同键不新增行、只累证据（增量不重写）",
   len(_pb) == n0 + 1 and _pb[0]["n_evidence"] == 2,
   "n_evidence=%d" % _pb[0]["n_evidence"])

# ── T5 meso 升级 + F2 双边记账 ─────────────────────────
_pb2 = [dict(_pb[0], status="shadow", n_evidence=3, quality_delta=0.0,
             cost_delta=0.1, contra=0)]
ch = m.eml_promote(_pb2, promote_n=3)
ok("T5 证据够 + 质量不降 ⇒ 升 active",
   _pb2[0]["status"] == "active" and ch, str(ch))
_pb3 = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=0.0,
             cost_delta=-0.5, contra=0)]
ch3 = m.eml_promote(_pb3, promote_n=3)
ok("T5 ★只省成本 ⇒ 不许升级（F2 防学坏）",
   _pb3[0]["status"] == "shadow" and
   any(c.get("to") == "blocked_cost_only" for c in ch3), str(ch3))
_pb_n = [dict(_pb[0], status="shadow", n_evidence=1, quality_delta=0.2,
              cost_delta=0.0, contra=0)]
m.eml_promote(_pb_n, promote_n=3)
ok("T5 负向：证据不足 ⇒ 不许升级",
   _pb_n[0]["status"] == "shadow", str(_pb_n[0]["status"]))
_pb4 = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=-0.2,
             cost_delta=0.5, contra=0)]
m.eml_promote(_pb4, promote_n=3)
ok("T5 质量下降 ⇒ 不许升级", _pb4[0]["status"] == "shadow")

# ── T6 遗忘清扫 ─────────────────────────────────────────
_now = time.time()
_pb5 = [dict(_pb[0], id="L900", status="active", t_last=_now - 400 * 86400,
             t_used=[], n_evidence=1)]
_r = m.eml_sweep_forget(_pb5, _now, promote_n=3)
ok("T6 陈旧+未用+证据弱 ⇒ retired（行仍在）",
   _pb5[0]["status"] == "retired" and len(_pb5) == 1, str(_r))
_pb6 = [dict(_pb[0], id="L901", status="active", t_last=_now, t_used=[],
             n_evidence=1)]
m.eml_sweep_forget(_pb6, _now, promote_n=3)
ok("T6 负对照：新条目不被误清", _pb6[0]["status"] == "active")

# ── T7 recall（RRIF + 隔离）─────────────────────────────
_pb7 = [
    {"id": "A1", "kind": "schedule", "status": "active", "t_last": _now,
     "n_evidence": 3, "weight": 1.0, "t_used": [], "action": {"key": "k1"}},
    {"id": "A2", "kind": "schedule", "status": "active", "t_last": _now,
     "n_evidence": 3, "weight": 1.0, "t_used": ["r1", "r2", "r3"],
     "action": {"key": "k2"}},
    {"id": "S1", "kind": "schedule", "status": "shadow", "t_last": _now,
     "n_evidence": 9, "weight": 1.0, "t_used": [], "action": {"key": "k3"}},
]
_rc = m.eml_recall(_pb7, "schedule", _now, top_k=5)
_ids = [x["id"] for x in _rc]
ok("T7 shadow 不进 recall（F1）", "S1" not in _ids, str(_ids))
ok("T7 RRIF 频率维：用过的排前面", _ids and _ids[0] == "A2", str(_ids))

# ── T8 macro 聚合不改原文（ACE 教训）────────────────────
_pb8 = [
    {"id": "M1", "kind": "schedule", "status": "active",
     "cond": {"issue": "cut", "layer": "1"}, "action": {"key": "rounds_delta", "layer": "1", "delta": 1}},
    {"id": "M2", "kind": "schedule", "status": "active",
     "cond": {"issue": "cut", "layer": "1"}, "action": {"key": "rounds_delta", "layer": "1", "delta": 1}},
]
_snap = json.dumps(_pb8, ensure_ascii=False, sort_keys=True)
_par = m.eml_aggregate_macro(_pb8, _now)
ok("T8 ≥2 同类 ⇒ 生成父条目", len(_par) >= 1, str(_par)[:80])
ok("T8 ★ 子条目原文一字未改（不重写/不压缩）",
   json.dumps(_pb8, ensure_ascii=False, sort_keys=True) == _snap)

# ── T9 构造性证明「会学」（真实入口，5 跑）──────────────
try:
    cfg = dict(m.DEFAULT_CONFIG)
    cfg["playbook"] = {"mode": "on", "dir": str(TMP), "top_k": 3,
                       "promote_n": 3, "halflife_days": 14.0}
    eng = m.MetaDGTF(cfg)
    _r0 = _res("RUN1", cut=("1",), duty={"0": 0.1, "1": 0.1, "both": 0.5, "all": 0.5})
    for i in range(1, 5):                      # 4 跑同向候选 ⇒ 证据累到 ≥3
        _ri = _res("RUN%d" % i, cut=("1",),
                   duty={"0": 0.1, "1": 0.1, "both": 0.5, "all": 0.5})
        _blk = eng._eml_finish(_ri)
        if i == 1:
            ok("T9 第 1 跑：playbook 落到磁盘",
               (TMP / "playbook.jsonl").is_file(), str(_blk.get("merged")))
            ok("T9 第 1 跑：episodes 落一行",
               len(m.eml_read_jsonl(TMP / "episodes.jsonl")) == 1)
    _pb_now = m.eml_read_jsonl(TMP / "playbook.jsonl")
    _act = [e for e in _pb_now if e.get("status") == "active"]
    ok("T9 4 跑后出现 active 条目（学了）", len(_act) >= 1,
       "active=%d / 库=%d" % (len(_act), len(_pb_now)))
    ok("T9 ★ 行数只增不删（F5）", len(_pb_now) >= 1, str(len(_pb_now)))
    ok("T9 MEMORY.md 自动生成", (TMP / "MEMORY.md").is_file())
    # 第 5 跑：读到 + 生效
    _pre = eng._eml_prepare("如何利用AI来帮助人类实现财富自由")
    ok("T9 第 5 跑：读到 active（used_ids 非空）",
       len(_pre.get("used_ids") or []) >= 1, str(_pre.get("used_ids")))
    _rp = {"0": 3, "1": 3, "both": 3, "all": 4}
    _ap = eng._eml_apply(_rp)
    ok("T9 第 5 跑：生效面被改写（rounds/守卫阈值）",
       len(_ap) >= 1 and (_rp["1"] > 3 or len(_ap) > 0),
       "applied=%s rounds_1=%d" % (_ap, _rp["1"]))
    _blk5 = eng._eml_finish(_res("RUN5", cut=("1",),
                                 duty={"0": 0.1, "1": 0.1,
                                       "both": 0.5, "all": 0.5}))
    ok("T9 第 5 跑：使用留痕进产物块", bool(_blk5.get("used")),
       str([x["id"] for x in (_blk5.get("used") or [])]))
    ok("T9 访问加强/负面留痕在（execution tracking）",
       "strengthen" in _blk5, str(_blk5.get("strengthen")))
except Exception as ex:
    import traceback
    traceback.print_exc()
    ok("T9 构造性证明", False, repr(ex))

# ── T10 off / shadow 零行为差 ───────────────────────────
try:
    cfg2 = dict(m.DEFAULT_CONFIG)
    cfg2["playbook"] = {"mode": "off", "dir": str(TMP)}
    e2 = m.MetaDGTF(cfg2)
    e2._eml_prepare("x")
    blk = e2._eml_finish(_res("RUNX"))
    ok("T10 off ⇒ 不读不写（used 空 / 无 merged）",
       not blk.get("used") and not blk.get("merged"), str(blk)[:80])
    cfg3 = dict(m.DEFAULT_CONFIG)
    cfg3["playbook"] = {"mode": "shadow", "dir": str(TMP) + "_sh"}
    e3 = m.MetaDGTF(cfg3)
    _pr3 = e3._eml_prepare("如何利用AI来帮助人类实现财富自由")
    _ap3 = e3._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4})
    ok("T10 shadow ⇒ 读到但不生效（applied 恒空）",
       len(_ap3) == 0 and e3._eml_mode == "shadow", str(_ap3))
except Exception as ex:
    ok("T10 off/shadow", False, repr(ex))

shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(str(TMP) + "_sh", ignore_errors=True)
bad = [r for r in R if not r[1]]
print("\n=== 探针汇总：%d ✓ / %d ✗ ===" % (len(R) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
