# -*- coding: utf-8 -*-
import json,tempfile,os
from dgtf_v2.recall_memory import recall_prior,prompt_hint
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 d=tempfile.mkdtemp();p=os.path.join(d,"a.packed.json")
 json.dump({"id":"R1","question":"DeepSeek-V4.1-Flash-1017 是什么时候发布的","decision_trace":{"fact_card":{"status":"answered","answer":"2026-10-17"}}},open(p,"w",encoding="utf-8"))
 h=recall_prior("DeepSeek-V4.1-Flash-1017 是什么时候发布的",d);ck("hit",len(h)==1 and h[0]["answer"]=="2026-10-17")
 ck("run id",h[0]["run_id"]=="R1")
 ck("no hit",recall_prior("完全不同的问题",d)==[])
 ck("hint", "历史回声" in prompt_hint(h))
 ck("no hint", prompt_hint([])=="")
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
