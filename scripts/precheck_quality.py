#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线质量门预检：只读 packed.json，不调 API、不真跑、不改产物。

真跑很贵，而验收要看的失败大多能从 packed 里离线复算出来。本脚本读一份
outputs/*.packed.json，用**引擎里同一份判据**重算五道质量门，逐项打印
PASS/FAIL 与原因，退出码 0/1。用途：验收前预检、4 份正负对照、队列排查。

五道门（对齐 V2.2.1 生产口径）：
  G1 过程账本 process_ledger  dgtf_v2/process_ledger.py:build_ledger
  G2 核心职责审计 core audit  dgtf_v2/core_duty.py:audit_packed
                              （audits/_core_audit.py 与引擎 shadow 同源）
  G3 元层闭环 meta_closure    views.all.meta_closure 的 clean/unsettled/uncovered
                              + quality.flags 里的 all_closure_gaps 留痕
  G4 研究层判定审计           dgtf_v2/decidability_audit.py:audit_view
                              （存证 + 重算双判：越权断言=FAIL）
  G5 质量门 quality           answer_ready / process_ready / answer_quality
                              （按 V2.2.1 decision_trace 门逻辑重算）+ tri 读数

用法（在仓库根执行）：
  python scripts/precheck_quality.py                    # 取 outputs/ 最新 packed
  python scripts/precheck_quality.py --packed <path>    # 指定 packed
  python scripts/precheck_quality.py --json             # 机器可读 JSON
退出码：0 = 全绿 PASS；1 = 任一门 FAIL（含读取/解析/引擎导入失败）。

口径说明：
  · G1/G2/G4 直接 import 引擎模块重算，不读产物里的旧结论；
  · G3 的 meta_closure 由引擎 _settle_meta（相似度匹配）在跑内生成，无法
    脱离引擎实例重算，故做「存证读数 + 内部一致性 + 质量旗」三重判据；
  · G4 存证与重算不一致时会上报（旧产物可能停在引擎修复前口径）；
  · quality.flags 只作警示，不拦截（V2.2.1 红线：线索留痕 ≠ 过程失败）。
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "dgtf_engine"
OUT_DIR = ROOT / "outputs"

# 事实卡的硬缺口：出现即 answer_quality=needs_evidence（V2.2.1 同口径）
HARD_GAPS = frozenset({
    "conflict_unresolved", "insufficient_evidence",
    "question_token_not_in_evidence", "no_query", "search_error",
    "no_record",
})
# 元层闭环被质量旗留痕的两种形状
CLOSURE_FLAG_PREFIXES = ("all_closure_gaps", "all_closure_unavailable")


def _reconfigure_stdio() -> None:
    """Windows 控制台默认 GBK，中文/α 会炸；能改就改，改不了不阻断。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _iso_ts(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")


def _load_engine():
    """导入引擎判据；sys.path 同时补仓库根与 dgtf_engine（两种跑法都兼容）。"""
    added = []
    for d in (str(ROOT), str(ENGINE_DIR)):
        if d not in sys.path:
            sys.path.insert(0, d)
            added.append(d)
    try:
        from dgtf_v2.core_duty import audit_packed
        from dgtf_v2.decidability_audit import audit_view
        from dgtf_v2.process_ledger import build_ledger
    except Exception:
        msg = traceback.format_exc()
        raise RuntimeError("引擎模块导入失败（需要 dgtf_engine/dgtf_v2）：\n" + msg)
    return build_ledger, audit_packed, audit_view


def _resolve_packed(arg: str | None) -> Path | None:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            cwd_p = Path.cwd() / p
            p = cwd_p if cwd_p.exists() else (ROOT / p)
        return p
    cands = sorted(OUT_DIR.glob("*.packed.json"),
                   key=lambda x: x.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _evidence(packed: dict) -> list:
    """与引擎判定审计同一取法：pools[*].web_results 全量。"""
    evs = []
    for pool in (packed.get("pools") or {}).values():
        wr = (pool.get("web_results") if isinstance(pool, dict)
              else getattr(pool, "web_results", None)) or []
        evs.extend([x for x in wr if isinstance(x, dict)])
    return evs


def _hard_gaps(card: dict) -> list:
    out = []
    for g in (card or {}).get("gaps") or []:
        gs = str(g or "")
        if gs.startswith("uncovered:") or gs in HARD_GAPS:
            out.append(gs)
    return out


def _layer_brief(layers: dict) -> str:
    return "｜".join(
        "%s:%s" % (e, "ok" if (layers.get(e) or {}).get("standard_ok") else "FAIL")
        for e in ("0", "1", "both", "all")
        if isinstance(layers.get(e), dict))


# ───────────────────────── 五道质量门 ─────────────────────────

def gate_process_ledger(packed: dict, build_ledger) -> dict:
    led = build_ledger(packed)
    layers = led.get("layers") or {}
    bad = [e for e, r in layers.items() if not (r or {}).get("standard_ok")]
    ok = bool(led.get("standard_all")) and not bad
    reasons = []
    for e in bad:
        r = layers.get(e) or {}
        reasons.append(
            "层 %s 未达标：rounds=%s product_chars=%s citations=%s "
            "decidability=%s bad=%s"
            % (e, r.get("rounds"), r.get("product_chars"), r.get("citations"),
               r.get("decidability"), r.get("decidability_bad")))
    stored_std = (packed.get("process_ledger") or {}).get("standard_all")
    if stored_std is not None and bool(stored_std) != ok:
        reasons.append("存证 process_ledger.standard_all=%s 与重算=%s 不一致"
                       % (stored_std, ok))
    if not ok and not reasons:
        reasons.append("build_ledger.standard_all=False")
    return {
        "id": "G1", "name": "过程账本 process_ledger",
        "status": "PASS" if ok else "FAIL", "ok": ok, "reasons": reasons,
        "data": {
            "standard_all": bool(led.get("standard_all")),
            "stored_standard_all": stored_std,
            "layers": {e: {k: (r or {}).get(k) for k in (
                "rounds", "product_chars", "standard_ok", "citations",
                "decidability", "decidability_bad")}
                for e, r in layers.items()},
        },
    }


def gate_core_audit(packed: dict, audit_packed) -> dict:
    aud = audit_packed(packed)
    gaps = list(aud.get("gaps") or [])
    over = list(aud.get("overreach") or [])
    repairs = list(aud.get("repairs") or [])
    ok = bool(aud.get("ok")) and not gaps and not over and not repairs
    reasons = []
    if gaps:
        reasons.append("gaps：" + "；".join(str(g) for g in gaps))
    if over:
        reasons.append("overreach：" + "；".join(str(g) for g in over))
    if repairs:
        reasons.append("repairs（有修复即不算通过）：" + "；".join(str(r) for r in repairs))
    if not ok and not reasons:
        reasons.append("audit_packed.ok=False")
    # 与跑内 shadow 存证对账
    shadow = packed.get("v2_shadow") or {}
    stored = shadow.get("core") if isinstance(shadow, dict) else None
    if isinstance(stored, dict):
        mism = []
        if bool(stored.get("ok")) != ok:
            mism.append("ok 存证=%s 重算=%s" % (stored.get("ok"), ok))
        for key, cur in (("gaps", gaps), ("overreach", over)):
            old = list(stored.get(key) or [])
            if old != cur:
                mism.append("%s 存证=%s 重算=%s" % (key, old, cur))
        if mism:
            ok = False
            reasons.append("存证 v2_shadow.core 与重算不一致：" + "；".join(mism))
    return {
        "id": "G2", "name": "核心职责审计 core audit",
        "status": "PASS" if ok else "FAIL", "ok": ok, "reasons": reasons,
        "data": {
            "ok": aud.get("ok"), "gaps": gaps, "overreach": over,
            "repairs": repairs,
            "layers": {e: (r or {}).get("ok")
                       for e, r in (aud.get("layers") or {}).items()},
        },
    }


def gate_meta_closure(packed: dict) -> dict:
    route = [str(x) for x in (packed.get("route") or [])]
    if "all" not in route:
        return {"id": "G3", "name": "元层闭环 meta_closure",
                "status": "N/A", "ok": True,
                "reasons": ["route 不含 all，元层未执行（不适用）"],
                "data": {"route": route}}
    va = ((packed.get("views") or {}).get("all") or {})
    mc = va.get("meta_closure") or {}
    clean = mc.get("clean")
    unsettled = int(mc.get("unsettled") or 0)
    uncovered = list(mc.get("uncovered") or [])
    closure_reason = str(va.get("closure_reason") or "")
    flags = [str(f) for f in ((packed.get("quality") or {}).get("flags") or [])]
    closure_flags = [f for f in flags if f.startswith(CLOSURE_FLAG_PREFIXES)]

    consistency = []
    if not isinstance(clean, bool):
        consistency.append("meta_closure.clean 缺失或非布尔")
    else:
        expect = (unsettled == 0 and not uncovered)
        if clean != expect:
            consistency.append(
                "clean=%s 与 unsettled=%d/uncovered=%d 不自洽"
                % (clean, unsettled, len(uncovered)))
    if unsettled != len(uncovered):
        consistency.append("unsettled(%d) != len(uncovered)(%d)"
                           % (unsettled, len(uncovered)))
    if clean is False and not closure_reason and not closure_flags:
        consistency.append("clean=False 但无 closure_reason/all_closure_gaps 留痕")

    ok = (clean is True) and unsettled == 0 and not uncovered \
        and not closure_flags and not consistency
    reasons = []
    if clean is not True:
        reasons.append(
            "meta closure 未闭合：clean=%s unsettled=%d 未交代=%s"
            % (clean, unsettled, "；".join(str(u) for u in uncovered[:5]) or "—"))
    if closure_flags:
        reasons.append("quality.flags 留痕：" + "、".join(closure_flags))
    reasons.extend(consistency)
    return {
        "id": "G3", "name": "元层闭环 meta_closure",
        "status": "PASS" if ok else "FAIL", "ok": ok, "reasons": reasons,
        "data": {
            "clean": clean, "unsettled": unsettled, "uncovered": uncovered,
            "total": mc.get("total"), "closed": mc.get("closed"),
            "closure_reason": closure_reason, "closure_flags": closure_flags,
            "meta_closure": mc,
        },
    }


def gate_research(packed: dict, audit_view) -> dict:
    route = [str(x) for x in (packed.get("route") or [])]
    if "1" not in route:
        return {"id": "G4", "name": "研究层判定审计 decidability",
                "status": "N/A", "ok": True,
                "reasons": ["route 不含 1，研究层未执行（不适用）"],
                "data": {"route": route}}
    views = packed.get("views") or {}
    pools = packed.get("pools") or {}
    v1 = views.get("1") or {}
    stored = (v1.get("decidability_audit")
              or packed.get("decidability_audit") or {})
    stored = stored if isinstance(stored, dict) else {}
    stored_n = int(stored.get("n") or 0)
    stored_bad = int(stored.get("bad") or 0)
    stored_status = str(stored.get("status") or "")
    # 与 process_ledger 同口径：没审计(n=0)不算标准失败；bad>0 即失败
    stored_ok = (not stored) or (
        stored_bad == 0 and (stored_n == 0
                             or stored_status in ("verified", "mixed")))

    p1 = pools.get("1") or {}
    v1_aud = copy.deepcopy(v1)
    sqs = list(v1_aud.get("sub_questions") or p1.get("sub_questions") or [])
    if sqs:
        v1_aud["sub_questions"] = sqs
    card = ((packed.get("decision_trace") or {}).get("fact_card") or {})
    fact_answer = (str(card.get("answer") or "")
                   if card.get("status") == "answered" else "")
    if not fact_answer:
        led = ((packed.get("fact_contract") or {}).get("ledger") or {})
        if led.get("known"):
            fact_answer = str(led.get("answer") or "")
    recomputed = audit_view(v1_aud, _evidence(packed),
                            fact_answer=fact_answer)
    re_n = int(recomputed.get("n") or 0)
    re_bad = int(recomputed.get("bad") or 0)
    re_status = str(recomputed.get("status") or "")
    re_ok = re_bad == 0 and re_status in ("verified", "mixed")

    ok = stored_ok and re_ok
    reasons = []
    if not stored_ok:
        reasons.append("存证判定审计未通过：status=%s n=%d bad=%d"
                       % (stored_status, stored_n, stored_bad))
    if not re_ok:
        reasons.append("重算判定审计未通过：status=%s n=%d bad=%d"
                       % (re_status, re_n, re_bad))
    issue_rows = [r for r in (recomputed.get("rows") or [])
                  if r.get("issue")]
    if issue_rows:
        reasons.append("重算 issue：" + "；".join(
            "%s→%s(%s)" % (r.get("id"), r.get("after"), r.get("issue"))
            for r in issue_rows[:5]))
    warning_rows = [r for r in (recomputed.get("rows") or [])
                    if r.get("warning")]
    if warning_rows:
        reasons.append("重算告警（不记 bad）：" + "、".join(
            str(r.get("warning")) for r in warning_rows[:5]))
    mismatch = (bool(stored) and (
        stored_bad != re_bad or stored_status != re_status))
    if mismatch:
        reasons.append(
            "存证与重算口径不一致：存证 %s(n=%d,bad=%d) / 重算 %s(n=%d,bad=%d)"
            "（旧产物可能停在引擎修复前）"
            % (stored_status, stored_n, stored_bad,
               re_status, re_n, re_bad))
    return {
        "id": "G4", "name": "研究层判定审计 decidability",
        "status": "PASS" if ok else "FAIL", "ok": ok, "reasons": reasons,
        "data": {
            "stored": {"status": stored_status, "n": stored_n,
                       "bad": stored_bad},
            "recomputed": {"status": re_status, "n": re_n, "bad": re_bad,
                           "ok": recomputed.get("ok"),
                           "evidence_n": recomputed.get("evidence_n"),
                           "rows": recomputed.get("rows")},
            "mismatch": mismatch,
        },
    }


def _tri_consistency(tri: dict) -> list:
    bad = []
    st = tri.get("tri_state")
    if st is not None:
        if not (isinstance(st, (list, tuple)) and len(st) == 2
                and all(isinstance(x, (int, float)) for x in st)):
            bad.append("tri_state 形状异常：%r" % (st,))
        else:
            a, b = int(st[0]), int(st[1])
            ratio = tri.get("tri_ratio")
            if b > 0 and isinstance(ratio, (int, float)):
                if abs(float(ratio) - a / b) > 2e-3:
                    bad.append("tri_ratio(%s) != state[0]/state[1](=%.4f)"
                               % (ratio, a / b))
    ratio = tri.get("tri_ratio")
    if ratio is not None and not (isinstance(ratio, (int, float))
                                  and 0.0 <= float(ratio) <= 1.0):
        bad.append("tri_ratio 越界：%r" % (ratio,))
    alpha = tri.get("tri_alpha")
    if alpha is not None:
        if not isinstance(alpha, (int, float)) or not -1.0 <= float(alpha) <= 1.0:
            bad.append("tri_alpha 越界：%r" % (alpha,))
    units = tri.get("tri_alpha_units")
    if units is not None and (not isinstance(units, int) or units < 0):
        bad.append("tri_alpha_units 异常：%r" % (units,))
    if bool(tri.get("tri_reliable")) and bool(tri.get("tri_unreliable")):
        bad.append("tri_reliable 与 tri_unreliable 同时为真")
    return bad


def _tri_readings(packed: dict) -> dict:
    q = packed.get("quality") or {}
    keys = ("tri_state", "tri_ratio", "tri_ratio_kind", "tri_agreement",
            "tri_alpha", "tri_kappa", "tri_alpha_units", "tri_alpha_kind",
            "tri_alpha_verdict", "tri_test_retest_alpha",
            "tri_test_retest_units", "tri_quality", "tri_reliable",
            "tri_unreliable")
    tri = {k: q.get(k) for k in keys if k in q}
    if not tri:
        src = packed.get("tri_alpha")
        if src is not None:
            tri = {"tri_alpha": src}
    return tri


def _fact_quality(packed: dict, process_ok: bool) -> dict:
    """按 V2.2.1 decision_trace 门逻辑重算 answer_ready/process_ready/aq。"""
    dt = packed.get("decision_trace") or {}
    card = dt.get("fact_card") or {}
    hard = _hard_gaps(card)
    raw = dt.get("raw_answer_ready")
    raw_from = "raw_answer_ready"
    if raw is None:
        raw = dt.get("answer_ready")
        raw_from = "answer_ready(旧产物无 raw 字段)"
    raw = bool(raw)
    if card.get("status") == "answered" and not hard:
        aq = ("verified" if card.get("official_evidence_ids")
              else "needs_evidence")
    elif card.get("status") == "answered":
        aq = "needs_evidence"
    else:
        aq = "unverified"
    ready = raw
    reason = ""
    if ready and not process_ok:
        ready = False
        reason = "四层过程标准未全达标"
    elif ready and aq == "needs_evidence":
        ready = False
        reason = "事实证据未覆盖题面/无官方依据"
    # V2.2.1 非事实题出口：过程四层全达标且答案非空 => verified（过程合同验证）
    qtype = str(dt.get("question_type") or "")
    ans_probe = str(((dt.get("reasoning") or {}).get("answer"))
                    or dt.get("answer") or "").strip()
    if qtype and qtype != "fact" and process_ok and ans_probe:
        raw = True
        ready = True
        aq = "verified"
        reason = "非事实题：四层过程合同全达标且答案非空"
    # ★ [V2.2.83] 预算截断口径：引擎在「体力耗尽（预算截断）」时**故意**写
    #   answer_ready=False（质量门不允许截断产物 ready）；G5 重算必须尊重该规则，
    #   否则会把正确的存证判成「不一致」（实测 1+1 题被误判 FAIL）。
    _trunc = ("体力耗尽" in str((packed.get("quality") or {}).get(
                   "answer_ready_reason") or "")
              or "体力耗尽" in str(dt.get("answer_ready_reason") or ""))
    if _trunc and ready:
        ready = False
        reason = "体力耗尽（预算截断），不视为 ready"
    return {"raw": raw, "raw_from": raw_from, "process_ok": bool(process_ok),
            "ready": bool(ready), "answer_ready_reason": reason,
            "answer_quality": aq, "hard_gaps": hard,
            "fact_card_status": card.get("status"),
            "official_evidence_ids": list(card.get("official_evidence_ids") or []),
            "question_type": qtype, "answer_nonempty": bool(ans_probe)}


def gate_quality(packed: dict, process_ok: bool) -> dict:
    rec = _fact_quality(packed, process_ok)
    dt = packed.get("decision_trace") or {}
    tri = _tri_readings(packed)
    tri_bad = _tri_consistency(tri)
    flags = [str(f) for f in ((packed.get("quality") or {}).get("flags") or [])]
    # ★ [V2.2.83] 预算截断（体力耗尽）是**预算边界**，不是质量回归：
    #   引擎故意写 answer_ready=False；此时 G5 判 N/A（不计 FAIL），
    #   否则「最新真跑」一旦撞上预算线就会把发布门误判成质量失败。
    _trunc = ("体力耗尽" in str(((packed.get("quality") or {}).get(
                   "answer_ready_reason") or ""))
              or "体力耗尽" in str(dt.get("answer_ready_reason") or ""))
    if _trunc:
        return {
            "id": "G5", "name": "质量门 quality", "status": "N/A", "ok": True,
            "reasons": ["预算截断（体力耗尽）：answer_ready=False 属引擎预期口径，"
                        "不作为质量失败（预算边界 N/A）"],
            "data": dict(rec, tri=tri, tri_inconsistent=tri_bad,
                         stored={"answer_ready": dt.get("answer_ready"),
                                 "answer_ready_reason":
                                     dt.get("answer_ready_reason")},
                         quality_flags=flags),
        }
    ok = rec["ready"] and rec["answer_quality"] == "verified" \
        and not rec["hard_gaps"] and not tri_bad
    reasons = []
    if rec["hard_gaps"]:
        reasons.append("事实卡硬缺口：" + "；".join(rec["hard_gaps"]))
    if not rec["ready"]:
        reasons.append("answer_ready=False（%s）"
                       % (rec["answer_ready_reason"] or "原始 ready 为 false"))
    if rec["answer_quality"] != "verified":
        reasons.append("answer_quality=%s（要求 verified）"
                       % rec["answer_quality"])
    reasons.extend("tri 读数结构性不一致：" + x for x in tri_bad)
    # 与跑内存证对账（引擎当时写下的结论）
    mism = []
    pairs = (
        ("answer_ready", dt.get("answer_ready"), rec["ready"]),
        ("process_ready", dt.get("process_ready"), rec["process_ok"]),
        ("answer_quality", dt.get("answer_quality"), rec["answer_quality"]),
    )
    for name, old, new in pairs:
        if old is None:
            continue
        if name == "answer_quality":
            if str(old) != str(new):
                mism.append("%s 存证=%s 重算=%s" % (name, old, new))
        elif bool(old) != bool(new):
            mism.append("%s 存证=%s 重算=%s" % (name, old, new))
    q = packed.get("quality") or {}
    for name in ("answer_ready", "process_ready"):
        old = q.get(name)
        if old is not None:
            new = rec["ready"] if name == "answer_ready" else rec["process_ok"]
            if bool(old) != bool(new):
                mism.append("quality.%s 存证=%s 重算=%s" % (name, old, new))
    if mism:
        ok = False
        reasons.append("存证与重算不一致：" + "；".join(mism))
    return {
        "id": "G5", "name": "质量门 quality",
        "status": "PASS" if ok else "FAIL", "ok": ok, "reasons": reasons,
        "data": dict(rec, tri=tri, tri_inconsistent=tri_bad,
                     stored={"raw_answer_ready": dt.get("raw_answer_ready"),
                             "process_ready": dt.get("process_ready"),
                             "answer_ready": dt.get("answer_ready"),
                             "answer_quality": dt.get("answer_quality"),
                             "answer_ready_reason":
                                 dt.get("answer_ready_reason")},
                     quality_flags=flags),
    }


# ───────────────────────── 输出 ─────────────────────────

_SUMMARY_KEYS = {
    "G1": lambda g: "standard_all=%s｜%s"
    % (g["data"]["standard_all"],
       _layer_brief(g["data"].get("layers") or {})),
    "G2": lambda g: "ok=%s gaps=%d overreach=%d repairs=%d"
    % (g["data"]["ok"], len(g["data"]["gaps"]),
       len(g["data"]["overreach"]), len(g["data"]["repairs"])),
    "G3": lambda g: "clean=%s unsettled=%s uncovered=%s flags=%s"
    % (g["data"].get("clean"), g["data"].get("unsettled"),
       len(g["data"].get("uncovered") or []),
       (g["data"].get("closure_flags") or ["—"])),
    "G4": lambda g: "存证 %s(n=%d,bad=%d)｜重算 %s(n=%d,bad=%d)"
    % (g["data"]["stored"]["status"], g["data"]["stored"]["n"],
       g["data"]["stored"]["bad"], g["data"]["recomputed"]["status"],
       g["data"]["recomputed"]["n"], g["data"]["recomputed"]["bad"]),
    "G5": lambda g: "ready=%s process=%s quality=%s"
    % (g["data"]["ready"], g["data"]["process_ok"],
       g["data"]["answer_quality"]),
}


def _print_human(result: dict) -> None:
    print("== 离线质量门预检 ==")
    print("packed : %s" % result["packed"])
    print("mtime  : %s" % result["packed_mtime"])
    print("question: %s" % result["question"])
    print("route  : %s｜type: %s｜tokens: %s"
          % (result["route"], result["question_type"], result["llm_tokens"]))
    print()
    for g in result["gates"]:
        try:
            brief = _SUMMARY_KEYS[g["id"]](g)
        except Exception:
            brief = ""
        print("[%s] %-5s %s  %s"
              % (g["status"], g["id"], g["name"], brief))
        if g["status"] == "FAIL":
            for r in g["reasons"]:
                print("        - " + str(r))
    tri = result["tri"]
    if tri:
        print()
        print("tri 读数：state=%s ratio=%s alpha=%s kappa=%s units=%s "
              "reliable=%s unreliable=%s quality=%s"
              % (tri.get("tri_state"), tri.get("tri_ratio"),
                 tri.get("tri_alpha"), tri.get("tri_kappa"),
                 tri.get("tri_alpha_units"), tri.get("tri_reliable"),
                 tri.get("tri_unreliable"), tri.get("tri_quality")))
        if tri.get("tri_alpha_verdict"):
            print("          verdict: %s" % tri.get("tri_alpha_verdict"))
    if result["warnings"]:
        print()
        print("warnings（仅警示，不影响判定）：")
        for w in result["warnings"]:
            print("  ! " + str(w))
    print()
    print("RESULT: %s（PASS %d / FAIL %d / N/A %d）"
          % (result["verdict"], result["counts"]["PASS"],
             result["counts"]["FAIL"], result["counts"]["N/A"]))
    if result["failed_gates"]:
        print("未通过：%s" % "、".join(result["failed_gates"]))
    for rb in result["failure_reasons"]:
        print("  - " + rb)


def _collect_warnings(packed: dict, gates: list) -> list:
    warns = []
    qflags = [str(f) for f in ((packed.get("quality") or {}).get("flags") or [])]
    if qflags:
        warns.append("quality.flags 共 %d 条（线索留痕，不拦截）：%s"
                     % (len(qflags), "、".join(qflags)))
    for g in gates:
        if g["status"] == "PASS" and g["id"] in ("G3", "G4"):
            for r in g["reasons"]:
                warns.append("%s：%s" % (g["id"], r))
    return warns


def run(packed_path: Path) -> dict:
    build_ledger, audit_packed, audit_view = _load_engine()
    try:
        with packed_path.open("r", encoding="utf-8", errors="replace") as f:
            packed = json.load(f)
    except Exception as exc:
        raise RuntimeError("packed 读取/解析失败：%s: %s"
                           % (type(exc).__name__, exc))
    if not isinstance(packed, dict):
        raise RuntimeError("packed 顶层不是 JSON 对象")
    if not (packed.get("views") or packed.get("pools")
            or packed.get("decision_trace")):
        raise RuntimeError("不是有效 packed：缺 views/pools/decision_trace")

    g1 = gate_process_ledger(packed, build_ledger)
    g2 = gate_core_audit(packed, audit_packed)
    g3 = gate_meta_closure(packed)
    g4 = gate_research(packed, audit_view)
    g5 = gate_quality(packed, g1["data"]["standard_all"])
    gates = [g1, g2, g3, g4, g5]

    counts = {"PASS": 0, "FAIL": 0, "N/A": 0}
    for g in gates:
        counts[g["status"]] += 1
    failed = [g for g in gates if g["status"] == "FAIL"]
    failure_reasons = []
    for g in failed:
        for r in g["reasons"][:2]:
            failure_reasons.append("%s %s：%s" % (g["id"], g["name"], r))
    st = packed_path.stat()
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "packed": str(packed_path.relative_to(ROOT))
        if packed_path.is_relative_to(ROOT) else str(packed_path),
        "packed_mtime": _iso_ts(st.st_mtime),
        "question": str(packed.get("question") or ""),
        "route": [str(x) for x in (packed.get("route") or [])],
        "question_type": str((packed.get("decision_trace") or {}).get(
            "question_type") or ""),
        "llm_tokens": packed.get("llm_tokens"),
        "gates": gates,
        "tri": _tri_readings(packed),
        "warnings": _collect_warnings(packed, gates),
        "verdict": "PASS" if not failed else "FAIL",
        "failed_gates": [g["id"] for g in failed],
        "failure_reasons": failure_reasons,
        "counts": counts,
    }


def main() -> int:
    _reconfigure_stdio()
    ap = argparse.ArgumentParser(
        description="离线质量门预检：只读 packed，重算五道质量门（PASS/FAIL）")
    ap.add_argument("--packed", default=None,
                    help="packed.json 路径；缺省取 outputs/ 最新一份")
    ap.add_argument("--json", action="store_true",
                    help="输出机器可读 JSON（默认人类可读）")
    args = ap.parse_args()

    p = _resolve_packed(args.packed)
    if p is None:
        msg = "未找到 packed：%s/*.packed.json 为空且未指定 --packed" % OUT_DIR
        print("PRECHECK FAIL：" + msg)
        if args.json:
            print(json.dumps({"verdict": "FAIL", "error": msg},
                             ensure_ascii=False, indent=1))
        return 1
    if not p.exists():
        msg = "packed 不存在：%s" % p
        print("PRECHECK FAIL：" + msg)
        if args.json:
            print(json.dumps({"verdict": "FAIL", "error": msg},
                             ensure_ascii=False, indent=1))
        return 1
    try:
        result = run(p)
    except Exception as exc:
        msg = "%s: %s" % (type(exc).__name__, exc)
        print("PRECHECK FAIL：" + msg)
        if args.json:
            print(json.dumps({"verdict": "FAIL", "error": msg,
                              "packed": str(p)},
                             ensure_ascii=False, indent=1))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        _print_human(result)
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
