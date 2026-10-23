# -*- coding: utf-8 -*-
from dgtf_v2.evidence import from_search_hits,detect_conflicts
P=[];F=[]
def ck(n,ok):
 (P if ok else F).append(n);print(("PASS " if ok else "FAIL ")+n)
def main():
 h=[{"title":"a","url":"https://api-docs.deepseek.com/zh-cn/updates/","snippet":"2026-10-17 10月17日"},{"title":"b","url":"https://api-docs.deepseek.com/news/news261017/","snippet":"2026-10-17 发布"}]
 ck("date no conflict",detect_conflicts(from_search_hits(h))==[])
 h2=[{"title":"a","url":"https://api-docs.deepseek.com/","snippet":"100 条"},{"title":"b","url":"https://api-docs.deepseek.com/","snippet":"200 条"}]
 ck("numeric conflict",len(detect_conflicts(from_search_hits(h2)))>=1)
 print();print("PASS %d / FAIL %d"%(len(P),len(F)));return 1 if F else 0
if __name__=="__main__":raise SystemExit(main())
