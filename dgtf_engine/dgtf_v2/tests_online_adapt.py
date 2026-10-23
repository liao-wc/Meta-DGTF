# -*- coding: utf-8 -*-
import json,tempfile,os
from dgtf_v2.online_adapt import OnlineAdapter
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 d=tempfile.mkdtemp();path=os.path.join(d,"o.json");a=OnlineAdapter(path,enabled=True)
 cfg={"spiral":{"soft_max":4},"web_search":{"enabled":False}}
 ck("load empty",a.load()=={})
 r=a.propose({"id":"R","self_feedback":{"signals":{"all":{"clean":False,"leftover":1},"channels":{"context":{"weak":True},"content":{"weak":True}}}}})
 ck("propose all",r["after"].get("spiral.all_extra_rounds")==1,r)
 ck("propose web",r["after"].get("web_search.enabled") is True)
 ap=a.apply(cfg);ck("apply web",cfg["web_search"]["enabled"] is True)
 ck("apply soft",cfg["spiral"]["soft_max"]==1)
 ck("persist",os.path.exists(path))
 b=OnlineAdapter(path);ck("reload",b.load().get("spiral.all_extra_rounds")==1)
 ck("bounds",OnlineAdapter(None).propose({"self_feedback":{"signals":{"all":{"clean":False,"leftover":9}}}})["after"].get("spiral.all_extra_rounds",0)<=3)
 ck("rollback",b.rollback()["rolled_back"] is True)
 ck("no enabled",OnlineAdapter(None,enabled=False).propose({})["applied"]=={})
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
