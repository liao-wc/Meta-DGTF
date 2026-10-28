# -*- coding: utf-8 -*-
"""App 侧「本地链路」守护与健康读数（8772 推理服务 + 8773 OpenAI 适配层）。

为什么需要（本会话实测的缺口）
------------------------------
本地全链路是**两段**服务：
  · 127.0.0.1:8772 —— 本地推理服务（dgtf_local_llm/service.py，Qwen2.5-0.5B + LoRA）
  · 127.0.0.1:8773 —— OpenAI 协议适配层（scripts/local_model/openai_shim.py，
    把引擎的 /v1/chat/completions 映射到 8772 的 /generate 并做 stage 路由）

旧版 App 只 watch 8772；8773 没有任何进程管理。实测 8773 死掉后整条本地链断路：
引擎 circuit breaker 全开、llm_calls=0，四层自动调度白跑 —— 而 App 的 /api/health
和侧栏仍显示「正常」。⇒ 缺的不是某段代码，是「本地链路是否活着」这个**读数本身**。

本模块职责（纯标准库；server.py 只做接线，改动可整块回滚）
--------------------------------------------------------
1. ChainWatchdog：两段服务纳入**同一**守护；失败 N 次后按**指数退避**重启；
   日志**节流**（状态迁移必记，重复失败每窗口最多一行）；可显式关（off）。
2. health_snapshot()：给 /api/health 的动态读数。读不到给 null + 原因；
   探测**有界**（0.6s/段、两段并行）+ 缓存（8s），不拖死 health。
3. LOCAL_PRESET_OVERRIDES / build_local_preset_text()：
   「本地模型-全链路」可选预设（configs/本地模型-全链路.yaml）的唯一生成源。
   预设从**出厂** dgtf_config.yaml 起（不吸收用户配置），叠本地覆盖；与
   params.build_temp_config() 对同一批覆盖的语义一致（判据对账）。

红线遵守
--------
「没有读数就不假装有」：所有 null/False 都带原因（reasons），不写 0 冒充读数；
「失败留痕」：状态迁移与重启尝试写 outputs/_lead_audit/local_chain_watchdog.log。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
VENV_PY = ROOT / "local_model" / "envs" / "dgtf_llm_env" / "Scripts" / "python.exe"
SERVICE_SCRIPT = ROOT / "dgtf_local_llm" / "service.py"
SHIM_SCRIPT = ROOT / "scripts" / "local_model" / "openai_shim.py"
FACTORY_CFG = ROOT / "dgtf_config.yaml"
PRESET_NAME = "本地模型-全链路.yaml"
PRESET_PATH = ROOT / "configs" / PRESET_NAME
WATCHDOG_LOG = ROOT / "outputs" / "_lead_audit" / "local_chain_watchdog.log"

#: 显式开关（默认 auto）：auto = 首次读数后按需守护（与旧行为同节奏）；
#: on = App 启动即守护；off = 显式关闭守护（**读数仍然可用**，只是不重启进程）。
ENV_MODE = "DGTF_APP_LOCAL_CHAIN_WATCHDOG"
ENV_SERVICE_URL = "DGTF_APP_LOCAL_SERVICE_URL"
ENV_SHIM_URL = "DGTF_APP_LOCAL_SHIM_URL"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8772"
DEFAULT_SHIM_URL = "http://127.0.0.1:8773"
#: 预设里的端点**写死字面量**（不用环境变量）：commit 进去的是可复现的档，
#: 运行期端口覆盖只走 ENV_SERVICE_URL / ENV_SHIM_URL，别让环境变量污染产物。
PRESET_BASE_URL = "http://127.0.0.1:8773/v1"

VALID_MODES = ("auto", "on", "off")
_MODE_ALIASES = {
    "": "auto", "auto": "auto", "default": "auto", "lazy": "auto",
    "1": "on", "on": "on", "true": "on", "yes": "on",
    "enable": "on", "enabled": "on", "force": "on", "start": "on",
    "0": "off", "off": "off", "false": "off", "no": "off",
    "disable": "off", "disabled": "off", "none": "off", "stop": "off",
}

# 探测/缓存/退避参数（判据里可注入覆盖，不要写死在函数体里）
#: ★ 1.2s（旧 watchdog 同值）：8772 在 GPU 忙/模型加载时 /health 偶发 0.3~1s
#:   才回，0.6s 会把「忙」误读成「死」⇒ 假掉线 + 白重启一次（实测）。
PROBE_TIMEOUT = 1.2
HEALTH_MAX_AGE = 8.0
TICK_INTERVAL = 30.0
FAILURE_THRESHOLD = 2
BACKOFF_SECONDS = (120.0, 300.0, 600.0, 900.0, 1800.0)
LOG_MIN_INTERVAL = 60.0
#: 「可达但未就绪」的状态词：进程活着、只是还在加载（8772 模型后台加载中）。
#: 这种状态**不累计失败、不触发重启** —— 重启只会多起一个抢显存的进程。
PENDING_STATUSES = ("loading",)


# ── 模式 ─────────────────────────────────────────────────────────
def resolve_mode(raw=None) -> str:
    """把 CLI/env 的原始值归一成 auto/on/off（未知值按 auto，保持旧行为）。"""
    if raw is None:
        raw = os.environ.get(ENV_MODE, "")
    key = str(raw or "").strip().lower()
    return _MODE_ALIASES.get(key, "auto")


# ── 端点分类（本地档 vs 云档）─────────────────────────────────────
def classify_endpoint(base_url) -> str:
    """api.base_url → local / cloud / unknown（回环地址算本地）。"""
    raw = str(base_url or "").strip()
    if not raw:
        return "unknown"
    try:
        u = urllib.parse.urlsplit(raw)
        host = (u.hostname or "").lower()
        if not host:                      # 允许 "127.0.0.1:8773/v1" 这种无 scheme 写法
            u = urllib.parse.urlsplit("//" + raw)
            host = (u.hostname or "").lower()
    except Exception:  # noqa: BLE001
        return "unknown"
    if not host:
        return "unknown"
    if host in ("127.0.0.1", "localhost", "::1") or host.startswith("127."):
        return "local"
    return "cloud"


# ── 单次探测 ─────────────────────────────────────────────────────
def _port_of(url: str, default: int) -> int:
    try:
        u = urllib.parse.urlsplit(str(url))
        return int(u.port or default)
    except Exception:  # noqa: BLE001
        return int(default)


def _int_or_none(v):
    """读数穿透：bool 不算数（True 会被 int 成 1，那是假读数）。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def probe(url: str, path: str = "/health", timeout: float = PROBE_TIMEOUT) -> dict:
    """探一个端点，**不抛异常**。返回统一结构（ok/status/data/error/延迟）。"""
    full = str(url or "").rstrip("/") + str(path or "/health")
    out = {"ok": False, "reachable": False, "http_status": None,
           "status": None, "data": None, "error": "", "latency_ms": None,
           "url": full, "checked_at": time.time()}
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(full, timeout=float(timeout)) as resp:
            raw = resp.read(65536)
            out["http_status"] = int(getattr(resp, "status", 200) or 200)
        out["latency_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        out["reachable"] = True              # 端口通了 ⇒ 进程活着（不一定就绪）
    except urllib.error.HTTPError as exc:    # 有 HTTP 响应：进程活着，只是状态码不对
        out["reachable"] = True
        out["http_status"] = int(getattr(exc, "code", 0) or 0)
        out["error"] = "HTTP %s: %s" % (out["http_status"], exc)
        return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
        return out
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        data = {"_unparsed": raw[:200].decode("utf-8", "replace")}
    if not isinstance(data, dict):
        data = {"_value": data}
    out["data"] = data
    status = str(data.get("status") or data.get("state")
                 or data.get("shim") or "").strip()
    out["status"] = status or None
    # 就绪口径：显式 ok=true，或状态词命中就绪集合。**loading 不算就绪**：
    # 8772 模型还在后台加载时 status=loading，此时整条链"活着但还不能用"，
    # 读数必须能区分（否则又会把「没准备好」报成「好了」）。
    out["ok"] = bool(data.get("ok")) or status.lower() in (
        "ready", "ok", "healthy", "running", "up")
    return out


def service_reading(result: dict) -> dict:
    """从 8772 /health 响应里取 App 需要的读数（取不到就是 None，不补 0）。"""
    d = (result or {}).get("data") or {}
    return {
        "service_status": (result or {}).get("status"),
        "service_queue_depth": _int_or_none(d.get("queue_depth")),
        "service_gpu_mem_mb": _int_or_none(d.get("gpu_mem_mb")),
        "service_model": str(d.get("model") or "") or None,
        "service_adapters": (d.get("adapters")
                             if isinstance(d.get("adapters"), dict) else None),
        "service_uptime_sec": (float(d["uptime_sec"])
                               if isinstance(d.get("uptime_sec"), (int, float))
                               else None),
    }


def shim_reading(result: dict) -> dict:
    """从 8773 /health 响应里取读数（stage 通道计数是 shim 的独有读数）。"""
    d = (result or {}).get("data") or {}
    return {
        "shim_status": (result or {}).get("status"),
        "shim_upstream": str(d.get("upstream") or "") or None,
        "shim_stage_channel": (d.get("stage_channel")
                               if isinstance(d.get("stage_channel"), dict) else None),
    }


# ── 两段服务的启动命令 / 目标规格 ────────────────────────────────
def _child_env() -> dict:
    """子进程环境：与 scripts/local_model/start_local_llm.ps1 对齐（离线可跑）。"""
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    return env


def service_url() -> str:
    return (os.environ.get(ENV_SERVICE_URL) or DEFAULT_SERVICE_URL).strip()


def shim_url() -> str:
    return (os.environ.get(ENV_SHIM_URL) or DEFAULT_SHIM_URL).strip()


def service_start_cmd():
    """8772 启动命令：venv python -m dgtf_local_llm.service --port 8772。

    ★ 必须用 -m：service.py 里有 from dgtf_local_llm.gates import ...，
      直跑脚本时 sys.path[0] 是 dgtf_local_llm/ 目录，顶层包 import 会失败
      （旧 watchdog 就是直跑 —— 那条自愈路径其实从来没成功过）。当前实例
      也是 -m 起的，口径一致。
    """
    if not (VENV_PY.is_file() and SERVICE_SCRIPT.is_file()):
        return None
    return [str(VENV_PY), "-m", "dgtf_local_llm.service",
            "--port", str(_port_of(service_url(), 8772))]


def shim_start_cmd():
    """8773 启动命令：<App 的 python> scripts/local_model/openai_shim.py。

    适配层只用标准库 + dgtf_local_llm.gates（无 torch），所以用 App 自己的
    Python 即可，不必占训练 venv —— 与当前实例的启动方式一致。
    """
    if not SHIM_SCRIPT.is_file():
        return None
    return [str(sys.executable or "python"), str(SHIM_SCRIPT),
            "--port", str(_port_of(shim_url(), 8773)),
            "--upstream", service_url()]


def default_targets() -> list:
    """两段服务的守护目标（服务在前：8772 没起来时先等它）。"""
    return [
        {"name": "service", "label": "本地推理服务(8772)", "kind": "service",
         "url": service_url(), "path": "/health",
         "start_cmd": service_start_cmd()},
        {"name": "shim", "label": "OpenAI 适配层(8773)", "kind": "shim",
         "url": shim_url(), "path": "/health",
         "start_cmd": shim_start_cmd()},
    ]


# ── 守护状态机 ──────────────────────────────────────────────────
class ChainWatchdog:
    """两段本地服务的守护状态机（可注入时钟/探针/启动器 ⇒ 可构造性单测）。

    ★ 状态机只做三件事：探活、计数、按退避重启。**不碰配置、不碰任务**，
      所以「云档默认行为不变」是结构保证：无论守护怎么动，云档的
      api.base_url 都不会被改写。
    """

    def __init__(self, targets=None, *, mode="auto", clock=None, probe_fn=None,
                 start_fn=None, log_path=None, log_fn=None,
                 tick_interval: float = TICK_INTERVAL,
                 failure_threshold: int = FAILURE_THRESHOLD,
                 backoff=BACKOFF_SECONDS,
                 log_min_interval=None):
        self.targets = [dict(t) for t in (targets if targets is not None
                                          else default_targets())]
        self.mode = resolve_mode(mode)
        self.tick_interval = float(tick_interval)
        self.failure_threshold = max(1, int(failure_threshold))
        self.backoff = tuple(float(x) for x in (backoff or ())) or (120.0,)
        # ★ 默认值在**运行期**读模块常量（不在 def 行绑定）：
        #   判据要把「节流」当变异体关掉，绑死在签名里就改不动、测不出来。
        self.log_min_interval = float(LOG_MIN_INTERVAL if log_min_interval is None
                                      else log_min_interval)
        self._clock = clock or time.time
        self._probe_fn = probe_fn or (lambda t: probe(
            t.get("url") or "", t.get("path") or "/health", PROBE_TIMEOUT))
        self._start_fn = start_fn
        self._log_fn = log_fn
        self._log_path = Path(log_path) if log_path else WATCHDOG_LOG
        self._lock = threading.RLock()
        self._ticks = 0
        self._last_tick = 0.0
        self._log_last = {}
        self._log_suppressed = {}
        self._spawn_errors = 0
        self.states = {}
        for t in self.targets:
            self.states[t["name"]] = {
                "name": t["name"], "ok": None, "reachable": False,
                "status": None, "error": "",
                "checked_at": 0.0, "failures": 0, "starts": 0,
                "last_start": 0.0, "next_start_at": 0.0, "backoff_idx": 0,
                "readings": {},
            }

    # ── 日志（节流）──
    def _log(self, msg: str, *, dedupe: str = "", throttle: bool = False) -> None:
        now = self._clock()
        if throttle and dedupe:
            last = self._log_last.get(dedupe)
            if last is not None and (now - float(last)) < self.log_min_interval:
                self._log_suppressed[dedupe] = \
                    self._log_suppressed.get(dedupe, 0) + 1
                return
            extra = int(self._log_suppressed.pop(dedupe, 0) or 0)
            if extra:
                msg += "（期间抑制 %d 条重复）" % extra
            self._log_last[dedupe] = now
        line = "[%s] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), msg)
        if self._log_fn is not None:
            try:
                self._log_fn(line)
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(line)
        except OSError:
            pass

    # ── 探针 / 启动 ──
    def _probe_one(self, target: dict) -> dict:
        try:
            res = self._probe_fn(target)
            return res if isinstance(res, dict) else {
                "ok": False, "status": None, "data": None,
                "error": "probe 返回非 dict: %r" % (type(res).__name__,)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": None, "data": None,
                    "error": "%s: %s" % (type(exc).__name__, exc)}

    def _spawn(self, target: dict) -> bool:
        cmd = target.get("start_cmd")
        if not cmd:
            return False
        try:
            flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) \
                if os.name == "nt" else 0
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write("[%s] spawn: %s\n" % (
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    " ".join(str(x) for x in cmd)))
                subprocess.Popen([str(x) for x in cmd], cwd=str(ROOT),
                                 stdout=fh, stderr=fh, creationflags=flags,
                                 env=_child_env())
            return True
        except Exception as exc:  # noqa: BLE001
            self._spawn_errors += 1
            self._log("启动失败 %s：%s: %s" % (
                target.get("label") or target.get("name"),
                type(exc).__name__, exc), dedupe="spawn:" + target["name"],
                throttle=True)
            return False

    def _start_target(self, target: dict, st: dict, now: float) -> bool:
        st["starts"] += 1
        st["last_start"] = now
        idx = int(st.get("backoff_idx") or 0)
        delay = self.backoff[min(idx, len(self.backoff) - 1)]
        st["next_start_at"] = now + delay
        st["backoff_idx"] = min(idx + 1, len(self.backoff) - 1)
        self._log("重启 %s（第 %d 次；退避 %ds 内不再试）"
                  % (target.get("label") or target.get("name"),
                     int(st["starts"]), int(delay)),
                  dedupe="start:" + target["name"], throttle=False)
        if self._start_fn is not None:
            try:
                return bool(self._start_fn(target, st, now))
            except Exception:  # noqa: BLE001
                return False
        return bool(self._spawn(target))

    # ── 状态更新 ──
    def _apply(self, target: dict, result: dict, now: float,
               events: list) -> None:
        st = self.states[target["name"]]
        prev = st.get("ok")
        ok = bool((result or {}).get("ok"))
        reachable = result.get("reachable")
        if reachable is None:                # 注入的探针没给：按「有没有 data」推
            reachable = bool((result or {}).get("data")) or (
                (result or {}).get("http_status") is not None)
        st["ok"] = ok
        st["reachable"] = bool(reachable)
        st["status"] = (result or {}).get("status")
        st["error"] = "" if ok else str((result or {}).get("error") or "")
        st["checked_at"] = now
        kind = target.get("kind") or target.get("name")
        st["readings"] = (service_reading(result) if kind == "service"
                          else shim_reading(result))
        if ok:
            if prev is False:
                self._log("恢复 %s（status=%s）"
                          % (target.get("label") or target["name"],
                             st.get("status")), dedupe="recover:" + target["name"])
                events.append({"event": "recovered", "target": target["name"],
                               "at": now})
            st["failures"] = 0
            st["backoff_idx"] = 0
            st["next_start_at"] = 0.0
            return
        # ★ 「可达但未就绪」（典型：8772 模型后台加载中 status=loading）
        #    ≠ 掉线：进程活着，重启只会多起一个抢 GPU 的进程。
        #   这种状态不累计 failures、不触发重启，只把读数如实报成未就绪。
        if st["reachable"] and str(st.get("status") or "").strip().lower() \
                in PENDING_STATUSES:
            st["failures"] = 0
            st["next_start_at"] = 0.0
            if prev is not False:
                self._log("未就绪 %s（status=%r，进程可达，不重启）"
                          % (target.get("label") or target["name"],
                             st.get("status")),
                          dedupe="pending:" + target["name"])
            return
        st["failures"] = int(st.get("failures") or 0) + 1
        if prev is not False:            # None(首探) 或 True(掉线) 都要留痕一次
            self._log("掉线 %s（failures=%d status=%r error=%s）"
                      % (target.get("label") or target["name"], st["failures"],
                         st.get("status"), (st.get("error") or "")[:160]),
                      dedupe="down:" + target["name"])
            events.append({"event": "down", "target": target["name"], "at": now})
        else:
            self._log("仍不可用 %s（failures=%d status=%r）"
                      % (target.get("label") or target["name"],
                         st["failures"], st.get("status")),
                      dedupe="down:" + target["name"], throttle=True)

    def tick(self, now=None) -> list:
        """守护一轮：探两段 → 计数 → 达到阈值且退避到期就重启。返回事件列表。"""
        now = self._clock() if now is None else float(now)
        events: list = []
        with self._lock:
            self._ticks += 1
            self._last_tick = now
            if self.mode == "off":
                return events          # 显式关闭：不探不启（读数走 refresh）
            for target in self.targets:
                res = self._probe_one(target)
                self._apply(target, res, now, events)
                st = self.states[target["name"]]
                # 只有「硬掉线」（连不上/无响应）才重启；loading 等未就绪不动进程。
                if (not st["ok"]) and (not st["reachable"]) \
                        and st["failures"] >= self.failure_threshold \
                        and target.get("start_cmd") and now >= st["next_start_at"]:
                    started = self._start_target(target, st, now)
                    events.append({"event": "restart", "target": target["name"],
                                   "at": now, "started": bool(started)})
        return events

    # ── 并行探测（health 用；有界，不拖死调用方）──
    def _probe_all(self, timeout: float) -> dict:
        results: dict = {}

        def _one(t):
            results[t["name"]] = self._probe_one(t)

        threads = []
        for t in self.targets:
            th = threading.Thread(target=_one, args=(t,), daemon=True,
                                  name="local-chain-probe-" + str(t["name"]))
            th.start()
            threads.append(th)
        deadline = time.monotonic() + float(timeout) + 0.6
        for th in threads:
            th.join(max(0.0, deadline - time.monotonic()))
        return results

    def refresh(self, *, force: bool = False, max_age=None,
                timeout: float = PROBE_TIMEOUT) -> bool:
        """读数缓存：过 max_age 才重探（并行有界）。返回本轮是否真的探了。"""
        with self._lock:
            now = self._clock()
            age_limit = HEALTH_MAX_AGE if max_age is None else float(max_age)
            # ★ 严格小于：max_age=0 表示「强制重探」，否则 age=0 会被当成命中缓存
            fresh = all((now - float(st.get("checked_at") or 0.0)) < age_limit
                        for st in self.states.values())
            if fresh and not force:
                return False
        results = self._probe_all(timeout)
        with self._lock:
            now = self._clock()
            for target in self.targets:
                res = results.get(target["name"])
                if res is None:
                    res = {"ok": False, "reachable": False, "status": None,
                           "data": None,
                           "error": "probe_timeout: %.1fs 内未返回（读数暂缺）"
                                    % (float(timeout) + 0.6)}
                self._apply(target, res, now, [])
        return True

    # ── 对外读数 ──
    def _reason(self, st: dict) -> str:
        if st.get("ok") is True:
            return ""
        err = str(st.get("error") or "").strip()
        if err:
            return err
        status = str(st.get("status") or "").strip()
        if status:
            if st.get("reachable") and status.lower() in PENDING_STATUSES:
                return "status=%r 未就绪（进程可达，加载中，不重启）" % status
            return "status=%r 未就绪" % status
        if not st.get("reachable"):
            return "未探测（无读数）"
        return "未就绪（无可解析的状态读数）"

    def health(self, *, engine_path: str = "", engine_version: str = "",
               endpoint_kind: str = "unknown", max_age=None,
               probe_timeout: float = PROBE_TIMEOUT) -> dict:
        """给 /api/health 的本地链路读数（不抛异常；读不到 = null + reason）。"""
        refreshed = False
        try:
            refreshed = self.refresh(max_age=max_age, timeout=probe_timeout)
        except Exception:  # noqa: BLE001  读数失败不能拖垮 health
            refreshed = False
        with self._lock:
            now = self._clock()
            sts = {name: dict(st) for name, st in self.states.items()}
            sts_r = {name: dict(st.get("readings") or {})
                     for name, st in self.states.items()}
            targets = {t["name"]: dict(t) for t in self.targets}
            ticks, last_tick = self._ticks, self._last_tick
            mode = self.mode
            backoff = list(self.backoff)
        svc = sts.get("service") or {}
        shim = sts.get("shim") or {}
        sv = sts_r.get("service") or {}
        sh = sts_r.get("shim") or {}
        checked = [float(st.get("checked_at") or 0.0) for st in sts.values()
                   if st.get("checked_at")]
        both = [svc.get("ok"), shim.get("ok")]
        ok = (True if both == [True, True]
              else False if all(x is not None for x in both) else None)
        reasons = {}
        for name in ("service", "shim"):
            reason = self._reason(sts.get(name) or {})
            if reason:
                reasons[name] = reason
        next_restart_in = {}
        restarts = {}
        failures = {}
        for name, st in sts.items():
            restarts[name] = int(st.get("starts") or 0)
            failures[name] = int(st.get("failures") or 0)
            nxt = float(st.get("next_start_at") or 0.0)
            next_restart_in[name] = (round(max(0.0, nxt - now), 1)
                                     if nxt > now else 0.0)
        return {
            # ── 读数口径：endpoint_kind 由调用方按 effective 配置传进来 ──
            "endpoint_kind": str(endpoint_kind or "unknown"),
            "ok": ok,
            "service_ok": svc.get("ok"),
            "shim_ok": shim.get("ok"),
            "service_reachable": svc.get("reachable"),
            "shim_reachable": shim.get("reachable"),
            "service_status": sv.get("service_status"),
            "service_queue_depth": sv.get("service_queue_depth"),
            "service_gpu_mem_mb": sv.get("service_gpu_mem_mb"),
            "service_model": sv.get("service_model"),
            "service_adapters": sv.get("service_adapters"),
            "shim_status": sh.get("shim_status"),
            "shim_upstream": sh.get("shim_upstream"),
            "shim_stage_channel": sh.get("shim_stage_channel"),
            "engine_path": str(engine_path or ""),
            "engine_version": str(engine_version or ""),
            "checked_at": (max(checked) if checked else None),
            "age_sec": (round(now - max(checked), 1) if checked else None),
            # ── 读不到就点名的原因（「没有读数就不假装有」）──
            "reasons": reasons,
            "probe": {"on_demand": bool(refreshed),
                      "timeout_sec": float(probe_timeout),
                      "max_age_sec": float(HEALTH_MAX_AGE if max_age is None
                                           else max_age)},
            "watchdog": {
                "mode": mode, "enabled": mode != "off",
                "ticks": int(ticks), "last_tick": last_tick or None,
                "failures": failures, "restarts": restarts,
                "next_restart_in": next_restart_in,
                "backoff_seconds": backoff,
                "restart_capable": {name: bool(targets.get(name, {}).get("start_cmd"))
                                    for name in sts},
                "log": str(self._log_path),
                "spawn_errors": int(self._spawn_errors),
            },
            "preset": {"name": PRESET_NAME, "path": str(PRESET_PATH),
                       "exists": PRESET_PATH.is_file(),
                       "endpoint": PRESET_BASE_URL},
        }


# ── 模块级单例（server.py 只跟这几个函数打交道）──────────────────
_MODE = {"mode": resolve_mode()}
_WD = None
_WD_THREAD = None
_WD_LOCK = threading.Lock()


def set_mode(mode) -> str:
    """设置守护模式（CLI/env 已在 main() 里解析），返回归一后的模式。"""
    global _WD
    m = resolve_mode(mode)
    _MODE["mode"] = m
    if _WD is not None:
        _WD.mode = m
    return m


def current_mode() -> str:
    return str(_MODE.get("mode") or "auto")


def get_watchdog():
    global _WD
    with _WD_LOCK:
        if _WD is None:
            _WD = ChainWatchdog(mode=_MODE["mode"])
        return _WD


def ensure_watchdog(mode=None) -> bool:
    """确保守护线程在跑；off 模式**不启动**（读数仍可走 health_snapshot）。"""
    global _WD, _WD_THREAD
    m = set_mode(_MODE["mode"] if mode is None else mode)
    if m == "off":
        return False
    with _WD_LOCK:
        wd = _WD or ChainWatchdog(mode=m)
        _WD = wd
        wd.mode = m
        if _WD_THREAD is not None and _WD_THREAD.is_alive():
            return True

        def _loop():
            while True:
                try:
                    wd.tick()
                except Exception:  # noqa: BLE001  单轮失败不能让守护线程死掉
                    pass
                time.sleep(max(5.0, float(wd.tick_interval)))

        _WD_THREAD = threading.Thread(target=_loop, daemon=True,
                                      name="local-chain-watchdog")
        _WD_THREAD.start()
        return True


def reset_for_tests() -> None:
    """测试用：清掉模块级单例与线程标记（不 join 线程——测试进程自行退出）。"""
    global _WD, _WD_THREAD
    with _WD_LOCK:
        _WD = None
        _WD_THREAD = None


def health_snapshot(*, engine_path: str = "", engine_version: str = "",
                    endpoint_kind: str = "unknown", max_age=None,
                    probe_timeout: float = PROBE_TIMEOUT) -> dict:
    """模块级读数入口：给 server.py 的 /api/health 与侧栏用。"""
    wd = get_watchdog()
    wd.mode = _MODE["mode"]
    return wd.health(engine_path=engine_path, engine_version=engine_version,
                     endpoint_kind=endpoint_kind, max_age=max_age,
                     probe_timeout=probe_timeout)


# ── 「本地模型-全链路」预设（唯一生成源）────────────────────────
#: 预设要覆盖的键。**只列"本地档必须不同"的键**：其余全部继承出厂
#: dgtf_config.yaml（本地档应该是"生产默认 × 换本地端点"，不是另一套引擎配置）。
LOCAL_PRESET_OVERRIDES = {
    "api.base_url": PRESET_BASE_URL,     # 引擎 → 8773 适配层 → 8772 推理服务
    "api.key": "local-shim",             # 适配层不校验 key，给个显式占位
    "api.default_model": "local",        # 适配层回显这个 model（不回显会报警别名漂移）
    "api.reasoner_model": "local",
    "api.timeout": 240,                  # 与出厂一致；本地慢，别调小
    "web_search.enabled": False,         # 本地链路验证不联网（零 API 成本）
    "output.save_dir": "outputs/_e2e_local",   # ★ 独立落盘：不污染生产质量统计
    "output.answer_gates.enabled": True,       # 读数照出
    "output.answer_gates.block": False,        # ★ 本地 0.5B 只留痕不阻断
}
#: 判据对账用的必需键（值必须逐项与 LOCAL_PRESET_OVERRIDES 一致）
PRESET_REQUIRED = (
    "api.base_url", "api.key", "api.default_model", "api.reasoner_model",
    "web_search.enabled", "output.save_dir",
    "output.answer_gates.enabled", "output.answer_gates.block",
)

_PRESET_HEADER = (
    "# ============================================================",
    "# Meta-DGTF · 本地模型全链路档（App 可选预设）",
    "# ============================================================",
    "# 链路：App/引擎 → 127.0.0.1:8773（OpenAI 适配层）→ 127.0.0.1:8772（本地推理）",
    "# 用途：零 API 成本跑通 App→引擎→本地模型全链路；读数结构/成本归因回归。",
    "#       ★ 本地 0.5B 的答案质量不能当生产质量看（判的是链路，不是质量）。",
    "#",
    "# ★ 本文件是**生成产物**，不要手改：",
    "#   生成源 = dgtf_app/local_chain.py 的 LOCAL_PRESET_OVERRIDES",
    "#   起点   = 出厂 dgtf_config.yaml（不吸收用户配置）",
    "#   复跑   = python -c \"import sys; sys.path.insert(0,'dgtf_app'); import local_chain; local_chain.write_local_preset()\"",
    "#   判据   = python dgtf_app/test_local_chain.py（含「生成结果与文件逐字相同」）",
    "#",
    "# App 选档方式（既有 preset/config 通道，不新增机制）：",
    "#   POST /api/tasks {\"question\": \"…\", \"opts\": {\"profile\": \"本地模型-全链路.yaml\",",
    "#                    \"route\": \"1\", \"rounds\": \"1\"}}",
    "#   或 POST /api/schedule/preview {\"question\": \"…\", \"profile\": \"本地模型-全链路.yaml\"}",
)


def _set_dotted(root: dict, dotted: str, value) -> None:
    node = root
    parts = str(dotted).split(".")
    for key in parts[:-1]:
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    node[parts[-1]] = value


def flatten(d, prefix: str = "") -> dict:
    """扁平化（与 params._flatten 同口径；本模块不 import params，保持可独立单测）。"""
    out: dict = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = "%s%s" % (prefix, k)
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def build_local_preset_text() -> str:
    """生成预设全文（确定性的：同一份出厂 yaml + 同一批覆盖 ⇒ 逐字相同）。

    ★ 起点用**出厂** dgtf_config.yaml 而不是 params.effective_flat()：
      commit 进仓库的档不能被某台机器的用户配置（dgtf_config.user.yaml）污染。
      「与 build_temp_config 覆盖语义一致」由 test_local_chain.py 对账。
    """
    import yaml
    if not FACTORY_CFG.is_file():
        raise FileNotFoundError("找不到出厂配置：%s" % FACTORY_CFG)
    raw = yaml.safe_load(FACTORY_CFG.read_text(encoding="utf-8",
                                               errors="replace")) or {}
    if not isinstance(raw, dict):
        raise ValueError("出厂配置顶层不是 mapping：%s" % FACTORY_CFG)
    for key, value in LOCAL_PRESET_OVERRIDES.items():
        _set_dotted(raw, key, value)
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=100000)
    text = "\n".join(_PRESET_HEADER) + "\n" + body
    # 生成即校验：本地档里不许残留云端点/密钥字样（有牙：写回云端点会当场炸）
    low = text.lower()
    for bad in ("api.deepseek.com", "sk-"):
        if bad in low:
            raise ValueError("本地档生成结果残留 %r，拒绝落盘" % bad)
    return text


def write_local_preset(path=None) -> str:
    """把预设写到 configs/（默认路径），返回文件路径。"""
    p = Path(path) if path else PRESET_PATH
    text = build_local_preset_text()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return str(p)


def read_preset_flat() -> dict:
    """读预设并扁平化（文件不存在返回 {}，不抛）。"""
    import yaml
    try:
        raw = yaml.safe_load(PRESET_PATH.read_text(encoding="utf-8",
                                                   errors="replace")) or {}
    except (OSError, ValueError):
        return {}
    return flatten(raw) if isinstance(raw, dict) else {}
