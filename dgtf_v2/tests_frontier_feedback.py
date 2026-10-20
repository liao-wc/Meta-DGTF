# -*- coding: utf-8 -*-
from dgtf_v2.frontier_feedback import score_candidate,rank_candidates,retrieval_weight,credit_assignment,process_reward
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def c(issue,val,src="engine",key="rounds_delta"):
 return {"kind":"schedule","cond":{"issue":issue},"action":{"key":key},"readings":{"before":{"x":val},"after":{}},"source":src}
def main():
 a=c("all_closure_gap",4);b=c("both_unresolved",1)
 ck("score high",score_candidate(a)>score_candidate(b),(score_candidate(a),score_candidate(b)))
 ck("score range",0<=score_candidate(a)<=1)
 ck("llm lower",score_candidate(c("all_closure_gap",4,"llm"))<score_candidate(a))
 ck("no readings",score_candidate({"cond":{"issue":"x"},"action":{"key":"rounds_delta"}})==0)
 r=rank_candidates([b,a]);ck("rank order",r[0]["cond"]["issue"]=="all_closure_gap")
 ck("dedup issue",len(rank_candidates([a,c("all_closure_gap",3)]))==1)
 ck("retrieval recency",retrieval_weight(0,1,1)>retrieval_weight(30,1,1))
 ck("credit normalize",abs(sum(credit_assignment({"0":.8,"1":.5,"both":.2,"all":.1}).values())-1.0)<1e-3)
 ck("reward",process_reward(True,.8,.1)>process_reward(False,.2,2))
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
