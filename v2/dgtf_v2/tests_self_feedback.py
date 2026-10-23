# -*- coding: utf-8 -*-
import json
from dgtf_v2.self_feedback import collect_feedback, candidates
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def pack(bthreads=2,third=True,du=None,clean=True,left=0,res=0,prov=2,acts=1,dec=True,flags=None):
 return {"id":"R1","quality":{"flags":flags or []},
  "views":{"0":{"candidates":[{},{}]},"1":{"sub_questions":[{"citations":["W1"]}]},
   "both":{"threads":[{}]*bthreads,"adjudications":[],
   "collision":"c" if third else "","manifest":"m" if third else "",
   "duel_suspensions":du or []},
   "all":{"meta_closure":{"clean":clean,"leftover":left},
    "residual_risks":[{}]*res,"provenance":[{}]*prov,
    "actions":[{}]*acts,"decision":"d" if dec else ""}}}
def test():
 s=collect_feedback(pack()); ck("signals both",s["both"]["threads"]==2)
 ck("signals all",s["all"]["clean"] is True)
 ck("no candidate clean",candidates(pack())==[])
 c=candidates(pack(bthreads=3,third=False,du=[{"status":"unstable"}]))
 ck("both unresolved rounds",any(x["action"].get("key")=="rounds_delta" for x in c),c)
 ck("both thinking",any(x["action"].get("key")=="thinking_hint" for x in c))
 c2=candidates(pack(clean=False,left=2,flags=["all_closure_gaps"]))
 ck("all closure rounds",any(x["action"].get("key")=="rounds_delta" and x["action"].get("layer")=="all" for x in c2),c2)
 c3=candidates(pack(res=1,flags=["core_audit_gaps"]))
 ck("all residual carve",any(x["action"].get("key")=="carve_first" for x in c3),c3)
 c4=candidates(pack(acts=0))
 ck("actions hint",any(x["action"].get("key")=="action_hint" for x in c4),c4)
 ck("json",json.dumps(c4,ensure_ascii=False).startswith("["))
 ck("deterministic",candidates(pack(clean=False))==candidates(pack(clean=False)))
 ck("no content",all(k not in json.dumps(c4,ensure_ascii=False) for k in ("answer_text","verdict_claim")))
 p01=pack();p01["views"]["0"]={"candidates":[],"amps":[],"duty":{"S":.2},"quality_flags":["self_check"]};p01["views"]["1"]={"sub_questions":[],"duty":{"S":.2},"quality_flags":["p"]}
 c01=candidates(p01)
 ck("0 rounds",any(x["action"].get("key")=="rounds_delta" and x["action"].get("layer")=="0" for x in c01))
 ck("0 carve",any(x["action"].get("key")=="carve_first" and "0" in (x["action"].get("layers") or []) for x in c01))
 ck("0 thinking",any(x["action"].get("key")=="thinking_hint" for x in c01))
 ck("1 rounds",any(x["action"].get("key")=="rounds_delta" and x["action"].get("layer")=="1" for x in c01))
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__": raise SystemExit(test())
