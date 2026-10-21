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

APP_VERSION = "1.4.1"

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
# Host 白名单 / CSRF：默认只接受本机回环 Host；--lan 时加入本机地址。
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
_CSRF_TOKEN = secrets.token_urlsafe(32)
_CSRF_COOKIE = "dgtf_csrf"

# DSH Agent 每次运行一个受控工作台工具令牌；只能调用固定动作，不能拿全站权限。
_DSH_TOKENS = {}


def _wb_issue_token(ttl=900, before=None):
    import time as _t_wb
    now = _t_wb.time()
    for k in [k for k, v in list(_DSH_TOKENS.items())
              if float((v or {}).get("exp") or 0) < now]:
        _DSH_TOKENS.pop(k, None)
    tok = secrets.token_urlsafe(24)
    _DSH_TOKENS[tok] = {"exp": now + max(60, int(ttl)),
                        "before": set(before or []),
                        "issued": now}
    try:
        # DSH 的沙箱子进程可能清洗环境变量；令牌文件作为回退通道。
        tf = Path(__file__).resolve().parent.parent / "dgtf_memory" / "dsh_workbench_token"
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text(tok, encoding="utf-8")
    except Exception:
        pass
    return tok


def _wb_token_info(tok):
    import time as _t_wb
    tok = str(tok or "")
    info = _DSH_TOKENS.get(tok)
    if not info or float(info.get("exp") or 0) < _t_wb.time():
        if tok:
            _DSH_TOKENS.pop(tok, None)
        return None
    return info


def _wb_token_ok(tok):
    return _wb_token_info(tok) is not None

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
    global _TOKEN, _ALLOWED_HOSTS
    _TOKEN = token
    _ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
    if str(host) not in ("127.0.0.1", "localhost", "::1"):
        # 显式 --lan：只允许本机网卡地址，不做通配。
        try:
            _ALLOWED_HOSTS.add(str(host))
            for _ip in (lan_ips() or []):
                try:
                    _ALLOWED_HOSTS.add(str(_ip[0] if isinstance(_ip, tuple) else _ip))
                except Exception:
                    pass
            for _ai in socket.getaddrinfo(socket.gethostname(), None):
                try:
                    _ALLOWED_HOSTS.add(str(_ai[4][0]))
                except Exception:
                    pass
        except Exception:
            pass
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.verbose = verbose
    srv.daemon_threads = True
    return srv






_DSH_ACTIVE = set()
_DSH_CONV = {}
_DSH_CONV_ACTIVE = set()
_DSH_CONV_PROCS = {}
_DSH_CONV_CANCELLED = set()
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


# ── Autopilot：常驻开关 + 队列守卫 + 安全提案自动修复 ───────────────
_AUTOPILOT = {
    "thread": None, "stop": None, "lock": None,
    "last_cycle": 0.0, "last_error": "", "last_spawn": 0.0,
    "last_learn": 0.0, "last_scan": 0.0,
}
_AUTOPILOT_CFG_PATH = Path(__file__).resolve().parent.parent / "dgtf_memory" / "agent_autopilot.json"
_AUTOPILOT_SAFE_CATS = {"agent_runtime", "docs", "verification", "process_gap", "quality_signal"}
_AUTOPILOT_MANUAL_CATS = {"fact_correctness", "input_sanity", "probe_quality",
                          "eml_experiment", "noise", "other"}


def _autopilot_lock():
    global _AUTOPILOT
    if _AUTOPILOT.get("lock") is None:
        import threading as _th
        _AUTOPILOT["lock"] = _th.Lock()
    return _AUTOPILOT["lock"]


def _autopilot_cfg_load():
    import json as _json
    base = {"enabled": False, "interval": 120.0, "knowledge_every": 0,
            "started_ts": 0, "last_cycle": 0, "last_learn": 0, "last_scan": 0}
    try:
        d = _json.loads(_AUTOPILOT_CFG_PATH.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            base.update(d)
    except Exception:
        pass
    return base


def _autopilot_cfg_save(cfg):
    import json as _json
    try:
        _AUTOPILOT_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _AUTOPILOT_CFG_PATH.write_text(
            _json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _autopilot_decision(prop):
    """返回 (auto: bool, reason)。只对 pending 做初判；confirmed 视为人工已确认。"""
    st = str(prop.get("status") or "")
    if st == "confirmed":
        return True, "already_confirmed"
    tri = prop.get("triage") or {}
    cat = str(tri.get("category") or "other")
    prio = str(tri.get("priority") or "P2")
    plan = str(prop.get("plan") or "")
    if cat in _AUTOPILOT_MANUAL_CATS:
        return False, "manual_category:" + cat
    if prio == "P0":
        return False, "manual_priority:P0"
    if cat not in _AUTOPILOT_SAFE_CATS:
        return False, "manual_unknown_category"
    if len(plan) < 80 or not any(k in plan for k in
                                ("文件", "验证", "测试", "fast_gate", "验收", "test")):
        return False, "manual_plan_too_weak"
    sec = _security_review_proposal(prop)
    if not sec.get("ok"):
        return False, "security_review:" + str(sec.get("reason") or "risk")
    return True, "safe_auto"


def _autopilot_knowledge(prop):
    """自动修复前检索相关技术知识；结果作为学习材料拼进修复提示。"""
    import time as _t
    key = (str(prop.get("id") or "")[:80] + "|" +
           str((prop.get("task") or {}).get("title") or "")[:80])
    cache = getattr(_autopilot_knowledge, "_cache", {})
    hit = cache.get(key)
    if hit and _t.time() - hit[0] < 1800:
        return hit[1]
    try:
        r = _knowledge_agent_search(
            [str((prop.get("task") or {}).get("title") or "元DGTF 技术优化") + " 最佳实践"],
            mode="query", limit=2)
        items = list(r.get("items") or [])
        lines = []
        for x in items[:2]:
            t = str(x.get("title") or "").strip()
            c = str(x.get("claim") or x.get("content") or "").strip()
            u = str(x.get("url") or "").strip()
            if t or c:
                lines.append("- %s：%s %s" % (t or "资料", c[:500], u))
        text = ("\n\n【自动学习材料（来自技术知识库/联网检索）】\n"
                + "\n".join(lines)) if lines else ""
    except Exception as exc:
        text = ""
        _AUTOPILOT["last_error"] = "learn: %s" % exc
    cache[key] = (_t.time(), text)
    _autopilot_knowledge._cache = cache
    return text


def _autopilot_spawn_proposal():
    """从队列挑一条尚未提案的任务，交给 DSH Agent 读项目后生成修复提案。"""
    import time as _t
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from dgtf_v2.agent_bridge import read_tasks
        tasks = [x for x in read_tasks(limit=80) if x.get("title")]
        if not tasks:
            return None
        have = {str((p.get("task") or {}).get("title") or "").strip()
                for p in _list_proposals(300)}
        task = next((x for x in reversed(tasks)
                     if str(x.get("title") or "").strip() not in have), None)
        if not task:
            return None
        ttl = str(task.get("title") or "").strip()[:160]
        detail = str(task.get("detail") or "")[:1600]
        res = _auto_proposal(task_text=detail, title=ttl, model="deepseek-flash")
        _AUTOPILOT["last_spawn"] = _t.time()
        return res.get("proposal") if isinstance(res, dict) else None
    except Exception as exc:
        _AUTOPILOT["last_error"] = "spawn: %s" % exc
        return None


def _autopilot_learn():
    """常驻期学习：检索当前技术知识，供修复时复用。"""
    import time as _t
    try:
        _knowledge_agent_search(
            ["LLM agent 自我修复 代码优化 2026 官方",
             "元DGTF 调度 记忆 RAG 最佳实践"],
            mode="refresh", limit=3)
        _AUTOPILOT["last_learn"] = _t.time()
        _AUTOPILOT["last_error"] = ""
    except Exception as exc:
        _AUTOPILOT["last_error"] = "learn: %s" % exc


def _autopilot_scan():
    """常驻期自主审视项目：让 DSH Agent 读项目后生成优化提案（不直接改）。"""
    import time as _t
    try:
        title = "自主审视与优化提案 " + _t.strftime("%Y-%m-%d %H:%M")
        _auto_proposal(
            task_text=("请审视当前元DGTF项目（源码、配置、docs、outputs 与最近质量问题），"
                       "结合技术知识库/近期技术趋势，给出 1-3 条可验证的优化或更新提案；"
                       "必须读取项目文件核对，不要直接修改源码。"),
            title=title, model="deepseek-flash")
        _AUTOPILOT["last_scan"] = _t.time()
    except Exception as exc:
        _AUTOPILOT["last_error"] = "scan: %s" % exc


def _autopilot_cycle():
    """一轮常驻：安全提案自动确认并修复；不确定项留人工。"""
    if not _autopilot_cfg_load().get("enabled", True):
        return
    import time as _t
    props = [p for p in _list_proposals(300)
             if str(p.get("status")) in ("pending", "confirmed")]
    # 1) 安全 pending 自动确认；不确定的保留人工
    for p in props:
        if str(p.get("status")) != "pending":
            continue
        auto, reason = _autopilot_decision(p)
        tri = p.get("triage") or {}
        tri["auto_decision"] = "auto" if auto else "manual"
        tri["auto_reason"] = reason
        p["triage"] = tri
        if auto:
            p["status"] = "confirmed"
            p["approver"] = "autopilot"
            import time as _tt
            p["approved_ts"] = _tt.time()
        _save_proposal(p)
    # 2) 只修 confirmed；自动修复内部仍会 fast_gate + 针对性验收
    confirmed = [p for p in _list_proposals(300)
                 if str(p.get("status")) == "confirmed"]
    if confirmed:
        lk = _autopilot_lock()
        if lk.acquire(blocking=False):
            try:
                _autofix_workflow({"autopilot": True, "model": "deepseek-flash"},
                                  lambda _m: None)
                _AUTOPILOT["last_cycle"] = _t.time()
            finally:
                lk.release()
    # 3) 每 30 分钟尝试一次从队列自发提案；每 6 小时学习/审视一次
    now = _t.time()
    if now - float(_AUTOPILOT.get("last_spawn") or 0) > 21600:
        _autopilot_spawn_proposal()
    if now - float(_AUTOPILOT.get("last_learn") or 0) > 21600:
        _autopilot_learn()
    if now - float(_AUTOPILOT.get("last_scan") or 0) > 21600:
        _autopilot_scan()


def _autopilot_loop():
    import time as _t
    stop = _AUTOPILOT.get("stop")
    while stop is not None and not stop.is_set():
        try:
            _autopilot_cycle()
        except Exception as exc:
            _AUTOPILOT["last_error"] = "%s: %s" % (type(exc).__name__, exc)
        try:
            stop.wait(max(15.0, float(_autopilot_cfg_load().get("interval") or 120)))
        except Exception:
            _t.sleep(60)


def _autopilot_status():
    cfg = _autopilot_cfg_load()
    d = agent_daemon_status()
    th = _AUTOPILOT.get("thread")
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "thread_running": bool(th is not None and th.is_alive()),
        "daemon": d,
        "interval": cfg.get("interval", 120),
        "knowledge_every": cfg.get("knowledge_every", 0),
        "last_cycle": _AUTOPILOT.get("last_cycle") or cfg.get("last_cycle") or 0,
        "last_error": _AUTOPILOT.get("last_error", ""),
        "started_ts": cfg.get("started_ts") or 0,
        "policy": {
            "auto_categories": sorted(_AUTOPILOT_SAFE_CATS),
            "human_categories": sorted(_AUTOPILOT_MANUAL_CATS),
            "high_risk_manual": True,
            "requires_fast_gate": True,
            "requires_acceptance": True,
        },
    }


def _autopilot_start(interval=None, knowledge_every=None, start_daemon=True):
    import threading as _th
    import time as _t
    cfg = _autopilot_cfg_load()
    if interval is not None:
        cfg["interval"] = float(interval)
    if knowledge_every is not None:
        cfg["knowledge_every"] = int(knowledge_every)
    cfg["enabled"] = True
    cfg["started_ts"] = cfg.get("started_ts") or _t.time()
    _autopilot_cfg_save(cfg)
    try:
        _paths = _agent_daemon_paths()
        for _sp in (_paths["stop"], _paths["root"] / "dgtf_memory" / "agent_daemon.stop"):
            _sp.unlink(missing_ok=True)
    except Exception:
        pass
    # 启动后先跑队列/修复；自发提案、学习、审视不要立刻烧 API，等首个周期。
    now = _t.time()
    if not _AUTOPILOT.get("last_spawn"):
        _AUTOPILOT["last_spawn"] = now
    if not _AUTOPILOT.get("last_learn"):
        _AUTOPILOT["last_learn"] = now
    if not _AUTOPILOT.get("last_scan"):
        _AUTOPILOT["last_scan"] = now
    st = start_agent_daemon(float(cfg.get("interval") or 120),
                            int(cfg.get("knowledge_every") or 0)) if start_daemon else {}
    th = _AUTOPILOT.get("thread")
    if th is None or not th.is_alive():
        stop = _th.Event()
        _AUTOPILOT["stop"] = stop
        th = _th.Thread(target=_autopilot_loop, daemon=True)
        _AUTOPILOT["thread"] = th
        th.start()
    return _autopilot_status() | {"ok": True, "daemon_start": st}


def _autopilot_stop():
    import time as _t
    cfg = _autopilot_cfg_load()
    cfg["enabled"] = False
    _autopilot_cfg_save(cfg)
    stop = _AUTOPILOT.get("stop")
    if stop is not None:
        stop.set()
    _AUTOPILOT["thread"] = None
    _AUTOPILOT["stop"] = None
    try:
        paths = _agent_daemon_paths()
        # 让 app 拉起的实例和外部复用的实例都收到停止信号
        for sp in (paths["stop"], paths["root"] / "dgtf_memory" / "agent_daemon.stop"):
            try:
                sp.write_text("stop", encoding="utf-8")
            except Exception:
                pass
        # 停止文件保留到下次开启：外部/手工启动的实例也能在下一轮看到并退出。
        time.sleep(0.8)
    except Exception:
        pass
    try:
        stop_agent_daemon()
    except Exception:
        pass
    return _autopilot_status() | {"ok": True, "stopped": True}


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


def _plan_paths(plan):
    """从提案计划抽取显式文件路径；自动提交只放行计划点名的新文件。"""
    import re as _re
    out = set()
    for m in _re.findall(r"[\w./-]+\.[A-Za-z0-9]{1,8}", str(plan or "")):
        p = m.replace("\\", "/").lstrip("./")
        if p and not p.startswith("/") and ".." not in p.split("/"):
            out.add(p)
    return out


def _commit_scope(paths, allowed=None):
    """自动修复只提交源码/文档；运行记录、缓存和计划外新文件不进提交。"""
    out = []
    allowed = set(allowed or [])
    tracked = set()
    try:
        plist = [str(p) for p in paths if p]
        if plist:
            tracked = set((_git(["ls-files", "--"] + plist).get("out") or "").splitlines())
    except Exception:
        tracked = set()
    for p in paths:
        p = str(p or "").strip()
        if not p or p.startswith(_RUNTIME_PREFIXES):
            continue
        if p.endswith((".log", ".pyc", ".sqlite3")):
            continue
        if allowed and p not in tracked and p not in allowed:
            continue
        out.append(p)
    return out


def _auto_commit(before: set, task: str, before_head: str = "", before_fp=None,
                 allowed=None):
    after = _git_snapshot()
    new = after - before
    if before_fp is not None:
        # 本轮新出现的 ∪ run 前就脏、本轮内容又变了的（后者集合差看不见）
        cur = _git_fingerprints()
        new = new | {p for p in (after & set(before_fp))
                     if cur.get(p) != before_fp.get(p)}
    new = _commit_scope(sorted(new), allowed=allowed)
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


_PROP_TEXT_CACHE = {}


def _prop_cached_text(path):
    import os as _os
    try:
        st = _os.stat(str(path))
        key = (int(st.st_mtime_ns), int(st.st_size))
    except Exception:
        return ""
    hit = _PROP_TEXT_CACHE.get(str(path))
    if hit and hit[0] == key:
        return hit[1]
    try:
        txt = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        txt = ""
    _PROP_TEXT_CACHE[str(path)] = (key, txt)
    return txt


def _proposal_project_context():
    """项目实时指纹：HEAD、关键文件 mtime、队列规模。用于判断提案是否已被新版本修掉。"""
    import hashlib as _hash
    import os as _os
    import subprocess as _sub
    import time as _t
    root = Path(__file__).resolve().parent.parent
    head = ""
    head_ts = 0
    try:
        r = _sub.run(["git", "rev-parse", "HEAD"], cwd=str(root), text=True,
                     capture_output=True, timeout=5)
        head = (r.stdout or "").strip()
        r2 = _sub.run(["git", "log", "-1", "--format=%ct", "HEAD"], cwd=str(root),
                      text=True, capture_output=True, timeout=5)
        head_ts = int((r2.stdout or "0").strip() or 0)
    except Exception:
        pass
    files = ["元DGTF-V1.30.0.py", "dgtf_v2/agent_bridge.py",
             "dgtf_app/server.py", "dgtf_app/static/app.js"]
    parts = [head]
    mtimes = {}
    for rel in files:
        try:
            st = _os.stat(str(root / rel))
            mtimes[rel] = float(st.st_mtime)
            parts.append("%s:%d:%d" % (rel, int(st.st_mtime), int(st.st_size)))
        except Exception:
            mtimes[rel] = 0.0
    q = root / "dgtf_memory" / "agent_tasks.jsonl"
    try:
        qn = sum(1 for _ in q.open(encoding="utf-8", errors="replace"))
    except Exception:
        qn = 0
    eng = _prop_cached_text(root / "元DGTF-V1.30.0.py")
    br = _prop_cached_text(root / "dgtf_v2/agent_bridge.py")
    return {
        "head": head[:12],
        "head_ts": head_ts,
        "fingerprint": _hash.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16],
        "queue_n": qn,
        "checked_at": _t.time(),
        "mtimes": mtimes,
        "fixed": {
            "fact_wording": "官方记录日期" in eng,
            "probe_link_guard": "只有确实带 id 形态" in eng,
            "input_sanity": "neutralize_negative_claims" in eng,
            "queue_gate": "_is_fixture_run" in br,
        },
    }


def _prop_classify(title, detail, severity):
    """提案归类 + 优先级（P0 最高，P3 最低）。"""
    t = str(title or "")
    low = t.lower()
    if (not t) or t.count("?") >= 2 or t in (
            "根据生成的提案执行任务", "app ????", "?? Tool Calls ??"):
        return "noise", "P3"
    if "EML" in t or "eml_candidate" in str(detail):
        return "eml_experiment", "P3"
    if ("验收" in t or "验证" in t) and ("探针" in t or "自动修复" in t or "autofix" in low):
        return "verification", "P2"
    if ("docs/" in t) or ("文档" in t):
        return "docs", "P2"
    if ("事实" in t) or ("发布" in t) or ("日期" in t and "事实" in str(detail)):
        return "fact_correctness", "P0" if severity == "high" else "P1"
    if "输入自检" in t:
        return "input_sanity", "P0"
    if ("probe_link" in low) or ("悬空" in t) or ("误报" in t) or ("闭合" in t):
        return "probe_quality", "P1" if severity in ("high", "med") else "P2"
    if ("队列" in t) or ("Tool Calls" in t) or ("Agent" in t and "来源" in t):
        return "agent_runtime", "P1" if severity in ("high", "med") else "P2"
    if "质量线索" in t:
        return "quality_signal", "P2"
    if ("层 " in t and "过程标准" in t):
        return "process_gap", "P2"
    return "other", "P2"


def _proposal_triage():
    """自动分诊：归类、优先级、过期原因、项目实时对账、历史留存。

    只改状态和 triage 元数据，不删除提案文件；每次分诊写 _index.json 留存。
    """
    import json as _json
    import time as _t
    now = _t.time()
    ctx = _proposal_project_context()
    per = _proposal_dir()
    rows = []
    for p in per.glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            rec = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        rec["_path"] = p
        if not rec.get("ts"):
            rec["ts"] = p.stat().st_mtime
        rows.append(rec)

    rank = {"applied": 5, "confirmed": 4, "pending": 3, "failed": 2,
            "rolled_back": 1, "expired": 0}
    changed = set()

    # 1) 分诊 + 过期规则
    for rec in rows:
        st = str(rec.get("status") or "pending")
        task = rec.get("task") or {}
        title = str(task.get("title") or "").strip()
        detail = str(task.get("detail") or "")
        sev = str(task.get("severity") or "")
        cat, prio = _prop_classify(title, detail, sev)
        age = now - float(rec.get("ts") or now)
        fixed_reason = ""
        if st in ("pending", "confirmed"):
            if cat == "noise":
                fixed_reason = "noise_or_self_referential"
            elif ('"rounds":0' in detail.replace(" ", "")
                  and '"product_chars":0' in detail.replace(" ", "")):
                fixed_reason = "fixture_empty_run"
            elif cat == "fact_correctness" and ctx["fixed"]["fact_wording"] and ctx["mtimes"].get("元DGTF-V1.30.0.py", 0) > float(rec.get("ts") or 0):
                fixed_reason = "fixed_fact_wording_in_current_project"
            elif cat == "probe_quality" and ctx["fixed"]["probe_link_guard"] and ctx["mtimes"].get("元DGTF-V1.30.0.py", 0) > float(rec.get("ts") or 0):
                fixed_reason = "fixed_probe_link_guard_in_current_project"
            elif cat == "input_sanity" and ctx["fixed"]["input_sanity"] and ctx["mtimes"].get("元DGTF-V1.30.0.py", 0) > float(rec.get("ts") or 0):
                fixed_reason = "fixed_input_sanity_in_current_project"
            elif cat == "agent_runtime" and ctx["fixed"]["queue_gate"] and ctx["mtimes"].get("dgtf_v2/agent_bridge.py", 0) > float(rec.get("ts") or 0):
                fixed_reason = "fixed_queue_gate_in_current_project"
            elif st == "pending" and age > 86400:
                fixed_reason = "pending_ttl_24h"
            elif st == "confirmed" and age > 3 * 86400:
                fixed_reason = "confirmed_ttl_72h"
            elif sev == "low" and age > 86400:
                fixed_reason = "low_stale_quality"
        if fixed_reason:
            rec["status"] = "expired"
            rec["expired_reason"] = fixed_reason
            rec["expired_ts"] = now
            changed.add(id(rec))
            st = "expired"
        rec["triage"] = {
            "category": cat,
            "priority": prio,
            "action": ("skip" if st == "expired" else
                       ("resolved" if st == "applied" else
                        ("observe" if st in ("failed", "rolled_back") else "repair"))),
            "reason": rec.get("expired_reason") or
                      ("already_applied" if st == "applied" else
                       ("repair_failed" if st == "failed" else
                        ("rolled_back" if st == "rolled_back" else "needs_attention"))),
            "decided_ts": now,
            "project": {"head": ctx["head"], "fingerprint": ctx["fingerprint"],
                        "checked_at": ctx["checked_at"]},
        }

    # 2) 同标题去重：保留最优状态 + 最新一条
    groups = {}
    for rec in rows:
        if str(rec.get("status")) == "expired":
            continue
        title = str((rec.get("task") or {}).get("title") or "").strip()
        if title:
            groups.setdefault(title, []).append(rec)
    for title, items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda r: (rank.get(str(r.get("status")), 0),
                                  float(r.get("ts") or 0)), reverse=True)
        keeper = str(items[0].get("status"))
        for rec in items[1:]:
            if str(rec.get("status")) in ("pending", "confirmed"):
                rec["status"] = "expired"
                rec["expired_reason"] = ("duplicate_of_" + keeper
                                         if keeper in ("applied", "confirmed")
                                         else "duplicate_older")
                rec["expired_ts"] = now
                tri = rec.get("triage") or {}
                tri["action"] = "skip"
                tri["reason"] = rec["expired_reason"]
                rec["triage"] = tri
                changed.add(id(rec))

    # 3) 保存变更 + 分诊历史
    for rec in rows:
        p = rec.pop("_path", None)
        tri = rec.get("triage") or {}
        hist = rec.setdefault("triage_history", [])
        sig = (tri.get("category"), tri.get("priority"), tri.get("action"),
               tri.get("reason"), rec.get("status"))
        if not hist or hist[-1].get("sig") != list(sig):
            hist.append({"ts": now, "sig": list(sig), "project": ctx["head"]})
            rec["triage_history"] = hist[-20:]
            changed.add(id(rec))
        if p is not None and id(rec) in changed:
            p.write_text(_json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    # 4) 留档索引（按分类/优先级聚合）
    from collections import Counter as _Counter
    items = []
    for rec in rows:
        tri = rec.get("triage") or {}
        items.append({
            "id": rec.get("id"), "title": (rec.get("task") or {}).get("title"),
            "status": rec.get("status"), "category": tri.get("category"),
            "priority": tri.get("priority"), "reason": tri.get("reason"),
            "ts": rec.get("ts"), "expired_ts": rec.get("expired_ts"),
            "applied_ts": rec.get("applied_ts"),
        })
    index = {
        "generated_at": now,
        "project": {"head": ctx["head"], "fingerprint": ctx["fingerprint"],
                    "queue_n": ctx["queue_n"]},
        "counts": dict(_Counter(str(x.get("status")) for x in rows)),
        "by_category": dict(_Counter(str(x.get("category")) for x in items)),
        "by_priority": dict(_Counter(str(x.get("priority")) for x in items)),
        "items": sorted(items, key=lambda x: float(x.get("ts") or 0), reverse=True),
    }
    try:
        (per / "_index.json").write_text(
            _json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _proposal_summary():
    import json as _json
    p = _proposal_dir() / "_index.json"
    try:
        d = _json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: d.get(k) for k in ("generated_at", "project", "counts",
                                   "by_category", "by_priority")}


def _list_proposals(limit=300):
    _proposal_triage()
    import json as _json
    rows = []
    for p in _proposal_dir().glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            rec = _json.loads(p.read_text(encoding="utf-8"))
            # 老提案可能没有 ts；用文件 mtime 兜底，保证「修复提案」列表不出现空时间。
            if isinstance(rec, dict) and not rec.get("ts"):
                rec["ts"] = p.stat().st_mtime
            rows.append(rec)
        except Exception:
            pass
    # 按提案自身 ts 排序（过期标记会更新文件 mtime，不能再用 mtime 排序）
    rows.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
    return rows[:max(1, int(limit))]


def _get_proposal(pid):
    import json as _json
    p = _proposal_dir() / (str(pid) + ".json")
    if not p.exists():
        return {}
    try:
        rec = _json.loads(p.read_text(encoding="utf-8"))
        if isinstance(rec, dict) and not rec.get("ts"):
            rec["ts"] = p.stat().st_mtime
        return rec
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
        rec = _get_dsh_session(sid) or {}
        return {"id": str(sid),
                # 优先会话记录时间，缺失时回退产物文件 mtime，详情页才有时间可标。
                "ts": rec.get("ts") or p.stat().st_mtime,
                "mtime": p.stat().st_mtime,
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


def _run_dsh_agent_raw(task: str, sid: str = "", timeout: int = 300,
                   auto_repair: bool = False, effort: str = "",
                   permission: str = "", attach_task_id: str = "",
                   model: str = "", emit=None, proc_ref=None) -> dict:
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
    _orig_perm = str(permission or "").strip()
    _auto_review = (_orig_perm == "auto")
    if _orig_perm in ("read-only", "workspace-write", "danger-full-access"):
        _perm = _orig_perm
    elif _auto_review:
        _perm = "workspace-write"
    else:
        _perm = "workspace-write"
    env["DSH_PERMISSION_MODE"] = _perm
    env["DGTF_DSH_PERMISSION_MODE"] = _orig_perm or _perm
    env["DGTF_AUTO_REVIEW"] = "1" if _auto_review else "0"
    _perm_warn = ""
    if _orig_perm == "auto":
        _perm_warn = "自动审查：DSH 使用 workspace-write，工作台负责安全审查"
    elif _orig_perm == "danger-full-access":
        _perm_warn = "完全访问：用户已选择，DSH 可越过工作区写入限制"
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    _wb_token = _wb_issue_token(int(timeout or 600) + 120, before=_before)
    env["DGTF_WORKBENCH_TOKEN"] = _wb_token
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
    _allow_write = bool(auto_repair or _perm != "read-only")
    if _perm == "danger-full-access":
        _mode = ("完全访问模式（用户已明确选择）：可读写工作区及本机文件；"
                 "仍不得把密钥/项目内容发到 API 以外的外部服务，禁止联网上传；"
                 "不要执行 git add / git commit / push，由工作台统一提交。")
    elif _allow_write:
        _mode = ("你可以读取并修改项目工作区文件；修改源码后不要直接跑 fast_gate（"
                 "Windows 沙箱临时写会被 ACL 拦），工作台会统一跑；不要执行 git add / git commit / push，"
                 "由工作台统一提交。不得读取或修改 .env、密钥、凭据、.git 内部文件；"
                 "不得把项目内容发到 API 以外的外部服务；禁止联网上传。")
    else:
        _mode = "只读模式：只读取项目文件，不修改任何文件。"
    if _auto_review:
        _mode += " 当前为自动审查模式：高风险操作仍应停下说明，由工作台/用户确认。"
    auth = ("你在元DGTF项目根目录：%s。请始终使用简体中文回答，"
            "思考过程（thinking）也必须使用简体中文，禁止输出英文思考；"
            "包括思考摘要、解释和最终答复；代码/命令保持原文。"
            "你有权读取该工作区内的项目文件、"
            "outputs/ 产物、docs/、dgtf_memory/、app 导入文件与配置；"
            "%s 不要泄露密钥；禁止联网搜索、网页抓取、上传文件到第三方服务；"
            "只允许通过 DeepSeek API 做本地推理。%s\n用户请求：%s"
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
    if _perm == "read-only":
        _pl += ["- id: permission",
                "  name: '@deepseek-ai/dsh-permission-presets'",
                "  config:",
                "    defaultPreset: read-only",
                "    presets:",
                "      read-only:",
                "        sandbox: read-only",
                "        approval: never"]
    elif _perm:
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
    proc = None
    _guard_blocked = []
    _secret_vals = [x for x in (key, env.get("TAVILY_API_KEY", ""),
                                env.get("DGTF_API_KEY", ""),
                                env.get("DGTF_WORKBENCH_TOKEN", "")) if x]
    _sensitive_paths = (".env", ".credentials", "dsh_conversations",
                        "agent_autopilot.json", "id_rsa", "authorized_keys")
    _block_sensitive = (_perm != "danger-full-access")

    def _redact_obj(obj):
        if isinstance(obj, str):
            out = obj
            for sv in _secret_vals:
                if sv and sv in out:
                    out = out.replace(sv, "[REDACTED]")
            return out
        if isinstance(obj, list):
            return [_redact_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _redact_obj(v) for k, v in obj.items()}
        return obj

    def _feed(line):
        nonlocal sid, final
        line = (line or "").strip()
        if not line.startswith("{"):
            return
        try:
            ev = json.loads(line)
        except Exception:
            return
        if ev.get("type") == "tool_call" and _block_sensitive:
            blob = json.dumps(ev.get("input") or {}, ensure_ascii=False).lower()
            hit = next((p for p in _sensitive_paths if p in blob), "")
            if hit:
                _guard_blocked.append(hit)
                try:
                    if proc is not None:
                        proc.kill()
                except Exception:
                    pass
                ev = {"type": "text",
                      "text": "[安全拦截] DSH Agent 尝试访问受保护路径，已终止本轮。"}
        ev = _redact_obj(ev)
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
        # ★ 实时流式读取：stdout 逐行 _feed（立刻 emit 给会话快照），
        #   stderr 用独立线程排空；主线程带超时等待，避免 communicate()
        #   把整轮输出憋到进程退出后才显示。
        import queue as _q
        import threading as _th
        import time as _t
        proc = _sp.Popen(cmd, cwd=str(root), env=env,
                         stdin=_sp.PIPE, stdout=_sp.PIPE,
                         stderr=_sp.PIPE, text=True,
                         encoding="utf-8", errors="replace")
        _DSH_ACTIVE.add(proc)
        if proc_ref is not None:
            try:
                proc_ref(proc)
            except Exception:
                pass
        _qout = _q.Queue()
        _err_chunks = []

        def _read_out():
            try:
                for _line in proc.stdout:
                    _qout.put(_line)
            except Exception:
                pass

        def _read_err():
            try:
                _err_chunks.append(proc.stderr.read() or "")
            except Exception:
                pass

        _to = _th.Thread(target=_read_out, daemon=True)
        _te = _th.Thread(target=_read_err, daemon=True)
        _to.start()
        _te.start()
        try:
            if proc.stdin is not None:
                if auth:
                    proc.stdin.write(auth)
                    proc.stdin.flush()
                proc.stdin.close()
        except Exception:
            pass
        _timed_out = False
        _deadline = _t.monotonic() + max(1, int(timeout))
        while True:
            _remain = _deadline - _t.monotonic()
            if _remain <= 0:
                _timed_out = True
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            try:
                _line = _qout.get(timeout=min(0.2, _remain))
            except _q.Empty:
                if proc.poll() is not None:
                    break
                continue
            _feed(_line)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        _to.join(timeout=2)
        _te.join(timeout=2)
        while True:
            try:
                _line = _qout.get_nowait()
            except _q.Empty:
                break
            _feed(_line)
        err_text = "".join(_err_chunks)
        if _timed_out:
            out = {"ok": False, "error": "DSH timeout",
                   "timeout": int(timeout), "session_id": sid,
                   "text": final or "".join(texts),
                   "events": events[-200:],
                   "settings": {"effort": _eff, "permission": _perm,
                          "permission_selected": _orig_perm or _perm,
                          "auto_review": _auto_review,
                          "write": _allow_write,
                          "permission_warning": _perm_warn},
                   "attach_task_id": str(attach_task_id or ""),
                   "stderr": (err_text or "")[-2000:]}
            if _guard_blocked:
                out["ok"] = False
                out["error"] = "DSH security guard: " + ",".join(_guard_blocked[:3])
                out["security_blocked"] = list(_guard_blocked[:3])
            _save_dsh_run(task, sid, out, auto_repair)
            return out
        rc = proc.returncode
        stderr = (err_text or "")[-2000:]
    finally:
        if proc is not None:
            _DSH_ACTIVE.discard(proc)
            if proc_ref is not None:
                try:
                    proc_ref(None)
                except Exception:
                    pass
        if _patch:
            try: Path(_patch).unlink()
            except Exception: pass
    out = {"ok": (rc == 0), "session_id": sid,
           "text": final or "".join(texts),
           "events": events[-200:],
           "settings": {"effort": _eff, "permission": _perm,
                         "permission_selected": _orig_perm or _perm,
                         "auto_review": _auto_review,
                         "write": _allow_write,
                         "permission_warning": _perm_warn},
           "attach_task_id": str(attach_task_id or ""),
           "stderr": stderr}
    if _guard_blocked:
        out["ok"] = False
        out["error"] = "DSH security guard: " + ",".join(_guard_blocked[:3])
        out["security_blocked"] = list(_guard_blocked[:3])
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
                _changed = _changed_since(_before, _before_fp)
                out["acceptance"] = _targeted_acceptance(_changed)
                if out["acceptance"].get("ok"):
                    out["repair"] = _auto_commit(_before, task, _before_head,
                                                 _before_fp)
                else:
                    out["repair"] = {"committed": False, "changed": _changed,
                                     "why": "针对性验收未通过，未提交"}
            else:
                out["repair"] = {"committed": False, "why": "fast_gate 未通过"}
        except Exception as exc:
            out["repair"] = {"committed": False, "why": str(exc)}
    return out


def _run_dsh_agent(task: str, *args, **kwargs):
    """带 DSH 会话留痕的 Agent 调用：事件实时写入 dsh_conversations，可在 DSH 会话页回看。"""
    import time as _t
    cid = "dshrun-" + str(int(_t.time() * 1000))
    tid = "turn-" + str(int(_t.time() * 1000))
    conv = {"id": cid, "session_id": "", "created_at": _t.time(),
            "updated_at": _t.time(),
            "turns": [{"id": tid, "task": str(task), "status": "running",
                       "events": [], "text": "", "ts_start": _t.time()}]}
    try:
        _DSH_CONV[cid] = conv
        _conv_save(conv)
    except Exception:
        pass
    _emit0 = kwargs.get("emit")

    def _emit(ev):
        try:
            _conv_event(cid, tid, ev)
        except Exception:
            pass
        if _emit0 is not None:
            try:
                _emit0(ev)
            except Exception:
                pass

    kwargs["emit"] = _emit
    try:
        task = (str(task) + "\n\n[工作台接入] 你是本 app 内置 DSH Agent；"
                "可用受控工具：python dgtf_app/dsh_tool.py "
                "status|fast_gate|acceptance|project|proposals|queue。"
                "工具结果仅作参考；最终验收和提交由工作台复核。")
    except Exception:
        pass
    res = _run_dsh_agent_raw(task, *args, **kwargs)
    try:
        conv = _DSH_CONV.get(cid) or conv
        for x in conv.get("turns") or []:
            if x.get("id") == tid:
                x["status"] = "done" if res.get("ok") else "error"
                x["events"] = list(res.get("events") or x.get("events") or [])
                x["text"] = str(res.get("text") or "")
                x["ts_end"] = _t.time()
                break
        if res.get("session_id"):
            conv["session_id"] = str(res["session_id"])
        conv["updated_at"] = _t.time()
        _DSH_CONV[cid] = conv
        _conv_save(conv)
    except Exception:
        pass
    res["conversation_id"] = cid
    return res


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
    prompt = ("提案模式：允许读取项目文件核对现状，但不要修改源码。只根据下面任务详情"
              "输出简短修复提案（≤200字）：涉及文件、步骤、风险、验证命令。"
              "任务：" + str(t.get("title") or "") + "。详情："
              + str(t.get("detail") or "")[:1200])
    res = _run_dsh_agent(prompt, "", timeout=300, auto_repair=False,
                         emit=emit, model=model)
    pid = "prop-" + str(int(_tm.time() * 1000))
    plan = str(res.get("text") or "")
    blocked = bool(res.get("security_blocked")) or ("[安全拦截]" in plan)
    prop = _save_proposal({"id": pid, "ts": _tm.time(), "task": t,
                           "plan": plan,
                           "session_id": res.get("session_id") or "",
                           "conversation_id": res.get("conversation_id") or "",
                           "status": ("expired" if blocked else "pending"),
                           "approver": "",
                           "expired_reason": ("security_blocked_tool_access" if blocked else ""),
                           "events": list(res.get("events") or [])[-50:]})
    return {"ok": bool(res.get("ok")) and not blocked, "proposal": prop}


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
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    for cmd in cmds:
        try:
            p = _sp.run(cmd[:2], cwd=str(root), text=True, encoding="utf-8",
                        errors="replace", capture_output=True, timeout=600,
                        env=env)
            good = p.returncode == 0
            ok = ok and good
            out.append({"name": cmd[2], "ok": good,
                        "tail": ((p.stdout or "") + (p.stderr or ""))[-1200:]})
        except Exception as exc:
            ok = False
            out.append({"name": cmd[2], "ok": False, "tail": str(exc)})
    return {"ok": ok, "checks": out}


_SECURITY_RISK_TERMS = (
    ".env", "credential", "password", "secret", "api_key", "danger-full-access",
    "eval(", "exec(", "pickle.loads", "subprocess", "shell=true", "rm -rf",
    "git push", "authorized_keys", "private key",
)
_SECURITY_CODE_EXTS = (".py", ".js", ".ts", ".json", ".yaml", ".yml",
                       ".ps1", ".cmd", ".bat", ".sh")


def _security_review_proposal(prop):
    """自动修复前的静态安全门槛：高风险/敏感词一律转人工。"""
    txt = (str(prop.get("plan") or "") + " " +
           str((prop.get("task") or {}).get("title") or "") + " " +
           str((prop.get("task") or {}).get("detail") or "")).lower()
    for term in _SECURITY_RISK_TERMS:
        if term in txt:
            return {"ok": False, "reason": "sensitive_term:" + term}
    return {"ok": True, "reason": "no_sensitive_term"}


def _security_scan_changed(changed):
    """提交前扫描新增代码/配置中的密钥与危险执行面；命中即不提交。"""
    import re as _re
    findings = []
    patterns = [
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private_key"),
        (r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}", "hardcoded_secret"),
        (r"\beval\s*\(", "eval"),
        (r"\bexec\s*\(", "exec"),
        (r"pickle\.loads", "pickle_loads"),
        (r"(?i)shell\s*=\s*True", "shell_true"),
        (r"danger-full-access", "danger_full_access"),
    ]
    for p in changed or []:
        path = str(p)
        if not path.lower().endswith(_SECURITY_CODE_EXTS):
            continue
        try:
            path_obj = Path(__file__).resolve().parent.parent / path
            if not path_obj.is_file():
                continue
            # 只看新增行，避免已有代码里的敏感词误伤。
            added = []
            for args in (["diff", "--unified=0", "--", path],
                         ["diff", "--cached", "--unified=0", "--", path]):
                d = _git(args).get("out") or ""
                added += [ln[1:] for ln in d.splitlines()
                          if ln.startswith("+") and not ln.startswith("+++")]
            lines = added or path_obj.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for ln in lines:
            for pat, name in patterns:
                if _re.search(pat, ln):
                    findings.append({"file": path, "rule": name})
                    break
    return {"ok": not findings, "findings": findings[:20]}


def _changed_since(before, before_fp=None):
    """当前相对修复前快照的变更文件（含修复前已脏但内容再变的）。"""
    after = _git_snapshot()
    new = after - set(before or [])
    if before_fp is not None:
        cur = _git_fingerprints()
        new = new | {p for p in (after & set(before_fp))
                     if cur.get(p) != before_fp.get(p)}
    return sorted(new)


def _run_fast_gate():
    import subprocess as _sp
    import sys as _sys
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        g = _sp.run([_sys.executable, "fast_gate.py"], cwd=str(root),
                    text=True, encoding="utf-8", errors="replace",
                    capture_output=True, timeout=300, env=env)
        return {"ok": g.returncode == 0,
                "tail": ((g.stdout or "") + (g.stderr or ""))[-1600:]}
    except Exception as exc:
        return {"ok": False, "tail": str(exc)}


def _repair_with_acceptance(prop, model="", emit=None, max_attempts=3,
                            extra_context="", permission=""):
    """修复 → fast_gate → 针对性验收；不通过就带着失败信息继续修，直到通过才提交。

    关键：DSH 阶段 auto_repair=False，不提前 git commit；工作台验收通过后
    才调用 _auto_commit。这样「验收不过」绝不会留下已提交的坏变更。
    """
    import time as _t
    root = Path(__file__).resolve().parent.parent
    before = _git_snapshot()
    before_fp = _git_fingerprints()
    before_head = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
    plan = str(prop.get("plan") or "")
    task = str(((prop.get("task") or {}).get("title")) or prop.get("id") or "")
    sid = str(prop.get("session_id") or "")
    convs, attempts = [], []
    prompt = ("按以下已确认提案执行修复：" + plan +
              "。先读取相关项目文件核对；只修改方案涉及的文件；"
              "不要在你的沙箱里直接运行 fast_gate.py（沙箱临时写在 Windows 上会被 ACL 拦）；"
              "如需自检，可运行受控工具：python dgtf_app/dsh_tool.py fast_gate "
              "或 python dgtf_app/dsh_tool.py acceptance 查看工作台结果；"
              "不要执行 git add / git commit / push；最终验收与提交由工作台统一执行。"
              + str(extra_context or ""))
    last_gate, last_acc, last_repair, last_sec = {}, {}, {}, {}
    for n in range(1, max(1, int(max_attempts)) + 1):
        if emit is not None:
            try:
                emit({"type": "text", "text": "修复第 %d 轮：DSH 修改中…" % n})
            except Exception:
                pass
        res = _run_dsh_agent(prompt, sid, timeout=600, auto_repair=False,
                             model=str(model or ""), emit=emit,
                             permission=str(permission or ""))
        sid = str(res.get("session_id") or sid)
        # 即使 DSH 自行提交，也先退回工作区（保留改动），验收通过后再统一提交。
        _now_head = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
        if before_head and _now_head and _now_head != before_head:
            _git(["reset", "--mixed", before_head])
        if res.get("conversation_id"):
            convs.append(str(res["conversation_id"]))
        # 只把源码/文档纳入验收与安全审查；DSH 会话文件、日志等运行产物不算变更。
        changed = _commit_scope(_changed_since(before, before_fp))
        last_gate = _run_fast_gate()
        last_acc = _targeted_acceptance(changed) if changed else {
            "ok": False, "checks": [{"name": "changed", "ok": False,
                                     "tail": "本轮没有文件变更"}]}
        last_sec = _security_scan_changed(_commit_scope(changed))
        attempts.append({"attempt": n, "changed": changed,
                         "gate": last_gate, "acceptance": last_acc,
                         "security": last_sec,
                         "conversation_id": res.get("conversation_id")})
        if not last_sec.get("ok"):
            # 安全审查不通过：绝不提交，交人工。
            return {"ok": False, "gate": last_gate, "acceptance": last_acc,
                    "security": last_sec,
                    "repair": {"committed": False,
                               "why": "安全审查未通过，未提交"},
                    "attempts": attempts, "conversation_ids": convs,
                    "conversation_id": convs[-1] if convs else "",
                    "session_id": sid, "events": list(res.get("events") or [])}
        if last_gate.get("ok") and last_acc.get("ok"):
            last_repair = _auto_commit(before, task, before_head, before_fp,
                                         allowed=_plan_paths(plan))
            return {"ok": bool(last_repair.get("committed")),
                    "gate": last_gate, "acceptance": last_acc,
                    "security": last_sec,
                    "repair": last_repair, "attempts": attempts,
                    "conversation_ids": convs,
                    "conversation_id": convs[-1] if convs else "",
                    "session_id": sid, "events": list(res.get("events") or [])}
        if not changed:
            break
        # 把失败原因回灌给同一个 DSH 会话继续修；仍不允许提交。
        fail = ("上一轮未通过，必须继续修复；不要提交 git。\n"
                "fast_gate：%s\n%s\n\n针对性验收：%s\n%s"
                % ("PASS" if last_gate.get("ok") else "FAIL",
                   str(last_gate.get("tail") or "")[-1200:],
                   "PASS" if last_acc.get("ok") else "FAIL",
                   json.dumps(last_acc.get("checks") or [], ensure_ascii=False)[-1600:]))
        prompt = ("继续修复同一提案，直到工作台验收通过为止。\n" + fail +
                  "\n\n提案：" + plan + str(extra_context or ""))
    _now_head = (_git(["rev-parse", "HEAD"]).get("out") or "").strip()
    if before_head and _now_head and _now_head != before_head:
        _git(["reset", "--mixed", before_head])
    return {"ok": False, "gate": last_gate, "acceptance": last_acc,
            "security": last_sec,
            "repair": {"committed": False, "why": "验收未通过，已停止且未提交"},
            "attempts": attempts, "conversation_ids": convs,
            "conversation_id": convs[-1] if convs else "",
            "session_id": sid, "events": []}


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


def _fmt_epoch_cn(v):
    """epoch 秒 → 本地可读时间；空/非法返回空串。"""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(v)))
    except (TypeError, ValueError, OSError):
        return ""


def _arxiv_refresh(queries, limit=3):
    """arXiv API 兜底刷新：无需商 key，抓最新论文摘要入库。"""
    import json as _json
    import urllib.parse as _up
    import urllib.request as _ur
    import xml.etree.ElementTree as _ET
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dgtf_v2.agent_bridge import DEFAULT_KNOWLEDGE
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    p = Path(DEFAULT_KNOWLEDGE)
    p.parent.mkdir(parents=True, exist_ok=True)
    for q in [str(x) for x in (queries or [])][:3]:
        t_search = time.time()
        term = _up.quote('all:"' + q[:80].replace('"', " ") + '"')
        url = ("https://export.arxiv.org/api/query?search_query=" + term
               + "&start=0&max_results=3&sortBy=submittedDate&sortOrder=descending")
        try:
            req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with _ur.urlopen(req, timeout=30) as r:
                root = _ET.fromstring(r.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        for e in root.findall("a:entry", ns)[:2]:
            title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
            link = (e.findtext("a:id", default="", namespaces=ns) or "").strip()
            summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
            pub = (e.findtext("a:published", default="", namespaces=ns) or "").strip()
            if not title or not link:
                continue
            item = {"run": "arxiv_refresh", "query": q[:200],
                    "title": title[:300], "url": link,
                    "claim": summary[:400], "summary": summary[:1200],
                    "content": summary[:4000], "fetched": True,
                    "published": pub, "source_type": "paper",
                    "pdf_url": link.replace("/abs/", "/pdf/"), "authority": 2,
                    # arXiv API 一次请求同时完成检索与摘要抓取；
                    # 两个时间都落库，前端可分别展示。
                    "retrieved_at": t_search, "fetched_at": time.time()}
            out.append(item)
            with p.open("a", encoding="utf-8") as fh:
                fh.write(_json.dumps(item, ensure_ascii=False) + "\n")
    return out


def _auto_refresh_knowledge(emit=None, queries=None):
    """技术知识刷新：DeepSeek Search + 入库去重；无 key 时优雅降级。"""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dgtf_v2.agent_bridge import (refresh_knowledge_http,
                                      knowledge_stats, dedupe_knowledge)
    qs = [str(q) for q in (queries or []) if str(q).strip()][:4]
    if not qs:
        qs = ["event memory large language model",
              "multi-agent scheduling LLM",
              "self-evolving agents feedback"]
    if emit:
        emit({"type": "text", "text": "技术知识刷新：" + " / ".join(qs)})
    try:
        res = refresh_knowledge_http(qs, return_stats=True, limit=2)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "queries": qs,
                "stats": {"items": [], "skipped_duplicates": 0}}
    items = list(res.get("items") or [])
    if not items:
        try:
            items = _arxiv_refresh(qs, limit=3)
        except Exception:
            items = []
    if not items:
        try:
            items = _arxiv_refresh(["event memory", "multi-agent scheduling"], limit=2)
        except Exception:
            items = []
    try:
        res["items"] = items
    except Exception:
        pass
    for it in items[:6]:
        if emit:
            emit({"type": "text",
                  "text": "知识入库：" + str(it.get("title") or "")[:120]
                          + "  " + str(it.get("url") or "")[:200]})
    try:
        ded = dedupe_knowledge()
        ks = knowledge_stats()
    except Exception as exc:
        ded, ks = {"error": str(exc)}, {}
    return {"ok": bool(items), "queries": qs,
            "stats": res, "dedupe": ded, "knowledge": ks,
            "items": [{"title": it.get("title"), "url": it.get("url"),
                       "source_type": it.get("source_type")} for it in items]}


_KNOW_OFFICIAL = (
    "deepseek.com", "api-docs.deepseek.com", "huggingface.co", "arxiv.org",
    "semanticscholar.org", "openreview.net", "aclanthology.org",
    "neurips.cc", "icml.cc", "openai.com", "microsoft.com", "nvidia.com",
    "googleblog.com", "github.com",
)
_KNOW_LOW = ("pypi.org", "npmjs.com", "medium.com", "reddit.com",
             "twitter.com", "x.com", "youtube.com", "facebook.com")
_KNOW_KEYWORDS = (
    "rag", "retrieval", "embedding", "agent", "multi-agent", "memory",
    "event", "scheduling", "self-evolution", "lora", "fine-tune", "llm",
    "deepseek", "harness", "dgtf", "eml", "knowledge", "reasoning",
)


def _knowledge_quality(it, qs):
    """权威/时效/置信/相关/可抓取 五维质量分；返回 (score, reasons)。"""
    title = str(it.get("title") or "")
    claim = str(it.get("claim") or it.get("summary") or "")
    url = str(it.get("url") or "")
    blob = (title + " " + claim + " " + str(it.get("content") or "")[:1500]).lower()
    reasons = []
    score = 0.0
    domain = ""
    try:
        domain = url.split("/")[2].lower() if "://" in url else ""
    except Exception:
        domain = ""
    if ("ezproxy" in domain and "arxiv" in domain):
        score += 3.0
        reasons.append("学术镜像域名")
    elif any(domain == d or domain.endswith("." + d) for d in _KNOW_OFFICIAL):
        score += 3.0
        reasons.append("官方/权威域名")
    if any(domain == d or domain.endswith("." + d) for d in _KNOW_LOW):
        score -= 4.0
        reasons.append("低价值源降权")
    if it.get("authority"):
        try:
            score += min(3.0, float(it.get("authority")) / 20.0)
            reasons.append("authority=" + str(it.get("authority")))
        except Exception:
            pass
    if it.get("confidence"):
        try:
            score += min(3.0, float(it.get("confidence")) * 3.0)
            reasons.append("置信=" + str(it.get("confidence")))
        except Exception:
            pass
    if it.get("fetched") or it.get("fetched_at") or it.get("content"):
        score += 1.0
        reasons.append("正文可抓取")
    pub = str(it.get("published") or "")
    if "2026" in pub or "2025" in pub:
        score += 1.5
        reasons.append("近期")
    qterms = [t for t in (str(qs or "").lower().replace(",", " ").split()) if len(t) >= 2]
    rel = sum(1 for k in _KNOW_KEYWORDS if k in blob)
    rel += sum(1 for t in qterms if t[:24] in blob)
    if rel:
        score += min(3.0, rel * 0.8)
        reasons.append("相关命中=" + str(rel))
    if len(claim) >= 80:
        score += 0.5
        reasons.append("摘要充分")
    return round(score, 2), reasons


def _knowledge_dsh_session(qs, mode, chosen, candidates, error=""):
    """写一条 DSH 知识检索会话记录，供前端实时展示检索/爬取/筛选过程。"""
    import time as _t
    cid = "dshknow-" + str(int(_t.time() * 1000))
    ev = [{"type": "text",
           "text": "DSH 知识检索会话 · " + ("前沿刷新" if mode == "refresh" else "自由查询")}]
    ev.append({"type": "tool_call", "tool": "knowledge.search",
               "input": {"queries": qs, "quality": "official/authoritative/recent/relevant"}})
    ev.append({"type": "tool_result", "status": "ok",
               "result": "检索候选 %d 条，进入质量评估" % len(candidates)})
    for i, x in enumerate(candidates[:8], 1):
        ev.append({"type": "text",
                   "text": "候选 %d · score=%s · %s" % (
                       i, x.get("_qscore"), str(x.get("title") or "")[:120])})
        if x.get("_qreasons"):
            ev.append({"type": "text",
                       "text": "  质量依据：" + "；".join(x["_qreasons"])})
    ev.append({"type": "tool_call", "tool": "knowledge.select",
               "input": {"limit": len(chosen), "min_quality": "official/high-confidence"}})
    for i, x in enumerate(chosen, 1):
        ev.append({"type": "tool_result", "status": "selected",
                   "result": "[%d] %s | %s | %s" % (
                       i, x.get("title") or "", x.get("url") or "",
                       "；".join(x.get("_qreasons") or []))})
    if error:
        ev.append({"type": "text", "text": "检索失败：" + error})
    else:
        ev.append({"type": "text",
                   "text": "已入库 %d 条高质量知识；可在技术知识库查看。" % len(chosen)})
    turn = {"id": "turn-" + str(int(_t.time() * 1000)), "task": " ".join(qs)[:500],
            "status": "error" if error else "done", "events": ev,
            "text": ("检索失败：" + error) if error else
                    ("已筛选入库 %d 条。" % len(chosen)),
            "ts_start": _t.time(), "ts_end": _t.time()}
    conv = {"id": cid, "session_id": "", "created_at": _t.time(),
            "updated_at": _t.time(), "agent": "knowledge-curator",
            "turns": [turn]}
    try:
        _conv_save(conv)
    except Exception:
        pass
    return cid, conv


def _knowledge_agent_search(queries=None, mode="refresh", limit=3):
    """统一知识检索：权威/时效/相关筛选 + 写 DSH 会话 + 入库。"""
    import sys as _sys
    import time as _kt
    qs = [str(q).strip() for q in (queries or []) if str(q).strip()]
    if mode == "refresh" and not qs:
        qs = ["DeepSeek 官方 最新发布 技术博客 模型 2026",
              "LLM agent RAG event memory scheduling 2026 official",
              "multi-agent self-evolution arxiv 2026"]
    if not qs:
        return {"ok": False, "error": "查询为空"}
    limit = max(1, min(6, int(limit or 3)))
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    # 从 .env 读检索 key（服务进程环境不一定带）
    try:
        for _ln in (Path(__file__).resolve().parent.parent / ".env").read_text(
                encoding="utf-8", errors="replace").splitlines():
            if _ln.startswith("DGTF_API_KEY="):
                os.environ.setdefault("DGTF_API_KEY",
                                      _ln.split("=", 1)[1].strip().strip('"').strip("'"))
            if _ln.startswith("TAVILY_API_KEY="):
                os.environ.setdefault("TAVILY_API_KEY",
                                      _ln.split("=", 1)[1].strip().strip('"').strip("'"))
    except Exception:
        pass
    from dgtf_v2.agent_bridge import refresh_knowledge_http, dedupe_knowledge
    try:
        res = refresh_knowledge_http(qs[:4], return_stats=True,
                                     limit=max(4, limit * 2))
    except Exception as exc:
        res = {"items": [], "error": str(exc)}
    candidates = list(res.get("items") or [])
    if not candidates:
        try:
            candidates = _arxiv_refresh(qs[:2], limit=limit * 2)
        except Exception:
            candidates = []
    if not candidates:
        # 检索为空/全是重复：从本地知识库按查询命中，避免“重复即空结果”
        try:
            from dgtf_v2.agent_bridge import read_knowledge
            rows = read_knowledge(limit=300)
            qblob = " ".join(qs).lower()
            terms = [t for t in qblob.replace(",", " ").split() if len(t) >= 2]
            for it in rows:
                blob = (str(it.get("title") or "") + " "
                        + str(it.get("claim") or it.get("summary") or "")).lower()
                _hit = any(t[:24] in blob for t in terms)
                if mode == "refresh":
                    _hit = _hit or any(k in blob for k in _KNOW_KEYWORDS)
                if _hit:
                    candidates.append(dict(it))
            candidates = candidates[:max(4, limit * 2)]
        except Exception:
            pass
    scored = []
    for it in candidates:
        try:
            sc, rs = _knowledge_quality(it, " ".join(qs))
        except Exception:
            sc, rs = 0.0, []
        x = dict(it)
        x["_qscore"] = sc
        x["_qreasons"] = rs
        scored.append(x)
    scored.sort(key=lambda x: x.get("_qscore", 0), reverse=True)
    _good = [x for x in scored
             if x.get("_qscore", 0) >= 5.0
             and not any("低价值源" in r for r in (x.get("_qreasons") or []))]
    chosen = _good[:limit]
    if not chosen and scored:
        # 没有达标源：取非低价值最高分并明确标注“兜底”
        _fallback = [x for x in scored
                     if not any("低价值源" in r for r in (x.get("_qreasons") or []))]
        if not _fallback:
            _fallback = scored
        chosen = _fallback[:min(limit, len(_fallback))]
        for _x in chosen:
            _x.setdefault("_qreasons", []).append("兜底（未达高质量阈值）")
    # 去重并写补丁说明
    try:
        dedupe_knowledge()
    except Exception:
        pass
    patch_path = ""
    try:
        pdir = Path(__file__).resolve().parent.parent / "dgtf_memory"
        pdir.mkdir(parents=True, exist_ok=True)
        pp = pdir / "agent_knowledge_patch.md"
        with pp.open("a", encoding="utf-8") as pf:
            pf.write("\n## DSH 知识检索 " + _kt.strftime("%Y-%m-%d %H:%M:%S")
                     + " · " + str(mode) + "\n")
            for it in chosen:
                pf.write("- [" + str(it.get("title") or "") + "]("
                         + str(it.get("url") or "") + ") — "
                         + str(it.get("claim") or "")[:200] + "\n")
                if it.get("_qreasons"):
                    pf.write("  - 质量：" + "；".join(it["_qreasons"]) + "\n")
        patch_path = str(pp)
    except Exception:
        pass
    cid, conv = _knowledge_dsh_session(qs, mode, chosen, scored,
                                       error=str(res.get("error") or ""))
    return {"ok": bool(chosen), "conversation_id": cid,
            "queries": qs, "mode": mode,
            "count": len(chosen), "items": [
                {k: v for k, v in it.items() if not k.startswith("_")}
                | {"quality_score": it.get("_qscore"),
                   "quality_reasons": it.get("_qreasons")}
                for it in chosen],
            "candidates": len(scored), "patch": patch_path,
            "conversation": conv,
            "note": "DSH 知识检索会话；检索/爬取/筛选过程在会话中可追溯"}


def _auto_engine_run(emit=None, question="", mock=True, opts=None, timeout=300):
    """全流程中的引擎跑次：默认 mock；显式 mock=False 才真跑。"""
    import time as _t
    # 复用模块级 runner：若再 from dgtf_app import engine_runner，
    # 会把同一文件加载成第二个模块，_tasks 等运行态与 API 侧不共享。
    q = str(question or "").strip() or "元DGTF 全流程自检：如何让 EML 反馈驱动调度细度？"
    o = dict(opts or {})
    o["mock"] = bool(mock)
    if emit:
        emit({"type": "text", "text": ("开始" + (" mock " if mock else " 真实 ")
                                      + "引擎跑次：" + q[:120])})
    tid = runner.start_task(q, o)
    last = {}
    for _ in range(max(1, int(timeout) // 2)):
        _t.sleep(2)
        last = runner.get_task(tid) or {}
        st = str(last.get("status") or "")
        if st in ("done", "error", "cancelled", "interrupted"):
            break
        if emit and int(_t.time()) % 30 < 2:
            emit({"type": "text", "text": "引擎跑次进行中：" + st})
    st = str(last.get("status") or "")
    ok = st == "done"
    if emit:
        emit({"type": "text", "text": "引擎跑次结束：" + st})
    return {"ok": ok, "task_id": tid, "status": st,
            "mock": bool(mock), "question": q,
            "output_name": last.get("output_name"),
            "error": last.get("error")}


def _auto_cycle_full(emit=None, model="", data=None):
    """全流程闭环：知识刷新 → 引擎跑次 → 消费者/任务 → 自审提案。"""
    data = data or {}
    out = {"ok": True}
    out["knowledge"] = _auto_refresh_knowledge(emit=emit,
                                               queries=data.get("queries"))
    out["engine"] = _auto_engine_run(
        emit=emit, question=str(data.get("question") or ""),
        mock=bool(data.get("mock", True)), opts=data.get("opts"),
        timeout=int(data.get("timeout") or 300))
    out.update(_auto_cycle_all(emit=emit, model=model))
    out["ok"] = bool(out.get("engine", {}).get("ok")) and bool(out.get("ok"))
    return out


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
    res = {}
    if todo:
        compact = [{"task_id": str(t.get("id") or ""),
                    "title": str(t.get("title") or "")[:160],
                    "detail": str(t.get("detail") or "")[:400]}
                   for t in todo[:80]]
        prompt = ("提案模式：允许读取项目文件核对现状，但不要修改源码。请为下列全部任务分别给出"
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
    _blocked = ("[安全拦截]" in audit_text) or ("security_blocked" in str(res))
    for t in todo:
        tid = str(t.get("id") or "")
        plan = plans.get(tid) or ("DSH 批量自审：待针对该任务补充具体方案。"
                                  + (("\n" + audit_text[:800]) if audit_text else ""))
        prop = _save_proposal({"id": "prop-" + str(int(_tm.time() * 1000)) + "-" + tid[:6],
                               "ts": _tm.time(), "task": t, "task_id": tid,
                               "plan": plan,
                               "status": ("expired" if _blocked else "pending"),
                               "expired_reason": ("security_blocked_tool_access" if _blocked else ""),
                               "approver": "", "session_id": "", "batch": True})
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


def _conv_set_proc(cid, proc):
    with _conv_lock():
        if proc is None:
            _DSH_CONV_PROCS.pop(cid, None)
        else:
            _DSH_CONV_PROCS[cid] = proc


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
            res = _run_dsh_agent_raw(
                task, sid, timeout=1800,
                effort=str(settings.get("effort") or ""),
                permission=str(settings.get("permission") or ""),
                model=str(settings.get("model") or ""),
                emit=lambda ev: _conv_event(cid, turn.get("id"), ev),
                proc_ref=lambda p: _conv_set_proc(cid, p))
        except Exception as exc:
            res = {"ok": False, "session_id": sid, "events": [],
                   "text": "", "stderr": str(exc)}
        with _conv_lock():
            conv = _DSH_CONV.get(cid) or _conv_load(cid)
            if not conv:
                _DSH_CONV_ACTIVE.discard(cid)
                return
            _was_cancelled = cid in _DSH_CONV_CANCELLED
            for x in conv.get("turns") or []:
                if x.get("id") == turn.get("id"):
                    x["status"] = ("canceled" if _was_cancelled else
                                    ("done" if res.get("ok") else "error"))
                    x["events"] = list(res.get("events") or x.get("events") or [])
                    x["text"] = str(res.get("text") or "")
                    x["ts_end"] = _t.time()
                    break
            if res.get("session_id"):
                conv["session_id"] = str(res["session_id"])
            if _was_cancelled:
                _DSH_CONV_CANCELLED.discard(cid)
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


def _conv_reconcile_on_start():
    """服务重启后，磁盘里遗留的 queued/running 已经没有 worker，统一标记 interrupted。"""
    import json as _json
    try:
        for p in _conv_dir().glob("*.json"):
            try:
                c = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            changed = False
            for t in c.get("turns") or []:
                if str(t.get("status")) in ("queued", "running"):
                    t["status"] = "interrupted"
                    changed = True
            if changed:
                c["updated_at"] = __import__("time").time()
                p.write_text(_json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _conv_list(limit=50):
    import json as _json
    rows = []
    try:
        files = sorted(_conv_dir().glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, int(limit))]
        for p in files:
            try:
                c = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            turns = c.get("turns") or []
            _busy = any(str(t.get("status")) in ("queued", "running") for t in turns)
            _active = (c.get("id") or p.stem) in _DSH_CONV_ACTIVE
            running = bool(_busy and _active)
            stale = bool(_busy and not _active)
            last = turns[-1] if turns else {}
            rows.append({"id": c.get("id") or p.stem,
                         "session_id": c.get("session_id") or "",
                         "created_at": c.get("created_at"),
                         "updated_at": c.get("updated_at"),
                         "turns": len(turns),
                         "running": running, "stale": stale,
                         "last_status": last.get("status") or "",
                         "last_task": str(last.get("task") or "")[:200]})
    except Exception:
        pass
    return rows


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
        if stage == "knowledge":
            out["knowledge"] = _auto_refresh_knowledge(
                emit=_stage("knowledge"),
                queries=(data or {}).get("queries"))
            out["ok"] = bool((out["knowledge"] or {}).get("ok"))
        if stage == "full":
            out.update(_auto_cycle_full(emit=_stage("full"), model=model,
                                        data=data))
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
    # ★ 自动修复前先做风险分流：
    #   拿得准的 pending 自动确认；高风险/弱计划保留 pending 等人工。
    manual = []
    for p in _list_proposals(300):
        if str(p.get("status")) != "pending":
            continue
        auto, reason = _autopilot_decision(p)
        tri = p.get("triage") or {}
        tri["auto_decision"] = "auto" if auto else "manual"
        tri["auto_reason"] = reason
        p["triage"] = tri
        if auto:
            p["status"] = "confirmed"
            p["approver"] = "autopilot"
            p["approved_ts"] = _t.time()
        else:
            manual.append({"id": p.get("id"), "reason": reason,
                           "title": (p.get("task") or {}).get("title")})
        _save_proposal(p)
    confs = [x for x in _list_proposals(300) if x.get("status") == "confirmed"]
    done = []
    for prop in confs:
        pid = str(prop.get("id") or "")
        write({"type": "stage", "stage": "proposal:" + pid})

        def _emit_fix(ev, _pid=pid):
            write({"type": "event", "stage": "proposal:" + _pid, "event": ev})

        learn = ""
        if _autopilot_cfg_load().get("enabled", True):
            try:
                learn = _autopilot_knowledge(prop)
            except Exception:
                learn = ""
        try:
            res = _repair_with_acceptance(
                prop, model=str((data or {}).get("model") or ""),
                emit=_emit_fix, max_attempts=3, extra_context=learn,
                permission=str((data or {}).get("permission") or ""))
        except Exception as exc:
            res = {"ok": False, "gate": {}, "acceptance": {},
                   "repair": {"committed": False, "why": str(exc)},
                   "attempts": [], "conversation_ids": [], "conversation_id": ""}
        repair = res.get("repair") or {}
        acc = res.get("acceptance") or {}
        prop["approver"] = "dsh_auto"
        prop["approved_ts"] = _t.time()
        prop["conversation_id"] = str(res.get("conversation_id") or "")
        prop["conversation_ids"] = list(res.get("conversation_ids") or [])
        prop["attempts"] = list(res.get("attempts") or [])
        prop["acceptance"] = acc
        prop["security"] = res.get("security") or {}
        prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                          "acceptance": acc, "security": prop["security"],
                          "repair": repair,
                          "conversation_id": prop["conversation_id"],
                          "conversations": prop["conversation_ids"],
                          "autopilot": bool((data or {}).get("autopilot"))}
        write({"type": "stage", "stage": "acceptance:" + pid})
        write({"type": "event", "stage": "acceptance:" + pid,
               "event": {"type": "text",
                         "text": "针对性验收：" + ("PASS" if acc.get("ok") else "FAIL")}})
        if repair.get("committed") and res.get("ok"):
            version = _next_repair_version()
            prop["version"] = version
            prop["status"] = "applied"
            prop["artifact"] = _save_repair_artifact(prop, acc, version)
        else:
            prop["status"] = "failed"
        _save_proposal(prop)
        done.append(prop)
        write({"type": "proposal_result", "proposal": prop})
    ok = all((x.get("status") == "applied") for x in done) if done else False
    write({"type": "result", "result": {"ok": ok, "proposals": done,
                                        "count": len(done),
                                        "manual_pending": manual}})


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


def _v2_event_ts(x, fallback=None):
    """V2 事件只有运行内相对秒（event_time/ingest_time），
    用 run_id 的 `YYYYMMDD_HHMMSS` 还原批次绝对时间；失败回退文件 mtime。"""
    import datetime as _dt
    rid = str((x or {}).get("run_id") or "")
    m = re.match(r"^(\d{8})_(\d{6})", rid)
    if m:
        try:
            return _dt.datetime.strptime(
                m.group(1) + m.group(2), "%Y%m%d%H%M%S").timestamp()
        except Exception:
            pass
    return fallback


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
    try:
        _fallback_ts = p.stat().st_mtime
    except OSError:
        _fallback_ts = None
    recent = []
    for x in rows[-5:]:
        y = dict(x)
        if not y.get("ts"):
            y["ts"] = _v2_event_ts(y, _fallback_ts)
        recent.append(y)
    tmpl = {}
    for x in rows:
        if str(x.get("kind") or "") != "schedule_outcome":
            continue
        pl = x.get("payload") if isinstance(x.get("payload"), dict) else {}
        t = str(pl.get("template") or "")
        if not t:
            continue
        d = tmpl.setdefault(t, {"n": 0, "quality": 0.0, "tokens": 0.0, "calls": 0.0,
                                "vals": []})
        try:
            q = float(pl.get("quality") or 0)
            d["quality"] += q
            d["tokens"] += float(pl.get("tokens") or 0)
            d["calls"] += float(pl.get("calls") or 0)
            d["vals"].append(q)
            d["n"] += 1
        except Exception:
            pass
    by_template = {}
    for t, d in tmpl.items():
        n = int(d["n"] or 0)
        mean = (d["quality"] / n) if n else 0.0
        vals = d.get("vals") or []
        sd = 0.0
        if len(vals) >= 2:
            mu = sum(vals) / len(vals)
            sd = (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
        ci = (1.96 * sd / (n ** 0.5)) if n > 1 else 0.0
        by_template[t] = {"n": n, "quality": round(mean, 3),
                          "sd": round(sd, 4), "ci95": round(ci, 4),
                          "low": round(mean - ci, 4),
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
        "app": {"name": "元DGTF app", "version": APP_VERSION,
                "commit": _git(["rev-parse", "HEAD"]).get("out", "")[:12]},
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


def _v2_ab(left="", right=""):
    import math as _math
    s = _v2_shadow_status(500)
    bt = s.get("by_template") or {}
    keys = sorted(bt, key=lambda k: (bt[k].get("n", 0), bt[k].get("quality", 0)),
                  reverse=True)
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left or left not in bt:
        left = keys[0] if keys else ""
    if not right or right not in bt:
        right = next((k for k in keys if k != left), "")
    if not left or not right:
        return {"ok": False, "error": "模板样本不足", "templates": list(bt)}
    a, b = bt[left], bt[right]
    se = ((a.get("sd", 0) ** 2 / max(1, a.get("n", 1)))
          + (b.get("sd", 0) ** 2 / max(1, b.get("n", 1)))) ** 0.5
    diff = float(a.get("quality", 0)) - float(b.get("quality", 0))
    t = (diff / se) if se > 0 else 0.0
    p = _math.erfc(abs(t) / (2 ** 0.5)) if se > 0 else 1.0
    return {"ok": True, "left": left, "right": right,
            "left_stats": a, "right_stats": b,
            "diff_quality": round(diff, 4),
            "se": round(se, 5), "t": round(t, 3), "p_approx": round(p, 4),
            "winner": (left if diff > 0 else right if diff < 0 else "tie"),
            "note": "Welch近似；p 用正态近似，样本小时仅作参考"}


def _v2_all_pairs(alpha=0.05):
    """多模板两两 Welch 对比 + Benjamini-Hochberg FDR 校正。"""
    import math as _math
    s = _v2_shadow_status(500)
    bt = s.get("by_template") or {}
    keys = [k for k in bt if int((bt[k] or {}).get("n") or 0) >= 2]
    rows = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = bt[keys[i]], bt[keys[j]]
            se = ((a.get("sd", 0) ** 2 / max(1, a.get("n", 1)))
                  + (b.get("sd", 0) ** 2 / max(1, b.get("n", 1)))) ** 0.5
            diff = float(a.get("quality", 0)) - float(b.get("quality", 0))
            t = (diff / se) if se > 0 else 0.0
            p = _math.erfc(abs(t) / (2 ** 0.5)) if se > 0 else 1.0
            rows.append({"left": keys[i], "right": keys[j], "diff": round(diff, 4),
                         "se": round(se, 5), "t": round(t, 3), "p": round(p, 5)})
    rows.sort(key=lambda x: x["p"])
    m = len(rows)
    for idx, r in enumerate(rows, 1):
        r["rank"] = idx
        r["q"] = round(min(1.0, r["p"] * m / idx), 5)
    for idx in range(m - 2, -1, -1):
        rows[idx]["q"] = round(min(rows[idx]["q"], rows[idx + 1]["q"]), 5)
    sig = [r for r in rows if r["q"] < float(alpha)]
    return {"ok": True, "alpha": float(alpha), "templates": keys,
            "pairs": rows, "significant": sig,
            "n_significant": len(sig),
            "method": "Welch t + Benjamini-Hochberg FDR（正态近似）"}


def _v2_best_template(min_n=5):
    """按 quality 的 95% 下界选最佳模板（比单看均值保守）。"""
    s = _v2_shadow_status(500)
    bt = s.get("by_template") or {}
    cands = [{"template": k, **v} for k, v in bt.items()
             if int(v.get("n") or 0) >= int(min_n)]
    if not cands:
        return {}
    cands.sort(key=lambda x: (x.get("low", 0), x.get("quality", 0)), reverse=True)
    return cands[0]


def _v2_apply_best(min_n=5):
    import json as _json
    import time as _t
    best = _v2_best_template(min_n=min_n)
    if not best:
        return {"ok": False, "error": "没有足够样本的 V2 模板"}
    _pair = _v2_paired_ab()
    _ident = bool(_pair.get("identifiable"))
    _warn = ("" if _ident else
             "V2 shadow 同一 run 内各模板 quality 相同，模板胜者不可识别；当前策略仅作影子参考")
    tmpl = str(best.get("template") or "")
    route = tmpl.split(":", 1)[0] if ":" in tmpl else "auto"
    rounds = ""
    if ":r" in tmpl:
        rounds = tmpl.rsplit(":r", 1)[1]
    pol = _schedule_policy_load()
    pol.update({"template": tmpl, "route": route, "rounds": rounds,
                "template_quality": best.get("quality"),
                "template_ci95": best.get("ci95"),
                "template_n": best.get("n"),
                "template_applied_at": _t.time(),
                "template_identifiable": _ident,
                "template_warning": _warn})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "best": best, "policy": pol, "warning": _warn,
                "identifiable": _ident, "paired": _pair,
                "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _v2_paired_ab(left="", right=""):
    """同 run 配对 Welch/配对 t：消除题目难度差异。"""
    import json as _json
    import math as _math
    from collections import defaultdict
    p = Path(__file__).resolve().parent.parent / "dgtf_memory" / "v2_events.jsonl"
    per = defaultdict(dict)
    if p.exists():
        try:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
                try:
                    d = _json.loads(ln)
                except Exception:
                    continue
                if not isinstance(d, dict) or str(d.get("kind") or "") != "schedule_outcome":
                    continue
                pl = d.get("payload") if isinstance(d.get("payload"), dict) else {}
                t = str(pl.get("template") or "")
                rid = str(d.get("run_id") or "")
                if not t or not rid:
                    continue
                try:
                    per[rid][t] = float(pl.get("quality") or 0)
                except Exception:
                    pass
        except Exception:
            pass
    all_t = sorted({t for m in per.values() for t in m})
    # 自动选「共同出现次数最多」的一对，避免选到没有交集的模板。
    if (not left or left not in all_t or not right or right not in all_t or left == right):
        best_pair, best_n = ("", ""), -1
        for i in range(len(all_t)):
            for j in range(i + 1, len(all_t)):
                a, b = all_t[i], all_t[j]
                nn = sum(1 for m in per.values() if a in m and b in m)
                if nn > best_n:
                    best_pair, best_n = (a, b), nn
        left, right = best_pair
    if not left or not right:
        return {"ok": False, "error": "配对样本不足", "templates": all_t}
    diffs = [m[left] - m[right] for m in per.values()
             if left in m and right in m]
    n = len(diffs)
    if n < 2:
        return {"ok": False, "error": "配对样本不足", "left": left,
                "right": right, "n": n}
    _nz = sum(1 for x in diffs if abs(x) > 1e-9)
    _ident = _nz >= max(2, int(n * 0.2))
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    se = sd / (n ** 0.5)
    t = (mu / se) if se > 0 else 0.0
    # 双侧 p：正态近似（小样本仅参考）
    pv = _math.erfc(abs(t) / (2 ** 0.5)) if se > 0 else 1.0
    return {"ok": True, "paired": True, "left": left, "right": right,
            "n_pairs": n, "nonzero_pairs": _nz,
            "nonzero_ratio": round(_nz / n, 3),
            "identifiable": bool(_ident),
            "diff_mean": round(mu, 4),
            "sd_diff": round(sd, 4), "se": round(se, 5),
            "t": round(t, 3), "p_approx": round(pv, 4),
            "winner": left if mu > 0 else right if mu < 0 else "tie",
            "note": ("同一 run_id 的多模板配对；"
                     + ("模板差异可识别" if _ident else
                        "同一 run 内各模板 quality 相同，模板胜者不可识别（影子读数未独立区分模板）"))}


_CONSISTENCY_HISTORY = Path(__file__).resolve().parent.parent / "dgtf_memory" / "consistency_history.jsonl"


def _consistency_history(n=10):
    import json as _json
    rows = []
    try:
        if _CONSISTENCY_HISTORY.exists():
            for ln in _CONSISTENCY_HISTORY.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(n)):]:
                try:
                    d = _json.loads(ln)
                    if isinstance(d, dict):
                        rows.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return rows


def _consistency_history_save(result):
    import json as _json
    import time as _t
    try:
        chk = result.get("checks") or {}
        row = {"ts": _t.time(), "ok": bool(result.get("ok")),
               "warnings": result.get("warnings") or [],
               "engine": (chk.get("engine") or {}).get("version"),
               "playbook": (chk.get("eml_memory") or {}).get("playbook"),
               "v2": (chk.get("eml_memory") or {}).get("v2"),
               "paired": (chk.get("v2_paired") or {}).get("identifiable"),
               "profile": (chk.get("schedule_policy") or {}).get("profile"),
               "template": (chk.get("schedule_policy") or {}).get("template"),
               "jobs": (chk.get("job_persistence") or {}).get("jobs")}
        _CONSISTENCY_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with _CONSISTENCY_HISTORY.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


_EML_DATASET = Path(__file__).resolve().parent.parent / "dgtf_memory" / "eml_training_dataset.jsonl"


def _eml_dataset_meta():
    import json as _json
    rows = []
    try:
        if _EML_DATASET.exists():
            for ln in _EML_DATASET.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    d = _json.loads(ln)
                    if isinstance(d, dict):
                        rows.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    tmpl = {}
    for r in rows:
        t = str(r.get("template") or "")
        tmpl[t] = tmpl.get(t, 0) + 1
    return {"ok": True, "path": str(_EML_DATASET), "n": len(rows),
            "templates": tmpl,
            "mtime": _EML_DATASET.stat().st_mtime if _EML_DATASET.exists() else 0,
            "fields": ["run_id", "template", "quality", "calls", "tokens", "success"]}


def _eml_export_dataset(limit=5000):
    """从 V2 schedule_outcome 导出纯数值训练集；不含答案正文。"""
    import json as _json
    import time as _t
    root = Path(__file__).resolve().parent.parent
    p = root / "dgtf_memory" / "v2_events.jsonl"
    latest = {}
    if p.exists():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)):]:
            try:
                d = _json.loads(ln)
            except Exception:
                continue
            if not isinstance(d, dict) or str(d.get("kind") or "") != "schedule_outcome":
                continue
            pl = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            t = str(pl.get("template") or "")
            rid = str(d.get("run_id") or "")
            if not t or not rid:
                continue
            try:
                row = {"run_id": rid, "template": t,
                       "quality": float(pl.get("quality") or 0),
                       "calls": float(pl.get("calls") or 0),
                       "tokens": float(pl.get("tokens") or 0),
                       "success": bool(pl.get("success"))}
            except Exception:
                continue
            latest[(rid, t)] = row
    rows = [latest[k] for k in sorted(latest)]
    try:
        _EML_DATASET.parent.mkdir(parents=True, exist_ok=True)
        tmp = _EML_DATASET.with_suffix(".tmp")
        tmp.write_text("".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                       encoding="utf-8")
        tmp.replace(_EML_DATASET)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "n": len(rows), "path": str(_EML_DATASET),
            "templates": len({r["template"] for r in rows}),
            "runs": len({r["run_id"] for r in rows}),
            "note": "纯数值训练集；不含答案正文", "at": _t.time()}


def _self_consistency():
    """元DGTF 自洽审计：把引擎/EML/V2/策略/持久化/映射集中校验。"""
    import json as _json
    import sys as _sys
    root = Path(__file__).resolve().parent.parent
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    checks = {}
    eng = runner.find_engine()
    _ver = ""
    try:
        import re as _re
        _m = _re.search(r'__version__\s*=\s*["\']([^"\']+)',
                        eng.read_text(encoding="utf-8", errors="replace")[:4000])
        _ver = _m.group(1) if _m else ""
    except Exception:
        _ver = ""
    checks["engine"] = {"ok": eng.is_file(), "name": eng.name, "version": _ver}
    mods = {}
    for name in ("self_feedback", "llm_feedback", "unified_memory",
                 "scheduler", "orchestrator", "fact_flow", "evidence",
                 "structural_diversity"):
        try:
            __import__("dgtf_v2." + name)
            mods[name] = True
        except Exception:
            mods[name] = False
    checks["eml_modules"] = {"ok": all(mods.values()), "modules": mods}
    try:
        eml = _eml_status()
        checks["eml_memory"] = {"ok": (eml.get("playbook") or {}).get("n", 0) > 0,
                                "playbook": (eml.get("playbook") or {}).get("n"),
                                "v2": (eml.get("v2_shadow") or {}).get("n"),
                                "tasks": (eml.get("agent") or {}).get("tasks"),
                                "results": (eml.get("agent") or {}).get("results")}
    except Exception as exc:
        checks["eml_memory"] = {"ok": False, "error": str(exc)}
    try:
        pair = _v2_paired_ab()
        checks["v2_paired"] = {"ok": bool(pair.get("ok")),
                               "identifiable": bool(pair.get("identifiable")),
                               "n_pairs": pair.get("n_pairs"),
                               "warning": "" if pair.get("identifiable") else pair.get("note", "")}
    except Exception as exc:
        checks["v2_paired"] = {"ok": False, "error": str(exc)}
    try:
        pol = _schedule_policy_load()
        prof = str(pol.get("profile") or "")
        pp = root / "configs" / prof if prof else None
        checks["schedule_policy"] = {"ok": bool(prof) and bool(pp and pp.is_file()),
                                     "profile": prof,
                                     "template": pol.get("pareto_template") or pol.get("template"),
                                     "route": pol.get("route"), "rounds": pol.get("rounds")}
    except Exception as exc:
        checks["schedule_policy"] = {"ok": False, "error": str(exc)}
    try:
        jf = root / "dgtf_memory" / "auto_jobs.json"
        jd = _json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
        checks["job_persistence"] = {"ok": jf.exists(), "jobs": len(jd),
                                     "path": str(jf)}
    except Exception as exc:
        checks["job_persistence"] = {"ok": False, "error": str(exc)}
    checks["layer_mapping"] = {"ok": True, "engine_layers": ["0", "1", "both", "all"],
                               "app_layers": ["0", "1", "both", "all"],
                               "canonical_ids": ["0", "1", "both", "all"]}
    try:
        _lm = _llm_status()
        checks["llm_lora"] = {"ok": bool(_lm.get("ok")),
                              "adapter": _lm.get("adapter"),
                              "eval": _lm.get("eval_summary"),
                              "note": _lm.get("note")}
    except Exception as exc:
        checks["llm_lora"] = {"ok": False, "error": str(exc)}
    try:
        _tr = _context_trace_list(20)
        checks["context_trace"] = {"ok": _CONTEXT_TRACE_FILE.exists(),
                                   "traces": len(_tr),
                                   "path": str(_CONTEXT_TRACE_FILE),
                                   "latest": _tr[-1] if _tr else None}
    except Exception as exc:
        checks["context_trace"] = {"ok": False, "error": str(exc)}
    checks["rag_policy"] = {"ok": True,
                            "external_allowed": _context_external_allowed(),
                            "retrieval": "keyword+bm25_rerank",
                            "citations": True, "layer_contexts": True,
                            "redaction": True}
    try:
        _m = _sched_model_load()
        checks["scheduler_model"] = {"ok": bool(_m),
                                     "rows": _m.get("rows"),
                                     "quality_test": _m.get("quality_test"),
                                     "path": str(_SCHED_MODEL_FILE)}
    except Exception as exc:
        checks["scheduler_model"] = {"ok": False, "error": str(exc)}
    crit = ["engine", "eml_modules", "eml_memory", "layer_mapping"]
    ok = all(bool(checks[k].get("ok")) for k in crit)
    warns = [k for k, v in checks.items() if not v.get("ok")]
    out = {"ok": ok, "checks": checks, "warnings": warns,
           "ts": time.time(),
           "note": "critical=engine/eml_modules/eml_memory/layer_mapping；其余为诊断项"}
    _consistency_history_save(out)
    out["history"] = _consistency_history(10)
    return out


def _v2_replay_packed(limit=30):
    """用真实 packed 重新回放 V2，写入按层 quality 的 schedule_outcome。"""
    import sys as _sys
    root = Path(__file__).resolve().parent.parent
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    try:
        from dgtf_v2 import replay as _rp
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    paths = [str(p) for p in sorted(oi.OUTPUTS_DIR.glob("*.packed.json"),
                                    key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, int(limit))]]
    if not paths:
        return {"ok": False, "error": "没有 packed 产物"}
    target = root / "dgtf_memory" / "v2_events.jsonl"
    import shutil as _sh
    import time as _t
    bak = ""
    try:
        if target.exists():
            bak = str(target) + ".bak-replay-" + str(int(_t.time()))
            _sh.copy2(target, bak)
        res = _rp.replay(paths, limit=max(1, int(limit)), memory_path=target)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "backup": bak}
    return {"ok": True, "limit": limit, "backup": bak,
            "runs": res.get("runs"), "quality_mean": res.get("quality_mean"),
            "memory": res.get("memory"), "paired": _v2_paired_ab()}


def _v2_template_pareto(prefer="balanced", limit=2000):
    """V2 模板级质量-成本联合帕累托：quality 越高越好，tokens 越低越好。"""
    s = _v2_shadow_status(limit=limit)
    bt = s.get("by_template") or {}
    pts = []
    for k, v in bt.items():
        n = int(v.get("n") or 0)
        if n <= 0:
            continue
        pts.append({"template": k, "n": n,
                    "quality": float(v.get("quality") or 0),
                    "low": float(v.get("low") or 0),
                    "tokens": float(v.get("tokens") or 0),
                    "calls": float(v.get("calls") or 0),
                    "ci95": float(v.get("ci95") or 0)})
    if not pts:
        return {"ok": True, "points": [], "frontier": [], "recommended": None,
                "note": "暂无 V2 模板样本"}
    # 非支配：quality 更高且 tokens 更低（用 low 做保守质量）。
    front = []
    for p in sorted(pts, key=lambda x: (x["tokens"], -x["low"])):
        if not any((q["tokens"] <= p["tokens"] and q["low"] >= p["low"]
                    and (q["tokens"] < p["tokens"] or q["low"] > p["low"]))
                   for q in pts):
            front.append(p)
    max_q = max(p["low"] for p in pts) or 1.0
    max_t = max(p["tokens"] for p in pts) or 1.0
    def _score(p):
        qn = p["low"] / max_q
        cn = p["tokens"] / max_t
        if prefer == "cost":
            return -cn + 0.15 * qn
        if prefer == "quality":
            return qn - 0.15 * cn
        return qn - 0.35 * cn
    rec = max(pts, key=_score)
    return {"ok": True, "points": pts, "frontier": front,
            "recommended": rec, "prefer": prefer,
            "metric_note": "quality 下界 vs tokens；真实 V2 模板聚合",
            "n": len(pts)}


def _v2_apply_pareto(prefer="balanced", limit=2000):
    import json as _json
    import time as _t
    pr = _v2_template_pareto(prefer=prefer, limit=limit)
    rec = pr.get("recommended") or {}
    tmpl = str(rec.get("template") or "")
    if not tmpl:
        return {"ok": False, "error": "没有可用的 V2 模板"}
    route = tmpl.split(":", 1)[0] if ":" in tmpl else "auto"
    rounds = tmpl.rsplit(":r", 1)[1] if ":r" in tmpl else ""
    pol = _schedule_policy_load()
    pol.update({"pareto_template": tmpl, "route": route, "rounds": rounds,
                "template": tmpl,
                "pareto_quality": rec.get("quality"),
                "pareto_low": rec.get("low"),
                "pareto_tokens": rec.get("tokens"),
                "pareto_applied_at": _t.time(), "pareto_prefer": prefer})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "recommended": rec, "policy": pol,
                "frontier_n": len(pr.get("frontier") or []),
                "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _v2_bandit(prefer="balanced", c=0.5, limit=5000):
    """V2 模板 UCB 选择：均值 + 探索奖励 - 成本惩罚。"""
    import math as _math
    s = _v2_shadow_status(limit=limit)
    bt = s.get("by_template") or {}
    arms = []
    max_t = max([float(v.get("tokens") or 0) for v in bt.values()] or [1.0]) or 1.0
    lam = {"cost": 0.50, "quality": 0.05}.get(str(prefer), 0.20)
    for k, v in bt.items():
        n = int(v.get("n") or 0)
        if n <= 0:
            continue
        q = float(v.get("quality") or 0)
        sd = float(v.get("sd") or 0)
        var = (sd * sd) if sd > 0 else max(0.0, q * (1.0 - q))
        bonus = float(c) * _math.sqrt(var / max(1, n)) if n > 0 else float(c)
        ucb = q + bonus
        cost = float(v.get("tokens") or 0) / max_t
        score = ucb - lam * cost
        arms.append({"template": k, "n": n, "quality": round(q, 4),
                     "sd": round(sd, 4), "bonus": round(bonus, 4),
                     "ucb": round(ucb, 4), "cost_norm": round(cost, 3),
                     "score": round(score, 4),
                     "tokens": float(v.get("tokens") or 0),
                     "calls": float(v.get("calls") or 0)})
    if not arms:
        return {"ok": True, "arms": [], "chosen": None,
                "note": "暂无 V2 模板样本"}
    arms.sort(key=lambda x: x["score"], reverse=True)
    return {"ok": True, "arms": arms, "chosen": arms[0],
            "prefer": prefer, "c": c, "lambda_cost": lam,
            "method": "UCB1（均值+探索奖励）- 成本惩罚",
            "note": "从 EML/V2 记忆读数估计，不是模型权重训练"}


def _question_bucket(q):
    s = str(q or "")
    if any(k in s for k in ("比较", "对比", "区别", "优劣", " vs ", "VS", "哪个好")):
        return "compare"
    if any(k in s for k in ("为什么", "原因", "导致", "影响", "后果")):
        return "causal"
    if any(k in s for k in ("如何", "怎么", "怎样", "步骤", "方案", "实现")):
        return "howto"
    if any(k in s for k in ("应该", "是否", "要不要", "选择", "决策")):
        return "decision"
    if any(k in s for k in ("什么时候", "何时", "时间", "发布", "多少", "定义", "是什么")):
        return "fact"
    return "general"


_SCHED_MODEL_FILE = Path(__file__).resolve().parent.parent / "models" / "scheduler_model_v1.json"
_SCHED_MODEL_RUNTIME = Path(__file__).resolve().parent.parent / "dgtf_memory" / "scheduler_model.json"


_LLM_PY = os.getenv("DGTF_LLM_PYTHON", r"D:\dgtf_llm_env\Scripts\python.exe")
_LLM_MODEL = os.getenv("DGTF_LLM_MODEL", r"D:/dgtf_models/Qwen2.5-0.5B-Instruct")
_LLM_ADAPTER = Path(__file__).resolve().parent.parent / "llm_sft" / "adapter_qwen05b_v1"
_LLM_SCRIPT = Path(__file__).resolve().parent.parent / "llm_predict.py"
_LLM_BACKENDS = {
    "qwen05b": {"model": r"D:/dgtf_models/Qwen2.5-0.5B-Instruct",
                "adapter": Path(__file__).resolve().parent.parent / "llm_sft" / "adapter_qwen05b_v1",
                "label": "Qwen2.5-0.5B + LoRA"},
    "qwen15b": {"model": r"D:/dgtf_models/Qwen2.5-1.5B-Instruct",
                "adapter": Path(__file__).resolve().parent.parent / "llm_sft" / "adapter_qwen15b_v1",
                "label": "Qwen2.5-1.5B + LoRA"},
    "deepseek15b": {"model": r"D:/dgtf_models/DeepSeek-R1-Distill-Qwen-1.5B",
                    "adapter": Path(__file__).resolve().parent.parent / "llm_sft" / "adapter_deepseek15b_v1",
                    "label": "DeepSeek-R1-Distill-Qwen-1.5B + LoRA"},
}


_LLM_METRICS = Path(__file__).resolve().parent.parent / "llm_sft" / "train_metrics.json"
_LLM_EVAL = Path(__file__).resolve().parent.parent / "llm_sft" / "eval_base_vs_lora.json"


_PROJECT_DOCS = [
    "README.md",
    "docs/app_engine_mapping.md",
    "docs/full_loop.md",
    "docs/llm_lora_finetune.md",
    "docs/scheduler_model.md",
    "v1200_报告.md",
    "v1110_报告.md",
]
_PROJECT_BRIEF = (
    "元DGTF 是一个本地四层螺旋推理引擎，版本 元DGTF-V1.30.0.py / 1.30.0。"
    "四层固定为：0 修行（展开/候选/锚点）、1 研究（证据/子问题/收敛）、"
    "both 对撞（裁决/冲突/线头）、all 元（闭环/决策/停止）。"
    "EML 是事件溯源记忆与自学习反馈层，含 V1 playbook 与 V2 schedule_outcome；"
    "DSH 是本机 DeepSeek Harness headless Agent，用于自动闭环、提案与源码修复。"
    "app 通过 dgtf_app/server.py 调用引擎子进程，提供任务、分层日志、调度策略、"
    "V2/EML/自洽审计、LLM LoRA 调度建议等接口。"
    "当前边界：本地 LLM 仅做 route/rounds 调度建议；四层深度推理仍走 DeepSeek API；"
    "项目知识需要显式注入，模型参数本身不含元DGTF事实。"
)


_PROJECT_DOC_CACHE = {}
_PROJECT_SENSITIVE = ("api_key", "apikey", "secret", "password", "token=",
                      "sk-", "dgtf_api_key", "deepseek_api_key", "tavily_api_key")


def _project_doc_paras(rel):
    """按 mtime/size 缓存文档段落；敏感片段过滤。"""
    import re as _re
    root = Path(__file__).resolve().parent.parent
    p = root / rel
    try:
        st = p.stat()
    except Exception:
        return []
    key = (str(p), int(st.st_mtime_ns), int(st.st_size))
    hit = _PROJECT_DOC_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")[:60000]
    except Exception:
        return []
    paras = []
    for para in _re.split(r"\n\s*\n", txt):
        para = para.strip()
        if len(para) < 40:
            continue
        low = para.lower()
        if any(s in low for s in _PROJECT_SENSITIVE):
            continue
        paras.append(para[:1200])
    _PROJECT_DOC_CACHE.clear()
    _PROJECT_DOC_CACHE[key] = paras
    return paras


_IMPORTED_ANCHOR_FILE = Path(__file__).resolve().parent / "anchors" / "external_anchor.json"
_IMPORTED_CACHE = {}


def _imported_anchor_items():
    """读取 app 本地上传资料的分块锚点（供 RAG 注入）。"""
    import json as _json
    p = _IMPORTED_ANCHOR_FILE
    try:
        st = p.stat()
    except Exception:
        return []
    key = (int(st.st_mtime_ns), int(st.st_size))
    hit = _IMPORTED_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        d = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
        anchors = d.get("anchors") if isinstance(d, dict) else []
    except Exception:
        anchors = []
    out = []
    for it in anchors or []:
        if not isinstance(it, dict) or str(it.get("kind") or "") != "local":
            continue
        txt = str(it.get("content") or "")
        if len(txt.strip()) < 40:
            continue
        low = txt.lower()
        if any(s in low for s in _PROJECT_SENSITIVE):
            continue
        out.append({"source": str(it.get("source") or "local"),
                    "text": txt[:1200]})
    _IMPORTED_CACHE.clear()
    _IMPORTED_CACHE[key] = out
    return out


_CONTEXT_TRACE_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "context_traces.jsonl"
_CONTEXT_REDACT = [
    (r"sk-[A-Za-z0-9_\-]{12,}", "[REDACTED_KEY]"),
    (r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}", "Bearer [REDACTED]"),
    (r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*[^\s,;]{6,}", r"\1=[REDACTED]"),
    (r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]"),
]


def _redact_context(text):
    import re as _re_r
    out = str(text or "")
    n = 0
    for pat, rep in _CONTEXT_REDACT:
        out, k = _re_r.subn(pat, rep, out)
        n += k
    return out, n


def _context_external_allowed():
    return str(os.getenv("DGTF_CONTEXT_EXTERNAL", "1")).strip().lower() not in (
        "0", "false", "off", "no", "block")


def _context_trace_save(task_id, ctx, question="", extra=None):
    import json as _json
    import time as _t
    try:
        row = {"ts": _t.time(), "task_id": str(task_id or ""),
               "question": str(question or "")[:500],
               "chars": ctx.get("chars"), "max_chars": ctx.get("max_chars"),
               "sources": ctx.get("sources") or [],
               "knowledge_sources": ctx.get("knowledge_sources") or [],
               "imported_sources": ctx.get("imported_sources") or [],
               "citations": ctx.get("citations") or [],
               "redactions": ctx.get("redactions", 0),
               "external_allowed": ctx.get("external_allowed", True),
               "policy": ctx.get("policy") or ""}
        if extra:
            row.update(extra)
        _CONTEXT_TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CONTEXT_TRACE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(row, ensure_ascii=False) + "\n")
        return row
    except Exception:
        return {}


def _context_trace_list(limit=50):
    import json as _json
    rows = []
    try:
        if _CONTEXT_TRACE_FILE.exists():
            for ln in _CONTEXT_TRACE_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)):]:
                try:
                    d = _json.loads(ln)
                    if isinstance(d, dict):
                        rows.append(d)
                except Exception:
                    pass
    except Exception:
        pass
    return rows


def _rag_tokens(s):
    import re as _re_t
    return _re_t.findall(r"[a-z]{2,}|[\u4e00-\u9fff]{2,4}", str(s or "").lower())


def _bm25_rank(cands, query, text_key="text", topk=20):
    """对候选片段做 BM25 重排；cands 为 [{text:...}]。"""
    import math as _math
    docs = [_rag_tokens(c.get(text_key) or "") for c in cands]
    if not docs:
        return []
    q = _rag_tokens(query)
    if not q:
        return cands[:topk]
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / max(1, n)
    df = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    k1, b = 1.2, 0.75
    out = []
    for c, d in zip(cands, docs):
        dl = len(d)
        tf = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        sc = 0.0
        for t in q:
            if t not in tf:
                continue
            idf = _math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            sc += idf * (tf[t] * (k1 + 1)) / (
                tf[t] + k1 * (1 - b + b * dl / max(1e-9, avgdl)))
        out.append((sc, c))
    out.sort(key=lambda x: x[0], reverse=True)
    return [c for _s, c in out[:topk]]


_RAG_INDEX_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "rag_index.json"
_RAG_QUERY_SCRIPT = Path(__file__).resolve().parent.parent / "rag_query.py"
_RAG_INDEX_CACHE = {}
_EMBED_CACHE = {}


def _load_rag_index():
    import json as _json
    p = _RAG_INDEX_FILE
    try:
        st = p.stat()
    except Exception:
        return None
    key = (int(st.st_mtime_ns), int(st.st_size))
    hit = _RAG_INDEX_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        data = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = None
    _RAG_INDEX_CACHE.clear()
    _RAG_INDEX_CACHE[key] = data
    return data


def _embed_query(q):
    """调用本地 BGE 脚本生成查询向量；失败返回 None（回退 BM25）。"""
    q = str(q or "").strip()
    if not q:
        return None
    hit = _EMBED_CACHE.get(q)
    if hit is not None:
        return hit
    try:
        import urllib.request as _ur_e
        import json as _json_e
        _req = _ur_e.Request(
            "http://127.0.0.1:8771/embed",
            data=_json_e.dumps({"texts": [q]}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with _ur_e.urlopen(_req, timeout=6) as _resp:
            _d = _json_e.loads(_resp.read().decode("utf-8"))
        _v = ((_d.get("vectors") or [None])[0])
        if isinstance(_v, list) and _v:
            _EMBED_CACHE.clear()
            _EMBED_CACHE[q] = _v
            return _v
    except Exception:
        pass
    try:
        import subprocess as _sp
        if not Path(_LLM_PY).exists() or not _RAG_QUERY_SCRIPT.exists():
            return None
        env = dict(os.environ)
        env["HF_HUB_OFFLINE"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        r = _sp.run([_LLM_PY, str(_RAG_QUERY_SCRIPT)], input=q,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=40, cwd=str(Path(__file__).resolve().parent.parent),
                    env=env)
        if r.returncode != 0:
            return None
        d = __import__("json").loads((r.stdout or "").strip())
        vec = d.get("vec") if isinstance(d, dict) else None
        if not isinstance(vec, list) or not vec:
            return None
        _EMBED_CACHE.clear()
        _EMBED_CACHE[q] = vec
        return vec
    except Exception:
        return None


_RAG_EMBED_PROC = None


def _rag_embed_health():
    try:
        import urllib.request as _ur_h
        with _ur_h.urlopen("http://127.0.0.1:8771/health", timeout=1.5) as r:
            return bool(__import__("json").loads(r.read().decode("utf-8")).get("ok"))
    except Exception:
        return False


def _ensure_rag_embed():
    """确保本地 BGE 常驻服务在跑；失败不影响 app（RAG 自动回退 BM25）。"""
    global _RAG_EMBED_PROC
    import time as _t_wait
    for _ in range(30):
        if _rag_embed_health():
            return {"ok": True, "started": False}
        _t_wait.sleep(1)
    script = Path(__file__).resolve().parent / "rag_embed_service.py"
    if not Path(_LLM_PY).exists() or not script.exists():
        return {"ok": False, "error": "embedding python/script missing"}
    try:
        import subprocess as _sp_e
        flags = 0x08000000 if os.name == "nt" else 0
        env = dict(os.environ)
        env.setdefault("HF_HUB_OFFLINE", "1")
        env.setdefault("PYTHONUTF8", "1")
        _RAG_EMBED_PROC = _sp_e.Popen(
            [_LLM_PY, str(script)], cwd=str(Path(__file__).resolve().parent.parent),
            env=env, stdout=_sp_e.DEVNULL, stderr=_sp_e.DEVNULL,
            creationflags=flags)
        return {"ok": True, "started": True, "pid": _RAG_EMBED_PROC.pid}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _stop_rag_embed():
    global _RAG_EMBED_PROC
    p = _RAG_EMBED_PROC
    if p is None:
        return
    try:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=4)
            except Exception:
                p.kill()
    except Exception:
        pass
    _RAG_EMBED_PROC = None


def _semantic_items(q, limit=4):
    data = _load_rag_index()
    if not data:
        return []
    vec = _embed_query(q)
    if not vec:
        return []
    out = []
    for it in data.get("items") or []:
        v = it.get("vec") or []
        if not v or len(v) != len(vec):
            continue
        try:
            score = sum(a * b for a, b in zip(vec, v))
        except Exception:
            continue
        txt = str(it.get("text") or "")
        if any(s in txt.lower() for s in _PROJECT_SENSITIVE):
            continue
        out.append((score, it))
    out.sort(key=lambda x: x[0], reverse=True)
    return [{"source": str(x.get("source") or ""),
             "kind": str(x.get("kind") or "semantic"),
             "text": str(x.get("text") or "")[:900],
             "score": round(float(sc), 4)} for sc, x in out[:max(1, int(limit))]]


def _project_context(question="", limit=6):
    """RAG-lite：从项目文档取相关段落 + 固定权威摘要。"""
    import re as _re
    q = str(question or "")
    keys = [k for k in ("元DGTF", "四层", "修行", "研究", "对撞", "元层", "EML",
                        "DSH", "调度", "LoRA", "app", "映射", "自洽", "边界",
                        "route", "rounds") if k in q]
    import re as _re_q
    qterms = [x.lower() for x in _re_q.findall(
        r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,4}", q)][:20]
    chunks = []
    for rel in _PROJECT_DOCS:
        for para in _project_doc_paras(rel):
            score = sum(para.count(k) for k in keys) if keys else 0
            score += 1 if "元DGTF" in para else 0
            chunks.append((score, rel, para))
    chunks.sort(key=lambda x: x[0], reverse=True)
    _pre = [{"source": rel, "text": para} for _s, rel, para in chunks[:40]]
    _query = " ".join(keys + qterms)
    _ranked = _bm25_rank(_pre, _query, topk=max(1, int(limit)))
    picked = []
    seen = set()
    for x in _ranked:
        para = str(x.get("text") or "")
        sig = para[:80]
        if sig in seen:
            continue
        seen.add(sig)
        picked.append({"source": str(x.get("source") or ""), "text": para})
    knowledge = []
    try:
        import sys as _sys_k
        _sys_k.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from dgtf_v2.agent_bridge import read_knowledge
        rows = read_knowledge(limit=200)
        scored = []
        for it in rows:
            blob = (str(it.get("title") or "") + " "
                    + str(it.get("claim") or it.get("summary") or ""))
            low = blob.lower()
            if any(s in low for s in _PROJECT_SENSITIVE):
                continue
            score = sum(blob.count(k) for k in keys) if keys else 0
            score += sum(1 for t in qterms if t in low)
            if score <= 0:
                continue
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        for _sc, it in scored[:4]:
            knowledge.append({"title": str(it.get("title") or "")[:200],
                              "url": str(it.get("url") or "")[:300],
                              "claim": str(it.get("claim") or it.get("summary") or "")[:600]})
    except Exception:
        knowledge = []
    parts = ["【元DGTF 项目权威背景（内置，本地文档+资料库注入）】", _PROJECT_BRIEF]
    imported = []
    try:
        cands = []
        for it in _imported_anchor_items():
            low = it["text"].lower()
            score = sum(it["text"].count(k) for k in keys) if keys else 0
            score += sum(1 for t in qterms if t in low)
            if score > 0:
                cands.append((score, it))
        cands.sort(key=lambda x: x[0], reverse=True)
        imported = [it for _s, it in cands[:3]]
    except Exception:
        imported = []
    external = _context_external_allowed()
    if not external:
        knowledge = []
        imported = []
    semantic = []
    if external:
        try:
            semantic = _semantic_items(q, 4)
        except Exception:
            semantic = []
    citations = []
    for _i, x in enumerate(picked, 1):
        _cid = "S%d" % _i
        citations.append({"id": _cid, "kind": "doc", "source": x["source"]})
        x["cid"] = _cid
    for _i, it in enumerate(knowledge, 1):
        _cid = "K%d" % _i
        citations.append({"id": _cid, "kind": "knowledge",
                          "source": it["title"], "url": it["url"]})
        it["cid"] = _cid
    for _i, it in enumerate(imported, 1):
        _cid = "I%d" % _i
        citations.append({"id": _cid, "kind": "imported",
                          "source": it["source"]})
        it["cid"] = _cid
    for _i, it in enumerate(semantic, 1):
        _cid = "E%d" % _i
        citations.append({"id": _cid, "kind": "semantic",
                          "source": it["source"]})
        it["cid"] = _cid
    for x in picked:
        parts.append("[" + x["cid"] + "] " + x["source"] + ": " + x["text"])
    if knowledge:
        parts.append("【本地资料库（导入/检索）】")
        for it in knowledge:
            parts.append("- [" + it["cid"] + "] " + it["title"] + " | "
                         + it["claim"] + " | " + it["url"])
    if imported:
        parts.append("【导入资料（app 本地上传）】")
        for it in imported:
            parts.append("[" + it["cid"] + "] " + it["source"] + ": " + it["text"])
    if semantic:
        parts.append("【语义检索（BGE 本地）】")
        for it in semantic:
            parts.append("[" + it["cid"] + "] " + it["source"] + ": " + it["text"])
    if not external:
        parts.append("【隐私策略】外部上下文已禁用：本地资料/导入资料未随请求外发。")
    parts.append("【回答约束】涉及元DGTF时必须依据以上背景；引用时标注 [S#]/[K#]/[I#]；背景没有的，明确说不知道，不得编造。")
    _max = max(1000, min(12000, int(os.getenv(
        "DGTF_PROJECT_CONTEXT_MAX_CHARS", "7000"))))
    _layer_kw = {"0": ["修行", "展开", "候选", "锚点"],
                 "1": ["研究", "证据", "子问题", "收敛"],
                 "both": ["对撞", "冲突", "裁决", "线头"],
                 "all": ["元", "闭环", "决策", "停止", "记忆"]}
    layer_contexts = {}
    for _ly, _kws in _layer_kw.items():
        _rows = []
        for _src_list in (picked, imported, semantic):
            for _x in _src_list:
                _t = str(_x.get("text") or "")
                _sc = sum(_t.count(k) for k in _kws)
                if _sc > 0:
                    _rows.append((_sc, _x))
        _rows.sort(key=lambda x: x[0], reverse=True)
        layer_contexts[_ly] = [{"source": x.get("source") or x.get("cid"),
                                "text": str(x.get("text") or "")[:600],
                                "score": sc} for sc, x in _rows[:2]]
    txt, _red = _redact_context("\n".join(parts))
    return {"ok": True, "text": txt[:_max],
            "layer_contexts": layer_contexts,
            "sources": [x["source"] for x in picked],
            "knowledge_sources": [x["title"] for x in knowledge],
            "imported_sources": [x["source"] for x in imported],
            "semantic_sources": [x["source"] for x in semantic],
            "citations": citations, "redactions": _red,
            "external_allowed": external,
            "policy": "project+knowledge+imported+semantic" if external else "brief-only",
            "keys": keys, "chars": len(txt[:_max]), "max_chars": _max,
            "retrieval_method": ("keyword+bm25+bge" if semantic else "keyword+bm25_rerank"),
            "sensitive_filter": True, "cached_docs": True}


def _quality_alt(task_id):
    """三态质量不可靠时的可解释替代分：覆盖 × 回答率 × 收尾完整度 − flags。"""
    import json as _json
    t = runner.get_task(str(task_id))
    if not t:
        # 服务重启后内存任务丢失：回退到 outputs/*.run.json
        for _p in oi.OUTPUTS_DIR.glob("*.run.json"):
            try:
                _d = _json.loads(_p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if str(_d.get("id") or "") == str(task_id):
                t = _d
                break
    if not t:
        return {"ok": False, "error": "task not found"}
    name = str(t.get("output_name") or "")
    if not name:
        return {"ok": False, "error": "no output yet", "status": t.get("status")}
    packed = oi.OUTPUTS_DIR / (name[:-3] + ".packed.json" if name.lower().endswith(".md")
                               else name + ".packed.json")
    if not packed.exists():
        return {"ok": False, "error": "packed not found", "status": t.get("status")}
    try:
        d = _json.loads(packed.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    q = d.get("quality") or {}
    cov = float(q.get("coverage") or 0.0)
    answered = int(q.get("answered") or 0)
    total = int(q.get("answerable_total") or 0)
    ans_rate = (answered / total) if total else (1.0 if answered else 0.0)
    flags = list(q.get("flags") or [])
    layers = list(q.get("layers") or [])
    closed = 0
    for ly in layers:
        stop = str(ly.get("stop") or "")
        if stop and not any(x in stop for x in ("token", "预算", "截断")):
            closed += 1
    closure = (closed / len(layers)) if layers else 0.0
    score = 100.0 * max(0.0, min(1.0, cov)) * ans_rate * (0.7 + 0.3 * closure)
    score = score - 6.0 * len(flags)
    score = max(0.0, min(100.0, round(score, 2)))
    grade = "A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 55 else "D"))
    return {"ok": True, "task_id": str(task_id), "score": score, "grade": grade,
            "basis": {"coverage": cov, "answered": answered,
                      "answerable_total": total, "answer_rate": round(ans_rate, 4),
                      "layers_closed": closed, "layers_total": len(layers),
                      "closure": round(closure, 4), "flags": flags},
            "tri_state": q.get("tri_state"), "tri_quality": q.get("tri_quality"),
            "scheme": "coverage*answer_rate*(0.7+0.3*closure)-6*flags",
            "note": "三态 α 不可靠时使用；可解释、可复算"}


def _llm_status():
    import json as _json
    out = {"ok": bool(_LLM_ADAPTER.exists()),
           "adapter": str(_LLM_ADAPTER),
           "base_model": _LLM_MODEL,
           "python": _LLM_PY,
           "adapter_files": 0,
           "note": "Qwen2.5-0.5B-Instruct + LoRA；本地调度规划器"}
    try:
        if _LLM_ADAPTER.exists():
            out["adapter_files"] = len(list(_LLM_ADAPTER.glob("*")))
    except Exception:
        pass
    for key, p in (("train", _LLM_METRICS), ("eval", _LLM_EVAL)):
        try:
            if p.exists():
                out[key] = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            out[key] = {"error": str(exc)}
    if out.get("eval"):
        out["eval_summary"] = {k: out["eval"].get(k) for k in ("base", "lora")}
    out["backends"] = [{"id": "hybrid", "label": "Qwen route + DeepSeek rounds",
                        "model": "hybrid", "adapter": "qwen05b + deepseek15b",
                        "ok": Path(_LLM_BACKENDS["qwen05b"]["adapter"]).exists()
                        and Path(_LLM_BACKENDS["deepseek15b"]["adapter"]).exists()}]
    out["backends"] += [{"id": _k, "label": _v.get("label"),
                        "model": _v.get("model"),
                        "adapter": str(_v.get("adapter")),
                        "ok": Path(_v.get("adapter")).exists()}
                       for _k, _v in _LLM_BACKENDS.items()]
    return out


def _llm_predict_local(question="", backend="qwen05b"):
    """调用本地 LoRA 小模型预测 route/rounds；不占用 app 主进程显存。"""
    import subprocess as _sp
    import json as _json
    if str(backend or "") == "hybrid":
        return _llm_hybrid(question)
    _bk = _LLM_BACKENDS.get(str(backend or "qwen05b")) or _LLM_BACKENDS["qwen05b"]
    _model = str(_bk["model"])
    _adapter = Path(_bk["adapter"])
    q = str(question or "").strip()
    if not q:
        return {"ok": False, "error": "question 为空"}
    if not Path(_LLM_PY).exists():
        return {"ok": False, "error": "训练环境不存在：" + _LLM_PY}
    if not _adapter.exists():
        return {"ok": False, "error": "adapter 不存在：" + str(_adapter)}
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["HF_HUB_OFFLINE"] = "1"
    try:
        p = _sp.run([_LLM_PY, str(_LLM_SCRIPT), "--question", q,
                     "--model", _model, "--adapter", str(_adapter)],
                    cwd=str(Path(__file__).resolve().parent.parent),
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=180, env=env)
        out = (p.stdout or "").strip().splitlines()
        data = {}
        for ln in reversed(out):
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    data = _json.loads(ln)
                    break
                except Exception:
                    pass
        if not data:
            return {"ok": False, "error": "无 JSON 输出",
                    "stderr": (p.stderr or "")[-800:]}
        parsed = data.get("parsed") or {}
        return {"ok": bool(data.get("ok")), "parsed": parsed,
                "raw": data.get("raw"), "returncode": p.returncode,
                "model": str(_bk.get("label") or ""), "backend": str(backend or "qwen05b")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _llm_hybrid(question=""):
    """融合：0.5B 给 route（更准），DeepSeek 蒸馏给 rounds（MAE 更低）。"""
    a = _llm_predict_local(question, backend="qwen05b")
    b = _llm_predict_local(question, backend="deepseek15b")
    pa = a.get("parsed") or {}
    pb = b.get("parsed") or {}
    route = pa.get("route") or pb.get("route") or []
    rounds = pb.get("rounds") or pa.get("rounds") or {}
    if not route:
        return {"ok": False, "error": "hybrid 无 route", "qwen": a, "deepseek": b}
    return {"ok": True, "parsed": {"route": route, "rounds": rounds,
                                   "why": "hybrid: Qwen route + DeepSeek rounds"},
            "backend": "hybrid",
            "model": "Qwen2.5-0.5B(route) + DeepSeek-R1-Distill(rounds)",
            "parts": {"qwen": {"ok": a.get("ok"), "model": a.get("model")},
                      "deepseek": {"ok": b.get("ok"), "model": b.get("model")}}}


def _llm_apply(question="", backend="qwen05b"):
    import json as _json
    import time as _t
    r = _llm_predict_local(question, backend=backend)
    p = r.get("parsed") or {}
    route = [str(x) for x in (p.get("route") or [])]
    rounds = p.get("rounds") or {}
    if not route:
        return {"ok": False, "error": r.get("error") or "LLM 未给出 route",
                "predict": r}
    route_txt = ",".join(route)
    rounds_txt = ",".join("%s:%s" % (k, int(v)) for k, v in rounds.items())
    pol = _schedule_policy_load()
    pol.update({"llm_route": route_txt, "llm_rounds": rounds_txt,
                "llm_why": p.get("why"), "llm_applied_at": _t.time(),
                "llm_model": str(r.get("model") or ""),
                "llm_backend": str(r.get("backend") or backend or "qwen05b")})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "route": route, "rounds": rounds,
                "policy": pol, "predict": r}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "predict": r}


def _sched_model_load():
    import json as _json
    for p in (_SCHED_MODEL_FILE, _SCHED_MODEL_RUNTIME):
        try:
            if p.exists():
                return _json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    return {}


def _sched_model_predict(question="", prefer="balanced", lam=None):
    import math as _math
    m = _sched_model_load()
    wq = m.get("quality_weights") or []
    tpl = list(m.get("templates") or [])
    bkt = list(m.get("buckets") or [])
    if not wq or not tpl:
        return {"ok": False, "error": "模型未训练", "path": str(_SCHED_MODEL_FILE)}
    q = str(question or "")
    b = _question_bucket(q)
    qlen_z = (len(q) - float(m.get("qlen_mean") or 0)) / max(1e-9, float(m.get("qlen_std") or 1))
    stats = _v2_shadow_status(limit=5000).get("by_template") or {}
    max_t = max([float(v.get("tokens") or 0) for v in stats.values()] or [1.0]) or 1.0
    lm = {"cost": 0.50, "quality": 0.05}.get(str(prefer), 0.20) if lam is None else float(lam)
    preds = []
    for t in tpl:
        rounds = 1
        try:
            rounds = int(str(t).rsplit(":r", 1)[1])
        except Exception:
            pass
        x = [1.0] + [1.0 if t == tt else 0.0 for tt in tpl] \
            + [1.0 if b == bb else 0.0 for bb in bkt] \
            + [float(rounds), qlen_z]
        if len(x) != len(wq):
            continue
        qhat = float(sum(a * c for a, c in zip(x, wq)))
        tok = float((stats.get(t) or {}).get("tokens") or 0)
        score = qhat - lm * (tok / max_t)
        preds.append({"template": t, "pred_quality": round(qhat, 4),
                      "tokens": round(tok, 1),
                      "calls": (stats.get(t) or {}).get("calls") or 0,
                      "n": (stats.get(t) or {}).get("n") or 0,
                      "score": round(score, 4)})
    preds.sort(key=lambda x: x["score"], reverse=True)
    return {"ok": True, "question_bucket": b, "question_len": len(q),
            "prefer": prefer, "lambda_cost": lm,
            "model": {"version": m.get("version"), "kind": m.get("kind"),
                      "rows": m.get("rows"), "quality_test": m.get("quality_test"),
                      "quality_baseline": m.get("quality_baseline")},
            "predictions": preds, "chosen": preds[0] if preds else None,
            "note": "quality 使用本地岭回归权重；tokens 用经验均值，token 模型未采用"}


def _sched_model_apply(question="", prefer="balanced", lam=None):
    import json as _json
    import time as _t
    r = _sched_model_predict(question=question, prefer=prefer, lam=lam)
    arm = r.get("chosen") or {}
    tmpl = str(arm.get("template") or "")
    if not tmpl:
        return {"ok": False, "error": r.get("error") or "没有可选模板"}
    route = tmpl.split(":", 1)[0]
    rounds = tmpl.rsplit(":r", 1)[1] if ":r" in tmpl else ""
    pol = _schedule_policy_load()
    pol.update({"model_template": tmpl, "template": tmpl,
                "route": route, "rounds": rounds,
                "model_pred_quality": arm.get("pred_quality"),
                "model_score": arm.get("score"),
                "model_bucket": r.get("question_bucket"),
                "model_applied_at": _t.time()})
    try:
        _SCHED_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "chosen": arm, "policy": pol,
                "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _v2_context_stats(limit=5000):
    """run_id → packed.question 分桶，再聚合该桶的模板质量/成本。"""
    import json as _json
    from collections import defaultdict
    root = Path(__file__).resolve().parent.parent
    run_bucket = {}
    for p in sorted((root / "outputs").glob("*.packed.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = _json.loads(p.read_text(encoding="utf-8", errors="replace"))
            run_bucket[p.stem] = _question_bucket(d.get("question"))
        except Exception:
            continue
    ev = root / "dgtf_memory" / "v2_events.jsonl"
    groups = defaultdict(lambda: defaultdict(lambda: {"n": 0, "q": 0.0, "sd": 0.0,
                                                       "vals": [], "tokens": 0.0,
                                                       "calls": 0.0}))
    if ev.exists():
        for ln in ev.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(limit)):]:
            try:
                d = _json.loads(ln)
            except Exception:
                continue
            if not isinstance(d, dict) or str(d.get("kind") or "") != "schedule_outcome":
                continue
            rid = str(d.get("run_id") or "")
            b = run_bucket.get(rid)
            if not b:
                continue
            pl = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            t = str(pl.get("template") or "")
            if not t:
                continue
            g = groups[b][t]
            try:
                qq = float(pl.get("quality") or 0)
                g["q"] += qq
                g["vals"].append(qq)
                g["tokens"] += float(pl.get("tokens") or 0)
                g["calls"] += float(pl.get("calls") or 0)
                g["n"] += 1
            except Exception:
                pass
    out = {}
    for b, tm in groups.items():
        bt = {}
        for t, g in tm.items():
            n = int(g["n"] or 0)
            if not n:
                continue
            mu = g["q"] / n
            vals = g["vals"]
            sd = ((sum((x - mu) ** 2 for x in vals) / (n - 1)) ** 0.5) if n > 1 else 0.0
            bt[t] = {"n": n, "quality": round(mu, 4), "sd": round(sd, 4),
                     "tokens": round(g["tokens"] / n, 1),
                     "calls": round(g["calls"] / n, 1)}
        if bt:
            out[b] = bt
    return {"run_bucket": run_bucket, "by_bucket": out}


def _v2_context_bandit(question="", prefer="balanced", c=0.5):
    import math as _math
    stats = _v2_context_stats()
    b = _question_bucket(question)
    bucket_bt = (stats.get("by_bucket") or {}).get(b) or {}
    allb = {}
    for tm in (stats.get("by_bucket") or {}).values():
        for t, v in tm.items():
            d = allb.setdefault(t, {"n": 0, "q": 0.0, "tokens": 0.0, "calls": 0.0})
            n0 = int(v.get("n") or 0)
            d["n"] += n0
            d["q"] += float(v.get("quality") or 0) * n0
            d["tokens"] += float(v.get("tokens") or 0) * n0
            d["calls"] += float(v.get("calls") or 0) * n0
    global_bt = {}
    for t, d in allb.items():
        n0 = int(d["n"] or 0)
        if n0:
            global_bt[t] = {"n": n0, "quality": d["q"] / n0,
                            "tokens": d["tokens"] / n0, "calls": d["calls"] / n0}
    K = 5.0
    bt = {}
    for t in set(bucket_bt) | set(global_bt):
        g = global_bt.get(t) or {"n": 0, "quality": 0.0, "tokens": 0.0, "calls": 0.0}
        x = bucket_bt.get(t)
        n_b = int(x.get("n") or 0) if x else 0
        q_g = float(g.get("quality") or 0)
        if x and n_b > 0:
            q_hat = (n_b * float(x.get("quality") or 0) + K * q_g) / (n_b + K)
            tok_hat = (n_b * float(x.get("tokens") or 0)
                       + K * float(g.get("tokens") or 0)) / (n_b + K)
            calls_hat = (n_b * float(x.get("calls") or 0)
                         + K * float(g.get("calls") or 0)) / (n_b + K)
            sd_hat = float(x.get("sd") or 0) if n_b >= 2 else (q_hat * (1 - q_hat)) ** 0.5
        else:
            q_hat, tok_hat, calls_hat = q_g, float(g.get("tokens") or 0), float(g.get("calls") or 0)
            sd_hat = (q_hat * (1 - q_hat)) ** 0.5
        _n_eff = n_b if (x and n_b > 0) else max(1, int(g.get("n") or 1))
        bt[t] = {"n": _n_eff, "quality": q_hat, "sd": sd_hat,
                 "tokens": tok_hat, "calls": calls_hat}
    fallback = not bool(bucket_bt)
    smoothed = bool(bucket_bt)
    max_t = max([float(v.get("tokens") or 0) for v in bt.values()] or [1.0]) or 1.0
    lam = {"cost": 0.50, "quality": 0.05}.get(str(prefer), 0.20)
    arms = []
    for t, v in bt.items():
        n = int(v.get("n") or 0)
        if n <= 0:
            continue
        q = float(v.get("quality") or 0)
        sd = float(v.get("sd") or 0)
        var = sd * sd if sd > 0 else max(0.0, q * (1 - q))
        bonus = float(c) * _math.sqrt(var / max(1, n))
        score = q + bonus - lam * (float(v.get("tokens") or 0) / max_t)
        arms.append({"template": t, "n": n, "quality": round(q, 4),
                     "bonus": round(bonus, 4), "score": round(score, 4),
                     "tokens": float(v.get("tokens") or 0),
                     "calls": float(v.get("calls") or 0)})
    arms.sort(key=lambda x: x["score"], reverse=True)
    return {"ok": True, "question_bucket": b, "fallback_global": fallback,
            "smoothed": bool(smoothed), "shrink_k": K,
            "arms": arms, "chosen": arms[0] if arms else None,
            "prefer": prefer, "c": c, "lambda_cost": lam,
            "note": "按问题类型分桶 + 向全局均值收缩的 UCB"}


def _v2_auto_apply(prefer="balanced"):
    """自动评估 V2 候选策略并按挡位选最优写入；保留完整候选与选择审计。"""
    import json as _json
    import time as _t
    prefer = str(prefer or "balanced")
    cands = []

    def add(name, tmpl, quality, tokens, low=None, calls=0, n=0, extra=None):
        if not tmpl:
            return
        cands.append({"name": name, "template": str(tmpl),
                      "quality": float(quality or 0),
                      "low": float(low if low is not None else (quality or 0)),
                      "tokens": float(tokens or 0), "calls": float(calls or 0),
                      "n": int(n or 0), "extra": extra or {}})

    try:
        pr = _v2_template_pareto(prefer=prefer, limit=2000)
        rec = pr.get("recommended") or {}
        add("pareto", rec.get("template"), rec.get("quality"), rec.get("tokens"),
            rec.get("low"), rec.get("calls"), rec.get("n"),
            {"frontier_n": len(pr.get("frontier") or [])})
    except Exception:
        pass
    try:
        bt = _v2_best_template(min_n=5)
        add("best", bt.get("template"), bt.get("quality"), bt.get("tokens"),
            bt.get("low"), bt.get("calls"), bt.get("n"), {})
    except Exception:
        pass
    try:
        bd = _v2_bandit(prefer=prefer, c=0.5)
        ch = bd.get("chosen") or {}
        add("bandit", ch.get("template"), ch.get("quality"), ch.get("tokens"),
            ch.get("quality"), ch.get("calls"), ch.get("n"),
            {"ucb": ch.get("ucb"), "score": ch.get("score")})
    except Exception:
        pass
    if not cands:
        return {"ok": False, "error": "暂无 V2 模板样本，无法自动选择"}
    max_q = max(c["low"] for c in cands) or 1.0
    max_t = max(c["tokens"] for c in cands) or 1.0
    lam = {"cost": 0.35, "quality": 0.10}.get(prefer, 0.20)
    for c in cands:
        qn = c["low"] / max_q
        cn = c["tokens"] / max_t
        c["quality_norm"] = round(qn, 4)
        c["cost_norm"] = round(cn, 4)
        c["auto_score"] = round(qn - lam * cn, 4)
    cands.sort(key=lambda x: x["auto_score"], reverse=True)
    chosen = cands[0]
    appliers = {"pareto": _v2_apply_pareto, "best": _v2_apply_best,
                "bandit": _v2_apply_bandit}
    applied = appliers[chosen["name"]](prefer=prefer)
    if not applied.get("ok"):
        return {"ok": False, "error": applied.get("error") or "写入策略失败",
                "candidates": cands, "chosen": chosen}
    pol = applied.get("policy") or _schedule_policy_load()
    pol.update({"auto_strategy": chosen["name"],
                "auto_template": chosen["template"],
                "auto_score": chosen["auto_score"],
                "auto_prefer": prefer,
                "auto_candidates": [{k: v for k, v in c.items() if k != "extra"}
                                    for c in cands],
                "auto_applied_at": _t.time()})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": "策略写入失败：" + str(exc),
                "candidates": cands, "chosen": chosen}
    try:
        audit = {"ts": _t.time(), "prefer": prefer, "chosen": chosen,
                 "candidates": cands, "applied": applied.get("ok")}
        ap = Path(__file__).resolve().parent.parent / "dgtf_memory" / "schedule_auto_apply.jsonl"
        ap.parent.mkdir(parents=True, exist_ok=True)
        with ap.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(audit, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"ok": True, "prefer": prefer, "chosen": chosen,
            "candidates": cands, "applied": applied,
            "policy": pol, "path": str(_SCHEDULE_POLICY_FILE),
            "note": "自动选择 V2 模板策略；挡位只影响质量/成本权重"}


def _v2_apply_bandit(prefer="balanced", c=0.5):
    import json as _json
    import time as _t
    r = _v2_bandit(prefer=prefer, c=c)
    arm = r.get("chosen") or {}
    tmpl = str(arm.get("template") or "")
    if not tmpl:
        return {"ok": False, "error": "没有可选模板"}
    route = tmpl.split(":", 1)[0] if ":" in tmpl else "auto"
    rounds = tmpl.rsplit(":r", 1)[1] if ":r" in tmpl else ""
    pol = _schedule_policy_load()
    pol.update({"bandit_template": tmpl, "template": tmpl,
                "route": route, "rounds": rounds,
                "bandit_score": arm.get("score"),
                "bandit_ucb": arm.get("ucb"),
                "bandit_n": arm.get("n"),
                "bandit_prefer": prefer,
                "bandit_applied_at": _t.time()})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "chosen": arm, "policy": pol,
                "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _v2_apply_context_bandit(question="", prefer="balanced", c=0.5):
    import json as _json
    import time as _t
    r = _v2_context_bandit(question=question, prefer=prefer, c=c)
    arm = r.get("chosen") or {}
    tmpl = str(arm.get("template") or "")
    if not tmpl:
        return {"ok": False, "error": "没有可选模板", "bucket": r.get("question_bucket")}
    route = tmpl.split(":", 1)[0] if ":" in tmpl else "auto"
    rounds = tmpl.rsplit(":r", 1)[1] if ":r" in tmpl else ""
    pol = _schedule_policy_load()
    pol.update({"context_template": tmpl, "template": tmpl,
                "route": route, "rounds": rounds,
                "context_bucket": r.get("question_bucket"),
                "context_score": arm.get("score"),
                "context_applied_at": _t.time()})
    try:
        _SCHEDULE_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_POLICY_FILE.write_text(
            _json.dumps(pol, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "chosen": arm, "bucket": r.get("question_bucket"),
                "fallback_global": r.get("fallback_global"),
                "policy": pol, "path": str(_SCHEDULE_POLICY_FILE)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _v2_rebuild():
    """用真实 packed 重算 V2 schedule_outcome 的按层 quality。"""
    import json as _json
    import sys as _sys
    import time as _t
    root = Path(__file__).resolve().parent.parent
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    try:
        from dgtf_v2.replay import _entry_quality
    except Exception:
        _entry_quality = None
    p = root / "dgtf_memory" / "v2_events.jsonl"
    if not p.exists():
        return {"ok": False, "error": "v2_events.jsonl 不存在"}
    rows, total, changed = [], 0, 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = _json.loads(ln)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        total += 1
        if str(d.get("kind") or "") == "schedule_outcome" and _entry_quality:
            pl = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            tmpl = str(pl.get("template") or "")
            entry = tmpl.split(":", 1)[0] if ":" in tmpl else ""
            rid = str(d.get("run_id") or "")
            packed = root / "outputs" / (rid + ".packed.json")
            if entry and packed.exists():
                try:
                    pk = _json.loads(packed.read_text(encoding="utf-8", errors="replace"))
                    q = _entry_quality(pk, entry)
                    if pl.get("quality") != q:
                        pl["quality"] = q
                        d["payload"] = pl
                        changed += 1
                except Exception:
                    pass
        rows.append(d)
    bak = p.with_suffix(".jsonl.bak-" + str(int(_t.time())))
    try:
        p.replace(bak)
        p.write_text("".join(_json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
                     encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "total": total, "changed": changed,
            "backup": str(bak), "note": "只改 schedule_outcome 的 quality，structure 原样保留"}


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
    server_version = "DGTFApp/" + APP_VERSION

    def log_message(self, fmt, *args):  # 默认静默，--verbose 才打访问日志
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # ── 响应助手 ──────────────────────────────────────────────────
    def _download(self, data: bytes, ctype: str, filename: str, code: int = 200):
        """导出用的二进制响应（带 Content-Disposition）。"""
        self.send_response(code)
        self._send_cookies()
        self._security_headers()
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
        self._send_cookies()
        self._security_headers()
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
        self._send_cookies()
        self._security_headers()
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

    def _cookies(self):
        """需要下发的 Set-Cookie：口令（可选）+ CSRF（始终）。"""
        import secrets as _sec
        out = []
        q = parse_qs(urlparse(self.path).query)
        if _TOKEN and q.get("t", [""])[0] == _TOKEN:
            out.append("dgtf_token=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000"
                       % _TOKEN)
        have = (self.headers.get("Cookie") or "")
        if (_CSRF_COOKIE + "=") not in have:
            out.append("%s=%s; Path=/; SameSite=Strict; Max-Age=2592000"
                       % (_CSRF_COOKIE, _CSRF_TOKEN))
        return out

    def _send_cookies(self):
        for c in self._cookies():
            self.send_header("Set-Cookie", c)

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                         "connect-src 'self'; font-src 'self' data:; "
                         "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")

    def _host_ok(self):
        raw = (self.headers.get("Host") or "").strip().lower()
        if not raw:
            return False
        if raw.startswith("["):
            h = raw[1:raw.find("]")] if "]" in raw else raw
        else:
            h = raw.rsplit(":", 1)[0] if raw.count(":") == 1 else raw
        return h in _ALLOWED_HOSTS

    def _origin_ok(self):
        """有 Origin/Referer 时必须来自白名单 Host；没有则交给 CSRF/本地调用。"""
        import urllib.parse as _up
        for hdr in ("Origin", "Referer"):
            val = (self.headers.get(hdr) or "").strip()
            if not val:
                continue
            try:
                u = _up.urlparse(val)
                h = (u.hostname or "").lower()
                if h not in _ALLOWED_HOSTS:
                    return False
            except Exception:
                return False
        return True

    def _csrf_ok(self):
        hdr = (self.headers.get("X-CSRF-Token") or "").strip()
        return bool(hdr) and hdr == _CSRF_TOKEN

    def _granted(self) -> bool:
        if not _TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == _TOKEN:
            return True
        return ("dgtf_token=" + _TOKEN) in (self.headers.get("Cookie") or "")

    def _guard(self, mutate: bool = False) -> bool:
        """Host 白名单 + 口令 + Origin/Referer + CSRF。"""
        if not self._host_ok():
            self._json({"error": "Host 不在白名单"}, 421)
            return False
        if not self._granted():
            self._json({"error": "未授权：本服务启用了访问口令，请用启动时打印的带 ?t= 的网址打开"}, 401)
            return False
        if mutate:
            if not self._origin_ok():
                self._json({"error": "Origin/Referer 不在白名单"}, 403)
                return False
            has_browser_origin = bool(self.headers.get("Origin") or self.headers.get("Referer"))
            if has_browser_origin and not self._csrf_ok():
                self._json({"error": "CSRF token 缺失或无效"}, 403)
                return False
        return True

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
        self._send_cookies()
        self._security_headers()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # ★ 静态资源**必须**禁缓存：这些文件是「每次请求现读磁盘」的开发产物，
        #   浏览器一缓存，改完 CSS/JS 用户刷新拿到的还是旧版（改了半天看不到效果）。
        #   API 那边本来就有 no-store，静态资源这里以前漏了。
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _dsh_workbench(self, action):
        """DSH 受控工具：固定动作 + 每次 run 令牌；不开放任意命令/密钥/git。"""
        import json as _json
        import time as _tw
        action = str(action or "")
        tok = (self.headers.get("X-DSH-Workbench") or "").strip()
        if not tok:
            try:
                tok = str((self._read_json() or {}).get("token") or "").strip()
            except Exception:
                tok = ""
        info = _wb_token_info(tok)
        if not info:
            return self._json({"error": "工作台工具令牌无效或已过期"}, 403)
        base = info.get("before") or set()
        changed = _commit_scope(_changed_since(base, {}))
        if action == "fast_gate":
            res = _run_fast_gate()
        elif action == "acceptance":
            res = {"changed": changed, "acceptance": _targeted_acceptance(changed)}
            res["ok"] = bool(res["acceptance"].get("ok"))
        elif action == "project":
            props = _list_proposals(300)
            counts = {}
            for p in props:
                st = str(p.get("status") or "")
                counts[st] = counts.get(st, 0) + 1
            try:
                from dgtf_v2.agent_bridge import read_tasks as _read_q
                _qn = len(_read_q(limit=1000))
            except Exception:
                _qn = len(_agent_queue_snapshot())
            res = {"ok": True, "app": APP_VERSION,
                   "head": (_git(["rev-parse", "HEAD"]).get("out") or "").strip(),
                   "branch": (_git(["rev-parse", "--abbrev-ref", "HEAD"]).get("out") or "").strip(),
                   "queue_n": _qn,
                   "proposal_counts": counts, "changed": changed}
        elif action == "proposals":
            props = [p for p in _list_proposals(300)
                     if str(p.get("status")) in ("pending", "confirmed")]
            res = {"ok": True, "count": len(props),
                   "proposals": [{"id": p.get("id"),
                                  "status": p.get("status"),
                                  "title": str((p.get("task") or {}).get("title") or "")[:160],
                                  "plan": str(p.get("plan") or "")[:600]}
                                 for p in props[:30]]}
        elif action == "queue":
            res = {"ok": True, "tasks": _agent_queue_snapshot()}
        elif action == "status":
            res = {"ok": True, "head": (_git(["rev-parse", "HEAD"]).get("out") or "").strip(),
                   "branch": (_git(["rev-parse", "--abbrev-ref", "HEAD"]).get("out") or "").strip(),
                   "changed": changed}
        else:
            return self._json({"error": "未知工作台工具"}, 404)
        try:
            root = Path(__file__).resolve().parent.parent
            with (root / "dgtf_memory" / "dsh_workbench_calls.jsonl").open(
                    "a", encoding="utf-8") as fh:
                fh.write(_json.dumps({"ts": _tw.time(), "action": action,
                                      "ok": bool(res.get("ok")),
                                      "changed": res.get("changed") or []},
                                     ensure_ascii=False) + "\n")
        except Exception:
            pass
        return self._json({"ok": bool(res.get("ok")), "action": action, "result": res})

    # ── GET ───────────────────────────────────────────────────────
    def do_GET(self):
        if not self._guard():          # ★ R42：口令开启时先过闸（默认关闭 ⇒ 恒真）
            return
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)

        if p in ("/", "/index.html"):
            return self._serve_static("index.html")
        if p == "/api/csrf":
            return self._json({"csrf": _CSRF_TOKEN})
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
        if p == "/api/agent/eml/dataset":
            try:
                return self._json(_eml_dataset_meta())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/eml":
            try:
                return self._json(_eml_status())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/consistency/history":
            try:
                return self._json({"ok": True, "history": _consistency_history(50)})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/consistency":
            try:
                return self._json(_self_consistency())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/context-bandit":
            try:
                return self._json(_v2_context_bandit(
                    question=str((q.get("q") or [""])[0]),
                    prefer=str((q.get("prefer") or ["balanced"])[0]),
                    c=float((q.get("c") or ["0.5"])[0] or 0.5)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/project/context/history":
            try:
                return self._json({"ok": True, "history": _context_trace_list(50)})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/security/context-policy":
            return self._json({"ok": True,
                               "external_allowed": _context_external_allowed(),
                               "env": "DGTF_CONTEXT_EXTERNAL",
                               "redaction": True, "length_cap": int(os.getenv(
                                   "DGTF_PROJECT_CONTEXT_MAX_CHARS", "7000")),
                               "trace_file": str(_CONTEXT_TRACE_FILE),
                               "embedding": "local BGE @127.0.0.1:8771",
                               "dsh": {"write": "workspace-write",
                                       "danger_full_access": "denied",
                                       "forbidden": [".env", "keys", ".git internals",
                                                     "third-party upload"],
                                       "api_only": True}})
        if p == "/api/project/context":
            try:
                return self._json(_project_context(
                    question=str((q.get("q") or [""])[0])))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/bandit":
            try:
                return self._json(_v2_bandit(
                    prefer=str((q.get("prefer") or ["balanced"])[0]),
                    c=float((q.get("c") or ["0.5"])[0] or 0.5)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/llm/status":
            try:
                return self._json(_llm_status())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/model":
            try:
                m = _sched_model_load()
                return self._json({"ok": bool(m), "model": m,
                                   "path": str(_SCHED_MODEL_FILE)})
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/model/predict":
            try:
                return self._json(_sched_model_predict(
                    question=str((q.get("q") or [""])[0]),
                    prefer=str((q.get("prefer") or ["balanced"])[0])))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/pareto":
            try:
                return self._json(_v2_template_pareto(
                    prefer=str((q.get("prefer") or ["balanced"])[0]),
                    limit=int((q.get("limit") or ["2000"])[0] or 2000)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/ab":
            try:
                if str((q.get("paired") or [""])[0]) in ("1", "true", "yes"):
                    return self._json(_v2_paired_ab(
                        left=str((q.get("left") or [""])[0]),
                        right=str((q.get("right") or [""])[0])))
                if str((q.get("all") or [""])[0]) in ("1", "true", "yes"):
                    return self._json(_v2_all_pairs(
                        alpha=float((q.get("alpha") or ["0.05"])[0] or 0.05)))
                return self._json(_v2_ab(
                    left=str((q.get("left") or [""])[0]),
                    right=str((q.get("right") or [""])[0])))
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
            return self._json({"proposals": _list_proposals(),
                               "summary": _proposal_summary()})
        m = re.match(r"^/api/dsh/artifacts/([^/]+)$", p)
        if m:
            return self._json(_read_dsh_artifact(unquote(m.group(1))))
        if p == "/api/dsh/artifacts":
            return self._json({"artifacts": _list_dsh_artifacts()})
        if p == "/api/dsh/sessions":
            return self._json({"sessions": _list_dsh_sessions()})
        if p == "/api/dsh/chats":
            return self._json({"chats": _conv_list(50)})
        if p == "/api/git/status":
            return self._json(_git_status())
        if p == "/api/agent/daemon":
            return self._json(agent_daemon_status())
        if p == "/api/agent/autopilot":
            st = _autopilot_status()
            if st.get("enabled") and not st.get("thread_running"):
                try:
                    _autopilot_start(start_daemon=False)
                    st = _autopilot_status()
                except Exception:
                    pass
            return self._json(st)
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

        m = re.match(r"^/api/quality/([^/]+)$", p)
        if m:
            return self._json(_quality_alt(unquote(m.group(1))))
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
                latest = max([float(h.get("ts") or 0) for h in hits] or [0])
                when = _fmt_epoch_cn(latest) if latest else ""
                lines.append("## " + title)
                lines.append("")
                lines.append("- 去重后 %d 条 · 最近检索 %s"
                             % (len(hits), when or "未知"))
                lines.append("")
                for h in hits:
                    ht = _fmt_epoch_cn(h.get("ts"))
                    lines.append("- [%s](%s)%s" % (
                        h.get("title", ""), h.get("url", ""),
                        (" — 检索 " + ht) if ht else ""))
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
        if not self._guard(mutate=True):   # Host + 口令 + Origin/Referer + CSRF
            return
        u = urlparse(self.path)
        p = u.path

        if p.startswith("/api/dsh/workbench/"):
            return self._dsh_workbench(p.rsplit("/", 1)[-1])

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
        if p == "/api/agent/eml/export":
            try:
                data = self._read_json()
                return self._json(_eml_export_dataset(
                    limit=int(data.get("limit") or 5000)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/eml/replay":
            try:
                data = self._read_json()
                return self._json(_eml_replay(
                    limit=int(data.get("limit") or 60),
                    dry_run=bool(data.get("dry_run", True))))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/replay":
            try:
                data = self._read_json()
                return self._json(_v2_replay_packed(
                    limit=int(data.get("limit") or 30)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/rebuild":
            try:
                return self._json(_v2_rebuild())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/llm/status":
            try:
                return self._json(_llm_status())
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/llm/predict":
            try:
                data = self._read_json()
                return self._json(_llm_predict_local(
                    question=str(data.get("question") or ""),
                    backend=str(data.get("backend") or "qwen05b")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/llm/apply":
            try:
                data = self._read_json()
                return self._json(_llm_apply(
                    question=str(data.get("question") or ""),
                    backend=str(data.get("backend") or "qwen05b")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/model/apply":
            try:
                data = self._read_json()
                return self._json(_sched_model_apply(
                    question=str(data.get("question") or ""),
                    prefer=str(data.get("prefer") or "balanced")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/apply-context-bandit":
            try:
                data = self._read_json()
                return self._json(_v2_apply_context_bandit(
                    question=str(data.get("question") or ""),
                    prefer=str(data.get("prefer") or "balanced"),
                    c=float(data.get("c") or 0.5)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/auto-apply":
            try:
                data = self._read_json()
                return self._json(_v2_auto_apply(
                    prefer=str(data.get("prefer") or "balanced")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/apply-bandit":
            try:
                data = self._read_json()
                return self._json(_v2_apply_bandit(
                    prefer=str(data.get("prefer") or "balanced"),
                    c=float(data.get("c") or 0.5)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/apply-pareto":
            try:
                data = self._read_json()
                return self._json(_v2_apply_pareto(
                    prefer=str(data.get("prefer") or "balanced"),
                    limit=int(data.get("limit") or 2000)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/v2/apply-best":
            try:
                data = self._read_json()
                return self._json(_v2_apply_best(
                    min_n=int(data.get("min_n") or 5)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/schedule/pareto/apply":
            try:
                data = self._read_json()
                return self._json(_schedule_policy_apply(
                    prefer=str(data.get("prefer") or "balanced")))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/knowledge/agent-search":
            try:
                data = self._read_json()
                q = str(data.get("q") or data.get("query") or "").strip()
                qs = [str(x).strip() for x in (data.get("queries") or []) if str(x).strip()]
                if q and not qs:
                    qs = [x.strip() for x in q.split(",") if x.strip()]
                return self._json(_knowledge_agent_search(
                    queries=qs, mode=str(data.get("mode") or "query"),
                    limit=int(data.get("limit") or 3)))
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        if p == "/api/agent/knowledge/refresh":
            try:
                data = self._read_json()
                return self._json(_auto_refresh_knowledge(
                    queries=data.get("queries")))
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
                            if it.get("retrieved_at"):
                                _meta.append("检索=" + _fmt_epoch_cn(
                                    it.get("retrieved_at")))
                            if it.get("fetched_at"):
                                _meta.append("爬取=" + _fmt_epoch_cn(
                                    it.get("fetched_at")))
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
                prompt = ("提案模式：允许读取项目文件核对现状，但不要修改源码。只根据下面任务详情"
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
        if p == "/api/agent/autopilot":
            data = self._read_json()
            if bool(data.get("enabled")):
                out = _autopilot_start(interval=data.get("interval"),
                                       knowledge_every=data.get("knowledge_every"))
            else:
                out = _autopilot_stop()
            return self._json(out)
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
                learn = _autopilot_knowledge(prop) if _autopilot_cfg_load().get("enabled", False) else ""
                res = _repair_with_acceptance(prop, model="deepseek-flash",
                                              emit=_emit_appr, max_attempts=3,
                                              extra_context=learn,
                                              permission=str(data.get("permission") or ""))
                repair = res.get("repair") or {}
                prop["status"] = ("applied" if (repair.get("committed") and res.get("ok"))
                                  else "failed")
                prop["approver"] = str(data.get("mode") or "user")
                import time as _tm3
                prop["approved_ts"] = _tm3.time()
                prop["conversation_id"] = str(res.get("conversation_id") or "")
                prop["conversation_ids"] = list(res.get("conversation_ids") or [])
                prop["attempts"] = list(res.get("attempts") or [])
                prop["acceptance"] = res.get("acceptance") or {}
                prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                                  "acceptance": res.get("acceptance"),
                                  "repair": repair,
                                  "conversation_id": prop["conversation_id"],
                                  "conversations": prop["conversation_ids"]}
                if prop["status"] == "applied":
                    version = _next_repair_version()
                    prop["version"] = version
                    prop["artifact"] = _save_repair_artifact(prop, prop["acceptance"], version)
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
            learn = _autopilot_knowledge(prop) if _autopilot_cfg_load().get("enabled", False) else ""
            res = _repair_with_acceptance(prop, model="deepseek-flash",
                                          max_attempts=3, extra_context=learn,
                                          permission=str(data.get("permission") or ""))
            repair = res.get("repair") or {}
            prop["status"] = ("applied" if (repair.get("committed") and res.get("ok"))
                              else "failed")
            prop["approver"] = str(data.get("mode") or "user")
            import time as _tm2
            prop["approved_ts"] = _tm2.time()
            prop["conversation_id"] = str(res.get("conversation_id") or "")
            prop["conversation_ids"] = list(res.get("conversation_ids") or [])
            prop["attempts"] = list(res.get("attempts") or [])
            prop["acceptance"] = res.get("acceptance") or {}
            prop["result"] = {"ok": res.get("ok"), "gate": res.get("gate"),
                              "acceptance": res.get("acceptance"),
                              "repair": repair,
                              "conversation_id": prop["conversation_id"],
                              "conversations": prop["conversation_ids"]}
            if prop["status"] == "applied":
                version = _next_repair_version()
                prop["version"] = version
                prop["artifact"] = _save_repair_artifact(prop, prop["acceptance"], version)
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
            proc = None
            with _conv_lock():
                conv = _DSH_CONV.get(cid) or _conv_load(cid)
                if conv:
                    _DSH_CONV_CANCELLED.add(cid)
                    for t in conv.get("turns") or []:
                        if t.get("status") in ("queued", "running"):
                            t["status"] = "canceled"
                    _DSH_CONV[cid] = conv
                    _conv_save(conv)
                proc = _DSH_CONV_PROCS.get(cid)
            if proc is None:
                _DSH_CONV_CANCELLED.discard(cid)
            if proc is not None:
                try:
                    import subprocess as _csp
                    _csp.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                             capture_output=True, timeout=10)
                except Exception:
                    try:
                        proc.kill()
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
            _pctx_opt = opts.pop("project_context", None)
            _is_mock_task = bool(opts.get("mock"))
            if _pctx_opt is None:
                # 项目背景内置：真实任务默认注入；mock/自检保持原文以稳定基线。
                _project_ctx = not _is_mock_task
            else:
                _project_ctx = bool(_pctx_opt)
            _pc = {}
            if _project_ctx:
                _pc = _project_context(question)
                if _pc.get("text"):
                    opts["_prompt_prefix"] = (_pc["text"]
                                             + "\n\n【用户问题】\n")
            _ap_opt = opts.pop("auto_pareto", None)
            # 默认自动帕累托：真实任务默认启用；mock/自检默认关闭以稳定基线。
            _auto_pareto = (bool(_ap_opt) if _ap_opt is not None
                            else not _is_mock_task)
            _auto_template = bool(opts.pop("auto_template", False))
            _auto_llm = bool(opts.pop("auto_llm", False))
            if _auto_llm:
                _lr = _llm_predict_local(question,
                                         backend=str(opts.pop("llm_backend", "") or "qwen05b"))
                _lp = _lr.get("parsed") or {}
                if _lp.get("route"):
                    opts.setdefault("route", ",".join(str(x) for x in _lp["route"]))
                    opts.setdefault("rounds", ",".join("%s:%s" % (k, v)
                                                        for k, v in (_lp.get("rounds") or {}).items()))
            if _auto_template:
                _pol = _schedule_policy_load()
                if _pol.get("template"):
                    opts.setdefault("route", str(_pol.get("route") or "auto"))
                    opts.setdefault("rounds", str(_pol.get("rounds") or "auto"))
            if _auto_pareto and not opts.get("profile"):
                _pol = _schedule_policy_load()
                opts["profile"] = str(_pol.get("profile") or "方案F-帕累托最优.yaml")
            try:
                tid = runner.start_task(question, opts)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            if _project_ctx and _pc:
                _context_trace_save(tid, _pc, question, {"kind": "task"})
            return self._json({"id": tid, "auto_pareto": _auto_pareto,
                               "auto_template": _auto_template,
                               "auto_llm": _auto_llm,
                               "project_context": _project_ctx,
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
        if _autopilot_cfg_load().get("enabled", True):
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

    try:
        _pol0 = _schedule_policy_load()
        if not _pol0.get("auto_strategy") and str(os.getenv(
                "DGTF_V2_AUTO_ON_START", "1")).strip().lower() not in ("0", "false", "off", "no"):
            _auto0 = _v2_auto_apply("balanced")
            print("  V2 自动策略：" + (("已选择 " + str((_auto0.get("chosen") or {}).get("name")))
                                      if _auto0.get("ok") else "无样本，跳过"))
    except Exception as _e:  # noqa: BLE001
        print("  V2 自动策略跳过：" + str(_e))
    try:
        _er = _ensure_rag_embed()
        print("  BGE embedding：" + ("已就绪" if _er.get("ok") else "不可用（回退 BM25）"))
    except Exception as _e:  # noqa: BLE001
        print("  BGE embedding 启动失败（回退 BM25）：" + str(_e))

    # ★ 常驻 Agent：app 启动即确保 agent_daemon 在跑（已有实例则复用）。
    #   只消费本地队列、写提案；不联网、不调 LLM。可用 --no-agent-daemon 关闭。
    daemon_started = None
    if not args.no_agent_daemon and _autopilot_cfg_load().get("enabled", True):
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
        try:
            _autopilot_start(start_daemon=False)
            print("  Autopilot：已启用（安全提案自动修复，高风险留人工）")
        except Exception as e:  # noqa: BLE001
            print(f"  Autopilot 启动失败（忽略）：{type(e).__name__}: {e}")

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
        try:
            _stop_rag_embed()
        except Exception:
            pass
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
