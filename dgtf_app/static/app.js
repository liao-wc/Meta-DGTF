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


/* ── 四张层卡（任务卡样式）：修行 / 研究 / 对撞 / 元 ─────────────
   头 = 层名 + 圈数/状态；中间 = 该层日志；脚 = 该层产物（md/运行日志/json）。
   没跑到的层显示「静默等待」。 */
const LANE_NAMES = ['修行', '研究', '对撞', '元'];
const lanes = { tid: null, text: {}, stats: {}, meta: {} };

function renderTasks() {
  const box = $('#tasks');
  if (!box) return;
  const ids = Object.keys(taskData);
  const empty = $('#tasks-empty');
  if (empty) empty.style.display = ids.length ? 'none' : 'block';
  if (!ids.length) { box.innerHTML = ''; return; }
  const tid = ids.sort((a, b) => taskData[b].created_at - taskData[a].created_at)[0];
  const t = taskData[tid] || {};
  const running = t.status === 'running' || t.status === 'queued';
  const stamp = (t.output_name && t.output_name.endsWith('.md'))
    ? t.output_name.slice(0, -3) : '';

  box.innerHTML = LANE_NAMES.map(n => {
    const body = (lanes.text && lanes.text[n]) || '';
    const has = body.trim().length > 0;
    const st = (lanes.stats && lanes.stats[n]) || {};
    let head;
    if (!has) head = `<span class="badge">静默等待</span>`;
    else if (running) head = `<span class="badge running">第 ${st.round || 1}/${st.rounds_cap || '?'} 圈</span>`;
    else head = `<span class="badge done">共 ${st.round || 1} 圈</span>`;
    const files = (t.layer_artifacts || []).includes(n) && stamp
      ? `<span class="chip packed">产物</span>`
        + `<a href="#" data-archive="${esc(stamp + '.' + n + '.md')}">md</a>`
        + `<a href="#" data-archive="${esc(stamp + '.' + n + '.run.log')}">运行日志</a>`
        + `<a href="#" data-archive="${esc(stamp + '.' + n + '.json')}">json</a>`
      : `<span class="muted">${has ? '该层运行中…' : '有运行到才显示'}</span>`;
    return `<div class="task lane${has ? '' : ' idle'}">
      <div class="task-head">
        <span class="task-q">${n}层</span>
        ${head}
      </div>
      <pre class="log lane-body">${has ? esc(body) : '静默等待…'}</pre>
      <div class="task-foot">${files}</div>
    </div>`;
  }).join('');
  box.querySelectorAll('.lane-body').forEach(el => { el.scrollTop = el.scrollHeight; });
}

/* 运行状态条：起始时间 / 已跑时长 / 实时 token / 累计花费 */
function fmtDur(s) {
  if (s < 60) return s + ' 秒';
  const m = Math.floor(s / 60);
  if (m < 60) return m + ' 分 ' + (s % 60) + ' 秒';
  return Math.floor(m / 60) + ' 时 ' + (m % 60) + ' 分';
}

function renderMeta() {
  const box = $('#run-meta');
  if (!box) return;
  const ids = Object.keys(taskData);
  if (!ids.length) { box.innerHTML = ''; return; }
  const t = taskData[ids.sort((a, b) => taskData[b].created_at - taskData[a].created_at)[0]] || {};
  const m = lanes.meta || {};
  const bits = [];
  const st = m.started_at || t.started_at;
  if (st) {
    const d = new Date(st * 1000);
    bits.push(`<span>起始 <b>${d.toLocaleTimeString('zh-CN', { hour12: false })}</b></span>`);
    const secs = Math.max(0, Math.floor(Date.now() / 1000 - st));
    bits.push(`<span>已跑 <b>${fmtDur(secs)}</b></span>`);
  }
  const tok = m.tok || {};
  bits.push(`<span>消耗 <b>${(tok.tokens || 0).toLocaleString()}</b> tokens`
    + (tok.calls ? ` · ${tok.calls} 次调用` : '') + `</span>`);
  const bal = m.balance || {};
  if (bal.spent != null) bits.push(`<span>花费 <b>¥${Number(bal.spent).toFixed(4)}</b></span>`);
  else if (bal.now != null) bits.push(`<span>余额 <b>¥${Number(bal.now).toFixed(2)}</b></span>`);
  box.innerHTML = bits.join('<span class="sep">·</span>');
}

async function pollLanes() {
  const ids = Object.keys(taskData);
  if (!ids.length) {
    if (lanes.tid !== null) {
      lanes.tid = null; lanes.text = {}; lanes.meta = {};
      renderTasks(); renderMeta();
    }
    return;
  }
  const tid = ids.sort((a, b) => taskData[b].created_at - taskData[a].created_at)[0];
  if (tid !== lanes.tid) { lanes.tid = tid; lanes.text = {}; }
  try {
    const r = await api('/api/tasks/' + tid + '/layers');
    lanes.text = r.layers || {};
    lanes.stats = r.stats || {};
    lanes.meta = { started_at: r.started_at, tok: r.tok, balance: r.balance };
    renderTasks();
    renderMeta();
  } catch (_) { /* 忽略 */ }
}

async function pollTask(id) {
  if (!polls[id]) polls[id] = { offset: 0, final: false };
  const p = polls[id];
  try {
    const st = await api('/api/tasks/' + id);
    taskData[id] = st;
    const running = st.status === 'running' || st.status === 'queued';

    if (running) {
      // 运行中：原始日志（不折叠），过程看得见
      const lg = await api(`/api/tasks/${id}/log?offset=${p.offset}&mode=raw`);
      if (lg && lg.text) {
        p.offset = lg.offset;
        const el = $('#log-' + id);
        if (el) { el.textContent += lg.text; el.scrollTop = el.scrollHeight; }
      }
    } else if (!p.final) {
      // 刚跑完：整段重拉为折叠版（干净）
      p.final = true;
      const lg = await api(`/api/tasks/${id}/log?offset=0&mode=filtered`);
      const el = $('#log-' + id);
      if (el) { el.textContent = (lg && lg.text) || ''; el.scrollTop = el.scrollHeight; }
      p.hidden = (lg && lg.hidden) || 0;
      p.offset = (lg && lg.offset) || 0;
      await refreshOutputsStat();
    }

    renderTasks();
    if (running) p.timer = setTimeout(() => pollTask(id), 1500);
    else clearTimeout(p.timer);
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

// 可判定性：chip 内嵌一个语义色圆点（decidable/partial/undecidable），其余 chip 保持中性
const DECID_DOT = { decidable: 'ok', partial: 'partial', undecidable: 'no' };
function chipDecid(v) {
  if (!v) return '';
  const d = DECID_DOT[String(v).toLowerCase()] || '';
  return `<span class="chip"><i class="d ${d}"></i>${esc(v)}</span>`;
}

function renderLib(items) {
  $('#lib-count').textContent = `共 ${items.length} 份`;
  $('#lib-list').innerHTML = items.map(r => {
    const m = r.meta || {};
    const t = r.time ? String(r.time).replace('T', ' ').slice(0, 16)
                     : new Date(r.mtime * 1000).toLocaleString('zh-CN');
    return `<div class="item" data-name="${esc(r.name)}">
      <div class="t">${esc(r.title)}</div>
      <div class="m">
        <span class="num">${esc(t)}</span>
        ${chipDecid(m['可判定性'])} ${chip(m['取向'])} ${chip(m['并行模式'])}
        <span class="num">${(r.size / 1024).toFixed(0)} KB</span>
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

async function openArchive(name) {
  $('#detail').classList.remove('hidden');
  $('#detail-title').textContent = name;
  $('#detail-body').innerHTML = '<div class="muted">加载中…</div>';
  try {
    const { body } = await api('/api/archive/' + encodeURIComponent(name));
    const MAX = 300000;                 // 超大文件只给头部，避免页面卡死
    const clip = body.length > MAX;
    const head = clip ? body.slice(0, MAX) : body;
    $('#detail-body').innerHTML =
      (clip ? `<p class="muted">（文件较大，仅显示前 ${Math.round(MAX / 1024)} KB；完整内容见 outputs/${esc(name)}）</p>` : '')
      + '<pre>' + esc(head) + '</pre>';
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
      const running = t.status === 'running' || t.status === 'queued';
      polls[t.id] = { offset: 0, final: !running };
      if (running) {
        pollTask(t.id);
      } else {
        // 已完成任务：拉折叠版整段
        api(`/api/tasks/${t.id}/log?offset=0&mode=filtered`).then(lg => {
          if (!lg) return;
          const el = $('#log-' + t.id);
          if (el) el.textContent = lg.text || '';
          polls[t.id].offset = lg.offset || 0;
          polls[t.id].hidden = lg.hidden || 0;
          renderTasks();
        }).catch(() => {});
      }
    });
    if (tasks.length) renderTasks();
  } catch (_) { /* 忽略 */ }
}

function init() {
  buildAdv();
  pollLanes();
  setInterval(pollLanes, 1500);
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
    const arc = e.target.closest('[data-archive]');
    if (arc) { e.preventDefault(); openArchive(arc.dataset.archive); return; }
    const ex = e.target.closest('[data-expand]');
    if (ex) {
      e.preventDefault();
      const id = ex.dataset.expand;
      polls[id] = polls[id] || { offset: 0 };
      polls[id].expanded = !polls[id].expanded;
      renderTasks();
      return;
    }
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

  // 键盘优先：⌘/Ctrl+Enter 提交 · / 聚焦搜索 · Esc 关闭浮层
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); startRun(); return; }
    const tag = (e.target.tagName || '');
    if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) {
      e.preventDefault();
      document.querySelector('.tab[data-view="lib"]').click();
      $('#lib-q').focus();
      return;
    }
    if (e.key === 'Escape') $('#detail').classList.add('hidden');
  });
}

document.addEventListener('DOMContentLoaded', init);
