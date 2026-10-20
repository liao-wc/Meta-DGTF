# -*- coding: utf-8 -*-
import base64,tempfile
from pathlib import Path
from dgtf_v2.vision_input import blocks,describe
P=[];F=[]
def ck(n,ok):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n)
class L:
 def call(self,*a,**k): return "可见 2026-10-17"
def main():
 p=Path(tempfile.mkdtemp())/"a.png";p.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lw1wAAAAAElFTkSuQmCC"))
 b=blocks([str(p)]);ck("local block",len(b)==1 and b[0]["image_url"]["url"].startswith("data:image/png"))
 ck("url block",blocks(["https://x/y.png"])[0]["image_url"]["url"]=="https://x/y.png")
 ck("bad path",blocks(["/no/such.png"])==[])
 ck("describe",describe(L(),[str(p)],"图")=="可见 2026-10-17")
 ck("no image",blocks([])==[])
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
