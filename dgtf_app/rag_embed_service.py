# -*- coding: utf-8 -*-
"""本地 BGE embedding HTTP 服务（仅 127.0.0.1）。"""
import hashlib, json, os, sys, threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModel

#: 默认按本文件定位模型，避免写死盘符/仓库绝对路径（迁移或换盘即失效）。
_ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get('DGTF_EMBED_MODEL',
                       str(_ROOT / 'local_model' / 'models' / 'bge-small-zh-v1.5'))
PORT = int(os.environ.get('DGTF_EMBED_PORT', '8771'))
_tok = None
_model = None
_dev = 'cpu'
_lock = threading.Lock()
_CACHE = OrderedDict()
_CACHE_MAX = int(os.environ.get('DGTF_EMBED_CACHE_MAX', '1024'))
_CACHE_HITS = 0
_CACHE_MISSES = 0
_CACHE_LOCK = threading.Lock()


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


def _cache_stats():
    with _CACHE_LOCK:
        return {'size': len(_CACHE), 'max': _CACHE_MAX,
                'hits': _CACHE_HITS, 'misses': _CACHE_MISSES}


def embed(texts):
    """批量 embedding；文本级 LRU 缓存（重复文本直接命中，向量逐位一致）。"""
    _load()
    global _CACHE_HITS, _CACHE_MISSES
    keys = []
    for x in texts:
        t = str(x)[:2000]
        keys.append(hashlib.sha256(t.encode('utf-8')).hexdigest())
    out = [None] * len(texts)
    missing = []
    with _CACHE_LOCK:
        for i, k in enumerate(keys):
            if k in _CACHE:
                out[i] = list(_CACHE[k])
                _CACHE.move_to_end(k)
                _CACHE_HITS += 1
            else:
                missing.append(i)
    if missing:
        miss_texts = [str(texts[i])[:2000] for i in missing]
        vecs = []
        with _lock:
            for i in range(0, len(miss_texts), 16):
                batch = miss_texts[i:i+16]
                enc = _tok(batch, padding=True, truncation=True, max_length=512,
                           return_tensors='pt')
                enc = {k: v.to(_dev) for k, v in enc.items()}
                with torch.no_grad():
                    v = _model(**enc).last_hidden_state[:, 0]
                v = torch.nn.functional.normalize(v.float(), p=2, dim=1)
                vecs.extend([[round(float(x), 5) for x in row]
                             for row in v.cpu().tolist()])
        with _CACHE_LOCK:
            for idx, vec in zip(missing, vecs):
                out[idx] = vec
                _CACHE[keys[idx]] = tuple(vec)
                _CACHE.move_to_end(keys[idx])
                _CACHE_MISSES += 1
                while len(_CACHE) > _CACHE_MAX:
                    _CACHE.popitem(last=False)
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
                                 'dim': 512, 'cache': _cache_stats()})
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
