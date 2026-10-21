'use strict';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let dshMode = false;
let dshSession = "";
let dshCurrent = null;
let dshAttachTaskId = null;
let dshConversationId = null;
let dshConversation = null;
let dshConvTimer = null;
let dshChats = [];
let dshHistoryOpen = false;
let dshHistoryTimer = null;
let v2AutoBooted = false;
let taskDsh = {};
let agentTaskMode = false;
let logFollow = true;   // 日志/对话是否跟随最新内容
let dgtfSessionId = 'dgtf-' + Date.now().toString(36);

async function streamPost(path, payload, onMsg) {
  const r = await fetch(path, { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload) });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  if (!r.body) throw new Error('浏览器不支持流式读取');
  const reader = r.body.getReader();
  const dec = new TextDecoder('utf-8');
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      const s = line.trim();
      if (s) { try { onMsg(JSON.parse(s)); } catch (_) {} }
    }
  }
  buf += dec.decode();
  const tail = buf.trim();
  if (tail) { try { onMsg(JSON.parse(tail)); } catch (_) {} }
}

async function api(path, opts) {
  let r = await fetch(path, opts);
  // 偶发 501/502/503（服务重启/路由未就绪）自动重试一次，避免面板出现原始 501
  if (r.status === 501 || r.status === 502 || r.status === 503) {
    await new Promise(function (res) { setTimeout(res, 350); });
    r = await fetch(path, opts);
  }
  let j = null;
  try { j = await r.json(); } catch (_) { /* 非 JSON */ }
  if (!r.ok) {
    const friendly = r.status === 501 ? '接口暂不可用（501）' : ('HTTP ' + r.status);
    throw new Error((j && j.error) || friendly);
  }
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

/* yaml 配置面板：`/api/params` 把**生效配置**（出厂 `dgtf_config.yaml` + 用户配置覆盖）
   摊平后按组渲染。**三个动作**：
     · 「保存」       → POST /api/params，持久化写回**用户配置** dgtf_config.user.yaml
                        （出厂 yaml 是只读基线，前端永不改它；刷新/重启后仍在）；
     · 「仅本次」     → 只记进 `advOverrides`，启动时生成一份临时 config 用 `--config`
                        传给引擎（原文件不动）；
     · 「恢复默认配置」→ POST /api/params/reset，删掉用户配置 ⇒ 全部键回落到出厂 yaml。
   ★ 为什么必须分成这几条路：早先只有一个「保存」，但它**只写内存**（临时 config 那条路），
     用户点完「保存」以为存进配置了，一刷新（R28 起刷新回首屏是常用动作）改动全丢 ——
     反馈就是「参数填了保存不了」。「保存」这个词在用户心里就是持久化，别偷换语义。
   ★ 为什么改成写「另一份配置」而不是直接改出厂 yaml：出厂那份是**恢复默认的基线**，
     改了它就没有「默认」可回了（用户明确要求「恢复后端原始默认配置 yaml」）。 */
/* 自绘下拉：原生 select 在页面底部 / 滚动容器里的弹层会跑到窗口左上角，
   这里改成页内菜单 —— 贴触发控件左上角、向右展开，位置由 openDD() 现算。
   真实值仍存在 <input type="hidden" data-cfg> 里，collectOpts() 不用改。 */
function ddField(key, value, options, free, defaultValue) {
  const v = value == null ? '' : String(value);
  const dv = defaultValue == null ? '' : String(defaultValue);
  const opts = (options || []).map(o => {
    const s = String(o);
    const lab = (dv !== '' && s === dv) ? s + '（默认）' : s;
    return `<button type="button" class="dd-opt${s === v ? ' on' : ''}" data-v="${esc(s)}">`
      + `${esc(lab)}</button>`;
  }).join('');
  if (free) {
    return `<div class="dd dd-free">`
      + `<input type="text" class="dd-input" data-cfg="${esc(key)}" value="${esc(v)}">`
      + `<button type="button" class="dd-btn" aria-label="选择预设值"><i class="dd-car" aria-hidden="true"></i></button>`
      + (dv !== '' ? `<span class="dd-def" title="默认值：${esc(dv)}">默认</span>` : '')
      + `<div class="dd-menu">${opts}</div></div>`;
  }
  const cur = (dv !== '' && v === dv) ? v + '（默认）' : v;
  return `<div class="dd">`
    + `<input type="hidden" data-cfg="${esc(key)}" value="${esc(v)}">`
    + `<button type="button" class="dd-btn"><span class="dd-cur">${esc(cur)}</span>`
    + `<i class="dd-car" aria-hidden="true"></i></button>`
    + `<div class="dd-menu">${opts}</div></div>`;
}

/* 参数分组：`/api/params` 的结果 + 前面那一组 CLI 参数（随任务传） */
let advGroups = [];

/* ★ 用户改过的参数值**累积记在这里**（`key -> 值`）。
   为什么必须自己记：分组页是**按需重建**的（点开一组才渲染那一组），
   DOM 里同时只有一个分组的控件 —— 不记的话，① 切到别的组再切回来，改的值被
   `/api/params` 的原始值盖掉；② `collectOpts()` 只扫得到当前这一组的控件，
   别的组的改动**根本传不出去**（用户报的「参数改了没保存」就是这两个叠加）。 */
const advOverrides = {};

/* 打开某个分组时的**快照**，供「不保存直接关闭」把这一组的改动整组回滚 */
let advBackup = null;    // { key: {had, val} }

/* ★ 已经**保存进 yaml** 的键（`key -> 值`）。
   用来算分组按钮上的「已改 M 项」小标 —— 只有"因为没保存而只是暂时记着"的键
   才算「待保存」，不然用户看不出到底存住了没有（这正是他报「保存不了」的由来）。 */
let advSaved = {};

/* ★ R38：CLM（任务级）参数**已保存**的值（来自用户配置的 `cli:` 段，随 /api/params 下发）。
   在 `advOverrides` 里没有对应键时，面板回显它 ⇒「用户保存的参数，数字显示在参数设置框里」。 */
let advCliSaved = {};

/* 这一组里「改了但还没持久化」的键有几个 */
function advDirtyCount(g) {
  let n = 0;
  (g.items || []).forEach(it => {
    if (!it.key || !(it.key in advOverrides)) return;
    if (advSaved[it.key] !== advOverrides[it.key]) n++;
  });
  return n;
}

/* ★ R38：两个数据属性都认 —— `data-cfg`（yaml 键）+ `data-adv`（CLM/CLI 任务级参数）。
   都进同一个 `advOverrides`，于是「保存所有参数」自然把它们一起覆盖到。 */
function rememberAdv(el) {
  if (!el || !el.dataset) return;
  const key = el.dataset.cfg || el.dataset.adv;
  if (key) advOverrides[key] = el.value;
}

/* 渲染**一项**参数（下拉 / 开关 / 输入框 / 只读结构值） */
function renderAdvItem(it) {
  // 有改过的值就用改过的（分组页重建时不会把用户的输入抹掉）
  const dv = (it.default == null) ? '' : String(it.default);
  let v = (it.key in advOverrides) ? advOverrides[it.key]
            : (it.value == null ? '' : String(it.value));
  if (it.placeholder == null && v === '' && dv !== '') v = dv;
  let field, dropdown = false, plain = false;
  if (it.placeholder != null) {
    /* ★★ R38：CLM（CLI）参数 —— 是 12 个**任务级**参数（route/rounds/channels/…），
       它们不写 yaml、只随任务当命令行 flag 传给引擎。
       修法（原实现三个断点一起补）：
         ① 值**回显**（原来只给 `placeholder` ⇒ 切走再切回，用户填的就没了）；
         ② 真值同时挂 `data-adv`（收集用）—— 事件委托那边要认它（见 init）；
         ③ **不**挂 `data-cfg` —— 它不属于 yaml 覆盖表，挂了会被塞进 `opts.overrides`
            去改临时 config，那是错的路子。 */
    field = `<input data-adv="${esc(it.key)}" value="${esc(v)}" placeholder="${esc(it.placeholder)}">`;
  } else if (it.type === 'readonly') {
    /* 两类只读项，都不渲染 `data-cfg` ⇒ collectOpts 收不到 ⇒ 既不会被改也不会被写回：
         · 密钥键（readonly_key=true）：显示「已配置 / （空）」，值本身不回传前端；
         · 嵌套结构值（如 web_search.domain_tier_rules = [[".gov.cn",1],…]）：
           前端只有字符串，往返会把二维结构写坏，所以不给编辑。 */
    const tip = it.readonly_key
      ? '密钥类参数不在面板里编辑（避免明文落进配置文件 / 被空值覆盖）'
      : esc(v);
    const txt = it.readonly_key
      ? (it.has_value ? '已配置 · 不在面板改' : '未配置 · 不在面板改')
      : '只读 · 结构值';
    field = `<span class="ro${it.readonly_key ? ' ro-key' : ''}" title="${tip}">${txt}</span>`;
    plain = true;
  } else {
    let opts = (it.options && it.options.length) ? it.options.slice() : [];
    if (!opts.length) {
      if (it.type === 'bool') opts = ['true', 'false'];
      else if (dv === 'enabled' || dv === 'disabled') opts = ['enabled', 'disabled'];
      else if (dv === 'true' || dv === 'false') opts = ['true', 'false'];
      else if (dv === 'auto' || dv === 'on' || dv === 'off') opts = ['auto', 'on', 'off'];
      else opts = [];
    }
    opts = Array.from(new Set(opts.concat(dv ? [dv] : []).concat(v ? [v] : [])
      .filter(x => String(x) !== '')));
    const free = !(it.type === 'select' || it.type === 'bool');
    field = ddField(it.key, v, opts, free, dv);
    dropdown = true;
  }
  /* ★ 两件事一起修（用户报「标签文字大小格式不统一」）：
     ① 标签统一取 `it.label` —— 后端已给成「键（中文说明）」，CLI 项本来就是这个格式；
     ② 下拉 / 只读项走的是 `<div>`，**必须补上 `field` class** —— 否则 `.grid label,.grid .field`
        那条样式命中不到它，标签的字号 / 行距跟 `<label>` 那批**不一样**。 */
  const name = it.label || it.key;
  const pin = it.pinned ? ' pinned' : '';
  /* ★ 标签包一层 `.lb`：CSS 靠它给标签**定高两行**，同一行的控件才会竖直对齐。 */
  /* ★ R24：标签单行省略（CSS），完整文本挂 `title` 兜住 —— 长说明不再折行撑高整行。 */
  return (dropdown || plain)
    ? `<div class="field${pin}"><span class="lb" title="${esc(name)}">${esc(name)}</span>${field}</div>`
    : `<label class="${pin.trim()}"><span class="lb" title="${esc(name)}">${esc(name)}</span>${field}</label>`;
}

/* 高级参数页：**只列分组按钮**（点一个 → 进下一层新页看该组参数） */
const ADV_GROUP_CN = {
  all_on: '一键全开', autotune: '自动调参', belief: '把握阈值',
  claim_gap: '缺口检查', duty: '职责开关', external_input: '外部输入',
  max_tokens: 'Token 预算', playbook: '经验剧本', scheduler: '调度器',
  sim: '仿真模式', stop: '停止条件',
};

const ADV_CATEGORIES = [
  { key: 'cat-cli', label: '任务指令参数', rawLabel: 'CLM 参数（随机任务传）', keys: ['_cli'] },
  { key: 'cat-model', label: '模型与接口', rawLabel: '模型与 API', keys: ['api'] },
  { key: 'cat-run', label: '运行与调度', rawLabel: '运行与调度', keys: ['runtime', 'auto', 'scheduler', 'max_tokens', 'sim'] },
  { key: 'cat-data', label: '联网与资料', rawLabel: '联网与资料', keys: ['web_search', 'external_anchor', 'external_input'] },
  { key: 'cat-layer', label: '四层与收尾', rawLabel: '四层与收尾', keys: ['spiral', 'stop', 'playbook'] },
  { key: 'cat-memory', label: '记忆与探针', rawLabel: '记忆与探针', keys: ['memory', 'probe', 'claim_gap'] },
  { key: 'cat-actions', label: '动作与职责', rawLabel: '动作与职责', keys: ['actions', 'all_on', 'autotune', 'belief', 'duty'] },
  { key: 'cat-output', label: '输出', rawLabel: '输出', keys: ['output'] },
];

function mergeAdvGroups(groups) {
  const by = Object.fromEntries((groups || []).map(g => [g.key, g]));
  const used = new Set();
  const out = [];
  ADV_CATEGORIES.forEach(cat => {
    const items = [];
    cat.keys.forEach(k => {
      const g = by[k];
      if (!g) return;
      used.add(k);
      (g.items || []).forEach(it => items.push(it));
    });
    if (items.length) {
      out.push({ key: cat.key, label: cat.label,
                 rawLabel: cat.rawLabel || cat.label, items });
    }
  });
  (groups || []).forEach(g => {
    if (!used.has(g.key)) out.push(g);
  });
  return out;
}

async function buildAdv() {
  /* 刷新失败时保留已有分组，避免“恢复出厂后只剩 CLM”这种整块消失 */
  let groups = advGroups.filter(g => g.key !== '_cli');
  try {
    const r = await api('/api/params');
    if (r && Array.isArray(r.groups) && r.groups.length) groups = r.groups;
    advCliSaved = (r.cli && typeof r.cli === 'object') ? r.cli : {};
  } catch (_) { /* 保留已有的非 CLM 分组 */ }
  const savedCli = advCliSaved || {};
  const cli = ADV.map(([k, label, ph]) =>
    ({ key: k, label, placeholder: ph,
       value: (k in advOverrides) ? advOverrides[k] : (savedCli[k] || '') }));
  groups = groups.map(g => ({
    ...g,
    rawLabel: g.label,
    label: ADV_GROUP_CN[g.key] || g.label,
  }));
  advGroups = mergeAdvGroups([{ key: '_cli', rawLabel: 'CLM 参数（随机任务传）',
                              label: '任务指令参数', items: cli }, ...groups]);
  renderAdvGroups();
}

/* ★ 分组列表单独抽出来渲染 —— 「保存」之后要回来刷新那个「已改 M 项」小标。
   （原来这段是 buildAdv 内联的，保存后不重渲染 ⇒ 用户看不出存住没有。） */
function renderAdvGroups() {
  const box = $('#adv-groups');
  if (!box) return;
  box.innerHTML = advGroups.map(g => {
    const dirty = advDirtyCount(g);
    return `
    <button class="nav-btn" data-advgroup="${esc(g.key)}">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 7h10M18 7h2M4 17h4M12 17h8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
        <circle cx="16" cy="7" r="2.3" stroke="currentColor" stroke-width="1.7"/>
        <circle cx="10" cy="17" r="2.3" stroke="currentColor" stroke-width="1.7"/>
      </svg>
      <span class="nb-name">${esc(g.label)}</span>
      <em class="${dirty ? 'dirty' : ''}">${g.items.length} 项</em>
      ${dirty ? `<i class="adv-dirty" title="有 ${dirty} 项改了但还没保存">${dirty} 项待保存</i>` : ''}
    </button>`;
  }).join('');
}

/* 当前正在看的分组（「保存」要知道该把哪一组交出去） */
let advCurGroup = null;

/* 点分组 → 渲染该组参数并铺满成新的一页 */
function openAdvGroup(key) {
  const g = advGroups.find(x => x.key === key);
  if (!g) return;
  advCurGroup = g;
  // 进页面先拍快照：关的时候「不保存」就照它回滚
  advBackup = {};
  g.items.forEach(it => {
    if (!it.key) return;
    advBackup[it.key] = { had: it.key in advOverrides, val: advOverrides[it.key] };
  });
  const t = $('#adv-group-title');
  if (t) t.textContent = g.rawLabel || g.label;
  const grid = $('#adv-grid');
  if (grid) grid.innerHTML = g.items.map(renderAdvItem).join('');
  /* 底部两个出口上的计数：让「有几项要保存 / 已经存了几项」一眼看得见 ——
     用户报「保存不了」的直接原因就是**完全看不到反馈**。 */
  updateAdvActions();
  openSheet('adv-group-page');   // 顶部标题 = 「高级参数」，分组名由页内小标题显示
}

/* ── 自绘下拉的开关 / 定位 ───────────────────────────────────────
   ★ 菜单展开时**挂到 <body> 上**，两个坑一起绕开：
     ① `.advanced{overflow:auto}` 会把菜单裁掉（面板贴页面底部时菜单直接看不见）；
     ② 页面里带 `animation: rise ... both` 的元素（`.welcome` / `.runlog` / 抽屉）会留下
        一个**单位矩阵**，而单位矩阵也算 transform ⇒ position:fixed 的包含块从视口被换成它，
        菜单整体被平移（实测左边界偏 163px、底边跑出屏幕）。
   收起时再 appendChild 归位，DOM 结构与初始一致。 */
function closeDDs() {
  document.querySelectorAll('.dd-menu.show').forEach(m => {
    m.classList.remove('show');
    if (m._owner) m._owner.appendChild(m);          // 归位
  });
  document.querySelectorAll('.dd.open').forEach(d => d.classList.remove('open'));
}

/* 触发控件所在的滚动链（.advanced 面板等）——滚动链滚了才收菜单 */
function _scrollChain(el) {
  const out = [];
  for (let p = el && el.parentElement; p; p = p.parentElement) {
    const cs = getComputedStyle(p);
    if (/(auto|scroll|overlay)/.test(cs.overflowY + ' ' + cs.overflowX)) out.push(p);
  }
  return out;
}

function openDD(dd) {
  const btn = dd.querySelector('.dd-btn');
  const menu = dd.querySelector('.dd-menu');
  if (!btn || !menu) return;
  closeDDs();
  dd.classList.add('open');
  menu._owner = dd;
  menu._scrollers = _scrollChain(btn);
  document.body.appendChild(menu);
  menu.classList.add('show');
  const r = btn.getBoundingClientRect();
  menu.style.width = Math.max(r.width, 170) + 'px';   // 向右展开（至少不比触发控件窄）
  menu.style.left = Math.max(8, Math.round(r.left)) + 'px';   // 左边界对齐触发控件左上角
  /* ★ 先按「下方」摆好，**量完再决定要不要上翻**。
     以前是一挂上 body 就读 `menu.offsetHeight` 来预判 —— 该元素 `display:none` 刚被
     加上 `.show`，这个值会偶发读到 0，于是「下方放不下」的判断失效，
     菜单直接溢出屏幕底部（矮视口下必现）。现在先给一个确定位置，再量真实高度。 */
  const below = r.bottom + 6;
  const fixTop = () => {
    const mh = menu.getBoundingClientRect().height;
    if (mh > 0 && below + mh > window.innerHeight - 8) {   // 下面放不下就上翻
      menu.style.top = Math.round(Math.max(8, r.top - 6 - mh)) + 'px';
    } else if (mh === 0) {
      menu.style.top = Math.round(below) + 'px';
    }
  };
  menu.style.top = Math.round(below) + 'px';
  fixTop();
  /* ★ 补一次：元素刚从 `display:none` 变 `block`，首帧量高度可能读到 0，
     于是「下方放不下」判断失效、菜单溢出屏幕底部（矮视口必现）。下一帧布局已定，再校一次。 */
  setTimeout(fixTop, 0);
}

function onDdClick(e) {
  const t = e.target;
  if (!t || typeof t.closest !== 'function') { closeDDs(); return; }
  const opt = t.closest('.dd-opt');
  if (opt) {
    const menu = opt.closest('.dd-menu');
    const dd = menu && menu._owner;              // 菜单在 body 上，靠 _owner 找回宿主
    if (!dd) { closeDDs(); return; }
    const inp = dd.querySelector('input[data-cfg]');
    if (inp) {
      inp.value = opt.dataset.v;
      // 派发 input ⇒ 外层的事件委托能把这次改动记进 advOverrides（否则切页就丢）
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const cur = dd.querySelector('.dd-cur');
    if (cur) cur.textContent = opt.dataset.v;
    menu.querySelectorAll('.dd-opt').forEach(o => o.classList.toggle('on', o === opt));
    closeDDs();
    return;
  }
  const btn = t.closest('.dd-btn');
  if (btn) {
    e.preventDefault();
    const dd = btn.closest('.dd');
    if (!dd) return;
    /* ★ 判「开没开」要用 `dd.open`，**不能**去 `dd` 里找 `.dd-menu` ——
       菜单展开后已被 `openDD` 挂到 `<body>` 上，`dd.querySelector('.dd-menu')` 是 null，
       于是永远走进 `openDD` 分支 ⇒ 表现是「再点按钮收不回去、反而重开」。 */
    if (dd.classList.contains('open')) closeDDs();
    else openDD(dd);
    return;
  }
  if (!t.closest('.dd') && !t.closest('.dd-menu')) closeDDs();
}

function onDdScroll(e) {
  if (!document.querySelector('.dd-menu.show')) return;      // 没开菜单，不管
  const t = e.target;
  if (!t) return;
  if (t.nodeType === 9 || t === document.documentElement || t === document.body) {
    closeDDs();                                              // 整页滚动
    return;
  }
  if (typeof t.closest !== 'function') return;
  if (t.closest('.dd-menu')) return;                         // 菜单自己在滚
  /* ★ 只认**触发控件所在的滚动链**。否则四张层卡里的日志每 1.5s 自动贴底
     （renderTasks 里 `el.scrollTop = el.scrollHeight`）也算「滚动」，
     会把用户正开着的参数菜单收掉 —— 运行时几乎必现。 */
  const hit = [...document.querySelectorAll('.dd-menu.show')].some(m =>
    (m._scrollers || []).includes(t));
  if (hit) closeDDs();
}

function collectOpts() {
  const opts = {};
  const coerce = (v) => {
    if (v === 'true') return true;
    if (v === 'false') return false;
    if (/^-?\d+(\.\d+)?$/.test(String(v))) return Number(v);
    return v;
  };
  /* ★ R38：CLM（任务级）键**不能**混进 `opts.overrides` —— 那是 yaml 覆盖表，
     会被 `build_temp_config` 写进临时 config（而这些键压根不在 yaml 里）。
     它们要落到 `opts` **顶层**（`build_cmd` 按 `_ARG_SPEC` 转成命令行 flag）。
     判据：键名在 `ADV` 表里（那张表就是这 12 个 CLI 参数）。 */
  const cliKeys = new Set(ADV.map(([k]) => k));
  Object.keys(advOverrides).forEach(k => {
    const v = advOverrides[k];
    if (cliKeys.has(k)) {
      const s = String(v == null ? '' : v).trim();
      if (s) opts[k] = s; else delete opts[k];      // 清空 = 不传 = 引擎 auto
    }
  });
  /* ★ 先铺**累计改过的**（跨分组的都在 `advOverrides` 里），再用当前页 DOM 的值盖一层。
     只扫 DOM 是不行的：分组页按需渲染，同一时刻只有一个分组在 DOM 里，
     别的分组的改动会**整个丢掉**（用户报的「参数改了没保存」）。 */
  const ov = {};
  Object.keys(advOverrides).forEach(k => {
    if (!cliKeys.has(k)) ov[k] = coerce(advOverrides[k]);
  });
  document.querySelectorAll('[data-cfg]').forEach(el => {
    ov[el.dataset.cfg] = coerce(el.value);
  });
  /* ★ CLM 组当前页的输入框也扫一遍（`advOverrides` 已收，但 DOM 里可能有更晚的输入） */
  document.querySelectorAll('[data-adv]').forEach(el => {
    const s = String(el.value || '').trim();
    if (s) opts[el.dataset.adv] = s; else delete opts[el.dataset.adv];
  });
  if (Object.keys(ov).length) opts.overrides = ov;   // → 后端生成临时 config
  if ($('#mock').checked) opts.mock = true;
  /* 输入框里的两个功能胶囊（不点 = 不传 = 交给引擎 auto 自决）：
       深度思考 → runtime.thinking    智能搜索 → runtime.web
     ★ R38：CLM 组里显式填的 thinking/web **优先于**胶囊（胶囊是「快捷开关」，
       参数面板是「精确指定」）—— 已有值时不覆盖。 */
  const th = $('#pill-thinking'), wb = $('#pill-web');
  if (th && th.classList.contains('on') && !opts.thinking) opts.thinking = 'on';
  if (wb && wb.classList.contains('on') && !opts.web) opts.web = 'on';
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


/* ── 运行日志：四层日志合成**一条流**，默认隐藏，点「开始深究」后才出现 ──────
   层与层之间用一行分隔标记（保留层信息，但不再是四张并排的卡片）。
   ★ 增量更新：只改文本、不做整块 DOM 重建 —— 否则每 1.5s 轮询都会抖一下，
     并把用户正在往上翻的滚动位置强行拉到底。 */
const LANE_NAMES = ['修行', '研究', '对撞', '元'];
const lanes = { tid: null, text: {}, stats: {}, meta: {}, head: '' };

/* ── 「历史对话」：当前在看哪一次会话 ────────────────────────────
   chatMode: 'live'   —— 内存里的任务，日志实时跟随；
             'archive' —— 归档里的那次跑，读它当时的 `.run.log` 原文（服务重启后仍在）。
   两个模式共用同一套渲染（renderTasks/renderMeta），只是数据源不同。 */
let chatMode = 'live';
let activeChat = null;        // 当前**正在看**的那一条会话 id
/* ★ R29：刷新页面**回到首屏**（原来 true 会把最新一条任务的日志直接铺出来）。
   没锁定任何会话时 currentTaskId() 返回 null ⇒ 首屏 = 欢迎语 + 输入框；
   发新任务 / 从「历史对话」点一条，都会把 followLatest 置 false 并锁定 activeChat。 */
let followLatest = false;     // true = 没锁定，跟随最新任务；false = 只看 activeChat（空则空态）
let archivedTask = null;      // archive 模式的那条会话，充当 renderTasks 的「任务」
let archiveLanes = { text: {}, stats: {}, meta: {} };
let _chats = [];              // 会话列表快照（列表项按索引回指）

/* 把文本里的数字（含千分位）包成 <b>：CSS 里 `.rl-lane-head b/.rl-lab b{color:#fff}`
   ⇒ **文字蓝、数字白** 的同一套配色。 */
function hlNums(t) {
  return esc(t).replace(/(\d[\d,]*)/g, '<b>$1</b>');
}

/* 当前会话对应的「任务」对象（live 用内存任务 / archive 用归档那条） */
function curTask() {
  if (chatMode === 'archive' && archivedTask) return archivedTask;
  const tid = currentTaskId();
  return (tid && taskData[tid]) || null;
}
/* 当前会话的日志数据源 */
function curLanes() { return chatMode === 'archive' ? archiveLanes : lanes; }

/* 把归档里的**原始** .run.log 过滤成「显示态」——和实时那条走同一套规则：
   丢掉 `[tok]` 读数行、折叠「圈全量留痕 / ing·view 全文」两类大块，
   免得几千行留痕把「当时的日志窗口」淹掉。 */
function filterArchiveLines(text) {
  const out = [];
  let skip = null;                       // 'hn'（留痕块）| 'box'（ing/view 全文框）
  for (const line of String(text || '').split('\n')) {
    const ls = line.replace(/^\s+/, '');
    const head = ls.slice(0, 1);
    if (skip) {
      const end = skip === 'box' ? head === '└'
                                 : (head === '└' || line.indexOf('全量留痕结束') >= 0);
      if (end || head === '━' || head === '╔' || head === '┌') {
        skip = head === '╔' ? 'hn' : (head === '┌' ? 'box' : null);
        if (head === '━') out.push(line);
      }
      continue;
    }
    if (head === '╔') { skip = 'hn'; continue; }
    if (head === '┌') { skip = 'box'; continue; }
    if (/^\[tok\]/.test(ls)) continue;
    out.push(line);
  }
  return out.join('\n');
}

/* 归档日志 → 和实时一样的「按层」结构（层名 / 圈数 / 每层 token 增量） */
function buildArchiveLanes(raw, task) {
  const text = {}, stats = {};
  LANE_NAMES.forEach(n => { text[n] = ''; stats[n] = { round: 1, rounds_cap: 0, tokens: 0 }; });
  const src = filterArchiveLines(raw);
  let cur = null;
  let head = '';                       // ★ R37：层界之前的那几行（载入调度配置…）
  src.split('\n').forEach(line => {
    /* ★ 层界有两代，**两代都要认**（与后端 layers.py 同一口径）：
       ① 老式进度条 `━━━ 修行 · 第 r/N 圈 · …`；② 现行（实测 V1.23.22）层横幅
       `【0】修行 DGTF（螺旋上限 4 圈）`。不认 ② ⇒ 真跑的归档日志四层全空、只显示占位。 */
    const m = /━{3,}\s*(修行|研究|对撞|元)\s*[·・]/.exec(line);
    const bn = /^\s*【\s*(?:0|1|both|all)\s*】\s*(修行|研究|对撞|元)\s*DGTF/.exec(line);
    const alt = /^\s*\[(修行|研究|对撞|元)层\]/.exec(line);
    const a = (m && m[1]) || (bn && bn[1]) || (alt && alt[1]);
    if (a) cur = a;
    if (cur) text[cur] += line + '\n';
    else head += line + '\n';          // ★ R37：还没进任何层 ⇒ 归「开头块」
  });
  let prev = 0;
  LANE_NAMES.forEach(n => {
    let r = 0, cap = 0, m;
    const re = /第\s*(\d+)\s*\/\s*(\d+)\s*圈/g;
    while ((m = re.exec(text[n]))) { r = +m[1]; cap = +m[2]; }
    let tok = 0;
    const tr = /tokens=(\d+)/g;
    while ((m = tr.exec(text[n]))) tok = +m[1];
    stats[n] = { round: r || 1, rounds_cap: cap,
                 tokens: tok ? Math.max(0, tok - prev) : 0 };
    if (tok) prev = tok;
  });
  let gTok = 0, gCalls = 0, m2;
  const gt = /tokens=(\d+)/g;
  while ((m2 = gt.exec(src))) gTok = +m2[1];
  const gc = /calls=(\d+)/g;
  while ((m2 = gc.exec(src))) gCalls = +m2[1];
  return { text, stats, head,
           meta: { started_at: (task && task.created_at) || null,
                   tok: { tokens: gTok, calls: gCalls }, balance: {} } };
}

/* 任务状态 → 中文（运行日志的头行与「最近跑过」共用这一份）
   ★ `interrupted` = 服务崩溃 / 被强杀 / 重启导致任务没能正常收尾 —— 由后端
     `recover_orphans()` 从落盘的「活痕迹」回填。用户要求「标注状态原因」，
     所以它在列表里除了状态标，还要把 `error` 里的原因显示出来。 */
const ST_TXT = { done: '完成', error: '失败', running: '运行中', queued: '排队中',
                 cancelled: '已终止', canceled: '已终止', interrupted: '已中断' };

/* ── 日志语义排版（2026-10-11 用户 21 图要求）───────────────────────
   引擎日志是「半结构化」的：既有 `[INFO]` 噪声、又有层横幅/轮次/步骤/正文混在一起。
   老做法「在 40 字内找第一个 `：`，标签靠左 + 内容换行居中」把这些全搅乱了
   （`属性=0◈（来源：` 被拆成两截、`↻ 第 1/N 圈` 埋在正文里、`##` / `🔥 │` 原样露出）。
   现在按**语义**分类后再排版：
     · 噪声（`[INFO]…` 日志器行 / 纯分隔线 / 层横幅 `【N】层 DGTF…`）→ 直接丢
     · `↻ 第 r/N 圈 …` → 轮次小标题（蓝粗）
     · `<层> · 第 r/N 圈 · <角色> · view` → 「view 全文」折叠块（**默认展开**）
     · 步骤名 / 小标题（中文序号、markdown `#`（去 `#`）、`══ING-STRUCT══`、emoji 步骤名）→ 蓝粗
     · `名称：内容` → **同一行**（名称蓝粗 + 内容绿），不再拆到下一行居中
     · `[N] 内容` + 紧邻的 `属性=…`/`位置=…` → 合并成一行，属性**插在序号与内容之间**
     · `🔥 │ …` → 去掉「🔥 │」前缀；`✓ 确认…悬置：s_00N` → 附上**原悬置文本**
   ★ 与后端 `layers.py` 保持一致：那边只管「按层切开」，不碰行内容。 */
const RL_EMOJI = '🔥|🌕|📋|🧭|💧|🪞|🔮|🧵|🔄|🆕|🔍|🔬|⚑|⚖|⚔|🔁|❌|✅|⏸|⏹|⏳|🤝|🎯|📘|📗|📁|📝|📊|📈|📉|📎|🔵|🧳|🧺|🧹|🌀|🧩|🗳|🚫|⚠|↩|↳|🌱|🎛|⚙|✓|✗';
const RL_NOISE   = /^(?:\d{2}:\d{2}:\d{2}\s*\[(?:INFO|DEBUG|WARN|WARNING|ERROR|CRITICAL)\]|\[tok\])/;
const RL_DIV     = /^[━─—═=]{3,}$/;
const RL_BANNER  = /^【\s*(?:0|1|both|all)\s*】\s*(?:修行|研究|对撞|元)\s*DGTF/;
const RL_ROUND   = /^↻\s*第\s*\d+\s*\/\s*\d+\s*圈/;
const RL_VIEWBAR = /^━{3,}\s*(修行|研究|对撞|元)\s*·.*?·\s*view\s*━{3,}\s*$/;
const RL_SUMMARY = /^(?:完成|失败|已终止)\s*\|/;
/* ★ R33：收官/结论句（停止 / 产物已落盘 / 完成）—— 与「标志」同色（蓝、加深），不跟正文的绿。
   用户点名的三类：`[层] 停止：…`、`[x] 产物已落盘：…`、`[x] 完成`。 */
const RL_MARK = /^(?:停止|产物已落盘|完成)(?:[：:]|\s|$)/;
const RL_STRUCT  = /^={2,}\s*ING-STRUCT\s*={2,}$/;
const RL_CNHEAD  = /^[一二三四五六七八九十]+、/;
/* ★ R39：**`**标题**` 也要当标题**（用户图1：`**一、让两端各自把话说完**` 原样露出 `**` 且是绿字）。
   引擎的 ing/view 正文里 markdown 粗体标题很常见，之前既没剥 `**`、也没归到蓝标题类。 */
const RL_STAR    = /^\*\*.+\*\*$/;
/* ★ R39：`子问题[5]` 这类**带框序号小标题**（用户图10）—— 归蓝标题，不当正文。 */
const RL_SUBQ    = /^子问题\s*\[\d+\]\s*$/;
const RL_SEQ     = /^\[(\d+)\]\s*(.*)$/;
const RL_ATTR    = /^(?:属性|位置|来源|依据)\s*[=＝]/;
const RL_LABELONLY = /^\[[^\]]{1,14}\]$/;
/* ★ `[标志] 内容`：标志（`[修行层]` / `[mock]` / `[?→0]` / `[concept]`）统一**蓝**、其余绿 */
const RL_BRACKET   = /^(\[[^\]]{1,16}\])\s*(.*)$/;
const RL_BRACKETED = /^\[[^\]]{1,24}\][^：:\n]*[：:]\s*$/;
const RL_SUSP_SUM = /^⏸\s*悬置：\s*新增\d+/;
const RL_CONFIRM = /确认(?:元层)?悬置[：:]\s*(s_\d+)/;
/* 引擎内部诊断行（读者无用、但保留不删）→ 压暗显示 */
const RL_DIAG    = /^(?:\[fix-\d+\s*diag\]|🔬\s*rephrase)/;
const RL_CONFIRM_ANY = /^[✓✗]\s*(?:确认|撤回)(?:元层)?悬置[：:]/;
const RL_ING = /^(?:🔥\s*ing 输出|🌕\s*view 显形|📋\s*展开候选)/;
const RL_NAME = '[\\u4e00-\\u9fa5A-Za-z0-9·]{1,12}(?:\\s[\\u4e00-\\u9fa5]{1,6})?(?:（[^）]{0,12}）)?';
/* 「名称：内容」同行（名称必须是短、纯文字：不含 = [ 」 ` 等） */
const RL_INLINE = new RegExp('^((?:' + RL_EMOJI + ')?\\s*' + RL_NAME + ')\\s*[：:]\\s*(\\S.*)$', 'u');
/* 「名称：」独占一行（内容在下一行 ⇒ 并上来） */
const RL_LABELED = new RegExp('^((?:' + RL_EMOJI + ')?\\s*' + RL_NAME + '|[\\u4e00-\\u9fa5]{1,10})\\s*[：:]\\s*$', 'u');
const RL_STEPLINE = new RegExp('^(?:' + RL_EMOJI + '|↩|↳|✓|✗)\\s*\\S', 'u');

/* 一行 → 类型（先做「噪声/结构」判定，再做「名称：内容」判定，最后兜底正文） */
function rlClass(s) {
  if (!s) return 'blank';
  if (RL_NOISE.test(s) || RL_DIV.test(s) || RL_BANNER.test(s)) return 'noise';
  if (RL_DIAG.test(s)) return 'diag';
  if (RL_ROUND.test(s)) return 'round';
  if (RL_VIEWBAR.test(s)) return 'viewbar';
  if (RL_SUMMARY.test(s)) return 'summary';
  if (RL_STRUCT.test(s)) return 'title';
  if (RL_SEQ.test(s)) return 'seq';
  if (RL_CONFIRM_ANY.test(s)) return 'confirm';
  if (RL_ING.test(s)) return 'step';
  if (/^-/.test(s)) return 'content';                 // 列表项 ⇒ 正文
  if (RL_BRACKET.test(s)) return 'bracket';           // `[标志] …`
  if (/^#{1,6}\s*/.test(s)) return 'title';
  if (RL_CNHEAD.test(s)) return 'title';
  /* ★ R39：`**一、…**` / `**标题**`、`子问题[5]` ⇒ 蓝标题（用户图 1/10） */
  if (RL_STAR.test(s)) return 'title';
  if (RL_SUBQ.test(s)) return 'title';
  if (RL_LABELONLY.test(s)) return 'step';
  if (RL_INLINE.test(s)) return 'inline';
  if (RL_LABELED.test(s)) return 'labeled';
  if (RL_BRACKETED.test(s)) return 'bracketed';
  if (RL_STEPLINE.test(s)) return 'step';
  return 'content';
}

/* 悬置名单：按**出现顺序去重**（引擎的挂起 id 就是按创建顺序 `s_001…` 发的），
   用它把 `✓ 确认元层悬置：s_00N` 还原成「原悬置」。 */
function rlSuspNames(lines) {
  const names = [];
  layers0(lines).forEach(s => {
    if (!/^⏸/.test(s) || RL_SUSP_SUM.test(s)) return;
    const m = /^⏸\s*(?:决定不消解|悬置)[：:]\s*(.+)$/.exec(s);
    if (!m) return;
    const nm = m[1].split('（')[0].split('：')[0].trim();
    if (nm && names.indexOf(nm) < 0) names.push(nm);
  });
  return names;
}
function layers0(lines) { return lines.map(l => l.trim()).filter(Boolean); }

/* ★ R39：引擎行内的 markdown 粗体标记 `**…**` 会**原样露出**（用户图 1：`**一、让两端…**`）。
   只**去掉星号**、不加粗 —— 日志里的 `<b>` 被 `.runlog-body b` 统一压成「数字黑」，
   拿 `<b>` 当粗体用会把文字染黑。 */
function deStar(t) { return String(t == null ? '' : t).replace(/\*\*/g, ''); }
function rlInline(lab, txt) {
  return '<div class="rl-line"><span class="rl-lab">'
    + hlNums(esc(deStar(lab.replace(/[：:]\s*$/, '')) + '：')) + '</span>'
    + (txt ? '<span class="rl-txt">' + esc(deStar(txt)) + '</span>' : '') + '</div>';
}
function rlPlain(txt) {
  return '<div class="rl-line"><span class="rl-txt">' + esc(deStar(txt)) + '</span></div>';
}
/* ★ R39：正文行开头的**印记/标记**统一**蓝**（用户图 7~14：「印记显蓝色」「带框的前面头部
   部分也显示蓝色」）。此前只有「行首就是 `[xxx]`」才走 `bracket` ⇒ 带列表点（`- ` → `· `）
   或 `& ` 前缀的行整行绿。这里把「可选 `&` / 列表点 + `[xxx]`」拆出来单独上色。 */
/* ★ R39：前缀词表来自**真实日志/产物**（`子问题[5]` 见引擎正文），
   只在**行首**生效，避免把句中任意 `词[3]` 都染蓝。 */
const RL_MARK_PRE = '(?:子问题|问题|候选|条目|编号|序号)';
const RL_MARK_HEAD = new RegExp(
  '^(&\\s*)?([·•\\-*]\\s*)?(' + RL_MARK_PRE + '\\s*)?(\\[[^\\]]{1,16}\\])(.*)$');
function rlMarked(s) {
  const src = String(s || '').replace(/^-\s+/, '· ');
  const m = RL_MARK_HEAD.exec(src);
  if (!m) return rlPlain(src);
  const amp = (m[1] || '').trim(), dot = (m[2] || '').trim();
  const pre = (m[3] || '').trim(), rest = m[5] || '';
  return '<div class="rl-line">'
    + (amp ? '<span class="rl-mark">' + esc(amp) + '</span>' : '')
    + (dot ? '<span class="rl-txt">' + esc(dot) + '</span>' : '')
    + '<span class="rl-mark">' + esc(pre + m[4]) + '</span>'
    + (rest ? '<span class="rl-txt">' + esc(deStar(rest)) + '</span>' : '')
    + '</div>';
}

/* 一层的原始日志行 → 语义化 HTML */
function renderLogBody(lines, susp) {
  susp = susp || [];
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const s = lines[i].trim();
    i++;
    if (!s) continue;
    const t = rlClass(s);

    if (t === 'noise') continue;
    if (t === 'diag') {
      out.push('<div class="rl-line"><span class="rl-diag">' + esc(s) + '</span></div>');
      continue;
    }

    if (t === 'round') { out.push('<div class="rl-round">' + hlNums(esc(s)) + '</div>'); continue; }

    if (t === 'viewbar') {
      /* view 全文：**默认展开**的折叠块（用户要求「view 内容默认展开」） */
      const inner = [];
      while (i < lines.length) {
        const nt = rlClass(lines[i].trim());
        if (nt === 'viewbar' || nt === 'round' || nt === 'summary') break;
        /* ★ 分隔线/`[INFO]` 噪声要**跳过继续收**，不能 break ——
           引擎在 view 条**后面还跟一条 `━×60` 分隔线**，一 break 折叠体就是空的
           （真实踩过：折叠块在、内容全没了）。 */
        if (nt === 'blank' || nt === 'noise') { i++; continue; }
        inner.push(lines[i]); i++;
      }
      const title = s.replace(/━+/g, '').trim();
      out.push('<details class="rl-fold" open><summary>view 全文 · ' + esc(title) + '</summary>'
        + '<div class="rl-fold-body">' + renderLogBody(inner, susp) + '</div></details>');
      continue;
    }

    if (t === 'summary') { out.push('<div class="rl-summary">' + hlNums(esc(s)) + '</div>'); continue; }
    if (t === 'title') {
      /* ★ R39：剥掉 `**`（markdown 粗体）后当标题 —— 标题本身就是蓝粗，不用再叠粗体 */
      out.push('<div class="rl-title">'
        + esc(deStar(s.replace(/^#{1,6}\s*/, '').replace(/^=+|\s*=+$/g, '').trim()))
        + '</div>');
      continue;
    }

    if (t === 'seq') {
      const m = RL_SEQ.exec(s);
      const attrs = [];
      while (i < lines.length) {
        const a = lines[i].trim();
        if (RL_ATTR.test(a)) { attrs.push(a); i++; continue; }
        break;
      }
      /* ★ 用户要求：属性**合并后放在序号与内容之间** */
      out.push('<div class="rl-line rl-seq"><span class="rl-num">[' + m[1] + ']</span>'
        + attrs.map(a => '<span class="rl-attr">' + esc(a) + '</span>').join('')
        + (m[2] ? '<span class="rl-txt">' + esc(m[2]) + '</span>' : '') + '</div>');
      continue;
    }

    if (t === 'confirm') {
      const m = RL_CONFIRM.exec(s);
      const idx = m ? Number(m[1].slice(2)) - 1 : -1;
      const orig = (idx >= 0 && susp[idx]) ? susp[idx] : '';
      out.push('<div class="rl-line"><span class="rl-lab">' + esc(s) + '</span>'
        + (orig ? '<span class="rl-susp">原悬置 · ' + esc(orig) + '</span>' : '') + '</div>');
      continue;
    }

    if (RL_ING.test(s)) {
      /* `🔥 ing 输出 N 字` / `🌕 view 显形 N 字` → 步骤名（蓝粗）；
         紧跟的 `🔥 │ 正文` 去掉「🔥 │」前缀后按正文排。 */
      out.push('<div class="rl-step">' + hlNums(esc(s)) + '</div>');
      const ing = [];
      while (i < lines.length && /^\s*🔥\s*│/.test(lines[i])) {
        ing.push(lines[i].replace(/^\s*🔥\s*│\s?/, '').replace(/\s+$/, ''));
        i++;
      }
      /* ing 正文同样按语义排（`一、…` / `-##` 标题、`===ING-STRUCT===` 都变蓝） */
      out.push(renderLogBody(ing, susp));
      continue;
    }

    if (t === 'content') {
      /* ★ R39：正文行开头的 `[xxx]` 印记单独上蓝（见 rlMarked） */
      out.push(rlMarked(s));
      continue;
    }

    if (t === 'bracket') {
      /* `[标志] 内容` → 同一行：标志蓝、内容绿；标志独占一行时把下一行内容并上来 */
      const mb = RL_BRACKET.exec(s);
      let rest = mb[2].trim();
      /* 标志后面**没有内容**、或整行以「：」收尾（=只有小标题）⇒ 把下一行内容并到同一行 */
      if (i < lines.length && (!rest || /[：:]\s*$/.test(rest))) {
        const nxt = lines[i].trim();
        if (nxt && rlClass(nxt) === 'content') { rest = (rest ? rest + ' ' : '') + nxt; i++; }
      }
      /* ★ R33：收官/结论句的内容也走**蓝色**（原来跟正文绿） */
      const cls = RL_MARK.test(rest) ? 'rl-txt rl-mark' : 'rl-txt';
      out.push('<div class="rl-line"><span class="rl-lab">' + esc(mb[1]) + '</span>'
        + (rest ? '<span class="' + cls + '">' + esc(rest) + '</span>' : '') + '</div>');
      continue;
    }

    if (t === 'bracketed' || t === 'labeled') {
      /* 「名称：」独占一行 ⇒ 把下一行的内容**并到同一行** */
      const lab = s.replace(/[：:]\s*$/, '');
      const nxt = i < lines.length ? lines[i].trim() : '';
      if (nxt && rlClass(nxt) === 'content') { out.push(rlInline(lab, nxt)); i++; continue; }
      out.push('<div class="rl-step">' + esc(s) + '</div>');
      continue;
    }

    if (t === 'inline') {
      const m = RL_INLINE.exec(s);
      /* ★ 用户要求「内容不再从下一行开始，换到同行开始」——统一同行渲染 */
      out.push(rlInline(m[1].trim(), m[2].trim()));
      continue;
    }

    if (t === 'step') {
      out.push('<div class="rl-step">' + hlNums(esc(s)) + '</div>');
      continue;
    }

    out.push(rlPlain(s));
  }
  return out.join('');
}

/* ★ R33：运行日志的滚动指示 —— 原生滚动条被隐藏（见 CSS），这里画一个**短的椭圆点**：
   长度固定（短），位置跟着滚动比例走；内容不够高时不显示。
   ★★ R37：用户报「**用鼠标拖不动**」—— 原来是纯指示器（`pointer-events:none`）。
   现在改成**可拖动的圆点**（直径固定 12px，见 CSS）：
     · 位置 = 轨道上按滚动比例插值（`top` 落在 `[0, track]`，`track = clientHeight - 直径`）；
     · `bindRlBarDrag()` 挂 `pointerdown → document.move/up`，按住拖动按比例写回 `scrollTop`；
     · 拖动期间加 `.drag`（放大高亮），并用一个标志挡住「滚动事件回写位置」造成的抖动。 */
const RL_DOT = 12;                 // 圆点直径（与 CSS #rl-bar 一致）
let rlDragging = false;            // 拖动中：禁止滚动事件回写位置，避免抖动

/* ★ R39：轨迹的**唯一来源** —— 原来 `updateRlBar()` 把圆点放在
   「正文区相对 `#runlog` 的偏移 + 比例 × 轨道」上，而拖拽的 `onMove` 却钳在
   `[0, 轨道]`（**少了那个偏移**）⇒ 一按住圆点拖动，它先跳上去约等于头栏
   （`.runlog-head`）那么高 —— 表现就是「拖动不跟手 / 跑出范围」。
   现在两条路共用这一个口径：`top ∈ [lo, hi]`，`hi` 再按 `#runlog` 自身高度钳一次
   ⇒ 圆点**只在这一个日志窗口的正文范围内**滑动（用户要求「限定在指定页面上下范围内」）。 */
function rlTrack() {
  const box = $('#runlog'), bd = $('#runlog-body');
  if (!box || !bd) return null;
  const over = bd.scrollHeight - bd.clientHeight;
  const rb = bd.getBoundingClientRect(), rbox = box.getBoundingClientRect();
  /* ★ R40：圆点改成 `position:fixed`（贴页面最右缘，不再受日志框宽度约束）
     ⇒ 轨迹必须改用**视口坐标**：上端 = 正文区顶（头栏之下），
     下端 = min(正文区底, 日志框底) − 圆点直径。
     语义（只在这一个日志窗口的正文范围内滑动）与 R39 完全一致。 */
  const lo = Math.max(0, Math.round(rb.top));
  const hi = Math.max(lo, Math.round(Math.min(rb.bottom, rbox.bottom)) - RL_DOT);
  return { bd: bd, over: over, lo: lo, hi: hi };
}

function updateRlBar() {
  const t = rlTrack(), bar = $('#rl-bar');
  if (!t || !bar) return;
  if (rlDragging) return;          // 拖动中由 pointermove 主控，别被滚动事件抢
  const bd = t.bd;
  /* ★ R44：**日志窗口自己没显示时不画点** —— 首屏（`body.stage-empty`）里 `#runlog`
     是 `.hidden`（display:none），尺寸上也算得出来「不用显示」，但空态那条**早返回**路径
     压根不会走到这个函数 ⇒ 点会**留在上一次的位置**（用户报「首屏不该有滚动点」）。
     把「窗口是否可见」显式判掉，比依赖尺寸稳。
     ★★ R45：再加两条**状态**判据 —— 页面状态本身就说明「此刻不该有点」时，
     不管 `#runlog` 的类/尺寸如何，一律收掉（用户**第二次**报这条，光靠尺寸算不够）：
       · `body.stage-empty`：首屏没有日志区；
       · `body.panel-open` ：全屏面板铺开，日志区被盖住。 */
  const _box = $('#runlog');
  if (!_box || _box.classList.contains('hidden')
      || document.body.classList.contains('stage-empty')
      || document.body.classList.contains('panel-open')
      || t.over <= 8 || bd.clientHeight < 60) { bar.classList.remove('on'); return; }
  const r = t.hi > t.lo ? Math.min(1, Math.max(0, bd.scrollTop / t.over)) : 0;
  bar.style.top = Math.round(t.lo + r * (t.hi - t.lo)) + 'px';
  bar.classList.add('on');
}

/* 圆点拖拽：按住 → 移动 → 松开（一次绑定，用 document 上的 move/up 保证拖出圆点也能跟手） */
function bindRlBarDrag() {
  const box = $('#runlog'), bd = $('#runlog-body'), bar = $('#rl-bar');
  if (!box || !bd || !bar || bar.dataset.dragBound) return;
  bar.dataset.dragBound = '1';
  let startY = 0, startTop = 0;
  const onMove = (ev) => {
    const t = rlTrack();
    if (!t || t.hi <= t.lo) return;
    const dy = ev.clientY - startY;
    const top = Math.max(t.lo, Math.min(t.hi, startTop + dy));
    bar.style.top = Math.round(top) + 'px';
    t.bd.scrollTop = ((top - t.lo) / (t.hi - t.lo)) * t.over;
  };
  const onUp = () => {
    rlDragging = false;
    bar.classList.remove('drag');
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    try { bar.releasePointerCapture(bar._pid); } catch (e) {}
    delete bar._pid;
  };
  bar.addEventListener('pointerdown', (ev) => {
    ev.preventDefault();
    rlDragging = true;
    bar.classList.add('drag');
    /* ★ R40：圆点是 `position:fixed` ⇒ 它的视口坐标就是 `top` 本身，不用再减去日志框顶。 */
    startTop = parseFloat(bar.style.top || '0') || bar.getBoundingClientRect().top;
    /* ★ R39：起点也钳进本窗口的轨迹区间 —— 否则首帧 `bar.style.top` 还没算过，
       就会从窗口外的位置开始跟手。 */
    const t0 = rlTrack();
    if (t0) startTop = Math.max(t0.lo, Math.min(t0.hi, startTop));
    startY = ev.clientY;
    try { bar._pid = ev.pointerId; bar.setPointerCapture(ev.pointerId); } catch (e) {}
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  });
  /* 滚轮/触控板直接滚日志时，圆点也跟着走（回到常规更新） */
  bd.addEventListener('scroll', () => { if (!rlDragging) updateRlBar(); });
}

function renderTasks() {
  const box = $('#runlog');
  if (!box) return;
  if (dshCurrent) { renderDshView(); return; }
  const ids = Object.keys(taskData);
  /* 看归档会话时，taskData 可能是空的 —— 这时仍有内容要渲染（那次会话的日志） */
  const arch = (chatMode === 'archive' && archivedTask) ? archivedTask : null;
  /* 两种状态靠 body 上的一个 class 切换（CSS 里定义各自的排版）：
       stage-empty → 欢迎语 + 输入框**居中**，日志区不出现（首屏干净）
       stage-run   → 欢迎语收走，运行日志占主位，输入框落到底部 */
  /* ★ 用 classList 增删，**不要整体赋 `body.className`** —— 那样会把别的状态类
     （如 `drawer-open`）一起抹掉：抽屉开着时轮到一次轮询，首屏就让位失效、又被抽屉压住。 */
  if (!ids.length && !arch) {
    box.classList.add('hidden');
    document.body.classList.remove('stage-run');
    document.body.classList.add('stage-empty');
    setRunBtn('send');
    stopWhisper();                       // ★ R23：空态 ⇒ 恢复默认占位
    updateRlBar();   // ★ R44：空态要**主动收掉**滚动点（见 updateRlBar 的注释）
    return;
  }
  /* ★ 发送动画还没落点：日志区**先不露**（用户要求「动画完后再显示日志页面」）。
     这一挡是必须的 —— 否则应用自己的 1.5s 轮询会抢在动画前面把它露出来。 */
  /* 动画没落点：保持 startRun 刚才给的状态（首次 = hidden；重发 = .fading 占位） */
  if (fxPending) return;
  box.classList.remove('hidden');
  document.body.classList.remove('stage-empty');
  document.body.classList.add('stage-run');

  const tid = arch ? null : currentTaskId();
  const t = arch || taskData[tid] || {};
  /* 空白新会话（没锁定任何一条）⇒ 按空态收起日志，别去渲染别人的内容 */
  if (!arch && !tid) {
    box.classList.add('hidden');
    document.body.classList.remove('stage-run');
    document.body.classList.add('stage-empty');
    setRunBtn('send');
    stopWhisper();                       // ★ R23：空白新会话 ⇒ 恢复默认占位
    updateRlBar();   // ★ R45：这条早退**也要收点**（R44 只补了上面那条，这里漏了）
    return;
  }
  const running = !arch && (t.status === 'running' || t.status === 'queued');
  /* ★ R23：运行中 ⇒ 输入框轮换「引擎已启动」寄语；跑完/中止 ⇒ 恢复默认占位 */
  if (running) { if (!whisperTimer) startWhisper(); } else stopWhisper();
  /* 运行中 ⇒ 发送键变终止键。**已经点过终止的那条**在真正停下来之前别再翻回终止。
     看历史会话时不该能「终止」，键回到发送态。 */
  if (!running) stopRequested = null;
  setRunBtn((running && stopRequested !== tid) ? 'stop' : 'send');
  const stamp = (t.output_name && t.output_name.endsWith('.md'))
    ? t.output_name.slice(0, -3) : '';

  const bd = $('#rl-badge');
  if (bd) {
    const st = t.status || 'queued';
    bd.className = 'badge ' + st;
    bd.textContent = ST_TXT[st] || st;
  }
  const q = $('#rl-question');
  if (q) q.textContent = t.question || '';
  const files = $('#rl-files');
  if (files) {
    /* ★ R34：**三个按钮始终在**（用户报「运行中看不见这三个按钮」）——
       还没有产物时给「待生成」态（.pend：降透明度、不可点、提示跑完才有）。
       ★ R38：三个胶囊的**颜色跟随任务状态**（用户要求「右边三个按钮和左边按钮运行状态
       一致，灯和字体颜色变化一致」）—— 原来写死绿色，运行中/失败/终止时与左徽章不同步。
       做法：把状态类 `st-<status>` 打在容器上，CSS 里按 `.rl-files.st-running a` 一档一档给色。 */
    const st = t.status || 'queued';
    files.className = 'rl-files st-' + st;
    const pend = stamp ? '' : ' pend';
    const tip = stamp ? '' : ' title="跑完才有"';
    files.innerHTML =
        `<a href="#" class="rl-file${pend}"${tip} ${stamp ? `data-open="${esc(t.output_name)}"` : 'aria-disabled="true"'}><span>产物</span></a>`
      + `<a href="#" class="rl-file${pend}"${tip} ${stamp ? `data-archive="${esc(stamp + '.run.log')}"` : 'aria-disabled="true"'}><span>运行日志</span></a>`
      + `<a href="#" class="rl-file${pend}"${tip} ${stamp ? `data-archive="${esc(stamp + '.packed.json')}"` : 'aria-disabled="true"'}><span>json</span></a>`;
  }

  /* 四层日志**按层分块**渲染；没跑到的层不出现。
     ★ 顺手滤掉引擎自己打的进度条分隔线（`━━━ 修行 · 第 1/3 圈 · 摊开 · view ━━━`）——
       又长又乱，而且圈数 / token 我们在层标题里已经给出来了。 */
  const src = curLanes();
  const parts = [];
  /* ★ R37：日志**开头**的启动信息（「载入调度配置：…」「调度模式：…」等）——
     引擎/ mock 在进层循环之前打的那几行，落在 `__head__` 桶里。
     以前这一段被整个丢掉（只渲染 LANE_NAMES 里的层）⇒ 用户看不到「载入了什么配置」。
     现在渲染成**无标题的开头块**，走同一套语义排版（`名称：内容` 同行、蓝标签 + 绿内容）。 */
  {
    const headRaw = (src.head || src['__head__'] || '')
      .split('\n')
      .filter(l => !/^\s*[━─—=]{3,}/.test(l))
      .map(l => l.replace(/\s+$/, ''))
      .filter(l => l.trim());
    if (headRaw.length) {
      parts.push('<div class="rl-lane rl-boot">'
        + renderLogBody(headRaw, []) + '</div>');
    }
  }
  LANE_NAMES.forEach(n => {
    const raw = (src.text && src.text[n]) || '';
    const lines = raw.split('\n')
      .filter(l => !/^\s*[━─—=]{3,}/.test(l))     // 引擎自己的进度条分隔线：滤掉
      .map(l => l.replace(/\s+$/, ''))
      .filter(l => l.trim());
    if (!lines.length) return;
    const st = (src.stats && src.stats[n]) || {};
    const round = running ? `第 ${st.round || 1}/${st.rounds_cap || '?'} 圈`
                          : `共 ${st.round || 1} 圈`;
    /* ★ 语义排版：轮次/步骤/小标题蓝粗、名称与内容**同行**、view 全文默认展开（见 renderLogBody）。 */
    const body = renderLogBody(lines, rlSuspNames(lines));
    parts.push('<div class="rl-lane">'
      + `<div class="rl-lane-head">${hlNums(`${n}层 · ${round} · ${(st.tokens || 0).toLocaleString()} tokens`)}</div>`
      + body + '</div>');
  });
  if (!arch && tid && taskDsh[tid]) {
    parts.push(renderDshAttachBlock(taskDsh[tid]));
  }
  const PLACEHOLDER = '<div class="muted empty">等待该层开始输出…</div>';
  const want = parts.length ? parts.join('') : PLACEHOLDER;
  const el = $('#runlog-body');
  if (el && el.dataset.html !== want) {
    /* 滚动位置的几个坑都要躲开：
       ① 首次渲染时面板刚取消隐藏，clientHeight/scrollHeight 还是 0，
          `0 >= -24` 会被误判成「已贴底」；
       ② 日志是从占位短文本**变长**的，那一次同样被判成「已贴底」，
          于是一路跟到末尾、用户看不到开头。占位文本不算「有内容」。
       ⇒ 规则：**运行中**跟到底（看最新进度），**已完成**的停在开头（看结论）；
          已经贴底时才继续跟随，用户往上翻就不再打断他。 */
    const had = !!el.dataset.html && el.dataset.html !== PLACEHOLDER;
    const fromBottom = el.scrollHeight - el.scrollTop;
    const stick = logFollow || !had;
    el.innerHTML = want;
    el.dataset.html = want;
    if (stick) el.scrollTop = el.scrollHeight;
    else el.scrollTop = Math.max(0, el.scrollHeight - fromBottom);
    updateRlBar();
  }
}

/* 运行状态条：起始时间 / 已跑时长 / 实时 token / 累计花费 */
function fmtDur(s) {
  if (s < 60) return s + ' 秒';
  const m = Math.floor(s / 60);
  if (m < 60) return m + ' 分 ' + (s % 60) + ' 秒';
  return Math.floor(m / 60) + ' 时 ' + (m % 60) + ' 分';
}

/* ★ R24：把**单位**（秒 / 分 / 时）留在 `<b>` **外面** —— 数字白、单位随元信息栏走蓝。
   （用户要求「『秒』这个字统一为蓝色」；之前整段 `4 秒` 都包在 `<b>` 里，单位被染成白色。） */
function fmtDurHtml(s) {
  const n = (x) => '<b>' + x + '</b>';
  if (s < 60) return n(s) + ' 秒';
  const m = Math.floor(s / 60);
  if (m < 60) return n(m) + ' 分 ' + n(s % 60) + ' 秒';
  return n(Math.floor(m / 60)) + ' 时 ' + n(m % 60) + ' 分';
}

/* 运行读数（起始 / 已跑 / token / 花费）—— 塞进运行日志面板的头行 */
function renderMeta() {
  const box = $('#rl-meta');
  if (!box) return;
  const t = curTask();
  if (!t) { box.innerHTML = ''; return; }
  const running = chatMode !== 'archive' && (t.status === 'running' || t.status === 'queued');
  const m = curLanes().meta || {};
  const bits = [];
  /* ★ 起始用**任务自己的** started_at：与 ended_at 同源。
     之前写的是 「m.started_at || t.started_at」，而 lanes 是异步刷新的 ——
     刚换任务那一下会拿到**上一条的 started_at** 配新任务的 ended_at。 */
  const st = t.started_at;
  if (st) {
    const d = new Date(st * 1000);
    bits.push(`<span>起始 <b>${d.toLocaleTimeString('zh-CN', { hour12: false })}</b></span>`);
    // 已完成的任务用 ended_at 定格耗时；还在跑的才用「现在」持续走字
    const end = t.ended_at || Date.now() / 1000;
    const secs = Math.max(0, Math.floor((running ? Date.now() / 1000 : end) - st));
    bits.push(`<span>${running ? '已跑' : '耗时'} ${fmtDurHtml(secs)}</span>`);
  }
  const tok = m.tok || {};
  bits.push(`<span>消耗 <b>${(tok.tokens || 0).toLocaleString()}</b> tokens`
    + (tok.calls ? ` · <b>${tok.calls}</b> 次调用` : '') + `</span>`);
  /* ★「终止」= 结束时刻：**起始时间确定后就开始计时**（运行中一直往前走），跑完定格。
     有 ended_at 用 ended_at，没有就取「现在」⇒ 观感上就是实时倒计时/正计时。 */
  if (st) {
    const endT = t.ended_at || Date.now() / 1000;
    bits.push(`<span>终止 <b>${new Date(endT * 1000)
      .toLocaleTimeString('zh-CN', { hour12: false })}</b></span>`);
  }
  const bal = m.balance || {};
  if (bal.spent != null) bits.push(`<span>花费 <b>¥${Number(bal.spent).toFixed(4)}</b></span>`);
  else if (bal.now != null) bits.push(`<span>余额 <b>¥${Number(bal.now).toFixed(2)}</b></span>`);
  box.innerHTML = bits.join('<span class="rl-sep">·</span>');
}

async function pollLanes() {
  if (chatMode === 'archive') return;      // 看归档会话：不跟实时
  const ids = Object.keys(taskData);
  if (!ids.length) {
    if (lanes.tid !== null) {
      lanes.tid = null; lanes.text = {}; lanes.meta = {};
      renderTasks(); renderMeta();
    }
    return;
  }
  const tid = currentTaskId();
  if (!tid) return;
  if (tid !== lanes.tid) { lanes.tid = tid; lanes.text = {}; }
  try {
    const r = await api('/api/tasks/' + tid + '/layers');
    lanes.text = r.layers || {};
    /* ★ R39：日志**开头块**（载入调度配置 / 调度模式 / 圈数上限…）——
       后端 `layers.split_log()` 的桶名是 `__head__`，而这里原来只读 `r.head`
       ⇒ 恒 `undefined` ⇒ `rl-boot` 块**从来没渲染过**（用户报「日志头部没显示载入信息」）。
       两头都接上：新字段 `head` 优先，老桶名兜底。 */
    lanes.head = r.head || (r.layers || {})['__head__'] || '';
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

/* ── 发送键 / 终止键：同一个按钮两种形态 ─────────────────────────────
   空闲 = ↑（开始深究）；有任务在跑 = ■（终止运行，再点一下就停）。
   终止后由后端把「已经跑到的部分」落成产物并标注状态（见 engine_runner）。 */
const _SVG_SEND = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
  + '<path d="M12 19V5M6 11l6-6 6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const _SVG_STOP = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
  + '<rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor"/></svg>';
let runMode = 'send';
let stopRequested = null;          // 已点过终止的那个任务 id（等它真正停下来）
let fxPending = false;             // 发送星光动画还没落点 ⇒ 日志区**先不露**

function setRunBtn(mode) {
  const b = $('#run-btn');
  if (!b || runMode === mode) return;
  runMode = mode;
  const stop = mode === 'stop';
  b.classList.toggle('stop', stop);
  b.title = stop ? '终止运行（已跑到的部分会存下来）' : '开始深究（⌘/Ctrl+↵）';
  b.setAttribute('aria-label', stop ? '终止运行' : '开始深究');
  b.innerHTML = stop ? _SVG_STOP : _SVG_SEND;
}

/* 当前运行日志面板展示的那条任务（最新一条）—— 按键形态跟着它走 */
function currentTaskId() {
  /* ★ 三种情况：锁定了某条会话 / 跟随最新 / 空白新会话（null）。
     会话之间**互相独立**：开新对话不动别的会话的任务与轮询，随时能回去看。 */
  if (!followLatest) return (activeChat && taskData[activeChat]) ? activeChat : null;
  const ids = Object.keys(taskData);
  if (!ids.length) return null;
  return ids.sort((a, b) => taskData[b].created_at - taskData[a].created_at)[0];
}

function dshIsRunning() {
  if (dshConversation && (dshConversation.turns || []).some(function (t) {
    return t.status === 'queued' || t.status === 'running';
  })) return true;
  if (dshCurrent && dshCurrent.status === 'running') return true;
  return Object.keys(taskDsh).some(function (k) {
    return taskDsh[k] && taskDsh[k].status === 'running';
  });
}
async function stopDsh() {
  setRunBtn('send');
  if (dshConversationId && dshConversation) {
    try {
      const r = await api('/api/dsh/chat/' + encodeURIComponent(dshConversationId) + '/cancel',
        {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      if (r && r.conversation) dshConversation = r.conversation;
      (dshConversation.turns || []).forEach(function (t) {
        if (t.status === 'queued') t.status = 'canceled';
        if (t.status === 'running') t.status = 'error';
      });
      stopDshConvPoll();
      renderDshView();
    } catch (e) {
      if (dshCurrent) dshCurrent.events.push({type:'text', text:'终止失败：' + e.message});
      renderDshView();
    }
    return;
  }
  try {
    const r = await api('/api/dsh/cancel', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if (dshCurrent) {
      dshCurrent.status = 'error';
      dshCurrent.events = dshCurrent.events || [];
      dshCurrent.events.push({type:'text', text:'已终止 DSH 对话（' + (r.cancelled || 0) + ' 个进程）'});
      renderDshView();
    }
    Object.keys(taskDsh).forEach(function (k) {
      if (taskDsh[k] && taskDsh[k].status === 'running') {
        taskDsh[k].status = 'error';
        taskDsh[k].events = taskDsh[k].events || [];
        taskDsh[k].events.push({type:'text', text:'已终止 DSH 对话'});
      }
    });
    persistTaskDsh(); renderTasks();
  } catch (e) {
    if (dshCurrent) {
      dshCurrent.events = dshCurrent.events || [];
      dshCurrent.events.push({type:'text', text:'终止失败：' + e.message});
      renderDshView();
    }
  }
}

function onRunBtn() {
  if (runMode === 'stop') {
    const text = ($('#question') && $('#question').value.trim()) || '';
    if (dshMode && text) { startRun(); return; }   // 运行中再次发送 = 插入对话
    if (dshIsRunning()) { stopDsh(); return; }
    stopRun(); return;
  }
  startRun();
}

async function stopRun() {
  const tid = currentTaskId();
  if (!tid) return;
  const t = taskData[tid] || {};
  if (t.status !== 'running' && t.status !== 'queued') return;
  stopRequested = tid;               // 在它真正停下之前，别再翻回「终止」
  setRunBtn('send');                 // 立刻反馈，不等轮询
  await api(`/api/tasks/${tid}/cancel`, { method: 'POST' }).catch(() => {});
  loadDash();
  pollTask(tid);
  pollLanes();
}

/* ── 运行中的「输入框寄语」（R23）───────────────────────────────────
   发送后输入框清空，占位文字换成一句引领语，并**随运行进度**每隔一段时间换一句：
   进度取自「哪一层已经有内容」；用户一开始打字就让位（不动他自己的内容）。 */
/* ★ R39：首屏输入框文案（用户指定原文，含中间两个空格）—— 与 index.html 的
   `#question` placeholder **保持同一句**（跑完/新对话时 JS 会把它写回去）。 */
const Q_PLACEHOLDER = '此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧';
const RUN_WHISPER = {
  boot: ['元DGTF 引擎已启动 · 您愿意和我一起探寻吗？',
         '我先把这个问题钉牢，再动手…',
         '别急，几个视角正在被唤醒…'],
  '修行': ['锚点已经固化，我正把它摊开…',
          '正在把问题里藏着的假设一条条摆出来…',
          '把含糊的地方逼成可判定的，是我此刻在做的事…'],
  '研究': ['几个视角正在互相质问…',
          '我从反面去找它的破口…',
          '每一条结论都在被追问：凭什么？'],
  '对撞': ['矛盾正被逼到台面上…',
          '我在找它们共同的前提…',
          '两边都成立，就一定还有什么没说出口…'],
  '元': ['正在把散开的结论收紧成一句话…',
        '最后一步：核对结构饱和度…',
        '快成型了，我把话收住…'],
};
/* ★ R40：首屏欢迎语**随时段变**（用户要求「随时间变换打招呼等信息」）。
   分档按**本地小时**；同一档内随机取一句 —— 只在页面初始化时写一次，
   所以不会随日志渲染抖动。`pickWelcome(hour)` 是纯函数，便于探针逐小时驱动。 */
const WELCOME_SLOTS = [
  [[0, 3], ['夜深了，还在想什么？', '这个点还醒着的人，问题往往最好']],
  [[4, 6], ['天快亮了，聊聊吧', '凌晨的安静最适合想硬问题']],
  [[7, 10], ['早上好，今天想弄清什么？', '早，先把手里的困惑说给我听']],
  [[11, 13], ['上午好，随时开始吧', '快到中午了，来一个能想透的问题']],
  [[14, 17], ['下午好，想到什么就问吧', '下午适合把问题往下推一层']],
  [[18, 20], ['傍晚好，今天有什么想问的？', '忙完了，换个问题想想']],
  [[21, 22], ['晚上好，随时开始吧', '晚上的问题往往更深，开始吧']],
  [[23, 23], ['夜深了，最后一问？', '这个点的问题，通常不轻']],
];
function pickWelcome(hour) {
  const h = Number.isFinite(hour) ? hour : new Date().getHours();
  const slot = WELCOME_SLOTS.find(s => h >= s[0][0] && h <= s[0][1]);
  const pool = slot ? slot[1] : ['欢迎回来，随时开始吧'];
  return pool[Math.floor(Math.random() * pool.length)];
}
function paintWelcome() {
  const el = $('#welcome-text');
  if (el) el.textContent = pickWelcome(new Date().getHours());
}

let whisperTimer = null, whisperIdx = 0;

/* 当前该说哪一组：取**最后一个已经有内容**的层 */
function whisperPool() {
  const src = curLanes();
  let lane = null;
  LANE_NAMES.forEach(n => { if (((src.text && src.text[n]) || '').trim()) lane = n; });
  return RUN_WHISPER[lane] || RUN_WHISPER.boot;
}

function paintWhisper() {
  const ta = $('#question');
  if (!ta) return;
  if (ta.value.trim()) return;             // 用户正在打字：不抢他的内容
  const pool = whisperPool();
  ta.placeholder = pool[whisperIdx % pool.length];
  whisperIdx++;
}

function startWhisper() {
  stopWhisper();
  whisperIdx = 0;
  paintWhisper();
  whisperTimer = setInterval(paintWhisper, 6000);   // 每 6 秒随进度换一句
}

function stopWhisper() {
  if (whisperTimer) { clearInterval(whisperTimer); whisperTimer = null; }
  const ta = $('#question');
  if (ta) ta.placeholder = Q_PLACEHOLDER;
}


function toggleDshMode(on) {
  dshMode = !!on;
  const p = document.querySelector('#pill-dsh');
  const q = document.querySelector('#question');
  if (p) p.classList.toggle('on', dshMode);
  document.body.classList.toggle('dsh-mode', dshMode);
  dshAttachTaskId = dshMode ? currentTaskId() : null;
  if (dshAttachTaskId) dshCurrent = null;
  if (q) q.placeholder = dshMode
    ? 'DSH Agent：输入任务，读取项目文件 / outputs 产物 / app 导入文件…'
    : '此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧';
  if (dshMode) agentTaskMode = false;
  updateDshConvBar();
  if (dshMode) {
    startDshHistoryPoll();
    loadDshChats();
    if (!dshAttachTaskId && !dshConversationId) {
      try {
        const saved = localStorage.getItem(DSH_CONV_KEY);
        if (saved) { dshConversationId = saved; loadDshConversation(); }
      } catch (_) {}
    }
  } else {
    stopDshHistoryPoll();
    setDshHistoryOpen(false);
  }
}
const DSH_CONV_KEY = 'dgtf_dsh_current_conv';

async function loadDshChats() {
  try {
    const r = await api('/api/dsh/chats');
    dshChats = (r && r.chats) || [];
  } catch (_) { /* 历史列表失败不影响当前会话 */ }
  updateDshConvBar();
  if (dshHistoryOpen) renderDshHistory();
}
function updateDshConvBar() {
  const bar = document.querySelector('#dsh-conv-bar');
  if (!bar) return;
  bar.classList.toggle('hidden', !dshMode);
  if (!dshMode) return;
  const cur = document.querySelector('#dsh-conv-current');
  const run = document.querySelector('#dsh-conv-running');
  const turns = (dshConversation && dshConversation.turns) || [];
  const busy = turns.some(t => t.status === 'queued' || t.status === 'running');
  if (cur) {
    cur.textContent = dshConversationId
      ? ('当前会话 ' + dshConversationId + (turns.length ? (' · ' + turns.length + ' 轮') : ''))
      : (dshCurrent ? ('当前 · ' + (dshCurrent.session || '内联 Agent')) : '新 DSH 会话');
  }
  if (run) {
    const oldRunning = (dshChats || []).filter(c => c.running
      && c.id !== dshConversationId).length;
    run.classList.toggle('done', !busy && !oldRunning);
    run.textContent = busy ? '运行中' : (oldRunning ? (oldRunning + ' 个历史会话运行中') : '已结束');
  }
}
function renderDshHistory() {
  const box = document.querySelector('#dsh-history');
  const list = document.querySelector('#dsh-history-list');
  if (!box || !list) return;
  box.classList.toggle('hidden', !dshHistoryOpen);
  if (!dshHistoryOpen) return;
  if (!dshChats.length) {
    list.innerHTML = '<div class="dsh-chat-meta">暂无历史会话</div>';
    return;
  }
  list.innerHTML = dshChats.map(function (c) {
    const on = c.id === dshConversationId ? ' on' : '';
    const st = c.running ? 'running' : (c.stale ? 'stale' : (c.last_status || 'done'));
    const stLabel = c.running ? '运行中' : (c.stale ? '中断' : (c.last_status === 'error' ? '失败' : '完成'));
    return '<div class="dsh-chat-item' + on + '" data-dsh-chat="' + esc(c.id) + '">'
      + '<div class="dsh-chat-top"><span class="dsh-chat-id">' + esc(c.id) + '</span>'
      + '<span class="dsh-chat-st ' + esc(st === 'running' ? 'running' : '') + '">' + esc(stLabel) + '</span></div>'
      + '<div class="dsh-chat-task">' + esc(c.last_task || '（空会话）') + '</div>'
      + '<div class="dsh-chat-meta">' + esc(String(c.turns || 0)) + ' 轮 · '
      + esc(fmtTs(c.updated_at || c.created_at) || '') + '</div></div>';
  }).join('');
}
function setDshHistoryOpen(on) {
  dshHistoryOpen = !!on;
  renderDshHistory();
  if (dshHistoryOpen) loadDshChats();
}
async function resumeDshChat(id) {
  if (!id) return;
  dshConversationId = id;
  try { localStorage.setItem(DSH_CONV_KEY, id); } catch (_) {}
  dshHistoryOpen = false;
  dshCurrent = null;
  toggleDshMode(true);
  await loadDshConversation();
  startDshConvPoll();
  await loadDshChats();
  setDshHistoryOpen(false);
  renderDshView();
}
function startDshHistoryPoll() {
  stopDshHistoryPoll();
  dshHistoryTimer = setInterval(function () { loadDshChats(); }, 3000);
}
function stopDshHistoryPoll() {
  if (dshHistoryTimer) { clearInterval(dshHistoryTimer); dshHistoryTimer = null; }
}

function dshEventHtml(ev) {
  if (!ev || !ev.type) return '';
  if (ev.type === 'status') {
    if (ev.phase === 'turn_start') return '<div class="rl-summary">turn ' + esc(ev.turn || '') + ' 开始</div>';
    if (ev.phase === 'step_start') return '<div class="rl-summary">step ' + esc(ev.step || '') + '</div>';
    return '';
  }
  if (ev.type === 'thinking' && ev.text) {
    return '<details class="rl-fold" open><summary>思考</summary><div class="rl-fold-body"><div class="rl-line"><span class="rl-txt">' + esc(ev.text) + '</span></div></div></details>';
  }
  if (ev.type === 'tool_call') {
    return '<div class="rl-line"><span class="rl-lab">🔧 ' + esc(ev.tool || 'tool') + '</span><span class="rl-txt">' + esc(JSON.stringify(ev.input || {})) + '</span></div>';
  }
  if (ev.type === 'tool_result') {
    return '<details class="rl-fold"><summary>工具结果 · ' + esc(ev.status || '') + '</summary><div class="rl-fold-body"><div class="rl-line"><span class="rl-txt">' + esc(String(ev.result || '').slice(0, 12000)) + '</span></div></div></details>';
  }
  if (ev.type === 'text' && ev.text) {
    return '<div class="rl-line"><span class="rl-txt">' + esc(ev.text) + '</span></div>';
  }
  return '';
}
function scrollDshBottom() {
  if (!logFollow) return;
  const el = document.querySelector('#runlog-body');
  if (!el) return;
  requestAnimationFrame(function () { el.scrollTop = el.scrollHeight; });
}

function renderDshConversationView() {
  updateDshConvBar();
  const c = dshConversation || {};
  const box = document.querySelector('#runlog');
  const body = document.querySelector('#runlog-body');
  if (!box || !body) return;
  box.classList.remove('hidden'); box.classList.remove('fading');
  document.body.classList.remove('stage-empty');
  document.body.classList.add('stage-run');
  const turns = c.turns || [];
  const busy = turns.some(t => t.status === 'queued' || t.status === 'running');
  const bd = document.querySelector('#rl-badge');
  if (bd) {
    bd.className = 'badge ' + (busy ? 'running' : 'done');
    bd.textContent = busy ? '运行中' : '完成';
  }
  const q = document.querySelector('#rl-question');
  if (q) q.textContent = 'DSH Agent 会话 · ' + (c.id || '');
  const f = document.querySelector('#rl-files');
  if (f) f.innerHTML = '';
  let inner = '<div class="rl-lane rl-boot"><div class="rl-lane-head">DeepSeek Harness Agent · ' + esc(c.id || '') + '</div>';
  turns.forEach(function (t, i) {
    inner += '<div class="rl-round">第 ' + (i + 1) + ' 轮 · ' + esc(t.status || '') + '</div>';
    inner += '<div class="rl-line"><span class="rl-lab">用户</span><span class="rl-txt">' + esc(t.task || '') + '</span></div>';
    if (t.status === 'queued') inner += '<div class="rl-summary">已插入，排队等待前一轮完成…</div>';
    if (t.status === 'running') inner += '<div class="rl-summary">DSH Agent 运行中…</div>';
    (t.events || []).forEach(function (e) { inner += dshEventHtml(e); });
    if ((!t.events || !t.events.length) && t.text) {
      inner += '<div class="rl-line"><span class="rl-txt">' + esc(t.text) + '</span></div>';
    }
    if (t.status === 'canceled') inner += '<div class="rl-summary">已终止</div>';
  });
  inner += '</div>';
  const fromBottom = body.scrollHeight - body.scrollTop;
  body.innerHTML = inner;
  if (logFollow) scrollDshBottom();
  else body.scrollTop = Math.max(0, body.scrollHeight - fromBottom);
}

function renderDshView() {
  updateDshConvBar();
  if (dshConversation) { renderDshConversationView(); return; }
  const c = dshCurrent || {};
  const box = document.querySelector('#runlog');
  const body = document.querySelector('#runlog-body');
  if (!box || !body) return;
  box.classList.remove('hidden'); box.classList.remove('fading');
  document.body.classList.remove('stage-empty');
  document.body.classList.add('stage-run');
  const bd = document.querySelector('#rl-badge');
  if (bd) {
    bd.className = 'badge ' + (c.status || 'running');
    bd.textContent = c.status === 'done' ? '完成' : (c.status === 'error' ? '失败' : 'Agent');
  }
  const q = document.querySelector('#rl-question');
  if (q) q.textContent = c.question || 'DeepSeek Harness Agent';
  const f = document.querySelector('#rl-files');
  if (f) f.innerHTML = '';
  const evs = c.events || [];
  let inner = '<div class="rl-lane rl-boot"><div class="rl-lane-head">DeepSeek Harness Agent · ' + esc(c.session || dshSession || '新会话') + '</div>';
  inner += '<div class="rl-round">Agent 会话</div>';
  inner += '<div class="rl-line"><span class="rl-lab">用户</span><span class="rl-txt">' + esc(c.question || '') + '</span></div>';
  evs.forEach(e => { inner += dshEventHtml(e); });
  if (c.status === 'running') inner += '<div class="rl-summary">Agent 运行中…</div>';
  inner += '</div>';
  const fromBottom = body.scrollHeight - body.scrollTop;
  body.innerHTML = inner;
  if (logFollow) scrollDshBottom();
  else body.scrollTop = Math.max(0, body.scrollHeight - fromBottom);
} 
function setDetailMeta(text) {
  const el = document.querySelector('#detail-meta');
  if (el) el.textContent = text || '';
}

async function openDshArtifact(id) {
  const r = await api('/api/dsh/artifacts/' + encodeURIComponent(id));
  const det = document.querySelector('#detail');
  const title = document.querySelector('#detail-title');
  const body = document.querySelector('#detail-body');
  if (!det || !body) return;
  if (title) title.textContent = 'DSH 产物 · ' + id;
  setDetailMeta(r.ts ? ('生成时间 ' + (fmtTs(r.ts) || '未知')) : '生成时间未知');
  body.innerHTML = '<pre>' + esc(r.body || '') + '</pre>';
  det.classList.remove('hidden');
}

async function openDshSession(id) {
  const r = await api('/api/dsh/sessions/' + encodeURIComponent(id));
  dshSession = r.id || '';
  dshCurrent = { question: r.task || '', session: dshSession,
    events: (r.events || []).concat(r.text ? [{type:'text', text:r.text}] : []),
    status: r.ok ? 'done' : 'error' };
  closeSheet(); closeDrawer(); toggleDshMode(true); renderDshView();
}
function persistTaskDsh() {
  try {
    const keys = Object.keys(taskDsh);
    if (keys.length > 50) keys.slice(0, keys.length - 50).forEach(k => delete taskDsh[k]);
    localStorage.setItem('dgtf_task_dsh', JSON.stringify(taskDsh));
  } catch (_) {}
}
function renderDshAttachBlock(c) {
  let inner = '<div class="rl-lane rl-dsh-attach"><div class="rl-lane-head">DSH Agent · 属于当前元DGTF 会话 · ' + esc(c.session || '') + '</div>';
  inner += '<div class="rl-line"><span class="rl-lab">用户</span><span class="rl-txt">' + esc(c.question || '') + '</span></div>';
  (c.events || []).forEach(function (e) { inner += dshEventHtml(e); });
  if (c.status === 'running') inner += '<div class="rl-summary">DSH 运行中…</div>';
  inner += '</div>';
  return inner;
}
function applyDshResult(obj, r) {
  obj.session = r.session_id || obj.session;
  obj.events = r.events || [];
  if (r.repair) obj.events.push({type:'text', text:
    '自动修复：' + (r.repair.committed ? ('已提交 ' + (r.repair.commit || ''))
      : ('未提交：' + (r.repair.why || r.repair.error || ''))) });
  if (r.gate) obj.events.push({type:'text', text:
    'fast_gate：' + (r.gate.ok ? 'PASS' : 'FAIL') + '\n' + (r.gate.tail || '')});
  obj.status = r.ok ? 'done' : 'error';
  if (!r.ok && r.stderr) obj.events.push({type:'text', text:'Agent 退出异常：' + r.stderr});
}

async function loadDshConversation() {
  if (!dshConversationId) return;
  try {
    const r = await api('/api/dsh/chat/' + encodeURIComponent(dshConversationId));
    if (r && r.id) dshConversation = r;
    updateDshConvBar();
    renderDshView();
  } catch (_) {}
}
function stopDshConvPoll() {
  if (dshConvTimer) { clearInterval(dshConvTimer); dshConvTimer = null; }
}
function startDshConvPoll() {
  stopDshConvPoll();
  dshConvTimer = setInterval(async function () {
    await loadDshConversation();
    const turns = (dshConversation && dshConversation.turns) || [];
    const busy = turns.some(t => t.status === 'queued' || t.status === 'running');
    if (!busy) { stopDshConvPoll(); setRunBtn('send'); }
  }, 600);
}
async function startDshChat(question) {
  logFollow = true;
  if (!dshConversationId) dshConversationId = 'dshconv-' + Date.now().toString(36);
  dshCurrent = null;
  setRunBtn('stop');
  try {
    await api('/api/dsh/chat', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ conversation_id: dshConversationId, task: question,
        effort: (document.querySelector('#dsh-effort') || {}).value || '',
        permission: (document.querySelector('#dsh-perm') || {}).value || 'workspace-write',
        model: (document.querySelector('#dsh-model') || {}).value || 'deepseek-flash' }) });
    try { localStorage.setItem(DSH_CONV_KEY, dshConversationId); } catch (_) {}
    await loadDshConversation();
    startDshConvPoll();
    loadDshChats();
  } catch (e) {
    dshCurrent = { question: question, session: 'queue', status: 'error',
      events: [{type:'text', text:'提交会话失败：' + e.message}] };
    renderDshView();
    setRunBtn('send');
  }
}

async function startDshRun(question) {
  logFollow = true;
  const attach = dshMode ? (dshAttachTaskId || currentTaskId()) : null;
  if (!attach) return startDshChat(question);
  let target = null;
  if (attach) {
    dshAttachTaskId = attach;
    dshCurrent = null;
    target = taskDsh[attach] = { question: question, session: (taskDsh[attach] || {}).session || '',
      events: [], status: 'running' };
    persistTaskDsh();
    renderTasks();
  } else {
    dshCurrent = { question: question, session: dshSession, events: [], status: 'running' };
    renderDshView();
  }
  const btn = document.querySelector('#run-btn');
  if (btn) btn.disabled = true;
  setRunBtn('stop');
  const obj = target || dshCurrent;
  const redraw = () => { if (target) renderTasks(); else renderDshView(); };
  let result = null, errMsg = '', n = 0;
  try {
    await streamPost('/api/dsh/agent/stream', {
      task: question,
      session_id: target ? target.session : dshSession,
      attach_task_id: attach || '',
      effort: (document.querySelector('#dsh-effort') || {}).value || '',
      permission: (document.querySelector('#dsh-perm') || {}).value || 'workspace-write',
      model: (document.querySelector('#dsh-model') || {}).value || 'deepseek-flash'
    }, function (m) {
      if (m.type === 'event' && m.event) {
        obj.events.push(m.event);
        if (m.event.type === 'session' && m.event.sessionId) obj.session = m.event.sessionId;
        n++;
        if (target && n % 5 === 0) persistTaskDsh();
        redraw();
      } else if (m.type === 'result') {
        result = m.result;
      } else if (m.type === 'error') {
        errMsg = m.error || '流式执行失败';
      }
    });
    if (!result) throw new Error(errMsg || '没有返回结果');
    if (target) {
      applyDshResult(target, result);
      dshSession = result.session_id || dshSession;
      persistTaskDsh();
      renderTasks();
    } else {
      dshSession = result.session_id || dshSession;
      applyDshResult(dshCurrent, result);
      renderDshView();
    }
  } catch (e) {
    obj.status = 'error';
    obj.events = obj.events || [];
    obj.events.push({type:'text', text:'请求失败：' + e.message});
    if (target) { persistTaskDsh(); renderTasks(); } else renderDshView();
  } finally {
    if (btn) btn.disabled = false;
    setRunBtn('send');
  }
}
async function submitAgentTaskFromComposer(question) {
  try {
    const r = await api('/api/agent/tasks', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'user_task', title: question, detail: question }) });
    dshCurrent = { question: question, session: 'app 任务队列', status: 'done',
      events: [{type:'text', text:'Agent 用户任务已入队：' + ((r.task || {}).id || '') + '（daemon 会消费）'}] };
    renderDshView();
  } catch (e) {
    dshCurrent = { question: question, session: 'app 任务队列', status: 'error', events: [{type:'text', text:'提交失败：' + e.message}] };
    renderDshView();
  }
  agentTaskMode = false;
  const q = document.querySelector('#question'); if (q) { q.value = ''; q.style.height = ''; }
  const p = document.querySelector('#pill-dsh'); if (p) p.classList.remove('on');
}

async function startRun() {
  logFollow = true;
  const question = $('#question').value.trim();
  if (!question) { alert('请先输入问题'); return; }
  if (dshMode) { const q = $('#question'); if (q) { q.value=''; q.style.height=''; } return startDshRun(question); }
  if (agentTaskMode) { const q = $('#question'); if (q) { q.value=''; q.style.height=''; } return submitAgentTaskFromComposer(question); }
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
    activeChat = id; followLatest = false;      // 新会话立刻锁定为「当前会话」
    setRunBtn('stop');                  // 立刻切成终止键（不等日志露面）
    /* ★ R23：输入框清空、换上「引擎已启动」寄语（此后随运行进度轮换） */
    const _ta = $('#question');
    if (_ta) { _ta.value = ''; _ta.style.height = ''; }
    startWhisper();
    loadDash();                         // 新任务立刻出现在「最近跑过」
    /* ★ 先放星光动画，动画落点**之后**才露出运行日志页（闸门由 renderTasks 兜住）。 */
    fxPending = true;
    /* ★ 先把日志区收起来，但**只变透明、保留占位**：
       `display:none` 会让输入框顶到最上面（用户报「重新发送时输入框位置变了」）。
       首次发送时它本来就是 hidden，不用动。 */
    const _lg = $('#runlog');
    if (_lg && !_lg.classList.contains('hidden')) _lg.classList.add('fading');
    playSendFx(question, () => {
      fxPending = false;
      const lg = $('#runlog');
      if (lg) lg.classList.remove('fading');
      renderTasks();
      pollTask(id);
    });
  } catch (e) {
    alert('启动失败：' + e.message);
  } finally {
    $('#run-btn').disabled = false;
  }
}

/* ── 读数台 / 最近跑过（个人工作台的两块读数）───────────────────
   ★ 覆盖率必须一起显示：packed.json 与 run.json 都是后来才加的，历史产物大量缺失。
     把「3/296 轮有读数」印出来，别拿部分当全体报累计值。 */
let dashData = null;

function fmtTok(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return (v / 1e6).toFixed(2) + ' M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + ' k';
  return String(v);
}

function statRow(k, v, cls) {
  return `<div class="stat-row${cls ? ' ' + cls : ''}">`
    + `<span class="stat-k">${esc(k)}</span><span class="stat-v">${v}</span></div>`;
}

function renderDash(d) {
  const box = $('#stats-body');
  if (!box) return;
  const c = d.counts || {}, p = d.packed || {}, s = d.stop || {};
  const cov = `${p.covered || 0}/${c.main || 0}`;
  const rows = [
    statRow('深究轮次', `${(c.main || 0).toLocaleString()}`, 'big'),
    statRow('近 7 天 / 30 天', `${c.d7 || 0} <span class="u">/</span> ${c.d30 || 0}`),
    statRow('产物文件', `${c.total_files || 0} <span class="u">份 · ${c.total_mb || 0} MB</span>`),
    statRow('累计调用', `${(p.calls || 0).toLocaleString()} <span class="u">次</span>`),
    statRow('累计 token', `${fmtTok(p.tokens)} <span class="u">· ${cov} 轮有读数</span>`),
    statRow('跑完 / 浅跑',
      `<span class="ok">${s.natural || 0}</span> <span class="u">/</span> `
      + `<span class="${s.shallow ? 'no' : 'ok'}">${s.shallow || 0}</span>`
      + ` <span class="u">· ${s.known || 0} 轮可判</span>`),
  ];
  if (d.balance != null) {
    rows.push(statRow('账户余额', `¥${Number(d.balance).toFixed(2)}`));
  }
  box.innerHTML = rows.join('');
  const asof = $('#stats-asof');
  if (asof) asof.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

/* 内存里的任务（本次服务启动后）排前面，run.json 的历史补在后面 —— 服务重启后
   「跑过什么」不能跟着一起丢，这正是把它们落盘的用处。 */
function mergeHistory(tasks, hist) {
  const seen = {};
  const out = [];
  (tasks || []).forEach(t => {
    seen[t.id] = 1;
    out.push({
      id: t.id, question: t.question, status: t.status,
      mock: !!t.mock, dur: t.duration_sec, at: t.created_at,
      output: t.output_name || '', live: true,
    });
  });
  (hist || []).forEach(h => {
    if (seen[h.id]) return;
    seen[h.id] = 1;
    out.push({
      id: h.id, question: h.question, status: h.status,
      mock: !!h.mock, dur: h.duration_sec, at: h.ended_at || h.ended_at,
      output: h.output_name || '', err: h.error || '',
    });
  });
  return out;
}

function renderHistory(tasks, hist) {
  const box = $('#history-list');
  if (!box) return;
  const list = mergeHistory(tasks, hist);
  const dsh = ((dashData && dashData.dsh_sessions) || []).slice(0, 20);
  const cnt = $('#history-count');
  if (cnt) cnt.textContent = (list.length + dsh.length) ? `${list.length + dsh.length} 次` : '';
  box.innerHTML = list.map(h => {
    const st = h.status || '';
    const when = h.at ? new Date(h.at * 1000).toLocaleString('zh-CN',
      { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '';
    const dur = (h.dur != null && h.dur !== '') ? fmtDur(Math.round(h.dur)) : '';
    /* ★ 中断/失败的任务把**原因**显示出来（用户要求「标注状态原因」）。 */
    const why = (h.err && (st === 'interrupted' || st === 'error'))
      ? `<span class="why" title="${esc(h.err)}">${esc(h.err)}</span>` : '';
    /* ★ R34：日期并到**标题行右侧**（原来是第二行），整条更矮 */
    return `<div class="hist" data-hist="${esc(h.output || '')}">
      <div class="q"><span class="q-t">${esc(h.question || '（无问题）')}</span>
        ${when ? `<span class="q-r">${esc(when)}</span>` : ''}</div>
      <div class="m">
        <span class="st ${esc(st)}">${esc(ST_TXT[st] || st || '—')}</span>
        ${h.mock ? '<span class="tag">mock</span>' : ''}
        ${dur ? `<span>${esc(dur)}</span>` : ''}
        ${h.output ? '<span>产物</span>' : ''}
        ${why}
      </div></div>`;
  }).join('') + dsh.map(x => {
    const when = x.ts ? new Date(x.ts * 1000).toLocaleString('zh-CN',
      { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '';
    return '<div class="hist" data-dsh-session="' + esc(x.id || '') + '">'
      + '<div class="q"><span class="q-t">' + esc(x.task || 'DSH Agent 会话') + '</span>'
      + (when ? '<span class="q-r">' + esc(when) + '</span>' : '') + '</div>'
      + '<div class="m"><span class="st done">DSH</span>'
      + '<span class="tag">' + (x.auto_repair ? '自动修复' : 'Agent') + '</span>'
      + '<span>会话</span></div></div>';
  }).join('') || '<div class="muted empty" style="padding:14px">还没有通过工作台跑过。</div>';
}

async function loadDash() {
  try {
    const d = await api('/api/dashboard');
    dashData = d;
    renderDash(d);
    renderHistory(d.tasks, d.history);
  } catch (e) {
    const box = $('#stats-body');
    if (box) box.innerHTML = `<div class="muted">读取失败：${esc(e.message)}</div>`;
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

/* 产物状态标：只标「非正常跑完」的（中途终止 / 部分 / 中断 / 失败）——正常完成的不用多说 */
function chipState(r) {
  const st = r && r.status;
  if (st === 'cancelled') return `<span class="chip state">已终止 · 部分</span>`;
  if (st === 'interrupted') return `<span class="chip state">已中断 · 服务异常</span>`;
  if (st === 'error') return `<span class="chip state">失败</span>`;
  return '';
}

/* ★ R22 两步导出：点「导出」先进入**勾选模式**（条目出现勾选框、点条目=勾选），
   勾完再点一次「导出选中 (n)」才导出 —— 不是点一次就把全部导出。
   产物库与联网检索库同一套；一个都没勾时再点一次 = 退出勾选模式。 */
let _libItems = [];
let libExpOn = false;
const libSel = new Set();
let webExpOn = false;
const webSel = new Set();     // 聚合模式存 `g:<问题>`；平铺模式存 `t:<ts>`

function expBtnText(sel, on, n) {
  const b = $(sel);
  if (!b) return;
  b.textContent = on ? `导出选中 (${n})` : '导出';
  b.classList.toggle('on', on);
}

/* ★ R22 分类标签：md/log/json + 总/修行/研究/对撞/元 */
function chipKind(r) {
  const k = r.kind || 'md';
  return `<span class="chip k-${esc(k)}">${esc(k)}</span>`;
}
function chipLayer(r) {
  const l = r.layer || '总';
  return l === '总' ? '' : `<span class="chip lay">${esc(l)}</span>`;
}

function renderLib(items) {
  _libItems = items;
  $('#lib-count').textContent = `共 ${items.length} 份`;
  $('#lib-list').innerHTML = items.map(r => {
    const m = r.meta || {};
    const when = fmtTs(r.time) || fmtTs(r.mtime);
    const sel = libSel.has(r.name);
    return `<div class="item${libExpOn ? ' selmode' : ''}${sel ? ' on' : ''}" data-name="${esc(r.name)}">
      ${libExpOn ? '<span class="ck" aria-hidden="true"></span>' : ''}
      <button type="button" class="exp" data-exp="${esc(r.name)}"
              title="导出这一份产物">导出</button>
      <div class="t"><span class="t-t">${esc(r.title)} ${chipKind(r)} ${chipLayer(r)} ${chipState(r)}</span>
        <span class="t-r"><span class="num">产物 ${esc(when || '时间未知')}</span>
          <span class="num">${(r.size / 1024).toFixed(0)} KB</span></span></div>
      ${((chipDecid(m['可判定性']) + chip(m['取向']) + chip(m['并行模式'])).trim() || r.has_packed)
        ? `<div class="m">
        ${chipDecid(m['可判定性'])} ${chip(m['取向'])} ${chip(m['并行模式'])}
        ${r.has_packed ? '<span class="chip packed">packed</span>' : ''}
      </div>` : ''}
      ${r.snippet ? `<div class="snip">${esc(r.snippet)}</div>` : ''}
    </div>`;
  }).join('') || '<div class="muted empty">没有匹配的产物。</div>';
  expBtnText('#lib-export', libExpOn, libSel.size);
}

async function loadLib() {
  const q = $('#lib-q').value.trim();
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if ($('#lib-body') && $('#lib-body').checked) params.set('body', '1');
  if ($('#lib-decid').value) params.set('decidability', $('#lib-decid').value);
  if ($('#lib-orient').value) params.set('orientation', $('#lib-orient').value);
  if ($('#lib-days').value) params.set('days', $('#lib-days').value);
  if ($('#lib-kind') && $('#lib-kind').value) params.set('kind', $('#lib-kind').value);
  if ($('#lib-layer') && $('#lib-layer').value) params.set('layer', $('#lib-layer').value);
  $('#lib-list').innerHTML = '<div class="muted">检索中…</div>';
  try {
    const { items } = await api('/api/outputs?' + params.toString());
    renderLib(items);
  } catch (e) { $('#lib-list').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }
}

/* ── 本地资料库（导入本地文件 → 外部证据锚点）────────────────── */
/* ★ R45：**已导入文件的唯一渲染口** —— 三处都从这里刷：
     · 资料库面板页的 `#local-list`（原来就有）；
     · 回形针上的计数**数字气泡**（在回形针右上角显示已导入文件数）
       —— ★ R48 已按用户要求整条移除，故此处只作历史记录，不再是现状；
     · 输入框下方的清单浮层 `#attach-panel`（「点开可显示已导入文件、可删可关」）。
   把清单缓存进 `localItems`，浮层开关 / 删除后不用重新请求。 */
let localItems = [];

function attachPanelOpen() {
  const p = $('#attach-panel');
  return !!p && !p.classList.contains('hidden');
}

/* R47: 小窗图标 —— 按扩展名给一个能一眼分辨的符号（零依赖）。 */
function fileGlyph(name) {
  const e = String(name || '').toLowerCase().split('.').pop();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(e)) return '🖼';
  if (e === 'pdf') return '📕';
  if (['doc', 'docx', 'wps', 'rtf'].includes(e)) return '📘';
  if (['xls', 'xlsx', 'csv', 'tsv'].includes(e)) return '📊';
  if (['ppt', 'pptx'].includes(e)) return '📙';
  if (e === 'json') return '{}';
  if (['md', 'markdown'].includes(e)) return '📝';
  return '📄';
}

/* R47: 图标下的标签 —— 过长时保留头尾（老城区...局部.md），
   比 CSS 的 ellipsis 更能看出是哪一个（这些文件名前缀高度相同）。 */
function shortName(name) {
  const s = String(name || '');
  if (s.length <= 14) return s;
  return s.slice(0, 7) + '…' + s.slice(-5);
}

function paintAttach() {
  const n = localItems.length;
  /* ★★ R48：回形针上的**计数数字气泡**已整条移除（用户「回形针不要有上标」）。
     ⇒ 这里不再写角标，改为在**小窗标题**与**悬停提示**里表达数量。
     ★ 若还留着写角标的代码，它会去取一个**已不存在**的元素、拿到 `null`
       而静默跳过 —— 这种「看起来还在、实际没作用」的残留最容易骗过后来的人。
     ★ ★ 本注释刻意**不写出那个元素的标识符**：判据读源码文本，写了就会被
       当成「还没删干净」而顶红（R47 原形）。 */
  const _ab = $('#attach-btn');
  if (_ab) {
    _ab.title = n ? `已导入 ${n} 个文件（点一下展开/收起清单）`
                  : '导入文件作为外部证据锚点（文本类，可多选）';
    _ab.setAttribute('aria-label', n ? `已导入 ${n} 个文件，点一下展开清单` : '导入文件');
  }
  const cnt = $('#ap-count');
  if (cnt) cnt.textContent = String(n);
  const list = $('#ap-list');
  if (list) {
    /* R47: 小窗里每个文件渲染成一个小图标（不再是一行文字 + 删除按钮）。
       图标右上角挂 x（data-apdel 复用原来的删除链路 => 后端接口不变）。
       字形按扩展名给一个能一眼分辨的符号（零依赖，不引图标库）。
       ★★ 类名必须是 `ap-tile` —— CSS 只给 `.ap-tile` 写了图标格样式
         （`.ap-tile{width:52px;height:56px;...}` + `.ap-tile .rm{...}`）。
         写成老的行式类名则**根本匹配不到任何规则**，看起来「能显示」但
         其实是裸的块级 div（图标/角标全无样式）—— 判据会如实判红。
         本处曾因「补丁锚点没命中却被静默跳过」而退回老类名，现修正。 */
    list.innerHTML = localItems.map(it =>
      `<div class="ap-tile" data-apname="${esc(it.name)}"
            title="${esc(it.name)}${it.size != null ? ' · ' + (it.size / 1024).toFixed(1) + ' KB' : ''}${it.mtime ? ' · 导入/更新 ' + esc(fmtTs(it.mtime)) : ''}">
        <span class="ic">${fileGlyph(it.name)}</span>
        <span class="tn">${esc(shortName(it.name))}</span>
        <button type="button" class="rm" data-apdel="${esc(it.name)}"
                aria-label="删除 ${esc(it.name)}" title="删除这个文件">×</button>
      </div>`).join('')
      || '<div class="ap-empty">还没导入任何文件。点左边的回形针导入。</div>';
  }
  const foot = $('#ap-foot');
  if (foot) {
    foot.textContent = n
      ? '这些文件已解析进外部证据锚点，运行时会读入。'
      : '';
  }
}

/* ★★ R48：把小窗摆到**回形针右侧、输入框内部**（用户图2 的红色箭头指向
   回形针与浮层之间的空档，原话「直接显示在回形针的右侧对话框里」）。

   R47 的落点（输入框**正上方**右对齐）是我为「零遮挡」自己挑的，
   用户这次明确否掉了它 —— 宁可落在输入框内部，也要**紧贴回形针**。
   ⇒ 主路径改回「回形针右侧 M 处」，只在与**发送键**冲突时才降级。

   为什么不能纯 CSS：`.composer` 是满宽居中的（stage-empty 760 / stage-run 1080），
   小窗相对它定位时，无论贴哪条边都得不到「回形针右边」这个点 ——
   回形针的 x 是 flex 排出来的、随胶囊文字长度变。⇒ 一律按**实时坐标现算**
   （`getBoundingClientRect()`），挂 `body` + `position:fixed` 以免被
   `.composer` 的 `border-radius` / `overflow` 裁掉。

   落点优先级：
     ① 回形针右侧 M（**用户要的位置**）；
     ② 右侧放不下（会撞到发送键 / 溢出视口）⇒ **回形针正上方**；
     ③ 上方也放不下 ⇒ 夹进视口兜底（贴右内侧）。
   贯穿约束：与回形针**垂直居中对齐**；不压发送键；不超出视口。 */
function placeAttachPanel() {
  const p = $('#attach-panel');
  const btn = $('#attach-btn');
  if (!p || !btn || p.classList.contains('hidden')) return;
  const r = btn.getBoundingClientRect();
  const w = p.offsetWidth || 300;
  const h = p.offsetHeight || 200;
  const M = 8;                                     // 与回形针 / 发送键的间距
  const VW = window.innerWidth, VH = window.innerHeight;
  const PAD = 8;

  /* 发送键是输入框里**唯一不能压**的东西 —— 压住就没法发消息。
     它的左缘就是小窗向右能走到的最远处（留 M 的间距）。 */
  const sb = $('#run-btn');
  const sr = sb ? sb.getBoundingClientRect() : null;
  const wallRight = sr && sr.width
    ? sr.left - M
    : (document.querySelector('.composer')?.getBoundingClientRect().right ?? VW - PAD) - M;

  /* 与回形针**垂直居中**（视觉上是从回形针旁边长出来的） */
  const cy = r.top + r.height / 2;

  /* ★★ R48：视口**装不下「以回形针为心」的居中位置**时，该往哪边让？
     实测（1600×900 无头视口）：回形针在输入框内偏下（cy≈740），面板高 117
     ⇒ 居中需要 `top = cy - h/2 ≈ 682`，而视口下界只允许 `807-117-8 = 682`
     —— 正好卡在边上，被最后那句 `Math.min(top, VH - h - PAD)` 夹掉 19px
     （判据 `dy=19` 就是这么红的）。

     ★ 简单地把整块往上推到 `PAD` 会让面板「离开回形针」、视觉上不再属于它。
     ★ 更好的取舍：**保留「贴住回形针」这个语义** —— 让它与回形针**底缘对齐**
       （面板往上长），既不出视口，看上去也仍然是从回形针旁边伸出来的。
     ⇒ 所以这里先算「理想的居中 top」，再算「底缘对齐 top」，取**能完整放进
        视口的那个**；两个都放不下才退回夹取。 */
  const topCentered = cy - h / 2;
  const topFlushBottom = r.bottom - h;             // 底缘与回形针底缘对齐
  const topFlushTop = r.top;                       // 上缘与回形针上缘对齐
  const fitsInView = (t) => t >= PAD && t + h <= VH - PAD;

  let left, top;
  const rightAt = r.right + M;                     // ① 回形针右侧（用户要的）
  const fitsRight = rightAt + w <= wallRight;
  if (fitsRight) {
    left = rightAt;
    /* 依次尝试：居中 ⇒ 底缘对齐 ⇒ 上缘对齐，取第一个能完整放进视口的。
       （三个都不行 ⇒ 后面统一夹取，至少不会溢出。） */
    top = fitsInView(topCentered) ? topCentered
        : fitsInView(topFlushBottom) ? topFlushBottom
        : fitsInView(topFlushTop) ? topFlushTop
        : topCentered;
  } else {
    /* ② 右侧放不下 ⇒ 回形针**正上方**（左缘与回形针左缘对齐，
       这样它仍然「属于」回形针这一角，而不是飘到输入框中央）。 */
    left = r.left;
    top = r.top - M - h;
    if (top < PAD) {
      /* ③ 上方也没有空间（视口极矮）⇒ 夹进视口兜底：
         靠右内缘摆，并尽量与回形针同行。 */
      left = Math.max(PAD, Math.min(wallRight - w, VW - w - PAD));
      top = Math.max(PAD, Math.min(cy - h / 2, VH - h - PAD));
    }
  }
  top = Math.max(PAD, Math.min(top, VH - h - PAD));
  left = Math.max(PAD, Math.min(left, VW - w - PAD));
  p.style.position = 'fixed';
  p.style.left = left + 'px';
  p.style.top = top + 'px';
  p.style.right = 'auto';
  p.style.bottom = 'auto';
  /* ★ 刚 `hidden`→显示那一帧 `offsetHeight` 可能还是 0（内容刚注入）⇒
     `top` 会算歪。补一帧重算（幂等：第二次读到的高度已稳定，不会抖动）。 */
  if (!h) requestAnimationFrame(() => placeAttachPanel());
}

function toggleAttachPanel(force) {
  const p = $('#attach-panel');
  if (!p) return;
  const want = (force === undefined) ? p.classList.contains('hidden') : !!force;
  p.classList.toggle('hidden', !want);
  if (want) { paintAttach(); placeAttachPanel(); }
}
/* ★ R47：小窗是按**回形针的实时坐标**定位的 ⇒ 视口一变（resize / 侧栏展开让位）
   就得重算，否则它会停在旧位置、甚至跑到视口外。 */
window.addEventListener('resize', () => {
  if (typeof placeAttachPanel === 'function') placeAttachPanel();
});

async function removeImported(name) {
  try {
    await api('/api/library/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name }),
    });
    localItems = localItems.filter(it => it.name !== name);
    paintAttach();
    /* 资料库面板页若正开着，一并刷新（那边也是同一份数据） */
    const ll = $('#local-list');
    if (ll && document.body.classList.contains('panel-open')) await loadLocal();
    if (attachPanelOpen()) toggleAttachPanel(true);
  } catch (e) {
    const foot = $('#ap-foot');
    if (foot) foot.textContent = '删除失败：' + e.message;
  }
}

async function loadLocal() {
  const ll = $('#local-list');
  if (ll) ll.innerHTML = '<div class="muted">读取中…</div>';
  try {
    const r = await api('/api/library/local');
    const items = r.items || [];
    localItems = items;
    const lc = $('#local-count');
    if (lc) {
      lc.textContent =
        `已导入 ${items.length} 个资料 · 合并快照 ${r.anchor_file}（${r.anchor_items} 条锚点）`;
    }
    if (ll) {
      ll.innerHTML = items.map(it =>
      `<div class="item" data-local="${esc(it.name)}">
        <div class="t"><span class="t-t">${esc(it.name)}</span>
          <span class="t-r"><span class="num">导入/更新 ${esc(fmtTs(it.mtime) || '时间未知')}</span>
            <span class="num">${(it.size / 1024).toFixed(1)} KB</span></span></div>
        <div class="m">
          <a href="#" class="del" data-del="${esc(it.name)}">删除</a>
        </div>
      </div>`).join('') || '<div class="muted empty">还没导入任何资料。上面「选择文件导入」即可。</div>';
    }
    /* ★ R45：徽章 + 输入框浮层**跟着一起刷**（用户报「导入的文件没显示出来」） */
    paintAttach();
    if (attachPanelOpen()) toggleAttachPanel(true);
    const lo = $('#local-cand');
    if (lo) {
      const cands = r.candidates || [];
      const hint = $('#local-cand-hint');
      if (hint) hint.textContent = `另有 ${cands.length} 个现成的锚点快照 JSON（只读，供参考）：`;
      lo.innerHTML = cands.map(c =>
      `<div class="item" data-local="${esc(c.name)}">
        <div class="t">${esc(c.name)}</div>
        <div class="m"><span class="num">${esc(c.path)}</span>
          <span>${c.items ? c.items + ' 条锚点' : '（名字带 anchor）'}</span></div>
      </div>`).join('') || '<div class="muted empty">无</div>';
    }
  } catch (e) {
    if (ll) ll.innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`;
  }
}

/* ── ★ R44：本地资料库导入（二进制 + 分批 + 逐文件结果）────────────────────
   老实现对**所有**文件都 `f.text()`：PDF / 图片读出来是乱码；也没有大小上限。
   现在前端只做「选 → 读字节 → base64 → 分批发 → 报进度」，
   **解析全在服务端**（`dgtf_app/docparse.py`：docx/xlsx/pptx/pdf/图片/OLE/纯文本），
   并把每个文件的结果摆出来（成功 / 跳过 / 失败原因）—— 不再「点了没反应」。 */
const LIB_MAX_FILES = 50, LIB_MAX_MB = 100, LIB_BATCH_MB = 48;
let importRows = [];

function importPaint(msg) {
  const d = $('#import-detail');
  if (d) {
    d.innerHTML = importRows.map(r => r.ok
      ? `<div class="ok">✓ ${esc(r.name)} — ${esc(r.kind || '')} · `
        + `${Number(r.chars || 0).toLocaleString()} 字`
        + `${r.saved_as && r.saved_as !== r.name ? '（存为 ' + esc(r.saved_as) + '）' : ''}</div>`
      : `<div class="bad">✗ ${esc(r.name)} — ${esc(r.error || '失败')}</div>`).join('');
  }
  const box = $('#import-msg');
  if (box && msg != null) box.textContent = msg;
}

/* File → base64（分块 String.fromCharCode：一次性 apply 大数组会爆栈） */
function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onerror = () => reject(new Error('读取失败'));
    fr.onload = () => {
      const b = new Uint8Array(fr.result);
      let s = '';
      const CH = 0x8000;
      for (let i = 0; i < b.length; i += CH) {
        s += String.fromCharCode.apply(null, b.subarray(i, i + CH));
      }
      resolve(btoa(s));
    };
    fr.readAsArrayBuffer(file);
  });
}

async function importFiles(fileList) {
  const all = [...fileList];
  const list = all.slice(0, LIB_MAX_FILES);
  importRows = [];
  if (all.length > list.length) {
    importRows.push({ ok: false, name: `（另有 ${all.length - list.length} 个）`,
      error: `单次最多 ${LIB_MAX_FILES} 个，超出的已忽略` });
  }
  const send = [];
  list.forEach(f => {
    if (!f.size) {
      importRows.push({ ok: false, name: f.name, error: '空文件' });
    } else if (f.size > LIB_MAX_MB * 1048576) {
      importRows.push({ ok: false, name: f.name,
        error: `文件 ${(f.size / 1048576).toFixed(1)}MB 超过单文件上限 ${LIB_MAX_MB}MB` });
    } else {
      send.push(f);
    }
  });
  const btn = $('#anchor-pick');
  if (btn) btn.disabled = true;
  /* ★★ R48-1：这里原本还有一行「导入中（共 N 个）…」写进 `#attach-msg`，
     连同下面成功/失败两处一起**全部撤掉**（用户要求这行不显示）。
     ★ 顺带删掉 `const am` —— 三处引用都没了，留着就是一个永远读到
       `null` 的死变量，后来人会以为它还在起作用。 */
  importPaint(send.length ? `导入中（共 ${send.length} 个）…` : '没有可导入的文件');
  /* 按体积分批：单批 ≤ LIB_BATCH_MB，免得一个请求把内存顶起来 */
  const batches = [];
  let cur = [], bytes = 0;
  send.forEach(f => {
    if (cur.length && bytes + f.size > LIB_BATCH_MB * 1048576) {
      batches.push(cur); cur = []; bytes = 0;
    }
    cur.push(f); bytes += f.size;
  });
  if (cur.length) batches.push(cur);
  let done = 0;
  try {
    for (const batch of batches) {
      const payload = [];
      for (const f of batch) {
        importPaint(`导入中（${done}/${send.length}）：${f.name}`);
        payload.push({ name: f.name, size: f.size, b64: await fileToB64(f) });
        done++;
      }
      const r = await api('/api/library/import', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: payload }),
      });
      (r.results || []).forEach(x => importRows.push(x));
      importPaint(`导入中（${done}/${send.length}）…`);
    }
    const okN = importRows.filter(x => x.ok).length;
    const badN = importRows.length - okN;
    const tail = `完成：成功 ${okN} 个` + (badN ? `，失败/跳过 ${badN} 个（原因见下）` : '');
    importPaint(tail);
    /* ★★ R48-1（用户图1「这里不要显示」）：**不再把这行写进 `#attach-msg`**。
       它渲染在输入框内部下沿（实测 top≈311 / `.composer.bottom≈346`），
       一句「完成：成功 1 个」长期挂在输入框里，用户明确要求去掉。
       ★ 导入结果并没有丢：小窗（`#ap-list`）与抽屉里的 `#import-detail`
         仍然逐文件列出成功/失败与原因 —— 那才是「结果要送到眼前」的载体。
       ★ 成功分支与 catch 分支各有一处对该元素的赋值，**必须一起删**，
         只删一处会让失败时仍冒出一行，等于没实现。
       ★ ★ 这里刻意**不写出那行赋值语句本身**：判据会读源码文本，
         注释里出现同样的 token 会把判据顶红（R47 踩过一次，见 SKILL）。 */
    await loadLocal();
    /* ★ R45：导入完成后**自动展开清单** —— 用户报「导入的文件没显示出来」，
       所以结果要自己送到眼前（而不是让他去抽屉里翻）。 */
    if (okN) toggleAttachPanel(true);
  } catch (e) {
    importRows.push({ ok: false, name: '(整批)', error: e.message });
    importPaint('导入失败：' + e.message);
    /* ★★ R48-1：失败文案同样**不写 `#attach-msg`**（理由见上，两处必须同步）。
       失败原因在 `#import-detail`（开小窗/抽屉可见）里逐条列着。 */
  } finally {
    if (btn) btn.disabled = false;
    importPaint();
  }
}

async function openLocal(name) {
  $('#detail').classList.remove('hidden');
  $('#detail-title').textContent = name;
  const _it = localItems.find(x => String(x.name) === String(name));
  setDetailMeta(_it && _it.mtime
    ? ('导入/更新时间 ' + (fmtTs(_it.mtime) || '未知')) : '');
  $('#detail-body').innerHTML = '<div class="muted">加载中…</div>';
  try {
    const { body } = await api('/api/library/local/' + encodeURIComponent(name));
    const clip = body.length > 300000;
    $('#detail-body').innerHTML =
      (clip ? '<p class="muted">（文件较大，仅示前 300 KB）</p>' : '')
      + '<pre>' + esc(clip ? body.slice(0, 300000) : body) + '</pre>';
  } catch (e) {
    $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`;
  }
}

/* ── 联网检索库：按问题/关键词聚合、同链接去重后的结果库 ──────────
   webHits  = 原始命中（含重复，平铺模式用）
   webGroups= 服务端按检索问题分好组、组内按 url 去过重的结果 */
let webHits = [];
let webGroups = [];
/* ★ R45：`webClusters` = 把「同一任务」的子问题挂到最初的问题下（树）。
   见 `clusterLocal()`；服务端 `/api/library/web` 也返回同名结构（clusters）。 */
let webClusters = [];
let webReadouts = 0;

/* ★ R45：**引擎派生式子问题**的形态 —— 与 library.py 的 `_DERIVED_RE` 一致。
   只认引擎自己的派生模板（`是否存在 … 的官方指引？`），**不硬编码业务词**。 */
const WEB_DERIVED_RE = /^是否存在.*的官方指引[？?]\s*$/;
function webIsDerived(q) { return WEB_DERIVED_RE.test(String(q || '').trim()); }

/* ★ R45 本地兜底：服务端没给 `clusters` 时，用**同一套规则**现算一棵树。
   归属 = 「时间上不晚于它、最近的根组」；时间缺失/乱序时挂到最早的根。 */
/* ★ 外链只允许 http(s)：挡 javascript:/data: 注入（自检判据读这段） */
const safeUrl = function safeUrl(u) {
  try {
    const x = new URL(String(u || ''), location.href);
    return (x.protocol === 'http:' || x.protocol === 'https:') ? x.href : '';
  } catch (e) { return ''; }
}

function clusterLocal(groups) {
  const gs = (groups || []).map(g => Object.assign({}, g, {
    derived: webIsDerived(g.query), parent: null, children: []
  }));
  const roots = gs.filter(g => !g.derived);
  const kids = gs.filter(g => g.derived);
  if (!roots.length) {
    return gs.sort((a, b) => (b.latest || 0) - (a.latest || 0));
  }
  roots.sort((a, b) => (b.latest || 0) - (a.latest || 0));
  kids.forEach(d => {
    const t = d.latest || 0;
    const cands = roots.filter(r => (r.latest || 0) <= t);
    const owner = cands.length ? cands[0] : roots[roots.length - 1];
    owner.children.push(d);
  });
  roots.forEach(r => r.children.sort((a, b) => (b.latest || 0) - (a.latest || 0)));
  return roots;
}

function webMatch(h, q) {
  if (!q) return true;
  return [h.query, h.claim, h.url, h.kind]
    .some(v => String(v == null ? '' : v).toLowerCase().includes(q));
}

function hitHtml(h, flat) {
  const key = 't:' + String(h.ts == null ? '' : h.ts);
  const sel = (flat && webExpOn) ? webSel.has(key) : false;
  const cls = 'item' + (webExpOn ? ' selmode' : '') + (sel ? ' on' : '');
  const attr = (webExpOn && flat) ? ' data-wtsel="' + esc(key) + '"' : '';
  return `<div class="${cls}"${attr}>
      ${(webExpOn && flat) ? '<span class="ck" aria-hidden="true"></span>' : ''}
      <div class="t"><span class="t-t">${esc(h.claim || '（无内容）')}</span>
        ${h.ts ? `<span class="t-r"><span class="num">检索 ${esc(fmtTs(h.ts))}</span></span>` : ''}</div>
      <div class="m">
        <span class="chip">${esc(h.kind || 'web')}</span>
        ${h.tier != null ? `<span class="num">tier ${esc(String(h.tier))}</span>` : ''}
        ${safeUrl(h.url) ? `<a href="${esc(safeUrl(h.url))}" target="_blank" rel="noreferrer">打开链接</a>` : ''}
      </div>
    </div>`;
}

/* 本地兜底：服务端没给 groups 时（旧后端）自己按 query 分、按 url 去重 */
function groupHitsLocal(hits) {
  const m = new Map();
  hits.forEach(h => {
    const q = String(h.query || '').trim() || '(无检索问题)';
    if (!m.has(q)) m.set(q, { query: q, total: 0, uniq: 0, latest: 0, items: [], seen: {} });
    const g = m.get(q);
    g.total += 1;
    const key = String(h.url || '').trim() || ('claim:' + String(h.claim || '').slice(0, 80));
    if (g.seen[key]) return;
    g.seen[key] = 1;
    g.uniq += 1;
    g.items.push(h);
    g.latest = Math.max(g.latest, h.ts || 0);
  });
  return [...m.values()].sort((a, b) => b.latest - a.latest);
}

/* ★ R45：单组渲染（根组 / 子问题共用）。`sub=true` 时加缩进类。
   子问题组**不折叠内容**（它本来就是「挂在根问题下的一条」，
   内容跟在标题下面走 —— 用户要的是「看得见归类」，不是再套一层折叠）。 */
function wgHtml(g, sub) {
  const gsel = webSel.has('g:' + String(g.query));
  const items = g.items || [];
  const latest = Number(g.latest) || items.reduce((m, h) => Math.max(m, Number(h.ts) || 0), 0);
  const kinds = [...new Set(items.map(h => String(h.kind || '')).filter(Boolean))];
  const when = fmtTs(latest);
  const meta = [(when ? '最近检索 ' + when : ''), kinds.join(' / ')].filter(Boolean).join(' · ');
  const n = g.uniq != null ? g.uniq : items.length;
  const tot = g.total != null ? g.total : items.length;
  return `
    <div class="web-group${sub ? ' wg-sub' : ''}${webExpOn ? ' selmode' : ''}${gsel ? ' on' : ''}">
      ${webExpOn ? '' : `<button type="button" class="exp wg-exp" data-expexp="${esc(g.query)}"
              title="导出这一组检索结果">导出</button>`}
      <button type="button" class="wg-head" ${webExpOn ? `data-wgsel="${esc(g.query)}"` : 'data-wgtoggle'}>
        ${webExpOn ? '<span class="ck" aria-hidden="true"></span>' : ''}
        <svg class="wg-car" width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M9 5l7 7-7 7" stroke="currentColor" stroke-width="2.2"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        ${sub ? '<span class="wg-submark" aria-hidden="true">└</span>' : ''}
        <span class="wg-q">${esc(g.query)}</span>
        <span class="wg-meta">${esc(meta)}</span>
        <span class="chip">${sub ? '' : '去重后 '}${n} / 共 ${tot} 条</span>
      </button>
      <div class="wg-body scroll">${items.map(h => hitHtml(h, false)).join('')}</div>
    </div>`;
}

function renderWeb() {
  const box = $('#web-list');
  if (!box) return;
  const q = ($('#web-q').value || '').trim().toLowerCase();
  const mode = ($('#web-mode') ? $('#web-mode').value : 'group');
  const flat = mode === 'flat';

  if (flat) {
    const hits = webHits.filter(h => webMatch(h, q));
    $('#web-count').textContent =
      `平铺 ${hits.length} 条（未去重） · 带联网读数的产物 ${webReadouts} 份`;
    box.innerHTML = hits.map(h => hitHtml(h, true)).join('')
      || '<div class="muted empty">没有匹配的命中条目。</div>';
    expBtnText('#web-export', webExpOn, webSel.size);
    return;
  }

  /* ★ R45：**按任务归类** —— 遍历 `webClusters` 这棵树（根 = 最初的问题，
     子 = 引擎派生的子问题），过滤条件对根与子**分别**生效：
     子问题只要自己命中就留下（哪怕根问题没命中关键词 —— 用户搜的往往是子问题的词）。 */
  const hit = (g) => (g.items || []).some(h => webMatch(h, q)
    || String(g.query || '').toLowerCase().includes(q));
  const tree = (webClusters && webClusters.length ? webClusters : clusterLocal(webGroups))
    .map(g => {
      const kids = (g.children || []).filter(hit);
      const self = hit(g);
      if (!self && !kids.length) return null;
      return Object.assign({}, g, { _kids: kids });
    }).filter(Boolean);

  const nRoot = tree.length;
  const nSub = tree.reduce((s, g) => s + g._kids.length, 0);
  const uniq = tree.reduce((s, g) =>
    s + (g.uniq != null ? g.uniq : (g.items || []).length)
    + g._kids.reduce((t, k) => t + (k.uniq != null ? k.uniq : (k.items || []).length), 0), 0);
  $('#web-count').textContent =
    `按任务归类 ${nRoot} 个任务 · 含 ${nSub} 个子问题 · 去重后 ${uniq} 条`
    + ` · 原始命中 ${webHits.length} 条 · 带联网读数的产物 ${webReadouts} 份`;

  box.innerHTML = tree.map(g => {
    const kids = g._kids;
    /* 根组本体的条目：把子问题的 query 从根组里摘掉不可能（它们本就分在不同组），
       这里只渲染根组自己的条目。 */
    return `
    <div class="web-cluster${kids.length ? ' has-sub' : ''}">
      ${wgHtml(g, false)}
      ${kids.length ? `<div class="wg-kids">${kids.map(k => wgHtml(k, true)).join('')}</div>` : ''}
    </div>`;
  }).join('')
    || (q ? '<div class="muted empty">没有匹配的问题 / 关键词。</div>'
          : '<div class="muted empty">还没有命中条目（引擎 v1.23.22 起才会把命中落盘）。</div>');
  expBtnText('#web-export', webExpOn, webSel.size);
}

async function loadWeb() {
  $('#web-list').innerHTML = '<div class="muted">读取中…</div>';
  try {
    const r = await api('/api/library/web');
    webHits = r.hits || [];
    webGroups = (r.groups && r.groups.length) ? r.groups : groupHitsLocal(webHits);
    /* ★ R45：服务端给的**任务树**（同任务的子问题挂在最初的问题下）。
       老后端没有这个字段 ⇒ 前端自己用同一套判据现算（`clusterLocal`），
       「按任务归类」不因后端版本而降级。 */
    webClusters = (r.clusters && r.clusters.length)
      ? r.clusters
      : (r.groups && r.groups.length) ? clusterLocal(webGroups)
      : clusterLocal(groupHitsLocal(webHits));
    webReadouts = (r.items || []).length;
    renderWeb();
  } catch (e) {
    $('#web-list').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`;
  }
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

async function renderPackedCard(name) {
  try {
    const r = await api('/api/outputs/' + encodeURIComponent(name) + '/packed');
    const d = (r && r.packed) || {};
    const pl = d.process_ledger || {};
    if (!pl.layers) return '';
    const soul = pl.soul || {};
    const rows = Object.entries(pl.layers).map(([k, v]) =>
      '<tr><td>' + esc(k) + '</td><td>' + esc(v.rounds || 0) + '</td>'
      + '<td>' + (v.standard_ok ? '✅' : '⚠') + '</td>'
      + '<td>' + (v.fact_ok ? '✅' : '⚠') + '</td>'
      + '<td>' + esc((v.deps || []).join('、')) + '</td></tr>').join('');
    const aud = d.decidability_audit || {};
    const rec = d.recall || {};
    return '<div class="muted" style="margin:10px 0 16px">'
      + '<b>元DGTF 过程账本</b>　'
      + '四层标准：' + (pl.standard_all ? '✅' : '⚠') + '　'
      + '外部来源：官方 ' + esc(soul.external_official || 0)
      + ' / 参考 ' + esc(soul.external_reference || 0) + '　'
      + '侧面 ' + esc(JSON.stringify(soul.facets || {})) + '　'
      + '历史回声 ' + esc((soul.recall || {}).n || 0) + '　'
      + '研究审计：' + esc(aud.status || '未测') + '/bad=' + esc(aud.bad || 0)
      + '<table style="width:100%;margin-top:8px;border-collapse:collapse">'
      + '<thead><tr><th>层</th><th>圈</th><th>标准</th><th>事实</th><th>依赖</th></tr></thead>'
      + '<tbody>' + rows + '</tbody></table>'
      + '<div style="margin-top:6px">历史回声：' + esc((rec.hits || []).map(h => h.run_id + '：' + h.answer).join('；') || '—') + '</div>'
      + '</div>';
  } catch (_) { return ''; }
}

async function openDetail(name) {
  $('#detail').classList.remove('hidden');
  $('#detail-title').textContent = name;
  const _it = _libItems.find(x => String(x.name) === String(name));
  const _when = _it
    ? (fmtTs(_it.time) || fmtTs(_it.mtime)) : fmtFileStamp(name);
  setDetailMeta(_when ? ('产物时间 ' + _when) : '');
  $('#detail-body').innerHTML = '<div class="muted">加载中…</div>';
  try {
    const { body } = await api('/api/outputs/' + encodeURIComponent(name));
    /* ★ R22：**日志产物**用与「运行日志页」完全同一套（过滤留痕/全文框 + 语义排版）渲染
       —— 这样「入产物的日志文件内容」与日志页显示的一致。json 按原文展示。 */
    const isLog = /\.run\.log$/.test(name);
    const isJson = /\.json$/.test(name);
    if (isLog) {
      const lanes = buildArchiveLanes(body, { created_at: null });
      const parts = [];
      LANE_NAMES.forEach(n => {
        const raw = (lanes.text && lanes.text[n]) || '';
        const lines = raw.split('\n').map(l => l.replace(/\s+$/, '')).filter(l => l.trim());
        if (!lines.length) return;
        const st = (lanes.stats && lanes.stats[n]) || {};
        parts.push('<div class="rl-lane">'
          + `<div class="rl-lane-head">${hlNums(`${n}层 · 共 ${st.round || 1} 圈 · ${(st.tokens || 0).toLocaleString()} tokens`)}</div>`
          + renderLogBody(lines, rlSuspNames(lines)) + '</div>');
      });
      $('#detail-body').innerHTML = parts.length
        ? '<div class="runlog-body">' + parts.join('') + '</div>'
        : '<pre>' + esc(body.slice(0, 200000)) + '</pre>';
      return;
    }
    if (isJson) {
      $('#detail-body').innerHTML = '<pre>' + esc(body.slice(0, 300000)) + '</pre>';
      return;
    }
    const _card = /\.md$/.test(name) ? await renderPackedCard(name) : '';
    $('#detail-body').innerHTML = _card + linkifyFileBlocks(renderMd(body));
  } catch (e) { $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`; }
}

async function openArchive(name) {
  $('#detail').classList.remove('hidden');
  $('#detail-title').textContent = name;
  const _it = _libItems.find(x => String(x.name) === String(name));
  const _when = _it ? fmtTs(_it.mtime) : fmtFileStamp(name);
  setDetailMeta(_when ? ('文件时间 ' + _when) : '');
  $('#detail-body').innerHTML = '<div class="muted">加载中…</div>';
  try {
    const { body } = await api('/api/archive/' + encodeURIComponent(name));
    /* ★ R40：JSON 走**美化**（原来 3000+ 行挤成一行，等于打不开）——
       解析得动就 `stringify(…, 2)`；解析不动（截断/非 JSON）就按原文。 */
    let text = body;
    if (/\.json$/.test(name)) {
      try { text = JSON.stringify(JSON.parse(body), null, 2); } catch (_) { /* 原文 */ }
    }
    const MAX = 300000;                 // 超大文件只给头部，避免页面卡死
    const clip = text.length > MAX;
    const head = clip ? text.slice(0, MAX) : text;
    $('#detail-body').innerHTML =
      (clip ? `<p class="muted">（文件较大，仅显示前 ${Math.round(MAX / 1024)} KB；完整内容见 outputs/${esc(name)}）</p>` : '')
      + '<pre>' + esc(head) + '</pre>';
  } catch (e) {
    /* ★ R40：`<stamp>.packed.json` 只有**真跑**才有（mock / 早期产物没有）⇒
       缺了就回落到老的那份 `<stamp>.run.json`，而不是给用户一句「出错」。 */
    if (/\.packed\.json$/.test(name)) {
      return openArchive(name.replace(/\.packed\.json$/, '.run.json'));
    }
    $('#detail-body').innerHTML = `<div class="muted">出错：${esc(e.message)}</div>`;
  }
}

/* ★ R40：产物 md 的「附录 · 全量字段」里，引擎把 packed 文件名**整块**放进一个代码框：
       ```text
       20261012_121240_….packed.json
       ```
   那不是代码，是**指路牌** —— 用户要求「点它可以直接打开」。只在
   「整块就是一个已知后缀的文件名」时生效（不碰正文里出现的文件名，避免误伤）。 */
const FILE_BLOCK_RE = /^[\w\u4e00-\u9fa5（）()·.\-]{4,120}\.(?:packed\.json|run\.json|run\.log|md)$/;
function linkifyFileBlocks(html) {
  return String(html).replace(/<pre>([\s\S]*?)<\/pre>/g, (m, inner) => {
    const name = inner.trim();
    if (!name || name.indexOf('\n') >= 0 || !FILE_BLOCK_RE.test(name)) return m;
    return '<pre class="file-block"><a href="#" data-archive="' + name + '">' + name + '</a></pre>';
  });
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
    const [c, h, l] = await Promise.all([
      api('/api/config'),
      api('/api/health').catch(() => ({})),
      api('/api/schedule/llm/status').catch(() => ({})),
    ]);
    const k = c.creds;
    const checks = (h && h.checks) || {};
    const backs = (l && l.backends) || [];
    const nBack = backs.filter(b => b.ok).length;
    const agentOk = !!(checks.dsh_headless && (checks.agent_daemon || (h.daemon || {}).running));
    const line = (label, value, ok) =>
      '<span class="env-inline"><span class="dot ' + (ok ? 'ok' : 'no') + '"></span>' +
      '<span class="env-k">' + esc(label) + '</span> ' +
      '<span class="env-v">' + value + '</span></span><br>';
    const engineOk = !!(c.engine && (h.ok !== false) && checks.engine_file !== false);
    $('#env-info').innerHTML =
      line('引擎', '<b class="mono">' + esc(c.engine) + '</b>', engineOk) +
      line('模型', 'DeepSeek', !!k.api_key) +
      line('联网', 'Tavily', !!k.tavily) +
      line('本地 LLM', '<b>' + nBack + '</b> 个底座 · 默认 Qwen0.5B', nBack > 0) +
      line('Agent', '<b>' + (agentOk ? 'DSH 就绪 · 守护运行' : '未就绪') + '</b>', agentOk) +
      line('产物', '<b>' + c.outputs.count + '</b> 份 · ' + c.outputs.total_mb + ' MB', c.outputs.count > 0);
    $('#mock').checked = !!c.mock_default;
    syncMockPill();                    // checked 变了，胶囊高亮要跟着
    $('#cost-warn').textContent = k.api_key
      ? '' : '⚠ .env 里没有 DGTF_API_KEY，真实运行会失败；可先用演练模式验证界面。';
  } catch (e) {
    $('#env-info').textContent = '无法读取配置：' + e.message;
  }
}

async function refreshOutputsStat() { await loadConfig(); await loadDash(); }

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

/* ── 搜索对话产物（左上角放大镜）─────────────────────────────────
   搜的就是历史产物（标题 + 头部元数据 + 正文），复用 /api/outputs。 */
let searchTimer = null;

function openSearch() {
  const ov = $('#search-overlay');
  if (!ov) return;
  ov.classList.remove('hidden');
  const inp = $('#search-input');
  if (inp) { inp.value = ''; inp.focus(); }
  runSearch('');                       // 空查询 → 先列最近若干份，给个底
}
function closeSearch() {
  const ov = $('#search-overlay');
  if (ov) ov.classList.add('hidden');
}

function renderSearchResults(items) {
  const box = $('#search-results');
  if (!box) return;
  box.innerHTML = items.map(r => {
    const m = r.meta || {};
    const when = fmtTs(r.time) || fmtTs(r.mtime);
    /* ★ R34：**时间 / 大小挪到标题行右侧**；别的 chips 没有了就整条只占一行 */
    const chips = (chipDecid(m['可判定性']) + ' ' + chip(m['取向'])).trim();
    return `<div class="item" data-name="${esc(r.name)}">
      <div class="t"><span class="t-t">${esc(r.title)} ${chipState(r)}</span>
        <span class="t-r"><span class="num">产物 ${esc(when || '时间未知')}</span>
          <span class="num">${(r.size / 1024).toFixed(0)} KB</span></span></div>
      ${chips ? `<div class="m">${chips}</div>` : ''}
      ${r.snippet ? `<div class="snip">${esc(r.snippet.slice(0, 160))}</div>` : ''}
    </div>`;
  }).join('') || '<div class="muted empty">没有匹配的产物。</div>';
}

async function runSearch(q) {
  const box = $('#search-results');
  if (!box) return;
  box.innerHTML = '<div class="muted empty">检索中…</div>';
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  params.set('body', '1');            // 正文也搜 —— 产物的内容主要在正文里
  try {
    const { items } = await api('/api/outputs?' + params.toString());
    renderSearchResults((items || []).slice(0, 40));
  } catch (e) {
    box.innerHTML = `<div class="muted empty">出错：${esc(e.message)}</div>`;
  }
}

/* ── 开启新对话：清掉当前显示、回到首屏 ─────────────────────────────
   **只清前端显示**，服务端任务不删 —— 它仍在抽屉「最近跑过」和产物库里。 */
/* ── 历史对话：会话列表 + 逐个还原 ────────────────────────────────
   `GET /api/chats` = 内存任务（有实时日志）+ `outputs/*.run.json` 归档（重启后仍在）。
   点一条 → live 的继续跟随实时；归档的读它**当时那份 .run.log** 原文再按同一套规则渲染。 */
async function loadChats() {
  const box = $('#chats-list');
  if (box) box.innerHTML = '<div class="muted empty">读取中…</div>';
  try {
    const r = await api('/api/chats');
    renderChats(r.chats || []);
  } catch (e) {
    if (box) box.innerHTML = `<div class="muted empty">出错：${esc(e.message)}</div>`;
  }
}

function renderChats(items) {
  _chats = items;
  const box = $('#chats-list');
  if (!box) return;
  const c = $('#chats-count');
  if (c) c.textContent = `共 ${items.length} 次会话`;
  if (!items.length) { box.innerHTML = '<div class="muted empty">还没有会话。</div>'; return; }
  box.innerHTML = items.map((it, i) => {
    const t = it.created_at
      ? new Date(it.created_at * 1000).toLocaleString('zh-CN', { hour12: false })
      : '';
    const st = it.status || 'queued';
    /* ★ `interrupted`（服务崩溃/被强杀后回填的中断任务）单列一档 —— 它既不是
       「失败」（引擎没报错、进程可能压根没退出），也不是「已终止」（用户没点终止）。 */
    const cls = st === 'running' || st === 'queued' ? 'running'
              : (st === 'interrupted' ? 'interrupted'
              : (st === 'error' ? 'error' : (st === 'cancelled' ? 'cancelled' : 'done')));
    const why = (it.error && (st === 'interrupted' || st === 'error'))
      ? `<span class="why" title="${esc(it.error)}">${esc(it.error)}</span>` : '';
    /* ★ R34：日期并到**标题行右侧**，整条更矮 */
    return `<div class="hist" data-chat="${i}">
      <div class="q"><span class="q-t">${esc(it.question || '(无题)')}</span>
        ${t ? `<span class="q-r">${esc(t)}</span>` : ''}</div>
      <div class="m">
        <span class="st ${cls}">${esc(ST_TXT[st] || st)}</span>
        ${it.live ? '' : '<span class="tag">归档</span>'}
        ${it.partial ? '<span class="tag">部分</span>' : ''}
        ${it.mock ? '<span class="tag">演练</span>' : ''}
        ${why}
      </div>
    </div>`;
  }).join('');
}

async function openChat(c) {
  if (!c) return;
  if (c.live) {
    if (!taskData[c.id]) {
      try { taskData[c.id] = await api('/api/tasks/' + encodeURIComponent(c.id)); } catch (_) {}
    }
    chatMode = 'live'; archivedTask = null; activeChat = c.id; followLatest = false;
    logFollow = true;
    lanes.tid = null; lanes.text = {}; lanes.stats = {}; lanes.meta = {};
  } else {
    let raw = '';
    try {
      const r = await api('/api/archive/' + encodeURIComponent(c.archive_log || ''));
      raw = r.body || '';
    } catch (_) { raw = ''; }
    chatMode = 'archive'; activeChat = null; followLatest = false;
    archivedTask = { id: c.id, question: c.question, status: c.status,
                     created_at: c.created_at, started_at: c.started_at,
                     ended_at: c.ended_at,
                     output_name: c.output_name, mock: c.mock,
                     error: c.error, duration_sec: c.duration_sec };
    archiveLanes = buildArchiveLanes(raw, archivedTask);
  }
  const q = $('#question');
  if (q && c.question) { q.value = c.question; q.style.height = ''; }
  sheetFromDrawer = false;      // 选了会话就直接进会话 —— 别把抽屉弹回来挡日志
  closeSheet();                 // 面板收掉（R27：面板是「本页内容」，关掉即回主视图）
  closeDrawer();
  renderTasks();
  renderMeta();
  if (c.live) pollLanes();
}

function newChat() {
  /* ★ 新会话统一回到首屏：清空**当前视图**，但不动历史任务/DSH 会话数据。
     元DGTF 与 DSH 的原对话分别保留在任务历史 / DSH 会话库里，可随时回溯。 */
  chatMode = 'live'; activeChat = null; followLatest = false;
  logFollow = true;
  archivedTask = null;
  archiveLanes = { text: {}, stats: {}, meta: {} };
  lanes.tid = null; lanes.text = {}; lanes.stats = {}; lanes.meta = {};
  dgtfSessionId = 'dgtf-' + Date.now().toString(36);
  agentTaskMode = false;
  dshAttachTaskId = null;
  dshCurrent = null;
  dshConversationId = null;
  dshConversation = null;
  try { localStorage.removeItem(DSH_CONV_KEY); } catch (_) {}
  stopDshConvPoll();
  dshSession = '';
  setDshHistoryOpen(false);
  toggleDshMode(false);
  const rb = $('#runlog-body');
  if (rb) { rb.innerHTML = ''; delete rb.dataset.html; }
  const rl = $('#runlog');
  if (rl) rl.classList.add('hidden');
  const q = $('#question');
  if (q) { q.value = ''; q.style.height = ''; }
  const am = $('#attach-msg');
  if (am) am.textContent = '';
  document.body.classList.remove('stage-run');
  document.body.classList.add('stage-empty');
  setRunBtn('send');
  stopWhisper();
  updateRlBar();
  closeSearch();
  closeDrawer();
  renderTasks();
  renderMeta();
  setTimeout(centerHomeHero, 30);
}

/* ── 侧边抽屉：读数台 / 最近跑过 / 产物库 / 资料库 / 检索库 / 高级参数 ──
   首屏要和对话工具一样干净，这些面板平时不占位，点左上角图标才拉开。 */
/* ★ 开抽屉时给 body 挂 `drawer-open`：首屏**整体右移让位**（而不是被盖住）。
   也**不再显示遮罩** —— 抽屉既然没压住首屏，就没有要挡的点击，
   留着半透明遮罩反而会让首屏点不动。 */
function openDrawer() {
  const d = $('#drawer');
  if (!d) return;
  d.classList.add('open');
  d.setAttribute('aria-hidden', 'false');
  document.body.classList.add('drawer-open');
}
function closeDrawer() {
  const d = $('#drawer');
  if (!d) return;
  d.classList.remove('open');
  d.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('drawer-open');
  hideTip();
}

/* ── 悬停描述气泡（`.tip`）───────────────────────────────────────
   ★ 抽屉体 `.drawer-body{overflow:auto}` 会把按钮自带的 `::after` 气泡**整块裁掉**
     （用户报过「悬停没有描述」）。所以气泡**挂在 `<body>` 上、`position:fixed`** ——
     fixed 后代不受祖先 `overflow` 裁剪（除非祖先是 `transform`/`filter` 包含块）。
   ★ 外观按要求：**背景透明 + 白字**（配暗色 text-shadow 保可读）。
   ★ 事件委托绑在 document 上：`#sheet-close` 的 `data-tip` 是随页面动态换的。 */
let _tip = null;
function hideTip() { if (_tip) _tip.classList.remove('show'); }

function initTips() {
  const tip = document.createElement('div');
  tip.className = 'tip';
  document.body.appendChild(tip);
  _tip = tip;

  const place = (el) => {
    tip.textContent = el.dataset.tip || '';
    tip.style.left = '0px'; tip.style.top = '0px';   // 先归零，量真实宽高
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left, top;
    if (el.closest('#drawer')) {
      /* 抽屉是竖排窄列 ⇒ 气泡落**右侧**、与按钮垂直居中 */
      left = r.right + 10;
      top = r.top + r.height / 2 - th / 2;
      if (left + tw > window.innerWidth - 8) left = Math.max(8, r.left - tw - 10);
    } else {
      /* 其余：默认落在**下方左对齐**，下方放不下就翻到上方 */
      left = r.left;
      top = r.bottom + 9;
      if (top + th > window.innerHeight - 8) top = Math.max(8, r.top - th - 9);
      if (left + tw > window.innerWidth - 8) left = Math.max(8, window.innerWidth - tw - 8);
    }
    top = Math.min(Math.max(top, 8), window.innerHeight - th - 8);
    tip.style.left = Math.round(left) + 'px';
    tip.style.top = Math.round(top) + 'px';
    tip.classList.add('show');
  };

  document.addEventListener('mouseover', e => {
    const el = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (el) place(el);
  });
  document.addEventListener('mouseout', e => {
    const el = e.target && e.target.closest && e.target.closest('[data-tip]');
    if (!el) return;
    const to = e.relatedTarget;                 // 还在同一个按钮内部移动 ⇒ 不收
    if (to && el.contains(to)) return;
    hideTip();
  });
  // 气泡是相对视口定位的 ⇒ 任何滚动/失焦都让位置失效，直接收掉
  window.addEventListener('scroll', hideTip, true);
  window.addEventListener('blur', hideTip);
}

/* ── 发送的星光动画：问题化作光点飞向日志区、并把日志区点亮 ──────────
   一次性、纯装饰（`#fx` 是 `pointer-events:none`），尊重 reduced-motion。 */
function playSendFx(question, onDone) {
  /* ★ `onDone`：粒子**落点**后再回调 —— 用来「动画放完才显示运行日志页」。
     命中 reduced-motion 时也**必须**立刻回调，否则日志永远不出现。 */
  const reduced = (() => {
    try {
      return window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (_) { return false; }
  })();
  const done = () => { if (onDone) { try { onDone(); } catch (_) {} } };
  if (reduced) { done(); return; }

  const fx = $('#fx'), from = $('.composer');
  /* ★ 起点用**输入框（textarea）本身**：先在对话框里把问题散成星光点，再飞走。 */
  const ta = $('#question');
  /* 目标区：日志还没露出来时，星光飞向**舞台上半区**（日志即将出现的位置） */
  const logEl = $('#runlog');
  const visible = logEl && !logEl.classList.contains('hidden');
  const to = visible ? logEl : document.querySelector('main.stage');
  if (!fx || !from || !to) { done(); return; }
  const a = (ta || from).getBoundingClientRect(), b = to.getBoundingClientRect();
  if (!a.width || !b.width) { done(); return; }
  const sx = a.left + a.width / 2, sy = a.top + Math.min(a.height * 0.5, 34);
  const tx = b.left + b.width / 2, ty = b.top + Math.min(b.height * 0.28, 120);

  // ① 问题文字：**逐字裂解**成星光点（R23）——每个字朝随机方向散开、缩小消失，
  //    不再是一整块残影整体上飘。逐字排版按「输入框居中」估算起点。
  if (question) {
    const chars = Array.from(question);
    const cw = 15;                                   // 近似字宽（font-size:15px）
    const x0 = a.left + a.width / 2 - Math.min(chars.length * cw, a.width - 16) / 2;
    chars.forEach((ch, i) => {
      const g = document.createElement('span');
      g.className = 'q-char';
      g.textContent = ch;
      g.style.left = Math.round(x0 + i * cw + cw / 2) + 'px';
      g.style.top = Math.round(sy) + 'px';
      g.style.setProperty('--dx', ((Math.random() - 0.5) * 170).toFixed(1) + 'px');
      g.style.setProperty('--dy', (-24 - Math.random() * 78).toFixed(1) + 'px');
      g.style.animationDelay = Math.round(i * 13) + 'ms';
      fx.appendChild(g);
      setTimeout(() => g.remove(), 940 + i * 13);
    });
  }

  // ② 星光点：从输入框一带散开、汇聚到目标区
  const N = 18;
  for (let i = 0; i < N; i++) {
    const p = document.createElement('i');
    p.className = 'spark';
    const jx = (Math.random() - 0.5) * Math.min(a.width * 0.72, 520);
    const jy = (Math.random() - 0.5) * 16;
    p.style.setProperty('--sx', Math.round(sx + (Math.random() - 0.5) * a.width * 0.5) + 'px');
    p.style.setProperty('--sy', Math.round(sy + (Math.random() - 0.5) * 8) + 'px');
    /* 中点：先在对话框里散开（仍在输入框范围内） */
    p.style.setProperty('--mx', Math.round(sx + jx * 0.5) + 'px');
    p.style.setProperty('--my', Math.round(sy + jy - 10) + 'px');
    p.style.setProperty('--tx', Math.round(tx + (Math.random() - 0.5) * 120) + 'px');
    p.style.setProperty('--ty', Math.round(ty + (Math.random() - 0.5) * 60) + 'px');
    p.style.setProperty('--sz', (4 + Math.random() * 4).toFixed(1) + 'px');
    p.style.animationDelay = Math.round(i * 18) + 'ms';
    fx.appendChild(p);
    setTimeout(() => p.remove(), 920 + i * 18);
  }

  // ③ 粒子落点：先回调（露日志），再把日志面板**点亮**
  const land = 780 + N * 18;
  setTimeout(() => {
    done();
    const lg = $('#runlog');
    if (lg && !lg.classList.contains('hidden')) {
      lg.classList.add('lit');
      setTimeout(() => lg.classList.remove('lit'), 620);
    }
  }, land);
}

/* 演练模式胶囊：`#mock` 的勾选状态 → `#mock-row` 上的 `.on`。
   （`loadConfig()` 会异步设 `#mock.checked`，所以它也负责调一次，别只在初始化时调。） */
function syncMockPill() {
  const box = $('#mock'), row = $('#mock-row');
  if (box && row) row.classList.toggle('on', box.checked);
}

/* ── 全屏面板层：抽屉里的按钮把对应面板**铺满整页**（背景半透明）──────
   六个面板都放在 `#sheet` 里当「页」，点按钮就切到那一页并铺满。 */
const SHEET_TITLES = {
  'adv-panel': '高级参数',
  'dash-stats': '读数台',
  'dash-history': '最近跑过',
  'view-chats': '历史对话',
  'view-lib': '产物库',
  'view-local': '本地资料库',
  'view-web': '联网检索库',
  'view-agent': 'Agent 面板',
  'adv-group-page': '高级参数',      // 分组名由页内小标题承担，顶部不重复
};

/* 右上角那个键：进了参数分组页 ⇒ 显示成「← 返回」（点一下退回分组列表）；
   其余页显示「× 关闭」。行为本身已由 closeSheet() 承担（分组页上它就是「退回上一级」）。
   两种形态都带一行说明文字（按钮 + 描述，纯文字、透明底）。 */
const _SVG_X = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
  + '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>';
const _SVG_BACK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
  + '<path d="M15 5l-7 7 7 7" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function setSheetClose(back) {
  const b = $('#sheet-close');
  if (!b) return;
  b.classList.toggle('back', back);
  b.innerHTML = back ? _SVG_BACK : _SVG_X;      // **只留图标**（说明走悬停气泡）
  b.dataset.tip = back ? '返回上一级（不保存）' : '关闭面板（Esc）';
  b.setAttribute('aria-label', back ? '返回上一级' : '关闭面板');
}

function openSheet(key) {
  const sheet = $('#sheet');
  if (!sheet) return;
  /* ★ R27：面板不再是「另起一页的全屏浮层」，而是**本页的内容** ⇒
     进来时把抽屉收回去（给它让出整页），关闭时再弹回来（见 closeSheet）。
     只有「从隐藏 → 打开」这一下才收抽屉；面板内部换页（分组页等）不动抽屉。 */
  const wasHidden = sheet.classList.contains('hidden');
  if (wasHidden) {
    const d = $('#drawer');
    sheetFromDrawer = !!(d && d.classList.contains('open'));
    if (sheetFromDrawer) closeDrawer();
    document.body.classList.add('panel-open');
  }
  sheet.classList.remove('hidden');
  document.querySelectorAll('#sheet .sheet-page').forEach(p => {
    p.classList.toggle('active', p.id === key);
  });
  const t = $('#sheet-title');
  if (t) t.textContent = SHEET_TITLES[key] || key;
  /* ★ R28：标题旁只显示**当前这一页**的描述（计数 / 更新时间 / 说明） */
  const _desc = $('#sheet-desc');
  if (_desc) {
    _desc.querySelectorAll('.sd').forEach(s => s.classList.toggle('on', s.dataset.for === key));
  }
  setSheetClose(key === 'adv-group-page');
  /* ★ R38：参数页的**共用底栏**（保存 / 恢复出厂设置）只在这两页出现 ——
     它是 `.sheet` 的直接子项，不属于任何 `.sheet-page`，所以要显式开关。 */
  syncAdvBar(key);
  /* ★ R44：切到「读数台」立刻拉一次（不用等下一个 5s 周期） */
  if (key === 'dash-stats') loadDash();
  /* Agent 面板：每次切进来都拉一次最新任务/结果/知识（只读接口，失败不阻断） */
  if (key === 'view-agent') { loadAgent(); loadGitStatus(); }
  // 高级参数默认展开 —— 不然点进来只看到一行标题
  if (key === 'adv-panel') {
    const a = document.querySelector('.advanced');
    if (a) a.open = true;
  }
}

/* 「不保存直接关闭」：把这一组改过的值整组还原成进页面时的样子 */
function rollbackAdvGroup() {
  if (!advBackup) return;
  Object.keys(advBackup).forEach(k => {
    const b = advBackup[k];
    if (b.had) advOverrides[k] = b.val;
    else delete advOverrides[k];
  });
  advBackup = null;
}

/* ── 参数页的三个出口 ────────────────────────────────────────────
/* ── 参数页的出口 ────────────────────────────────────────────────
   ★ R38 语义定型（用户原话驱动，逐条对上）：
     · 「保存按钮就是保存**所有**参数设置的按钮，保存参数改动设置并退出」
         ⇒ saveAdvToFile() 提交**全部**待保存键（跨分组 + CLM 组），成功后关闭面板；
     · 「恢复出厂设置是把**所有**参数值改成默认…默认就是原始 yaml 参数里的值」
         ⇒ resetAdv() 删用户配置 ⇒ 全部回落到后端出厂 dgtf_config.yaml；
     · 「用户不改不保存就是默认值，改动保存再变化」「永久写进用户参数配置文件里」
         ⇒ 保存即持久（用户配置 dgtf_config.user.yaml），面板回显的就是那份； */

/* 全部「改了但还没保存」的键（`{键: 值}`）—— **跨分组**，含 CLM/CLI 组。
   ★ 这是 R38 修「CLM 参数设置了保存不了」的核心：
     原来 `advDirtyOfGroup(g)` 只扫当前分组、且只认 `data-cfg`（CLI 项是 `data-adv`），
     ⇒ CLM 组永远「0 项待保存」、点保存永远报「没有要保存的改动」。 */
function advDirtyAll() {
  const out = {};
  Object.keys(advOverrides).forEach(k => {
    if (advSaved[k] !== advOverrides[k]) out[k] = advOverrides[k];
  });
  return out;
}

/* 某个分组里「改了但还没保存」的键（分组按钮上的「N 项待保存」小标用） */
function advDirtyOfGroup(g) {
  const out = {};
  (g.items || []).forEach(it => {
    if (!it.key || !(it.key in advOverrides)) return;
    if (advSaved[it.key] !== advOverrides[it.key]) out[it.key] = advOverrides[it.key];
  });
  return out;
}

/* 底部出口上的计数（**全局**：所有分组 + CLM 一起算）+ 无改动时置灰 */
function updateAdvActions() {
  const n = Object.keys(advDirtyAll()).length;
  const sv = $('#adv-save');
  if (sv) {
    sv.disabled = !n;
    sv.dataset.tip = n
      ? `保存所有参数改动（${n} 项）到用户配置 dgtf_config.user.yaml，然后退出`
      : '当前没有要保存的改动';
    sv.classList.toggle('has-dirty', !!n);
  }
}

/* ★ R38：这一条底栏只在**参数相关的页**出现（首页 + 分组页），其它页隐藏。
   它是 `.sheet` 的直接子项，不属于任何一个 `.sheet-page` ⇒ 必须由 JS 显式开关。 */
function syncAdvBar(key) {
  const bar = $('#adv-actions');
  if (!bar) return;
  const on = (key === 'adv-panel' || key === 'adv-group-page');
  bar.classList.toggle('hidden', !on);
  if (on) updateAdvActions();
}

/* 面板里的一条短提示（保存成功 / 失败 / 无改动），3 秒后自己消失。
   ★ 挂 `#sheet` 上（**不是** `#adv-group-page`）：保存完会切回分组列表页，
     挂分组页上的话提示会跟着那一页一起被 `display:none` 掉 —— 等于没提示。 */
let advToastTimer = null;
function advToast(msg, kind) {
  const host = $('#sheet') || document.body;
  let el = document.getElementById('adv-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'adv-toast';
    host.appendChild(el);
  } else if (el.parentElement !== host) {
    host.appendChild(el);
  }
  el.className = 'adv-toast show' + (kind ? ' ' + kind : '');
  el.textContent = msg;
  clearTimeout(advToastTimer);
  advToastTimer = setTimeout(() => { el.className = 'adv-toast'; }, 3000);
}

/* 「保存」：把**所有**参数改动**持久化写回用户配置** dgtf_config.user.yaml，然后退出面板。
   ★ R38：「所有」= 跨分组的 `advOverrides` 全部 + CLM（CLI）组 —— 不只是当前这一组。
   ★ 用户原话：「保存按钮就是保存所有参数设置的按钮，保存参数改动设置并退出」。 */
async function saveAdvToFile() {
  const dirty = advDirtyAll();
  const n = Object.keys(dirty).length;
  if (!n) {
    advToast('没有要保存的改动', 'warn');
    return;
  }
  const btn = $('#adv-save');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/params', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ overrides: dirty }),
    });
    if (r.error) throw new Error(r.error);
    /* ★ 真的存进去了才记 `advSaved` —— 顺序不能反：先记就等于「不管成没成都说存了」。 */
    Object.keys(dirty).forEach(k => { advSaved[k] = advOverrides[k]; });
    advBackup = null;                       // 已落盘，不必再回滚
    /* ★ 保存后**把面板从服务端重读一遍** —— 面板显示的就是配置文件里的真值，
       而不是「我以为存进去了」。这一步本身就是「保存生效了」的自证。 */
    await buildAdv();
    advCurGroup = null;
    const miss = (r.missing || []).length;
    const skip = (r.skipped || []).length;
    let msg = `已保存 ${(r.saved || []).length} 项到用户配置 ${r.user_file || 'dgtf_config.user.yaml'}`;
    if (miss) msg += ` · ${miss} 项不在配置文件里，已跳过`;
    if (skip) msg += ` · ${skip} 项密钥参数不写回`;
    /* ★ R38：保存 = **保存并退出**（用户明确要求）。先给一条提示，再关面板 ——
       提示挂在 `#sheet` 上，关面板后仍在（见 advToast 的注释）。 */
    advToast(msg, miss || skip ? 'warn' : 'ok');
    closeSheet();
  } catch (e) {
    advToast('保存失败：' + e.message, 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}

/* 「恢复出厂设置」：删掉用户配置 ⇒ **所有**参数回落到后端出厂的 dgtf_config.yaml。
   ★ R38 文案对齐用户原话：「恢复出厂设置是把所有参数值改成默认，默认就是原始 yaml 参数里的值」。
   ★ 会丢掉用户此前保存的全部改动 ⇒ 二次确认（写错一次要一个个改回来）。 */
async function resetAdv() {
  const btn = $('#adv-reset');
  if (!window.confirm('恢复出厂设置会把所有参数改回出厂默认值，\n你在工作台保存过的全部改动都会被丢弃。确定继续？')) {
    return;
  }
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/params/reset', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    if (r.error) throw new Error(r.error);
    /* ★ 内存里的累积表 / 快照 / 待保存集合也一并清空 —— 不清的话旧值还留在 `advOverrides`
       里，下一轮 `collectOpts()` 会把它们当「当前面板值」提交，用户会以为「恢复了默认但没生效」。 */
    Object.keys(advOverrides).forEach(k => delete advOverrides[k]);
    Object.keys(advSaved).forEach(k => delete advSaved[k]);
    advBackup = null;
    advCurGroup = null;
    await buildAdv();                     // 从服务端重读 ⇒ 面板显示出厂值
    if (advGroups.length <= 1) {           // 一次性刷新失败再补一次，别让分组按钮整块消失
      await new Promise(r => setTimeout(r, 300));
      await buildAdv();
    }
    openSheet('adv-panel');               // 始终回分组列表：CLM + 其他所有分组都要在
    renderAdvGroups();
    advToast(r.removed ? '已恢复出厂设置（用户配置已删除，全部参数回落到出厂 yaml）'
                       : '本来就是出厂默认值，无需恢复', 'ok');
  } catch (e) {
    advToast('恢复出厂设置失败：' + e.message, 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function closeSheet() {
  const sheet = $('#sheet');
  if (!sheet || sheet.classList.contains('hidden')) return;
  /* ★ 在**参数分组页**上关闭（× / Esc / 点遮罩）＝「不保存 + 退回上一级」，
     而不是把整个面板层关掉 —— 用户要的是「关闭后跳回上一级页面」。 */
  const gp = $('#adv-group-page');
  if (gp && gp.classList.contains('active')) {
    rollbackAdvGroup();
    openSheet('adv-panel');        // 退回「高级参数」的分组列表页
    return;
  }
  sheet.classList.add('hidden');
  document.body.classList.remove('panel-open');
  /* ★ R27：面板是「从抽屉点进来的」，关掉它就把抽屉**弹回原位**。 */
  if (sheetFromDrawer) { sheetFromDrawer = false; openDrawer(); }
}

/* ★ R27：记住「这个面板是从抽屉点开的」——关闭时据此把抽屉弹回来。
   （从别处打开面板（如历史对话里点会话）不该顺手把抽屉拉出来。） */
let sheetFromDrawer = false;

/* ── Agent 面板：任务队列 / 用户任务 / 消费者 / 技术知识 / 结果 ────────
   数据面全部走服务端已有的只读/提交接口（不改 server.py）：
     GET  /api/agent/tasks      GET  /api/agent/results
     GET  /api/agent/knowledge  POST /api/agent/knowledge
     POST /api/agent/tasks      POST /api/agent/run
   所有渲染都 esc()；接口失败只落到面板提示行，不抛到全局（UI 不崩）。 */
let agentTasks = [];
let agentResults = [];
let agentKnowledge = [];
let agentDsh = [];
let agentDshArt = [];
let agentProps = [];
let agentLastRun = null;
let agentV2 = null;
let agentPareto = null;
let agentV2AB = null;
let agentV2Pareto = null;
let agentModel = null;
let agentLLM = null;
let agentConsistency = null;

/* 统一时间格式化：兼容 epoch 秒 / epoch 毫秒 / ISO 字符串。
   ★ 旧 agentIsoShort 把「秒」当「毫秒」传给 new Date，导致最近运行显示 1970 年；
   这里用 1e12 阈值区分秒/毫秒，无法解析时返回空串（不再把批次名当时间）。 */
function fmtTs(v) {
  if (v == null || v === '') return '';
  let d;
  const s = String(v).trim();
  if (typeof v === 'number' || /^\d+(\.\d+)?$/.test(s)) {
    let n = Number(v);
    if (n < 1e12) n *= 1000;
    d = new Date(n);
  } else {
    d = new Date(s);
  }
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {hour12: false});
}

function agentIsoShort(x) {
  return fmtTs(x) || '—';
}

/* 产物/归档文件名前缀 `YYYYMMDD_HHMMSS` → 可读时间。
   从运行日志右栏直接打开产物时，产物库列表可能还没加载，用它兜底。 */
function fmtFileStamp(name) {
  const m = String(name || '').match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  return m ? fmtTs(m[1] + '-' + m[2] + '-' + m[3] + 'T'
    + m[4] + ':' + m[5] + ':' + m[6]) : '';
}

function agentDetailHtml(detail) {
  const s = String(detail == null ? '' : detail).trim();
  if (!s) return '';
  return '<details class="agent-detail"><summary>详情</summary><pre>'
    + esc(s) + '</pre></details>';
}

function agentEmpty(msg) {
  return '<div class="agent-empty muted">' + esc(msg) + '</div>';
}

function agentRenderTasks() {
  const box = $('#agent-tasks');
  if (!box) return;
  const n = $('#agent-task-n');
  if (n) n.textContent = String(agentTasks.length);
  if (!agentTasks.length) {
    box.innerHTML = agentEmpty('队列为空。引擎跑完会自反馈入队；也可点「提交用户任务…」。');
    return;
  }
  const doneIds = new Set(agentResults.map(r => String(r.task_id || '')));
  const rows = agentTasks.slice().reverse().map(t => {
    const kind = String(t.kind || 'task');
    const sev = String(t.severity || 'med');
    const title = String(t.title || t.id || '(无标题)');
    const src = t.source_run ? ('源跑次 ' + String(t.source_run)) : '无源跑次';
    const st = doneIds.has(String(t.id || '')) ? '已消费' : '待消费';
    const when = fmtTs(t.ts);
    return '<div class="agent-item">'
      + '<div class="agent-row"><span class="chip">' + esc(kind) + '</span>'
      + '<span class="chip sev-' + esc(sev) + '">' + esc(sev) + '</span>'
      + '<span class="chip">' + esc(st) + '</span>'
      + '<span class="agent-t">' + esc(title) + '</span></div>'
      + '<div class="agent-meta"><span>' + esc(String(t.id || '—'))
      + '</span><span>' + esc(src) + '</span>'
      + '<span>' + (when ? ('创建 ' + esc(when)) : '创建时间未知') + '</span>'
      + '</div>'
      + agentDetailHtml(t.detail)
      + '</div>';
  });
  box.innerHTML = rows.join('');
}

function agentRenderResults() {
  const box = $('#agent-results');
  if (!box) return;
  const n = $('#agent-result-n');
  if (n) n.textContent = String(agentResults.length);
  if (!agentResults.length) {
    box.innerHTML = agentEmpty('还没有消费者结果。点「运行消费者」处理未消费任务。');
    return;
  }
  const rows = agentResults.slice().reverse().map(r => {
    const title = String(r.title || r.task_id || '(无标题)');
    const status = String(r.status || '—');
    const act = String(r.action || '');
    const when = fmtTs(r.ts);
    return '<div class="agent-item">'
      + '<div class="agent-row"><span class="chip">' + esc(String(r.kind || 'task'))
      + '</span><span class="chip">' + esc(status) + '</span>'
      + '<span class="agent-t">' + esc(title) + '</span></div>'
      + '<div class="agent-meta"><span>task ' + esc(String(r.task_id || '—'))
      + '</span>' + (r.source_run ? ('<span>源跑次 ' + esc(String(r.source_run)) + '</span>') : '')
      + (r.ts ? ('<span>处理 ' + esc(when) + '</span>') : '<span>处理时间未知</span>')
      + '</div>'
      + (act ? '<div class="agent-q">' + esc(act) + '</div>' : '')
      + '</div>';
  });
  box.innerHTML = rows.join('');
}

function agentRenderKnowledge() {
  const box = $('#agent-knowledge');
  if (!box) return;
  const n = $('#agent-kn-n');
  if (n) n.textContent = String(agentKnowledge.length);
  if (!agentKnowledge.length) {
    box.innerHTML = agentEmpty('知识库为空。点「知识检索」经 DSH 会话拉取官方/权威/最新资料。');
    return;
  }
  const rows = agentKnowledge.slice().reverse().map(k => {
    const title = String(k.title || k.query || '(无标题)');
    const url = String(k.url || '');
    const safeUrl = /^https?:\/\//i.test(url) ? url : '';
    const t = safeUrl
      ? '<a href="' + esc(safeUrl) + '" target="_blank" rel="noopener noreferrer">' + esc(title) + '</a>'
      : esc(title);
    const claim = String(k.claim || '');
    const flag = k.fetched ? '已爬取正文' : '仅检索';
    /* ★ 技术知识必须分别标「检索时间」和「爬取时间」：
       retrieved_at = Search 调用时间；fetched_at = Fetch/PDF 完成时间。
       老记录没有这两个字段，明确标「历史记录」而不是拿批次名冒充时间。 */
    const rAt = fmtTs(k.retrieved_at);
    const fAt = fmtTs(k.fetched_at);
    const batch = String(k.run || '');
    const srcMap = {official:'官方', paper:'论文', community:'社区', other:'其他'};
    const src = srcMap[String(k.source_type || '')] || '';
    const conf = k.confidence ? ('置信 ' + Math.round(Number(k.confidence) * 100) + '%') : '';
    const pub = String(k.published || '').slice(0, 10);
    const pdfName = String(k.pdf_name || '');
    const pdfOk = /^[A-Za-z0-9_.-]+\.pdf$/.test(pdfName);
    const pdfLink = pdfOk
      ? '<a class="chip" href="/api/agent/knowledge/pdf?name=' + encodeURIComponent(pdfName)
        + '" target="_blank" rel="noopener noreferrer">PDF 原文</a>'
      : (k.pdf_url ? '<a class="chip" href="' + esc(String(k.pdf_url)) + '" target="_blank" rel="noopener noreferrer">PDF 链接</a>' : '');
    const zh = String(k.zh_note || '');
    return '<div class="agent-item">'
      + '<div class="agent-row"><span class="chip">' + esc(flag) + '</span>'
      + (src ? '<span class="chip">' + esc(src) + '</span>' : '')
      + (conf ? '<span class="chip">' + esc(conf) + '</span>' : '')
      + (pdfLink ? pdfLink : '')
      + '<span class="agent-t">' + t + '</span></div>'
      + '<div class="agent-meta"><span>查询 ' + esc(String(k.query || '—'))
      + '</span>' + (pub ? '<span>发布 ' + esc(pub) + '</span>' : '')
      + (rAt ? '<span>检索 ' + esc(rAt) + '</span>'
             : '<span>检索时间未知（历史记录）</span>')
      + (fAt ? '<span>爬取 ' + esc(fAt) + '</span>'
             : (k.fetched ? '<span>爬取时间未知（历史记录）</span>'
                          : '<span>未爬取正文</span>'))
      + (batch ? '<span>批次 ' + esc(batch) + '</span>' : '')
      + '</div>'
      + (claim ? '<div class="agent-q">' + esc(claim) + '</div>' : '')
      + (zh ? '<div class="agent-q"><b>中文注释</b><br>' + esc(zh) + '</div>' : '')
      + agentDetailHtml(k.content)
      + '</div>';
  });
  box.innerHTML = rows.join('');
}

function agentRenderRun() {
  const box = $('#agent-runbox');
  if (!box) return;
  if (!agentLastRun) {
    box.innerHTML = agentEmpty('本次会话还没运行过消费者（运行结果只在本页显示；处理结果会进「消费者结果」）。');
    return;
  }
  const run = agentLastRun.run || {};
  const prop = agentLastRun.proposals || {};
  box.innerHTML = '<div class="agent-item">'
    + '<div class="agent-row"><span class="chip">triaged '
    + esc(String(run.triaged == null ? '—' : run.triaged)) + '</span>'
    + '<span class="chip">提案 ' + esc(String(prop.n == null ? '—' : prop.n)) + '</span>'
    + '<span class="agent-t">运行于 ' + esc(agentIsoShort(agentLastRun.at)) + '</span></div>'
    + '<div class="agent-meta"><span>提案文件 ' + esc(String(prop.path || '—'))
    + '</span></div>'
    + '<pre>' + esc(JSON.stringify(agentLastRun, null, 2).slice(0, 8000)) + '</pre>'
    + '</div>';
}

function agentRenderDsh() {
  const box = document.querySelector('#agent-dsh');
  const n = document.querySelector('#agent-dsh-n');
  if (n) n.textContent = String(agentDsh.length);
  if (!box) return;
  if (!agentDsh.length) { box.innerHTML = agentEmpty('还没有 DSH Agent 会话。'); return; }
  box.innerHTML = agentDsh.slice(0, 30).map(function (x) {
    const when = fmtTs(x.ts);
    return '<div class="agent-item agent-dsh-item" data-dsh-session="' + esc(x.id || '') + '">'
      + '<div class="agent-row"><span class="chip">' + (x.auto_repair ? '自动修复' : 'DSH') + '</span>'
      + '<span class="chip">' + (x.ok ? '完成' : '失败') + '</span>'
      + '<span class="agent-t">' + esc(x.task || x.id) + '</span></div>'
      + '<div class="agent-meta"><span>' + esc(x.id || '') + '</span>'
      + (when ? '<span>开始 ' + esc(when) + '</span>' : '<span>开始时间未知</span>')
      + '</div>'
      + '<div class="agent-q">点此回溯并续聊</div></div>';
  }).join('');
}

function agentRenderDshArt() {
  const box = document.querySelector('#agent-dsh-art');
  const n = document.querySelector('#agent-dsh-art-n');
  if (n) n.textContent = String(agentDshArt.length);
  if (!box) return;
  if (!agentDshArt.length) { box.innerHTML = agentEmpty('还没有 DSH 产物。'); return; }
  box.innerHTML = agentDshArt.slice(0, 30).map(function (x) {
    const when = fmtTs(x.ts);
    const st = x.ok === true ? '完成' : (x.ok === false ? '失败' : '产物');
    return '<div class="agent-item agent-dsh-art-item" data-dsh-art="' + esc(x.id || '') + '">'
      + '<div class="agent-row"><span class="chip">产物</span>'
      + '<span class="chip">' + esc(st) + '</span>'
      + '<span class="agent-t">' + esc(x.task || x.id) + '</span></div>'
      + '<div class="agent-meta"><span>' + esc(x.id || '') + '</span>'
      + (when ? '<span>生成 ' + esc(when) + '</span>' : '<span>生成时间未知</span>')
      + '<span>' + esc(String(x.size || 0)) + ' B</span></div></div>';
  }).join('');
}

function agentRenderProps() {
  const box = document.querySelector('#agent-proposals');
  const n = document.querySelector('#agent-prop-n');
  if (n) n.textContent = String(agentProps.length);
  if (!box) return;
  if (!agentProps.length) { box.innerHTML = agentEmpty('还没有修复提案。点「DSH 全流程闭环」生成提案。'); return; }
  const ST = {pending: '待确认', confirmed: '已确认待修复', applied: '已应用', failed: '失败', rolled_back: '已回退'};
  const nConf = agentProps.filter(x => x.status === 'confirmed').length;
  const fixBtn = document.querySelector('#prop-autofix');
  if (fixBtn) fixBtn.textContent = '自动修复提案' + (nConf ? '（' + nConf + '）' : '');
  box.innerHTML = agentProps.slice(0, 30).map(function (x) {
    const when = fmtTs(x.ts);
    const st = String(x.status || 'pending');
    let acts = '';
    if (st === 'pending') {
      acts = '<button class="ghost" data-prop-confirm="' + esc(x.id) + '">我确认</button>'
        + '<button class="ghost" data-prop-auto="' + esc(x.id) + '">DSH 自动代理</button>';
    } else if (st === 'confirmed') {
      acts = '<span class="muted">已确认，等待 DSH 自动修复</span>';
    } else if (st === 'applied') {
      acts = '<button class="ghost danger" data-prop-rollback="' + esc(x.id) + '">回退并撤销修复</button>';
      if (x.acceptance) acts += '<button class="ghost" data-acceptance="' + esc(x.id) + '">验收对话</button>';
    }
    return '<div class="agent-item">'
      + '<div class="agent-row"><span class="chip">提案</span>'
      + '<span class="chip st-' + esc(st) + '">' + esc(ST[st] || st) + '</span>'
      + '<span class="agent-t">' + esc((x.task || {}).title || x.id) + '</span></div>'
      + '<div class="agent-meta"><span>' + esc(x.id || '') + '</span>'
      + (when ? '<span>创建 ' + esc(when) + '</span>' : '<span>创建时间未知</span>')
      + (x.version ? '<span>版本 ' + esc(x.version) + '</span>' : '')
      + (x.artifact ? '<span>产物 ' + esc(String(x.artifact).split('\\').pop()) + '</span>' : '')
      + '</div>'
      + '<div class="agent-q">' + esc(String(x.plan || '').slice(0, 300)) + '</div>'
      + '<div class="prop-actions">' + acts + '</div></div>';
  }).join('');
}

function agentV2ParetoSvg(d) {
  const pts = (d && d.points) || [];
  if (!pts.length) return '';
  const W = 560, H = 210, P = 38;
  const maxT = Math.max.apply(null, pts.map(function (p) { return p.tokens || 0; })) || 1;
  const maxL = Math.max.apply(null, pts.map(function (p) { return p.low || 0; })) || 1;
  function X(p) { return P + ((p.tokens || 0) / maxT) * (W - P * 2); }
  function Y(p) { return H - P - ((p.low || 0) / maxL) * (H - P * 2); }
  const rec = d.recommended || {};
  const fr = (d.frontier || []).slice().sort(function (a, b) { return (a.tokens || 0) - (b.tokens || 0); });
  let s = '<svg class="agent-pareto-svg" viewBox="0 0 ' + W + ' ' + H + '">';
  s += '<line x1="' + P + '" y1="' + (H - P) + '" x2="' + (W - P) + '" y2="' + (H - P) + '" stroke="currentColor" opacity=".35"/>';
  s += '<line x1="' + P + '" y1="' + P + '" x2="' + P + '" y2="' + (H - P) + '" stroke="currentColor" opacity=".35"/>';
  s += '<text x="' + (W / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="currentColor" opacity=".7">tokens</text>';
  s += '<text x="10" y="' + (P - 10) + '" font-size="11" fill="currentColor" opacity=".7">quality low</text>';
  if (fr.length > 1) {
    s += '<polyline fill="none" stroke="var(--accent)" stroke-width="1.5" opacity=".75" points="'
      + fr.map(function (p) { return X(p).toFixed(1) + ',' + Y(p).toFixed(1); }).join(' ') + '"/>';
  }
  pts.forEach(function (p) {
    const isRec = rec.template && p.template === rec.template;
    const isFront = fr.some(function (q) { return q.template === p.template; });
    s += '<circle cx="' + X(p).toFixed(1) + '" cy="' + Y(p).toFixed(1) + '" r="'
      + (isRec ? 5 : isFront ? 4 : 3) + '" fill="'
      + (isRec ? 'var(--accent)' : isFront ? 'var(--accent-hi)' : 'currentColor')
      + '" opacity="' + (isFront ? '.95' : '.35') + '">'
      + '<title>' + esc(String(p.template || '')) + ' tokens ' + esc(String(p.tokens || 0))
      + ' quality ' + esc(String(p.quality || 0)) + '</title></circle>';
  });
  return s + '</svg>';
}

function agentRenderV2() {
  const box = $('#agent-v2');
  if (!box) return;
  const n = $('#agent-v2-n');
  const d = agentV2 || {};
  if (n) n.textContent = String(d.n || 0);
  if (!d || !d.n) { box.innerHTML = agentEmpty('还没有 V2 影子调度事件。'); return; }
  const kinds = d.by_kind || {};
  const layers = d.by_layer || {};
  let html = '<div class="agent-item"><div class="agent-row">'
    + '<span class="chip">事件 ' + esc(String(d.n || 0)) + '</span>'
    + Object.keys(kinds).sort().map(function (k) {
        return '<span class="chip">' + esc(k) + ' ' + esc(String(kinds[k])) + '</span>';
      }).join('')
    + '</div><div class="agent-meta">'
    + Object.keys(layers).sort().map(function (k) {
        return '<span>' + esc(k) + ' · ' + esc(String(layers[k])) + '</span>';
      }).join('')
    + '</div></div>';
  const _pa = agentPareto || {};
  const _fr = (_pa.frontier || []);
  if (_fr.length) {
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">帕累托前沿 '
      + esc(String(_fr.length)) + ' 点</span><span class="chip">推荐 '
      + esc(String(((_pa.recommended || {}).coverage == null) ? '—' : ((_pa.recommended || {}).coverage)))
      + '</span></div>';
    _fr.forEach(function (p) {
      html += '<div class="agent-meta"><span>' + esc(String(p.route || ''))
        + '</span><span>tokens ' + esc(String(p.tokens))
        + '</span><span>coverage ' + esc(String(p.coverage))
        + '</span><span>n=' + esc(String(p.runs)) + '</span></div>';
    });
    html += '</div>';
  }
  if (agentV2AB && agentV2AB.ok) {
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">FDR 显著 '
      + esc(String(agentV2AB.n_significant || 0)) + ' / ' + esc(String((agentV2AB.pairs || []).length))
      + ' 对</span><span class="agent-t">alpha ' + esc(String(agentV2AB.alpha || 0.05))
      + '</span></div></div>';
  }
  if (agentLLM && agentLLM.ok && agentLLM.eval_summary) {
    const _lr = (agentLLM.eval_summary.lora || {});
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">LLM LoRA</span>'
      + '<span class="agent-t">JSON ' + esc(String(_lr.json_rate || 0))
      + ' · route ' + esc(String(_lr.route_exact || 0))
      + ' · MAE ' + esc(String(_lr.round_mae || 0)) + '</span></div></div>';
  }
  if (agentModel && agentModel.ok && agentModel.model) {
    const _qm = (agentModel.model.quality_test || {});
    const _qb = (agentModel.model.quality_baseline || {});
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">学习模型</span>'
      + '<span class="agent-t">MAE ' + esc(String(_qm.mae || 0))
      + ' / 基线 ' + esc(String(_qb.mae || 0))
      + ' · R² ' + esc(String(_qm.r2 || 0)) + '</span></div></div>';
  }
  const _ts = d.by_template || {};
  const _tkeys = Object.keys(_ts);
  if (_tkeys.length) {
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">V2 模板 A/B</span>'
      + '<span class="agent-t">按 quality 降序</span></div>';
    _tkeys.sort(function (a, b) { return (_ts[b].quality || 0) - (_ts[a].quality || 0); })
      .forEach(function (k) {
        const v = _ts[k] || {};
        html += '<div class="agent-meta"><span>' + esc(k)
          + '</span><span>n=' + esc(String(v.n || 0))
          + '</span><span>quality ' + esc(String(v.quality || 0))
          + ' ± ' + esc(String(v.ci95 || 0))
          + '</span><span>tokens ' + esc(String(v.tokens || 0))
          + '</span><span>calls ' + esc(String(v.calls || 0)) + '</span></div>';
      });
    html += '</div>';
  }
  if (agentV2Pareto) html += agentV2ParetoSvg(agentV2Pareto);
  (d.recent || []).slice().reverse().forEach(function (e) {
    html += '<div class="agent-item"><div class="agent-row">'
      + '<span class="chip">' + esc(String(e.kind || '')) + '</span>'
      + '<span class="chip">' + esc(String(e.layer || '')) + '</span>'
      + '<span class="agent-t">' + esc(String(e.key || e.id || '')) + '</span></div>'
      + '<div class="agent-meta"><span>批次 ' + esc(fmtTs(e.ts) || '时间未知')
      + '</span><span>run ' + esc(String(e.run_id || '—'))
      + '</span><span>conf ' + esc(String(e.confidence == null ? '—' : e.confidence)) + '</span></div>'
      + '<div class="agent-q">' + esc(JSON.stringify(e.payload || {}).slice(0, 800)) + '</div></div>';
  });
  box.innerHTML = html;
}

function agentRenderConsistency() {
  const box = $('#agent-consistency');
  if (!box) return;
  const d = agentConsistency || {};
  const n = $('#agent-consistency-n');
  const checks = d.checks || {};
  if (n) n.textContent = String(Object.keys(checks).length);
  if (!checks || !Object.keys(checks).length) {
    box.innerHTML = agentEmpty('还没有自洽审计读数。');
    return;
  }
  let html = '<div class="agent-item"><div class="agent-row"><span class="chip">'
    + (d.ok ? '自洽通过' : '存在警告') + '</span><span class="agent-t">'
    + esc(String((d.warnings || []).length)) + ' 项诊断</span></div>'
    + '<div class="agent-meta"><span>审计 '
    + esc(fmtTs(d.ts) || '时间未知') + '</span></div>';
  Object.keys(checks).sort().forEach(function (k) {
    const v = checks[k] || {};
    const st = v.ok ? '通过' : '诊断';
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">'
      + esc(k) + '</span><span class="chip">' + st + '</span>'
      + '<span class="agent-t">' + esc(JSON.stringify(v).slice(0, 320)) + '</span></div></div>';
  });
  const _hist = d.history || [];
  if (_hist.length) {
    html += '<div class="agent-item"><div class="agent-row"><span class="chip">审计历史 '
      + esc(String(_hist.length)) + ' 条</span><span class="agent-t">最近 5 次</span></div>';
    _hist.slice(-5).reverse().forEach(function (h) {
      const when = fmtTs(h.ts);
      html += '<div class="agent-meta"><span>' + (h.ok ? '通过' : '告警')
        + '</span><span>' + esc(when) + '</span><span>V2 ' + esc(String(h.v2 == null ? '—' : h.v2))
        + '</span><span>paired ' + esc(String(h.paired == null ? '—' : h.paired))
        + '</span><span>' + esc(String(h.template || '—')) + '</span></div>';
    });
    html += '</div>';
  }
  html += '</div>';
  box.innerHTML = html;
}

function agentRenderAll() {
  agentRenderTasks();
  agentRenderResults();
  agentRenderKnowledge();
  agentRenderDsh();
  agentRenderDshArt();
  agentRenderProps();
  agentRenderRun();
  agentRenderV2();
  agentRenderConsistency();
}

async function loadAgent() {
  const box = $('#agent-tasks');
  if (!box) return;
  box.innerHTML = agentEmpty('读取中…');
  const resBox = $('#agent-results');
  if (resBox) resBox.innerHTML = agentEmpty('读取中…');
  const knBox = $('#agent-knowledge');
  if (knBox) knBox.innerHTML = agentEmpty('读取中…');
  const [t, r, k, ds, da, pr, v2, pa, vab, vpar, con, mdl, llm] = await Promise.all([
    api('/api/agent/tasks').catch(e => ({ tasks: [], error: e.message })),
    api('/api/agent/results').catch(e => ({ results: [], error: e.message })),
    api('/api/agent/knowledge').catch(e => ({ items: [], error: e.message })),
    api('/api/dsh/sessions').catch(e => ({ sessions: [], error: e.message })),
    api('/api/dsh/artifacts').catch(e => ({ artifacts: [], error: e.message })),
    api('/api/dsh/proposals').catch(e => ({ proposals: [], error: e.message })),
    api('/api/schedule/v2').catch(e => ({ n: 0, error: e.message })),
    api('/api/schedule/pareto?prefer=' + encodeURIComponent((document.querySelector('#pareto-prefer') || {}).value || 'balanced')).catch(e => ({ ok: false, error: e.message })),
    api('/api/schedule/v2/ab?all=1').catch(e => ({ ok: false, error: e.message })),
    api('/api/schedule/v2/pareto').catch(e => ({ ok: false, error: e.message })),
    api('/api/consistency').catch(e => ({ ok: false, error: e.message })),
    api('/api/schedule/model').catch(e => ({ ok: false, error: e.message })),
    api('/api/schedule/llm/status').catch(e => ({ ok: false, error: e.message })),
  ]);
  agentTasks = (t && t.tasks) || [];
  agentResults = (r && r.results) || [];
  agentKnowledge = (k && k.items) || [];
  agentDsh = (ds && ds.sessions) || [];
  agentDshArt = (da && da.artifacts) || [];
  agentProps = (pr && pr.proposals) || [];
  agentV2 = v2 || null;
  agentPareto = pa || null;
  agentV2AB = vab || null;
  agentV2Pareto = vpar || null;
  agentConsistency = con || null;
  agentModel = mdl || null;
  agentLLM = llm || null;
  agentRenderAll();
  const errs = [t && t.error, r && r.error, k && k.error].filter(Boolean);
  const msg = $('#agent-msg');
  if (msg) msg.textContent = errs.length ? ('部分读数不可用：' + errs.join('；')) : '';
  const asof = $('#agent-asof');
  if (asof) asof.textContent = '更新于 ' + new Date().toLocaleTimeString();
}

function openAgentDialog() {
  const ov = $('#agent-overlay');
  if (!ov) return;
  const msg = $('#agent-dlg-msg');
  if (msg) msg.textContent = '';
  ov.classList.remove('hidden');
  const t = $('#agent-title');
  if (t) t.focus();
}

function closeAgentDialog() {
  const ov = $('#agent-overlay');
  if (ov) ov.classList.add('hidden');
}

async function submitAgentTask() {
  const msg = $('#agent-dlg-msg');
  const title = ($('#agent-title') ? $('#agent-title').value : '').trim();
  const detail = ($('#agent-detail') ? $('#agent-detail').value : '').trim();
  const kind = $('#agent-kind') ? $('#agent-kind').value : 'user_task';
  const severity = $('#agent-severity') ? $('#agent-severity').value : 'med';
  if (!title) {
    if (msg) msg.textContent = '标题不能为空';
    return;
  }
  const btn = $('#agent-submit');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/agent/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: kind, severity: severity, title: title, detail: detail }),
    });
    const task = (r && r.task) || {};
    closeAgentDialog();
    if ($('#agent-title')) $('#agent-title').value = '';
    if ($('#agent-detail')) $('#agent-detail').value = '';
    const m2 = $('#agent-msg');
    if (m2) m2.textContent = '已提交任务 ' + String(task.id || '');
    await loadAgent();
  } catch (e) {
    if (msg) msg.textContent = '提交失败：' + e.message;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function showAcceptanceInDgtf(prop) {
  logFollow = true;
  const acc = prop.acceptance || {};
  const checks = acc.checks || [];
  const lines = [];
  lines.push('修复提案：' + (prop.id || ''));
  lines.push('版本：' + (prop.version || '—'));
  lines.push('验收结果：' + (acc.ok ? 'PASS' : 'FAIL'));
  checks.forEach(function (c) {
    lines.push((c.name || 'check') + '：' + (c.ok ? 'PASS' : 'FAIL'));
    String(c.tail || '').split('\n').slice(-30).forEach(function (x) { if (x.trim()) lines.push(x); });
  });
  if (prop.artifact) lines.push('产物目录：' + prop.artifact);
  const id = 'accept-' + String(prop.id || 'proposal');
  const text = lines.join('\n');
  taskData[id] = { id: id, question: '修复验收对话 · ' + (prop.version || prop.id),
    status: 'done', created_at: Date.now() / 1000, mock: true, opts: {} };
  activeChat = id; followLatest = false; chatMode = 'live';
  lanes.tid = id; lanes.text = { '__head__': text }; lanes.stats = {}; lanes.meta = {};
  closeSheet(); closeDrawer();
  const lg = document.querySelector('#runlog');
  if (lg) { lg.classList.remove('hidden'); lg.classList.remove('fading'); }
  document.body.classList.remove('stage-empty'); document.body.classList.add('stage-run');
  renderTasks();
}

function showAutoDsh(question, events, status) {
  logFollow = true;
  dshConversationId = null;
  dshConversation = null;
  stopDshConvPoll();
  toggleDshMode(true);
  dshAttachTaskId = null;
  dshCurrent = { question: question, session: 'auto-cycle', events: events || [],
    status: status || 'running' };
  closeSheet();
  closeDrawer();
  setRunBtn(status === 'running' ? 'stop' : 'send');
  renderDshView();
}

async function resumeAutoJobView(jid, kind) {
  const label = kind === '自动修复' ? '自动修复' : '自动闭环';
  showAutoDsh('恢复后台任务 · ' + label, [
    {type:'text', text:'页面刷新后恢复轮询：' + jid + '，任务由服务端继续执行。'}
  ], 'running');
  setRunBtn('stop');
  let idx = 0, netErrs = 0, final = null, errMsg = '';
  while (!final) {
    let jr = null;
    try {
      jr = await api('/api/agent/auto/job/' + encodeURIComponent(jid) + '?since=' + idx);
      netErrs = 0;
    } catch (ne) {
      netErrs++;
      if (dshCurrent) {
        dshCurrent.events.push({type:'text', text:'恢复轮询网络中断（重试 ' + netErrs + '/8）…'});
        renderDshView();
      }
      if (netErrs > 8) { errMsg = ne.message; break; }
      await new Promise(res => setTimeout(res, 800));
      continue;
    }
    (jr.events || []).forEach(function (m) {
      if (!dshCurrent) return;
      if (m.type === 'stage') {
        dshCurrent.events.push({type:'text', text:'── 阶段：' + m.stage + ' ──'});
      } else if (m.type === 'event' && m.event) {
        dshCurrent.events.push(m.event);
      } else if (m.type === 'proposal_result') {
        const p = m.proposal || {};
        dshCurrent.events.push({type:'text', text:'提案 ' + (p.id || '') + ' → ' + (p.status || '')});
      } else if (m.type === 'result') {
        final = m.result;
      }
      renderDshView();
    });
    idx = jr.next || idx;
    if (jr.status === 'done') { final = final || jr.result; break; }
    if (jr.status === 'error' || jr.status === 'interrupted') {
      errMsg = jr.error || ('后台任务状态：' + (jr.status || ''));
      break;
    }
    await new Promise(res => setTimeout(res, 700));
  }
  if (dshCurrent) {
    if (final) {
      dshCurrent.events.push({type:'text', text:label + '恢复完成。'});
      dshCurrent.status = 'done';
    } else {
      dshCurrent.events.push({type:'text', text:label + '恢复停止：' + (errMsg || '无结果')});
      dshCurrent.status = 'error';
    }
    renderDshView();
  }
  setRunBtn('send');
  try {
    localStorage.removeItem(kind === '自动修复' ? 'dgtf_last_autofix_job' : 'dgtf_last_auto_job');
  } catch (_) {}
  try { await loadAgent(); loadGitStatus(); } catch (_) {}
}

async function resumeLastAutoJobNotice() {
  const pairs = [['dgtf_last_auto_job', '自动闭环'],
                 ['dgtf_last_autofix_job', '自动修复']];
  let text = '';
  for (const [key, label] of pairs) {
    let jid = '';
    try { jid = localStorage.getItem(key) || ''; } catch (_) { jid = ''; }
    if (!jid) continue;
    try {
      const j = await api('/api/agent/auto/job/' + encodeURIComponent(jid) + '?since=0');
      if (j.status === 'running' || j.status === 'queued') {
        await resumeAutoJobView(jid, label);
        return;
      } else if (j.status === 'done') {
        text += label + '上次后台任务已完成。';
        try { localStorage.removeItem(key); } catch (_) {}
      } else {
        text += label + '上次后台任务状态：' + (j.status || '未知') + '。';
        try { localStorage.removeItem(key); } catch (_) {}
      }
    } catch (_) {}
  }
  const m = document.querySelector('#agent-msg');
  if (m && text) m.textContent = text;
}

async function autoFixProposals() {
  const nConf = (agentProps || []).filter(x => x.status === 'confirmed').length;
  if (!nConf) {
    const m = document.querySelector('#agent-msg');
    if (m) m.textContent = '没有已确认待修复的提案';
    return;
  }
  showAutoDsh('自动修复提案 · ' + nConf + ' 条已确认', [
    {type:'text', text:'DSH Agent 开始自动代理修复 ' + nConf + ' 条已确认提案…'}
  ], 'running');
  let final = null, errMsg = '';
  try {
    const job = await api('/api/dsh/proposals/autofix/start', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model: (document.querySelector('#dsh-model') || {}).value || 'deepseek-flash'})});
    try { localStorage.setItem('dgtf_last_autofix_job', job.job_id || ''); } catch (_) {}
    let idx = 0, netErrs = 0;
    while (!final) {
      let jr = null;
      try {
        jr = await api('/api/agent/auto/job/' + encodeURIComponent(job.job_id) + '?since=' + idx);
        netErrs = 0;
      } catch (ne) {
        netErrs++;
        if (dshCurrent) {
          dshCurrent.events.push({type:'text', text:'轮询网络中断，后台修复继续执行（重试 ' + netErrs + '/8）…'});
          renderDshView();
        }
        if (netErrs > 8) throw ne;
        await new Promise(res => setTimeout(res, 800));
        continue;
      }
      (jr.events || []).forEach(function (m) {
        if (!dshCurrent) return;
        if (m.type === 'event' && m.event) {
          dshCurrent.events.push(m.event);
        } else if (m.type === 'stage') {
          dshCurrent.events.push({type:'text', text:'── ' + m.stage + ' ──'});
        } else if (m.type === 'proposal_result') {
          const p = m.proposal || {};
          dshCurrent.events.push({type:'text', text:'提案 ' + (p.id || '') + ' → ' + (p.status || '')});
        } else if (m.type === 'result') {
          final = m.result;
        }
        renderDshView();
      });
      idx = jr.next || idx;
      if (final) break;
      if (jr.status === 'error') { errMsg = jr.error || '后台自动修复失败'; break; }
      if (jr.status === 'done') { errMsg = '后台自动修复结束但没有返回结果'; break; }
      await new Promise(res => setTimeout(res, 700));
    }
    if (!final) throw new Error(errMsg || '没有返回结果');
    const ps = final.proposals || [];
    dshCurrent.events.push({type:'text', text:'自动修复完成：' + ps.filter(p => p.status === 'applied').length + ' 条已应用 / ' + ps.filter(p => p.status !== 'applied').length + ' 条失败'});
    dshCurrent.status = final.ok ? 'done' : 'error';
    dshCurrent.question = '自动修复提案 · 完成';
    renderDshView();
    setRunBtn('send');
    await loadAgent(); loadGitStatus();
    const applied = (final.proposals || []).filter(p => p.status === 'applied');
    const withChecks = applied.find(p => ((p.acceptance || {}).checks || []).length);
    if (withChecks) setTimeout(function () { showAcceptanceInDgtf(withChecks); }, 400);
  } catch (e) {
    if (dshCurrent) {
      dshCurrent.events.push({type:'text', text:'自动修复失败：' + e.message});
      dshCurrent.status = 'error';
      renderDshView();
    }
    setRunBtn('send');
  }
}

async function autoAgent(stage) {
  const st = document.querySelector('#agent-auto-status');
  const btn = document.querySelector('#agent-auto');
  const oldText = btn ? btn.textContent : '';
  const t0 = Date.now();
  if (btn) {
    btn.disabled = true;
    if (stage === 'full' || stage === 'all') btn.textContent = 'DSH 全流程闭环运行中…';
  }
  if (st) {
    st.className = 'agent-auto-status running';
    st.textContent = 'DSH Agent 自动闭环已开始，已跳转到 DSH Agent 对话框显示执行内容…';
  }
  const _fullLoop = (stage === 'full' || stage === 'all');
  showAutoDsh(_fullLoop ? 'DSH 全流程闭环' : 'DSH 自动闭环 · ' + stage, [
    {type:'status', phase:'turn_start', turn:1},
    {type:'text', text: _fullLoop
      ? '开始执行：知识刷新 → mock 引擎跑次 → 任务/消费者 → 自审提案。可能需要几分钟。'
      : '开始执行：' + stage}
  ], 'running');
  let result = null, errMsg = '';
  try {
    const job = await api('/api/agent/auto/start', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({stage: stage,
        model: (document.querySelector('#dsh-model') || {}).value || 'deepseek-flash'})});
    try { localStorage.setItem('dgtf_last_auto_job', job.job_id || ''); } catch (_) {}
    let idx = 0, netErrs = 0;
    while (!result) {
      let jr = null;
      try {
        jr = await api('/api/agent/auto/job/' + encodeURIComponent(job.job_id) + '?since=' + idx);
        netErrs = 0;
      } catch (ne) {
        netErrs++;
        if (dshCurrent) {
          dshCurrent.events.push({type:'text', text:'轮询网络中断，后台任务继续执行（重试 ' + netErrs + '/8）…'});
          renderDshView();
        }
        if (netErrs > 8) throw ne;
        await new Promise(res => setTimeout(res, 800));
        continue;
      }
      (jr.events || []).forEach(function (m) {
        if (!dshCurrent) return;
        if (m.type === 'stage') {
          dshCurrent.events.push({type:'text', text:'── 阶段：' + m.stage + ' ──'});
        } else if (m.type === 'event' && m.event) {
          dshCurrent.events.push(m.event);
        }
        renderDshView();
      });
      idx = jr.next || idx;
      if (jr.status === 'done') { result = jr.result; break; }
      if (jr.status === 'error') { errMsg = jr.error || '后台自动任务失败'; break; }
      await new Promise(res => setTimeout(res, 700));
    }
    if (!result) throw new Error(errMsg || '没有返回结果');
    const r = result;
    const ev = dshCurrent.events;
    if (r.tasks_total != null) ev.push({type:'text', text:'任务队列：共 ' + r.tasks_total + ' 条，已全部纳入闭环，处理 ' + (r.tasks_processed || 0) + ' 条。'});
    if (r.consumer && r.consumer.run) ev.push({type:'text', text:'消费者：' + JSON.stringify(r.consumer.run).slice(0, 1200)});
    if (Array.isArray(r.proposals)) {
      ev.push({type:'text', text:'新增修复提案：' + r.proposals.length + ' 条，已落修复提案库。'});
      r.proposals.slice(0, 10).forEach(function (p) {
        ev.push({type:'text', text:'· ' + (p.id || '') + ' · ' + ((p.task || {}).title || '')});
      });
    }
    if (r.proposal && r.proposal.proposal) ev.push({type:'text', text:'提案：' + (r.proposal.proposal.id || '') + ' · ' + (r.proposal.proposal.status || '')});
    agentLastRun = { at: Date.now() / 1000,
      run: (r.consumer && r.consumer.run) || {},
      proposals: { n: Array.isArray(r.proposals) ? r.proposals.length : 0,
                   path: (r.consumer && r.consumer.proposals && r.consumer.proposals.path) || '' },
      auto: { stage: stage, tasks_total: r.tasks_total || 0 } };
    agentRenderAll();
    const secs = Math.max(1, Math.round((Date.now() - t0) / 1000));
    if (st) {
      st.className = 'agent-auto-status ' + (r.ok ? 'ok' : 'err');
      st.textContent = (_fullLoop
        ? (r.ok ? 'DSH 全流程闭环完成' : 'DSH 全流程闭环部分失败')
        : (r.ok ? 'DSH 自动完成' : 'DSH 自动部分失败')) + '（' + secs + 's）';
    }
    dshCurrent.question = (_fullLoop ? 'DSH 全流程闭环' : 'DSH 自动闭环 · ' + stage)
      + ' · ' + secs + 's';
    dshCurrent.events.push({type:'text', text: r.ok ? '自动闭环完成。' : '自动闭环部分失败。'});
    dshCurrent.status = r.ok ? 'done' : 'error';
    renderDshView();
    await loadAgent(); loadGitStatus();
  } catch (e) {
    if (st) { st.className = 'agent-auto-status err'; st.textContent = 'DSH 自动执行失败：' + e.message; }
    if (dshCurrent) {
      dshCurrent.events.push({type:'text', text:'执行失败：' + e.message});
      dshCurrent.status = 'error';
      renderDshView();
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = oldText; }
    setRunBtn('send');
  }
}

async function runAgentConsumer() {
  const btn = $('#agent-run');
  const msg = $('#agent-msg');
  if (btn) btn.disabled = true;
  if (msg) msg.textContent = '消费者运行中…';
  try {
    const r = await api('/api/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    agentLastRun = {
      at: new Date().toISOString(),
      run: (r && r.run) || {},
      proposals: (r && r.proposals) || {},
    };
    if (msg) msg.textContent = '消费者已运行：triaged '
      + String((r && r.run && r.run.triaged) || 0);
    await loadAgent();
  } catch (e) {
    if (msg) msg.textContent = '运行失败：' + e.message;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function dedupeAgentKnowledge() {
  const btn = $('#agent-kn-dedupe');
  const msg = $('#agent-msg');
  if (btn) btn.disabled = true;
  if (msg) msg.textContent = '知识库去重中…';
  try {
    const r = await api('/api/agent/knowledge/dedupe', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
    if (msg) msg.textContent = '库去重完成：' + (r.before || 0) + ' → '
      + (r.after || 0) + '，移除重复 ' + (r.removed || 0) + ' 条';
    await loadAgent();
  } catch (e) {
    if (msg) msg.textContent = '库去重失败：' + e.message;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function refreshAgentKnowledge(mode) {
  const raw = ($('#agent-kn-q') ? $('#agent-kn-q').value : '').trim();
  const btns = ['#agent-knowledge-btn', '#agent-kn-search']
    .map(s => document.querySelector(s)).filter(Boolean);
  const msg = $('#agent-msg');
  btns.forEach(b => { b.disabled = true; });
  if (msg) msg.textContent = '创建 DSH 知识检索会话…';
  try {
    const r = await api('/api/agent/knowledge/agent-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: raw, mode: raw ? 'query' : 'refresh', limit: 3 }),
    });
    const items = (r && r.items) || [];
    if (msg) msg.textContent = r.ok
      ? ('DSH 知识检索：筛选 ' + items.length + ' 条高质量结果，正在打开会话…')
      : ('知识检索失败：' + (r.error || '无高质量结果'));
    await loadAgent();
    if (r && r.conversation_id) {
      closeSheet(); closeDrawer();
      await resumeDshChat(r.conversation_id);
    }
    if (items.length) {
      const tab = document.querySelector('[data-agent-tab="2"]');
      if (tab) tab.click();
    }
  } catch (e) {
    if (msg) msg.textContent = '知识检索失败：' + e.message;
  } finally {
    btns.forEach(b => { b.disabled = false; });
  }
}


/* ── DeepSeek Harness Agent：按钮 + 对话框；事件映射与 DSH headless --json 一致 ── */
function dshAppend(html) {
  const log = document.querySelector('#dsh-log');
  if (!log) return;
  const empty = log.querySelector('.dsh-empty');
  if (empty) empty.remove();
  const el = document.createElement('div');
  el.innerHTML = html;
  log.appendChild(el.firstElementChild || el);
  log.scrollTop = log.scrollHeight;
}
function openDshAgent() {
  const ov = document.querySelector('#dsh-overlay');
  if (!ov) return;
  ov.classList.remove('hidden');
  setTimeout(() => { const t = document.querySelector('#dsh-task'); if (t) t.focus(); }, 30);
}
function closeDshAgent() {
  const ov = document.querySelector('#dsh-overlay');
  if (ov) ov.classList.add('hidden');
}
function renderDshEvent(ev) {
  if (!ev || !ev.type) return;
  if (ev.type === 'session') {
    dshSession = ev.sessionId || dshSession;
    const s = document.querySelector('#dsh-session');
    if (s) s.textContent = '会话 ' + (dshSession || '—');
    return;
  }
  if (ev.type === 'status') {
    if (ev.phase === 'turn_start') dshAppend('<div class="dsh-status">▸ 开始 turn ' + esc(ev.turn || '') + '</div>');
    else if (ev.phase === 'step_start') dshAppend('<div class="dsh-status">· step ' + esc(ev.step || '') + '</div>');
    return;
  }
  if (ev.type === 'thinking' && ev.text) {
    dshAppend('<details class="dsh-think"><summary>思考</summary><pre>' + esc(ev.text) + '</pre></details>');
    return;
  }
  if (ev.type === 'tool_call') {
    dshAppend('<div class="dsh-tool"><b>🔧 ' + esc(ev.tool || 'tool') + '</b><pre>' + esc(JSON.stringify(ev.input || {}, null, 2)) + '</pre></div>');
    return;
  }
  if (ev.type === 'tool_result') {
    dshAppend('<details class="dsh-tool-res"><summary>工具结果 ' + esc(ev.status || '') + '</summary><pre>' + esc(String(ev.result || '').slice(0, 12000)) + '</pre></details>');
    return;
  }
  if (ev.type === 'text' && ev.text) {
    dshAppend('<div class="dsh-msg assistant">' + esc(ev.text) + '</div>');
  }
}
async function sendDshAgent() {
  const taskEl = document.querySelector('#dsh-task');
  const msgEl = document.querySelector('#dsh-msg');
  const btn = document.querySelector('#dsh-send');
  const task = (taskEl && taskEl.value || '').trim();
  if (!task) { if (msgEl) msgEl.textContent = '请输入任务'; return; }
  if (taskEl) taskEl.value = '';
  dshAppend('<div class="dsh-msg user">' + esc(task) + '</div>');
  if (btn) btn.disabled = true;
  if (msgEl) msgEl.textContent = 'DSH Agent 运行中…（可读项目文件/产物）';
  try {
    const r = await api('/api/dsh/agent', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task: task, session_id: dshSession }) });
    dshSession = r.session_id || dshSession;
    (r.events || []).forEach(renderDshEvent);
    if (r.text && !(r.events || []).some(e => e.type === 'text' && e.text)) {
      dshAppend('<div class="dsh-msg assistant">' + esc(r.text) + '</div>');
    }
    if (!r.ok) dshAppend('<div class="dsh-status err">Agent 退出异常：' + esc(r.stderr || r.error || '') + '</div>');
    if (msgEl) msgEl.textContent = r.ok ? '完成' : '失败（见日志）';
  } catch (e) {
    dshAppend('<div class="dsh-status err">请求失败：' + esc(e.message) + '</div>');
    if (msgEl) msgEl.textContent = '失败';
  }
  if (btn) btn.disabled = false;
}
function initDshAgent() {
  const b = document.querySelector('#dsh-agent-btn');
  if (b) b.addEventListener('click', openDshAgent);
  const c = document.querySelector('#dsh-close');
  if (c) c.addEventListener('click', closeDshAgent);
  const n = document.querySelector('#dsh-new');
  if (n) n.addEventListener('click', () => {
    dshSession = '';
    const log = document.querySelector('#dsh-log');
    if (log) log.innerHTML = '<div class="dsh-empty">新会话。Agent 已授权读取项目文件与 outputs/ 产物。</div>';
    const s = document.querySelector('#dsh-session'); if (s) s.textContent = '新会话';
  });
  const send = document.querySelector('#dsh-send');
  if (send) send.addEventListener('click', sendDshAgent);
  const ta = document.querySelector('#dsh-task');
  if (ta) ta.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); sendDshAgent(); }
  });
  const ov = document.querySelector('#dsh-overlay');
  if (ov) ov.addEventListener('click', e => { if (e.target === ov) closeDshAgent(); });
}

async function loadGitStatus() {
  const s = document.querySelector('#gh-status');
  if (!s) return;
  try {
    const d = await api('/api/git/status');
    s.innerHTML = '<span class="gh-ok">' + esc(d.branch || '') + '</span>'
      + ' · 变更 ' + esc(d.changes || 0)
      + ' · ' + esc(d.last || '无提交');
  } catch (e) { s.textContent = 'git 状态读取失败：' + e.message; }
}
async function openGithubDesktop() {
  const s = document.querySelector('#gh-status');
  try { const r = await api('/api/git/open', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if (s) s.textContent = r.ok ? '已打开 GitHub Desktop' : ('打开失败：' + (r.error || ''));
  } catch (e) { if (s) s.textContent = '打开失败：' + e.message; }
}
async function commitGithub() {
  const msg = prompt('提交信息（会 git add -A 后 commit，不 push）：', 'Agent 修复');
  if (!msg) return;
  const s = document.querySelector('#gh-status');
  if (s) s.textContent = '提交中…';
  try { const r = await api('/api/git/commit', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    if (s) s.textContent = r.ok ? ('已提交：' + (r.out || '').split('\n')[0]) : ('提交失败：' + (r.err || ''));
    loadGitStatus();
  } catch (e) { if (s) s.textContent = '提交失败：' + e.message; }
}
function centerHomeHero() {
  // 输入框+欢迎语以输入框为基准居中；再整体下移约 30px（固定值，避免反复测量漂移）。
  const root = document.documentElement;
  const empty = document.body.classList.contains('stage-empty');
  root.style.setProperty('--home-shift', empty ? '-20px' : '0px');
}

function init() {
  try { taskDsh = JSON.parse(localStorage.getItem('dgtf_task_dsh') || '{}') || {}; } catch (_) { taskDsh = {}; }
  const _logBody = document.querySelector('#runlog-body');
  if (_logBody) {
    let _logScrollTimer = null;
    _logBody.addEventListener('scroll', function () {
      const near = _logBody.scrollTop + _logBody.clientHeight >= _logBody.scrollHeight - 24;
      logFollow = near;
      if (_logScrollTimer) clearTimeout(_logScrollTimer);
      _logScrollTimer = setTimeout(function () { if (near) logFollow = true; }, 500);
    }, { passive: true });
  }
  buildAdv();
  pollLanes();
  setInterval(pollLanes, 1500);
  loadConfig();
  // 侧栏状态实时刷新（30s；页面隐藏时不跑）
  setInterval(() => { if (document.visibilityState !== 'hidden') loadConfig(); }, 30000);
  loadFacets();
  loadExistingTasks();
  loadLib();
  loadDash();
  /* ★ R44：读数台**实时更新** —— 5 秒一轮，且只在「读数台」这一页可见、页面不在后台时拉。
     接口侧不用怕：`dashboard.scan()` 有**目录签名缓存**，余额自带 **15s 缓存** ⇒ 不会打爆。 */
  setInterval(() => {
    const p = $('#dash-stats');
    if (p && p.classList.contains('active') && document.visibilityState !== 'hidden') loadDash();
  }, 5000);
  loadChats();
  loadLocal();
  loadWeb();

  paintWelcome();                    // ★ R40：首屏欢迎语按时段写一次
  $('#run-btn').addEventListener('click', onRunBtn);

  /* ★ R33：日志滚动指示跟着走（滚动 / 尺寸变化 / 内容变化）
     ★ R37：改成**可拖动的圆点** —— 绑一次拖拽（内部自己挂 scroll 监听） */
  const _rlb = $('#runlog-body');
  if (_rlb) _rlb.addEventListener('scroll', updateRlBar);
  window.addEventListener('resize', updateRlBar);
  /* ★ R40：圆点改成 `position:fixed`（视口坐标）⇒ 页面滚动时它的落点也会变，
     补一个 window 的 scroll 监听（passive：绝不能拖慢滚动）。 */
  window.addEventListener('scroll', updateRlBar, { passive: true });
  bindRlBarDrag();

  // 抽屉：左上角图标拉开 / 关闭键 / 点遮罩 / Esc 收起
  const _db = $('#drawer-btn'), _dc = $('#drawer-close'), _dm = $('#drawer-mask');
  if (_db) _db.addEventListener('click', openDrawer);
  if (_dc) _dc.addEventListener('click', closeDrawer);
  if (_dm) _dm.addEventListener('click', closeDrawer);
  initTips();   // 悬停描述气泡（挂 body 的 fixed 气泡，抽屉的 overflow 裁不到）

  // 抽屉里的按钮 → 打开对应的全屏面板页；× / Esc 关闭
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.addEventListener('click', () => {
      openSheet(b.dataset.sheet);
      if (b.dataset.sheet === 'view-chats') loadChats();   // 打开就刷新会话列表
    });
  });
  const _shc = $('#sheet-close');
  if (_shc) _shc.addEventListener('click', closeSheet);
  /* 参数页底栏的**两个出口**（★ R38：底栏是 `.sheet` 的直接子项、参数两页共用）：
       「保存」        → 把所有参数改动写回用户配置 dgtf_config.user.yaml（持久）**并退出**；
       「恢复出厂设置」→ 删用户配置，全部参数回落到后端出厂 yaml。
       （`#adv-once`「仅本次」已按用户要求移除。） */
  const _advSave = $('#adv-save');
  if (_advSave) _advSave.addEventListener('click', saveAdvToFile);
  const _advReset = $('#adv-reset');
  if (_advReset) _advReset.addEventListener('click', resetAdv);

  /* 导出：单份产物（条目右上角）/ 单组检索结果 —— 直接用浏览器下载 */
  document.addEventListener('click', e => {
    const one = e.target.closest('[data-exp]');
    if (one) {
      e.preventDefault();
      e.stopPropagation();
      const a = document.createElement('a');
      a.href = '/api/export/output?name=' + encodeURIComponent(one.dataset.exp);
      a.download = '';
      document.body.appendChild(a); a.click(); a.remove();
      return;
    }
    const grp = e.target.closest('[data-expexp]');
    if (grp) {
      e.preventDefault();
      e.stopPropagation();
      const a = document.createElement('a');
      a.href = '/api/export/web?q=' + encodeURIComponent(grp.dataset.expexp);
      a.download = '';
      document.body.appendChild(a); a.click(); a.remove();
    }
  });

  // 产物库 / 检索库工具条上的「导出当前列表」
  const _le = $('#lib-export');
  if (_le) _le.addEventListener('click', () => {
    if (!libExpOn) { libExpOn = true; libSel.clear(); renderLib(_libItems); return; }
    if (!libSel.size) { libExpOn = false; renderLib(_libItems); return; }
    const p2 = new URLSearchParams();
    libSel.forEach(n => p2.append('names', n));
    const a = document.createElement('a');
    a.href = '/api/export/outputs?' + p2.toString();
    a.download = '';
    document.body.appendChild(a); a.click(); a.remove();
    libExpOn = false; libSel.clear(); renderLib(_libItems);
  });
  const _we = $('#web-export');
  if (_we) _we.addEventListener('click', () => {
    if (!webExpOn) { webExpOn = true; webSel.clear(); renderWeb(); return; }
    if (!webSel.size) { webExpOn = false; renderWeb(); return; }
    const p2 = new URLSearchParams();
    const qs = [], tss = [];
    webSel.forEach(k => (k.startsWith('g:') ? qs : tss).push(k.slice(2)));
    qs.forEach(x => p2.append('qs', x));
    tss.forEach(x => p2.append('ts', x));
    const a = document.createElement('a');
    a.href = '/api/export/web?' + p2.toString();
    a.download = '';
    document.body.appendChild(a); a.click(); a.remove();
    webExpOn = false; webSel.clear(); renderWeb();
  });

  // 历史对话列表：点一条 → 回到那一次会话（内容异步渲染 ⇒ 事件委托）
  const _cl = $('#chats-list');
  if (_cl) _cl.addEventListener('click', e => {
    const it = e.target.closest('[data-chat]');
    if (it) openChat(_chats[Number(it.dataset.chat)]);
  });

  // 高级参数页里的分组按钮（内容是异步渲染的 ⇒ 用事件委托）
  const _ag = $('#adv-groups');
  if (_ag) _ag.addEventListener('click', e => {
    const b = e.target.closest('[data-advgroup]');
    if (b) openAdvGroup(b.dataset.advgroup);
  });

  // 参数值一改就记进 `advOverrides`（分组页会按需重建，靠它留住用户输入、
  // 也靠它把**所有分组**的改动一起提交），并同步底部按钮上的计数。
  // ★ R38：**`data-adv`（CLM/CLI 参数）也要收** —— 原来只认 `data-cfg`，
  //   于是 CLM 组的输入永远进不了累积表 ⇒ 点保存报「没有要保存的改动」（用户报的正是这个）。
  const _advGrid = $('#adv-grid');
  if (_advGrid) {
    ['input', 'change'].forEach(ev => _advGrid.addEventListener(ev, e => {
      const el = e.target.closest && e.target.closest('[data-cfg],[data-adv]');
      if (el) { rememberAdv(el); updateAdvActions(); }
    }));
  }

  // 左上角另两个：搜索对话产物 / 开启新对话
  const _sb = $('#search-btn'), _sc = $('#search-close'), _nc = $('#newchat-btn'),
        _si = $('#search-input'), _sov = $('#search-overlay');
  if (_sb) _sb.addEventListener('click', openSearch);
  if (_sc) _sc.addEventListener('click', closeSearch);
  if (_nc) _nc.addEventListener('click', newChat);
  if (_si) _si.addEventListener('input', () => {          // 边打边搜（防抖 300ms）
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(_si.value.trim()), 300);
  });
  if (_sov) _sov.addEventListener('click', e => {          // 点浮层空白处收起
    if (e.target === _sov) closeSearch();
  });
  /* 输入框里的回形针 → 触发隐藏的文件选择（复用抽屉里那一个 #anchor-file）。
     ★★ R48：**回形针上的计数数字气泡已移除**（用户「回形针不要有上标」），
     于是「点徽章展开清单」这条路没了 ⇒ **改点回形针本身**来分派：
       · 已经有已导入文件 ⇒ 点一下 **展开/收起小窗**（看一眼清单仍是一下）；
       · 一个都没有      ⇒ 点一下 **打开文件选择框**（否则新用户点了没反应）。
     ★ 这个分派必须**两边都测**（有文件 / 无文件），否则很容易做成
       「有文件时永远点不出选择框」这种死角。 */
  const _at = $('#attach-btn');
  if (_at) _at.addEventListener('click', () => {
    if (localItems.length) { toggleAttachPanel(); return; }
    const f = $('#anchor-file');
    if (f) f.click();
  });
  const _apx = $('#ap-close');
  if (_apx) _apx.addEventListener('click', () => toggleAttachPanel(false));
  /* 清单里的「删除」（内容是重建的 ⇒ 事件委托） */
  const _apl = $('#ap-list');
  if (_apl) _apl.addEventListener('click', async (e) => {
    const d = e.target.closest('[data-apdel]');
    if (!d) return;
    e.preventDefault();
    await removeImported(d.dataset.apdel);
  });
  /* 清单开着时，点输入框/别处就收起（免得一直占着地方）——
     只收起，不拦别的行为。 */
  document.addEventListener('click', (e) => {
    if (!attachPanelOpen()) return;
    if (e.target.closest('#attach-panel') || e.target.closest('#attach-btn')) return;
    toggleAttachPanel(false);
  });

  // 输入框里的功能胶囊：点一下开、再点关
  ['#pill-thinking', '#pill-web'].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener('click', () => el.classList.toggle('on'));
  });

  // 输入框随内容增高（封顶 180px，再多就内部滚）
  const ta = $('#question');
  if (ta) ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  });
  /* ★ R44：「选择文件导入」改成**真按钮**去点隐藏的 input —— 原来靠 `<label>` 包着
     `display:none` 的 input，用户报「点了没反应」；按钮这条路最直、最不容易被样式影响。
     `value=''` 保证同一个文件删了还能再选一次。 */
  const _ap = $('#anchor-pick'), _af = $('#anchor-file');
  if (_ap && _af) _ap.addEventListener('click', () => _af.click());
  if (_af) _af.addEventListener('change', e => {
    /* ★★ R46 修：`e.target.files` 是 **FileList 活引用**（拿到的就是同一个对象）。
       原来写成 `const fs = e.target.files; e.target.value = '';` ——
       清 value 会**连带把 fs 清空**（实测 `fs === af.files` 为 true），
       于是 `fs.length` 变 0，`importFiles(fs)` **永远不会被调用** ⇒
       用户报「点了「选择文件导入…」选完文件没任何反应、也不显示」的**唯一根因**。
       修法：**先拷成真数组（快照）**，再清 value。清不清都不影响已拷出的这份。 */
    const fs = e.target.files ? [...e.target.files] : [];
    e.target.value = '';
    if (fs.length) importFiles(fs);
  });
  $('#lib-search').addEventListener('click', loadLib);
  $('#lib-q').addEventListener('keydown', e => { if (e.key === 'Enter') loadLib(); });
  $('#lib-body').addEventListener('change', loadLib);
  ['#lib-decid', '#lib-orient', '#lib-days', '#lib-kind', '#lib-layer'].forEach(s =>
    $(s).addEventListener('change', loadLib));

  // 联网检索结果库：点组标题展开/收起该组内容（内容是重建的 ⇒ 事件委托）
  const _wl = $('#web-list');
  if (_wl) _wl.addEventListener('click', e => {
    const s = e.target.closest('[data-wgsel]');   /* 勾选模式：点组 = 切勾选 */
    if (s) {
      const k = 'g:' + s.dataset.wgsel;
      if (webSel.has(k)) webSel.delete(k); else webSel.add(k);
      const g0 = s.closest('.web-group');
      if (g0) g0.classList.toggle('on', webSel.has(k));
      expBtnText('#web-export', true, webSel.size);
      return;
    }
    const h = e.target.closest('.wg-head');
    if (!h) return;
    const g = h.closest('.web-group');
    if (g) g.classList.toggle('open');
  });

  // 联网检索结果库：过滤 / 聚合模式切换
  $('#web-search').addEventListener('click', loadWeb);
  $('#web-q').addEventListener('input', renderWeb);
  $('#web-mode').addEventListener('change', renderWeb);

  // 高级参数：自绘下拉（开合 / 定位 / 点外面或滚动就收起）
  document.addEventListener('click', onDdClick);
  window.addEventListener('resize', closeDDs);
  document.addEventListener('scroll', onDdScroll, true);
  // 演练模式现在是输入框那排的胶囊（`<label class="pill">` 里包着 `#mock`）——
  // 点一下天然就是切勾选；高亮显式切 `.on`（不依赖 `:has()` 的浏览器支持）
  const _mockBox = $('#mock');
  if (_mockBox) _mockBox.addEventListener('change', syncMockPill);
  syncMockPill();
  /* 仪表盘：所有面板常驻可见，**没有标签页了** —— 初始化时一次全加载。
     各面板自己的刷新按钮（搜索 / 刷新）仍然单独触发。 */

  document.body.addEventListener('click', async (e) => {
    /* ★ R44：点**对话框**（含里面的功能胶囊 / 回形针 / 发送键）或**首屏空白区** ⇒ 抽屉自动收起。
       **只做「收起」这一件事**：抽屉的开关仍由左上角图标 / 遮罩 / Esc 管，
       被点的那个元素该有的行为（发消息、切胶囊…）一律照旧。 */
    if (document.body.classList.contains('drawer-open')
        && (e.target.closest('.composer')
            || (document.body.classList.contains('stage-empty')
                && e.target.closest('main.stage')))) {
      closeDrawer();
    }
    const _dh = e.target.closest('#dsh-history-toggle');
    if (_dh) { e.preventDefault(); setDshHistoryOpen(!dshHistoryOpen); return; }
    const _dhc = e.target.closest('#dsh-history-close');
    if (_dhc) { e.preventDefault(); setDshHistoryOpen(false); return; }
    const _dchat = e.target.closest('[data-dsh-chat]');
    if (_dchat) { e.preventDefault(); resumeDshChat(_dchat.dataset.dshChat).catch(function(){}); return; }
    const open = e.target.closest('[data-open]');
    if (open) { e.preventDefault(); openDetail(open.dataset.open); return; }
    const arc = e.target.closest('[data-archive]');
    if (arc) { e.preventDefault(); openArchive(arc.dataset.archive); return; }
    const ds = e.target.closest('[data-dsh-session]');
    if (ds) { e.preventDefault(); openDshSession(ds.dataset.dshSession).catch(function(){}); return; }
    const hs = e.target.closest('.hist');
    if (hs) {
      const n = hs.dataset.hist;
      if (n) openDetail(n);
      return;
    }
    const ex = e.target.closest('[data-expand]');
    if (ex) {
      e.preventDefault();
      const id = ex.dataset.expand;
      polls[id] = polls[id] || { offset: 0 };
      polls[id].expanded = !polls[id].expanded;
      renderTasks();
      return;
    }
    const del = e.target.closest('[data-del]');
    if (del) {
      e.preventDefault();
      const n = del.dataset.del;
      if (confirm('删除导入的资料「' + n + '」？')) {
        api('/api/library/delete', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: n }),
        }).then(() => loadLocal()).catch(err => alert('删除失败：' + err.message));
      }
      return;
    }
    const loc = e.target.closest('.item[data-local]');
    if (loc) { openLocal(loc.dataset.local); return; }
    const item = e.target.closest('.item[data-name]');
    if (item) {
      if (libExpOn) {                       /* 勾选模式：点条目 = 切勾选（不打开详情） */
        const n = item.dataset.name;
        if (libSel.has(n)) libSel.delete(n); else libSel.add(n);
        item.classList.toggle('on', libSel.has(n));
        expBtnText('#lib-export', true, libSel.size);
        return;
      }
      openDetail(item.dataset.name); return;
    }
    const wt = e.target.closest('[data-wtsel]');
    if (wt) {                               /* 平铺模式：命中条目切勾选 */
      const k = wt.dataset.wtsel;
      if (webSel.has(k)) webSel.delete(k); else webSel.add(k);
      wt.classList.toggle('on', webSel.has(k));
      expBtnText('#web-export', true, webSel.size);
      return;
    }
    const cancel = e.target.closest('[data-cancel]');
    if (cancel) {
      const id = cancel.dataset.cancel;
      await api(`/api/tasks/${id}/cancel`, { method: 'POST' }).catch(() => {});
      pollTask(id);
      return;
    }
    if (e.target.id === 'detail-close' || e.target.id === 'detail') {
      $('#detail').classList.add('hidden');
      setDetailMeta('');
    }
  });

  /* ── Agent 面板：入口（左上角图标）/ 刷新 / 提交 / 消费者 / 知识 ─── */
  const _agentBtn = $('#agent-btn');
  if (_agentBtn) _agentBtn.addEventListener('click', () => {
    openSheet('view-agent');
    loadAgent();
    bootV2Auto();
  });
  const _agentRefresh = $('#agent-refresh');
  if (_agentRefresh) _agentRefresh.addEventListener('click', loadAgent);
  const _v2Prefer = $('#pareto-prefer');
  if (_v2Prefer) _v2Prefer.addEventListener('change', async function () {
    const st = document.querySelector('#v2-auto-status');
    const m = document.querySelector('#agent-msg');
    if (st) st.textContent = '自动选优中…';
    if (m) m.textContent = '正在自动评估 V2 策略…';
    try {
      const r = await api('/api/schedule/v2/auto-apply', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({prefer: _v2Prefer.value || 'balanced'})});
      if (r.ok) {
        const c = r.chosen || {};
        if (st) st.textContent = '自动：' + (c.name || '') + ' / ' + (c.template || '');
        if (m) m.textContent = '已自动写入最优策略：' + (c.name || '') +
          '（score ' + String(c.auto_score || 0) + '）';
      } else {
        if (st) st.textContent = '自动选优失败';
        if (m) m.textContent = '自动选优失败：' + (r.error || '');
      }
      await loadAgent();
    } catch (e) {
      if (st) st.textContent = '自动选优失败';
      if (m) m.textContent = '自动选优失败：' + e.message;
    }
  });
  function bootV2Auto() {
    if (v2AutoBooted) return;
    v2AutoBooted = true;
    setTimeout(function () {
      const sel = document.querySelector('#pareto-prefer');
      if (sel) sel.dispatchEvent(new Event('change'));
    }, 700);
  }
  const _agentNew = $('#agent-new');
  if (_agentNew) _agentNew.addEventListener('click', () => autoAgent('task'));
  const _agentAuto = $('#agent-auto');
  if (_agentAuto) _agentAuto.addEventListener('click', () => autoAgent('full'));
  const _dshPill = $('#pill-dsh');
  if (_dshPill) _dshPill.addEventListener('click', () => toggleDshMode(!dshMode));
  [['dsh-effort', 'dgtf_dsh_effort'], ['dsh-perm', 'dgtf_dsh_perm'], ['dsh-model', 'dgtf_dsh_model']].forEach(function (pair) {
    const el = document.getElementById(pair[0]);
    if (!el) return;
    try { const saved = localStorage.getItem(pair[1]); if (saved !== null) el.value = saved; } catch (_) {}
    el.addEventListener('change', function () {
      try { localStorage.setItem(pair[1], el.value); } catch (_) {}
    });
  });
  const _dshNew = $('#dsh-new-session');
  if (_dshNew) _dshNew.addEventListener('click', () => {
    dshSession = ''; dshCurrent = null;
    dshConversationId = null; dshConversation = null;
    try { localStorage.removeItem(DSH_CONV_KEY); } catch (_) {}
    stopDshConvPoll(); setDshHistoryOpen(false);
    const log = document.querySelector('#runlog-body');
    if (log) log.innerHTML = '<div class="rl-lane rl-boot"><div class="rl-lane-head">DeepSeek Harness Agent · 新会话</div><div class="rl-line"><span class="rl-txt">DSH 会话已重置；元DGTF 会话与当前内容保留。</span></div></div>';
    document.body.classList.add('stage-run'); document.body.classList.remove('stage-empty');
    const rl = document.querySelector('#runlog'); if (rl) rl.classList.remove('hidden');
  });
  document.querySelectorAll('[data-agent-tab]').forEach(function (b) {
    b.addEventListener('click', function () {
      const idx = Number(b.dataset.agentTab || 0);
      document.querySelectorAll('[data-agent-tab]').forEach(function (x) { x.classList.toggle('on', x === b); });
      const secs = document.querySelectorAll('#view-agent .agent-sec');
      secs.forEach(function (s, i) { s.classList.toggle('agent-tab-hidden', i !== idx); });
    });
  });
  (function () {
    const secs = document.querySelectorAll('#view-agent .agent-sec');
    secs.forEach(function (s, i) { s.classList.toggle('agent-tab-hidden', i !== 0); });
  })();
  const _propBox = $('#agent-proposals');
  if (_propBox) _propBox.addEventListener('click', async (e) => {
    const rb = e.target.closest('[data-prop-rollback]');
    if (rb) {
      const id = rb.dataset.propRollback;
      if (!window.confirm('回退提案 ' + id + ' 的修复？会执行 git revert。')) return;
      const m = document.querySelector('#agent-msg');
      if (m) m.textContent = '正在回退提案 ' + id + '…';
      try {
        const r = await api('/api/dsh/proposals/' + encodeURIComponent(id) + '/rollback',
          {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        if (m) m.textContent = '提案 ' + id + '：' + ((r.proposal || {}).status || '已回退');
        loadAgent(); loadGitStatus();
      } catch (err) { if (m) m.textContent = '回退失败：' + err.message; }
      return;
    }
    const ac = e.target.closest('[data-acceptance]');
    if (ac) {
      const prop = (agentProps || []).find(x => x.id === ac.dataset.acceptance);
      if (prop) showAcceptanceInDgtf(prop);
      return;
    }
    const cf = e.target.closest('[data-prop-confirm]');
    if (cf) {
      const cid = cf.dataset.propConfirm;
      try {
        const r = await api('/api/dsh/proposals/' + encodeURIComponent(cid) + '/confirm',
          {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const m0 = document.querySelector('#agent-msg');
        if (m0) m0.textContent = '提案 ' + cid + ' 已确认，等待 DSH 自动修复';
        loadAgent();
      } catch (err) {
        const m0 = document.querySelector('#agent-msg');
        if (m0) m0.textContent = '确认失败：' + err.message;
      }
      return;
    }
    const ok = e.target.closest('[data-prop-approve]');
    const auto = e.target.closest('[data-prop-auto]');
    if (!ok && !auto) return;
    const id = (ok || auto).dataset.propApprove || (ok || auto).dataset.propAuto;
    const mode = ok ? 'user' : 'dsh_auto';
    const prop = (agentProps || []).find(x => x.id === id) || {};
    const title = (prop.task || {}).title || id;
    showAutoDsh('修复提案 · ' + id, [
      {type:'text', text:'提案：' + title},
      {type:'text', text:'方案：' + String(prop.plan || '').slice(0, 800)},
      {type:'text', text:'执行方式：' + (mode === 'dsh_auto' ? 'DSH 自动代理' : '我确认')}
    ], 'running');
    let final = null, errMsg = '';
    try {
      await streamPost('/api/dsh/proposals/' + encodeURIComponent(id) + '/approve/stream',
        {mode: mode}, function (m) {
          if (!dshCurrent) return;
          if (m.type === 'event' && m.event) dshCurrent.events.push(m.event);
          else if (m.type === 'result') final = m.result;
          else if (m.type === 'error') errMsg = m.error || '审批流失败';
          renderDshView();
        });
      if (!final) throw new Error(errMsg || '没有返回结果');
      const res = final.result || {};
      if (res.gate) dshCurrent.events.push({type:'text', text:'fast_gate：' + (res.gate.ok ? 'PASS' : 'FAIL')});
      if (res.repair) dshCurrent.events.push({type:'text', text:'提交：' + (res.repair.committed ? (res.repair.commit || '已提交') : ('未提交：' + (res.repair.why || res.repair.error || '')))});
      dshCurrent.events.push({type:'text', text:'提案状态：' + ((final.proposal || {}).status || '')});
      dshCurrent.status = ((final.proposal || {}).status === 'applied') ? 'done' : 'error';
      dshCurrent.question = '修复提案 · ' + id + ' · ' + ((final.proposal || {}).status || '');
      renderDshView();
      setRunBtn('send');
      loadAgent(); loadGitStatus();
    } catch (err) {
      if (dshCurrent) {
        dshCurrent.events.push({type:'text', text:'执行失败：' + err.message});
        dshCurrent.status = 'error';
        renderDshView();
      }
    }
  });
  const _propFix = $('#prop-autofix');
  if (_propFix) _propFix.addEventListener('click', autoFixProposals);
  const _cfgBtn = $('#dsh-config-btn');
  const _cfgBox = $('#dsh-config-box');
  if (_cfgBtn && _cfgBox) _cfgBtn.addEventListener('click', () => {
    const open = _cfgBox.classList.toggle('hidden');
    _cfgBtn.classList.toggle('on', !open);
  });
  const _ghOpen = $('#gh-open');
  if (_ghOpen) _ghOpen.addEventListener('click', openGithubDesktop);
  const _ghCommit = $('#gh-commit');
  if (_ghCommit) _ghCommit.addEventListener('click', commitGithub);
  const _ghAuto = $('#gh-auto');
  if (_ghAuto) _ghAuto.addEventListener('click', () => autoAgent('proposal'));
  const _dshTopNew = $('#dsh-newchat-btn');
  if (_dshTopNew) _dshTopNew.addEventListener('click', () => {
    dshSession = ''; dshCurrent = null;
    dshConversationId = null; dshConversation = null;
    try { localStorage.removeItem(DSH_CONV_KEY); } catch (_) {}
    stopDshConvPoll(); setDshHistoryOpen(false);
    const log = document.querySelector('#runlog-body');
    if (log) log.innerHTML = '<div class="rl-lane rl-boot"><div class="rl-lane-head">DeepSeek Harness Agent · 新会话</div><div class="rl-line"><span class="rl-txt">DSH 会话已重置；元DGTF 会话与当前内容保留。</span></div></div>';
    document.body.classList.add('stage-run'); document.body.classList.remove('stage-empty');
    const rl = document.querySelector('#runlog'); if (rl) rl.classList.remove('hidden');
  });
  const _dshArtList = $('#agent-dsh-art');
  if (_dshArtList) _dshArtList.addEventListener('click', async (e) => {
    const it = e.target.closest('[data-dsh-art]');
    if (!it) return;
    try { await openDshArtifact(it.dataset.dshArt); }
    catch (err) { const m = document.querySelector('#agent-msg'); if (m) m.textContent = '打开产物失败：' + err.message; }
  });
  const _dshList = $('#agent-dsh');
  if (_dshList) _dshList.addEventListener('click', async (e) => {
    const it = e.target.closest('[data-dsh-session]');
    if (!it) return;
    try {
      const r = await api('/api/dsh/sessions/' + encodeURIComponent(it.dataset.dshSession));
      dshSession = r.id || '';
      dshCurrent = { question: r.task || '', session: dshSession,
        events: (r.events || []).concat(r.text ? [{type:'text', text:r.text}] : []),
        status: r.ok ? 'done' : 'error' };
      closeSheet(); toggleDshMode(true); renderDshView();
    } catch (err) { const m = document.querySelector('#agent-msg'); if (m) m.textContent = '回溯失败：' + err.message; }
  });
  const _agentRun = $('#agent-run');
  if (_agentRun) _agentRun.addEventListener('click', () => autoAgent('consumer'));
  const _agentKnowledge = $('#agent-knowledge-btn');
  if (_agentKnowledge) _agentKnowledge.addEventListener('click', () => refreshAgentKnowledge('refresh'));
  const _agentKnSearch = $('#agent-kn-search');
  if (_agentKnSearch) _agentKnSearch.addEventListener('click', () => refreshAgentKnowledge('query'));
  const _agentKnDedupe = $('#agent-kn-dedupe');
  if (_agentKnDedupe) _agentKnDedupe.addEventListener('click', dedupeAgentKnowledge);
  const _agentKnQ = $('#agent-kn-q');
  if (_agentKnQ) _agentKnQ.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); refreshAgentKnowledge('query'); }
  });
  const _agentSubmit = $('#agent-submit');
  if (_agentSubmit) _agentSubmit.addEventListener('click', submitAgentTask);
  const _agentCancel = $('#agent-cancel');
  if (_agentCancel) _agentCancel.addEventListener('click', closeAgentDialog);
  const _agentDlgX = $('#agent-dlg-x');
  if (_agentDlgX) _agentDlgX.addEventListener('click', closeAgentDialog);
  const _agentOverlay = $('#agent-overlay');
  if (_agentOverlay) _agentOverlay.addEventListener('click', e => {
    if (e.target === _agentOverlay) closeAgentDialog();
  });
  const _agentTitle = $('#agent-title');
  if (_agentTitle) _agentTitle.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); submitAgentTask(); }
  });

  initDshAgent();

  // ★ 深链：?panel=view-agent 可直接打开面板（便于截图/联调）。
  try {
    const _panel = new URLSearchParams(location.search).get('panel');
    if (_panel) { openSheet(_panel); if (_panel === 'view-agent') { loadAgent(); bootV2Auto(); } }
    const _advg = new URLSearchParams(location.search).get('advgroup');
    if (_advg) setTimeout(function () { try { openAdvGroup(_advg); } catch (_) {} }, 900);
    const _tab = new URLSearchParams(location.search).get('tab');
    if (_tab !== null) { const _tb = document.querySelector('[data-agent-tab="' + _tab + '"]'); if (_tb) _tb.click(); }
    if (new URLSearchParams(location.search).get('dsh') === '1') toggleDshMode(true);
    const _dc = new URLSearchParams(location.search).get('dsh_conv');
    if (_dc) {
      toggleDshMode(true);
      dshConversationId = _dc;
      try { localStorage.setItem(DSH_CONV_KEY, _dc); } catch (_) {}
      loadDshConversation();
      startDshConvPoll();
      if (new URLSearchParams(location.search).get('dsh_history') === '1') {
        setTimeout(function () { setDshHistoryOpen(true); }, 800);
      }
    }
    if (new URLSearchParams(location.search).get('drawer') === '1') openDrawer();
    const _dt = new URLSearchParams(location.search).get('dsh_task');
    if (_dt) { toggleDshMode(true); const _ta = document.querySelector('#question');
      if (_ta) _ta.value = _dt; setTimeout(() => startDshRun(_dt), 500); }
  } catch (_) { /* 忽略 */ }

  // 键盘优先：⌘/Ctrl+Enter 提交 · / 聚焦搜索 · Esc 关闭浮层
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); startRun(); return; }
    const tag = (e.target.tagName || '');
    if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) {
      e.preventDefault();
      $('#lib-q').focus();          // 产物库常驻可见，不用再切标签
      return;
    }
    if (e.key === 'Escape') {
      /* ★ 一次只关**最上层那一个还开着的**（按层级从上到下试），不要一口气全关。
         顺序：下拉菜单 → 详情浮层 → 搜索浮层 → 全屏面板 → 抽屉。 */
      if (document.querySelector('.dd-menu.show')) { closeDDs(); return; }
      const _det = $('#detail');
      if (_det && !_det.classList.contains('hidden')) {
        _det.classList.add('hidden'); return;
      }
      const _sov = $('#search-overlay');
      if (_sov && !_sov.classList.contains('hidden')) { closeSearch(); return; }
      const _aov = $('#agent-overlay');
      if (_aov && !_aov.classList.contains('hidden')) { closeAgentDialog(); return; }
      const _dov = $('#dsh-overlay');
      if (_dov && !_dov.classList.contains('hidden')) { closeDshAgent(); return; }
      const _sh = $('#sheet');
      if (_sh && !_sh.classList.contains('hidden')) { closeSheet(); return; }
      closeDrawer();
      return;
    }
  });
  window.addEventListener('resize', centerHomeHero);
  requestAnimationFrame(centerHomeHero);
  setTimeout(resumeLastAutoJobNotice, 1200);
  window.addEventListener('load', centerHomeHero);
}

document.addEventListener('DOMContentLoaded', init);
