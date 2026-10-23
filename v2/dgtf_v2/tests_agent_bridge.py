# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from dgtf_v2.agent_bridge import build_tasks,enqueue,read_tasks,refresh_knowledge,read_knowledge
P=[];F=[]
def ck(n,ok):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n)
class C:
 def search(self,q,max_n=3):return ([{"title":"T","url":"https://api-docs.deepseek.com/updates","claim":"2026-10-17"}],"")
 def fetch(self,u):return {"title":"T","content":"2026-10-17"}
def main():
 p={"self_feedback":{"eml_candidates":[{"kind":"guard","action":{"key":"thinking_hint"}}]},"decidability_audit":{"rows":[{"status":"bad","claim":"x"}]},"process_ledger":{"layers":{"0":{"standard_ok":False}}},"quality":{"flags":["probe_link_dangling(2)"]},"api_usage":{"tools_calls":0}}
 t=build_tasks(p,"r1");ck("tasks",len(t)>=4);ck("ids",all(x.get("id") for x in t))
 d=Path(tempfile.mkdtemp())/"q.jsonl";r=enqueue(p,"r1",str(d));ck("enqueue",r["added"]==len(t));r2=enqueue(p,"r1",str(d));ck("dedupe",r2["added"]==0);ck("read",len(read_tasks(str(d)))==len(t))
 k=refresh_knowledge(["q"],C(),"r1",str(d.with_name("k.jsonl")));ck("knowledge",k and k[0]["fetched"] and k[0]["url"].startswith("https://"))
 ck("read knowledge",len(read_knowledge(str(d.with_name("k.jsonl"))))==1)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
