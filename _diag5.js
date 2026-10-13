(async () => {
  const R = [], d = document;
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const log = (s) => R.push(s);
  for (let i = 0; i < 100; i++) { if (d.querySelector('#runlog')) break; await sleep(100); }

  // ---- 0. 记录初始状态 ----
  const before = {
    list: d.querySelectorAll('#local-list .item').length,
    count: (d.querySelector('#local-count') || {}).textContent || '',
    badge: (d.querySelector('#attach-n') || {}).textContent || '0',
  };

  // ---- 1. 像用户一样：点导航按钮打开「本地资料库」面板 ----
  const navs = [...d.querySelectorAll('[data-sheet]')];
  const target = navs.find(b => (b.getAttribute('data-sheet') || '').indexOf('local') >= 0);
  log('打开面板: ' + (target ? '点了 ' + target.getAttribute('data-sheet') : '★ 没找到本地资料库按钮'));
  if (target) { target.click(); await sleep(700); }

  // ---- 2. ★ 走完整真实链路：设 files + 派发 change ----
  const af = d.querySelector('#anchor-file');
  const pick = d.querySelector('#anchor-pick');
  log('#anchor-file 存在: ' + !!af + ' / #anchor-pick 存在: ' + !!pick);

  // 记录 importFiles 是否被真的调用了
  let called = 0, calledWith = '';
  if (window.__origImportFiles === undefined && typeof importFiles === 'function') {
    window.__origImportFiles = importFiles;
    // 换名包装：不改变原逻辑，只做探针
    window.__wrappedImportFiles = function (fl) {
      called++;
      calledWith = fl ? (fl.length + ' 个文件') : String(fl);
      return window.__origImportFiles.apply(this, arguments);
    };
  }
  // 用 change 监听记录事件是否到达
  let changeFired = 0;
  if (af) af.addEventListener('change', () => { changeFired++; }, true);
  if (af && pick) pick.addEventListener('click', () => { log('  (click 事件已到达 #anchor-pick)'); }, true);

  // 造 3 个文件（纯文本，走 library 的文本分支）
  const mk = (n, txt) => new File([txt], n, { type: 'text/markdown' });
  const dt = new DataTransfer();
  dt.items.add(mk('_diag5_a.md', '# 诊断文件A\n\n这是第一份资料。\n'));
  dt.items.add(mk('_diag5_b.md', '# 诊断文件B\n\n这是第二份资料。\n'));
  dt.items.add(mk('_diag5_c.md', '# 诊断文件C\n\n这是第三份资料。\n'));

  if (af) {
    af.files = dt.files;
    log('已设 #anchor-file.files = ' + af.files.length + ' 个');
    // ★ 只派发 change（真实链路就是这样）：先试不冒泡、再试冒泡，看哪个能触发
    af.dispatchEvent(new Event('change', { bubbles: false }));
    await sleep(300);
    log('  change(不冒泡) 后 changeFired=' + changeFired + '，列表行数=' + d.querySelectorAll('#local-list .item').length);
    if (d.querySelectorAll('#local-list .item').length === before.list && changeFired === 0) {
      // 换冒泡再试一次
      af.files = dt.files;
      af.dispatchEvent(new Event('change', { bubbles: true }));
      await sleep(300);
      log('  change(冒泡) 后 changeFired=' + changeFired + '，列表行数=' + d.querySelectorAll('#local-list .item').length);
    }
    // 等导入完成（POST 往返）
    for (let i = 0; i < 60; i++) {
      if (d.querySelectorAll('#local-list .item').length > before.list) break;
      await sleep(250);
    }
  }

  // ---- 3. 结果 ----
  log('');
  log('=== 结果 ===');
  log('起始: 列表 ' + before.list + ' 行 / 计数 "' + before.count + '" / 徽章 ' + before.badge);
  log('结束: 列表 ' + d.querySelectorAll('#local-list .item').length + ' 行 / 计数 "'
      + ((d.querySelector('#local-count') || {}).textContent || '') + '" / 徽章 '
      + ((d.querySelector('#attach-n') || {}).textContent || '?') + ' hidden='
      + ((d.querySelector('#attach-n') || { classList: { contains: () => '?' } }).classList.contains('hidden')));
  log('');
  log('★ change 事件到达次数: ' + changeFired);
  log('★ 面板页消息位 #import-msg (211行): ' + JSON.stringify((d.querySelector('#import-msg') || {}).textContent));
  log('★ 输入框消息位 #attach-msg (323行): ' + JSON.stringify((d.querySelector('#attach-msg') || {}).textContent));
  log('');
  const rows = [...d.querySelectorAll('#local-list .item')];
  log('列表前 4 行:');
  rows.slice(0, 4).forEach((x, i) => log('  [' + i + '] ' + (x.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 110)));

  return R.join('\n');
})()
