# -*- coding: utf-8 -*-
from dgtf_v2.fact_contract import check_layer,repair_layer,run_contract
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def views():
 return {"0":{"manifest":"已核实 2026-10-17 发布"},"1":{"decidable_product":{"answer":"2026-10-17 发布"}},"both":{"manifest":"事实是 2026-10-17"},"all":{"decision":"2026-10-17"}}
def main():
 l={"known":True,"question":"1017 何时发布","answer":"2026-10-17"}
 r=run_contract(views(),l);ck("all ok",r["ok_all"] is True,r)
 v={"0":{"manifest":"没有记录，未确定"}}
 ck("0 missing",check_layer("0",v["0"],l)["ok"] is False)
 repair_layer("0",v["0"],l);ck("0 repaired",check_layer("0",v["0"],l)["ok"] is True)
 ck("no ledger",run_contract({}, {"known":False})["ok_all"] is True)
 v2={"1":{"decidable_product":{}}};repair_layer("1",v2["1"],l);ck("1 repaired",check_layer("1",v2["1"],l)["ok"])
 ck("both missing",check_layer("both",{},l)["ok"] is False)
 ck("all missing",check_layer("all",{},l)["ok"] is False)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
