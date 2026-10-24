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
 vneg={"decidable_product":{"answer":"检索结果不存在可核对连接，两种撞法无法合成一个形状"}}
 rneg=annotate(vneg,ev);ck("evidence-backed negative",rneg["status"]=="verified" and rneg["bad"]==0,rneg)
 ck("empty",audit_view({},ev)["status"] in ("empty","unverified"))
 v5={"decidable_product":{}}
 r5=annotate(v5,ev,fact_answer="2026-10-17");ck("empty repaired",r5["status"]=="verified" and "已核实" in v5["decidable_product"]["answer"])
 # ★ partial 无证据：欠声明不是 overclaim ⇒ 留 warning、不记 bad（真跑实测）
 vp={"sub_questions":[{"id":1,"question":"夜间窗切法是否可分解","decidability":"partial"}]}
 rp=audit_view(vp,ev)
 ck("partial 无证据不记 bad",rp["status"]=="verified" and rp["bad"]==0,rp)
 ck("partial 无证据留 warning",(rp["rows"][0].get("warning")=="partial_without_evidence"),rp["rows"])
 # ★ 纯数字 token 不得冒充证据命中（3.4 K 里的 3.4）
 vnum={"sub_questions":[{"id":1,"question":"夜间温差 3.4 K 的分解是否可行","decidability":"undecidable"}]}
 evnum=[{"id":"W1","claim":"夜间温差 3.4 K，白天 2.1 K，站点 39 个"}]
 rnum=audit_view(vnum,evnum)
 ck("纯数字不冒充证据命中",rnum["status"]=="verified" and rnum["bad"]==0,rnum)
 # ★ 负对照：有字母术语命中 ⇒ 不可判定仍判 overclaim
 vhit={"sub_questions":[{"id":1,"question":"GDP 增速可分解吗","decidability":"undecidable"}]}
 rhit=audit_view(vhit,[{"id":"W1","claim":"GDP 增速与用电量相关"}])
 ck("字母术语命中仍判 overclaim",rhit["bad"]==1 and rhit["status"]=="unverified",rhit)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
