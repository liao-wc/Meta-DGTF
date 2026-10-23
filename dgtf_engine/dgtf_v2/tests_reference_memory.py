# -*- coding: utf-8 -*-
import json, tempfile, os
from dgtf_v2.reference_memory import ReferenceMemory
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 p=os.path.join(tempfile.mkdtemp(),"ref.jsonl");m=ReferenceMemory(p)
 r=m.record(run_id="R1",layer="all",kind="decision",text="完整答案正文 1017 发布",metrics={"x":1})
 ck("record no content flag",r["contains_content"] is False)
 ck("digest exists",len(r["digest"])==24)
 ck("no_copy",r["no_copy"] is True)
 snap=m.read_for_prompt();ck("snapshot no content","完整答案正文" not in json.dumps(snap,ensure_ascii=False))
 ck("snapshot hashed terms",bool(snap[0]["term_hashes"]))
 ck("file persisted",os.path.exists(p))
 m2=ReferenceMemory(p);ck("reload",len(m2.load())==1)
 ck("stats no content",m2.stats()["contains_content"] is False)
 empty=ReferenceMemory(None);ck("disabled path",empty.load()==[])
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
