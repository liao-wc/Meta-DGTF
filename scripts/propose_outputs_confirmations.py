# -*- coding: utf-8 -*-
"""把产物库审计中需要人工确认的问题写成 App 修复提案（幂等）。"""
from __future__ import annotations
import hashlib, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "docs" / "outputs_audit_latest.json"
PROPOSALS = ROOT / "dgtf_memory" / "dsh_proposals"
NL = chr(10)


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(rec):
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    p = PROPOSALS / (str(rec["id"]) + ".json")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _mk(cat, title, detail, plan_lines, severity="med"):
    h = hashlib.sha256(cat.encode("utf-8")).hexdigest()[:10]
    return {"id": "prop-audit-" + h, "ts": time.time(),
            "task": {"kind": "quality_flag", "severity": severity,
                     "title": title, "detail": detail,
                     "source_run": "outputs_library_audit"},
            "plan": NL.join(plan_lines), "plan_gap": False, "session_id": "",
            "conversation_id": "", "status": "pending", "approver": "",
            "events": []}


def main() -> int:
    d = _load(AUDIT, {})
    if not d:
        print("no audit")
        return 1
    c = d.get("counts") or {}
    rs = d.get("run_status") or {}
    made = []
    n1, n2 = int(c.get("needs_evidence") or 0), int(c.get("unverified") or 0)
    if n1 or n2:
        made.append(_mk(
            "quality-needs-evidence",
            "产物库质量问题需人工确认：needs_evidence=%d，unverified=%d" % (n1, n2),
            "全产物库审计发现 %d 条 needs_evidence、%d 条 unverified；涉及证据门/官方源/联网策略，不能靠改题型分类掩盖。" % (n1, n2),
            ["提案（不自动改代码/阈值）：",
             "1. 复核 needs_evidence 与 unverified 的 packed 清单，按领域分组；",
             "2. 对事实题确认 web/官方源策略是否生效，必要时补 1 次 web-on 真跑验证；",
             "3. 若发现分类误判，只修确定性规则并跑 fast_gate/selftest/V2；",
             "4. 若发现证据缺口，保留 needs_evidence，不把缺陷改成 verified；",
             "5. 记录改动前后 quality、tokens、verified 率。",
             "需要人工确认：是否允许追加真跑（预算/题目范围）以及是否接受 web 成本。",
             "验证：fast_gate.py；selftest.py；run_v2_tests.py；precheck_quality.py。"],
            "high"))
    mm = int(d.get("missing_md_n") or c.get("missing_md_n") or 0)
    mp = int(d.get("missing_pack_n") or c.get("missing_pack_n") or 0)
    if mm or mp:
        made.append(_mk(
            "artifact-pairing",
            "产物配对缺口需人工确认：md 无 packed=%d，packed 无 md=%d" % (mp, mm),
            "历史产物存在 md/packed 不配对；可能是分层产物、旧格式或归档不完整。需人工确认哪些可重建、哪些只归档，不能直接删除。",
            ["提案：",
             "1. 以 docs/outputs_audit_latest.json 的配对缺口为清单；",
             "2. 区分 layer/中间产物与主产物；主产物缺 packed 时优先从 run.json/原始日志回放；",
             "3. 不删除任何历史文件；不配对项移动到 archive 需人工确认；",
             "4. 重建后跑 outputs_library_audit.py，确认配对缺口下降且无新增异常。",
             "需要人工确认：是否允许回放/重建，是否允许归档移动。"]))
    dup = int(d.get("duplicate_questions") or c.get("duplicate_questions") or 0)
    if dup:
        made.append(_mk(
            "duplicate-questions",
            "重复题目需人工确认：%d 组" % dup,
            "重复题会重复消耗 API；可能来自缓存未命中、语义缓存阈值或人工重跑。需确认是否收紧缓存/合并题目，避免误复用不同答案。",
            ["提案：",
             "1. 从 outputs_library_audit 的重复题清单抽样；",
             "2. 检查 _find_cached_pack / 语义缓存为何未命中（opts、web、题型差异）；",
             "3. 只优化确定性缓存键/去重，不降低答案质量门；",
             "4. 变更后跑缓存回归 + App selftest，确认无错题复用。",
             "需要人工确认：是否接受更激进的缓存命中策略。"]))
    ne = int(rs.get("error") or 0) + int(rs.get("interrupted") or 0)
    if ne:
        made.append(_mk(
            "run-errors",
            "异常 run 需人工确认：error=%d，interrupted=%d" % (int(rs.get("error") or 0), int(rs.get("interrupted") or 0)),
            "产物库存在 error/interrupted run；可能是服务重启、并发锁、引擎异常或超时。需确认是否重跑及是否需要修复恢复逻辑。",
            ["提案：",
             "1. 列出对应 run.json 与日志尾部；",
             "2. 区分服务重启/并发锁/引擎错误；",
             "3. 修复可确定性恢复的孤儿任务标记；",
             "4. 对需重跑的题走人工确认，不自动消耗预算。",
             "验证：runner 恢复/列表接口 + selftest。",
             "需要人工确认：是否重跑及预算上限。"],
            "high"))
    created = []
    for rec in made:
        p = PROPOSALS / (rec["id"] + ".json")
        if p.exists():
            print("exists", rec["id"])
            continue
        _save(rec)
        created.append(rec["id"])
        print("created", rec["id"], rec["task"]["title"])
    print(json.dumps({"ok": True, "created": created,
                      "skipped": len(made) - len(created)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
