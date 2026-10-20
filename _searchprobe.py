import os,json,urllib.request
from pathlib import Path
for ln in Path('.env').read_text(encoding='utf-8').splitlines():
    if ln.startswith('DGTF_API_KEY='):
        os.environ['DGTF_API_KEY']=ln.split('=',1)[1].strip(); break
key=os.environ['DGTF_API_KEY']
q='DeepSeek 官方 最新 模型 技术 2026'
body=json.dumps({'query':q,'count':6,'need_content':False}).encode()
req=urllib.request.Request('https://api.deepseek.com/v1/tools/search',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
with urllib.request.urlopen(req,timeout=60) as r: d=json.loads(r.read().decode())
res=d.get('results') or []
print('N',len(res))
for it in res[:6]:
    print(json.dumps(it,ensure_ascii=False)[:500])
