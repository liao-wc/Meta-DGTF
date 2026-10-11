/* 登录闸门状态机测试：用 DOM 桩在 Node 里跑真实的 app.js。
   验证「未登录 → 原地显示登录卡」这条路，以及 401 就地弹闸门、登出重载。 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP_JS = path.join(__dirname, 'dgtf_app', 'static', 'app.js');
const SRC = fs.readFileSync(APP_JS, 'utf8');

let ok = 0, fail = 0;
const chk = (name, cond, extra = '') => {
  if (cond) { ok++; console.log('  OK  ' + name); }
  else { fail++; console.log('  BAD ' + name + (extra ? '  ' + extra : '')); }
};

/* ── 极简 DOM 桩 ─────────────────────────────────────────────── */
function mkClassList() {
  const s = new Set();
  return {
    add: (...c) => c.forEach(x => s.add(x)),
    remove: (...c) => c.forEach(x => s.delete(x)),
    contains: (c) => s.has(c),
    toggle: (c, on) => { if (on === undefined) { s.has(c) ? s.delete(c) : s.add(c); } else if (on) s.add(c); else s.delete(c); },
    _set: s,
  };
}
function mkEl(id) {
  return {
    id, hidden: false, disabled: false, value: '', textContent: '', innerHTML: '',
    checked: false, dataset: {}, style: {},
    classList: mkClassList(),
    _handlers: {},
    addEventListener(t, fn) { (this._handlers[t] = this._handlers[t] || []).push(fn); },
    focus() { this._focused = true; },
    click() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    closest: () => null,
  };
}
// 未注册的选择器 → 万能桩，避免 startApp 里到处炸
function anyEl() {
  const t = function () { return anyEl(); };
  return new Proxy(t, {
    get(_, k) {
      if (k === 'classList') return mkClassList();
      if (k === 'dataset') return {};
      if (k === 'style') return {};
      if (k === 'length') return 0;
      if (typeof k === 'symbol') return undefined;
      return anyEl();
    },
    set() { return true; },
    apply() { return anyEl(); },
  });
}

function makeEnv() {
  const reg = {};
  ['#auth-gate', '#auth-form', '#auth-msg', '#auth-btn', '#auth-user', '#auth-pass',
   '#auth-sub', '#whoami', '#env-info', '#mock', '#cost-warn', '#detail',
   '#tasks', '#tasks-empty', '#question', '#run-btn', '#adv-grid', '#logout-btn',
   '#lib-q', '#lib-body', '#lib-count', '#lib-list',
   '#lib-decid', '#lib-orient', '#lib-days', '#lib-search',
   '#anchor-file', '#import-msg', '#local-count', '#local-list',
   '#local-cand', '#local-cand-hint', '#web-count', '#web-list',
  ].forEach(id => { reg[id] = mkEl(id); });

  const gate = reg['#auth-gate'];
  gate.hidden = true;                                  // 与 index.html 的 hidden 属性一致
  const body = Object.assign(mkEl('body'), { classList: mkClassList() });
  body.classList.add('auth-pending');                  // 与 <body class="auth-pending"> 一致

  const document = {
    body,
    querySelector: (s) => (s in reg ? reg[s] : anyEl()),
    querySelectorAll: () => [],
    createElement: () => mkEl('new'),
    addEventListener(t, fn) { (this._h = this._h || {})[t] = fn; },
  };

  const calls = { reload: 0, fetch: [] };
  const location = { reload: () => { calls.reload++; }, replace: () => { calls.replace = true; } };

  let fetchImpl = async () => ({ ok: false, status: 401, json: async () => ({ error: '未登录' }) });
  const fetch = async (url, opts) => {
    calls.fetch.push({ url, method: (opts && opts.method) || 'GET' });
    return fetchImpl(url, opts);
  };

  const sandbox = {
    document, location, fetch, console,
    setInterval: () => 0, clearInterval: () => {}, setTimeout: (f) => { f(); return 0; },
    alert: () => {}, confirm: () => true,
    URLSearchParams, JSON, Object, Array, String, Number, Boolean, Math, Date, Error, RegExp, Promise,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  return { sandbox, reg, body, gate, calls, setFetch: (f) => { fetchImpl = f; }, document };
}

const jsonRes = (status, obj) => ({ ok: status >= 200 && status < 300, status, json: async () => obj });

function boot(env) {
  vm.createContext(env.sandbox);
  vm.runInContext(SRC, env.sandbox, { filename: 'app.js' });
  return env.document._h['DOMContentLoaded'];      // 取 bootstrap
}
const tick = () => new Promise(r => setImmediate(r));

(async () => {
  console.log('\n[A] 未登录：原地显示登录卡，不跳转');
  {
    const env = makeEnv();
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(401, { error: '未登录', allow_register: false });
      throw new Error('不该请求 ' + url);
    });
    const onReady = boot(env);
    chk('已注册 DOMContentLoaded 启动钩子', typeof onReady === 'function');
    onReady(); await tick(); await tick(); await tick();

    chk('页面已解锁 pending 态', !env.body.classList.contains('auth-pending'));
    chk('body 进入 locked 态', env.body.classList.contains('locked'));
    chk('登录卡已显示', env.gate.hidden === false);
    chk('副标题为默认文案', /管理员开通/.test(env.reg['#auth-sub'].textContent),
        env.reg['#auth-sub'].textContent);
    chk('没有发生跳转', !env.calls.reload && !env.calls.replace);
  }

  console.log('\n[B] 登录失败：就地报错，不重载');
  {
    const env = makeEnv();
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(401, { error: '未登录' });
      if (url === '/api/auth/login') return jsonRes(401, { error: '用户名或密码不正确' });
      throw new Error('不该请求 ' + url);
    });
    boot(env)(); await tick(); await tick(); await tick();

    env.reg['#auth-user'].value = 'admin.aL';
    env.reg['#auth-pass'].value = 'wrong';
    await env.reg['#auth-form']._handlers['submit'][0]({ preventDefault() {} });
    await tick();

    const msg = env.reg['#auth-msg'];
    chk('显示服务端错误原文', msg.textContent === '用户名或密码不正确', msg.textContent);
    chk('错误态样式生效', msg.className === 'auth-msg err', msg.className);
    chk('失败不重载页面', env.calls.reload === 0);
    chk('按钮已恢复可用', env.reg['#auth-btn'].disabled === false);
  }

  console.log('\n[C] 登录成功：整页重载进入工作台');
  {
    const env = makeEnv();
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(401, { error: '未登录' });
      if (url === '/api/auth/login') return jsonRes(200, { ok: true, user: { username: 'admin.aL' } });
      throw new Error('不该请求 ' + url);
    });
    boot(env)(); await tick(); await tick(); await tick();

    env.reg['#auth-user'].value = 'admin.aL';
    env.reg['#auth-pass'].value = 'Admin@DGTF2026';
    await env.reg['#auth-form']._handlers['submit'][0]({ preventDefault() {} });
    await tick();

    chk('成功后重载（清掉上一用户界面残留）', env.calls.reload === 1, 'reload=' + env.calls.reload);
    chk('成功提示已显示', /正在进入/.test(env.reg['#auth-msg'].textContent));
  }

  console.log('\n[D] 已登录：直接进工作台，不显示登录卡');
  {
    const env = makeEnv();
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(200, { username: 'admin.aL', role: 'admin' });
      return jsonRes(200, {});                         // config / tasks / facets / outputs
    });
    boot(env)(); await tick(); await tick(); await tick();

    chk('退出 pending 态', !env.body.classList.contains('auth-pending'));
    chk('未进入 locked 态', !env.body.classList.contains('locked'));
    chk('登录卡保持隐藏', env.gate.hidden === true);
  }

  console.log('\n[E] 会话过期：api 401 就地弹闸门（不跳转）');
  {
    const env = makeEnv();
    let expired = false;                 // 先正常运行，稍后才过期
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(200, { username: 'admin.aL', role: 'admin' });
      if (url === '/api/tasks') {
        return expired ? jsonRes(401, { error: '未登录', code: 'UNAUTHORIZED' })
                       : jsonRes(200, { tasks: [] });
      }
      return jsonRes(200, {});
    });
    boot(env)(); await tick(); await tick(); await tick();
    chk('起手是工作台态', !env.body.classList.contains('locked'));

    // 模拟运行中会话被踢：直接调内部 api()
    expired = true;
    const api = vm.runInContext('api', env.sandbox);
    let threw = '';
    try { await api('/api/tasks'); } catch (e) { threw = e.message; }
    await tick();

    chk('401 后进入 locked 态', env.body.classList.contains('locked'));
    chk('401 后登录卡出现', env.gate.hidden === false);
    chk('副标题提示已失效', /登录已失效/.test(env.reg['#auth-sub'].textContent),
        env.reg['#auth-sub'].textContent);
    chk('未跳转，仍是同一页', env.calls.reload === 0 && !env.calls.replace);
    chk('向上抛出可读错误', /重新登录/.test(threw), threw);
  }

  console.log('\n[F] 登出：清会话后重载回闸门');
  {
    const env = makeEnv();
    env.setFetch(async (url) => {
      if (url === '/api/auth/me') return jsonRes(200, { username: 'admin.aL', role: 'admin' });
      return jsonRes(200, {});
    });
    boot(env)(); await tick(); await tick(); await tick();

    const out = env.reg['#logout-btn']._handlers['click'][0];
    await out(); await tick();

    const hit = env.calls.fetch.find(f => f.url === '/api/auth/logout');
    chk('调用了登出接口', !!hit && hit.method === 'POST', JSON.stringify(hit));
    chk('登出后重载回登录闸门', env.calls.reload === 1, 'reload=' + env.calls.reload);
    chk('登出按钮置灰防重复点击', env.reg['#logout-btn'].disabled === true);
  }

  console.log('\n' + '─'.repeat(44));
  console.log(`结果：${ok} 通过 / ${fail} 失败`);
  console.log('─'.repeat(44) + '\n');
  process.exit(fail === 0 ? 0 : 1);
})();
