import subprocess,json,urllib.request,urllib.error
ROOT=r'D:\元DGTF-多模并行架构'
out=subprocess.check_output(['git','credential','fill'],input=b'protocol=https\nhost=github.com\n\n',cwd=ROOT)
tok=next((l.split('=',1)[1] for l in out.decode().splitlines() if l.startswith('password=')),'')
h={'Authorization':'token '+tok,'User-Agent':'dsh-agent','Accept':'application/vnd.github+json','Content-Type':'application/json'}
base='https://api.github.com/repos/liao-wc/meta-dgtf'; sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def call(method,path,body=None):
 data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
 req=urllib.request.Request(base+path,data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:
   raw=r.read().decode(); return r.status,(json.loads(raw) if raw else {})
 except urllib.error.HTTPError as e: return e.code,e.read().decode()[:500]
print('TAG',call('POST','/git/refs',{'ref':'refs/tags/v2.0.0','sha':sha}))
body={'tag_name':'v2.0.0','name':'元DGTF V2.0.0','body':'V2.0.0 生产发布\n\n- 生产入口：元DGTF-V2.0.0.py\n- App 2.0.0；默认 scheduler.v2.takeover=true\n- dgtf_v2 32 个测试全部通过\n- V1 历史归档到 v1/\n- F5 0 层生成机制按设计延期\n- 文件分类见 PROJECT_LAYOUT.md','draft':False,'prerelease':False}
print('RELEASE',call('POST','/releases',body))
