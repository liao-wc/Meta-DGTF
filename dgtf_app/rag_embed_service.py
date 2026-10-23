# -*- coding: utf-8 -*-
"""本地 BGE embedding HTTP 服务（仅 127.0.0.1）。"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import torch
from transformers import AutoTokenizer, AutoModel

MODEL = os.environ.get('DGTF_EMBED_MODEL', 'D:/Meta-DGTF/local_model/models/bge-small-zh-v1.5')
PORT = int(os.environ.get('DGTF_EMBED_PORT', '8771'))
_tok = None
_model = None
_dev = 'cpu'
_lock = threading.Lock()


def _load():
    global _tok, _model, _dev
    if _model is not None:
        return
    _tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    _model = AutoModel.from_pretrained(MODEL, torch_dtype=torch.float16,
                                       trust_remote_code=True)
    _model.eval()
    _dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    _model.to(_dev)


def embed(texts):
    _load()
    out = []
    with _lock:
        for i in range(0, len(texts), 16):
            batch = [str(x)[:2000] for x in texts[i:i+16]]
            enc = _tok(batch, padding=True, truncation=True, max_length=512,
                       return_tensors='pt')
            enc = {k: v.to(_dev) for k, v in enc.items()}
            with torch.no_grad():
                v = _model(**enc).last_hidden_state[:, 0]
            v = torch.nn.functional.normalize(v.float(), p=2, dim=1)
            out.extend([[round(float(x), 5) for x in row] for row in v.cpu().tolist()])
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith('/health'):
            try:
                _load()
                self._send(200, {'ok': True, 'model': MODEL, 'dev': _dev,
                                 'dim': 512})
            except Exception as exc:
                self._send(500, {'ok': False, 'error': str(exc)})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.path.startswith('/embed'):
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
            texts = data.get('texts') or []
            if isinstance(texts, str):
                texts = [texts]
            if not texts:
                self._send(400, {'error': 'texts empty'})
                return
            self._send(200, {'ok': True, 'vectors': embed(texts)})
        except Exception as exc:
            self._send(500, {'ok': False, 'error': str(exc)})


if __name__ == '__main__':
    # 单实例锁：避免 app 重复启动多个 embedding 服务抢 GPU/端口。
    import msvcrt
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', 'dgtf_memory', 'rag_embed.lock')
    lock_path = os.path.abspath(lock_path)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    _lf = open(lock_path, 'a+')
    try:
        msvcrt.locking(_lf.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print('RAG_EMBED_ALREADY_RUNNING', PORT, flush=True)
        sys.exit(0)
    _lf.seek(0)
    _lf.truncate()
    _lf.write(str(os.getpid()))
    _lf.flush()
    _load()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    print('RAG_EMBED_READY', PORT, MODEL, flush=True)
    try:
        srv.serve_forever()
    finally:
        try:
            msvcrt.locking(_lf.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
