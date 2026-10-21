import json,urllib.request,time
B='http://127.0.0.1:8765/api/agent/auto/job/autofix-1792609999151?since=0'
for i in range(25):
 try:
  with urllib.request.urlopen(B,timeout=10) as r: d=json.load(r)
 except Exception as e:
  print('ERR',e); time.sleep(2); continue
 evs=d.get('events') or []
 print('STATUS',d.get('status'),'NEV',len(evs))
 if evs:
  e=evs[-1].get('event') or {}
  print('LAST',e.get('type'),str(e.get('text') or e.get('tool') or '')[:150])
 if d.get('status') in ('done','failed','interrupted') or d.get('result'):
  print('DONE'); break
 time.sleep(3)
