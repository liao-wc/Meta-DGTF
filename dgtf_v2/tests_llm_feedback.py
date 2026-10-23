# -*- coding: utf-8 -*-
import json
from dgtf_v2.llm_feedback import build_digest,parse_candidates,propose
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
class L:
 def __init__(self,raw):self.raw=raw
 def call(self,*a,**k):return self.raw
def main():
 p={"id":"R","decision_trace":{"question_type":"fact"},"views":{"all":{"duty":{"S":.4}}},"quality":{"flags":["x"]},"claim_gaps":{"resolved":1,"unresolved":2},"llm_tokens":100}
 d=build_digest(p);ck("digest",d["run_id"]=="R" and d["claim_gaps"]["unresolved"]==2)
 raw=json.dumps({"candidates":[{"kind":"schedule","cond":{"issue":"x"},"action":{"key":"rounds_delta","layer":"all","delta":1},"readings":{"before":{"x":1}},"why":"w"}]})
 cs=parse_candidates(raw);ck("parse",len(cs)==1 and cs[0]["source"]=="llm")
 bad=json.dumps({"candidates":[{"kind":"schedule","cond":{},"action":{"key":"answer_text"},"readings":{"before":{"x":1}}}]})
 ck("redline reject",parse_candidates(bad)==[])
 bad2=json.dumps({"candidates":[{"kind":"schedule","cond":{},"action":{"key":"rounds_delta"},"readings":{}}]})
 ck("readings reject",parse_candidates(bad2)==[])
 r=propose(L(raw),p);ck("propose",r["n"]==1)
 ck("propose error",propose(None,p)["enabled"] is False)
 ck("bad json",parse_candidates("not json")==[])
 ck("max n",len(parse_candidates(json.dumps({"candidates":[{"action":{"key":"rounds_delta"},"readings":{"before":{"x":1}}},{"action":{"key":"carve_first"},"readings":{"before":{"x":1}}}]}),max_n=1))==1)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
