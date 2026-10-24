# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path
from dgtf_v2.agent_worker import run_once, write_proposals, repair_results


def _check(ok, name, *extra):
    print(("PASS" if ok else "FAIL"), name, *extra)
    return ok


def main():
    ok = True
    d = Path(tempfile.mkdtemp())
    q = d / "q.jsonl"
    r = d / "r.jsonl"
    p = d / "p.md"
    q.write_text(json.dumps({"id": "t1", "kind": "audit_gap", "title": "x", "severity": "high"})
                 + "\n" + json.dumps({"id": "t2", "kind": "eml_candidate", "title": "y"})
                 + "\n", encoding="utf-8")
    n = run_once(str(q), str(r))
    ok = _check(n["triaged"] == 2, "triaged", n["triaged"]) and ok
    n2 = run_once(str(q), str(r))
    ok = _check(n2["triaged"] == 0, "dedupe") and ok
    ok = _check(write_proposals(str(q), str(p))["n"] == 2, "proposals") and ok
    ok = _check(p.exists() and "不自动" in p.read_text(encoding="utf-8"), "proposal content") and ok
    ok = _check(r.exists(), "results") and ok
    rr = d / "rr.jsonl"
    rr.write_text(json.dumps({"task_id": "x", "kind": "user_task", "status": "triaged",
                              "action": "未识别任务，只留痕"}) + "\n", encoding="utf-8")
    fx = repair_results(str(rr))
    ok = _check(fx["fixed"] == 1, "repair_results") and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
