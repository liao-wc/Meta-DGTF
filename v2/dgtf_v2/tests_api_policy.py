# -*- coding: utf-8 -*-
from dgtf_v2.api_policy import decide
from dgtf_v2.online_adapt import OnlineAdapter,_SPEC
P=[];F=[]
def ck(n,ok):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n)
def main():
 s={"process_ledger":{"soul":{"external_official":0,"external_reference":3}},"fetch_calls":1,"research_audit":{"status":"mixed"},"facets":{"history":2}}
 d=decide(s);ck("fetch on",d.get("web_search.fetch") is True);ck("fetch_per_run",d.get("web_search.fetch_per_run",0)>=3);ck("multi",d.get("api.multi_turn.enabled") is True)
 s2={"process_ledger":{"soul":{"external_official":4,"external_reference":0},"standard_all":False},"research_audit":{"status":"verified"},"facets":{"history":3}}
 ck("tools off",decide(s2).get("api.tools.enabled") is False)
 ck("spec keys",all(k in _SPEC for k in ("web_search.fetch","api.multi_turn.enabled","api.tools.enabled")))
 a=OnlineAdapter(path=None);r=a.propose({"self_feedback":{"signals":{"process_ledger":{"soul":{"external_official":0,"external_reference":2}},"research_audit":{"status":"mixed"},"layers":{},"channels":{},"all":{"clean":True},"facets":{"x":1}}}})
 ck("propose fetch",r["after"].get("web_search.fetch") is True)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
