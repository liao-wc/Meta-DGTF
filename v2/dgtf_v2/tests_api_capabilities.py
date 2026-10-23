# -*- coding: utf-8 -*-
from dgtf_v2.api_capabilities import summary,MATRIX
def main():
 s=summary();print("PASS" if s["n"]==len(MATRIX) else "FAIL","n")
 print("PASS" if s["counts"].get("used",0)>=6 else "FAIL","used")
 print("PASS" if not any(x["status"] not in ("used","adapted","optional","n/a","auto") for x in MATRIX) else "FAIL","status")
 print("PASS" if any(x["feature"]=="Fetch" and x["status"]=="used" for x in MATRIX) else "FAIL","fetch")
if __name__=="__main__":main()
