# -*- coding: utf-8 -*-
"""本地实时日志面板：给 DSH 右栏 Browser tab 打开用。

只读 workspace 内日志文件；默认跟随最近修改的 _ab_*/_gate_* / dgtf_app/runs/*.log。
不写日志、不依赖第三方库、只绑定 127.0.0.1。
"""
from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
MAX_TAIL = 400_000


def _candidates() -> list[Path]:
    out: list[Path] = []
    for pat in ("_ab_*.log", "_gate_*.log", "*.log"):
        out.extend(ROOT.glob(pat))
    out.extend(ROOT.glob("dgtf_app/runs/*.log"))
    seen, uniq = set(), []
    for p in out:
        try:
            rp = p.resolve()
            if rp in seen or not rp.is_file() or ROOT not in rp.parents:
                continue
            seen.add(rp)
            uniq.append(rp)
        except OSError:
            continue
    # 运行日志优先（_ab_*），其次 gate/其它；否则最新 gate 会盖掉刚跑的任务
    uniq.sort(key=lambda p: (not p.name.startswith("_ab_"),
                             -p.stat().st_mtime))
    return uniq[:80]


def _safe(name: str) -> Path | None:
    if not name:
        return None
    try:
        p = (ROOT / name).resolve()
        if ROOT not in p.parents or not p.is_file():
            return None
        return p
    except (OSError, ValueError):
        return None


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>元DGTF · 实时日志</title>
<style>
:root{color-scheme:dark;--bg:#101218;--panel:#171a22;--line:#2a2f3a;--t1:#e8eaf0;--t2:#b8bdc9;--t3:#7c8394;--acc:#8f9bff;--ok:#61d6a5}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--t2);
font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}
header{display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid var(--line);
background:var(--panel);position:sticky;top:0;z-index:2}
h1{font-size:13px;margin:0;color:var(--t1);font-weight:600;white-space:nowrap}
#file{flex:1;min-width:0;background:#0c0e13;color:var(--t2);border:1px solid var(--line);
border-radius:7px;padding:6px 8px;font:inherit}
#state{color:var(--t3);white-space:nowrap;font-size:11px}
#out{margin:0;padding:12px 14px 40px;white-space:pre-wrap;word-break:break-word;
font:12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--t2)}
#out .err{color:#ff9b9b} #out .ok{color:var(--ok)} #out .hl{color:var(--acc)}
#bottom{padding:8px 14px;color:var(--t3);font-size:11px;border-top:1px solid var(--line);
position:fixed;left:0;right:0;bottom:0;background:rgba(16,18,24,.96)}
</style></head><body>
<header><h1>元DGTF · 实时日志</h1>
<select id="file" aria-label="选择日志文件"></select><span id="state">连接中…</span></header>
<pre id="out"></pre><div id="bottom">自动跟随最新输出 · 仅本机 loopback</div>
<script>
let off=0, cur='', timer=null, files=[];
const $=s=>document.querySelector(s);
function esc(t){return t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function loadFiles(){
  const r=await fetch('/api/files',{cache:'no-store'}); files=(await r.json()).files||[];
  const sel=$('#file'); const prev=sel.value||cur;
  sel.innerHTML=files.map(f=>'<option value="'+esc(f)+'">'+esc(f)+'</option>').join('');
  if(prev && files.includes(prev)) sel.value=prev;
  if(!sel.value && files.length) sel.value=files[0];
  if(sel.value!==cur){cur=sel.value; off=0; $('#out').textContent='';}
}
async function poll(){
  if(!cur){await loadFiles(); if(!cur) return;}
  try{
    const r=await fetch('/api/log?file='+encodeURIComponent(cur)+'&offset='+off,{cache:'no-store'});
    const j=await r.json();
    if(j.reset){$('#out').textContent='';off=0;}
    if(j.text){$('#out').textContent+=j.text;off=j.offset;window.scrollTo(0,document.body.scrollHeight);}
    $('#state').textContent=(j.mtime||'')+' · '+(j.size||0)+' B · 跟随中';
  }catch(e){$('#state').textContent='连接失败';}
}
$('#file').addEventListener('change',()=>{cur=$('#file').value;off=0;$('#out').textContent='';});
loadFiles().then(poll);
setInterval(async()=>{await loadFiles();await poll();},1200);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if u.path == "/api/files":
            body = json.dumps({"files": [str(p.relative_to(ROOT)).replace("\\", "/")
                                        for p in _candidates()]},
                              ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if u.path == "/api/log":
            qs = parse_qs(u.query)
            p = _safe((qs.get("file") or [""])[0])
            if p is None:
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            try:
                off = max(0, int((qs.get("offset") or ["0"])[0]))
            except ValueError:
                off = 0
            size = p.stat().st_size
            reset = off > size
            if reset:
                off = 0
            with p.open("rb") as f:
                f.seek(off)
                data = f.read(MAX_TAIL)
            self._send(200, json.dumps({
                "text": data.decode("utf-8", "replace"),
                "offset": off + len(data),
                "size": size,
                "reset": reset,
                "mtime": time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime)),
            }, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, fmt, *args):
        # 面板每 1.2s 轮询，别把访问日志打到宿主控制台
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("http://127.0.0.1:%d" % args.port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
