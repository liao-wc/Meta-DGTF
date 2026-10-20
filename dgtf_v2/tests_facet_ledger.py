# -*- coding: utf-8 -*-
from dgtf_v2.facet_flow import plan_facets,source_confidence,annotate_hits
from dgtf_v2.process_ledger import build_ledger
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 pl=plan_facets("DeepSeek-V4.1-Flash-1017 是什么时候发布的",max_queries=4)
 ck("facets",len(pl)==4 and pl[0]["facet"]=="release_date")
 ck("query token",all("1017" in x["query"] or "site:" in x["query"] for x in pl))
 ck("official conf",source_confidence({"url":"https://api-docs.deepseek.com/news"})["official"] is True)
 ck("reference conf",source_confidence({"url":"https://blog.example.com"})["used_as"]=="reference")
 ck("annotate",annotate_hits([{"url":"https://api-docs.deepseek.com/x"}],"history")[0]["facet"]=="history")
 p={"question":"Q","views":{"0":{"manifest":"fact"},"1":{"decidable_product":{"answer":"fact"}},"both":{"collision":"c"},"all":{"decision":"d","meta_closure":{"clean":True}}},"pools":{},"fact_contract":{"layers":{e:{"ok":True} for e in ("0","1","both","all")}}}
 L=build_ledger(p);ck("ledger layers",len(L["layers"])==4)
 ck("deps",L["layers"]["1"]["deps"]==["0","external_facets"])
 ck("soul",L["soul"]["identity"]=="元DGTF")
 p2={"question":"Q","views":{"0":{"manifest":"f"},"1":{"decidable_product":{"answer":"x"},"decidability_audit":{"status":"empty","bad":0}},"both":{"collision":"c"},"all":{"decision":"d","meta_closure":{"clean":True}}},"pools":{},"fact_contract":{"layers":{e:{"ok":True} for e in ("0","1","both","all")}}}
 L2=build_ledger(p2);ck("empty audit fails 1",L2["layers"]["1"]["standard_ok"] is False)
 ck("empty audit all false",L2["standard_all"] is False)
 p3={"question":"Q","views":{"0":{"manifest":"f"},"1":{"decidable_product":{"answer":"f"}},"both":{"collision":"c"},"all":{"decision":"d","meta_closure":{"clean":True}}},"pools":{"1":{"web_results":[{"id":"W1","official":True,"used_as":"evidence"},{"id":"W2","tier":"reference","used_as":"reference","confidence":0.4}]}},"fact_contract":{"layers":{e:{"ok":True} for e in ("0","1","both","all")}}}
 L3=build_ledger(p3);ck("official count",L3["soul"]["external_official"]==1)
 ck("reference count",L3["soul"]["external_reference"]==1)
 ck("confidence avg",L3["soul"]["external_confidence_avg"]>0)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
