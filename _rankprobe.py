import json,urllib.request,time
B='http://127.0.0.1:8765'
req=urllib.request.Request(B+'/api/agent/knowledge',data=json.dumps({'queries':['DeepSeek Harness agent 最新 2026'],'limit':3}).encode(),headers={'Content-Type':'application/json'},method='POST')
t=time.time()
with urllib.request.urlopen(req,timeout=300) as r: d=json.loads(r.read().decode())
print('ELAPSED',round(time.time()-t,1),'COUNT',d.get('count'),'SKIP',d.get('skipped_duplicates'))
for it in d.get('items') or []:
    print('SRC',it.get('source_type'),'CONF',it.get('confidence'),'SCORE',it.get('score'),'PUB',str(it.get('published'))[:10])
    print(' TITLE',str(it.get('title'))[:70])
    print(' URL',str(it.get('url'))[:100])
    print(' PDF',bool(it.get('pdf_name')),'NOTE',len(str(it.get('zh_note') or '')),'CONTENT',len(str(it.get('content') or '')))
