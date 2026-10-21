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






_DSH_ACTIVE = set()
_DSH_CONV = {}
_DSH_CONV_ACTIVE = set()
_DSH_CONV_LOCK = None   # 延迟创建，避免顶层 import threading
_AUTO_JOBS = {}
_AUTO_JOBS_LOCK = None

# ── 常驻 Agent 守护：app 启动时拉起 agent_daemon.py ─────────────────
# 定位：只做「本地队列消费 + 修复提案」，不联网、不调 LLM、不碰源码；
# DSH 对话仍是按需拉起的一次性 headless 进程，不在本守护内。
_AGENT_DAEMON = {
    "proc": None, "pid": 0, "interval": 60.0, "knowledge_every": 0,
    "log": None, "pid_file": None, "stop_file": None,
}


def _agent_daemon_paths():
    root = Path(__file__).resolve().parent.parent
    mem = root / "dgtf_memory"
    return {
        "root": root,
        "script": root / "agent_daemon.py",
        "log": mem / "agent_daemon.log",
        "stdout": mem / "agent_daemon.stdout.log",
        "pid": mem / "agent_daemon.app.pid",
        "stop": mem / "agent_daemon.app.stop",
    }


def _pid_alive(pid) -> bool:
    """跨平台判断 PID 是否还活着（Windows 用 GetExitCodeProcess）。"""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.OpenProcess.restype = ctypes.c_void_p
            k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool,
                                      ctypes.c_ulong]
            k.GetExitCodeProcess.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            k.CloseHandle.argtypes = [ctypes.c_void_p]
            h = k.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return code.value == 259            # STILL_ACTIVE
            finally:
                k.CloseHandle(h)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _mtime_age(path):
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except Exception:
        return None


def _read_last_log(path, limit=2000):
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - limit))
            rows = f.read().decode("utf-8", "replace").strip().splitlines()
        return rows[-1] if rows else ""
    except Exception:
        return ""


def agent_daemon_status():
    """返回常驻 Agent 的只读状态；不启动、不修改任何东西。"""
    paths = _agent_daemon_paths()
    proc = _AGENT_DAEMON.get("proc")
    managed = bool(proc is not None and proc.poll() is None)
    pid = int(proc.pid) if managed else 0
    if not managed:
        try:
            pid = int(paths["pid"].read_text(encoding="utf-8").strip())
        except Exception:
            pid = 0
        if not _pid_alive(pid):
            pid = 0
    age = _mtime_age(paths["log"])
    # 兼容改造前已手动/开机启动的实例：没有 pid 文件，但日志仍在写。
    # 轮询间隔 60s，150s 内有过 cycle 就视为活着，避免再起一份。
    recent = bool(age is not None and age < 150)
    running = bool(managed or pid or recent)
    return {
        "running": running,
        "managed": managed,
        "pid": pid,
        "interval": _AGENT_DAEMON.get("interval", 60.0),
        "knowledge_every": _AGENT_DAEMON.get("knowledge_every", 0),
        "log_age_s": None if age is None else round(age, 1),
        "last_log": _read_last_log(paths["log"]),
        "log": str(paths["log"]),
    }


def start_agent_daemon(interval: float = 60.0,
                       knowledge_every: int = 0) -> dict:
    """确保常驻 Agent 在跑；已在跑就复用，不重复拉起。"""
    paths = _agent_daemon_paths()
    if not paths["script"].is_file():
        return {"ok": False, "running": False,
                "error": "找不到 %s" % paths["script"]}
    force = str(os.environ.get("DGTF_APP_AGENT_DAEMON_FORCE") or "") == "1"
    cur = agent_daemon_status()
    if cur.get("running") and not force:
        cur.update({"ok": True, "started": False,
                    "why": "已有实例在运行，复用"})
        return cur

    import subprocess as _sp
    try:
        paths["stop"].unlink(missing_ok=True)
    except Exception:
        pass
    flags = getattr(_sp, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    out = None
    try:
        paths["stdout"].parent.mkdir(parents=True, exist_ok=True)
        out = open(paths["stdout"], "ab")
        cmd = [sys.executable, str(paths["script"]),
               "--interval", str(float(interval)),
               "--knowledge-every", str(int(knowledge_every)),
               "--stop-file", str(paths["stop"])]
        proc = _sp.Popen(
            cmd, cwd=str(paths["root"]), stdin=_sp.DEVNULL,
            stdout=out, stderr=_sp.STDOUT, creationflags=flags,
            close_fds=True)
    except Exception as exc:
        return {"ok": False, "running": False,
                "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        if out is not None:
            try:
                out.close()
            except Exception:
                pass

    _AGENT_DAEMON.update({
        "proc": proc, "pid": int(proc.pid),
        "interval": float(interval), "knowledge_every": int(knowledge_every),
        "log": paths["log"], "pid_file": paths["pid"],
        "stop_file": paths["stop"],
    })
    try:
        paths["pid"].write_text(str(proc.pid), encoding="utf-8")
    except Exception:
        pass
    time.sleep(0.4)         # 给异常退出（缺依赖/参数错）一个暴露窗口
    if proc.poll() is not None:
        return {"ok": False, "running": False, "pid": int(proc.pid),
                "error": "agent_daemon 启动后立即退出，见 %s"
                         % paths["stdout"]}
    st = agent_daemon_status()
    st.update({"ok": True, "started": True, "why": "已启动"})
    return st


def stop_agent_daemon(timeout: float = 4.0) -> dict:
    """只停本进程拉起的实例；外部/复用实例不动。"""
    proc = _AGENT_DAEMON.get("proc")
    paths = _agent_daemon_paths()
    if proc is None or proc.poll() is not None:
        _AGENT_DAEMON["proc"] = None
        try:
            paths["stop"].unlink(missing_ok=True)
        except Exception:
            pass
        try:
            paths["pid"].unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": True, "stopped": False}

    try:
        paths["stop"].write_text("stop", encoding="utf-8")
    except Exception:
        pass
    try:
        proc.wait(timeout=1.5)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _AGENT_DAEMON["proc"] = None
    try:
        paths["stop"].unlink(missing_ok=True)
    except Exception:
        pass
    try:
        paths["pid"].unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True, "stopped": True}


def _git(args, timeout=60, stdin_text=None, limit=4000):
    import subprocess as _sp
    root = Path(__file__).resolve().parent.parent
    p = _sp.run(["git"] + list(args), cwd=str(root),
                input=stdin_text,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True, timeout=timeout)
    return {"ok": p.returncode == 0, "out": (p.stdout or "")[-limit:],
            "err": (p.stderr or "")[-2000:]}


def _git_snapshot():
    """脏文件名集合。

    ★ 必须用 `-z`（原样路径）：非 ASCII/含空格名在普通 porcelain 里会被转义成
      `"\\346..."`，与 `_git_fingerprints()` 的键对不上，指纹比对会全部落空。
    """
    r = _git(["status", "--porcelain", "-z", "--no-renames"],
             limit=4_000_000)
    return set(ent[3:] for ent in (r.get("out") or "").split("\0")
               if len(ent) > 3)


def _git_fingerprints():
    """当前所有脏文件的内容指纹 {path: git hash}（已删除的记空串）。

    ★ `_git_snapshot()` 只有文件名：任务开始前就已改过、本轮又被 DSH 改动的
      文件前后同名，集合差是空的 ⇒ 会漏提交。指纹才能看出「内容变了」。
    """
    st = _git(["status", "--porcelain", "-z", "--no-renames"],
              limit=4_000_000)
    if not st.get("ok"):
        return {}
    paths = [ent[3:] for ent in (st.get("out") or "").split("\0")
             if len(ent) > 3]
    root = Path(__file__).resolve().parent.parent
    live = [p for p in paths if (root / p).is_file()]
    liveset = set(live)
    fp = {p: "" for p in paths if p not in liveset}     # 删除/不可读
    if not live:
        return fp
    h = _git(["hash-object", "--stdin-paths"],
             stdin_text="\n".join(live) + "\n", timeout=120,
             limit=4_000_000)
    outs = (h.get("out") or "").splitlines()
    if h.get("ok") and len(outs) == len(live):
        fp.update(zip(live, outs))
    else:                                     # 兜底：逐文件取指纹
        for p in live:
            r = _git(["hash-object", "--", p])
            fp[p] = (r.get("out") or "").strip() if r.get("ok") else ""
    return fp


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


_RUNTIME_PREFIXES = ("dgtf_memory/", "outputs/", "dgtf_app/runs/",
                     "dgtf_app/anchors/", "smoke_outputs/", "_archive/",
                     ".workbuddy/")


def _commit_scope(paths):
    """自动修复只提交源码/文档；运行记录与缓存不进提交。"""
    out = []
    for p in paths:
        p = str(p or "").strip()
        if not p or p.startswith(_RUNTIME_PREFIXES):
            continue
        if p.endswith((".log", ".pyc", ".sqlite3")):
            continue
        out.append(p)
    return out


def _auto_commit(before: set, task: str, before_head: str = "", before_fp=None):
    after = _git_snapshot()
    new = after - before
    if before_fp is not None:
        # 本轮新出现的 ∪ run 前就脏、本轮内容又变了的（后者集合差看不见）
        cur = _git_fingerprints()
        new = new | {p for p in (after & set(before_fp))
                     if cur.get(p) != before_fp.get(p)}
    new = _commit_scope(sorted(new))
    if not new:
        ah = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
        if before_head and ah and ah != before_head:
            return {"committed": True, "changed": [],
                    "commit": (_git(["log", "-1", "--oneline"]).get("out") or "").strip(),
                    "commit_hash": ah,
                    "why": "DSH Agent 已自行提交本次变更"}
        return {"committed": False, "changed": [], "why": "本次没有新增文件变更"}
    a = _git(["add", "--"] + new)
    if not a.get("ok"):
        return {"committed": False, "changed": new, "error": a.get("err")}
    if _git(["diff", "--cached", "--quiet"]).get("ok"):
        return {"committed": False, "changed": [],
                "why": "本次没有可提交的内容变更"}
    msg = "DSH Agent auto-repair: " + str(task)[:80]
    c = _git(["commit", "-m", msg])
    ch = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
    return {"committed": bool(c.get("ok")), "changed": new,
            "commit": (c.get("out") or "").strip()[-200:],
            "commit_hash": ch if c.get("ok") else "",
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
           "gate": out.get("gate"), "repair": out.get("repair"),
           "attach_task_id": str(out.get("attach_task_id") or "")}
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
            rec = _get_dsh_session(p.stem) or {}
            rows.append({"id": p.stem, "size": p.stat().st_size,
                         "task": task, "ts": rec.get("ts") or p.stat().st_mtime,
                         "ok": rec.get("ok")})
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


_DSH_THINK_ZH_CACHE = {}


def _thinking_zh(text, key):
    """DSH thinking 兜底中文化：无中文的英文思考自动翻译；失败保留原文。"""
    import re as _re
    import hashlib as _h
    s = str(text or "").strip()
    if not s or not key:
        return s
    if _re.search(r"[一-龥]", s):
        return s
    if len(_re.findall(r"[A-Za-z]", s)) < 8:
        return s
    ck = _h.sha1(s.encode("utf-8")).hexdigest()
    if ck in _DSH_THINK_ZH_CACHE:
        return _DSH_THINK_ZH_CACHE[ck]
    import urllib.request as _ur
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "把英文思考翻译成简体中文，只输出译文；保留技术名词、代码、命令原文。"},
            {"role": "user", "content": s[:6000]},
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
    }).encode("utf-8")
    req = _ur.Request("https://api.deepseek.com/chat/completions",
                      data=body, headers={
                          "Content-Type": "application/json",
                          "Authorization": "Bearer " + key})
    out = s
    try:
        with _ur.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
        zh = str((((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
        if zh:
            out = zh
    except Exception:
        pass
    _DSH_THINK_ZH_CACHE[ck] = out
    return out


def _run_dsh_agent(task: str, sid: str = "", timeout: int = 300,
                   auto_repair: bool = False, effort: str = "",
                   permission: str = "", attach_task_id: str = "",
                   model: str = "", emit=None) -> dict:
    """调用本机 DeepSeek Harness headless Agent；返回 NDJSON 事件映射。"""
    import os as _os
    import subprocess as _sp
    root = Path(__file__).resolve().parent.parent
    _before = _git_snapshot()
    _before_fp = _git_fingerprints() if auto_repair else None
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
    auth = ("你在元DGTF项目根目录：%s。请始终使用简体中文回答，"
            "思考过程（thinking）也必须使用简体中文，禁止输出英文思考；"
            "包括思考摘要、解释和最终答复；代码/命令保持原文。"
            "你有权读取该工作区内的项目文件、"
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
                "    model: " + (str(model or "").strip() or "deepseek-flash"),
                "    reasoningEffort: " + _eff]
    if _perm:
        _pl += ["- id: permission",
                "  name: '@deepseek-ai/dsh-permission-presets'",
                "  config:",
                "    defaultPreset: " + _perm]
    # DSH Agent 默认 PTC 模式：headless 用 insert 挂载 tool-presentation。
    _pl += ["- insert:",
            "    - id: tool-presentation",
            "      name: \"@deepseek-ai/dsh-agent-tool-presentation\"",
            "      config:",
            "        mode: ptc"]
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
    events, texts, final = [], [], ""

    def _feed(line):
        nonlocal sid, final
        line = (line or "").strip()
        if not line.startswith("{"):
            return
        try:
            ev = json.loads(line)
        except Exception:
            return
        if ev.get("type") == "thinking" and ev.get("text"):
            ev["text"] = _thinking_zh(str(ev.get("text") or ""), key)
        events.append(ev)
        if ev.get("type") == "text" and ev.get("text"):
            texts.append(str(ev["text"]))
        if ev.get("type") == "session" and ev.get("sessionId"):
            sid = str(ev["sessionId"])
        if ev.get("type") == "final":
            final = str(ev.get("text") or "")
        if emit is not None:
            try:
                emit(ev)
            except Exception:
                pass

    proc = None
    try:
        if emit is not None:
            proc = _sp.Popen(cmd, cwd=str(root), env=env,
                             stdin=_sp.PIPE, stdout=_sp.PIPE,
                             stderr=_sp.PIPE, text=True,
                             encoding="utf-8", errors="replace")
            _DSH_ACTIVE.add(proc)
            proc.stdin.write(auth)
            proc.stdin.close()
            for line in proc.stdout:
                _feed(line)
            try:
                proc.wait(timeout=timeout)
            except _sp.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise
            rc = proc.returncode
            stderr = (proc.stderr.read() or "")[-2000:]
        else:
            p = _sp.run(cmd, cwd=str(root), env=env, input=auth,
                        text=True, encoding="utf-8", errors="replace",
                        capture_output=True, timeout=timeout)
            for line in (p.stdout or "").splitlines():
                _feed(line)
            rc = p.returncode
            stderr = (p.stderr or "")[-2000:]
    finally:
        if proc is not None:
            _DSH_ACTIVE.discard(proc)
        if _patch:
            try: Path(_patch).unlink()
            except Exception: pass
    out = {"ok": (rc == 0), "session_id": sid,
           "text": final or "".join(texts),
           "events": events[-200:],
           "settings": {"effort": _eff, "permission": _perm},
           "attach_task_id": str(attach_task_id or ""),
           "stderr": stderr}
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
                out["repair"] = _auto_commit(_before, task, _before_head,
                                             _before_fp)
            else:
                out["repair"] = {"committed": False, "why": "fast_gate 未通过"}
        except Exception as exc:
            out["repair"] = {"committed": False, "why": str(exc)}
    return out


def _extract_json(text):
    import json as _json
    import re as _re
    s = str(text or "")
    m = _re.search(r"(\{.*\})", s, _re.S)
    if not m:
        return {}
    try:
        return _json.loads(m.group(1))
    except Exception:
        return {}


def _agent_queue_snapshot():
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        from dgtf_v2.agent_bridge import read_tasks
        rows = read_tasks(limit=30)
    except Exception:
        rows = []
    return [{"title": str(x.get("title") or ""),
             "kind": str(x.get("kind") or ""),
             "severity": str(x.get("severity") or "")} for x in rows[-15:]]


def _auto_submit_task(emit=None, model=""):
    """DSH Agent 审阅队列并自动提交一条用户任务；解析失败时退回一条安全任务。"""
    queue = _agent_queue_snapshot()
    prompt = ("你是元DGTF Agent 面板操作员。审阅下面的任务队列，"
              "提出一条最有价值的新用户任务。只输出 JSON，不要改源码："
              '{"title":"...","detail":"...","severity":"med"}。'
              "队列：" + json.dumps(queue, ensure_ascii=False)[:3000])
    res = _run_dsh_agent(prompt, "", timeout=180, auto_repair=False,
                         emit=emit, model=model)
    obj = _extract_json(res.get("text") or "")
    title = str(obj.get("title") or "").strip()
    detail = str(obj.get("detail") or "").strip()
    if not title:
        title = "DSH Agent 自动提交的任务"
        detail = ("根据 Agent 队列自动生成：" + json.dumps(queue, ensure_ascii=False)[:2000])
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dgtf_v2.agent_bridge import append_task
    task = append_task({"kind": "user_task",
                        "severity": str(obj.get("severity") or "med"),
                        "title": title[:200], "detail": detail[:4000],
                        "source_run": "dsh_auto"})
    return {"ok": bool(res.get("ok")), "task": task,
            "dsh_text": str(res.get("text") or "")[:2000],
            "session_id": res.get("session_id") or ""}


def _auto_proposal(task_text="", title="", emit=None, model=""):
    import time as _tm
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dgtf_v2.agent_bridge import read_tasks
    if task_text:
        t = {"title": (title or task_text)[:200], "detail": task_text,
             "kind": "user_task", "severity": "med"}
    else:
        rows = [x for x in read_tasks(limit=100)
                if x.get("kind") in ("process_gap", "audit_gap",
                                     "api_gap", "quality_flag")]
        rows.sort(key=lambda x: {"high": 0, "med": 1, "low": 2}.get(
            str(x.get("severity")), 3))
        if not rows:
            return {"ok": False, "text": "没有可自审的任务"}
        t = rows[0]
    prompt = ("提案模式：不要读取项目文件、不要修改源码。只根据下面任务详情"
              "输出简短修复提案（≤200字）：涉及文件、步骤、风险、验证命令。"
              "任务：" + str(t.get("title") or "") + "。详情："
              + str(t.get("detail") or "")[:1200])
    res = _run_dsh_agent(prompt, "", timeout=300, auto_repair=False,
                         emit=emit, model=model)
    pid = "prop-" + str(int(_tm.time() * 1000))
    prop = _save_proposal({"id": pid, "ts": _tm.time(), "task": t,
                           "plan": str(res.get("text") or ""),
                           "session_id": res.get("session_id") or "",
                           "status": "pending", "approver": "",
                           "events": list(res.get("events") or [])[-50:]})
    return {"ok": bool(res.get("ok")), "proposal": prop}


_REPAIR_VERSION_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "repair_version.json"


def _next_repair_version():
    import json as _json
    d = _REPAIR_VERSION_FILE
    d.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = _json.loads(d.read_text(encoding="utf-8"))
    except Exception:
        cur = {"major": 1, "minor": 30, "patch": 0}
    cur["patch"] = int(cur.get("patch") or 0) + 1
    d.write_text(_json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    return "V-%d.%d.%d" % (cur["major"], cur["minor"], cur["patch"])


def _targeted_acceptance(changed):
    import subprocess as _sp
    import sys as _sys
    root = Path(__file__).resolve().parent.parent
    cmds = []
    if any(str(p).startswith("dgtf_app/") for p in changed):
        cmds.append([_sys.executable, "dgtf_app/selftest.py", "app-selftest"])
    if any(str(p).endswith("元DGTF-V1.30.0.py") or str(p).startswith("dgtf_v2/")
           for p in changed):
        cmds.append([_sys.executable, "smoke_test.py", "smoke"])
    out = []
    ok = True
    for cmd in cmds:
        try:
            p = _sp.run(cmd[:2], cwd=str(root), text=True, encoding="utf-8",
                        errors="replace", capture_output=True, timeout=600)
            good = p.returncode == 0
            ok = ok and good
            out.append({"name": cmd[2], "ok": good,
                        "tail": ((p.stdout or "") + (p.stderr or ""))[-1200:]})
        except Exception as exc:
            ok = False
            out.append({"name": cmd[2], "ok": False, "tail": str(exc)})
    return {"ok": ok, "checks": out}


def _save_repair_artifact(prop, acceptance, version):
    import json as _json
    root = Path(__file__).resolve().parent.parent
    d = root / "outputs" / "repairs" / version
    d.mkdir(parents=True, exist_ok=True)
    (d / "proposal.json").write_text(
        _json.dumps(prop, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "acceptance.log").write_text(
        _json.dumps(acceptance, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 修复产物 " + version, "",
             "- 提案: " + str(prop.get("id") or ""),
             "- 任务: " + str(((prop.get("task") or {}).get("title")) or ""),
             "- 状态: applied",
             "- 验收: " + ("通过" if acceptance.get("ok") else "失败"), ""]
    for c in acceptance.get("checks") or []:
        lines.append("## " + str(c.get("name")) + " " + ("PASS" if c.get("ok") else "FAIL"))
        lines += ["", "```", str(c.get("tail") or ""), "```", ""]
    (d / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return str(d)


def _auto_cycle_all(emit=None, model=""):
    """全队列闭环：处理所有任务、跑完消费者、为所有任务批量自审并落提案。"""
    import json as _json
    import sys as _sys
    import time as _tm
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dgtf_v2.agent_bridge import read_tasks
    from dgtf_v2.agent_worker import run_once, write_proposals
    tasks = read_tasks(limit=200)
    all_results = []
    for _ in range(30):
        rr = run_once(limit=200)
        if not rr.get("triaged"):
            break
        all_results += list(rr.get("results") or [])
    prop_file = write_proposals()
    existing = set()
    for p in _list_proposals(300):
        tid = str(((p.get("task") or {}).get("id")) or "")
        if tid and p.get("status") in ("pending", "applied"):
            existing.add(tid)
    todo = [t for t in tasks if str(t.get("id") or "") not in existing]
    plans = {}
    audit_text = ""
    audit_ok = True
    if todo:
        compact = [{"task_id": str(t.get("id") or ""),
                    "title": str(t.get("title") or "")[:160],
                    "detail": str(t.get("detail") or "")[:400]}
                   for t in todo[:80]]
        prompt = ("提案模式：不要读取项目文件、不要修改源码。请为下列全部任务分别给出"
                  "简短修复提案，只输出一个 JSON 对象："
                  '{"proposals":[{"task_id":"...","plan":"..."}]}。'
                  "任务列表：" + _json.dumps(compact, ensure_ascii=False)[:24000])
        res = _run_dsh_agent(prompt, "", timeout=300, auto_repair=False,
                             emit=emit, model=model)
        audit_text = str(res.get("text") or "")
        audit_ok = bool(res.get("ok"))
        obj = _extract_json(audit_text)
        arr = obj.get("proposals") if isinstance(obj, dict) else obj
        if isinstance(arr, list):
            for x in arr:
                if isinstance(x, dict) and x.get("task_id"):
                    plans[str(x["task_id"])] = str(x.get("plan") or "")
    made = []
    for t in todo:
        tid = str(t.get("id") or "")
        plan = plans.get(tid) or ("DSH 批量自审：待针对该任务补充具体方案。"
                                  + (("\n" + audit_text[:800]) if audit_text else ""))
        prop = _save_proposal({"id": "prop-" + str(int(_tm.time() * 1000)) + "-" + tid[:6],
                               "ts": _tm.time(), "task": t, "task_id": tid,
                               "plan": plan, "status": "pending", "approver": "",
                               "session_id": "", "batch": True})
        made.append(prop)
    return {"ok": audit_ok or bool(made),
            "tasks_total": len(tasks), "tasks_submitted": len(tasks),
            "tasks_processed": len(all_results),
            "consumer": {"run": {"triaged": len(all_results),
                                 "results": all_results},
                         "proposals": prop_file},
            "proposals": made, "audit_text": audit_text[:2000],
            "audit_ok": audit_ok}


def _proposal_commit_hash(prop):
    import re as _re
    r = ((prop or {}).get("result") or {}).get("repair") or {}
    h = str(r.get("commit_hash") or "").strip()
    if h:
        return h
    m = _re.search(r"\[[^\]]*?\s([0-9a-fA-F]{7,40})\]",
                   str(r.get("commit") or ""))
    return m.group(1) if m else ""


def _conv_lock():
    global _DSH_CONV_LOCK
    import threading as _th
    if _DSH_CONV_LOCK is None:
        _DSH_CONV_LOCK = _th.Lock()
    return _DSH_CONV_LOCK


def _conv_dir():
    d = Path(__file__).resolve().parent.parent / "dgtf_memory" / "dsh_conversations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _conv_path(cid):
    import re as _re
    safe = _re.sub(r"[^A-Za-z0-9_.-]", "_", str(cid or ""))[:120] or "conversation"
    return _conv_dir() / (safe + ".json")


def _conv_save(conv):
    import json as _json
    try:
        _conv_path(conv.get("id")).write_text(
            _json.dumps(conv, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _conv_load(cid):
    import json as _json
    p = _conv_path(cid)
    if not p.exists():
        return None
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _conv_event(cid, turn_id, ev):
    with _conv_lock():
        conv = _DSH_CONV.get(cid)
        if not conv:
            return
        for turn in conv.get("turns") or []:
            if turn.get("id") == turn_id:
                turn.setdefault("events", []).append(ev)
                return


def _conv_worker(cid):
    import time as _t
    while True:
        with _conv_lock():
            conv = _DSH_CONV.get(cid) or _conv_load(cid)
            if not conv:
                _DSH_CONV_ACTIVE.discard(cid)
                return
            turn = None
            for x in conv.get("turns") or []:
                if x.get("status") == "queued":
                    turn = x
                    break
            if turn is None:
                _DSH_CONV_ACTIVE.discard(cid)
                return
            turn["status"] = "running"
            turn["ts_start"] = _t.time()
            _DSH_CONV[cid] = conv
            _conv_save(conv)
            sid = str(conv.get("session_id") or "")
            task = str(turn.get("task") or "")
            settings = conv.get("settings") or {}
        try:
            res = _run_dsh_agent(
                task, sid, timeout=1800,
                effort=str(settings.get("effort") or ""),
                permission=str(settings.get("permission") or ""),
                model=str(settings.get("model") or ""),
                emit=lambda ev: _conv_event(cid, turn.get("id"), ev))
        except Exception as exc:
            res = {"ok": False, "session_id": sid, "events": [],
                   "text": "", "stderr": str(exc)}
        with _conv_lock():
            conv = _DSH_CONV.get(cid) or _conv_load(cid)
            if not conv:
                _DSH_CONV_ACTIVE.discard(cid)
                return
            for x in conv.get("turns") or []:
                if x.get("id") == turn.get("id"):
                    x["status"] = "done" if res.get("ok") else "error"
                    x["events"] = list(res.get("events") or x.get("events") or [])
                    x["text"] = str(res.get("text") or "")
                    x["ts_end"] = _t.time()
                    break
            if res.get("session_id"):
                conv["session_id"] = str(res["session_id"])
            _DSH_CONV[cid] = conv
            _conv_save(conv)


def _conv_enqueue(cid, task, settings=None):
    import time as _t
    with _conv_lock():
        conv = _DSH_CONV.get(cid) or _conv_load(cid)
        if not conv:
            conv = {"id": cid, "session_id": "", "created_at": _t.time(),
                    "turns": []}
        conv["settings"] = settings or conv.get("settings") or {}
        turn = {"id": "turn-" + str(int(_t.time() * 1000)),
                "task": str(task), "status": "queued",
                "events": [], "text": "", "ts_start": _t.time()}
        conv.setdefault("turns", []).append(turn)
        conv["updated_at"] = _t.time()
        _DSH_CONV[cid] = conv
        _conv_save(conv)
        need_worker = cid not in _DSH_CONV_ACTIVE
        if need_worker:
            _DSH_CONV_ACTIVE.add(cid)
    if need_worker:
        import threading as _th
        _th.Thread(target=_conv_worker, args=(cid,), daemon=True).start()
    return conv, turn


def _conv_snapshot(cid):
    with _conv_lock():
        conv = _DSH_CONV.get(cid) or _conv_load(cid)
    return conv


def _auto_jobs_lock():
    global _AUTO_JOBS_LOCK
    import threading as _th
    if _AUTO_JOBS_LOCK is None:
        _AUTO_JOBS_LOCK = _th.Lock()
    return _AUTO_JOBS_LOCK


def _auto_run_stage(stage, data, write):
    out = {"ok": True, "stage": stage}

    def _stage(name):
        write({"type": "stage", "stage": name})
        return lambda ev: write({"type": "event", "stage": name, "event": ev})

    model = str((data or {}).get("model") or "")
    if stage == "all":
        out.update(_auto_cycle_all(emit=_stage("all"), model=model))
    else:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        if stage == "task":
            out["task"] = _auto_submit_task(emit=_stage("task"), model=model)
            out["ok"] = bool(out["task"].get("ok"))
        if stage == "consumer":
            _stage("consumer")
            from dgtf_v2.agent_worker import run_once, write_proposals
            out["consumer"] = {"run": run_once(), "proposals": write_proposals()}
        if stage == "proposal":
            out["proposal"] = _auto_proposal(
                str((data or {}).get("task_text") or ""), "",
                emit=_stage("proposal"), model=model)
            out["ok"] = bool((out["proposal"] or {}).get("ok"))
    return out


def _auto_job_worker(jid, stage, data):
    job = _AUTO_JOBS.get(jid) or {}

    def write(msg):
        with _auto_jobs_lock():
            j = _AUTO_JOBS.get(jid)
            if j is not None:
                j.setdefault("events", []).append(msg)

    try:
        out = _auto_run_stage(stage, data, write)
        with _auto_jobs_lock():
            j = _AUTO_JOBS.get(jid) or job
            j["status"] = "done"
            j["result"] = out
            _AUTO_JOBS[jid] = j
        _auto_jobs_save()
    except Exception as exc:
        with _auto_jobs_lock():
            j = _AUTO_JOBS.get(jid) or job
            j["status"] = "error"
            j["error"] = str(exc)
            _AUTO_JOBS[jid] = j
        _auto_jobs_save()


def _auto_job_start(stage, data):
    import threading as _th
    import time as _t
    jid = "auto-" + str(int(_t.time() * 1000))
    with _auto_jobs_lock():
        _AUTO_JOBS[jid] = {"id": jid, "stage": stage, "status": "running",
                           "events": [], "result": None, "ts": _t.time()}
        # 只保留最近 20 个任务，避免内存长期增长
        for k in sorted(list(_AUTO_JOBS), key=lambda x: _AUTO_JOBS[x].get("ts") or 0)[:-20]:
            _AUTO_JOBS.pop(k, None)
    _auto_jobs_save()
    _th.Thread(target=_auto_job_worker, args=(jid, stage, data), daemon=True).start()
    return jid


def _autofix_workflow(data, write):
    import time as _t
    confs = [x for x in _list_proposals(300) if x.get("status") == "confirmed"]
    done = []
    for prop in confs:
        pid = str(prop.get("id") or "")
        write({"type": "stage", "stage": "proposal:" + pid})

        def _emit_fix(ev, _pid=pid):
            write({"type": "event", "stage": "proposal:" + _pid, "event": ev})

        prompt = ("按以下已确认提案执行修复：" + str(prop.get("plan") or "")
                  + "。修改后运行 fast_gate.py，通过后只提交本次变更，不 push。")
        try:
            res = _run_dsh_agent(prompt, str(prop.get("session_id") or ""),
                                 timeout=600, auto_repair=True,
                                 model=str((data or {}).get("model") or ""),
                                 emit=_emit_fix)
        except Exception as exc:
            res = {"ok": False, "events": [], "text": "", "stderr": str(exc)}
        repair = res.get("repair") or {}
        prop["approver"] = "dsh_auto"
        prop["approved_ts"] = _t.time()
        prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                          "repair": repair}
        if repair.get("committed"):
            write({"type": "stage", "stage": "acceptance:" + pid})
            acc = _targeted_acceptance(repair.get("changed") or [])
            prop["acceptance"] = acc
            write({"type": "event", "stage": "acceptance:" + pid,
                   "event": {"type": "text",
                             "text": "针对性验收：" + ("PASS" if acc.get("ok") else "FAIL")}})
            if acc.get("ok"):
                version = _next_repair_version()
                prop["version"] = version
                prop["status"] = "applied"
                prop["artifact"] = _save_repair_artifact(prop, acc, version)
            else:
                if repair.get("commit_hash"):
                    rv = _git(["revert", "--no-edit", repair["commit_hash"]])
                    prop["rollback_on_fail"] = {"ok": rv.get("ok"), "err": rv.get("err")}
                prop["status"] = "failed"
        else:
            prop["status"] = "failed"
        _save_proposal(prop)
        done.append(prop)
        write({"type": "proposal_result", "proposal": prop})
    ok = all((x.get("status") == "applied") for x in done) if done else False
    write({"type": "result", "result": {"ok": ok, "proposals": done,
                                        "count": len(done)}})


def _autofix_job_start(data):
    import threading as _th
    import time as _t
    jid = "autofix-" + str(int(_t.time() * 1000))
    with _auto_jobs_lock():
        _AUTO_JOBS[jid] = {"id": jid, "stage": "autofix", "status": "running",
                           "events": [], "result": None, "ts": _t.time()}
        for k in sorted(list(_AUTO_JOBS), key=lambda x: _AUTO_JOBS[x].get("ts") or 0)[:-20]:
            _AUTO_JOBS.pop(k, None)
    _auto_jobs_save()

    def worker():
        def write(msg):
            with _auto_jobs_lock():
                j = _AUTO_JOBS.get(jid)
                if j is not None:
                    j.setdefault("events", []).append(msg)
        try:
            _autofix_workflow(data, write)
            with _auto_jobs_lock():
                j = _AUTO_JOBS.get(jid) or {}
                j["status"] = "done"
                _AUTO_JOBS[jid] = j
            _auto_jobs_save()
        except Exception as exc:
            with _auto_jobs_lock():
                j = _AUTO_JOBS.get(jid) or {}
                j["status"] = "error"
                j["error"] = str(exc)
                _AUTO_JOBS[jid] = j
            _auto_jobs_save()

    _th.Thread(target=worker, daemon=True).start()
    return jid


_AUTO_JOBS_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "auto_jobs.json"


def _auto_jobs_save():
    import json as _json
    try:
        with _auto_jobs_lock():
            data = _json.loads(_json.dumps(_AUTO_JOBS, ensure_ascii=False, default=str))
    except Exception:
        data = {}
    try:
        _AUTO_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _AUTO_JOBS_FILE.with_suffix(".tmp")
        tmp.write_text(_json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(_AUTO_JOBS_FILE)
    except Exception:
        pass


def _auto_jobs_load():
    import json as _json
    try:
        data = _json.loads(_AUTO_JOBS_FILE.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    n = 0
    with _auto_jobs_lock():
        for jid, j in data.items():
            if not isinstance(j, dict):
                continue
            if j.get("status") == "running":
                j["status"] = "interrupted"
                j["error"] = "服务重启/中断：后台任务未正常收尾"
            _AUTO_JOBS[jid] = j
            n += 1
    return n


def _auto_job_list(limit=20):
    with _auto_jobs_lock():
        rows = sorted(_AUTO_JOBS.values(), key=lambda x: x.get("ts") or 0, reverse=True)[:limit]
    return [{"id": j.get("id"), "stage": j.get("stage"),
             "status": j.get("status"), "ts": j.get("ts"),
             "events": len(j.get("events") or []),
             "result_keys": sorted((j.get("result") or {}).keys())
             if isinstance(j.get("result"), dict) else [],
             "error": j.get("error")} for j in rows]


def _auto_job_get(jid, since=0):
    with _auto_jobs_lock():
        j = _AUTO_JOBS.get(jid)
        if not j:
            return None
        evs = list(j.get("events") or [])
        return {"id": jid, "stage": j.get("stage"), "status": j.get("status"),
                "events": evs[max(0, int(since)):], "next": len(evs),
                "result": j.get("result"), "error": j.get("error")}


def _eml_status():
    import json as _json
    from collections import Counter
    root = Path(__file__).resolve().parent.parent
    mem = root / "dgtf_memory"
    def _jsonl(name, cap=2000):
        p = mem / name
        rows = []
        if p.exists():
            try:
                for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-cap:]:
                    try:
                        d = _json.loads(ln)
                        if isinstance(d, dict):
                            rows.append(d)
                    except Exception:
                        pass
            except Exception:
                pass
        return p, rows
    pb_path, pb = _jsonl("playbook.jsonl")
    v2_path, v2 = _jsonl("v2_events.jsonl")
    tasks = _jsonl("agent_tasks.jsonl")[1]
    results = _jsonl("agent_results.jsonl")[1]
    knowledge = _jsonl("agent_knowledge.jsonl")[1]
    proposals = []
    try:
        proposals = [x for x in _list_proposals(300) if x]
    except Exception:
        pass
    by_kind = Counter(str(x.get("kind") or "") for x in pb)
    v2_kind = Counter(str(x.get("kind") or "") for x in v2)
    return {
        "ok": True,
        "playbook": {"path": str(pb_path), "n": len(pb),
                     "by_kind": dict(by_kind),
                     "last": pb[-1] if pb else None},
        "v2_shadow": {"path": str(v2_path), "n": len(v2),
                      "by_kind": dict(v2_kind),
                      "last": v2[-1] if v2 else None},
        "agent": {"tasks": len(tasks), "results": len(results),
                  "knowledge": len(knowledge), "proposals": len(proposals)},
        "proposal_status": dict(Counter(str(x.get("status") or "") for x in proposals)),
        "self_feedback": {"engine_module": True,
                          "app_tasks": len(tasks),
                          "app_proposals": len(proposals)},
    }


def _v2_shadow_status(limit=200):
    import json as _json
    from collections import Counter
    p = Path(__file__).resolve().parent.parent / "dgtf_memory" / "v2_events.jsonl"
    rows = []
    if p.exists():
        try:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
                try:
                    d = _json.loads(ln)
                    if isinstance(d, dict):
                        rows.append(d)
                except Exception:
                    pass
        except Exception:
            pass
    recent = rows[-5:]
    tmpl = {}
    for x in rows:
        if str(x.get("kind") or "") != "schedule_outcome":
            continue
        pl = x.get("payload") if isinstance(x.get("payload"), dict) else {}
        t = str(pl.get("template") or "")
        if not t:
            continue
        d = tmpl.setdefault(t, {"n": 0, "quality": 0.0, "tokens": 0.0, "calls": 0.0})
        try:
            d["quality"] += float(pl.get("quality") or 0)
            d["tokens"] += float(pl.get("tokens") or 0)
            d["calls"] += float(pl.get("calls") or 0)
            d["n"] += 1
        except Exception:
            pass
    by_template = {}
    for t, d in tmpl.items():
        n = int(d["n"] or 0)
        by_template[t] = {"n": n,
                          "quality": round(d["quality"] / n, 3) if n else 0.0,
                          "tokens": round(d["tokens"] / n, 1) if n else 0.0,
                          "calls": round(d["calls"] / n, 1) if n else 0.0}
    return {"ok": True, "n": len(rows),
            "by_kind": dict(Counter(str(x.get("kind") or "") for x in rows)),
            "by_layer": dict(Counter(str(x.get("layer") or "") for x in rows)),
            "by_template": by_template,
            "recent": recent,
            "paths": str(p)}


def _app_health():
    import importlib.util as _iu
    _proj = Path(__file__).resolve().parent.parent
    if str(_proj) not in sys.path:
        sys.path.insert(0, str(_proj))
    eng = runner.find_engine()
    m = re.search(r"V(\d+)\.(\d+)\.(\d+)", eng.name)
    ver = ".".join(m.groups()) if m else ""
    flat = {}
    try:
        flat = prm.effective_flat()
    except Exception:
        pass
    modules = ("self_feedback", "llm_feedback", "online_adapt", "frontier_feedback",
               "unified_memory", "scheduler", "orchestrator", "facet_flow",
               "fact_flow", "evidence", "process_ledger", "shadow")
    mods = {}
    for name in modules:
        try:
            mods[name] = _iu.find_spec("dgtf_v2." + name) is not None
        except Exception:
            mods[name] = False
    creds = runner.credential_status()
    daemon = agent_daemon_status()
    dsh = Path(os.getenv("DSH_BIN") or str(Path(
        os.getenv("LOCALAPPDATA", "")) /
        "Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd"))
    checks = {
        "engine_file": eng.is_file(),
        "engine_version": ver,
        "dgtf_v2_modules": all(mods.values()),
        "self_feedback_loop": bool(mods.get("self_feedback") and mods.get("llm_feedback")),
        "eml_memory": bool(mods.get("unified_memory")),
        "fact_flow": bool(mods.get("fact_flow") and mods.get("evidence")),
        "scheduler": bool(mods.get("scheduler") and mods.get("orchestrator")),
        "api_key": bool(creds.get("api_key")),
        "dsh_headless": dsh.is_file(),
        "agent_daemon": bool(daemon.get("running")),
        "outputs_dir": oi.OUTPUTS_DIR.is_dir(),
    }
    critical = ["engine_file", "dgtf_v2_modules", "self_feedback_loop",
                "eml_memory", "fact_flow", "scheduler", "outputs_dir"]
    warnings = [k for k in ("api_key", "dsh_headless", "agent_daemon") if not checks[k]]
    return {
        "ok": all(bool(checks[k]) for k in critical),
        "app": {"name": "元DGTF app", "commit": _git(["rev-parse", "HEAD"]).get("out", "")[:12]},
        "engine": {"file": eng.name, "version": ver,
                   "layers": ["0", "1", "both", "all"],
                   "eml": bool(checks["self_feedback_loop"]),
                   "scheduler": bool(checks["scheduler"])},
        "checks": checks,
        "warnings": warnings,
        "modules": mods,
        "config": {"auto_enabled": flat.get("auto.enabled"),
                   "history_limit": flat.get("auto.history_limit"),
                   "v2_shadow": flat.get("scheduler.v2.shadow"),
                   "parallel_mode": flat.get("actions.parallel_mode"),
                   "max_tokens": flat.get("max_tokens")},
        "daemon": {"running": bool(daemon.get("running")), "pid": daemon.get("pid"),
                   "last_log": daemon.get("last_log")},
        "eml": _eml_status(),
        "mapping": {
            "engine_layers": "→ /api/chats /api/tasks /api/outputs/layers",
            "EML_self_feedback": "→ /api/tasks 产物 + /api/agent/* + eML/反馈",
            "scheduler": "→ /api/tasks opts + /api/params + /api/schedule/preview",
            "outputs": "→ /api/outputs /api/outputs/facets /api/export/*",
            "knowledge": "→ /api/agent/knowledge*",
            "DSH": "→ /api/dsh/* /api/agent/auto*",
        },
    }


def _schedule_profiles():
    import yaml
    rows = []
    try:
        files = sorted(runner.CONFIG_DIR.glob("*.yaml"))
    except Exception:
        files = []
    for p in files:
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace")) or {}
        except Exception:
            d = {}
        auto = d.get("auto") if isinstance(d.get("auto"), dict) else {}
        sched = ((d.get("scheduler") or {}).get("v2") or {}) if isinstance(d.get("scheduler"), dict) else {}
        actions = d.get("actions") if isinstance(d.get("actions"), dict) else {}
        runtime = d.get("runtime") if isinstance(d.get("runtime"), dict) else {}
        rows.append({
            "id": p.name,
            "name": p.stem,
            "recommended": ("帕累托" in p.stem),
            "auto_enabled": auto.get("enabled"),
            "history_limit": auto.get("history_limit"),
            "v2_shadow": sched.get("shadow"),
            "v2_takeover": sched.get("takeover"),
            "parallel_mode": actions.get("parallel_mode"),
            "parallel_warmup_rounds": actions.get("parallel_warmup_rounds"),
            "max_tokens": d.get("max_tokens"),
            "runtime": {"web": runtime.get("web"), "thinking": runtime.get("thinking"),
                        "effort": runtime.get("effort")},
        })
    return rows


def _eml_replay(limit=60, dry_run=True):
    """EML 反馈回放：历史 packed → unified_memory schedule outcome → 先验。

    dry_run=True 用临时记忆库（绝不碰生产）；dry_run=False 才显式允许写生产。
    """
    import json as _json
    import sys as _sys
    import tempfile as _tf
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent.parent
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    from dgtf_v2.unified_memory import UnifiedMemory
    files = sorted(oi.OUTPUTS_DIR.glob("*.packed.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, int(limit))]
    replayed = deduped = skipped = 0
    priors = {}
    stats = {}
    ctx = _tf.TemporaryDirectory() if dry_run else None
    try:
        mem = (UnifiedMemory.for_tests(ctx.name) if dry_run
               else UnifiedMemory(allow_production=True))
        for p in files:
            try:
                d = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                skipped += 1
                continue
            if not isinstance(d, dict):
                skipped += 1
                continue
            try:
                tok = int(d.get("llm_tokens") or 0)
                calls = int(d.get("llm_calls") or 0)
            except Exception:
                continue
            if tok <= 0:
                skipped += 1
                continue
            views = d.get("views") if isinstance(d.get("views"), dict) else {}
            hits = 0
            for v in views.values():
                if isinstance(v, dict) and any(v.get(x) for x in (
                        "candidates", "threads", "sub_questions",
                        "adjudications", "meta_closure")):
                    hits += 1
            quality = round(hits / 4.0, 3)
            route = d.get("route") or ["auto"]
            try:
                route_txt = ",".join(str(x) for x in route) if isinstance(route, list) else str(route)
            except Exception:
                route_txt = "auto"
            try:
                rounds = d.get("rounds") or {}
                rn = max([int(v) for v in rounds.values()]) if isinstance(rounds, dict) and rounds else 1
            except Exception:
                rn = 1
            tmpl = ("auto:r%d" % rn) if route_txt in ("auto", "[]", "") else ("route:r%d" % rn)
            rid = p.name.replace(".packed.json", "")
            try:
                rr = mem.record_outcome(run_id=rid, template=tmpl,
                                        quality=quality, calls=calls,
                                        tokens=tok, success=True,
                                        mirror_playbook=True)
                if rr.get("recorded"):
                    replayed += 1
                elif rr.get("deduped"):
                    deduped += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        stats = mem.stats()
        try:
            priors = mem.read_priors()
        except Exception:
            priors = {}
    finally:
        if ctx is not None:
            try:
                ctx.cleanup()
            except Exception:
                pass
    return {"ok": True, "dry_run": bool(dry_run), "scanned": len(files),
            "replayed": replayed, "deduped": deduped, "skipped": skipped,
            "priors": priors, "stats": stats,
            "note": "品质=四层覆盖数/4；不写答案正文"}


def _schedule_pareto(limit=120, prefer="balanced"):
    """从真实 packed 产物聚合 token/层覆盖，返回调度帕累托点。

    指标：cost = llm_tokens（越低越好）；quality = 四层覆盖面（0..1，越高越好）。
    这是**可复核的经验前沿**，不是拍脑袋的权重表。
    """
    import json as _json
    rows = []
    try:
        files = sorted(oi.OUTPUTS_DIR.glob("*.packed.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, int(limit))]
    except Exception:
        files = []
    for p in files:
        try:
            d = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        try:
            tok = int(d.get("llm_tokens") or 0)
        except Exception:
            tok = 0
        if tok <= 0:
            continue
        views = d.get("views") if isinstance(d.get("views"), dict) else {}
        hits = 0
        flags = 0
        for _k, v in views.items():
            if not isinstance(v, dict):
                continue
            if any(v.get(x) for x in ("candidates", "threads", "sub_questions",
                                      "adjudications", "meta_closure")):
                hits += 1
            try:
                flags += len(v.get("quality_flags") or [])
            except Exception:
                pass
        coverage = round(hits / 4.0, 3)
        rounds = d.get("rounds")
        try:
            rounds_key = _json.dumps(rounds, ensure_ascii=False, sort_keys=True)[:80]
        except Exception:
            rounds_key = str(rounds)[:80]
        rows.append({"route": str(d.get("route") or "auto"),
                     "rounds": rounds_key, "tokens": tok,
                     "coverage": coverage, "flags": flags,
                     "output": p.name.replace(".packed.json", ".md")})
    if not rows:
        return {"ok": True, "points": [], "recommended": None,
                "note": "暂无可统计的真实 packed 产物"}
    # 按 (route, rounds) 聚合；样本越多越可信。
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        groups[(r["route"], r["rounds"])].append(r)
    pts = []
    for (route, rounds), rs in groups.items():
        n = len(rs)
        avg_tok = round(sum(x["tokens"] for x in rs) / n, 1)
        avg_cov = round(sum(x["coverage"] for x in rs) / n, 3)
        bad = sum(1 for x in rs if x["flags"])
        pts.append({"route": route, "rounds": rounds, "runs": n,
                    "tokens": avg_tok, "coverage": avg_cov, "flag_runs": bad})
    # 非支配：token 更低且 coverage 不低于别人；同 token 取 coverage 高。
    front = []
    for p in sorted(pts, key=lambda x: (x["tokens"], -x["coverage"])):
        if not any((q["tokens"] <= p["tokens"] and q["coverage"] >= p["coverage"]
                    and (q["tokens"] < p["tokens"] or q["coverage"] > p["coverage"]))
                   for q in pts):
            front.append(p)
    # 推荐：balanced 用 coverage - 归一化 token 惩罚；cost/quality 优先。
    _max_tok = max([p["tokens"] for p in pts] or [1])
    def _score(p):
        cost = p["tokens"] / _max_tok
        if prefer == "cost":
            return -cost + 0.15 * p["coverage"]
        if prefer == "quality":
            return p["coverage"] - 0.15 * cost
        return p["coverage"] - 0.35 * cost
    recommended = max(pts, key=_score)
    return {"ok": True, "points": pts, "frontier": front,
            "recommended": recommended, "prefer": prefer,
            "metric_note": "cost=llm_tokens；quality=四层覆盖数/4（真实 packed 聚合）",
            "recommended_profile": "方案F-帕累托最优.yaml"}


_SCHEDULE_POLICY_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "schedule_policy.json"


def _schedule_policy_load():
    import json as _json
    try:
        d = _json.loads(_SCHEDULE_POLICY_FILE.read_text(encoding="utf-8", errors="replace"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _schedule_policy_apply(prefer="balanced"):
    import json as _json
    import time as _t
    pr = _schedule_pareto(limit=120, prefer=str(prefer or "balanced"))
    rec = pr.get("recommended") or {}
    profile = str(pr.get("recommended_profile") or "方案F-帕累托最优.yaml")
    rec = dict(rec)
    rec["applied_at"] = _t.time()
    rec["prefer"] = str(prefer or "balanced")
    rec["profile"] = profile
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "policy": rec, "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _schedule_preview(data):
    question = str((data or {}).get("question") or "").strip()
    _raw_opts = (data or {}).get("opts") or {}
    if not isinstance(_raw_opts, dict):
        return {"ok": False, "error": "opts 必须是对象"}
    opts = dict(_raw_opts)
    _profile = str((data or {}).get("profile") or opts.get("profile") or "")
    if _profile:
        _pp = runner.profile_path(_profile)
        if _pp is None:
            return {"ok": False, "error": "未知调度 profile：" + _profile}
        opts["_config"] = str(_pp)
    flat = {}
    try:
        flat = prm.effective_flat()
    except Exception:
        pass
    effective = {}
    precedence = {}
    for k in ("route", "rounds", "parallel", "web", "thinking", "effort",
              "orientation", "landing", "decidability"):
        if k in opts and opts.get(k) not in (None, ""):
            effective[k] = opts[k]
            precedence[k] = "opts"
        elif k in flat and flat.get(k) not in (None, ""):
            effective[k] = flat.get(k)
            precedence[k] = "config"
        else:
            effective[k] = "auto"
            precedence[k] = "auto"
    try:
        argv = runner.build_cmd(question or "（预览占位问题）", dict(opts))
        argv = argv[2:] if len(argv) > 2 else argv
    except Exception as exc:
        argv = []
        return {"ok": False, "error": str(exc), "effective": effective}
    _pareto = {}
    try:
        _pr = _schedule_pareto(limit=120, prefer=str((data or {}).get("prefer") or "balanced"))
        _rec = _pr.get("recommended") or {}
        _pareto = {"recommended": _rec, "frontier_n": len(_pr.get("frontier") or []),
                   "suggested_profile": _pr.get("recommended_profile") or ""}
    except Exception:
        _pareto = {}
    return {
        "ok": True,
        "question_present": bool(question),
        "engine": runner.find_engine().name,
        "profile": (_profile or ""),
        "effective": effective,
        "precedence": precedence,
        "cli": argv,
        "config": {
            "auto_enabled": flat.get("auto.enabled"),
            "auto_history_limit": flat.get("auto.history_limit"),
            "v2_enabled": flat.get("scheduler.v2.enabled"),
            "v2_shadow": flat.get("scheduler.v2.shadow"),
            "v2_takeover": flat.get("scheduler.v2.takeover"),
            "parallel_mode": flat.get("actions.parallel_mode"),
            "parallel_warmup_rounds": flat.get("actions.parallel_warmup_rounds"),
            "max_tokens": flat.get("max_tokens"),
        },
        "layers": ["0", "1", "both", "all"],
        "dynamic": {"max_concurrent": runner.MAX_CONCURRENT,
                    "history_limit": flat.get("auto.history_limit"),
                    "budget_soft": flat.get("max_tokens")},
        "pareto": _pareto,
        "policy": _schedule_policy_load(),
    }


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

    def _stream_open(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _stream_write(self, obj):
        self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()

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

        if p == "/api/schedule/pareto":
            try:
                return self._json(_schedule_pareto(
                    limit=int((q.get("limit") or ["120"])[0] or 120),
                    prefer=str((q.get("prefer") or ["balanced"])[0])))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/profiles":
            try:
                return self._json({"profiles": _schedule_profiles()})
            except Exception as exc:
                return self._json({"profiles": [], "error": str(exc)}, 500)
        if p == "/api/agent/eml":
            try:
                return self._json(_eml_status())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/policy":
            try:
                return self._json({"ok": True, "policy": _schedule_policy_load(),
                                   "path": str(_SCHEDULE_POLICY_FILE)})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2":
            try:
                return self._json(_v2_shadow_status())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/auto/jobs":
            return self._json({"jobs": _auto_job_list()})
        if p == "/api/health":
            try:
                return self._json(_app_health())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
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

        if p == "/api/agent/knowledge/pdf":
            name = Path(str((q.get("name") or [""])[0])).name
            pdf = Path(__file__).resolve().parent.parent / "dgtf_memory" / "agent_knowledge_pdfs" / name
            if not name.lower().endswith(".pdf") or not pdf.is_file():
                return self._json({"error": "pdf not found"}, 404)
            try:
                data = pdf.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", "inline; filename=\"" + name + "\"")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True
                return
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/agent/knowledge":
            try:
                path = "dgtf_memory/agent_knowledge.jsonl"
                lines = Path(path).read_text(encoding="utf-8").splitlines()[-100:] if Path(path).exists() else []
                return self._json({"items": [__import__("json").loads(x) for x in lines if x.strip()]})
            except Exception as exc:
                return self._json({"items": [], "error": str(exc)})
        m = re.match(r"^/api/agent/auto/job/([^/]+)$", p)
        if m:
            since = int((q.get("since") or ["0"])[0] or 0)
            return self._json(_auto_job_get(m.group(1), since) or {"error": "job not found"})
        m = re.match(r"^/api/dsh/chat/([^/]+)$", p)
        if m:
            return self._json(_conv_snapshot(unquote(m.group(1))) or {})
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
        if p == "/api/agent/daemon":
            return self._json(agent_daemon_status())
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
        if p == "/api/agent/eml/replay":
            try:
                data = self._read_json()
                return self._json(_eml_replay(
                    limit=int(data.get("limit") or 60),
                    dry_run=bool(data.get("dry_run", True))))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/pareto/apply":
            try:
                data = self._read_json()
                return self._json(_schedule_policy_apply(
                    prefer=str(data.get("prefer") or "balanced")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/knowledge/dedupe":
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from dgtf_v2.agent_bridge import dedupe_knowledge
                return self._json({"ok": True, **dedupe_knowledge()})
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        if p == "/api/agent/knowledge":
            data = self._read_json()
            default_qs = [
                "DeepSeek 官方 最新发布 技术博客 模型 2026",
                "arxiv LLM multi-agent self-evolution PDF 2026",
                "AI Agent 技术论坛 社区 最新 讨论 2026",
            ]
            raw_qs = data.get("queries")
            qs = [str(x).strip() for x in raw_qs if str(x).strip()] if isinstance(raw_qs, list) else []
            if not qs:
                qs = default_qs
            limit = max(1, min(6, int(data.get("limit") or 3)))
            try:
                import sys as _sys
                import time as _kt
                _proj = Path(__file__).resolve().parent.parent
                try:
                    for _ln in (_proj / ".env").read_text(
                            encoding="utf-8", errors="replace").splitlines():
                        if _ln.startswith("DGTF_API_KEY="):
                            os.environ.setdefault(
                                "DGTF_API_KEY",
                                _ln.split("=", 1)[1].strip().strip('"').strip("'"))
                            break
                except Exception:
                    pass
                _sys.path.insert(0, str(_proj))
                from dgtf_v2.agent_bridge import refresh_knowledge_http, dedupe_knowledge
                _dd = dedupe_knowledge()
                _kr = refresh_knowledge_http(qs[:4], return_stats=True, limit=limit)
                picked = (_kr.get("items") or [])[:limit]
                _skipped = int(_kr.get("skipped_duplicates") or 0) + int(_dd.get("removed") or 0)
                patch_path = ""
                try:
                    pdir = Path(__file__).resolve().parent.parent / "dgtf_memory"
                    pdir.mkdir(parents=True, exist_ok=True)
                    pp = pdir / "agent_knowledge_patch.md"
                    with pp.open("a", encoding="utf-8") as pf:
                        pf.write("\n## 联网技术知识补丁 " + _kt.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                        for it in picked:
                            pf.write("- [" + str(it.get("title") or it.get("query") or "") + "]("
                                     + str(it.get("url") or "") + ") — "
                                     + str(it.get("claim") or "")[:200] + "\n")
                            _meta = []
                            if it.get("source_type"):
                                _meta.append("来源=" + str(it.get("source_type")))
                            if it.get("published"):
                                _meta.append("发布=" + str(it.get("published"))[:20])
                            if it.get("confidence"):
                                _meta.append("置信=" + str(it.get("confidence")))
                            if _meta:
                                pf.write("  - " + "；".join(_meta) + "\n")
                            if it.get("pdf_url"):
                                pf.write("  - PDF 原文：" + str(it.get("pdf_url")) + "\n")
                            if it.get("zh_note"):
                                pf.write("  - 中文注释：" + str(it.get("zh_note")) + "\n")
                    patch_path = str(pp)
                except Exception:
                    pass
                return self._json({"items": picked, "queries": qs,
                                   "count": len(picked), "patch": patch_path,
                                   "skipped_duplicates": _skipped,
                                   "deduped": _dd})
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
        if p == "/api/dsh/proposals/autofix/start":
            data = self._read_json()
            jid = _autofix_job_start(data)
            return self._json({"ok": True, "job_id": jid})
        if p == "/api/dsh/proposals/autofix/stream":
            data = self._read_json()
            self._stream_open()
            confs = [x for x in _list_proposals(300)
                     if x.get("status") == "confirmed"]
            done = []
            try:
                for prop in confs:
                    pid = str(prop.get("id") or "")
                    self._stream_write({"type": "stage",
                                        "stage": "proposal:" + pid})

                    def _emit_fix(ev, _pid=pid):
                        self._stream_write({"type": "event", "stage": "proposal:" + _pid,
                                            "event": ev})

                    prompt = ("按以下已确认提案执行修复：" + str(prop.get("plan") or "")
                              + "。修改后运行 fast_gate.py，通过后只提交本次变更，不 push。")
                    res = _run_dsh_agent(prompt, str(prop.get("session_id") or ""),
                                         timeout=600, auto_repair=True,
                                         model=str(data.get("model") or ""),
                                         emit=_emit_fix)
                    repair = res.get("repair") or {}
                    prop["approver"] = "dsh_auto"
                    import time as _aft
                    prop["approved_ts"] = _aft.time()
                    prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                                      "repair": repair}
                    if repair.get("committed"):
                        self._stream_write({"type": "stage",
                                            "stage": "acceptance:" + pid})
                        acc = _targeted_acceptance(repair.get("changed") or [])
                        prop["acceptance"] = acc
                        self._stream_write({"type": "event", "stage": "acceptance:" + pid,
                                            "event": {"type": "text",
                                                      "text": "针对性验收：" + ("PASS" if acc.get("ok") else "FAIL")}})
                        if acc.get("ok"):
                            version = _next_repair_version()
                            prop["version"] = version
                            prop["status"] = "applied"
                            prop["artifact"] = _save_repair_artifact(prop, acc, version)
                        else:
                            if repair.get("commit_hash"):
                                rv = _git(["revert", "--no-edit", repair["commit_hash"]])
                                prop["rollback_on_fail"] = {"ok": rv.get("ok"),
                                                            "err": rv.get("err")}
                            prop["status"] = "failed"
                    else:
                        prop["status"] = "failed"
                    _save_proposal(prop)
                    done.append(prop)
                    self._stream_write({"type": "proposal_result", "proposal": prop})
                ok = all((x.get("status") == "applied") for x in done) if done else False
                self._stream_write({"type": "result",
                                    "result": {"ok": ok, "proposals": done,
                                               "count": len(done)}})
            except Exception as exc:
                try:
                    self._stream_write({"type": "error", "error": str(exc)})
                except Exception:
                    pass
            return
        if p.startswith("/api/dsh/proposals/") and p.endswith("/confirm"):
            pid = p.split("/")[4]
            prop = _get_proposal(pid)
            if not prop:
                return self._json({"error": "proposal not found"}, 404)
            if prop.get("status") != "pending":
                return self._json({"error": "只有 pending 提案可确认"}, 400)
            prop["status"] = "confirmed"
            import time as _cft
            prop["confirmed_ts"] = _cft.time()
            prop["approver"] = "user"
            _save_proposal(prop)
            return self._json({"ok": True, "proposal": prop})
        if p.startswith("/api/dsh/proposals/") and p.endswith("/rollback"):
            pid = p.split("/")[4]
            prop = _get_proposal(pid)
            if not prop:
                return self._json({"error": "proposal not found"}, 404)
            if prop.get("status") != "applied":
                return self._json({"error": "只有 applied 提案可回退"}, 400)
            h = _proposal_commit_hash(prop)
            if not h:
                return self._json({"error": "提案缺少提交 hash，无法自动回退"}, 400)
            r = _git(["revert", "--no-edit", h])
            if not r.get("ok"):
                return self._json({"error": "git revert 失败", "detail": r.get("err")}, 500)
            prop["status"] = "rolled_back"
            import time as _rwt
            prop["rolled_back_ts"] = _rwt.time()
            prop["rollback"] = {"ok": True, "revert": (r.get("out") or "")[-200:],
                                "commit_hash": h}
            _save_proposal(prop)
            return self._json({"ok": True, "proposal": prop})
        if p.startswith("/api/dsh/proposals/") and p.endswith("/approve/stream"):
            data = self._read_json()
            pid = p.split("/")[4]
            prop = _get_proposal(pid)
            if not prop:
                return self._json({"error": "proposal not found"}, 404)
            self._stream_open()

            def _emit_appr(ev):
                self._stream_write({"type": "event", "event": ev})

            try:
                prompt = ("按以下已批准提案执行修复：" + str(prop.get("plan") or "")
                          + "。修改后运行 fast_gate.py，通过后只提交本次变更，不 push。")
                res = _run_dsh_agent(prompt, str(prop.get("session_id") or ""),
                                     timeout=600, auto_repair=True, emit=_emit_appr)
                prop["status"] = ("applied" if (res.get("repair") or {}).get("committed")
                                  else "failed")
                prop["approver"] = str(data.get("mode") or "user")
                import time as _tm3
                prop["approved_ts"] = _tm3.time()
                prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                                  "repair": res.get("repair")}
                _save_proposal(prop)
                self._stream_write({"type": "result",
                                    "result": {"ok": bool(res.get("ok")),
                                               "proposal": prop, "result": res}})
            except Exception as exc:
                try:
                    self._stream_write({"type": "error", "error": str(exc)})
                except Exception:
                    pass
            return
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
        if p == "/api/dsh/chat":
            data = self._read_json()
            task = str(data.get("task") or "").strip()
            if not task:
                return self._json({"error": "task 不能为空"}, 400)
            cid = str(data.get("conversation_id") or "").strip()
            if not cid:
                import time as _ct
                cid = "dshconv-" + str(int(_ct.time() * 1000))
            settings = {"effort": str(data.get("effort") or ""),
                        "permission": str(data.get("permission") or ""),
                        "model": str(data.get("model") or "")}
            conv, turn = _conv_enqueue(cid, task[:8000], settings)
            return self._json({"ok": True, "conversation_id": cid,
                               "turn_id": turn.get("id"),
                               "conversation": _conv_snapshot(cid)})
        if p.startswith("/api/dsh/chat/") and p.endswith("/cancel"):
            cid = p.split("/")[4]
            with _conv_lock():
                conv = _DSH_CONV.get(cid) or _conv_load(cid)
                if conv:
                    for t in conv.get("turns") or []:
                        if t.get("status") == "queued":
                            t["status"] = "canceled"
                    _DSH_CONV[cid] = conv
                    _conv_save(conv)
            try:
                import subprocess as _csp
                for proc in list(_DSH_ACTIVE):
                    try:
                        _csp.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                 capture_output=True, timeout=10)
                    except Exception:
                        pass
            except Exception:
                pass
            return self._json({"ok": True, "conversation": _conv_snapshot(cid)})
        if p == "/api/dsh/agent/stream":
            data = self._read_json()
            task = str(data.get("task") or "").strip()
            if not task:
                return self._json({"error": "task 不能为空"}, 400)
            if len(task) > 8000:
                task = task[:8000]
            sid = str(data.get("session_id") or "").strip()
            self._stream_open()

            def _emit_direct(ev):
                self._stream_write({"type": "event", "event": ev})

            try:
                res = _run_dsh_agent(
                    task, sid,
                    auto_repair=bool(data.get("auto_repair")),
                    effort=str(data.get("effort") or ""),
                    permission=str(data.get("permission") or ""),
                    attach_task_id=str(data.get("attach_task_id") or ""),
                    model=str(data.get("model") or ""),
                    emit=_emit_direct)
                self._stream_write({"type": "result", "result": res})
            except Exception as exc:
                try:
                    self._stream_write({"type": "error", "error": str(exc)})
                except Exception:
                    pass
            return
        if p == "/api/agent/auto/start":
            data = self._read_json()
            stage = str(data.get("stage") or "all")
            jid = _auto_job_start(stage, data)
            return self._json({"ok": True, "job_id": jid, "stage": stage})
        if p == "/api/agent/auto/stream":
            data = self._read_json()
            stage = str(data.get("stage") or "all")
            self._stream_open()
            out = {"ok": True, "stage": stage}

            def _emit_stage(name):
                self._stream_write({"type": "stage", "stage": name})
                return lambda ev: self._stream_write(
                    {"type": "event", "stage": name, "event": ev})

            try:
                if stage == "all":
                    out.update(_auto_cycle_all(emit=_emit_stage("all"),
                                               model=str(data.get("model") or "")))
                else:
                    import sys as _sys
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    if stage == "task":
                        out["task"] = _auto_submit_task(emit=_emit_stage("task"),
                                                    model=str(data.get("model") or ""))
                        out["ok"] = bool(out["task"].get("ok"))
                    if stage == "consumer":
                        _emit_stage("consumer")
                        from dgtf_v2.agent_worker import run_once, write_proposals
                        out["consumer"] = {"run": run_once(), "proposals": write_proposals()}
                    if stage == "proposal":
                        out["proposal"] = _auto_proposal(
                            str(data.get("task_text") or ""), "",
                            emit=_emit_stage("proposal"),
                            model=str(data.get("model") or ""))
                        out["ok"] = bool((out["proposal"] or {}).get("ok"))
                self._stream_write({"type": "result", "result": out})
            except Exception as exc:
                try:
                    self._stream_write({"type": "error", "error": str(exc)})
                except Exception:
                    pass
            return
        if p == "/api/dsh/cancel":
            import subprocess as _csp
            n = 0
            for proc in list(_DSH_ACTIVE):
                try:
                    _csp.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                             capture_output=True, timeout=10)
                    n += 1
                except Exception:
                    try:
                        proc.kill()
                        n += 1
                    except Exception:
                        pass
            return self._json({"ok": True, "cancelled": n})
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
                                     permission=str(data.get("permission") or ""),
                                     attach_task_id=str(data.get("attach_task_id") or ""),
                                     model=str(data.get("model") or ""))
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
        if p == "/api/agent/auto":
            data = self._read_json()
            stage = str(data.get("stage") or "all")
            out = {"ok": True, "stage": stage}
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                if stage == "all":
                    out.update(_auto_cycle_all(model=str(data.get("model") or "")))
                else:
                    if stage == "task":
                        out["task"] = _auto_submit_task(model=str(data.get("model") or ""))
                        out["ok"] = bool(out["task"].get("ok"))
                    if stage == "consumer":
                        from dgtf_v2.agent_worker import run_once, write_proposals
                        out["consumer"] = {"run": run_once(),
                                           "proposals": write_proposals()}
                    if stage == "proposal":
                        out["proposal"] = _auto_proposal(
                            str(data.get("task_text") or ""), "",
                            model=str(data.get("model") or ""))
                        out["ok"] = bool((out["proposal"] or {}).get("ok"))
                return self._json(out)
            except Exception as exc:
                return self._json({"ok": False, "stage": stage,
                                   "error": str(exc)}, 500)
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
        if p == "/api/schedule/preview":
            try:
                return self._json(_schedule_preview(self._read_json()))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
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
            _auto_pareto = bool(opts.pop("auto_pareto", False))
            if _auto_pareto and not opts.get("profile"):
                _pol = _schedule_policy_load()
                opts["profile"] = str(_pol.get("profile") or "方案F-帕累托最优.yaml")
            try:
                tid = runner.start_task(question, opts)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"id": tid, "auto_pareto": _auto_pareto,
                               "profile": opts.get("profile") or ""}, 201)

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
    ap.add_argument("--no-agent-daemon", action="store_true",
                    help="不随 app 启动常驻 Agent 守护（默认启动）")
    ap.add_argument("--keep-agent-daemon", action="store_true",
                    help="app 退出时保留 Agent 守护（默认随 app 退出）")
    ap.add_argument("--agent-interval", type=float, default=60.0,
                    help="Agent 守护轮询间隔秒（默认 %(default)s）")
    ap.add_argument("--agent-knowledge-every", type=int, default=0,
                    help="每 N 轮刷新技术知识；0=关（默认 0，避免自动联网）")
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

    try:
        _ads = start_agent_daemon(interval=60.0)
        if _ads.get("running"):
            print("  Agent 常驻：运行中（pid=%s）" % (_ads.get("pid") or "复用"))
        else:
            print("  Agent 常驻启动失败：%s" % (_ads.get("error") or "未知"))
    except Exception as _e:
        print("  Agent 常驻启动异常（忽略）：%s" % _e)
    try:
        _nj = _auto_jobs_load()
        if _nj:
            print("  后台任务恢复：%d 条（运行中标记 interrupted）" % _nj)
    except Exception as _e:
        print("  后台任务恢复异常（忽略）：%s" % _e)
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

    # ★ 常驻 Agent：app 启动即确保 agent_daemon 在跑（已有实例则复用）。
    #   只消费本地队列、写提案；不联网、不调 LLM。可用 --no-agent-daemon 关闭。
    daemon_started = None
    if not args.no_agent_daemon:
        try:
            st = start_agent_daemon(args.agent_interval,
                                    args.agent_knowledge_every)
            if st.get("ok"):
                tag = "已启动" if st.get("started") else "复用已运行实例"
                ke = ("每 %d 轮" % args.agent_knowledge_every
                      if args.agent_knowledge_every else "关")
                pid_txt = str(st.get("pid") or "外部实例")
                print(f"  Agent 守护：{tag}（pid {pid_txt}，"
                      f"轮询 {int(args.agent_interval)}s，知识刷新 {ke}）")
                daemon_started = st
            else:
                print(f"  Agent 守护未启动：{st.get('error')}")
        except Exception as e:  # noqa: BLE001    守护起不来不该拖垮 app
            print(f"  Agent 守护启动失败（忽略）：{type(e).__name__}: {e}")

    print("  Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        if (daemon_started and daemon_started.get("started")
                and not args.keep_agent_daemon):
            try:
                stop_agent_daemon()
            except Exception as e:  # noqa: BLE001
                print(f"  Agent 守护停止失败（忽略）：{type(e).__name__}: {e}")
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
