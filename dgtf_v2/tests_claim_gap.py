# -*- coding: utf-8 -*-
import json
from dgtf_v2.claim_gap import Claim, extract_claims, run_claim_gap_loop

P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n)
 print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))

def views():
 return {"0":{"candidates":[{"desc":"1017 是否日期"}]},
         "1":{"sub_questions":[{"id":"S1","question":"1017 什么时候发布","status":"open"}],
              "decidable_product":{"answer":"2026-10-17 发布","evidence":[]}},
         "both":{"threads":[{"desc":"发布日期是哪一天"}]},
         "all":{"actions":[{"desc":"核对官方更新日志"}],"residual_risks":["1017 未核实"]}}

def fake(hits):
 calls=[]
 def s(q):
  calls.append(q); return hits
 return s,calls

def main():
 cs=extract_claims(views())
 ck("extract nonempty",len(cs)>=3,len(cs))
 ids={c.claim_id for c in cs}
 ck("ids unique",len(ids)==len(cs))
 hits=[{"title":"官方","url":"https://api-docs.deepseek.com/news/1","snippet":"2026-10-17 发布 1017","date":"2026-10-17"}]
 s,calls=fake(hits)
 r=run_claim_gap_loop(cs,s)
 ck("search called",len(calls)>0,len(calls))
 ck("resolved some",r["resolved"]>0,r)
 ck("official citation",any(c["citations"] for c in r["claims"]))
 ck("trace serializable",json.dumps(r,ensure_ascii=False).startswith("{"))
 r2=run_claim_gap_loop(extract_claims(views()),s)
 ck("deterministic shape",set(r2)==set(r))
 s3,_=fake([{"title":"博客","url":"https://blog.example.com/x","snippet":"1017 发布于 10-17"}])
 r3=run_claim_gap_loop(extract_claims(views()),s3)
 ck("third party unresolved",r3["resolved"]==0 and r3["unresolved"]>0,r3)
 r4=run_claim_gap_loop(extract_claims(views()),None)
 ck("no search skipped",r4["skipped"]>0 and r4["searches"]==0,r4)
 c4=[Claim("C1","1","1017 什么时候发布")]
 r5=run_claim_gap_loop(c4,s,max_per_layer=0)
 ck("layer budget",r5["unresolved"]==1,r5)
 ck("does not write content",all("答案正文" not in str(x) for x in r5["claims"]))
 print()
 print("PASS %d / FAIL %d"%(len(P),len(F)))
 return 1 if F else 0

if __name__=="__main__":
 raise SystemExit(main())
