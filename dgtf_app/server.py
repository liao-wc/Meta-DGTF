# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 本地 HTTP 服务（默认只监听 127.0.0.1；`--lan` 放开到同一局域网）。

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
  GET  /api/chats                     → 历次「会话」（历史对话：内存任务 + 归档 run.json）
  GET  /api/params                    → 高级参数（yaml 摊平 + 中文说明 + 已改键）
  POST /api/params                    → 持久化写回用户配置 dgtf_config.user.yaml {overrides:{…}}
  POST /api/params/reset              → 恢复默认配置（删用户配置 ⇒ 回落到出厂 dgtf_config.yaml）
  GET  /api/dashboard                 → 工作台读数
  GET  /api/outputs?q=&body=&days=…   → 历史产物列表 / 检索
  GET  /api/outputs/facets            → 筛选项集合
  GET  /api/outputs/<name>            → 单份产物正文

启动： python dgtf_app/server.py [--port 8765] [--verbose]
       python dgtf_app/server.py --lan                 # 同一局域网可访问（**无口令**，谁都能操作）
       python dgtf_app/server.py --lan --token 口令     # 带访问口令（启动时会打印带 ?t= 的网址）
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
sys.path.insert(0, str(APP_DIR))

import dashboard as dash  # noqa: E402
import engine_runner as runner  # noqa: E402
import library as lib  # noqa: E402
import outputs_index as oi  # noqa: E402
import params as prm  # noqa: E402

_FACETS = ("decidability", "orientation", "parallel", "stop", "kind", "layer")


# ══ ★ R42：局域网访问（--lan）+ 可选访问口令（--token）═══════════════════════
# 默认仍然是**只监听 127.0.0.1**（最安全）；只有显式 `--lan` 才绑 0.0.0.0。
# 口令默认**关闭** —— 一开 `--lan`，同一网段里任何人都能跑任务（花 API 额度）、
# 删本地资料库导入的文件、翻全部产物。要收紧就 `--token <口令>`。
_TOKEN = ""

# ★ R44：导入是二进制上传（base64 后还要膨胀 1/3）⇒ 单独给一个大上限，超了 413。
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


def _routable(ip: str) -> bool:
    """这个地址能不能出网（= 有没有 IPv4 默认路由）。

    做法：把 UDP 套接字 **bind 到该地址**再 `connect` 一个公网 IP —— 内核必须按
    路由表选路，选不出来就抛 `WSAENETUNREACH`。**不发任何包**。
    用途：区分「真网卡」与 VMware/VBox 那种只能本地互访的 host-only 网卡。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((ip, 0))
            s.connect(("1.1.1.1", 53))
            return True
        finally:
            s.close()
    except OSError:
        return False


def lan_ips() -> list:
    """本机所有非回环 IPv4，按「能出网」优先排序 —— 返回 `[(ip, 能否出网), …]`。

    ★ 为什么**不能**只按「默认路由出口」排：那只是「去公网走哪块网卡」，
      跟「手机连在哪个网段」是两回事。实测这台机器上，默认路由出口是**有线**的
      192.168.1.5，而手机在 WiFi 上是 192.168.10.7 —— 标「首选」会把用户带沟里。
      ⇒ 所以只做「能出网的在前、只能本地互访的在后」，剩下的**让用户按网段自己挑**。
    """
    ips: list = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    pairs = [(ip, _routable(ip)) for ip in ips]
    return sorted(pairs, key=lambda t: (not t[1],))       # True（能出网）在前


def lan_ipv4() -> list:
    """只要地址（保持老签名 —— `_audit_tmp/_r42_lan.py` 在用）。"""
    return [ip for ip, _ok in lan_ips()]


def make_server(host: str, port: int, token: str = "", verbose: bool = False):
    """建好（**不启动**）服务。

    ★ 为什么抽出来：本机 sandbox 在命令结束时会把子进程全清掉 —— 验收只能在
      **同一个进程**里起服务（`_audit_tmp/_r42_lan.py` 就是这么用的）。
    """
    global _TOKEN
    _TOKEN = token
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.verbose = verbose
    srv.daemon_threads = True
    return srv


class Handler(BaseHTTPRequestHandler):
    # ★ HTTP/1.1 = 默认**长连接**（HTTP/1.0 每请求一连接 ⇒ 关一次就进 TIME_WAIT）。
    #   前端 1.5s 轮询 + 验收台密集轮询会把 TIME_WAIT 堆到上千条、把端口耗光，
    #   表现是「某个 fetch 再也不返回」（无头里虚拟时间还会因此停住、dump 不出来）。
    #   前提已满足：所有响应都显式带 Content-Length（见 _json / _serve_static）。
    protocol_version = "HTTP/1.1"
    server_version = "DGTFApp/1.0"

    def log_message(self, fmt, *args):  # 默认静默，--verbose 才打访问日志
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # ── 响应助手 ──────────────────────────────────────────────────
    def _download(self, data: bytes, ctype: str, filename: str, code: int = 200):
        """导出用的二进制响应（带 Content-Disposition）。"""
        self.send_response(code)
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        ascii_name = filename.encode("ascii", "ignore").decode() or "export"
        self.send_header("Content-Disposition",
                         "attachment; filename=\"%s\"; filename*=UTF-8''%s"
                         % (ascii_name, urllib.parse.quote(filename)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ── ★ R42：访问口令（只在 `--token` 时生效；默认 _TOKEN 为空 ⇒ 全部放行）──
    def _auth_note(self):
        """首次带 `?t=<口令>` 进来时，把口令种进 cookie。

        之后同源 `fetch` 会自动带上 ⇒ **手机上只要把那条带口令的网址存成书签**，
        不用在界面里做登录页。`SameSite=Lax` 够用（本站全部同源）。
        """
        if not _TOKEN:
            return None
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == _TOKEN:
            return ("dgtf_token=%s; Path=/; SameSite=Lax; Max-Age=2592000"
                    % _TOKEN)
        return None

    def _granted(self) -> bool:
        if not _TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == _TOKEN:
            return True
        return ("dgtf_token=" + _TOKEN) in (self.headers.get("Cookie") or "")

    def _guard(self) -> bool:
        """口令闸：不通过就 401（**不泄露**任何业务信息）。"""
        if self._granted():
            return True
        self._json({"error": "未授权：本服务启用了访问口令，请用启动时打印的带 ?t= 的网址打开"}, 401)
        return False

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
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # ★ 静态资源**必须**禁缓存：这些文件是「每次请求现读磁盘」的开发产物，
        #   浏览器一缓存，改完 CSS/JS 用户刷新拿到的还是旧版（改了半天看不到效果）。
        #   API 那边本来就有 no-store，静态资源这里以前漏了。
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ── GET ───────────────────────────────────────────────────────
    def do_GET(self):
        if not self._guard():          # ★ R42：口令开启时先过闸（默认关闭 ⇒ 恒真）
            return
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)

        if p in ("/", "/index.html"):
            return self._serve_static("index.html")
        if p.startswith("/static/"):
            return self._serve_static(p[len("/static/"):])

        if p == "/api/config":
            try:
                oi.reap_mock()          # 顺手回收过期的演练/验收产物
            except Exception:  # noqa: BLE001
                pass
            return self._json({
                "engine": runner.find_engine().name,
                "mock_default": os.environ.get("DGTF_APP_MOCK") == "1",
                "creds": runner.credential_status(),
                "outputs": oi.stats(),
                "max_concurrent": runner.MAX_CONCURRENT,
            })

        if p == "/api/params":
            return self._json(prm.load_params())

        if p == "/api/chats":
            return self._json({"chats": dash.list_chats()})

        if p == "/api/dashboard":
            d = dash.scan()
            d["engine"] = runner.find_engine().name
            d["creds"] = runner.credential_status()
            d["balance"] = runner.current_balance()
            d["tasks"] = runner.list_tasks()
            return self._json(d)

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

        m = re.match(r"^/api/tasks/([^/]+)/layers$", p)
        if m:
            r = runner.read_layers(m.group(1))
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
            try:
                oi.reap_mock()
            except Exception:  # noqa: BLE001
                pass
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

        # 本地资料库（导入的资料 → 外部证据锚点）/ 联网检索库
        if p == "/api/library/local":
            try:
                _obj = json.loads(lib.ANCHOR_FILE.read_text(
                    encoding="utf-8", errors="replace"))
                _n = lib._anchor_items(_obj)
            except (OSError, ValueError):
                _n = 0
            return self._json({
                "items": lib.imported_files(),
                "candidates": lib.local_anchors(),
                "anchor_file": str(lib.ANCHOR_FILE.relative_to(
                    lib.PROJECT_ROOT)).replace("\\", "/"),
                "anchor_items": _n,
            })
        if p == "/api/library/web":
            _flat = lib.web_hits_grouped()
            # ★ R45：`clusters` = 把同一任务的子问题挂到最初的问题下
            # （用户要求「按同一任务的问题归类」）。前端优先用它渲染，
            # 老前端拿 `groups` 也能照旧工作。
            return self._json({"items": lib.web_results(),
                               "hits": lib.web_hits(),
                               "groups": _flat,
                               "clusters": lib.cluster_groups(_flat)})
        m = re.match(r"^/api/library/local/(.+)$", p)
        if m:
            body = lib.read_local(unquote(m.group(1)))
            if body is None:
                return self._json({"error": "not found"}, 404)
            return self._json({"name": Path(m.group(1)).name, "body": body})

        # ── 导出：单份产物 ──────────────────────────────────────
        if p == "/api/export/output":
            name = Path((q.get("name") or [""])[0]).name
            body = oi.read_body(name)
            if not body:
                return self._json({"error": "not found"}, 404)
            return self._download(body.encode("utf-8"),
                                  "text/markdown; charset=utf-8", name)

        # ── 导出：当前筛选下的一批产物（含旁挂，打成一个 zip）────
        if p == "/api/export/outputs":
            # ★ R22：`names` 非空 ⇒ 只导**勾选的那几份**（并入同名旁挂文件）
            picked = [n for n in (q.get("names") or []) if n.strip()]
            if picked:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for raw in picked:
                        nm = Path(raw).name
                        stamp = nm[:-3] if nm.endswith(".md") else nm
                        for f in sorted(oi.OUTPUTS_DIR.glob(stamp + "*")):
                            if f.is_file():
                                try:
                                    z.write(f, arcname=f.name)
                                except OSError:
                                    pass
                if not buf.getvalue():
                    return self._json({"error": "没有可导出的产物"}, 404)
                ts0 = time.strftime("%Y%m%d_%H%M%S")
                return self._download(buf.getvalue(), "application/zip",
                                      "元DGTF_选中产物_%s.zip" % ts0)
            body = (q.get("body") or ["0"])[0] == "1"
            filters: dict = {}
            for k in _FACETS:
                v = (q.get(k) or [""])[0]
                if v:
                    filters[k] = v
            days = (q.get("days") or [""])[0]
            if days:
                filters["days"] = days
            recs = oi.search((q.get("q") or [""])[0], with_body=body,
                             filters=filters)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for r in recs:
                    stamp = r["name"][:-3] if r["name"].endswith(".md") else r["name"]
                    for f in sorted(oi.OUTPUTS_DIR.glob(stamp + "*")):
                        if f.is_file():
                            try:
                                z.write(f, arcname=f.name)
                            except OSError:
                                pass
            if not buf.getvalue():
                return self._json({"error": "没有可导出的产物"}, 404)
            ts = time.strftime("%Y%m%d_%H%M%S")
            return self._download(buf.getvalue(), "application/zip",
                                  "元DGTF_产物_%s.zip" % ts)

        # ── 导出：联网检索库（按问题聚合的 md）────────────────────
        if p == "/api/export/web":
            groups = lib.web_hits_grouped()
            picked_q = [x for x in (q.get("qs") or []) if x]
            picked_ts = {x for x in (q.get("ts") or []) if x}
            kw = ((q.get("q") or [""])[0] or "").strip().lower()
            lines = ["# 元DGTF · 联网检索库", "",
                     "**导出时间**: " + time.strftime("%Y-%m-%dT%H:%M:%S"), ""]
            n_g = 0
            for g in groups:
                # ★ 分组的字段是 query/items（不是 question/hits）—— 写错会让「只导勾选的组」
                #   永远匹配不上（title 恒为空）⇒ 整份导出被判成空的 404。
                title = str(g.get("query") or g.get("question") or "")
                hits = g.get("items") or g.get("hits") or []
                if picked_q:                      # ★ 只导勾选的组
                    if title not in picked_q:
                        continue
                elif picked_ts:                   # ★ 平铺模式：只留勾选的命中
                    hits = [h for h in hits if str(h.get("ts")) in picked_ts]
                    if not hits:
                        continue
                elif kw and kw not in title.lower() and not any(
                        kw in str(h.get("title", "")).lower() for h in hits):
                    continue
                n_g += 1
                lines.append("## " + title)
                lines.append("")
                lines.append("- 去重后 %d 条 · 日期 %s · 检索模型 %s"
                             % (len(hits), g.get("time", ""), g.get("model", "")))
                lines.append("")
                for h in hits:
                    lines.append("- [%s](%s)" % (h.get("title", ""), h.get("url", "")))
                lines.append("")
            if not n_g:
                return self._json({"error": "没有可导出的条目"}, 404)
            ts = time.strftime("%Y%m%d_%H%M%S")
            return self._download("\n".join(lines).encode("utf-8"),
                                  "text/markdown; charset=utf-8",
                                  "元DGTF_联网检索库_%s.md" % ts)

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
        if not self._guard():          # ★ R42：口令开启时先过闸（默认关闭 ⇒ 恒真）
            return
        u = urlparse(self.path)
        p = u.path

        # 本地资料库：导入 / 删除
        if p == "/api/library/import":
            _n = int(self.headers.get("Content-Length") or 0)
            if _n > MAX_UPLOAD_BYTES:
                return self._json({"error": "请求体 %.1fMB 超过上限 %.0fMB（请分批导入）"
                                            % (_n / 1048576.0, MAX_UPLOAD_BYTES / 1048576.0)},
                                  413)
            data = self._read_json()
            files = data.get("files")
            if not isinstance(files, list) or not files:
                return self._json({"error": "files 不能为空"}, 400)
            return self._json(lib.import_files(files))

        if p == "/api/library/delete":
            data = self._read_json()
            ok = lib.delete_imported(str(data.get("name") or ""))
            return self._json({"ok": ok}, 200 if ok else 404)

        # ★ 高级参数「保存」：把改动**持久化写回用户配置** dgtf_config.user.yaml
        #   （出厂 dgtf_config.yaml 是只读基线，前端永不改它）。
        #   与「仅本次任务生效」（走 opts.overrides → 临时 config）是两条路。
        if p == "/api/params":
            data = self._read_json()
            ov = data.get("overrides")
            if not isinstance(ov, dict):
                return self._json({"error": "overrides 必须是对象"}, 400)
            res = prm.save_params(ov)
            code = 500 if res.get("error") else 200
            return self._json(res, code)

        # ★「恢复默认配置」：删用户配置 ⇒ 全部键回落到出厂 dgtf_config.yaml。
        if p == "/api/params/reset":
            res = prm.reset_params()
            code = 500 if res.get("error") else 200
            return self._json(res, code)

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
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（默认只监听本机回环）")
    ap.add_argument("--lan", action="store_true",
                    help="绑 0.0.0.0：同一局域网内的其它设备也能访问（默认只监听 127.0.0.1）")
    ap.add_argument("--token", nargs="?", const="@gen", default="",
                    help="访问口令（不带值时自动生成）。开启后所有请求都要带它；"
                         "启动时会打印带 ?t= 的网址")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # ★ R42：`--lan` 是 `--host 0.0.0.0` 的语义化写法；两者都给时以 `--lan` 为准。
    host = "0.0.0.0" if args.lan else args.host
    token = ""
    if args.token:
        token = args.token
        if token == "@gen":
            token = secrets.token_urlsafe(9)
        token = re.sub(r"[^A-Za-z0-9_-]", "", token)
        if len(token) < 6:
            print("口令太短（至少 6 位，只允许字母 / 数字 / _ / -）—— 换一个再试。")
            return 2

    # ★★ 启动时先回填「孤儿任务」：上次服务被强杀/崩溃时，任务表（进程内存）连同
    #    未归档的进度一起没了，但 `<tid>.run.json` 活痕迹还留在盘上。
    #    把它们标成 `interrupted` + 原因 ⇒ 历史对话 / 产物库 / 最近跑过**三处都能看到**。
    try:
        orphans = runner.recover_orphans()
        if orphans:
            dash.invalidate()
            oi.invalidate()
            print(f"  回填中断任务：{len(orphans)} 条 → " +
                  "、".join(str(o.get("question") or o.get("id"))[:18] for o in orphans))
    except Exception as e:  # noqa: BLE001    回填失败不该拖垮启动
        print(f"  回填中断任务失败（忽略）：{type(e).__name__}: {e}")

    srv = make_server(host, args.port, token=token, verbose=args.verbose)
    mock = "开" if os.environ.get("DGTF_APP_MOCK") == "1" else "关"
    print(f"元DGTF 应用已启动： http://127.0.0.1:{args.port}")
    if host == "0.0.0.0":
        print("  局域网已打开（同一 WiFi / 同网段的设备可以访问）：")
        _ips = lan_ips()
        for _ip, _ok in (_ips or [("<本机内网 IP，用 ipconfig 查>", False)]):
            if not _ips:
                _tag = ""
            elif _ok:
                _tag = "   （真网卡）"
            else:
                _tag = "   （隔离/虚拟网卡，手机一般连不上）"
            print("    http://%s:%d%s%s" % (_ip, args.port,
                                            ("/?t=" + token) if token else "", _tag))
        print("  · 手机连的 WiFi 是哪个网段，就开**同一网段**那条（前三位数字对上）——")
        print("    手机「设置 → WLAN → 当前网络」里能看到自己的 IP；")
        print("    拿不准就把上面两条「真网卡」各试一遍（各 10 秒），虚拟网卡那条不用试。")
        print("  · 网址**必须带 http://**：不少手机浏览器会自动改成 https，")
        print("    表现就是「无法建立加密连接」。真跳了就关掉浏览器里的")
        print("    「始终使用安全连接 / HTTPS-First」再打开。")
        if not token:
            print("  ⚠ 没设口令：同一网络里任何人都能操作这个应用"
                  "（跑任务花 API 额度、删本地资料库导入的文件）。")
            print("    要收紧就加 `--token <你定的口令>`；只是临时用一下，用完 Ctrl+C 关掉即可。")
    else:
        print("  （只监听本机；要让同一局域网访问，加 --lan）")
    if token:
        print("  访问口令已启用：网址要带 ?t=<口令>（首次打开会自动记进 cookie）")
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
