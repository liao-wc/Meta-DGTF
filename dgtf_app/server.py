# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 本地 HTTP 服务（仅监听 127.0.0.1）。

纯标准库 ThreadingHTTPServer。路由：

  GET  /                              → static/index.html
  GET  /static/<file>                 → 静态资源
  GET  /api/config                    → 引擎版本 / 凭据状态（不泄露值）/ 产物统计
  GET  /api/tasks                     → 任务列表
  POST /api/tasks                     → 新建任务 {question, opts}
  GET  /api/tasks/<id>                → 单任务状态
  GET  /api/tasks/<id>/log?offset=N   → 日志增量（按字节偏移）
  POST /api/tasks/<id>/cancel         → 取消任务
  GET  /api/tasks/<id>/result         → 产物正文
  GET  /api/outputs?q=&body=&days=…   → 历史产物列表 / 检索
  GET  /api/outputs/facets            → 筛选项集合
  GET  /api/outputs/<name>            → 单份产物正文

启动： python dgtf_app/server.py [--port 8765] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
sys.path.insert(0, str(APP_DIR))

import engine_runner as runner  # noqa: E402
import outputs_index as oi  # noqa: E402

_FACETS = ("decidability", "orientation", "parallel", "stop")


class Handler(BaseHTTPRequestHandler):
    server_version = "DGTFApp/1.0"

    def log_message(self, fmt, *args):  # 默认静默，--verbose 才打访问日志
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # ── 响应助手 ──────────────────────────────────────────────────
    def _json(self, obj, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self, rel: str):
        rel = rel.split("?", 1)[0].lstrip("/")
        base = STATIC_DIR.resolve()
        target = (base / rel).resolve()
        if base not in target.parents and target != base:
            return self._json({"error": "forbidden"}, 403)
        if not target.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── GET ───────────────────────────────────────────────────────
    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)

        if p in ("/", "/index.html"):
            return self._serve_static("index.html")
        if p.startswith("/static/"):
            return self._serve_static(p[len("/static/"):])

        if p == "/api/config":
            return self._json({
                "engine": runner.find_engine().name,
                "mock_default": os.environ.get("DGTF_APP_MOCK") == "1",
                "creds": runner.credential_status(),
                "outputs": oi.stats(),
                "max_concurrent": runner.MAX_CONCURRENT,
            })

        if p == "/api/tasks":
            return self._json({"tasks": runner.list_tasks()})

        m = re.match(r"^/api/tasks/([^/]+)/log$", p)
        if m:
            off = int((q.get("offset") or ["0"])[0] or 0)
            mode = (q.get("mode") or ["filtered"])[0]
            if mode not in ("raw", "filtered"):
                mode = "filtered"
            r = runner.read_log(m.group(1), off, mode)
            return self._json(r) if r is not None else self._json({"error": "not found"}, 404)

        m = re.match(r"^/api/tasks/([^/]+)/result$", p)
        if m:
            t = runner.get_task(m.group(1))
            if not t or not t.get("output_name"):
                return self._json({"error": "尚无产物"}, 404)
            return self._json({"name": t["output_name"],
                               "body": oi.read_body(t["output_name"])})

        m = re.match(r"^/api/tasks/([^/]+)$", p)
        if m:
            t = runner.get_task(m.group(1))
            return self._json(t) if t else self._json({"error": "not found"}, 404)

        if p == "/api/outputs":
            if (q.get("facets") or [""])[0] == "1":
                return self._json(oi.facets())
            body = (q.get("body") or ["0"])[0] == "1"
            filters: dict = {}
            for k in _FACETS:
                v = (q.get(k) or [""])[0]
                if v:
                    filters[k] = v
            days = (q.get("days") or [""])[0]
            if days:
                filters["days"] = days
            if (q.get("packed") or [""])[0] == "1":
                filters["has_packed"] = True
            recs = oi.search((q.get("q") or [""])[0], with_body=body, filters=filters)
            return self._json({"count": len(recs), "items": recs})

        if p == "/api/outputs/facets":
            return self._json(oi.facets())

        m = re.match(r"^/api/archive/(.+)$", p)
        if m:
            name = unquote(m.group(1))
            body = runner.read_archive(name)
            if body is None:
                return self._json({"error": "not found"}, 404)
            return self._json({"name": Path(name).name, "body": body})

        m = re.match(r"^/api/outputs/(.+)$", p)
        if m:
            name = unquote(m.group(1))
            body = oi.read_body(name)
            if not body:
                return self._json({"error": "not found"}, 404)
            return self._json({"name": Path(name).name, "body": body})

        return self._json({"error": "not found"}, 404)

    # ── POST ──────────────────────────────────────────────────────
    def do_POST(self):
        u = urlparse(self.path)
        p = u.path

        m = re.match(r"^/api/tasks/([^/]+)/cancel$", p)
        if m:
            ok = runner.cancel_task(m.group(1))
            return self._json({"ok": ok}, 200 if ok else 409)

        if p == "/api/tasks":
            data = self._read_json()
            question = (data.get("question") or "").strip()
            if not question:
                return self._json({"error": "问题不能为空"}, 400)
            opts = data.get("opts") or {}
            if not isinstance(opts, dict):
                opts = {}
            try:
                tid = runner.start_task(question, opts)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"id": tid}, 201)

        return self._json({"error": "not found"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser(description="元DGTF 本地 Web 应用")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.verbose = args.verbose
    srv.daemon_threads = True
    mock = "开" if os.environ.get("DGTF_APP_MOCK") == "1" else "关"
    print(f"元DGTF 应用已启动： http://{args.host}:{args.port}")
    print(f"  引擎：{runner.find_engine().name}")
    print(f"  mock：{mock}    并发上限：{runner.MAX_CONCURRENT}")
    print("  Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
