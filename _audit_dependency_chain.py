# -*- coding: utf-8 -*-
"""元DGTF app 依赖链自洽审计（会恢复一次默认 V2 自动策略）。"""
import json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
B = os.environ.get('DGTF_APP', 'http://127.0.0.1:8765')
PASS, FAIL = [], []

def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)[:300]) if detail and not ok else ''))

def get(path, timeout=30):
    with urllib.request.urlopen(B + path, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode('utf-8'))

def req(method, path, data=None, timeout=30):
    body = None if data is None else json.dumps(data).encode('utf-8')
    r = urllib.request.Request(B + path, data=body, method=method,
                               headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

# 1. 引擎/app 版本
eng = ROOT / '元DGTF-V1.30.0.py'
ck('engine file exists', eng.exists())
ck('engine version 1.30.0', '__version__ = "1.30.0"' in eng.read_text(encoding='utf-8', errors='replace'))
srv = (ROOT / 'dgtf_app' / 'server.py').read_text(encoding='utf-8', errors='replace')
appver = re.search(r'APP_VERSION = "([^"]+)"', srv)
ck('app version present 1.4.1', bool(appver and appver.group(1) == '1.4.1'), appver.group(1) if appver else '')
readme = (ROOT / 'README.md').read_text(encoding='utf-8', errors='replace')
ck('README app version synced', bool(appver and ('app V' + appver.group(1)) in readme),
   [l for l in readme.splitlines() if 'app V' in l][:2])

# 2. 在线健康/自洽
st, h = get('/api/health')
ck('health ok', st == 200 and h.get('ok') and h.get('app', {}).get('version') == (appver.group(1) if appver else ''), h)
st, c = get('/api/consistency')
ck('consistency ok', st == 200 and c.get('ok'), c.get('warnings'))
ck('context trace check', bool((c.get('checks') or {}).get('context_trace', {}).get('ok')))
ck('rag policy check', bool((c.get('checks') or {}).get('rag_policy', {}).get('ok')))

# 3. RAG
idx = ROOT / 'dgtf_memory' / 'rag_index.json'
ck('rag index exists', idx.exists())
if idx.exists():
    d = json.loads(idx.read_text(encoding='utf-8'))
    ck('rag index nonempty', len(d.get('items') or []) > 0, len(d.get('items') or []))
    ck('rag index dim 512', int(d.get('dim') or 0) == 512, d.get('dim'))
try:
    with urllib.request.urlopen('http://127.0.0.1:8771/health', timeout=20) as r:
        eh = json.loads(r.read().decode())
    ck('embedding service healthy', bool(eh.get('ok')))
except Exception as e:
    ck('embedding service healthy', False, e)
st, ctx = get('/api/project/context?q=' + urllib.parse.quote('元DGTF四层 EML'), 60)
ck('context semantic', st == 200 and ctx.get('retrieval_method') == 'keyword+bm25+bge', ctx.get('retrieval_method'))
ck('context citations', bool(ctx.get('citations')))
ck('context layer contexts', len(ctx.get('layer_contexts') or {}) == 4)
st, hist = get('/api/project/context/history')
ck('context trace history', st == 200 and isinstance(hist.get('history'), list))

# 4. DSH
st, chats = get('/api/dsh/chats')
ck('dsh chats list', st == 200 and isinstance(chats.get('chats'), list), len(chats.get('chats') or []))
st, sess = get('/api/dsh/sessions')
ck('dsh sessions list', st == 200 and isinstance(sess.get('sessions'), list))
ck('dsh conversation cancel scoped', '_DSH_CONV_PROCS' in srv and 'per-conv' not in srv)
appjs = (ROOT / 'dgtf_app' / 'static' / 'app.js').read_text(encoding='utf-8', errors='replace')
ck('dsh danger requires explicit confirmation', '完全访问会让 DSH' in appjs and 'danger-full-access' in srv)
ck('dsh high-risk still manual', 'allow_sensitive' in srv and 'missing_security_invariant' in srv)
ck('dsh write prompt', '你可以读取并修改项目工作区文件' in srv)
ck('dsh privacy prompt', '禁止联网搜索' in srv)
st, pol = get('/api/security/context-policy')
ck('security policy dsh', st == 200 and pol.get('dsh', {}).get('danger_full_access') == 'denied', pol)
ck('embedding local only', '127.0.0.1:8771' in str(pol.get('embedding') or ''))

# 5. 产物命名 / 质量替代
ck('clean output helper', '_clean_prefixed_output' in (ROOT / 'dgtf_app' / 'engine_runner.py').read_text(encoding='utf-8', errors='replace'))
st, q = get('/api/quality/20261021_155104_950be7')
ck('quality alternative api', st == 200 and q.get('ok') and isinstance(q.get('score'), (int, float)), q)
ck('quality alt grade', q.get('grade') in ('A', 'B', 'C', 'D'), q.get('grade'))

# 6. V2 自动策略（审计会恢复默认自动策略；这是默认行为的一部分）
st, auto = req('POST', '/api/schedule/v2/auto-apply', {'prefer': 'balanced'}, timeout=60)
ck('v2 auto apply', st == 200 and auto.get('ok') and bool((auto.get('chosen') or {}).get('name')), auto)
st, pol2 = get('/api/schedule/policy')
ck('v2 auto strategy applied', st == 200 and bool((pol2.get('policy') or {}).get('auto_strategy')),
   (pol2.get('policy') or {}).get('auto_strategy'))
html = (ROOT / 'dgtf_app' / 'static' / 'index.html').read_text(encoding='utf-8', errors='replace')
ck('v2 only gear select', 'id="pareto-prefer"' in html and 'agent-v2-best-apply' not in html)
ck('v2 auto status', 'v2-auto-status' in html)

# 7. LLM / 模型
for rel in ['llm_sft/adapter_qwen05b_v1/adapter_config.json',
            'llm_sft/eval_base_vs_lora.json',
            'llm_sft/adapter_qwen15b_v1/adapter_config.json',
            'llm_sft/adapter_deepseek15b_v1/adapter_config.json',
            'llm_sft/eval_deepseek_base.json']:
    ck('artifact ' + rel, (ROOT / rel).exists())
st, llm = get('/api/schedule/llm/status')
ck('llm adapter ready', st == 200 and llm.get('ok'), llm.get('ok'))
ck('llm eval json', bool((llm.get('eval') or {}).get('lora')), llm.get('eval'))

# 8. 前端
js = (ROOT / 'dgtf_app' / 'static' / 'app.js').read_text(encoding='utf-8', errors='replace')
ck('dsh history ui', 'dsh-history' in html and 'resumeDshChat' in js)
ck('dsh multi-turn one session', 'loadDshConversation' in js and 'conversation_id' in js)
ck('input moved up', 'body.stage-empty main.stage{padding-bottom:0}' in (ROOT / 'dgtf_app' / 'static' / 'style.css').read_text(encoding='utf-8', errors='replace'))

print('\n===== DEPENDENCY AUDIT PASS %d / FAIL %d =====' % (len(PASS), len(FAIL)))
out = ROOT / 'docs' / 'dependency_chain_audit.md'
lines = ['# 元DGTF app 依赖链自洽审计', '', '生成：' + __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
         '', 'PASS %d / FAIL %d' % (len(PASS), len(FAIL)), '', '## FAIL']
lines += ['- ' + x for x in FAIL] or ['- 无']
lines += ['', '## PASS'] + ['- ' + x for x in PASS]
out.write_text('\n'.join(lines), encoding='utf-8')
print('WROTE', out)
sys.exit(0 if not FAIL else 1)
