# -*- coding: utf-8 -*-
import json,tempfile
from pathlib import Path
from dgtf_v2.agent_worker import run_once,write_proposals,repair_results
def main():
 d=Path(tempfile.mkdtemp());q=d/"q.jsonl";r=d/"r.jsonl";p=d/"p.md"
 q.write_text(json.dumps({"id":"t1","kind":"audit_gap","title":"x","severity":"high"})+"\n"+json.dumps({"id":"t2","kind":"eml_candidate","title":"y"})+"\n",encoding="utf-8")
 n=run_once(str(q),str(r));print(("PASS" if n["triaged"]==2 else "FAIL"),"triaged",n["triaged"])
 n2=run_once(str(q),str(r));print(("PASS" if n2["triaged"]==0 else "FAIL"),"dedupe")
 print(("PASS" if write_proposals(str(q),str(p))["n"]==2 else "FAIL"),"proposals")
 print(("PASS" if p.exists() and "不自动" in p.read_text(encoding="utf-8") else "FAIL"),"proposal content")
 print(("PASS" if r.exists() else "FAIL"),"results")
 rr=d/"rr.jsonl"; rr.write_text(json.dumps({"task_id":"x","kind":"user_task","status":"triaged","action":"未识别任务，只留痕"})+"\n",encoding="utf-8")
 fx=repair_results(str(rr)); print(("PASS" if fx["fixed"]==1 else "FAIL"),"repair_results")
if __name__=="__main__":main()
