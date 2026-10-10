'use strict';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function api(path, opts) {
  const r = await fetch(path, opts);
  let j = null;
  try { j = await r.json(); } catch (_) { /* 非 JSON */ }
  if (!r.ok) throw new Error((j && j.error) || ('HTTP ' + r.status));
  return j;
}

/* ── 高级参数（留空 = 不传给引擎，走 auto）───────────────────────── */
const ADV = [
  ['route',       'route（层组合）',            '如 1 或 0,1,both,all'],
  ['rounds',      'rounds（圈数上限）',          '如 2 或 2,2,2,3'],
  ['channels',    'channels（三通道）',          '如 all 或 content,context,self'],
  ['parallel',    'parallel（并行模式）',        'auto / serial / B / C …'],
  ['web',         'web（联网）',                'auto / on / off'],
  ['thinking',    'thinking（思考）',            'auto / on / off'],
  ['effort',      'effort（强度）',             'auto / low / medium / high / max'],
  ['orientation', 'orientation（取向）',         'auto / decision / boundary'],
  ['landing',     'landing（落地层模板）',       'auto / decision / boundary'],
  ['decidability','decidability（可判定性）',     'auto / decidable / partial / undecidable'],
  ['appendix',    'appendix（附录）',           'inline / file'],
  ['keep',        'keep（保留名单）',            '逗号分隔'],
];

function buildAdv() {
  $('#adv-grid').innerHTML = ADV.map(([k, label, ph]) =>
    `<label>${label}<input data-adv="${k}" placeholder="${ph}"></label>`).join('');
}

function collectOpts() {
  const opts = {};
  document.querySelectorAll('[data-adv]').forEach(el => {
    const v = el.value.trim();
    if (v) opts[el.dataset.adv] = v;
  });
  if ($('#mock').checked) opts.mock = true;
  return opts;
}

/* ── 任务轮询与渲染 ─────────────────────────────────────────────── */
const polls = {};      // id -> {offset, timer}
let taskData = {};     // id -> task

function badge(st) {
  const txt = { running: '运行中', queued: '排队中', done: '完成', error: '失败' }[st] || st;
  return `<span class="badge ${st}">${txt}</span>`;
}

function fmtTime(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('zh-CN', { hour12: false });
}

function renderTasks() {
  const ids = Object.keys(taskData).sort((a, b) => taskData[b].created_at - taskData[a].created_at);
  $('#tasks-empty').style.display = ids.length ? 'none' : 'block';
  const box = $('#tasks');
  box.innerHTML = ids.map(id => {
    const t = taskData[id];
    const foot = t.status === 'done' && t.output_name
      ? `<span class="chip packed">产物</span> <a href="#" data-open="${esc(t.output_name)}">${esc(t.output_name)}</a>`
      : (t.status === 'error' ? `<span class="err">${esc(t.error || '失败')}</span>`
        : (t.mock ? '<span class="muted">演练中…</span>' : '<span class="muted">引擎运行中（真跑约 30–45 分钟，可离开页面，服务在后台跑）</span>'));
    const cancel = (t.status === 'running' || t.status === 'queued')
      ? `<button data-cancel="${id}">取消</button>` : '';
    return `<div class="task" data-id="${id}">
      <div class="task-head">${badge(t.status)}
        <span class="task-q">${esc(t.question)}</span>
        <span class="task-time">${fmtTime(t.created_at)}</span>
        ${cancel}
      </div>
      <pre class="log" id="log-${id}"></pre>
      <div class="task-foot">${foot}</div>
    </div>`;
  }).join('');
}

async function pollTask(id) {
  if (!polls[id]) polls[id] = { offset: 0 };
  const p = polls[id];
  try {
    const [st, lg] = await Promise.all([
      api('/api/tasks/' + id),
      api(`/api/tasks/${id}/log?offset=${p.offset}`),
    ]);
    taskData[id] = st;
    if (lg && lg.text) {
      p.offset = lg.offset;
      const el = $('#log-' + id);
      if (el) { el.textContent += lg.text; el.scrollTop = el.scrollHeight; }
    }
    renderTasks();
    if (st.status === 'running' || st.status === 'queued') {
      p.timer = setTimeout(() => pollTask(id), 1500);
    } else {
      clearTimeout(p.timer);
      if (!p.finalShown) { p.finalShown = true; await refreshOutputsStat(); }
    }
  } catch (e) {
    if (taskData[id]) { taskData[id].status = 'error'; taskData[id].error = e.message; renderTasks(); }
  }
}

async function startRun() {
  const question = $('#question').value.trim();
  if (!question) { alert('请先输入问题'); return; }
  const opts = collectOpts();
  const real = !opts.mock;
  if (real && !confirm('真实运行会调用 DeepSeek：单次约 30–45 分钟、几十万 token、真花钱（约 ¥4–9）。确认启动？')) return;
  $('#run-btn').disabled = true;
  try {
    const { id } = await api('/api/tasks', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, opts }),
    });
    taskData[id] = { id, question, status: 'queued', created_at: Date.now() / 1000, opts, mock: !!opts.mock };
    renderTasks();
    pollTask(id);
  } catch (e) {
    alert('启动失败：' + e.message);
  } finally {
    $('#run-btn').disabled = false;
  }
}

/* ── 产物库 ─────────────────────────────────────────────────────── */
function chip(v) { return v ? `<span class="chip">${esc(v)}</span>` : ''; }

function renderLib(items) {
  $('#lib-count').textContent = `共 ${items.length} 份`;
  $('#lib-list').innerHTML = items.map(r => {
    const m = r.meta || {};
    return `<div class="item" data-name="${esc(r.name)}">
      <div class="t">${esc(r.title)}</div>
      <div class="m">
        <span>${esc(r.time || new Date(r.mtime * 1000).toLocaleString('zh-CN'))}</span>
        ${chip(m['可判定性'])} ${chip(m['取向'])} ${chip(m['并行模式'])}
        <span>${(r.size / 1024).toFixed(0)} KB</span>
        ${r.has_packed ? '<span class="chip packed">packed</span>' : ''}
      </div>
      ${r.snippet ? `<div class="snip">${esc(r.snippet)}</div>` : ''}
    </div>`;
  }).join('') || '<div class="muted empty">没有匹配的产物。</div>';
}

async function loadLib() {
  const q = $('#lib-q').value.trim();
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if ($('#lib-body').checked) params.set('body', '1');
  if ($('#lib-decid').value) params.set('decidability', $('#lib-decid').value);
  if ($('#lib-orient').value) params.set('orientation', $('#lib-orient').value);
  if ($('#lib-days').value) params.set('days', $('#lib-days').value);
  $('#lib-list').innerHTML = '<div class="muted">检索中…</div>';
  try {
    const { items } = await api('/api/outputs?' + params.toString());
    renderLib(items);
  } catch (e) { $('#lib-list').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }
}

async function loadFacets() {
  try {
    const f = await api('/api/outputs/facets');
    const fill = (sel, list, label) => {
      const el = $(sel);
      el.innerHTML = `<option value="">${label}：全部</option>` +
        (list || []).map(o => `<option value="${esc(o.value)}">${esc(o.value)} (${o.count})</option>`).join('');
    };
    fill('#lib-decid', f.decidability, '可判定性');
    fill('#lib-orient', f.orientation, '取向');
  } catch (_) { /* 忽略 */ }
}

async function openDetail(name) {
  $('#detail').classList.remove('hidden');
  $('#detail-title').textContent = name;
  $('#detail-body').innerHTML = '<div class="muted">加载中…</div>';
  try {
    const { body } = await api('/api/outputs/' + encodeURIComponent(name));
    $('#detail-body').innerHTML = renderMd(body);
  } catch (e) { $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }
}

/* ── 极简 Markdown 渲染（离线，无外部库）────────────────────────── */
function renderMd(src) {
  const lines = esc(src).split('\n');
  const out = [];
  let inCode = false, listOpen = false;
  const closeList = () => { if (listOpen) { out.push('</ul>'); listOpen = false; } };
  for (let raw of lines) {
    if (/^```/.test(raw)) {
      if (inCode) { out.push('</pre>'); inCode = false; }
      else { closeList(); out.push('<pre>'); inCode = true; }
      continue;
    }
    if (inCode) { out.push(raw); continue; }
    const line = raw
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
    let m;
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      closeList(); const lv = m[1].length; out.push(`<h${lv}>${m[2]}</h${lv}>`); continue;
    }
    if (/^(---|\*\*\*)\s*$/.test(line)) { closeList(); out.push('<hr>'); continue; }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (!listOpen) { out.push('<ul>'); listOpen = true; }
      out.push(`<li>${m[1]}</li>`); continue;
    }
    if ((m = line.match(/^>\s?(.*)$/))) { closeList(); out.push(`<blockquote>${m[1]}</blockquote>`); continue; }
    if (!line.trim()) { closeList(); out.push(''); continue; }
    closeList(); out.push(`<p>${line}</p>`);
  }
  closeList();
  if (inCode) out.push('</pre>');
  return out.join('\n');
}

/* ── 配置与初始化 ───────────────────────────────────────────────── */
async function loadConfig() {
  try {
    const c = await api('/api/config');
    const k = c.creds;
    $('#env-info').innerHTML =
      `<b>${esc(c.engine)}</b><br>` +
      `<span class="dot ${k.api_key ? 'ok' : 'no'}"></span>DeepSeek ${k.api_key ? '已配置' : '缺 key'}　` +
      `<span class="dot ${k.tavily ? 'ok' : 'no'}"></span>Tavily ${k.tavily ? '已配置' : '未配置'}` +
      `<br>产物 <b>${c.outputs.count}</b> 份 · ${c.outputs.total_mb} MB`;
    $('#mock').checked = !!c.mock_default;
    $('#cost-warn').textContent = k.api_key
      ? '' : '⚠ .env 里没有 DGTF_API_KEY，真实运行会失败；可先用演练模式验证界面。';
  } catch (e) {
    $('#env-info').textContent = '无法读取配置：' + e.message;
  }
}

async function refreshOutputsStat() { await loadConfig(); }

async function loadExistingTasks() {
  try {
    const { tasks } = await api('/api/tasks');
    tasks.forEach(t => {
      taskData[t.id] = t;
      const p = polls[t.id] = { offset: 0 };
      if (t.status === 'running' || t.status === 'queued') pollTask(t.id);
      else {
        // 已完成任务：补拉一次整段日志
        api(`/api/tasks/${t.id}/log?offset=0`).then(lg => {
          const el = $('#log-' + t.id);
          if (el && lg) el.textContent = lg.text;
        }).catch(() => {});
      }
      void p;
    });
    if (tasks.length) renderTasks();
  } catch (_) { /* 忽略 */ }
}

function init() {
  buildAdv();
  loadConfig();
  loadFacets();
  loadExistingTasks();
  loadLib();

  $('#run-btn').addEventListener('click', startRun);
  $('#lib-search').addEventListener('click', loadLib);
  $('#lib-q').addEventListener('keydown', e => { if (e.key === 'Enter') loadLib(); });
  $('#lib-body').addEventListener('change', loadLib);
  ['#lib-decid', '#lib-orient', '#lib-days'].forEach(s =>
    $(s).addEventListener('change', loadLib));

  document.querySelectorAll('.tab').forEach(tb => tb.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === tb));
    document.querySelectorAll('.view').forEach(v =>
      v.classList.toggle('active', v.id === 'view-' + tb.dataset.view));
    if (tb.dataset.view === 'lib') { loadFacets(); loadLib(); }
  }));

  document.body.addEventListener('click', async (e) => {
    const open = e.target.closest('[data-open]');
    if (open) { e.preventDefault(); openDetail(open.dataset.open); return; }
    const item = e.target.closest('.item[data-name]');
    if (item) { openDetail(item.dataset.name); return; }
    const cancel = e.target.closest('[data-cancel]');
    if (cancel) {
      const id = cancel.dataset.cancel;
      await api(`/api/tasks/${id}/cancel`, { method: 'POST' }).catch(() => {});
      pollTask(id);
      return;
    }
    if (e.target.id === 'detail-close' || e.target.id === 'detail') {
      $('#detail').classList.add('hidden');
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') $('#detail').classList.add('hidden');
  });
}

document.addEventListener('DOMContentLoaded', init);
