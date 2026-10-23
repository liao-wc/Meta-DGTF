# -*- coding: utf-8 -*-
from types import SimpleNamespace
from dgtf_v2.multi_turn import run_turns,run_tool_loop
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n)
class L:
 def __init__(self): self.n=0
 def call(self,system,user,**kw):
  self.n+=1
  if kw.get("return_message"):
   if self.n==1:
    fn=SimpleNamespace(name="add",arguments='{"a":1,"b":2}')
    return SimpleNamespace(content="",tool_calls=[SimpleNamespace(id="c1",function=fn)])
   return SimpleNamespace(content="3",tool_calls=[])
  return "turn-"+str(self.n)
def main():
 r=run_turns(L(),"s",["a","b"]);ck("two turns",len(r["turns"])==2 and r["last"]=="turn-2")
 t=run_tool_loop(L(),"s","q",[{"type":"function"}],lambda n,a:str(sum(a.values())))
 ck("tool result",t["text"]=="3",t)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
