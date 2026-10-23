# -*- coding: utf-8 -*-
"""Agent 消费者：消费 agent_tasks.jsonl，产出处理结果与安全源码提案。"""
from __future__ import annotations
import json, time
from pathlib import Path
from dgtf_v2.agent_bridge import read_tasks, DEFAULT_QUEUE

DEFAULT_RESULTS = "dgtf_memory/agent_results.jsonl"
DEFAULT_PROPOSALS = "dgtf_memory/agent_repair_proposals.md"


def _read_results(path):
    p = Path(path)
    out = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def run_once(queue: str = DEFAULT_QUEUE, results: str = DEFAULT_RESULTS,
             limit: int = 50) -> dict:
    tasks = read_tasks(queue, limit)
    done = {str(r.get("task_id")) for r in _read_results(results)}
    out = []
    for t in tasks:
        tid = str(t.get("id") or "")
        if not tid or tid in done:
            continue
        kind = t.get("kind")
        if kind == "eml_candidate":
            action = "进入候选验证：检查同向证据数、边界与回滚"
        elif kind == "audit_gap":
            action = "进入研究复核：补官方/高置信来源，仍不可判定则挂起"
        elif kind == "process_gap":
            action = "进入复现：检查该层轮数、事实命中、依赖是否断"
        elif kind == "api_gap":
            action = "检查 API 配置/触发条件，不直接改源码"
        elif kind == "quality_flag":
            action = "生成诊断报告，交人工/下一跑观察"
        elif kind == "user_task":
            action = "用户任务：待 DSH Agent 开发/映射落地"
        else:
            action = "未识别任务，只留痕"
        out.append({"task_id": tid, "kind": kind, "status": "triaged",
                    "action": action, "title": t.get("title"),
                    "source_run": t.get("source_run"),
                    "ts": time.time()})
    p = Path(results)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"triaged": len(out), "results": out}




def repair_results(path: str = DEFAULT_RESULTS) -> dict:
    """纠正历史 user_task 的“未识别”结果（过程产物自修复，不重复消费）。"""
    p = Path(path)
    if not p.exists():
        return {"fixed": 0}
    rows = []
    fixed = 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if (r.get("kind") == "user_task"
                and "未识别" in str(r.get("action") or "")):
            r["action"] = "用户任务：待 DSH Agent 开发/映射落地"
            r["status"] = "retriaged"
            fixed += 1
        rows.append(r)
    if fixed:
        tmp = p.with_suffix(".tmp")
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                  for r in rows) + "\n", encoding="utf-8")
        tmp.replace(p)
    return {"fixed": fixed}


def write_proposals(queue: str = DEFAULT_QUEUE,
                    path: str = DEFAULT_PROPOSALS) -> dict:
    tasks = read_tasks(queue, 200)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Agent 修复提案（只提案，不自动 apply）", ""]
    for t in tasks:
        lines += ["## %s" % (t.get("title") or t.get("id")),
                  "- kind: `%s`" % t.get("kind"),
                  "- severity: `%s`" % t.get("severity"),
                  "- source_run: `%s`" % t.get("source_run"),
                  "- detail: %s" % str(t.get("detail") or "")[:800],
                  "- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。",
                  ""]
    p.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(p), "n": len(tasks)}


__all__ = ["run_once", "write_proposals", "repair_results"]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="元DGTF Agent 消费者")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--proposals", action="store_true")
    ap.add_argument("--repair-results", action="store_true")
    a = ap.parse_args()
    if a.repair_results:
        print(repair_results())
    if a.proposals:
        print(write_proposals())
    r = run_once()
    print({"triaged": r["triaged"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
