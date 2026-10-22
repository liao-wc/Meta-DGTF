# -*- coding: utf-8 -*-
"""元DGTF app 依赖链自洽审计（会恢复一次默认 V2 自动策略）。"""
import json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
B = os.environ.get('DGTF_APP', 'https://127.0.0.1:8765')
import ssl as _ssl
_ssl._create_default_https_context = _ssl._create_unverified_context  # 本机自签名测试
PASS, FAIL = [], []
_ACCESS_TOKEN = os.environ.get("DGTF_ACCESS_TOKEN", "").strip()
_AUTH_HEADERS = ({"Cookie": "dgtf_token=" + _ACCESS_TOKEN}
                 if _ACCESS_TOKEN else {})

def ck(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)[:300]) if detail and not ok else ''))

def get(path, timeout=30):
    _rq = urllib.request.Request(B + path, headers=dict(_AUTH_HEADERS))
    with urllib.request.urlopen(_rq, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode('utf-8'))

def req(method, path, data=None, timeout=30):
    body = None if data is None else json.dumps(data).encode('utf-8')
    r = urllib.request.Request(B + path, data=body, method=method,
                               headers={'Content-Type': 'application/json', **_AUTH_HEADERS})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

# 1. 引擎/app 版本
eng = ROOT / '元DGTF-V1.30.3.py'
ck('engine file exists', eng.exists())
ck('engine version 1.30.3', '__version__ = "1.30.3"' in eng.read_text(encoding='utf-8', errors='replace'))
srv = (ROOT / 'dgtf_app' / 'server.py').read_text(encoding='utf-8', errors='replace')
appver = re.search(r'APP_VERSION = "([^"]+)"', srv)
ck('app version present 1.5.15', bool(appver and appver.group(1) == '1.5.15'), appver.group(1) if appver else '')
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
# 4b. 出站网络安全 / DSH 联网授权 / HTTPS 钩子
sys.path.insert(0, str(ROOT))
from dgtf_v2.net_policy import display_url_allowed
try:
    ck('net policy blocks localhost', not display_url_allowed('http://127.0.0.1:8765/'))
    ck('net policy blocks metadata', not display_url_allowed('http://169.254.169.254/latest/meta-data'))
    ck('net policy allows public https', display_url_allowed('https://example.com/'))
    ck('net policy blocks file scheme', not display_url_allowed('file:///C:/Windows/win.ini'))
except Exception as exc:
    ck('net policy checks', False, exc)
st, netpol = get('/api/dsh/network-policy')
ck('dsh network policy api', st == 200 and 'enabled' in netpol and 'clause' in netpol)
_html_now = (ROOT / 'dgtf_app' / 'static' / 'index.html').read_text(encoding='utf-8', errors='replace')
ck('dsh network configurable hooks', 'DGTF_DSH_NETWORK' in srv and '_dsh_net_clause' in srv)
ck('https support hooks', '--https' in srv and 'Strict-Transport-Security' in srv and 'Secure' in srv)
ck('agent action log hooks', 'agentLogAction' in appjs and 'agent-action-log-list' in _html_now)

st, tasks = get('/api/agent/tasks')
rows = tasks.get('tasks') or []
ck('front task mapping keys', st == 200 and all({'id', 'title', 'kind', 'severity'}.issubset(x) for x in rows[:10]))
st, results = get('/api/agent/results')
rows = results.get('results') or []
ck('front result mapping keys', st == 200 and all({'task_id', 'status', 'action'}.issubset(x) for x in rows[:10]))
st, kn = get('/api/agent/knowledge')
rows = kn.get('items') or []
ck('front knowledge mapping keys', st == 200 and all({'query', 'title', 'url', 'fetched'}.issubset(x) for x in rows[:10]))
ck('front chat status mapping keys', all({'id', 'running', 'stale', 'last_status', 'last_task'}.issubset(x) for x in (chats.get('chats') or [])[:10]))
ck('dsh conversation archive retained', st == 200 and 'chats' in chats)
st, props = get('/api/dsh/proposals')
rows = props.get('proposals') or []
ck('front proposal mapping keys', st == 200 and all({'id', 'status', 'task', 'plan'}.issubset(x) for x in rows[:10]))
_html_lib = (ROOT / 'dgtf_app' / 'static' / 'index.html').read_text(encoding='utf-8', errors='replace')
ck('library action log hooks', 'agentLogAction' in appjs and 'agent-asof' in _html_lib)
ck('dsh current-session bridge hooks', '/api/dsh/current' in srv and '_dsh_current_prompt' in srv
   and 'dsh-current-box' not in _html_lib and 'dsh-current-log' not in _html_lib)
ck('agent panel residual controls removed', all(x not in _html_lib for x in
   ('ap-learn', 'ap-spawn', 'ap-selflearn', 'agent-overlay')))
ck('knowledge retrieval restored', 'agent-kn-q' in _html_lib and 'agent-kn-search' in _html_lib
   and '/api/agent/knowledge/agent-search' in appjs)
ck('dsh self-feedback loop prompt', all(x in appjs for x in ('自我反馈', '学习：', '迭代：', 'fast_gate')))
ck('dsh content/status consistency hooks', 'inbox_next_turn' in srv and 'syncDshCurrentView' in appjs
   and 'dshViewPollTimer' in appjs and "status: 'queued'" in appjs)
ck('dsh live events hooks', '/api/dsh/current/events' in srv and '_dsh_current_events' in srv
   and 'dshLiveEvents' in appjs and 'dshLiveSeq' in appjs)
ck('dsh dialog chrome hooks', 'dsh-elapsed' in _html_lib and 'dsh-history-toggle' in _html_lib
   and 'startDshElapsed' in appjs and 'dshToolLabel' in appjs
   and '<details class="rl-fold" data-dsh-key=' in appjs
   and '<summary>思考过程' in appjs)
ck('dsh fold state regression hooks', 'captureDshFoldState' in appjs
   and 'restoreDshFoldState' in appjs and 'data-dsh-key' in appjs
   and 'logFollow = true;' in appjs)
ck('dsh history archive hooks', '_sync_current_dsh_archive' in srv and 'external' in srv
   and 'dsh-current-' in srv)
ck('dsh artifact file hooks', '/api/fs/file' in srv and 'openDshFile' in appjs
   and 'data-dsh-file' in appjs and 'dsh-art-files' in appjs)
ck('dsh history continuation hooks', "external === 'dsh-current'" in appjs
   and 'refreshDshLibraries' in appjs and 'dsh-current' in appjs)
ck('dsh guard hooks', '/api/dsh/guard' in srv and '_dsh_guard_loop' in srv
   and 'dsh-guard' in srv and '/api/dsh/guard' in appjs)
ck('dsh logical conversation hooks', '_new_dsh_current_conversation' in srv and 'start_seq' in srv
   and '/api/dsh/current/conversation' in srv and 'resumeDshCurrentConversation' in appjs)
ck('dsh interject/cancel hooks', '"steer"' in srv and '/api/dsh/current/cancel' in srv
   and 'cancelDshCurrent' in appjs)
ck('agent dsh control buttons', all(x in _html_lib for x in ('dsh-config-btn', 'dsh-config-box',
     'dsh-model', 'dsh-effort', 'dsh-network', 'dsh-perm'))
   and 'dsh-stop-btn' not in _html_lib and 'dsh-newchat-btn' not in _html_lib
   and 'diag-btn' not in _html_lib)
ck('dsh send-to-stop controls', 'setRunBtn(busy && !hasText' in appjs
   and 'send to stop' not in appjs and 'cancelDshCurrent' in appjs)
ck('newchat home + new dsh conversation hooks', 'const wasDsh = dshMode' in appjs
   and 'newDshCurrentConversation(\'新对话\', {silent: true})' in appjs
   and 'toggleDshMode(false)' in appjs)
ck('v2 transparent selector css', '#pareto-prefer:hover' in (ROOT / 'dgtf_app' / 'static' / 'style.css').read_text(encoding='utf-8', errors='replace'))
ck('agent live info screen hooks', 'agent-live' in _html_lib and 'agent-action-log-list' in _html_lib
   and 'agentLogAction' in appjs and 'slice(0, 1)' in appjs)
st, lt = get('/api/tasks')
lt_rows = lt.get('tasks') or []
if lt_rows:
    tid = str(lt_rows[0].get('id'))
    st, layer_payload = get('/api/tasks/' + tid + '/layers')
    ck('engine layer payload contract', st == 200 and isinstance(layer_payload.get('layers'), dict) and bool(layer_payload.get('head')), list((layer_payload.get('layers') or {}).keys())[:10])
    st, out_payload = get('/api/outputs?days=1')
    ck('output list contract', st == 200 and isinstance(out_payload.get('items'), list) and 'count' in out_payload)
else:
    ck('engine layer payload contract', True, 'no tasks')
    ck('output list contract', True, 'no tasks')

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
