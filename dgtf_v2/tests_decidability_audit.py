# -*- coding: utf-8 -*-
from dgtf_v2.decidability_audit import audit_view,annotate
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 ev=[{"id":"W1","claim":"2026-10-17 官方发布 1017"}]
 v={"sub_questions":[{"id":1,"question":"1017 发布日期","decidability":"decidable"}]}
 r=audit_view(v,ev);ck("decidable no evidence",r["bad"]==1 and r["status"]=="unverified",r)
 ck("status corrected",v["sub_questions"][0]["decidability"]=="partial")
 v2={"sub_questions":[{"id":1,"question":"1017 发布日期","decidability":"decidable","citations":["W1"]}]}
 ck("decidable evidence",audit_view(v2,ev)["status"]=="verified")
 v3={"decidable_product":{"answer":"无法确认发布日期"}}
 r3=annotate(v3,ev,fact_answer="2026-10-17");ck("repair research",r3["status"]=="verified",r3)
 ck("fact inserted","已核实" in v3["decidable_product"]["answer"])
 ck("evidence ids",bool(v3["decidable_product"].get("external_evidence_ids")))
 ck("no fact no repair",audit_view({"decidable_product":{"answer":"无法确认"}},ev)["bad"]==1)
 ck("empty",audit_view({},ev)["status"] in ("empty","unverified"))
 v5={"decidable_product":{}}
 r5=annotate(v5,ev,fact_answer="2026-10-17");ck("empty repaired",r5["status"]=="verified" and "已核实" in v5["decidable_product"]["answer"])
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
