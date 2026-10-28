# -*- coding: utf-8 -*-
"""全产物库分析：扫描 outputs/ 下所有 packed / md / run.json。

用法：
  python scripts/outputs_library_audit.py
  python scripts/outputs_library_audit.py --json-out docs/outputs_audit_latest.json
"""
from __future__ import annotations
import argparse, json, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
_REPORT_DIR = ROOT / "docs" / "reports"


def _norm_q(q: str) -> str:
    return re.sub(r"\s+", "", str(q or "")).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default="")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    packs = sorted(OUT.glob("*.packed.json"))
    mds = sorted(OUT.glob("*.md"))
    runs = sorted(OUT.glob("*.run.json"))
    issues = []
    warnings = []
    stats = Counter()
    qualities = Counter()
    flags = Counter()
    stops = Counter()
    routes = Counter()
    questions = defaultdict(list)
    verified = needs = unverified = ready_false = 0
    missing_quality = 0
    tokens = []
    stale = 0
    now = time.time()
    for fp in packs:
        stats["packed"] += 1
        try:
            d = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            issues.append("packed JSON 损坏：" + fp.name)
            continue
        q = d.get("quality") or {}
        aq = str(q.get("answer_quality") or "")
        qualities[aq or "(missing)"] += 1
        if not q:
            missing_quality += 1
        if aq == "verified":
            verified += 1
        elif aq == "needs_evidence":
            needs += 1
        elif aq:
            unverified += 1
        if q.get("answer_ready") is False:
            ready_false += 1
        for f in (q.get("flags") or []):
            flags[str(f)] += 1
        st = str((q.get("stop") or {}).get("primary") or d.get("stop") or "")
        if st:
            stops[st[:40]] += 1
        r = d.get("route")
        if isinstance(r, list):
            routes[",".join(str(x) for x in r)] += 1
        try:
            tokens.append(float(d.get("llm_tokens") or 0))
        except Exception:
            pass
        qn = _norm_q(d.get("question") or "")
        if qn:
            questions[qn].append(fp.name)
        try:
            if now - fp.stat().st_mtime > 30 * 86400:
                stale += 1
        except OSError:
            pass
    # md 配对
    pack_names = {p.name[:-len(".packed.json")] for p in packs}
    md_names = {p.name[:-3] for p in mds}
    missing_md = sorted(pack_names - md_names)
    missing_pack = sorted(md_names - pack_names)
    if missing_md:
        warnings.append("packed 无 md：%d 条" % len(missing_md))
    if missing_pack:
        warnings.append("md 无 packed：%d 条" % len(missing_pack))
    # run.json 状态
    run_status = Counter()
    for fp in runs:
        try:
            d = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        run_status[str(d.get("status") or "?")] += 1
    bad_runs = [k for k in run_status if k in ("error", "interrupted", "failed")]
    if bad_runs:
        warnings.append("异常 run 状态：" + ", ".join("%s=%d" % (k, run_status[k]) for k in bad_runs))
    # 重复题
    dups = {k: v for k, v in questions.items() if len(v) > 1}
    if dups:
        warnings.append("重复题目：%d 组" % len(dups))
    if needs:
        warnings.append("needs_evidence：%d" % needs)
    if ready_false:
        warnings.append("answer_ready=false：%d" % ready_false)
    if missing_quality:
        issues.append("缺少 quality 段：%d" % missing_quality)
    # 质量分布
    if qualities:
        top_q = qualities.most_common(5)
    else:
        top_q = []
    # 建议
    recs = []
    if needs:
        recs.append("优先复核 needs_evidence：按官方源/联网策略补证，不要只改分类")
    if dups:
        recs.append("重复题可走缓存/语义去重，减少无效真跑")
    if missing_md:
        recs.append("为 packed 生成/恢复对应 md，保证产物可读")
    if bad_runs:
        recs.append("排查异常 run 日志与中断原因，避免重复失败")
    if stale:
        recs.append("30 天以上旧产物可归档，不要删除")
    if not recs:
        recs.append("产物库结构正常，继续积累")
    out = {"ok": not issues, "generated_at": time.time(),
           "counts": {"packed": len(packs), "md": len(mds), "run_json": len(runs),
                      "verified": verified, "needs_evidence": needs,
                      "unverified": unverified, "answer_ready_false": ready_false,
                      "missing_quality": missing_quality, "stale_30d": stale},
           "qualities": dict(qualities), "top_flags": flags.most_common(20),
           "top_stops": stops.most_common(15), "routes": dict(routes),
           "run_status": dict(run_status),
           "duplicate_questions": len(dups),
           "missing_md_n": len(missing_md), "missing_pack_n": len(missing_pack),
           "issues": issues, "warnings": warnings, "recommendations": recs}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json_out:
        op = ROOT / args.json_out
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("JSON_OUT", op)
    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
