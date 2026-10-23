#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R44 第 5 条（续）：服务端**上传体积闸** + 前端**二进制分批上传 + 逐文件结果**。

- `server.py`：`/api/library/import` 先看 `Content-Length`，超过 200MB 直接 **413**
  （base64 会膨胀 1/3；不设闸的话一个大文件就能把内存吃光）。
- `app.js`：`importFiles` 重写 —— `File.text()` → **`ArrayBuffer` + base64**（PDF/图片必须这样读），
  按体积分批（每批 ≤48MB）、显示进度、把**逐文件结果**摆出来（成功/跳过/失败原因）。

`server.py` 纯 LF；`app.js` 纯 CRLF。

    python _mk_r44_import2.py
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRV = HERE / "dgtf_app" / "server.py"
JS = HERE / "dgtf_app" / "static" / "app.js"

SRV_CONST_ANCHOR = '_TOKEN = ""'
SRV_CONST_NEW = '_TOKEN = ""\n\n# ★ R44：导入是二进制上传（base64 后还要膨胀 1/3）⇒ 单独给一个大上限，超了 413。\nMAX_UPLOAD_BYTES = 200 * 1024 * 1024'

SRV_ROUTE_OLD = '''        if p == "/api/library/import":
            data = self._read_json()
            files = data.get("files")'''
SRV_ROUTE_NEW = '''        if p == "/api/library/import":
            _n = int(self.headers.get("Content-Length") or 0)
            if _n > MAX_UPLOAD_BYTES:
                return self._json({"error": "请求体 %.1fMB 超过上限 %.0fMB（请分批导入）"
                                            % (_n / 1048576.0, MAX_UPLOAD_BYTES / 1048576.0)},
                                  413)
            data = self._read_json()
            files = data.get("files")'''

JS_OLD = '''async function importFiles(fileList) {
  const all = [...fileList];
  const list = all.slice(0, 50);              // 上限 50 个（对齐提示气泡的说明）
  const files = [];
  for (const f of list) files.push({ name: f.name, content: await f.text() });
  if (!files.length) return;
  const am = $('#attach-msg');
  const more = all.length > list.length ? `（超出的 ${all.length - list.length} 个已忽略）` : '';
  $('#import-msg').textContent = `导入中（${files.length} 个）…`;
  if (am) am.textContent = `导入中（${files.length} 个）…`;
  try {
    const r = await api('/api/library/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files }),
    });
    $('#import-msg').textContent = `已导入 ${r.saved.length} 个`;
    if (am) {
      am.textContent = `已导入 ${r.saved.length} 个文件，作为外部证据锚点`
        + `（抽屉「本地资料库」里可查看 / 删除）${more}`;
    }
    await loadLocal();
  } catch (e) {
    $('#import-msg').textContent = '导入失败：' + e.message;
    if (am) am.textContent = '导入失败：' + e.message;
  }
}'''

JS_NEW = '''/* ── ★ R44：本地资料库导入（二进制 + 分批 + 逐文件结果）────────────────────
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
  const am = $('#attach-msg');
  importPaint(send.length ? `导入中（共 ${send.length} 个）…` : '没有可导入的文件');
  if (am) am.textContent = `导入中（共 ${send.length} 个）…`;
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
    if (am) am.textContent = tail + '（抽屉「本地资料库」里可查看 / 删除）';
    await loadLocal();
  } catch (e) {
    importRows.push({ ok: false, name: '(整批)', error: e.message });
    importPaint('导入失败：' + e.message);
    if (am) am.textContent = '导入失败：' + e.message;
  } finally {
    if (btn) btn.disabled = false;
    importPaint();
  }
}'''


def rd(p: Path, crlf: bool) -> str:
    b = p.read_bytes()
    if crlf:
        assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    else:
        assert b.count(b"\r") == 0, "%s 不是纯 LF" % p.name
    return b.decode("utf-8")


def wr(p: Path, s: str, crlf: bool) -> None:
    body = s.replace("\r\n", "\n")
    if crlf:
        body = body.replace("\n", "\r\n")
    b = body.encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)


def apply(path: Path, pairs, crlf: bool) -> None:
    s = rd(path, crlf).replace("\r\n", "\n")      # ★ 归一成 LF 再匹配（CRLF 会让多行锚点失配）
    for old, new, what in pairs:
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            continue
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)
    wr(path, s, crlf)


def main() -> int:
    apply(SRV, [(SRV_CONST_ANCHOR, SRV_CONST_NEW, "① server：上传体积上限常量"),
                (SRV_ROUTE_OLD, SRV_ROUTE_NEW, "① server：导入路由 413 闸")], False)
    apply(JS, [(JS_OLD, JS_NEW, "② app.js：importFiles 重写（base64 + 分批 + 逐文件结果）")], True)

    srv = rd(SRV, False)
    js = rd(JS, True)
    ast.parse(srv)
    bad = []
    for k in ("MAX_UPLOAD_BYTES = 200 * 1024 * 1024", "413", "_n > MAX_UPLOAD_BYTES"):
        if k not in srv:
            bad.append("server.py 缺：" + k)
    for k in ("function fileToB64(", "LIB_MAX_FILES = 50, LIB_MAX_MB = 100",
              "readAsArrayBuffer", "btoa(s)", "function importPaint(", "r.results"):
        if k not in js:
            bad.append("app.js 缺：" + k)
    if "for (const f of list) files.push({ name: f.name, content: await f.text() });" in js:
        bad.append("老的 `f.text()` 通路还在")
    r = subprocess.run(["node", "--check", str(JS)], capture_output=True)
    if r.returncode != 0:
        bad.append("node --check 失败：" + r.stderr.decode("utf-8", "replace")[:200])
    else:
        print("  ✓ node --check app.js 通过")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：server 413 闸 + 前端 base64/分批/结果 都在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
