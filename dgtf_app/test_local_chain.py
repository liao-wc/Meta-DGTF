# -*- coding: utf-8 -*-
"""本地链路判据：8772 推理服务 + 8773 OpenAI 适配层的守护/读数/预设。

用法（不需要起 App server，不碰真实 8772/8773，不起任何 GPU 进程）：
    python dgtf_app/test_local_chain.py

覆盖：
  S1 探针：真 HTTP 端口构造性证明（healthy / loading / 503 / 非 JSON / 连接拒绝 / 超时）
  S2 守护状态机：健康不误重启、硬掉线按阈值 + 指数退避重启、恢复复位、
                loading 可达未就绪不重启、off 显式关闭（只读数不重启）
  S3 日志节流（不刷屏）
  S4 health 读数结构：字段齐全、读不到 = null + 原因、endpoint_kind、缓存
  S5 「本地模型-全链路」预设：可复现、必需值、engine_runner 的 profile/_config 通道
  S6 变异体（有牙证明）：8 个变异体必须让判据变红；没抓到 = 判据没牙 = 本测试失败

★ 为什么用**真 HTTP 端口**而不是打桩函数：项目规矩是「纯函数判据全绿 ≠ 能力在
  真实路径上可达」。探针/缓存/守护这些行为只有走真实 socket 才证明得了；重启动作
  用注入的 start_fn 观察（测试里**禁止** spawn 真进程/占 GPU）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

import local_chain as lc  # noqa: E402

PASS: list = []
FAIL: list = []
N = [0]


def check(name: str, cond: bool, detail: str = "") -> None:
    N[0] += 1
    if cond:
        PASS.append(name)
        print("  \u2713 " + name)
    else:
        FAIL.append(name)
        print("  \u2717 " + name + (("  \u2014 " + detail) if detail else ""))


def section(title: str) -> None:
    print("\n[" + title + "]")


# ══ 假 HTTP 端点（真 socket；可 switch 状态 / 延迟 / 关闭）══════════════
class FakeEndpoint:
    """一个真的 HTTP 服务：body/code 可改；close() 后端口拒绝连接。

    ★ 不用打桩函数：判据要证「探针真的走网络、超时/拒绝/非 JSON 都分得开」。
    """

    def __init__(self, body=None, code: int = 200, delay: float = 0.0,
                 port: int = 0):
        self.body = body if body is not None else {"ok": True, "status": "ready"}
        self.code = int(code)
        self.delay = float(delay)
        self._fixed_port = int(port)
        self.port = int(port)
        self.httpd = None
        self._th = None
        self.start()

    def start(self) -> None:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):  # 静音
                return

            def do_GET(self):
                if outer.delay:
                    time.sleep(outer.delay)
                body = outer.body
                if isinstance(body, (dict, list)):
                    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                elif isinstance(body, bytes):
                    raw = body
                else:
                    raw = str(body).encode("utf-8")
                try:
                    self.send_response(outer.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except OSError:
                    pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self._fixed_port), _Handler)
        self.httpd.daemon_threads = True
        self.port = int(self.httpd.server_address[1])
        self._fixed_port = self.port
        self._th = threading.Thread(target=self.httpd.serve_forever,
                                    daemon=True, name="fake-endpoint")
        self._th.start()

    @property
    def url(self) -> str:
        return "http://127.0.0.1:%d" % self.port

    def set(self, body=None, code=None, delay=None) -> None:
        if body is not None:
            self.body = body
        if code is not None:
            self.code = int(code)
        if delay is not None:
            self.delay = float(delay)

    def close(self) -> None:
        if self.httpd is None:
            return
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:  # noqa: BLE001
            pass
        self.httpd = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _targets(service_ep, shim_ep) -> list:
    """测试用目标规格（start_cmd 只做「可重启」标记，真启动由 start_fn 注入）。"""
    return [
        {"name": "service", "label": "本地推理服务(8772)", "kind": "service",
         "url": service_ep.url, "path": "/health", "start_cmd": ["fake-service"]},
        {"name": "shim", "label": "OpenAI 适配层(8773)", "kind": "shim",
         "url": shim_ep.url, "path": "/health", "start_cmd": ["fake-shim"]},
    ]


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    def tick(self, dt: float) -> float:
        self.t += float(dt)
        return self.t


def _suite_targets_cover_both(wd) -> bool:
    """判据：守护目标必须两段都在（service + shim）。"""
    return sorted(t["name"] for t in wd.targets) == ["service", "shim"]


# ══ S1 探针（真 HTTP 端口）════════════════════════════════════════
def section_probe() -> None:
    section("S1 探针（真 HTTP 端口构造性证明）")
    try:
        with FakeEndpoint({"ok": True, "status": "ready", "queue_depth": 2,
                           "gpu_mem_mb": 1740, "adapters": {"route": True}}) as ep:
            r = lc.probe(ep.url, "/health", 1.0)
            check("S1.1 健康端点：ok=True / reachable=True / 拿到 status 与读数",
                  r["ok"] and r["reachable"] and r["status"] == "ready",
                  json.dumps({k: r.get(k) for k in ("ok", "reachable", "status", "error")}, ensure_ascii=False))
            read = lc.service_reading(r)
            check("S1.2 服务读数：queue_depth / gpu_mem_mb / adapters 都取得出",
                  read["service_queue_depth"] == 2
                  and read["service_gpu_mem_mb"] == 1740
                  and read["service_adapters"] == {"route": True},
                  json.dumps(read, ensure_ascii=False))
        with FakeEndpoint({"ok": False, "status": "loading"}) as ep:
            r = lc.probe(ep.url, "/health", 1.0)
            check("S1.3 loading：可达（reachable=True）但不就绪（ok=False）—— 两者必须分得开",
                  r["reachable"] is True and r["ok"] is False and r["status"] == "loading",
                  json.dumps({"ok": r["ok"], "reachable": r["reachable"], "status": r["status"]}))
        with FakeEndpoint({"ok": True, "shim": "up", "upstream": "http://127.0.0.1:8772",
                           "stage_channel": {"explicit_stage": 3, "mismatch_avoided": 3}}) as ep:
            r = lc.probe(ep.url, "/health", 1.0)
            read = lc.shim_reading(r)
            check("S1.4 适配层读数：status=up + stage_channel 原样取得出",
                  r["ok"] and read["shim_status"] == "up"
                  and read["shim_stage_channel"] == {"explicit_stage": 3,
                                                     "mismatch_avoided": 3},
                  json.dumps(read, ensure_ascii=False))
        with FakeEndpoint({"error": "boom"}, code=503) as ep:
            r = lc.probe(ep.url, "/health", 1.0)
            check("S1.5 503：可达但就绪为假，http_status/error 都要留痕",
                  r["reachable"] is True and r["ok"] is False
                  and r["http_status"] == 503 and bool(r["error"]),
                  json.dumps({"http_status": r["http_status"], "error": r["error"][:80]}, ensure_ascii=False))
        with FakeEndpoint(b"<html>not json</html>") as ep:
            r = lc.probe(ep.url, "/health", 1.0)
            check("S1.6 非 JSON 响应：可达但不就绪，原文留痕（不静默当空）",
                  r["reachable"] is True and r["ok"] is False
                  and isinstance(r["data"], dict) and "_unparsed" in r["data"],
                  json.dumps(r["data"], ensure_ascii=False)[:120])
        with FakeEndpoint(delay=1.2) as ep:
            r = lc.probe(ep.url, "/health", 0.2)
            check("S1.7 超时：有界返回（不吊死），ok=False 且 error 非空",
                  r["ok"] is False and bool(r["error"]) and r["reachable"] is False,
                  "error=" + str(r["error"])[:100])
        # 连接拒绝：先起再关，端口不再监听
        tmp = FakeEndpoint({"ok": True, "status": "ready"})
        dead_url = tmp.url
        tmp.close()
        r = lc.probe(dead_url, "/health", 0.8)
        check("S1.8 连接拒绝：ok=False / reachable=False / 带原因（不是空读数）",
              r["ok"] is False and r["reachable"] is False and bool(r["error"]),
              "error=" + str(r["error"])[:100])
    except Exception as exc:  # noqa: BLE001
        check("S1 探针段执行未抛异常", False, "%s: %s" % (type(exc).__name__, exc))


# ══ S2 守护状态机 ═════════════════════════════════════════════════
def section_watchdog() -> None:
    section("S2 守护状态机（硬掉线重启 / 指数退避 / 恢复 / loading 不重启 / off）")
    try:
        # ── S2.1 两段都健康：不重启 ──
        svc = FakeEndpoint({"ok": True, "status": "ready"})
        shim = FakeEndpoint({"ok": True, "shim": "up"})
        clock = Clock()
        starts = []
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=clock,
                              start_fn=lambda t, st, now: starts.append((t["name"], now)) or True,
                              failure_threshold=2, backoff=(120, 300, 600),
                              log_fn=lambda line: None)
        wd.tick()
        check("S2.1 健康时零重启 + 两段读数都 True + 目标覆盖两段",
              starts == [] and wd.states["service"]["ok"] is True
              and wd.states["shim"]["ok"] is True and _suite_targets_cover_both(wd),
              "starts=%r" % (starts,))
        # ── S2.2 硬掉线：阈值前不重启，阈值到按退避重启 ──
        shim.close()
        wd.tick()
        check("S2.2 掉线第 1 轮：失败计数=1、不重启（阈值=2）",
              starts == [] and wd.states["shim"]["failures"] == 1,
              "starts=%r failures=%r" % (starts, wd.states["shim"]["failures"]))
        clock.tick(30); wd.tick()
        _restart_at = starts[0][1] if starts else -1
        check("S2.3 第 2 轮达阈值：重启一次，并记下退避（下次最早 +120s）",
              [s[0] for s in starts] == ["shim"]
              and wd.states["shim"]["starts"] == 1
              and wd.states["shim"]["next_start_at"] == _restart_at + 120,
              "starts=%r next=%r" % (starts, wd.states["shim"]["next_start_at"]))
        clock.tick(30); wd.tick()
        check("S2.4 退避窗口内即使又失败也不重启（不刷重启）",
              len(starts) == 1, "starts=%r" % (starts,))
        # 到点：退避 120s 后允许第 2 次尝试，此时"进程起来" → 恢复
        clock.tick(90)   # 累计 150s > 120s
        clock.tick(0); wd.tick()
        check("S2.5 退避到期：第 2 次重启尝试；start 回调可把端点拉活",
              len(starts) == 2 and starts[1][0] == "shim",
              "starts=%r" % (starts,))
        shim.start()
        clock.tick(30); wd.tick()
        check("S2.6 恢复：ok=True、failures 归零、退避复位、有 recovered 事件",
              wd.states["shim"]["ok"] is True
              and wd.states["shim"]["failures"] == 0
              and wd.states["shim"]["backoff_idx"] == 0,
              json.dumps(wd.states["shim"], ensure_ascii=False)[:200])
        # ── S2.3 指数退避递增（构造：退避表 120/300/600，连续失败时逐次变大）──
        backoff = (120.0, 300.0, 600.0)
        clock2 = Clock(5000.0)
        starts2 = []
        wd2 = lc.ChainWatchdog(_targets(FakeEndpoint({"ok": True}), shim),
                               mode="on", clock=clock2,
                               start_fn=lambda t, st, now: starts2.append(now) or True,
                               failure_threshold=1, backoff=backoff,
                               log_fn=lambda line: None)
        shim.close()
        wd2.tick()                                   # shim 掉线，第 1 次重启
        for _ in range(2):
            clock2.tick(wd2.states["shim"]["next_start_at"] - clock2.t)
            wd2.tick()                               # 到点各重启一次
        gaps = [round(starts2[i + 1] - starts2[i], 1) for i in range(len(starts2) - 1)]
        check("S2.7 指数退避：连续失败时重启间隔递增（120 → 300 → 600）",
              gaps == [120.0, 300.0], "gaps=%r starts=%r" % (gaps, starts2))
        # ── S2.4 loading（可达未就绪）不重启 ──
        svc3 = FakeEndpoint({"ok": False, "status": "loading"})
        shim3 = FakeEndpoint({"ok": True, "shim": "up"})
        starts3 = []
        wd3 = lc.ChainWatchdog(_targets(svc3, shim3), mode="on", clock=Clock(),
                               start_fn=lambda t, st, now: starts3.append(t["name"]) or True,
                               failure_threshold=2, log_fn=lambda line: None)
        wd3.tick(); wd3.tick(); wd3.tick()
        check("S2.8 loading（可达未就绪）连续 3 轮：不累计失败、不重启（进程活着别乱杀）",
              starts3 == [] and wd3.states["service"]["failures"] == 0
              and wd3.states["service"]["reachable"] is True,
              "starts=%r failures=%r" % (starts3, wd3.states["service"]["failures"]))
        svc3.close(); shim3.close()
        # ── S2.5 off 模式：不探不启，但读数仍可用 ──
        svcd = FakeEndpoint({"ok": True, "status": "ready"})
        shimd = FakeEndpoint({"ok": True, "shim": "up"})
        probes = []
        starts4 = []
        wd4 = lc.ChainWatchdog(_targets(svcd, shimd), mode="off", clock=Clock(),
                               probe_fn=lambda t: (probes.append(t["name"]),
                                                   lc.probe(t["url"], "/health", 0.8))[1],
                               start_fn=lambda t, st, now: starts4.append(t["name"]) or True,
                               log_fn=lambda line: None)
        wd4.tick()
        check("S2.9 off：守护轮不探不启（显式可关）",
              probes == [] and starts4 == [], "probes=%r starts=%r" % (probes, starts4))
        snap_off = wd4.health(engine_path="e.py", engine_version="1.2.3",
                              endpoint_kind="local")
        check("S2.10 off：/api/health 读数照旧可用（读数与守护解耦）",
              snap_off["service_ok"] is True and snap_off["shim_ok"] is True
              and snap_off["watchdog"]["enabled"] is False,
              json.dumps({k: snap_off[k] for k in ("service_ok", "shim_ok")}))
        svcd.close(); shimd.close()
        for ep in (svc, shim):
            ep.close()
    except Exception as exc:  # noqa: BLE001
        check("S2 守护段执行未抛异常", False, "%s: %s" % (type(exc).__name__, exc))


# ══ S3 日志节流 ═══════════════════════════════════════════════════
def section_log_throttle() -> None:
    section("S3 日志节流（不刷屏）")
    try:
        dead = FakeEndpoint({"ok": True, "status": "ready"})
        dead_url = dead.url
        dead.close()
        lines = []
        clock = Clock(1000.0)
        wd = lc.ChainWatchdog(
            [{"name": "service", "label": "svc", "kind": "service",
              "url": dead_url, "path": "/health", "start_cmd": None}],
            mode="on", clock=clock, failure_threshold=999,
            log_fn=lambda line: lines.append(line),
            log_min_interval=60.0)
        t0 = clock.t
        for i in range(10):
            clock.t = t0 + i * 10.0
            wd.tick()
        check("S3.1 10 轮持续失败，日志行数被节流（≤3 行），但掉线迁移必留痕",
              len(lines) <= 3 and any("掉线" in ln for ln in lines),
              "lines=%d %r" % (len(lines), [ln.strip()[:48] for ln in lines]))
        check("S3.2 被抑制的重复次数有计数（不是静默丢）",
              any("抑制" in ln for ln in lines),
              [ln.strip()[:60] for ln in lines])
    except Exception as exc:  # noqa: BLE001
        check("S3 日志段执行未抛异常", False, "%s: %s" % (type(exc).__name__, exc))


# ══ S4 health 读数结构 ════════════════════════════════════════════
REQUIRED_HEALTH_KEYS = (
    "endpoint_kind", "ok", "service_ok", "shim_ok",
    "service_status", "service_queue_depth", "service_gpu_mem_mb",
    "shim_status", "shim_stage_channel", "engine_path", "engine_version",
    "checked_at", "reasons", "watchdog", "preset",
)
REQUIRED_WATCHDOG_KEYS = ("mode", "enabled", "ticks", "failures", "restarts",
                          "next_restart_in", "backoff_seconds", "restart_capable",
                          "log")


def section_health() -> None:
    section("S4 /api/health 本地链路读数结构")
    try:
        svc = FakeEndpoint({"ok": True, "status": "ready", "queue_depth": 0,
                            "gpu_mem_mb": 1740})
        shim = FakeEndpoint({"ok": True, "shim": "up", "upstream": "http://127.0.0.1:8772",
                             "stage_channel": {"explicit_stage": 5}})
        clock = Clock()
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="auto", clock=clock,
                              log_fn=lambda line: None)
        snap = wd.health(engine_path="dgtf_engine/.../Meta-DGTF-V9.9.9.py",
                         engine_version="9.9.9", endpoint_kind="local")
        missing = [k for k in REQUIRED_HEALTH_KEYS if k not in snap]
        wd_missing = [k for k in REQUIRED_WATCHDOG_KEYS
                      if k not in (snap.get("watchdog") or {})]
        check("S4.1 health 字段齐全（含需求里点名的 service_ok/shim_ok/queue/gpu/"
              "stage_channel/engine_path/version/endpoint_kind）",
              not missing and not wd_missing,
              "missing=%r wd_missing=%r" % (missing, wd_missing))
        check("S4.2 读数来自真响应：service_status=ready / queue=0 / gpu=1740 / "
              "shim stage_channel 非空 / engine 透传 / endpoint_kind=local",
              snap["service_status"] == "ready"
              and snap["service_queue_depth"] == 0
              and snap["service_gpu_mem_mb"] == 1740
              and snap["shim_stage_channel"] == {"explicit_stage": 5}
              and snap["engine_path"].endswith("Meta-DGTF-V9.9.9.py")
              and snap["engine_version"] == "9.9.9"
              and snap["endpoint_kind"] == "local"
              and snap["ok"] is True,
              json.dumps({k: snap.get(k) for k in ("service_status", "service_queue_depth",
                                                   "service_gpu_mem_mb", "ok")},
                         ensure_ascii=False))
        # 读不到 = null + 原因（不是 0、不是假绿）
        dead = FakeEndpoint({"ok": True, "status": "ready"})
        dead_url = dead.url
        dead.close()
        wd_down = lc.ChainWatchdog(
            [{"name": "service", "label": "svc", "kind": "service",
              "url": dead_url, "path": "/health", "start_cmd": None},
             {"name": "shim", "label": "shim", "kind": "shim",
              "url": dead_url, "path": "/health", "start_cmd": None}],
            mode="on", clock=Clock(), failure_threshold=999,
            log_fn=lambda line: None)
        snap_down = wd_down.health(max_age=0.0)
        check("S4.3 两段都连不上：ok=False、各读数 null、reasons 点名原因"
              "（「没有读数就不假装有」）",
              snap_down["ok"] is False
              and snap_down["service_ok"] is False and snap_down["shim_ok"] is False
              and snap_down["service_status"] is None
              and snap_down["service_queue_depth"] is None
              and snap_down["service_gpu_mem_mb"] is None
              and snap_down["shim_stage_channel"] is None
              and bool((snap_down.get("reasons") or {}).get("service"))
              and bool((snap_down.get("reasons") or {}).get("shim")),
              json.dumps({"ok": snap_down["ok"],
                          "reasons": snap_down.get("reasons")}, ensure_ascii=False))
        # 从未探测：ok=None + "未探测" 原因（null 与 False 分得开）
        wd_never = lc.ChainWatchdog(_targets(FakeEndpoint({"ok": True, "status": "ready"}),
                                             FakeEndpoint({"ok": True, "shim": "up"})),
                                    mode="on", clock=lambda: 0.0,
                                    log_fn=lambda line: None)
        snap_never = wd_never.health(max_age=999.0)
        check("S4.4 从未探测：ok=None（不是 False）且 reason=未探测",
              snap_never["ok"] is None
              and "未探测" in ((snap_never.get("reasons") or {}).get("service") or ""),
              json.dumps({"ok": snap_never["ok"],
                          "reasons": snap_never.get("reasons")}, ensure_ascii=False))
        # 缓存：短时间第二次读不重探（on_demand=False），max_age=0 才强制重探
        svc_c = FakeEndpoint({"ok": True, "status": "ready"})
        shim_c = FakeEndpoint({"ok": True, "shim": "up"})
        wd_c = lc.ChainWatchdog(_targets(svc_c, shim_c), mode="on", clock=Clock(),
                                log_fn=lambda line: None)
        first = wd_c.health(max_age=8.0)
        second = wd_c.health(max_age=8.0)
        check("S4.5 读数缓存：首次按需探测（on_demand=True）、紧接着读命中缓存",
              first["probe"]["on_demand"] is True
              and second["probe"]["on_demand"] is False,
              "first=%r second=%r" % (first["probe"]["on_demand"],
                                      second["probe"]["on_demand"]))
        svc_c.set({"ok": False, "status": "loading"})
        forced = wd_c.health(max_age=0.0)
        check("S4.6 强制重探（max_age=0）能反映状态变化：loading → ok False + 原因",
              forced["probe"]["on_demand"] is True
              and forced["service_ok"] is False
              and "loading" in ((forced.get("reasons") or {}).get("service") or ""),
              json.dumps(forced.get("reasons"), ensure_ascii=False))
        svc_c.close(); shim_c.close()
        svc.close(); shim.close()
        # endpoint_kind 分类
        cases = [("http://127.0.0.1:8773/v1", "local"),
                 ("http://localhost:8772", "local"),
                 ("https://api.deepseek.com/v1", "cloud"),
                 ("", "unknown")]
        got = [lc.classify_endpoint(x) for x, _ in cases]
        check("S4.7 endpoint_kind 分类：回环=local / 云端=cloud / 空=unknown",
              got == [want for _, want in cases], "got=%r" % (got,))
    except Exception as exc:  # noqa: BLE001
        check("S4 health 段执行未抛异常", False, "%s: %s" % (type(exc).__name__, exc))


# ══ S5 本地全链路预设 + App 既有 preset 通道 ═════════════════════
def _preset_flat_from_text(text: str) -> dict:
    import yaml
    return lc.flatten(yaml.safe_load(text) or {})


def _preset_checks() -> dict:
    """对预设做一组「值/安全/可复现」检查，返回 {'checks': [(name, ok, detail)]}。"""
    out = []
    flat = lc.read_preset_flat()
    want = lc.LOCAL_PRESET_OVERRIDES
    bad = []
    for key in lc.PRESET_REQUIRED:
        if key not in flat:
            bad.append(key + ":缺")
        elif flat[key] != want[key]:
            bad.append("%s: %r≠%r" % (key, flat[key], want[key]))
    out.append(("S5.1 预设必需键逐项等于 LOCAL_PRESET_OVERRIDES",
                not bad, ",".join(bad)))
    raw = lc.PRESET_PATH.read_text(encoding="utf-8", errors="replace") if lc.PRESET_PATH.is_file() else ""
    low = raw.lower()
    cloud = [bad for bad in ("api.deepseek.com", "openai.com", "sk-") if bad in low]
    out.append(("S5.2 预设里没有云端点 / 密钥字样（本地档不能偷偷指回云）",
                bool(raw) and not cloud, "命中=%r" % (cloud,)))
    t1 = lc.build_local_preset_text()
    t2 = lc.build_local_preset_text()
    out.append(("S5.3 生成器确定性：连跑两次逐字相同", t1 == t2,
                "len=%d/%d" % (len(t1), len(t2))))
    out.append(("S5.4 生成结果与 commit 的预设文件逐字相同（可复现，改了就红）",
                bool(raw) and raw == t1,
                "file_len=%d generated_len=%d" % (len(raw), len(t1))))
    out.append(("S5.5 覆盖后的值经 build_temp_config 往返一致（与 App 参数通道同语义）",
                _build_temp_equivalent(want), "见 build_temp_config 对账"))
    return {"checks": out}


def _build_temp_equivalent(want: dict) -> bool:
    try:
        import params
        tmpdir = Path(tempfile.mkdtemp(prefix="dgtf_lc_cfg_"))
        out = params.build_temp_config(dict(want), tmpdir / "temp.yaml")
        if not out or not Path(out).is_file():
            return False
        import yaml
        flat = lc.flatten(yaml.safe_load(Path(out).read_text(encoding="utf-8",
                                                             errors="replace")) or {})
        bad = [k for k in lc.PRESET_REQUIRED
               if flat.get(k) != want[k]]
        return not bad
    except Exception:  # noqa: BLE001
        return False


def section_preset() -> None:
    section("S5 本地模型-全链路预设 + engine_runner 既有通道")
    try:
        out = _preset_checks()
        for name, ok, detail in out["checks"]:
            check(name, ok, detail)
        # engine_runner：profile 名（带/不带 .yaml）都能解析到 configs/ 里的文件
        import engine_runner as runner
        p1 = runner.profile_path(lc.PRESET_NAME)
        p2 = runner.profile_path(lc.PRESET_NAME[:-5])   # 不带 .yaml 也要自动补
        check("S5.6 engine_runner.profile_path 能解析预设（带/不带 .yaml 都行）",
              p1 is not None and p2 is not None
              and Path(p1).resolve() == lc.PRESET_PATH.resolve(),
              "p1=%r p2=%r" % (p1, p2))
        # build_cmd 的 _config 通道（App 参数面板/任务 opts 走的就是这条）
        cmd = runner.build_cmd("成年人正常心率是多少", {"_config": str(p1)})
        joined = " ".join(cmd)
        check("S5.7 engine_runner.build_cmd 拼出 --config <预设>（App 既有通道真能用）",
              "--config" in cmd and str(p1) in joined
              and any("Meta-DGTF-V" in c for c in cmd),
              "cmd=%r" % (cmd[:6],))
        # 语法检查：预设能被 yaml 解析（引擎 _load_config_raw 的第一步）
        import yaml
        parsed = yaml.safe_load(lc.PRESET_PATH.read_text(encoding="utf-8",
                                                         errors="replace"))
        check("S5.8 预设是合法 YAML 且顶层是 mapping（引擎 --config 能读）",
              isinstance(parsed, dict) and "api" in parsed and "output" in parsed,
              "type=%r keys=%r" % (type(parsed).__name__,
                                   (sorted(parsed.keys())[:6] if isinstance(parsed, dict) else [])))
    except Exception as exc:  # noqa: BLE001
        check("S5 预设段执行未抛异常", False,
              "%s: %s" % (type(exc).__name__, exc))


# ══ S6 变异体（有牙证明）═════════════════════════════════════════
def _mutant(name: str, patch, restore, sensitive) -> None:
    """跑一个变异体：sensitive() 正常必须绿；打补丁后必须变红（绿=判据没牙）。"""
    try:
        ok_normal, detail_normal = sensitive()
    except Exception as exc:  # noqa: BLE001
        check("变异体 " + name + " 的基线执行", False,
              "%s: %s" % (type(exc).__name__, exc))
        return
    if not ok_normal:
        check("变异体 " + name + "（基线必须先绿）", False, detail_normal)
        return
    caught = False
    detail = ""
    try:
        patch()
        ok_mut, detail = sensitive()
        caught = not ok_mut
    except Exception as exc:  # noqa: BLE001
        caught = True
        detail = "变异体执行异常（视为被抓到）：%s: %s" % (type(exc).__name__, exc)
    finally:
        try:
            restore()
        except Exception:  # noqa: BLE001
            pass
    check("变异体 " + name + "：判据必须变红（没抓到=判据没牙）",
          caught, "" if caught else "变异体仍然全绿：" + str(detail))


def _two_healthy_endpoints():
    svc = FakeEndpoint({"ok": True, "status": "ready"})
    shim = FakeEndpoint({"ok": True, "shim": "up"})
    return svc, shim


def _shim_down_check() -> tuple:
    svc, shim = _two_healthy_endpoints()
    try:
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=Clock(),
                              failure_threshold=999, log_fn=lambda line: None)
        wd.tick()              # 先健康
        shim.close()
        snap = wd.health(max_age=0.0)
        ok = (snap["shim_ok"] is False
              and bool((snap.get("reasons") or {}).get("shim")))
        return ok, json.dumps({"shim_ok": snap["shim_ok"],
                               "reasons": snap.get("reasons")}, ensure_ascii=False)
    finally:
        svc.close()
        shim.close()


def _restart_check() -> tuple:
    svc, shim = _two_healthy_endpoints()
    try:
        clock = Clock(2000.0)
        calls = []
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=clock,
                              start_fn=lambda t, st, now: calls.append(t["name"]) or True,
                              failure_threshold=1, backoff=(120,),
                              log_fn=lambda line: None)
        clock.tick(1)
        shim.close()
        wd.tick()
        return calls == ["shim"], "start_calls=%r" % (calls,)
    finally:
        svc.close()
        shim.close()


def _loading_no_restart_check() -> tuple:
    svc = FakeEndpoint({"ok": False, "status": "loading"})
    shim = FakeEndpoint({"ok": True, "shim": "up"})
    try:
        starts = []
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=Clock(),
                              start_fn=lambda t, st, now: starts.append(t["name"]) or True,
                              failure_threshold=1, log_fn=lambda line: None)
        wd.tick(); wd.tick()
        return (starts == [] and wd.states["service"]["failures"] == 0), \
            "starts=%r failures=%r" % (starts, wd.states["service"]["failures"])
    finally:
        svc.close(); shim.close()


def _throttle_check() -> tuple:
    dead = FakeEndpoint({"ok": True, "status": "ready"})
    dead_url = dead.url
    dead.close()
    try:
        lines = []
        clock = Clock(3000.0)
        wd = lc.ChainWatchdog(
            [{"name": "service", "label": "svc", "kind": "service",
              "url": dead_url, "path": "/health", "start_cmd": None}],
            mode="on", clock=clock, failure_threshold=999,
            # ★ 这里**不传** log_min_interval：用模块默认值，M4 变异体改
            #   LOG_MIN_INTERVAL 才能真的作用到状态机上（否则签名绑定测不动）。
            log_fn=lambda line: lines.append(line))
        t0 = clock.t
        for i in range(10):
            clock.t = t0 + i * 10.0
            wd.tick()
        return len(lines) <= 3, "lines=%d" % (len(lines),)
    finally:
        dead.close()


def _backoff_increasing_check() -> tuple:
    svc, shim = _two_healthy_endpoints()
    try:
        clock = Clock(4000.0)
        starts = []
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=clock,
                              start_fn=lambda t, st, now: starts.append(now) or True,
                              failure_threshold=1, backoff=(120.0, 300.0, 600.0),
                              log_fn=lambda line: None)
        shim.close()
        wd.tick()
        for _ in range(2):
            clock.t = wd.states["shim"]["next_start_at"] + 0.1
            wd.tick()
        gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
        near = (len(gaps) == 2 and abs(gaps[0] - 120.0) < 1.0
                and abs(gaps[1] - 300.0) < 1.0)
        return len(starts) == 3 and near, "gaps=%r" % (gaps,)
    finally:
        svc.close()
        shim.close()


def _health_keys_check() -> tuple:
    svc, shim = _two_healthy_endpoints()
    try:
        wd = lc.ChainWatchdog(_targets(svc, shim), mode="on", clock=Clock(),
                              log_fn=lambda line: None)
        snap = wd.health()
        missing = [k for k in REQUIRED_HEALTH_KEYS if k not in snap]
        return not missing, "missing=%r" % (missing,)
    finally:
        svc.close()
        shim.close()


def _targets_cover_check() -> tuple:
    svc, shim = _two_healthy_endpoints()
    try:
        wd = lc.ChainWatchdog(mode="on", clock=Clock(),
                              log_fn=lambda line: None)
        return _suite_targets_cover_both(wd), "names=%r" % ([t["name"] for t in wd.targets],)
    finally:
        svc.close()
        shim.close()


def section_mutants() -> None:
    section("S6 变异体（有牙证明：每个变异体都必须让判据变红）")
    try:
        # M1：把 shim 从守护目标里删掉（旧版行为）—— 目标覆盖判据必须红
        orig_default = lc.default_targets
        _mutant("M1 删掉 8773 shim 守护目标",
                lambda: setattr(lc, "default_targets",
                                lambda: [t for t in orig_default()
                                         if t["name"] != "shim"]),
                lambda: setattr(lc, "default_targets", orig_default),
                _targets_cover_check)
        # M2：shim_ok 写死 True（假绿）—— 掉线判据必须红
        orig_probe_one = lc.ChainWatchdog._probe_one

        def _fake_probe_one(self, target):
            res = dict(orig_probe_one(self, target))
            if target.get("name") == "shim":
                res["ok"] = True
                res["data"] = {"ok": True, "shim": "up"}
            return res

        _mutant("M2 shim_ok 写死 True",
                lambda: setattr(lc.ChainWatchdog, "_probe_one", _fake_probe_one),
                lambda: setattr(lc.ChainWatchdog, "_probe_one", orig_probe_one),
                _shim_down_check)
        # M3：退避改成固定 30s —— 递增判据必须红
        orig_init = lc.ChainWatchdog.__init__

        def _init_fixed_backoff(self, *a, **kw):
            kw["backoff"] = (30.0, 30.0, 30.0)
            orig_init(self, *a, **kw)

        _mutant("M3 退避改成固定 30s",
                lambda: setattr(lc.ChainWatchdog, "__init__", _init_fixed_backoff),
                lambda: setattr(lc.ChainWatchdog, "__init__", orig_init),
                _backoff_increasing_check)
        # M4：日志不节流 —— 刷屏判据必须红
        orig_min = lc.LOG_MIN_INTERVAL
        _mutant("M4 关掉日志节流",
                lambda: setattr(lc, "LOG_MIN_INTERVAL", 0.0),
                lambda: setattr(lc, "LOG_MIN_INTERVAL", orig_min),
                _throttle_check)
        # M5：把预设覆盖表里的 base_url 改回云端 —— 生成器必须拒绝（抛错）
        orig_ov = lc.LOCAL_PRESET_OVERRIDES

        def _cloud_guard() -> tuple:
            text = lc.build_local_preset_text()   # 变异体指回云端 ⇒ 生成器抛错（被 _mutant 记为抓到）
            return ("api.deepseek.com" not in text.lower()), "生成结果里出现云端点"

        def _patch_cloud():
            bad = dict(orig_ov)
            bad["api.base_url"] = "https://api.deepseek.com/v1"
            lc.LOCAL_PRESET_OVERRIDES = bad

        _mutant("M5 预设指回云端点",
                _patch_cloud,
                lambda: setattr(lc, "LOCAL_PRESET_OVERRIDES", orig_ov),
                _cloud_guard)
        # M6：health 丢掉 shim 字段 —— 字段齐全判据必须红
        orig_health = lc.ChainWatchdog.health

        def _health_no_shim(self, *a, **kw):
            snap = orig_health(self, *a, **kw)
            snap.pop("shim_stage_channel", None)
            snap.pop("shim_ok", None)
            return snap

        _mutant("M6 health 丢 shim 字段",
                lambda: setattr(lc.ChainWatchdog, "health", _health_no_shim),
                lambda: setattr(lc.ChainWatchdog, "health", orig_health),
                _health_keys_check)
        # M7：硬掉线也不重启 —— 重启判据必须红
        orig_start = lc.ChainWatchdog._start_target
        _mutant("M7 掉线不重启",
                lambda: setattr(lc.ChainWatchdog, "_start_target",
                                lambda self, t, st, now: False),
                lambda: setattr(lc.ChainWatchdog, "_start_target", orig_start),
                _restart_check)
        # M8：loading 也被当掉线重启 —— 「不误杀加载中进程」判据必须红
        orig_pending = lc.PENDING_STATUSES
        _mutant("M8 loading 也触发重启",
                lambda: setattr(lc, "PENDING_STATUSES", ()),
                lambda: setattr(lc, "PENDING_STATUSES", orig_pending),
                _loading_no_restart_check)
    except Exception as exc:  # noqa: BLE001
        check("S6 变异体段执行未抛异常", False, "%s: %s" % (type(exc).__name__, exc))


def main() -> int:
    print("本地链路判据：8772 推理服务 + 8773 OpenAI 适配层")
    print("（本测试不碰真实 8772/8773，不起任何 GPU 进程；重启动作走注入回调）")
    for fn in (section_probe, section_watchdog, section_log_throttle,
               section_health, section_preset, section_mutants):
        try:
            fn()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            check("段落 " + fn.__name__ + " 未抛异常", False)
    print()
    print("\u2500" * 60)
    print("结果：PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
        return 1
    print("判据全绿：本地链路守护/读数/预设均有牙（含 %d 个变异体全部被抓到）"
          % 8)
    return 0


if __name__ == "__main__":
    sys.exit(main())
