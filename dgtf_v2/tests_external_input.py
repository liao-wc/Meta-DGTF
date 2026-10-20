# -*- coding: utf-8 -*-
import json,tempfile,os
from dgtf_v2.external_input import ExternalInput
P=[];F=[]
def ck(n,ok,info=""):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n+(" :: "+str(info) if info and not ok else ""))
def main():
 d=tempfile.mkdtemp();ap=os.path.join(d,"a.json");open(ap,"w",encoding="utf-8").write(json.dumps({"items":[{"id":"A1","claim":"锚点事实"}]}))
 fp=os.path.join(d,"f.txt");open(fp,"w",encoding="utf-8").write("外部文件事实")
 calls=[]
 def search(q): calls.append(q); return [{"title":"web","url":"https://x","claim":"联网事实"}]
 e=ExternalInput(anchor_path=ap,file_paths=[fp],search=search);s=e.load()
 ck("stats",s["anchors"]==1 and s["files"]==1)
 r=e.resolve("q");ck("anchor priority",r["source"]=="anchor" and r["fallback"] is False)
 ck("web not called when anchor",calls==[])
 e2=ExternalInput(anchor_path=os.path.join(d,"none.json"),search=search)
 r2=e2.resolve("q");ck("web fallback",r2["source"]=="web" and r2["fallback"] is True)
 ck("search called",len(calls)==1)
 e3=ExternalInput(anchor_path=os.path.join(d,"none.json"),file_paths=[fp],search=search)
 r3=e3.resolve("q");ck("file before web",r3["source"]=="file")
 ck("separate channels",set(["anchor","file","web"]).issubset(e.stats()["channels"]))
 ck("prompt nonempty",bool(e.as_prompt("q")))
 e4=ExternalInput(search=None);r4=e4.resolve("q");ck("no source ok",r4["source"]=="")
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
