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

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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






def _git(args, timeout=60):
    import subprocess as _sp
    root = Path(__file__).resolve().parent.parent
    p = _sp.run(["git"] + list(args), cwd=str(root),
                text=True, encoding="utf-8", errors="replace",
                capture_output=True, timeout=timeout)
    return {"ok": p.returncode == 0, "out": (p.stdout or "")[-4000:],
            "err": (p.stderr or "")[-2000:]}


def _git_snapshot():
    r = _git(["status", "--porcelain"])
    return set(x[3:].strip() for x in (r.get("out") or "").splitlines()
               if len(x) > 3)

def _git_status():
    br = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    st = _git(["status", "--porcelain"])
    rem = _git(["remote", "-v"])
    last = _git(["log", "-1", "--oneline"])
    return {"branch": (br.get("out") or "").strip(),
            "changes": len([x for x in (st.get("out") or "").splitlines()
                            if x.strip()]),
            "remote": (rem.get("out") or "").splitlines()[:2],
            "last": (last.get("out") or "").strip()}


def _open_github_desktop():
    import os as _os
    import subprocess as _sp
    exe = _os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe")
    if not Path(exe).exists():
        return {"ok": False, "error": "GitHub Desktop 未安装"}
    root = Path(__file__).resolve().parent.parent
    try:
        _sp.Popen([exe, "--repository", str(root)], close_fds=True)
        return {"ok": True, "opened": str(root)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _auto_commit(before: set, task: str, before_head: str = ""):
    after = _git_snapshot()
    new = sorted(after - before)
    if not new:
        ah = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
        if before_head and ah and ah != before_head:
            return {"committed": True, "changed": [],
                    "commit": (_git(["log", "-1", "--oneline"]).get("out") or "").strip(),
                    "why": "DSH Agent 已自行提交本次变更"}
        return {"committed": False, "changed": [], "why": "本次没有新增文件变更"}
    a = _git(["add", "--"] + new)
    if not a.get("ok"):
        return {"committed": False, "changed": new, "error": a.get("err")}
    msg = "DSH Agent auto-repair: " + str(task)[:80]
    c = _git(["commit", "-m", msg])
    return {"committed": bool(c.get("ok")), "changed": new,
            "commit": (c.get("out") or "").strip()[-200:],
            "error": "" if c.get("ok") else c.get("err")}


def _dsh_session_dir():
    d = Path(__file__).resolve().parent.parent / "dgtf_memory" / "dsh_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_dsh_run(task, sid, out, auto_repair=False):
    import json as _json
    import time as _time
    d = _dsh_session_dir()
    sid = str(sid or ("session-" + str(int(_time.time() * 1000))))
    rec = {"id": sid, "task": str(task)[:8000], "ts": _time.time(),
           "auto_repair": bool(auto_repair), "ok": bool(out.get("ok")),
           "text": str(out.get("text") or "")[:20000],
           "events": list(out.get("events") or [])[-200:],
           "gate": out.get("gate"), "repair": out.get("repair")}
    (d / (sid + ".json")).write_text(
        _json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        ad = d.parent / "dsh_artifacts"
        ad.mkdir(parents=True, exist_ok=True)
        md = ["# DSH Agent 产物", "", "- session: %s" % sid,
              "- task: %s" % str(task),
              "- auto_repair: %s" % bool(auto_repair),
              "- gate: %s" % (out.get("gate") or "—"),
              "- repair: %s" % (out.get("repair") or "—"),
              "", "## 回答", "", str(out.get("text") or ""), "",
              "## 事件", "", "```json",
              _json.dumps(out.get("events") or [], ensure_ascii=False, indent=1),
              "```", ""]
        (ad / (sid + ".md")).write_text("\n".join(md), encoding="utf-8")
    except Exception:
        pass
    return sid


def _list_dsh_sessions(limit=50):
    import json as _json
    rows = []
    for p in sorted(_dsh_session_dir().glob("*.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            d = _json.loads(p.read_text(encoding="utf-8"))
            rows.append({"id": d.get("id"), "task": d.get("task"),
                         "ts": d.get("ts"), "ok": d.get("ok"),
                         "auto_repair": d.get("auto_repair"),
                         "repair": d.get("repair"),
                         "text": (d.get("text") or "")[:300]})
        except Exception:
            pass
    return rows


def _get_dsh_session(sid):
    import json as _json
    p = _dsh_session_dir() / (str(sid) + ".json")
    if not p.exists():
        return {}
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _proposal_dir():
    d = Path(__file__).resolve().parent.parent / "dgtf_memory" / "dsh_proposals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_proposal(rec):
    import json as _json
    import time as _time
    pid = str(rec.get("id") or ("prop-" + str(int(_time.time() * 1000))))
    rec["id"] = pid
    (_proposal_dir() / (pid + ".json")).write_text(
        _json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def _list_proposals(limit=100):
    import json as _json
    rows = []
    for p in sorted(_proposal_dir().glob("*.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            rows.append(_json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return rows


def _get_proposal(pid):
    import json as _json
    p = _proposal_dir() / (str(pid) + ".json")
    if not p.exists():
        return {}
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _dsh_artifact_dir():
    d = Path(__file__).resolve().parent.parent / "dgtf_memory" / "dsh_artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _list_dsh_artifacts(limit=50):
    rows = []
    for p in sorted(_dsh_artifact_dir().glob("*.md"),
                    key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")[:2000]
            task = p.stem
            for ln in txt.splitlines():
                if ln.startswith("- task:"):
                    task = ln.split(":", 1)[1].strip()
                    break
            rows.append({"id": p.stem, "size": p.stat().st_size,
                         "task": task})
        except Exception:
            pass
    return rows


def _read_dsh_artifact(sid):
    p = _dsh_artifact_dir() / (str(sid) + ".md")
    if not p.exists():
        return {}
    try:
        return {"id": str(sid),
                "body": p.read_text(encoding="utf-8", errors="replace")}
    except Exception:
        return {}


def _run_dsh_agent(task: str, sid: str = "", timeout: int = 300,
                   auto_repair: bool = False, effort: str = "",
                   permission: str = "") -> dict:
    """调用本机 DeepSeek Harness headless Agent；返回 NDJSON 事件映射。"""
    import os as _os
    import subprocess as _sp
    root = Path(__file__).resolve().parent.parent
    _before = _git_snapshot()
    _before_head = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
    dsh = _os.getenv("DSH_BIN") or str(Path(
        _os.getenv("LOCALAPPDATA", "")) /
        "Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd")
    if not Path(dsh).exists():
        return {"ok": False, "error": "找不到 dsh headless：%s" % dsh,
                "events": [], "text": "", "session_id": sid}
    key = _os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        try:
            for line in (root / ".env").read_text(
                    encoding="utf-8", errors="replace").splitlines():
                if line.startswith("DGTF_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            key = ""
    env = dict(_os.environ)
    if key:
        env["DEEPSEEK_API_KEY"] = key
    env.setdefault("DSH_HOME", str(Path.home() / ".dsh"))
    _perm = str(permission or "").strip()
    if _perm not in ("read-only", "workspace-write", "danger-full-access"):
        _perm = "workspace-write"
    env["DSH_PERMISSION_MODE"] = _perm
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    _anchors = Path(__file__).resolve().parent / "anchors"
    _imports = []
    try:
        if _anchors.is_dir():
            _imports = [str(p) for p in sorted(
                _anchors.iterdir(), key=lambda x: x.stat().st_mtime,
                reverse=True)[:20] if p.is_file()
                and p.name != "external_anchor.json"]
    except Exception:
        _imports = []
    _extra = ""
    if _imports:
        _extra = ("\napp 导入文件（可直接读取）：\n- "
                  + "\n- ".join(_imports))
    _mode = ("你可以直接修改项目源码/文件；若修改源码，必须运行 "
             "python fast_gate.py 并保证通过；不要执行 git add / git commit / push，"
             "由工作台统一提交本次变更。"
             if auto_repair else "只读模式：不要修改项目文件。")
    auth = ("你在元DGTF项目根目录：%s。你有权读取该工作区内的项目文件、"
            "outputs/ 产物、docs/、dgtf_memory/、app 导入文件与配置；"
            "%s 不要泄露密钥。%s\n用户请求：%s"
            % (root, _mode, _extra, task))
    _patch = None
    _pl = []
    _eff = str(effort or "").strip()
    if _eff in ("low", "medium", "high", "max"):
        _pl += ["- id: agent-default-model",
                "  name: \"@deepseek-ai/dsh-agent-default-model\"",
                "  config:",
                "    provider: deepseek-official",
                "    model: deepseek-flash",
                "    reasoningEffort: " + _eff]
    if _perm:
        _pl += ["- id: permission",
                "  name: '@deepseek-ai/dsh-permission-presets'",
                "  config:",
                "    defaultPreset: " + _perm]
    if _pl:
        import tempfile as _tf
        _fd, _patch = _tf.mkstemp(prefix="dgtf-dsh-", suffix=".yml")
        _os.close(_fd)
        Path(_patch).write_text("\n".join(_pl) + "\n", encoding="utf-8")
        cmd = [_os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", dsh,
               "--profile", "headless", "--patch", _patch, "--json"]
    else:
        cmd = [_os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", dsh,
               "headless", "--json"]
    if sid:
        cmd += ["--session-id", sid]
    cmd += ["-"]
    try:
        p = _sp.run(cmd, cwd=str(root), env=env, input=auth,
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True, timeout=timeout)
    finally:
        if _patch:
            try: Path(_patch).unlink()
            except Exception: pass
    events, texts, final = [], [], ""
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        events.append(ev)
        if ev.get("type") == "text" and ev.get("text"):
            texts.append(str(ev["text"]))
        if ev.get("type") == "session" and ev.get("sessionId"):
            sid = str(ev["sessionId"])
        if ev.get("type") == "final":
            final = str(ev.get("text") or "")
    out = {"ok": p.returncode == 0, "session_id": sid,
           "text": final or "".join(texts),
           "events": events[-200:],
           "settings": {"effort": _eff, "permission": _perm},
           "stderr": (p.stderr or "")[-2000:]}
    _save_dsh_run(task, sid, out, auto_repair)
    if auto_repair and out["ok"]:
        import subprocess as _sp
        import sys as _sys
        try:
            g = _sp.run([_sys.executable, "fast_gate.py"], cwd=str(root),
                        text=True, encoding="utf-8", errors="replace",
                        capture_output=True, timeout=300)
            out["gate"] = {"ok": g.returncode == 0,
                           "tail": ((g.stdout or "") + (g.stderr or ""))[-1200:]}
            if g.returncode == 0:
                out["repair"] = _auto_commit(_before, task, _before_head)
            else:
                out["repair"] = {"committed": False, "why": "fast_gate 未通过"}
        except Exception as exc:
            out["repair"] = {"committed": False, "why": str(exc)}
    return out


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

        if p == "/api/agent/knowledge":
            try:
                path = "dgtf_memory/agent_knowledge.jsonl"
                lines = Path(path).read_text(encoding="utf-8").splitlines()[-100:] if Path(path).exists() else []
                return self._json({"items": [__import__("json").loads(x) for x in lines if x.strip()]})
            except Exception as exc:
                return self._json({"items": [], "error": str(exc)})
        m = re.match(r"^/api/dsh/sessions/([^/]+)$", p)
        if m:
            return self._json(_get_dsh_session(unquote(m.group(1))))
        m = re.match(r"^/api/dsh/proposals/([^/]+)$", p)
        if m:
            return self._json(_get_proposal(unquote(m.group(1))))
        if p == "/api/dsh/proposals":
            return self._json({"proposals": _list_proposals()})
        m = re.match(r"^/api/dsh/artifacts/([^/]+)$", p)
        if m:
            return self._json(_read_dsh_artifact(unquote(m.group(1))))
        if p == "/api/dsh/artifacts":
            return self._json({"artifacts": _list_dsh_artifacts()})
        if p == "/api/dsh/sessions":
            return self._json({"sessions": _list_dsh_sessions()})
        if p == "/api/git/status":
            return self._json(_git_status())
        if p == "/api/agent/results":
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_worker import _read_results
                return self._json({"results": _read_results(
                    "dgtf_memory/agent_results.jsonl")[-200:]})
            except Exception as exc:
                return self._json({"results": [], "error": str(exc)})
        if p == "/api/agent/tasks":
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_bridge import read_tasks
                return self._json({"tasks": read_tasks(limit=200)})
            except Exception as exc:
                return self._json({"tasks": [], "error": str(exc)})
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
            try:
                d["dsh_sessions"] = _list_dsh_sessions(20)
            except Exception:
                d["dsh_sessions"] = []
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
            if (q.get("packed") or [""])[0] == "1":
                return self._json({"name": t["output_name"],
                                   "packed": oi.read_packed(t["output_name"])})
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
            # ★ R47：先 unquote 再取文件名 —— 老写法把**编码串**当名字返回
            #   （`name` 字段是 `%E8%80%81…` 而不是真文件名）。
            _nm = unquote(m.group(1))
            body = lib.read_local(_nm)
            if body is None:
                return self._json({"error": "not found"}, 404)
            return self._json({"name": Path(_nm).name, "body": body})

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

        m = re.match(r"^/api/outputs/(.+)/packed$", p)
        if m:
            name = unquote(m.group(1))
            d = oi.read_packed(name)
            return self._json({"name": Path(name).name, "packed": d})                 if d else self._json({"error": "not found"}, 404)
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
        if p == "/api/agent/tasks":
            data = self._read_json()
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_bridge import append_task
                task = {"kind": str(data.get("kind") or "user_task"),
                        "severity": str(data.get("severity") or "med"),
                        "title": str(data.get("title") or data.get("text") or ""),
                        "detail": str(data.get("detail") or data.get("text") or "")[:4000],
                        "source_run": "app_user"}
                return self._json({"task": append_task(task)})
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/agent/knowledge":
            data = self._read_json()
            qs = data.get("queries") or ["DeepSeek API 更新日志", "DeepSeek V4.1 Flash 新功能"]
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_bridge import refresh_knowledge_http
                return self._json({"items": refresh_knowledge_http(qs)})
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/git/status":
            return self._json(_git_status())
        if p == "/api/git/open":
            return self._json(_open_github_desktop())
        if p == "/api/git/commit":
            data = self._read_json()
            msg = str(data.get("message") or "").strip()
            if not msg:
                return self._json({"error": "message 不能为空"}, 400)
            _git(["add", "-A"])
            r = _git(["commit", "-m", msg])
            return self._json(r)
        if p == "/api/dsh/autorepair":
            try:
                import sys as _sys
                import time as _tm
                data = self._read_json()
                _custom = str(data.get("task") or "").strip()
                if _custom:
                    t = {"title": _custom[:200], "detail": _custom,
                         "kind": "user_task", "severity": "med"}
                else:
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    from dgtf_v2.agent_bridge import read_tasks
                    tasks = [x for x in read_tasks(limit=100)
                             if x.get("kind") in ("process_gap", "audit_gap",
                                                  "api_gap", "quality_flag")]
                    tasks.sort(key=lambda x: {"high": 0, "med": 1, "low": 2}.get(
                        str(x.get("severity")), 3))
                    if not tasks:
                        return self._json({"ok": False,
                                           "text": "没有可自审的任务"})
                    t = tasks[0]
                prompt = ("提案模式：不要读取项目文件、不要修改源码。只根据下面任务详情"
                          "输出简短修复提案（≤200字）：涉及文件、步骤、风险、验证命令。"
                          "任务：" + str(t.get("title") or "") + "。详情："
                          + str(t.get("detail") or "")[:1200])
                res = _run_dsh_agent(prompt, "", timeout=180, auto_repair=False)
                pid = "prop-" + str(int(_tm.time() * 1000))
                prop = _save_proposal({"id": pid, "ts": _tm.time(), "task": t,
                    "plan": str(res.get("text") or ""),
                    "session_id": res.get("session_id") or "",
                    "status": "pending", "approver": "",
                    "events": list(res.get("events") or [])[-50:]})
                return self._json({"ok": bool(res.get("ok")), "proposal": prop})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p.startswith("/api/dsh/proposals/") and p.endswith("/approve"):
            data = self._read_json()
            pid = p.split("/")[4]
            prop = _get_proposal(pid)
            if not prop:
                return self._json({"error": "proposal not found"}, 404)
            prompt = ("按以下已批准提案执行修复：" + str(prop.get("plan") or "")
                      + "。修改后运行 fast_gate.py，通过后只提交本次变更，不 push。")
            res = _run_dsh_agent(prompt, str(prop.get("session_id") or ""),
                                 timeout=600, auto_repair=True)
            prop["status"] = ("applied" if (res.get("repair") or {}).get("committed")
                              else "failed")
            prop["approver"] = str(data.get("mode") or "user")
            import time as _tm2
            prop["approved_ts"] = _tm2.time()
            prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                              "repair": res.get("repair")}
            _save_proposal(prop)
            return self._json({"ok": bool(res.get("ok")), "proposal": prop,
                               "result": res})
        if p == "/api/dsh/agent":
            data = self._read_json()
            task = str(data.get("task") or "").strip()
            if not task:
                return self._json({"error": "task 不能为空"}, 400)
            if len(task) > 8000:
                task = task[:8000]
            sid = str(data.get("session_id") or "").strip()
            try:
                res = _run_dsh_agent(task, sid,
                                     auto_repair=bool(data.get("auto_repair")),
                                     effort=str(data.get("effort") or ""),
                                     permission=str(data.get("permission") or ""))
                return self._json(res)
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/agent/apply":
            data = self._read_json()
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_repair import apply_patch
                return self._json(apply_patch(str(data.get("patch") or ""),
                                              str(data.get("approve") or "")))
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/agent/run":
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_worker import run_once, write_proposals
                res = run_once()
                prop = write_proposals()
                return self._json({"run": res, "proposals": prop})
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
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
