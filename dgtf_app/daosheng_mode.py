# -*- coding: utf-8 -*-
"""道生专属模式 · App 侧「三体动态最优」计划生成器。

三体 = App（本模块） / 引擎（并行模式、route/rounds、新机制键） / 本地模型（8772）。

本模块只做**离线可测**的决策与摘要，不启动引擎、不调用真实 API：

- `resolve_mode()`：mode 请求（auto / daosheng / daosheng_fast / standard）
  → 实际档位 + 理由。auto：项目相关题 → daosheng，其它 → standard（既有链路）。
- `build_plan()`：给定 question + 历史读数 → 可审计 plan
  （policy / plan 字段 / reason / budget_guard / context_injected / local_llm /
  m4 / memory / cache 预判），全程 fail-open。
- `apply_plan()`：以 **setdefault** 方式落成引擎 opts（显式 opts 永远优先）。
- `local_llm_route()`：优先 HTTP 服务 127.0.0.1:8772（GET /health、
  POST /generate {stage:"route", ...}）；总预算 1.5s；不可达 → 子进程 →
  规则回退，绝不阻塞任务创建。
- `read_history()` / `memory_summary()`：episodes.jsonl / playbook.jsonl /
  MEMORY.md 的相关性摘要（带 mtime 缓存与 1600 字上限；非项目题不注入）。
- `budget_guard()`：余额 + 历史中位 tokens + 引擎 raw_max_tokens → 估算费用；
  余额 < ¥8 → 降级 daosheng_fast；< ¥4 → 告警；查询失败 fail-open。

一切决策都写进 plan 的显式字段，供 `/api/tasks` 响应回显与 selftest 判据使用。
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "configs"
MEMORY_DIR = PROJECT_ROOT / "dgtf_memory"
PRESET_NAME = "道生专属模式.yaml"
PRESET_PATH = CONFIG_DIR / PRESET_NAME

POLICY = "daosheng.v1"


def _engine_supports_dual_judge_local() -> bool:
    """引擎源码是否已支持 --dual-judge-mode local（dual_judge local 合并后自动 True）。"""
    try:
        engine = (PROJECT_ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
                  / "Meta-DGTF-V2.2.3.py")
        text = engine.read_text(encoding="utf-8", errors="replace")
        return ('"llm", "cache", "auto", "local"' in text
                or "llm,cache,auto,local" in text)
    except Exception:  # noqa: BLE001
        return False
VALID_MODES = ("auto", "daosheng", "daosheng_fast", "standard")
VALID_ROUTE = ("0", "1", "both", "all")

# ★ [V2.2.24] 层依赖闭包：both 需要 0/1 的上游产物；all 需要 both/0/1。
#   动态预测/预算裁剪后若留下 both/all，则补齐依赖，避免"调度了 all 却没有 upstream"。
_ROUTE_ORDER = ("0", "1", "both", "all")
_ROUTE_DEPS = {"both": ("0", "1"), "all": ("both", "0", "1")}


def route_with_deps(route_list) -> tuple[list, list]:
    """返回 (按顺序补全依赖后的 route, 新增条目)。纯函数，可单测。"""
    have = set(str(x) for x in (route_list or []) if str(x))
    added: list[str] = []
    changed = True
    while changed:
        changed = False
        for entry in list(have):
            for dep in _ROUTE_DEPS.get(entry, ()):
                if dep not in have:
                    have.add(dep)
                    added.append(dep)
                    changed = True
    ordered = [e for e in _ROUTE_ORDER if e in have]
    return ordered, added

#: 与 server._PROJECT_CTX_MARKS 同口径的兜底判据（server 会显式传入 project_related，
#: 这里是给独立 CLI / selftest 用的；两处不一致时以 server 传入值为准）。
_PROJECT_MARKS = ("meta-dgtf", "dgtf", "道生三阶", "四层", "修行", "研究",
                  "对撞", "元层", "eml", "dsh", "调度", "lora", "自洽",
                  "route", "rounds", "app", "项目")

_UNSET = object()


# ── 预设加载 ────────────────────────────────────────────────────
#: 预设缺失时仍能工作的内置兜底（与 configs/道生专属模式.yaml 的 app_daosheng 同步）。
_BUILTIN_DS = {
    "schema": "metadgtf.app_daosheng.v1",
    "version": "1.0.0",
    "route": "0,1,both,all",
    # [V2.2.23] route 安全门默认：预测不砍层
    "route_policy": "union",
    "rounds": "auto",
    "rounds_quality": "0:3,1:3,both:4,all:4",
    "rounds_fast": "0:2,1:3,both:2,all:2",
    "parallel": "B",
    "web": "auto",
    "thinking": "auto",
    "effort": "auto",
    "self_check_mode": "auto",
    "dual_judge_mode": "auto",
    "history_fusion": "auto",
    "quality_policy": {"project": "auto:verified",
                       "fact": "auto:web-retry",
                       "other": "auto:stable"},
    "budget": {"cny_per_million_tokens": 2.0, "degrade_below_cny": 8.0,
               "warn_below_cny": 4.0, "est_tokens_default": 1300000,
               "raw_max_tokens_fallback": 2000000,
               # ★ [V2.2.24] 动态配置：预留比例/临界倍数/降档圈数模板
               "reserve_ratio": 0.5, "critical_est_mult": 1.2,
               "reserve_runs": 2,
               "rounds_economy": "0:1,1:2,both:1,all:1",
               "rounds_critical": "0:1,1:1,both:1,all:1"},
    "history": {"episodes_limit": 80, "min_samples": 5},
    "memory": {"max_chars": 1600, "max_lessons": 2, "max_playbook": 2,
               "episodes_recent": 80, "cache_entries": 64},
    "local_llm": {"enabled": True, "url": "http://127.0.0.1:8772",
                  "stage": "route", "max_new_tokens": 96, "temperature": 0.0,
                  "total_timeout_s": 1.5, "health_timeout_s": 0.6,
                  "health_cache_s": 30},
    "m4": {"enabled": True},
}

_PRESET_LOCK = threading.Lock()
_PRESET_CACHE: dict = {"stamp": None, "ds": None, "error": ""}


def preset_path() -> Path:
    return PRESET_PATH


def _builtin_ds() -> dict:
    return copy.deepcopy(_BUILTIN_DS)


def _deep_fill(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = _deep_fill(out[k], v)
        else:
            out[k] = v
    return out


def load_preset(force: bool = False) -> dict:
    """读 `configs/道生专属模式.yaml` 的 app_daosheng 段（mtime 缓存）。

    返回**已用内置默认深填充**的 dict（缺键不会炸）；文件缺失/解析失败时
    整段回落内置默认，并在 `preset_info()` 里留痕（不阻断任务）。
    """
    p = preset_path()
    try:
        st = p.stat()
        stamp = (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        stamp = None
    with _PRESET_LOCK:
        if (not force and stamp is not None
                and _PRESET_CACHE.get("stamp") == stamp
                and isinstance(_PRESET_CACHE.get("ds"), dict)):
            return copy.deepcopy(_PRESET_CACHE["ds"])
    data = _builtin_ds()
    err = ""
    if stamp is not None:
        try:
            import yaml  # 项目主环境自带（params.py / selftest.py 同款依赖）
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            sec = raw.get("app_daosheng") if isinstance(raw, dict) else None
            if isinstance(sec, dict):
                data = _deep_fill(_BUILTIN_DS, sec)
            else:
                err = "预设缺少 app_daosheng 段"
        except Exception as exc:  # noqa: BLE001  预设坏了不该拖垮任务
            err = "%s: %s" % (type(exc).__name__, exc)
    else:
        err = "预设文件不存在：" + str(p)
    with _PRESET_LOCK:
        if len(_PRESET_CACHE) > 8:
            _PRESET_CACHE.clear()
        _PRESET_CACHE.update(stamp=stamp, ds=copy.deepcopy(data), error=err)
    return copy.deepcopy(data)


def preset_info() -> dict:
    p = preset_path()
    try:
        st = p.stat()
        return {"path": str(p), "name": PRESET_NAME, "exists": True,
                "bytes": int(st.st_size), "mtime": float(st.st_mtime),
                "error": _PRESET_CACHE.get("error") or ""}
    except OSError:
        return {"path": str(p), "name": PRESET_NAME, "exists": False,
                "bytes": 0, "mtime": 0.0,
                "error": _PRESET_CACHE.get("error") or "预设文件不存在"}


# ── 小工具 ─────────────────────────────────────────────────────
def _median(vals) -> float:
    xs = sorted(float(v) for v in (vals or []) if isinstance(v, (int, float))
                or (isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v)))
    if not xs:
        return 0.0
    n = len(xs)
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def _q_tokens(text: str) -> list[str]:
    return [x.lower() for x in re.findall(
        r"[A-Za-z]{2,}|[\u4e00-\u9fff]{2,4}", str(text or ""))][:24]


def project_relevant(question: str) -> bool:
    q = str(question or "").lower()
    return any(k in q for k in _PROJECT_MARKS)


def _norm_route(route) -> list[str]:
    """route 归一：list / "0,1,both,all" → ["0","1","both","all"]（保序去重）。"""
    if isinstance(route, str):
        items = [x.strip() for x in re.split(r"[,，\s]+", route) if x.strip()]
    elif isinstance(route, (list, tuple)):
        items = [str(x).strip() for x in route]
    else:
        items = []
    out: list[str] = []
    for x in items:
        x = x.lower()
        if x.isdigit():
            x = str(int(x))
        if x in VALID_ROUTE and x not in out:
            out.append(x)
    return out


def _norm_rounds(rounds) -> dict:
    """rounds 归一：{"0":3,...,"both":4} → {"0":3,...}（键/值域过滤，非法丢弃）。"""
    out: dict[str, int] = {}
    if isinstance(rounds, str):
        for kv in re.split(r"[,，\s]+", rounds):
            if ":" in kv:
                k, v = kv.split(":", 1)
                k = k.strip().lower()
                if k.isdigit():
                    k = str(int(k))
                try:
                    iv = int(float(v))
                except (TypeError, ValueError):
                    continue
                if k in VALID_ROUTE and 0 < iv <= 12:
                    out[k] = iv
    elif isinstance(rounds, dict):
        for k, v in rounds.items():
            k = str(k).strip().lower()
            if k.isdigit():
                k = str(int(k))
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if k in VALID_ROUTE and 0 < iv <= 12:
                out[k] = iv
    return out


def rounds_to_text(rounds: dict) -> str:
    return ",".join("%s:%d" % (k, int(v)) for k, v in (rounds or {}).items())


# ── mode 解析 ──────────────────────────────────────────────────
def resolve_mode(requested: str, question: str,
                 project_related: bool | None = None) -> dict:
    """mode 请求 → 实际档位。

    返回 {id, requested, source, project_related, reason}；
    id ∈ daosheng / daosheng_fast / standard。
    """
    req = str(requested or "auto").strip().lower() or "auto"
    if req not in VALID_MODES:
        raise ValueError("未知 mode：%r（允许 %s）"
                         % (requested, "/".join(VALID_MODES)))
    if project_related is None:
        project_related = project_relevant(question)
    _prj = bool(project_related)
    # ★ [V2.2.21 融合] 道生模式 = 标准模式：auto/standard 统一解析为 daosheng，
    #   全项目只有一条调度链路（道生 plan：预设 + M4 + 预算守卫 + MODE_CONFIGS +
    #   运行期动态调整）。project_related 只决定是否注入项目背景，不改链路。
    if req == "auto":
        return {"id": "daosheng", "requested": req, "source": "auto-fused",
                "project_related": _prj, "fused": True,
                "reason": ("auto → 道生模式（已融合为标准模式；项目相关题注入项目背景）"
                           if _prj else
                           "auto → 道生模式（已融合为标准模式；非项目题不注入项目背景）")}
    if req == "standard":
        return {"id": "daosheng", "requested": req, "source": "fused-standard",
                "project_related": _prj, "fused": True,
                "reason": "standard 已并入道生模式（融合为标准模式，单一链路）"}
    if req == "daosheng_fast":
        return {"id": "daosheng_fast", "requested": req, "source": "explicit",
                "project_related": _prj,
                "reason": "显式 daosheng_fast：便宜档（低圈 + thinking off），质量让位于预算"}
    return {"id": "daosheng", "requested": req, "source": "explicit",
            "project_related": _prj,
            "reason": "显式 daosheng：道生专属模式（质量优先）"}


# ── 历史读数（episodes / playbook / MEMORY.md）──────────────────
_HIST_LOCK = threading.Lock()
_HIST_CACHE: dict = {"stamp": None, "data": None}


def _file_stamp(p: Path):
    try:
        st = p.stat()
        return (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        return None


def _read_jsonl(path: Path, limit: int) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                rows.append(ln)
                if len(rows) > limit * 4:
                    rows = rows[-limit:]
    except OSError:
        return []
    out: list[dict] = []
    for ln in rows[-max(1, int(limit)):]:
        try:
            d = json.loads(ln)
            if isinstance(d, dict):
                out.append(d)
        except ValueError:
            continue
    return out


def _parse_memory_md(path: Path) -> dict:
    """MEMORY.md 是索引：解析 active 经验行与计数（active/shadow）。"""
    out = {"counts": {}, "active_lessons": [], "shadow_lessons": [],
           "bytes": 0, "exists": False}
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    out["exists"] = True
    out["bytes"] = len(txt.encode("utf-8"))
    m = re.search(r"计数：active=(\d+)、shadow=(\d+)", txt)
    if m:
        out["counts"] = {"active": int(m.group(1)), "shadow": int(m.group(2))}
    sec = "active"
    for ln in txt.splitlines():
        line = ln.strip()
        if line.startswith("## "):
            sec = "active" if "active" in line else "shadow"
            continue
        lm = re.match(r"^- `(L\d+)` \[(\w+)\] (.*)$", line)
        if not lm:
            continue
        item = {"id": lm.group(1), "kind": lm.group(2),
                "text": lm.group(3)[:300], "section": sec}
        key = "active_lessons" if sec == "active" else "shadow_lessons"
        if len(out[key]) < 80:
            out[key].append(item)
    return out


def read_history(preset: dict | None = None, force: bool = False) -> dict:
    """聚合记忆读数：episodes 统计 + playbook 摘要 + MEMORY.md 索引（mtime 缓存）。"""
    ds = (preset or load_preset())
    hist_cfg = ds.get("history") or {}
    limit = int(hist_cfg.get("episodes_limit") or 80)
    ep = MEMORY_DIR / "episodes.jsonl"
    pb = MEMORY_DIR / "playbook.jsonl"
    md = MEMORY_DIR / "MEMORY.md"
    stamp = (_file_stamp(ep), _file_stamp(pb), _file_stamp(md), limit)
    with _HIST_LOCK:
        if not force and _HIST_CACHE.get("stamp") == stamp and _HIST_CACHE.get("data"):
            return copy.deepcopy(_HIST_CACHE["data"])
    episodes = _read_jsonl(ep, limit)
    playbook = _read_jsonl(pb, 80)
    mem = _parse_memory_md(md)

    modes: dict[str, int] = {}
    tokens: list[int] = []
    calls: list[int] = []
    tri_rates: list[float] = []
    cut = 0
    web = 0
    caps: dict[str, list[int]] = {k: [] for k in VALID_ROUTE}
    for e in episodes:
        m = str(e.get("mode") or "").strip() or "serial"
        modes[m] = modes.get(m, 0) + 1
        cost = e.get("cost") or {}
        try:
            tokens.append(int(cost.get("tokens") or 0))
            calls.append(int(cost.get("calls") or 0))
        except (TypeError, ValueError):
            pass
        if e.get("tri_rate") is not None:
            try:
                tri_rates.append(float(e["tri_rate"]))
            except (TypeError, ValueError):
                pass
        if e.get("cut_layers"):
            cut += 1
        if int(e.get("n_web") or 0) > 0:
            web += 1
        for k, v in (e.get("rounds_cap") or {}).items():
            kk = str(k).lower()
            if kk.isdigit():
                kk = str(int(kk))
            if kk in caps:
                try:
                    caps[kk].append(int(v))
                except (TypeError, ValueError):
                    pass
    n = len(episodes)
    latest = episodes[-1] if episodes else {}
    stats = {
        "n": n,
        "mode_counts": modes,
        "tokens_med": _median(tokens),
        "calls_med": _median(calls),
        "tri_rate": (sum(tri_rates) / len(tri_rates)) if tri_rates else 0.0,
        "cut_rate": (cut / n) if n else 0.0,
        "web_ratio": (web / n) if n else 0.0,
        "rounds_cap_med": {k: _median(v) for k, v in caps.items() if v},
        "latest_run_id": str(latest.get("run_id") or ""),
        "latest_t": latest.get("t"),
        "latest_mode": str(latest.get("mode") or ""),
        "latest_route": _norm_route(latest.get("route") or []),
        "latest_tokens": int((latest.get("cost") or {}).get("tokens") or 0),
    }
    pb_rows = [r for r in playbook if isinstance(r, dict)]
    pb_stats = {
        "n": len(pb_rows),
        "active": sum(1 for r in pb_rows if r.get("status") == "active"),
        "shadow": sum(1 for r in pb_rows if r.get("status") == "shadow"),
        "recent": [{"id": str(r.get("id") or ""), "kind": str(r.get("kind") or ""),
                    "status": str(r.get("status") or ""),
                    "why": str(r.get("why") or "")[:160],
                    "cond": r.get("cond") or {}, "contra": r.get("contra", 0)}
                   for r in pb_rows[-12:]],
    }
    data = {"episodes": stats, "playbook": pb_stats, "memory_md": mem,
            "stamp": repr(stamp),
            "files": {"episodes": str(ep),
                      "playbook": str(pb), "memory": str(md)}}
    with _HIST_LOCK:
        if len(_HIST_CACHE) > 8:
            _HIST_CACHE.clear()
        _HIST_CACHE.update(stamp=stamp, data=copy.deepcopy(data))
    return data


# ── 引擎能力探测（V2.2.3 新机制键）──────────────────────────────
def engine_capabilities(force: bool = False) -> dict:
    """引擎能力：路径/版本/新机制 CLI flag 与 config 键（engine_runner 统一实现）。"""
    _empty = {"ok": False, "path": "", "version": "", "mock": False,
              "supports": {"self_check_mode": False,
                           "dual_judge_mode": False,
                           "history_fusion": False},
              "supports_config": {"self_check_mode": False,
                                  "dual_judge_mode": False,
                                  "history_fusion": False}}
    try:
        import engine_runner as _runner
        fn = getattr(_runner, "engine_capabilities", None)
        if callable(fn):
            return fn(force=force)
    except Exception as exc:  # noqa: BLE001 探测失败 → 一律当「不支持」= 缺省
        return {**_empty, "error": "%s: %s" % (type(exc).__name__, exc)}
    return {**_empty, "error": "engine_runner.engine_capabilities 缺失"}


# ── 本地推理服务客户端（8772）────────────────────────────────────
_LLM_HEALTH_LOCK = threading.Lock()
_LLM_HEALTH: dict = {"ts": 0.0, "url": "", "ok": False, "error": "", "detail": {}}


def _llm_cfg(preset: dict | None = None) -> dict:
    ds = preset or load_preset()
    cfg = dict(_BUILTIN_DS["local_llm"])
    cfg.update(ds.get("local_llm") or {})
    url = (os.getenv("DGTF_LOCAL_LLM_URL", "").strip() or str(cfg.get("url") or "")).rstrip("/")
    cfg["url"] = url
    return cfg


def _http_json(url: str, payload: dict | None, timeout: float) -> dict:
    """极简 JSON HTTP（GET 无 payload / POST JSON）。失败抛异常给调用方兜。"""
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=max(0.05, float(timeout))) as r:
        body = r.read(200_000).decode("utf-8", "replace")
    try:
        obj = json.loads(body) if body else {}
    except ValueError:
        return {"_raw": body}
    return obj if isinstance(obj, dict) else {"_raw": body, "_value": obj}


_LOCAL_METRICS_CACHE: dict = {"ts": 0.0, "data": {}}


def local_llm_metrics(preset: dict | None = None,
                      force: bool = False) -> dict:
    """GET /metrics（本地服务可观测性）；fail-open，2 秒轻缓存。

    返回 {ok, busy, avg_ms, requests_total, errors, adapter}；
    服务不可达/旧版无 /metrics 时返回 {"ok": False, "reason": ...}（不抛错）。
    """
    ds = preset or load_preset()
    cfg = dict(_BUILTIN_DS["local_llm"])
    cfg.update(ds.get("local_llm") or {})
    if not cfg.get("enabled", True) or os.getenv("DGTF_LOCAL_LLM", "").strip().lower() in (
            "0", "false", "off"):
        return {"ok": False, "reason": "disabled"}
    now = time.time()
    if (not force) and now - float(_LOCAL_METRICS_CACHE.get("ts") or 0) < 2.0:
        return dict(_LOCAL_METRICS_CACHE.get("data") or {})
    out = {"ok": False}
    try:
        detail = _http_json(cfg["url"] + "/metrics", None, timeout=0.8)
        st = (detail or {}).get("stats") or {}
        out = {"ok": True, "busy": bool(st.get("busy_now")),
               "avg_ms": (detail or {}).get("avg_ms"),
               "requests_total": st.get("requests_total"),
               "errors": st.get("errors"),
               "adapter": (detail or {}).get("adapter_paths") or {}}
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "reason": "%s: %s" % (type(e).__name__, e)}
    _LOCAL_METRICS_CACHE["ts"] = now
    _LOCAL_METRICS_CACHE["data"] = dict(out)
    return out


def local_llm_health(preset: dict | None = None, force: bool = False) -> dict:
    """GET /health（成功/失败都缓存；`DGTF_LOCAL_LLM=0` 可整体关闭）。"""
    cfg = _llm_cfg(preset)
    if not cfg.get("enabled", True) or os.getenv("DGTF_LOCAL_LLM", "").strip().lower() in (
            "0", "false", "off", "no"):
        return {"ok": False, "url": cfg["url"], "cached": False,
                "error": "本地推理服务已被配置/环境变量关闭"}
    ttl = float(cfg.get("health_cache_s") or 30)
    now = time.time()
    with _LLM_HEALTH_LOCK:
        if (not force and _LLM_HEALTH.get("url") == cfg["url"]
                and now - float(_LLM_HEALTH.get("ts") or 0) < ttl):
            return dict(_LLM_HEALTH)
    t0 = time.perf_counter()
    ok, err, detail = False, "", {}
    try:
        detail = _http_json(cfg["url"] + "/health", None,
                            float(cfg.get("health_timeout_s") or 0.6))
        ok = bool(detail.get("ok", True)) and not detail.get("error")
        if not ok:
            err = str(detail.get("error") or "health 返回 ok=false")
    except Exception as exc:  # noqa: BLE001  fail-open
        err = "%s: %s" % (type(exc).__name__, exc)
    rec = {"ok": bool(ok), "url": cfg["url"], "cached": False, "error": err,
           "detail": detail, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    with _LLM_HEALTH_LOCK:
        _LLM_HEALTH.update(ts=time.time(), **rec)
    return dict(rec)


def _extract_route_rounds(obj: dict) -> tuple[list[str], dict, str]:
    """从 /generate 响应里容错解析 route/rounds。

    兼容三种形态：① 顶层直接给 route/rounds；② `parsed` / `result` / `json` 子对象；
    ③ `text` / `output` / `content` 是 JSON 字符串（含首尾杂字时抓第一个 {...}）。
    """
    if not isinstance(obj, dict):
        return [], {}, ""
    cands: list = [obj]
    for k in ("parsed", "result", "json", "data", "prediction", "meta"):
        v = obj.get(k)
        if isinstance(v, dict):
            cands.append(v)
    for c in list(cands):
        for k in ("route", "rounds"):
            if c.get(k) not in (None, "", [], {}):
                route = _norm_route(c.get("route")) if c.get("route") is not None else []
                rounds = _norm_rounds(c.get("rounds"))
                if route or rounds:
                    return route, rounds, "direct"
    for k in ("text", "output", "content", "answer", "response"):
        txt = obj.get(k)
        if not isinstance(txt, str) or not txt.strip():
            continue
        parsed = None
        try:
            parsed = json.loads(txt)
        except ValueError:
            m = re.search(r"\{.*\}", txt, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except ValueError:
                    parsed = None
        if isinstance(parsed, dict):
            route = _norm_route(parsed.get("route"))
            rounds = _norm_rounds(parsed.get("rounds"))
            if route or rounds:
                return route, rounds, "text-json"
    return [], {}, ""


def local_llm_route(question: str, preset: dict | None = None,
                    budget_s: float | None = None) -> dict:
    """优先走 HTTP 服务 8772 做 stage=route 预测（总预算 1.5s，fail-open）。"""
    cfg = _llm_cfg(preset)
    total = float(budget_s if budget_s is not None else
                  (cfg.get("total_timeout_s") or 1.5))
    t0 = time.perf_counter()
    health = local_llm_health(preset)
    if not health.get("ok"):
        return {"ok": False, "source": "http", "available": False,
                "url": cfg["url"], "error": health.get("error") or "服务不可达",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    remain = total - (time.perf_counter() - t0)
    if remain <= 0.05:
        return {"ok": False, "source": "http", "available": True, "url": cfg["url"],
                "error": "总预算 %.2fs 已耗尽" % total,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    payload = {
        "stage": str(cfg.get("stage") or "route"),
        "text": question,
        "messages": [{"role": "user", "content": question}],
        "max_new_tokens": int(cfg.get("max_new_tokens") or 96),
        "temperature": float(cfg.get("temperature") or 0.0),
        "timeout": round(max(0.05, remain), 2),
    }
    try:
        resp = _http_json(cfg["url"] + "/generate", payload, remain)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "http", "available": True, "url": cfg["url"],
                "error": "%s: %s" % (type(exc).__name__, exc),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    route, rounds, how = _extract_route_rounds(resp)
    lat = round((time.perf_counter() - t0) * 1000, 1)
    if resp.get("ok") is False or not route:
        return {"ok": False, "source": "http", "available": True, "url": cfg["url"],
                "error": str(resp.get("error") or "响应无可解析 route"),
                "how": how, "raw": json.dumps(resp, ensure_ascii=False)[:400],
                "latency_ms": lat}
    return {"ok": True, "source": "http", "available": True, "url": cfg["url"],
            "route": route, "rounds": rounds, "how": how,
            "raw": json.dumps(resp, ensure_ascii=False)[:400], "latency_ms": lat}


def _default_subprocess_predict(question: str) -> dict:
    """回退②：根目录 `llm_predict.py` 子进程（旧链路；缺失则返回 ok=False）。"""
    script = PROJECT_ROOT / "llm_predict.py"
    py = os.getenv("DGTF_LLM_PYTHON",
                   str(PROJECT_ROOT / "local_model" / "envs" / "dgtf_llm_env"
                       / "Scripts" / "python.exe"))
    if not script.is_file():
        return {"ok": False, "error": "llm_predict.py 不存在（子进程回退不可用）"}
    if not Path(py).is_file():
        return {"ok": False, "error": "本地训练环境不存在：" + py}
    model = os.getenv("DGTF_LLM_MODEL", str(
        PROJECT_ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct"))
    adapter = str(PROJECT_ROOT / "llm_sft" / "adapter_qwen05b_v1")
    if not Path(adapter).is_dir():
        return {"ok": False, "error": "adapter 不存在：" + adapter}
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "HF_HUB_OFFLINE": "1"})
    try:
        p = subprocess.run([py, str(script), "--question", str(question or ""),
                            "--model", model, "--adapter", adapter],
                           cwd=str(PROJECT_ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=60, env=env)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    data: dict = {}
    for ln in reversed((p.stdout or "").strip().splitlines()):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                data = json.loads(ln)
                break
            except ValueError:
                continue
    if not data:
        return {"ok": False, "error": "子进程无 JSON 输出",
                "stderr": (p.stderr or "")[-500:]}
    parsed = data.get("parsed") if isinstance(data.get("parsed"), dict) else data
    route = _norm_route((parsed or {}).get("route"))
    rounds = _norm_rounds((parsed or {}).get("rounds"))
    if not route:
        return {"ok": False, "error": "子进程未给出 route"}
    return {"ok": True, "source": "subprocess", "route": route, "rounds": rounds,
            "raw": json.dumps(parsed, ensure_ascii=False)[:400]}


def _rules_prediction(question: str, preset: dict | None = None) -> dict:
    """回退③：纯规则（quality_predictor 题面特征 + 预设 route），永远可用。"""
    ds = preset or load_preset()
    feats: dict = {}
    try:
        root = str(PROJECT_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from dgtf_v2.quality_predictor import question_features as _qf
        feats = _qf(question) or {}
    except Exception:  # noqa: BLE001 主环境缺 numpy 也不影响纯 Python 特征
        feats = {}
    route = ds.get("route") or "0,1,both,all"
    route_list = _norm_route(route) or list(VALID_ROUTE)
    _short = bool(feats.get("short")) or len(str(question or "")) <= 40
    # ★ Round 8 修正：事实短题**不再**省掉对撞/元层。
    #   实测（App daosheng + web on + route=0,1）：「珠穆朗玛峰的海拔是多少米？」
    #   → quality 0.2253 / unverified（conflict_unresolved、layers_standard=2）；
    #   同题 CLI 全四层 → 0.9581 / verified。事实门需要 both/all 层做证据冲突
    #   消解与元层闭合 ⇒ 事实题一律全四层。
    if False and feats.get("fact") and _short and not feats.get("meta"):
        route_list = ["0", "1"]  # 已废弃：见上（保留分支形状便于回滚）
    rounds = _norm_rounds(ds.get("rounds") or "")
    return {"ok": True, "source": "rules", "route": route_list, "rounds": rounds,
            "features": feats,
            "why": "规则回退：fact=%s/short=%s/meta=%s → route=%s"
                   % (bool(feats.get("fact")), _short, bool(feats.get("meta")),
                      ",".join(route_list))}


def predict_route_rounds(question: str, preset: dict | None = None, *,
                         is_mock: bool = False,
                         subprocess_predict=None) -> dict:
    """本地模型三级回退链：HTTP 8772 → 子进程 → 规则（fail-open，不阻塞）。"""
    ds = preset or load_preset()
    attempts: list[dict] = []
    if is_mock:
        attempts.append({"source": "http", "ok": False,
                         "skipped": "mock 任务跳过本地模型探测（保证自检快）"})
    else:
        http = local_llm_route(question, ds)
        attempts.append({k: http.get(k) for k in
                         ("source", "ok", "available", "latency_ms", "error")})
        if http.get("ok"):
            return {**http, "attempts": attempts}
        # 旧子进程回退依赖根目录 llm_predict.py；文件缺失时不要制造虚假尝试/错误。
        _sub_script = PROJECT_ROOT / "llm_predict.py"
        if subprocess_predict is not None or _sub_script.is_file():
            cb = subprocess_predict or _default_subprocess_predict
            try:
                sub = cb(question)
            except Exception as exc:  # noqa: BLE001
                sub = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
            sub = dict(sub or {})
            sub.setdefault("source", "subprocess")
            attempts.append({k: sub.get(k) for k in ("source", "ok", "error")})
            if sub.get("ok") and _norm_route(sub.get("route")):
                sub["route"] = _norm_route(sub.get("route"))
                sub["rounds"] = _norm_rounds(sub.get("rounds"))
                return {**sub, "attempts": attempts}
    rules = _rules_prediction(question, ds)
    attempts.append({"source": "rules", "ok": True})
    return {**rules, "attempts": attempts}


# ── 项目自进化记忆注入（相关性摘要 + 缓存 + 上限）─────────────────
_MEM_LOCK = threading.Lock()
_MEM_CACHE: dict = {}
_MEM_CACHE_MAX = 64


def memory_summary(question: str, preset: dict | None = None, *,
                   project_related: bool = True,
                   history: dict | None = None,
                   force: bool = False) -> dict:
    """从 MEMORY.md + playbook.jsonl + episodes.jsonl 生成**相关性**摘要。

    - 只对项目相关题注入（project_related=False ⇒ 空摘要，调用方不要塞 prompt）；
    - 只收与问题词面有重合的经验条；全无重合时只给「近 N 次跑次」聚合读数；
    - 2000 字上限（max_chars），带 mtime 缓存。
    """
    ds = preset or load_preset()
    cfg = dict(_BUILTIN_DS["memory"])
    cfg.update(ds.get("memory") or {})
    base = {"text": "", "chars": 0, "injected": False, "truncated": False,
            "cache": "miss", "lessons": 0, "playbook": 0,
            "sources": [], "reason": ""}
    if not project_related:
        base["reason"] = "非项目相关题：不注入 EML 记忆（避免无关内容进 prompt）"
        return base
    hist = history or read_history(ds)
    key = (str(question or "")[:200], hist.get("stamp"),
           int(cfg.get("max_chars") or 1600))
    with _MEM_LOCK:
        hit = _MEM_CACHE.get(key)
        if hit is not None and not force:
            out = copy.deepcopy(hit)
            out["cache"] = "hit"
            return out
    eps = hist.get("episodes") or {}
    mem = hist.get("memory_md") or {}
    pb = hist.get("playbook") or {}
    terms = _q_tokens(question)
    marks = [k for k in _PROJECT_MARKS if k in str(question or "").lower()]

    def _score(blob: str) -> int:
        low = str(blob or "").lower()
        return sum(1 for t in terms if t and t in low) * 2 + sum(
            1 for m in marks if m in low)

    lines: list[str] = ["【项目自进化记忆（EML · 相关性摘要）】"]
    lessons = 0
    scored = sorted(mem.get("active_lessons") or [],
                    key=lambda it: _score(it.get("text")), reverse=True)
    for it in scored[:int(cfg.get("max_lessons") or 2)]:
        if _score(it.get("text")) <= 0:
            continue
        lines.append("- 经验 %s [%s] %s" % (it.get("id"), it.get("kind"),
                                            str(it.get("text"))[:180]))
        lessons += 1
    pb_rows = sorted((pb.get("recent") or []),
                     key=lambda it: _score(it.get("why")), reverse=True)
    pbn = 0
    for it in pb_rows[:int(cfg.get("max_playbook") or 2)]:
        if it.get("status") == "retired" or _score(it.get("why")) <= 0:
            continue
        lines.append("- 玩法 %s [%s·%s] %s" % (it.get("id"), it.get("kind"),
                                              it.get("status"),
                                              str(it.get("why"))[:140]))
        pbn += 1
    if lessons == 0 and (mem.get("active_lessons") or []):
        # 词面没命中不等于没有项目记忆：给一行**索引**（不假装与本题相关，
        # 只用于项目连续性），并列出证据量最高的一条供参考。
        _all = mem.get("active_lessons") or []
        _kinds: dict[str, int] = {}
        for _it in _all:
            _k = str(_it.get("kind") or "?")
            _kinds[_k] = _kinds.get(_k, 0) + 1
        _top = max(_all, key=lambda it: _evidence_num(it.get("text")))
        lines.append("- 经验索引：active %d 条（%s）；最高证据 %s [%s] %s"
                     % (len(_all),
                        "/".join("%s×%s" % (k, v) for k, v in sorted(_kinds.items())),
                        _top.get("id"), _top.get("kind"),
                        str(_top.get("text"))[:120]))
    if pbn == 0 and int(pb.get("n") or 0) > 0:
        lines.append("- 玩法库：%d 条（active %d / shadow %d；本题未命中词面相关条目）"
                     % (int(pb.get("n") or 0), int(pb.get("active") or 0),
                        int(pb.get("shadow") or 0)))
    if eps.get("n"):
        modes = eps.get("mode_counts") or {}
        mode_txt = "/".join("%s×%d" % (k, v) for k, v in sorted(modes.items()))
        lines.append("- 近 %d 次跑次：模式 %s；tokens 中位 %s；被砍层比例 %d%%；"
                     "web 比例 %d%%；圈数上限中位 %s"
                     % (int(eps.get("n")), mode_txt or "-",
                        _fmt_tokens(eps.get("tokens_med")),
                        round(float(eps.get("cut_rate") or 0) * 100),
                        round(float(eps.get("web_ratio") or 0) * 100),
                        json.dumps(eps.get("rounds_cap_med") or {},
                                   ensure_ascii=False)))
    if eps.get("latest_run_id"):
        lines.append("- 最近跑次 %s（%s，%s tokens）"
                     % (eps.get("latest_run_id"), eps.get("latest_mode") or "-",
                        _fmt_tokens(eps.get("latest_tokens"))))
    if lessons == 0 and pbn == 0 and not eps.get("n"):
        base["reason"] = "无可用的记忆读数（不注入空壳）"
        return base
    text = "\n".join(lines)
    cap = max(160, int(cfg.get("max_chars") or 1600))
    truncated = False
    if len(text) > cap:
        text = text[:cap - 1].rstrip() + "…"
        truncated = True
    out = {"text": text, "chars": len(text), "injected": bool(text.strip()),
           "truncated": truncated, "cache": "miss",
           "lessons": lessons, "playbook": pbn,
           "sources": ["MEMORY.md", "playbook.jsonl", "episodes.jsonl"],
           "reason": "项目相关题 → 注入 %d 字相关性摘要" % len(text)}
    with _MEM_LOCK:
        if len(_MEM_CACHE) >= int(cfg.get("cache_entries") or _MEM_CACHE_MAX):
            _MEM_CACHE.clear()
        _MEM_CACHE[key] = copy.deepcopy(out)
    return out


def _evidence_num(text: str) -> int:
    """从 MEMORY.md 经验行里取「证据 N」的数字（排序用）。"""
    m = re.search(r"证据\s*(\d+)", str(text or ""))
    try:
        return int(m.group(1)) if m else 0
    except (TypeError, ValueError):
        return 0


def _fmt_tokens(n) -> str:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return "0"
    if v >= 1e6:
        return "%.2fM" % (v / 1e6)
    if v >= 1e3:
        return "%.0fk" % (v / 1e3)
    return str(int(v))


# ── M4 质量预测 ────────────────────────────────────────────────
def m4_prediction(question: str, history: dict, preset: dict | None = None) -> dict:
    """M4 auto-fused：kNN+ridge 质量预测 + 三模式选档（失败即关闭，不影响计划）。"""
    ds = preset or load_preset()
    if not (ds.get("m4") or {}).get("enabled", True):
        return {"enabled": False, "ok": False, "reason": "预设关闭 M4 预测"}
    for _sp in (str(PROJECT_ROOT), str(PROJECT_ROOT / "dgtf_engine")):
        if _sp not in sys.path:
            sys.path.insert(0, _sp)
    hist = history.get("episodes") or {}
    m4_hist = {"calls_med": hist.get("calls_med") or 0,
               "tokens_med": hist.get("tokens_med") or 0,
               "tri_rate": hist.get("tri_rate") or 0,
               "cut_rate": hist.get("cut_rate") or 0}
    try:
        from dgtf_v2.mode_fusion import (fused_plan, kind_of_question,
                                         recommend_scenario)
        from dgtf_v2.quality_predictor import question_features
        feats = question_features(question) or {}
        plan = fused_plan(cascade=True, features=feats, history=m4_hist)
        # [Round 4] 实测场景矩阵：题面→场景桶→推荐档（含事实题强制联网规则）。
        #   只做 plan 字段与审计，不改变既有 opts 决策路径（失败即忽略）。
        _scenario = {}
        try:
            _kind = kind_of_question(question)
            _scenario = recommend_scenario(_kind, min_quality=0.9,
                                           prefer="quality")
            _scenario["kind"] = _kind
        except Exception as _se:  # noqa: BLE001
            _scenario = {"error": "%s: %s" % (type(_se).__name__, _se)}
        first = plan.get("first") or {}
        # [Round 2] 保形下界与弃权状态进入 plan，供 App/审计侧读取
        #   （无 conformal 段时为空 dict，旧行为不变）。
        return {"enabled": True, "ok": True, "features": feats,
                "first_mode": str(first.get("mode") or ""),
                "first_reason": str(first.get("reason") or ""),
                # [V2.2.20] 统一模式体系回显：模式专属配置与最优性证据
                "first_config": dict(first.get("config") or {}),
                "optimality": plan.get("optimality") or {},
                "policy": plan.get("policy") or "",
                "quality_prediction": plan.get("quality_prediction") or {},
                "quality_prediction_lower": plan.get("quality_prediction_lower") or {},
                "conformal": plan.get("conformal") or {},
                "quality_prediction_kind": plan.get("quality_prediction_kind") or "",
                "quality_guard": plan.get("quality_guard") or "",
                "scenario": _scenario,
                "history_input": m4_hist}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "ok": False,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "history_input": m4_hist}


# ── 预算守卫 ───────────────────────────────────────────────────
def _latest_packed_raw_max() -> int:
    """从最新 packed 产物读引擎预算上限（budget.raw_max_tokens）；失败返回 0。"""
    try:
        packs = sorted((PROJECT_ROOT / "outputs").glob("*.packed.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        if not packs:
            return 0
        d = json.loads(packs[0].read_text(encoding="utf-8", errors="replace"))
        return int((d.get("budget") or {}).get("raw_max_tokens") or 0)
    except Exception:  # noqa: BLE001
        return 0


def budget_guard(history: dict, preset: dict | None = None, *,
                 balance_cny=_UNSET, is_mock: bool = False) -> dict:
    """预算守卫：余额 + 历史中位 tokens + 引擎预算上限 → ok|degrade|warn。

    fail-open：余额查询失败/未知时 decision=ok（继续），只写 warning。
    """
    ds = preset or load_preset()
    cfg = dict(_BUILTIN_DS["budget"])
    cfg.update(ds.get("budget") or {})
    eps = history.get("episodes") or {}
    raw_max = int(cfg.get("raw_max_tokens_fallback") or 2000000)
    if not is_mock:
        _raw = _latest_packed_raw_max()
        if _raw > 0:
            raw_max = _raw
    est_tokens = int(eps.get("tokens_med") or 0) or int(
        cfg.get("est_tokens_default") or 1300000)
    # 引擎预算上限推断：历史中位与 raw_max 取小（超预算会硬停，估费用按实际可跑量）。
    est_tokens = max(50_000, min(est_tokens, int(raw_max * 0.97)))
    cny_per_m = float(cfg.get("cny_per_million_tokens") or 2.0)
    est_cost = round(est_tokens / 1_000_000.0 * cny_per_m, 2)
    # 余额：显式传入 > 环境变量（可测） > runner.current_balance()（mock 跳过网络）
    src = ""
    balance = None
    if balance_cny is not _UNSET:
        try:
            balance = float(balance_cny)
        except (TypeError, ValueError):
            balance = None
        src = "explicit"
    if balance is None and balance_cny is _UNSET:
        env_b = os.getenv("DGTF_DAOSHENG_BALANCE_CNY", "").strip()
        if env_b:
            try:
                balance = float(env_b)
                src = "env"
            except ValueError:
                balance = None
        elif is_mock:
            src = "mock-skip"
        else:
            src = "runner"
            try:
                import engine_runner as _runner
                balance = _runner.current_balance()
            except Exception:  # noqa: BLE001
                balance = None
    warn_b = float(cfg.get("warn_below_cny") or 4.0)
    degrade_b = float(cfg.get("degrade_below_cny") or 8.0)
    out = {"balance_cny": (round(balance, 2) if isinstance(balance, (int, float))
                           else None),
           "balance_source": src, "est_tokens": int(est_tokens),
           "est_cost_cny": est_cost, "raw_max_tokens": int(raw_max),
           "cny_per_million_tokens": cny_per_m,
           "fail_open": False, "decision": "ok", "reason": ""}
    if not isinstance(balance, (int, float)):
        out["fail_open"] = True
        out["budget_level"] = "unknown"
        out["reason"] = ("余额未知（%s）→ fail-open：不拒绝任务，按质量档继续"
                         % ("mock 跳过查询" if src == "mock-skip" else "查询失败"))
        return out
    # ★ [V2.2.24] 预算层级（动态配置用；decision 旧语义保持不变）
    _est_mult = float(cfg.get("critical_est_mult") or 1.2)
    _reserve = float(cfg.get("reserve_ratio") or 0.5)
    out["reserve_ratio"] = _reserve
    out["est_affordable"] = bool(balance >= est_cost / max(1e-6, _reserve))
    if balance < max(1.0, est_cost * _est_mult):
        out["budget_level"] = "critical"
    elif balance < warn_b:
        out["budget_level"] = "warn"
    elif balance < degrade_b:
        out["budget_level"] = "degrade"
    else:
        out["budget_level"] = "ok"
    if balance < warn_b:
        out["decision"] = "warn"
        out["reason"] = ("余额 ¥%.2f < ¥%.0f：任务仍可创建，但请立即确认额度"
                         "（自动降级 daosheng_fast）" % (balance, warn_b))
    elif balance < degrade_b:
        out["decision"] = "degrade"
        out["reason"] = ("余额 ¥%.2f < ¥%.0f：自动降级 daosheng_fast（低圈+thinking off）"
                         % (balance, degrade_b))
    else:
        out["decision"] = "ok"
        out["reason"] = "余额 ¥%.2f ≥ ¥%.0f：允许质量档（估算 %.2fM tokens / ¥%.2f）" % (
            balance, degrade_b, est_tokens / 1e6, est_cost)
    return out


# ── 动态配置优化（预算/质量/时延多目标；纯函数）──────────────────
_DYN_TIER_FLOOR = {"project": 0.95, "quality_first": 0.95, "default": 0.90}
_WEB_TOKENS_EXTRA = 0.10   # 事实题 web on 的 token 增量（实测 ~+13.6 万 / 1.15M）

# ★ [V2.2.26] route 子集感知成本模型（3 臂有界云实测校准：
#   docs/dynamic_cost_calibration_20261029.json；fast/web-off/单层单圈口径）
_CALIB = {
    "u0": 31620.0,          # 层 0 每圈 tokens（fast；R3=63,240/2）
    "u1": 37119.0,          # 层 1 每圈 tokens（fast；R1）
    "multi_overlap": 0.905, # 两层可加性的重叠系数（R2 实测/可加预测）
    "full_default_tokens": 816983.0,   # fast 四层默认圈数（2,3,2,2）整单实测
    "web_fact_factor": 1.12, # 事实题 web on 的 token 增量（实测约 +12%）
    # App 全流程开销（自省/质量门/归档；1 臂云实测 34,727/31,620=1.098；
    # docs/app_path_cost_calibration_20261029.json）
    "app_overhead": 1.10,
    "fast_default_rounds": {"0": 2, "1": 3, "both": 2, "all": 2},
}
# ★ [V2.2.32] 题型级实测省层收益（route0 vs full，rounds=1）：
#   fact：6 跑 tokens 61-67k 无显著差异（收益≈0）；reasoning：route0 39.6-46k vs
#   full 70.7-74.9k（约省 39%）。证据见 docs/route_subset_*_ab_20261029.json
_ROUTE_SAVINGS_EVIDENCE = {
    "fact": {"saved_pct": 0.0, "n": 6,
             "evidence": "docs/route_subset_multisample_20261029.json",
             "note": "6 跑 route0/0,1/full tokens 61-67k 无显著差异"},
    "reasoning": {"saved_pct": 0.39, "n": 4,
                  "evidence": "docs/route_subset_reasoning_ab_20261029.json",
                  "note": "reasoning route0 39.6-46k vs full 70.7-74.9k（约省 39%）",
                  "high_rounds": {"saved_pct": 0.0, "n": 2, "min_total_rounds": 5,
                                  "evidence": "docs/route_reasoning_rounds2_ab_20261029.json",
                                  "note": "rounds=2/层时 route0 65.6k vs full 62.3k，"
                                          "无省层收益（全层反而略省）"}},
    "choice": {"saved_pct": 0.40, "n": 4,
               "evidence": "docs/route_subset_choice_ab_20261029.json",
               "note": "choice route0 50.6-50.9k vs full 85.3k（约省 40%）"},
}

# ★ [V2.2.33] 短程实测锚点（App 路径实际 tokens，B 模式，每层 1 圈口径）：
#   事实题（web on）6 跑：full≈65,427 / route0≈65,360 / route0,1≈60,962；
#   reasoning（web off）4 跑：full≈72,799 / route0≈42,798。
#   动态配置对短跑直接用实测锚点（不再用四层可加模型，后者高估 10 倍以上）。
_SHORT_RUN_ANCHORS = {
    "fact": {"web": "on", "mode": "B",
             "full": 65427.0, "0": 65360.0, "0,1": 60962.0, "n": 6,
             "evidence": "docs/route_subset_multisample_20261029.json"},
    "reasoning": {"web": "off", "mode": "B",
                  "full": 72799.0, "0": 42798.0, "n": 4,
                  "evidence": "docs/route_subset_reasoning_ab_20261029.json"},
    "choice": {"web": "on", "mode": "B",
               "full": 85342.0, "0": 50752.0, "n": 4,
               "evidence": "docs/route_subset_choice_ab_20261029.json"},
}


# ★ [V2.2.35] 高圈锚点（reasoning rounds=2/层，总 8 圈）：route0 65,608 / full 62,317
_LONG_RUN_ANCHORS = {
    "fact": {"web": "on", "mode": "B", "min_total": 5, "max_total": 10,
             "full": 67753.0, "n": 2,
             "evidence": "docs/quality_retry_ab_20261029.json"},
    "reasoning": {"web": "off", "mode": "B", "min_total": 5, "max_total": 10,
                  "full": 62317.0, "0": 65608.0, "n": 2,
                  "evidence": "docs/route_reasoning_rounds2_ab_20261029.json"},
}


def _long_run_anchor(kind, web, route, rounds, engine_mode):
    """高圈实测锚点（reasoning 总圈数 5-10）；无匹配返回 None。"""
    _a = _LONG_RUN_ANCHORS.get(str(kind or ""))
    if not _a or engine_mode != _a.get("mode") or str(web or "") != _a.get("web"):
        return None
    entries = [e.strip() for e in str(route or "").split(",") if e.strip()]
    total = 0
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            try:
                total += int(part.rsplit(":", 1)[1])
            except (TypeError, ValueError):
                total += 1
        elif part.isdigit():
            total += int(part) * max(1, len(entries))
    if not (_a.get("min_total", 5) <= total <= _a.get("max_total", 10)):
        return None
    key = ",".join(entries)
    if key in _a:
        return float(_a[key])
    if len(entries) == 4:
        return float(_a["full"])
    if "0" in entries:
        return float(_a.get("0") or _a["full"])
    return float(_a["full"])


def _short_run_anchor(kind, web, route, rounds, engine_mode):
    """短跑（总圈数<=4）的实测 token 锚点；无匹配返回 None。"""
    _a = _SHORT_RUN_ANCHORS.get(str(kind or ""))
    if not _a or engine_mode != _a.get("mode"):
        return None
    if str(web or "") != _a.get("web"):
        return None
    entries = [e.strip() for e in str(route or "").split(",") if e.strip()]
    total = 0
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            try:
                total += int(part.rsplit(":", 1)[1])
            except (TypeError, ValueError):
                total += 1
        elif part.isdigit():
            total += int(part) * max(1, len(entries))
    if total <= 0 or total > 4:
        return None
    key = ",".join(entries)
    if key in _a:
        return float(_a[key])
    if len(entries) == 4:
        return float(_a["full"])
    # 其他子集：按 route0 与 full 的中间值保守取
    if "0" in entries:
        return float(_a.get("0") or _a["full"])
    return float(_a["full"])

# ★ [V2.2.36] 项目背景注入成本（A/B：默认注入 48,173 vs 关闭 42,511，+5,662 tokens）
# ★ [V2.2.43] fact+web on 质量证据（2 跑均 verified；加圈未提升质量且 rounds2 更省）
# ★ [V2.2.44] 题型 verified 期望矩阵（真跑证据；加圈均未提升）
_QUALITY_EXPECTATION = {
    "fact_web_on": {"verified": 2, "n": 2,
                    "evidence": "docs/quality_retry_ab_20261029.json"},
    "reasoning": {"verified": 0, "n": 6,
                  "evidence": ["docs/route_subset_reasoning_ab_20261029.json",
                               "docs/route_reasoning_rounds2_ab_20261029.json"]},
    "choice": {"verified": 0, "n": 6,
               "evidence": ["docs/route_subset_choice_ab_20261029.json",
                            "docs/choice_rounds_ab_20261029.json"]},
    "project": {"verified": 0, "n": 4,
                "evidence": ["docs/project_context_ab_20261029.json",
                             "docs/project_context_rounds2_ab_20261029.json"]},
}

_QUALITY_RETRY_EVIDENCE = {
    "fact_web_on": {"verified": 2, "n": 2,
                    "tokens": [85362, 67753],
                    "evidence": "docs/quality_retry_ab_20261029.json",
                    "note": "fact+web on 两臂均 verified；rounds2 更省（67.8k vs 85.4k）"},
}

_CONTEXT_COST = {"project": {"tokens": 5662, "n": 2,
                             "evidence": "docs/project_context_ab_20261029.json",
                             "note": "项目题 RAG+EML 注入实测 +5,662 tokens（约 ¥0.011）"}}

_un0, _un1 = _CALIB["u0"], _CALIB["u1"]
_avg = (_un0 + _un1) / 2.0
_base01 = 2 * _un0 + 3 * _un1
_remain = max(1.0, _CALIB["full_default_tokens"] - _base01)
_uB = _remain / (2 + 2 * (4.0 / 3.0))
_CALIB["both"] = round(_uB, 1)
_CALIB["all"] = round(_uB * 4.0 / 3.0, 1)


def _route_round_tokens(route, rounds, engine_mode="fast", web="off",
                        kind="") -> float:
    """层子集 × 圈数的 token 估算（fast 校准；其他 mode 按 MODES 比例缩放）。"""
    import re as _re
    entries = [e.strip() for e in str(route or "").split(",") if e.strip()]
    if not entries:
        entries = ["0", "1", "both", "all"]
    rmap = dict(_CALIB["fast_default_rounds"])
    _parts = [p.strip() for p in str(rounds or "").split(",") if p.strip()]
    if _parts and all(":" not in p and p.isdigit() for p in _parts):
        rmap = {e: int(_parts[0]) for e in entries}
    else:
        for part in _parts:
            if ":" in part:
                k, v = part.rsplit(":", 1)
                try:
                    rmap[k.strip()] = int(v)
                except (TypeError, ValueError):
                    pass
    tok = 0.0
    for e in entries:
        if e == "0":
            unit = _un0
        elif e == "1":
            unit = _un1
        else:
            unit = _CALIB.get(e)
        if unit:
            tok += float(unit) * float(rmap.get(e, 1) or 1)
    # 两层 0/1 的实测重叠系数只在"纯 0/1 子集"生效；
    # 含 both/all 时单位已按整单实测反解，不再叠系数（避免双重打折）。
    if len(entries) > 1 and not any(e in ("both", "all") for e in entries):
        tok *= _CALIB["multi_overlap"]
    # mode 比例：以 fast 为基准，其余按 MODES tokens 比例
    try:
        from dgtf_v2.mode_fusion import MODES as _MODES
        _fast = float((_MODES.get("fast") or {}).get("tokens") or 816983.0)
        _mode = float((_MODES.get(engine_mode) or {}).get("tokens") or _fast)
        tok *= (_mode / _fast)
    except Exception:  # noqa: BLE001
        pass
    if str(web) == "on" and str(kind) == "fact":
        tok *= _CALIB["web_fact_factor"]
    return round(tok, 1)


def _rounds_count(rounds) -> int:
    """解析 rounds 字符串里的总圈数（auto/空 => 0，表示交给引擎）。"""
    n = 0
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            try:
                n += int(part.rsplit(":", 1)[1])
            except (TypeError, ValueError):
                continue
    return n


def dynamic_config(*, ds: dict | None = None, tier: str = "quality",
                   engine_mode: str = "B", parallel: str = "B",
                   thinking: str = "auto", effort: str = "auto",
                   web: str = "auto", rounds="auto",
                   budget_guard: dict | None = None,
                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None,
                   project_related: bool = False, route=None,
                   cache: dict | None = None,
                   context_injected: bool = False) -> dict:
    """在现有资源（余额/历史/场景）上枚举可行配置，选质量最高且成本可控者。

    返回可审计 dict；applied 只含安全可覆盖项（rounds/web），显式 opts 永远优先。
    """
    ds = ds or load_preset()
    bg = dict(budget_guard or {})
    opts = dict(opts or {})
    cfg = dict(_BUILTIN_DS["budget"])
    cfg.update(ds.get("budget") or {})
    cny_m = float(cfg.get("cny_per_million_tokens") or 2.0)
    reserve = float(cfg.get("reserve_ratio") or 0.5)
    balance = bg.get("balance_cny")
    level = str(bg.get("budget_level") or "ok")
    kind = str((scenario or {}).get("kind") or "")
    try:
        from dgtf_v2.mode_fusion import MODES as _MODES
    except Exception:  # noqa: BLE001
        _MODES = {}
    base = dict(_MODES.get(engine_mode) or {})
    base_q = float(base.get("quality") or (0.93 if engine_mode == "fast" else 1.0))
    base_tok = float(base.get("tokens") or (816983 if engine_mode == "fast" else 1269082))
    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if (project_related or kind == "project") else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))
    # ★ fast 档的实测质量上限≈0.93：降级到 fast 后若仍卡 0.95 会假 fallback，
    #   把下限对齐到 fast 可满足档（0.90）；quality 档仍用项目/quality_first 0.95。
    if tier == "fast":
        floor = min(floor, _DYN_TIER_FLOOR["default"])
    # ★ [V2.2.25] 候选 rounds：按 tier 枚举（quality 保持 auto/quality 档；
    #   fast 才做 fast/economy/critical 多目标，由成本约束 + 质量排序选择）。
    _rounds_opts: list[str] = []
    if opts.get("rounds"):
        # 显式轮数：只评估这一档（锁定语义；成本才能用短程实测锚点）
        _pool = (str(opts.get("rounds")),)
    elif tier == "fast":
        _pool = (ds.get("rounds_fast"), cfg.get("rounds_economy"),
                 cfg.get("rounds_critical"))
    else:
        _pool = ((str(rounds) if str(rounds or "") not in ("", "auto")
                  else "auto"),
                 ((ds.get("rounds_quality") or "0:3,1:3,both:4,all:4")
                  if quality_first else None))
    for _rc in _pool:
        if _rc and str(_rc) not in _rounds_opts:
            _rounds_opts.append(str(_rc))
    if not _rounds_opts:
        _rounds_opts = ["auto"]
    _web_opts = ["on"] if require_web else ([str(web)] if web not in ("", "auto") else ["off"])
    ref_count = max(1, _rounds_count("0:2,1:3,both:2,all:2"))
    candidates = []
    for rd in _rounds_opts:
        cnt = _rounds_count(rd)
        factor = 1.0 if cnt <= 0 else max(0.3, min(1.3, cnt / float(ref_count)))
        for wb in _web_opts:
            _anchor = _short_run_anchor(kind, wb, route, rd, engine_mode)
            if _anchor is None:
                _anchor = _long_run_anchor(kind, wb, route, rd, engine_mode)
                _anchor_src = "measured_long_anchor"
            else:
                _anchor_src = "measured_short_anchor"
            if _anchor is not None:
                tok = _anchor
                _cost_source = _anchor_src
            else:
                try:
                    tok = _route_round_tokens(route, rd, engine_mode=engine_mode,
                                              web=wb, kind=kind)
                except Exception:  # noqa: BLE001
                    tok = base_tok * factor
                tok = tok * float(_CALIB.get("app_overhead") or 1.0)
                _cost_source = "route_subset_rounds.v1+app_overhead"
            _ctx_cost = 0.0
            if context_injected:
                _ctx_cost = float((_CONTEXT_COST.get("project") or {}).get("tokens") or 0)
                tok += _ctx_cost
            q = base_q
            if wb == "on" and kind == "fact":
                # token 增量已在 _route_round_tokens 内计入，这里只抬质量
                q = max(q, 0.955)          # 事实 web on 实测 0.958（fast）
            if factor < 1.0:
                q -= (1.0 - factor) * 0.03  # 圈数减少的保守质量折扣（线性）
            cost = round(tok / 1e6 * cny_m, 2)
            # ★ [V2.2.25] 缓存命中感知：精确命中 ⇒ 实际成本按 10% 计（近似零成本）
            _cache_hit = bool((cache or {}).get("exact")
                              or (cache or {}).get("semantic_hit"))
            cost_eff = round(cost * 0.1, 2) if _cache_hit else cost
            feasible = True
            if isinstance(balance, (int, float)):
                # 估算误差容差 ±20%（模型误差 + App 开销）：预算线附近保留更优档
                feasible = cost_eff <= max(0.01, float(balance) * reserve) * 1.20
            candidates.append({"engine_mode": engine_mode, "parallel": parallel,
                               "thinking": thinking, "effort": effort, "web": wb,
                               "rounds": rd, "est_quality": round(q, 4),
                               "est_tokens": int(tok), "est_cost_cny": cost,
                               "est_cost_effective_cny": cost_eff,
                               "cache_hit": _cache_hit,
                               "cache_kind": ("exact" if (cache or {}).get("exact")
                                              else "semantic" if (cache or {}).get("semantic_hit")
                                              else ""),
                               "budget_level": level, "feasible": bool(feasible),
                               "cost_source": _cost_source,
                               "context_tokens": int(_ctx_cost)})
    feasible_cs = [c for c in candidates
                   if c["feasible"] and c["est_quality"] >= floor - 1e-9]
    fallback = not feasible_cs
    if feasible_cs:
        chosen = max(feasible_cs, key=lambda c: (c["est_quality"], -c["est_cost_cny"]))
    else:
        chosen = min(candidates, key=lambda c: (c["est_cost_cny"], -c["est_quality"]))
    applied = {}
    if not isinstance(balance, (int, float)):
        # ★ 余额未知（fail-open）：只审计候选，保持原配置（不改 rounds/web）
        _same = next((c for c in candidates
                      if str(c["rounds"]) == str(rounds or "auto")), None)             or candidates[0]
        chosen = _same
        applied = {}
        fallback = False
        why = "余额未知 → fail-open：保持原配置（候选仅供审计）"
        return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
                "balance_cny": balance, "reserve_ratio": reserve,
                "quality_floor": round(floor, 4),
                "require_web": bool(require_web), "scenario": kind,
                "route": route,
                "cache_hit": bool((cache or {}).get("exact")
                                  or (cache or {}).get("semantic_hit")),
                "candidates": candidates, "chosen": chosen,
                "applied": applied, "fallback": fallback, "why": why,
                "regret": 0.0}
    if not opts.get("rounds") and str(chosen["rounds"]) != str(rounds or "auto"):
        applied["rounds"] = chosen["rounds"]
    # web=auto 表示"交给引擎自决"：动态配置只记录 chosen，不写 opts
    # （否则会把 auto 落成具体值，改变 apply_plan 的既有语义）。
    if (not opts.get("web") and str(web) not in ("", "auto")
            and str(chosen["web"]) != str(web)):
        applied["web"] = chosen["web"]
    _cache_hit0 = bool((cache or {}).get("exact")
                       or (cache or {}).get("semantic_hit"))
    why = ("预算层级=%s 余额=%s 预留=%.0f%%%s → 选 quality=%.3f/tokens=%d/¥%.2f"
           % (level, ("¥%.2f" % float(balance)) if isinstance(balance, (int, float)) else "未知",
              reserve * 100, ("（缓存命中，按 10% 成本计）" if _cache_hit0 else ""),
              chosen["est_quality"], chosen["est_tokens"],
              chosen["est_cost_cny"]))
    return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
            "balance_cny": balance, "reserve_ratio": reserve,
            "quality_floor": round(floor, 4), "require_web": bool(require_web),
            "scenario": kind, "route": route, "cache_hit": _cache_hit0,
            "cost_model": "route_subset_rounds.v1",
            "app_overhead": float(_CALIB.get("app_overhead") or 1.0),
            "candidates": candidates, "chosen": chosen,
            "applied": applied, "fallback": fallback, "why": why,
            "context_cost": (dict(_CONTEXT_COST.get("project") or {})
                             if context_injected else {}),
            "regret": 0.0 if not fallback else None}


# ── 缓存命中预判 ───────────────────────────────────────────────
# ★ [V2.2.41] 语义缓存命中预判：对最近 verified 产物做 BGE 余弦（本地 8771，零 API）
_VERIFIED_CACHE_TTL_H = 168.0
_SEMANTIC_MIN_SIM = 0.98
# ★ [V2.2.42] 候选清单/命中结果双层缓存：避免每次 build_plan 重读 200+ packed
_SEM_CAND_TTL_S = 300.0
_SEM_PROBE_TTL_S = 120.0
_SEM_CAND_CACHE = {"ts": 0.0, "items": None}
_SEM_PROBE_CACHE: dict = {}
_SEM_INDEX_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "semantic_cache_index.json"
_SEM_PROBE_FILE = Path(__file__).resolve().parent.parent / "dgtf_memory" / "semantic_probe_index.json"


def _embed_batch(texts: list[str]):
    try:
        import json as _j
        import urllib.request as _u
        req = _u.Request(
            "http://127.0.0.1:8771/embed",
            data=_j.dumps({"texts": list(texts)}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with _u.urlopen(req, timeout=4) as resp:
            d = _j.loads(resp.read().decode("utf-8"))
        vs = d.get("vectors") or []
        return vs if len(vs) == len(texts) else None
    except Exception:  # noqa: BLE001
        return None


def _semantic_candidates():
    """verified 产物候选清单（按 mtime 倒序；缓存 300s，最多 40 条）。"""
    import time as _t
    now = _t.time()
    hit = _SEM_CAND_CACHE.get("items")
    if hit is not None and now - float(_SEM_CAND_CACHE.get("ts") or 0) < _SEM_CAND_TTL_S:
        return hit
    import json as _j
    # ★ [V2.2.45] 跨进程持久索引：进程重启后 300s 内复用磁盘候选清单
    try:
        if _SEM_INDEX_FILE.is_file():
            _disk = _j.loads(_SEM_INDEX_FILE.read_text(encoding="utf-8",
                                                      errors="replace"))
            _ts = float(_disk.get("ts") or 0)
            _items = _disk.get("items") or []
            if _items and now - _ts < _SEM_CAND_TTL_S:
                _restored = [(str(x[0]), str(x[1]), bool(x[2])) for x in _items
                             if isinstance(x, (list, tuple)) and len(x) >= 3]
                if _restored:
                    _SEM_CAND_CACHE["items"] = _restored
                    _SEM_CAND_CACHE["ts"] = _ts
                    return _restored
    except Exception:  # noqa: BLE001
        pass
    root = Path(__file__).resolve().parent.parent / "outputs"
    items = []
    try:
        packs = sorted(root.glob("*.packed.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:300]
    except Exception:  # noqa: BLE001
        packs = []
    for p in packs:
        try:
            if now - p.stat().st_mtime > _VERIFIED_CACHE_TTL_H * 3600:
                continue
            d = _j.loads(p.read_text(encoding="utf-8", errors="replace"))
            q = d.get("quality") or {}
            if not (q.get("answer_ready") and q.get("answer_quality") == "verified"):
                continue
            dq = str(d.get("question") or "")
            if not dq:
                continue
            items.append((str(p), dq,
                          bool((d.get("api_usage") or {}).get("web_enabled"))))
            if len(items) >= 200:
                break
        except Exception:  # noqa: BLE001
            continue
    _SEM_CAND_CACHE["items"] = items
    _SEM_CAND_CACHE["ts"] = now
    try:
        _SEM_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEM_INDEX_FILE.write_text(_j.dumps(
            {"ts": now, "items": [[p, q, bool(w)] for p, q, w in items]},
            ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return items


def _sem_probe_persist(key: tuple, ts: float, result) -> None:
    try:
        import json as _j
        items = {}
        if _SEM_PROBE_FILE.is_file():
            d = _j.loads(_SEM_PROBE_FILE.read_text(encoding="utf-8",
                                                  errors="replace"))
            items = dict(d.get("items") or {})
        items[str(key[0]) + "||" + str(key[1])] = [float(ts), result]
        if len(items) > 300:
            _old = sorted(items.items(), key=lambda kv: float((kv[1] or [0])[0]))
            items = dict(_old[-300:])
        _SEM_PROBE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEM_PROBE_FILE.write_text(_j.dumps({"items": items}, ensure_ascii=False),
                                   encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _semantic_cache_probe(question: str, opts: dict | None = None):
    """返回最近 verified 产物的最佳语义命中（>=0.98），否则 None（结果缓存 120s）。"""
    try:
        import json as _j
        import math as _m
        import time as _t
        want_web = str((opts or {}).get("web") or "")
        _key = (str(question or ""), want_web)
        now = _t.time()
        _ph = _SEM_PROBE_CACHE.get(_key)
        if _ph is not None and now - float(_ph[0]) < _SEM_PROBE_TTL_S:
            return _ph[1]
        # ★ [V2.2.47] 跨进程结果缓存：进程重启后 120s 内复用上次预判
        try:
            if _SEM_PROBE_FILE.is_file():
                _pd = _j.loads(_SEM_PROBE_FILE.read_text(encoding="utf-8",
                                                        errors="replace"))
                _pk = str(question or "") + "||" + want_web
                _pe = (_pd.get("items") or {}).get(_pk)
                if _pe and now - float((_pe[0] if isinstance(_pe, list) else 0) or 0) < _SEM_PROBE_TTL_S:
                    _SEM_PROBE_CACHE[_key] = (float(_pe[0]), _pe[1])
                    return _pe[1]
        except Exception:  # noqa: BLE001
            pass
        cand = []
        for _p, _dq, _web in _semantic_candidates():
            if want_web in ("on", "off") and _web != (want_web == "on"):
                continue
            cand.append((_p, _dq))
            if len(cand) >= 8:
                break
        if not cand:
            _SEM_PROBE_CACHE[_key] = (now, None)
            _sem_probe_persist(_key, now, None)
            return None
        vecs = _embed_batch([str(question or "")] + [c[1] for c in cand])
        if not vecs:
            _SEM_PROBE_CACHE[_key] = (now, None)
            return None
        v1 = vecs[0]
        n1 = _m.sqrt(sum(float(x) * float(x) for x in v1)) or 1.0
        best = None
        for (_p, dq), v2 in zip(cand, vecs[1:]):
            n2 = _m.sqrt(sum(float(x) * float(x) for x in v2)) or 1.0
            sim = sum(float(a) * float(b) for a, b in zip(v1, v2)) / (n1 * n2)
            if sim >= _SEMANTIC_MIN_SIM and (best is None or sim > best[0]):
                best = (sim, Path(_p).name.replace(".packed.json", ""))
        if not best:
            _SEM_PROBE_CACHE[_key] = (now, None)
            _sem_probe_persist(_key, now, None)
            return None
        sim, from_id = best
        _out = {"hit": True, "similarity": round(sim, 4),
                "from": from_id, "evidence": "BGE 余弦>=0.98"}
        _SEM_PROBE_CACHE[_key] = (now, _out)
        _sem_probe_persist(_key, now, _out)
        return _out
    except Exception:  # noqa: BLE001
        return None


def warm_semantic_cache(max_wait_s: float = 12.0) -> dict:
    """启动预热：构建候选索引（持久化）并批量 embedding，降低首任务预判延迟。"""
    try:
        import time as _t
        items = _semantic_candidates()
        if not items:
            return {"ok": False, "why": "no verified candidates"}
        qs = [q for _p, q, _w in items[:8]]
        deadline = _t.time() + max(0.0, float(max_wait_s or 0))
        vecs = None
        while True:
            vecs = _embed_batch(qs)
            if vecs or _t.time() >= deadline:
                break
            _t.sleep(1.5)
        return {"ok": bool(vecs), "candidates": len(items),
                "embedded": len(vecs or [])}
    except Exception as _e:  # noqa: BLE001
        return {"ok": False, "why": str(_e)}


def cache_prediction(question: str, opts: dict | None = None) -> dict:
    """精确/语义缓存命中预判（只读本地状态，不触发 embedding）。"""
    opts = dict(opts or {})
    out = {"exact": False, "exact_from": "", "semantic_capable": False,
           "semantic_min_similarity": 0.98, "note": ""}
    try:
        import engine_runner as _runner
        q = str(question or "")
        for t in _runner.list_tasks():
            if str(t.get("status")) != "done" or str(t.get("question") or "") != q:
                continue
            if not t.get("output_name"):
                continue
            oo = t.get("opts") or {}
            if (str(oo.get("web") or "") != str(opts.get("web") or "")
                    and (oo.get("web") in ("on", "off") or opts.get("web") in ("on", "off"))):
                continue
            out["exact"] = True
            out["exact_from"] = str(t.get("id") or "")
            break
    except Exception:  # noqa: BLE001
        pass
    try:
        out["semantic_capable"] = bool((MEMORY_DIR / "rag_index.json").is_file())
    except Exception:  # noqa: BLE001
        out["semantic_capable"] = False
    if not out["exact"] and out["semantic_capable"]:
        _probe = _semantic_cache_probe(question, opts)
        if _probe:
            out["semantic_hit"] = True
            out["semantic_similarity"] = _probe.get("similarity")
            out["semantic_from"] = _probe.get("from")
    if out["exact"]:
        out["note"] = "同题已完成的精确缓存候选：%s（真实任务会直接复用产物）" % out["exact_from"]
    elif out.get("semantic_hit"):
        out["note"] = ("语义缓存预判命中：%s（BGE 余弦 %.3f ≥ 0.98，真实任务可复用）"
                       % (out.get("semantic_from"), float(out.get("semantic_similarity") or 0)))
    elif out["semantic_capable"]:
        out["note"] = "精确缓存未命中；语义缓存可用（BGE 余弦 ≥0.98 才复用）"
    else:
        out["note"] = "精确/语义缓存均不可用（按正常跑次）"
    return out


# ── 计划生成 ───────────────────────────────────────────────────
def _scenario_of(m4: dict) -> dict:
    sc = (m4 or {}).get("scenario") or {}
    return sc if isinstance(sc, dict) else {}


def _choose_engine_mode(tier: str, m4: dict) -> tuple[str, str]:
    """按 tier + 实测场景矩阵选引擎模式。

    Round 5：场景规则真正生效（不只做审计字段）：
      · fact 场景要求 web + thinking ⇒ 预算档不得降到 fast（实测 fast 事实题
        0.474/needs_evidence），回 B 并强制 web on；
      · reasoning/choice 的预算档用 fast（实测 tokens −33%、墙钟 −68%、质量 −1pp）。
    """
    sc = _scenario_of(m4)
    kind = str(sc.get("kind") or "")
    if tier == "fast":
        if sc.get("require_web") or kind == "fact":
            # ★ [Round 23] 修复后重测：fast+web on 事实题 0.9472/0.9726 verified，
            #   tokens −34~44%、墙钟 −82% ⇒ 允许 fast（web 由场景规则强制 on）
            return "fast", ("预算档：fast + web on（实测事实题 0.9472/0.9726 "
                            "verified，tokens −34~44%、墙钟 −82%）")
        return "fast", ("预算档：fast（thinking off、低圈；实测推理 tokens −33%、"
                        "墙钟 −68%、质量 −1pp）")
    first = str((m4 or {}).get("first_mode") or "")
    if first in ("B", "serial"):
        return first, "M4 预测首选 %s（%s）" % (first, (m4 or {}).get("first_reason") or "-")
    return "B", "质量优先默认 B（历史实测 质量1.0 / 墙钟1064s）"


def build_plan(question: str, opts: dict | None = None, *,
               requested: str = "auto",
               project_related: bool | None = None,
               is_mock: bool = False,
               subprocess_predict=None,
               balance_cny=_UNSET) -> dict:
    """生成道生专属计划（只对 daosheng / daosheng_fast 调用）。

    返回可审计 dict：policy / plan 字段 / reason / budget_guard /
    context_injected / local_llm / m4 / memory / cache 预判。
    """
    t_begin = time.perf_counter()
    opts = dict(opts or {})
    preset = load_preset()
    ds = preset
    resolved = resolve_mode(requested, question, project_related)
    if resolved.get("id") == "standard":
        raise ValueError("standard 模式不走 daosheng plan（请用 resolve_mode 判定）")
    _prj = bool(resolved.get("project_related"))
    tier = "fast" if resolved["id"] == "daosheng_fast" else "quality"
    quality_first = bool(opts.get("quality_first")) and tier == "quality"
    warnings: list[str] = []
    if opts.get("profile"):
        warnings.append("用户显式 profile=%s 覆盖道生预设：引擎配置以用户 profile 为准"
                        % opts.get("profile"))

    history = read_history(ds)
    local = predict_route_rounds(question, ds, is_mock=is_mock,
                                 subprocess_predict=subprocess_predict)
    m4 = m4_prediction(question, history, ds)
    engine_mode, mode_reason = _choose_engine_mode(tier, m4)
    # ★ [Round 26] 本地服务可观测性：busy 时若预设要求本地自省，本次回云端（fail-open）
    _lm = local_llm_metrics(ds)
    _busy_fallback = False
    if _lm.get("ok") and _lm.get("busy"):
        _scm0 = str(ds.get("self_check_mode") or "auto")
        if _scm0 == "local":
            _busy_fallback = True
            warnings.append("本地服务忙（busy_now）→ 本次 self_check 改走云端 llm")
    bg = budget_guard(history, ds, balance_cny=balance_cny, is_mock=is_mock)
    degrade_reason = ""
    if tier == "quality" and bg.get("decision") in ("degrade", "warn"):
        _sc0 = _scenario_of(m4)
        if _sc0.get("require_web") or str(_sc0.get("kind") or "") == "fact":
            # ★ [Round 23] fast+web on 事实题已实测 verified 且更省 ⇒ 降级也允许 fast
            tier = "fast"
            engine_mode = "fast"
            mode_reason = ("预算守卫 %s → fast + 强制联网（事实题成本档）：%s"
                           % (bg.get("decision"), bg.get("reason") or ""))
            degrade_reason = str(bg.get("reason") or "")
            warnings.append("预算守卫触发：事实题降 fast（web 强制 on）")
        else:
            tier = "fast"
            engine_mode = "fast"
            mode_reason = "预算守卫 %s → %s" % (bg.get("decision"), bg.get("reason") or "")
            degrade_reason = str(bg.get("reason") or "")
            warnings.append("预算守卫触发：已自动降级 daosheng_fast")
    if tier == "quality" and bg.get("fail_open"):
        warnings.append("余额未知：fail-open 继续质量档（未因余额查询失败拒任务）")

    # ★ [V2.2.38] 余额续航预测：质量档前按估算成本检查"还能跑几次"
    _bud_cfg = dict(_BUILTIN_DS["budget"])
    _bud_cfg.update(ds.get("budget") or {})
    try:
        _reserve_runs = float(_bud_cfg.get("reserve_runs") or 2)
    except (TypeError, ValueError):
        _reserve_runs = 2.0
    _bal0 = bg.get("balance_cny")
    _est0 = float(bg.get("est_cost_cny") or 0)
    if (tier == "quality" and bg.get("decision") == "ok"
            and isinstance(_bal0, (int, float)) and _est0 > 0):
        _safe0 = float(_bal0) / _est0
        if _safe0 < _reserve_runs:
            tier = "fast"
            engine_mode = "fast"
            mode_reason = ("余额续航不足（¥%.2f/估¥%.2f≈%.1f 次 < reserve %.1f 次）"
                           "→ 降级 fast 保续航" % (float(_bal0), _est0, _safe0,
                                                    _reserve_runs))
            warnings.append("预算续航：估算只剩 %.1f 次 < reserve %.1f 次 → 降 fast"
                            % (_safe0, _reserve_runs))
    caps = engine_capabilities()
    supports = (caps.get("supports") or {}) if isinstance(caps, dict) else {}
    supports_cfg = (caps.get("supports_config") or {}) if isinstance(caps, dict) else {}

    def _mechanism_via(name: str):
        """新机制键生效通道：auto 走预设 config（--config 里有）；非 auto 才走 CLI flag。"""
        val = ds.get(name)
        if str(val) in ("auto", "llm", "cache") and supports_cfg.get(name):
            return "config", val
        if (supports.get(name) and not is_mock
                and str(val) not in ("auto", "llm", "cache", "None", "")):
            return "cli", val
        return None, None

    scm_via, scm = _mechanism_via("self_check_mode")
    if _busy_fallback:
        scm_via, scm = "busy-fallback", "llm"
    djm_via, djm = _mechanism_via("dual_judge_mode")
    # ★ [Round 58] 引擎 --dual-judge-mode 只接受 llm/cache/auto（无 local 档）；
    #   预设若写了 local，这里确定性回退 llm，避免透传非法 flag 直接把引擎打挂。
    _djm_raw = str(ds.get("dual_judge_mode") or "").strip().lower()
    if _djm_raw == "local" or str(djm or "").strip().lower() == "local":
        if _engine_supports_dual_judge_local():
            # 引擎已支持 local 档（dual_judge local 补丁已合并）⇒ 显式透传
            djm_via, djm = "local", "local"
        else:
            djm_via, djm = "local-unsupported-fallback", "llm"
            warnings.append("dual_judge 不支持 local 档（引擎仅 llm/cache/auto），已回退 llm")
    # history_fusion 的 auto 本来就是引擎默认（V2.2.2 已有 --history-fusion auto），
    # 记「engine-default」而不是假装 App 传了参数；显式 off/on 才走 CLI。
    hf = ds.get("history_fusion")
    if str(hf) == "auto":
        hf_via = "engine-default"
    elif supports.get("history_fusion") and not is_mock:
        hf_via = "cli"
    else:
        hf, hf_via = None, None

    # ★ [V2.2.23] route 安全门：本地 route 预测默认**不砍层**。
    #   route_policy:
    #     union（默认）: 预设 route ∪ 预测 route（预设为四层时结果恒四层，预测仅供审计/补充）
    #     preset       : 完全忽略预测（纯预设）
    #     predict      : 旧行为（预测非空即采用，可砍层；用于显式省层实验）
    _route_preset = _norm_route(ds.get("route"))
    _route_pred = [str(x) for x in (local.get("route") or []) if str(x)]
    _route_policy = str(ds.get("route_policy") or "union").strip().lower()
    if _route_policy not in ("union", "preset", "predict"):
        _route_policy = "union"
    if _route_policy == "predict":
        _route_list = _route_pred or _route_preset
        _route_source = "predict" if _route_pred else "preset"
    elif _route_policy == "preset":
        _route_list = _route_preset
        _route_source = "preset"
    else:  # union
        _route_list = list(_route_preset)
        for _e in _route_pred:
            if _e not in _route_list:
                _route_list.append(_e)
        _route_source = ("union" if _route_pred and _route_pred != _route_preset
                         else "preset")
    # ★ [V2.2.24] 动态依赖调整：补全层依赖（both ⇒ 0/1；all ⇒ both/0/1）
    _route_ordered, _route_added = route_with_deps(_route_list)
    _route_list = _route_ordered
    route = ",".join(_route_list)
    if _route_added:
        warnings.append("层依赖闭包：补 %s（both 需 0/1，all 需 both/0/1）"
                        % ",".join(_route_added))
    if _route_policy != "predict" and _route_pred and _route_pred != _route_preset:
        warnings.append("route 安全门（%s）：预测=%s 未砍层，实际=%s"
                        % (_route_policy, ",".join(_route_pred), route))
    # ★ [V2.2.20 / 方案 A] 道生支路接入统一模式体系：
    #   engine_mode（B/fast/serial）对应 MODE_CONFIGS 的专门配置作为默认值；
    #   道生预设显式值（rounds/rounds_quality/rounds_fast/parallel）与场景规则
    #   （事实/选项题强制 web）仍然优先 ⇒ 默认行为不变，配置来源统一 +
    #   引擎可据此启用运行期 dynamic_adjust。
    try:
        from dgtf_v2.mode_fusion import MODE_CONFIGS as _MODE_CONFIGS
        _unified_cfg = dict(_MODE_CONFIGS.get(engine_mode) or {})
    except Exception:  # noqa: BLE001
        _unified_cfg = {}
    if tier == "fast":
        rounds = ds.get("rounds_fast") or "0:2,1:3,both:2,all:2"
        # 统一模式配置：fast => parallel=B / thinking=off（实测 782s/817k 档）
        parallel = _unified_cfg.get("parallel") or "serial"
        thinking = _unified_cfg.get("thinking") or "off"
        effort = _unified_cfg.get("effort") or "auto"
        web = "off"
        _scf = _scenario_of(m4)
        if _scf.get("require_web") or str(_scf.get("kind") or "") == "fact":
            web = "on"
    else:
        rounds = (ds.get("rounds_quality") or "0:3,1:3,both:4,all:4") if (
            quality_first and bg.get("decision") == "ok") else (ds.get("rounds") or "auto")
        parallel = ds.get("parallel") or _unified_cfg.get("parallel") or "B"
        if engine_mode == "serial":
            parallel = _unified_cfg.get("parallel") or "serial"
        _think = str(ds.get("thinking") or "auto")
        _eff = str(ds.get("effort") or "auto")
        thinking = _unified_cfg.get("thinking") if _think in ("", "auto") \
            else _think
        effort = _unified_cfg.get("effort") if _eff in ("", "auto") else _eff
        thinking = thinking or "auto"
        effort = effort or "auto"
        web = ds.get("web") or "auto"
    #: 显式 rounds（道生质量档/快档）已锁定圈数 ⇒ 运行期动态调整不改圈。
    rounds_locked = str(rounds) not in ("", "auto", "None")
    if _unified_cfg:
        warnings.append(
            "统一模式配置：engine_mode=%s → parallel=%s/thinking=%s/effort=%s"
            "（rounds=%s%s）"
            % (engine_mode, parallel, thinking, effort, rounds,
               "，锁定" if rounds_locked else ""))

    qp_cfg = ds.get("quality_policy") or {}
    feats = (m4.get("features") if m4.get("ok") else None) or (
        local.get("features") if local.get("source") == "rules" else {}) or {}
    if _prj:
        quality_policy = str(qp_cfg.get("project") or "auto:verified")
    elif feats.get("fact"):
        quality_policy = str(qp_cfg.get("fact") or "auto:web-retry")
    else:
        quality_policy = str(qp_cfg.get("other") or "auto:stable")

    # [Round 5] 实测场景规则：事实题强制联网（web off 实测 0.444/unverified，
    # web on 0.958/verified；成本只多 ~13.6 万 tokens）。
    _sc1 = _scenario_of(m4)
    if (_sc1.get("require_web") or str(_sc1.get("kind") or "") == "fact") \
            and str(web) != "on":
        web = "on"
        warnings.append("场景规则：事实题强制联网（web on，实测 +0.51 质量）")

    # [Round 91] 选项题（A./B./C./D. ≥2）引擎侧可能判 fact：强制 web on 取证据
    _opt_n = len(re.findall(r"(?:^|[\s（(])[A-DＡＢＣＤ]\s*[.、)）．]",
                            str(question or "")))
    if _opt_n >= 2 and str(web) != "on":
        web = "on"
        warnings.append("选项题：A./B./C./D. ≥2 ⇒ 强制联网（引擎事实门需证据）")

    # ★ [V2.2.25] 缓存预判提前：动态配置需要知道"这次是否近似零成本"
    cache = cache_prediction(question, opts)
    # ★ [V2.2.24] 全链路动态配置：预算（余额/预留/层级）× 质量（场景下限）×
    #   成本（token 估算）多目标枚举，选可行解中质量最高、成本最低者。
    _require_web = bool(_sc1.get("require_web")
                        or str(_sc1.get("kind") or "") == "fact"
                        or _opt_n >= 2)
    # ★ [V2.2.27] 成本模型用"有效 route"：显式 opts.route 优先（否则会高估省层任务）
    _dyn_route = str(opts.get("route") or route)
    dyn = dynamic_config(ds=ds, tier=tier, engine_mode=engine_mode,
                         parallel=parallel, thinking=thinking, effort=effort,
                         web=web, rounds=rounds, budget_guard=bg,
                         scenario=_sc1, quality_first=quality_first,
                         require_web=_require_web, opts=opts,
                         project_related=_prj, route=_dyn_route, cache=cache,
                         context_injected=bool(
                             _prj and opts.get("project_context") is not False))
    _dyn_applied = dyn.get("applied") or {}
    if _dyn_applied.get("rounds"):
        rounds = str(_dyn_applied["rounds"])
        rounds_locked = True
        warnings.append("动态配置：预算层级=%s→圈数降为 %s"
                        % (dyn.get("budget_level"), rounds))
    if _dyn_applied.get("web"):
        web = str(_dyn_applied["web"])
    if dyn.get("fallback"):
        warnings.append("动态配置：无满足质量下限的可行解 → 取最低成本兜底"
                        "（质量下限 %.2f，余额 %s）"
                        % (dyn.get("quality_floor"), dyn.get("balance_cny")))
    # ★ [V2.2.28] 动态依赖调整：预算 warn/critical ⇒ 运行期 token 硬上限
    #   （est×1.5 的安全边界；显式 opts.max_tokens 永远优先）。
    budget_max_tokens = 0
    if (dyn.get("budget_level") in ("warn", "critical")
            and opts.get("max_tokens") in (None, "")):
        _est = int((dyn.get("chosen") or {}).get("est_tokens") or 0)
        if _est > 0:
            budget_max_tokens = max(20000, int(_est * 1.5 / 1000.0) * 1000)
            warnings.append("预算依赖：%s 档 ⇒ 运行期 max_tokens=%d（估算 %d×1.5）"
                            % (dyn.get("budget_level"), budget_max_tokens, _est))
            dyn.setdefault("applied", {})["max_tokens"] = budget_max_tokens
            dyn["budget_cap"] = {"max_tokens": budget_max_tokens,
                                 "based_on_est_tokens": _est,
                                 "why": "预算 %s 档的硬边界，防止估算偏差导致超支"
                                        % dyn.get("budget_level")}
    # ★ [V2.2.29] 墙钟硬上限：按估算 tokens / 保守速率折算分钟数（×1.5 安全边界）
    budget_max_minutes = 0
    if (dyn.get("budget_level") in ("warn", "critical")
            and opts.get("max_minutes") in (None, "")):
        _est2 = int((dyn.get("chosen") or {}).get("est_tokens") or 0)
        if _est2 > 0:
            _tps = 600.0  # 保守：500-1000 tokens/s 区间取下沿
            _sec = _est2 / _tps * 1.5
            budget_max_minutes = max(1, int((_sec + 59) // 60))
            warnings.append("预算依赖：%s 档 ⇒ 运行期 max_minutes=%d（估算 %d tokens）"
                            % (dyn.get("budget_level"), budget_max_minutes, _est2))
            dyn.setdefault("applied", {})["max_minutes"] = budget_max_minutes
            dyn.setdefault("budget_cap", {})["max_minutes"] = budget_max_minutes
    if budget_max_tokens:
        _ctx_tok = int((dyn.get("context_cost") or {}).get("tokens") or 0)
        dyn.setdefault("budget_cap", {})["context_tokens"] = _ctx_tok
        dyn["budget_cap"]["base_tokens"] = max(
            0, int((dyn.get("chosen") or {}).get("est_tokens") or 0) - _ctx_tok)
    # ★ [V2.2.30] 层子集质量风险标注：显式/预测省层未被单题 A/B 证实
    #   证据 docs/route_subset_quality_ab_20261029.json：
    #   route0=verified / route0,1=needs_evidence / full=verified+ready（单题单次，方差内）
    _route_entries = [e.strip() for e in str(_dyn_route or "").split(",") if e.strip()]
    _missing_layers = [e for e in ("0", "1", "both", "all")
                       if e not in _route_entries]
    if _missing_layers and (_require_web or _prj
                            or str(quality_policy or "").startswith("auto:verified")):
        dyn["route_quality_risk"] = {
            "level": "high" if (_prj or str(quality_policy or "").startswith("auto:verified"))
                     else "info",
            "missing": _missing_layers,
            "evidence": {"reasoning": "docs/route_subset_reasoning_ab_20261029.json",
                         "choice": "docs/route_subset_choice_ab_20261029.json"}.get(
                             str(_sc1.get("kind") or ""),
                             "docs/route_subset_multisample_20261029.json"),
            "evidence_prev": "docs/route_subset_quality_ab_20261029.json",
            "note": ("层子集质量未被证实：choice 4 跑 route0/full 均 needs_evidence（ready=0），"
                     "省层省 tokens 但质量未证明；显式省层保留但风险已记录，默认 union 不砍层"
                     if str(_sc1.get("kind") or "") == "choice" else
                     "层子集质量未被证实：reasoning 4 跑 route0/full 均 unverified（ready=0），"
                     "省层省 tokens 但质量未证明；显式省层保留但风险已记录，默认 union 不砍层"
                     if str(_sc1.get("kind") or "") == "reasoning" else
                     "层子集质量未被证实：6 跑 A/B 中 route0/route0,1 各 2/2 verified 但 "
                     "ready=0，full 1/2 verified+1/2 ready（方差主导）；显式省层保留但风险已记录，"
                     "默认 route_policy=union 不砍层"),
        }
        warnings.append("层子集质量风险：缺 %s（证据 route_subset_quality_ab；"
                        "默认 union 四层更稳）" % ",".join(_missing_layers))
    # ★ [V2.2.31] 省层收益判定：6 跑 A/B（route0/0,1/full ×2）实际 tokens 61-67k 无显著差异
    #   ⇒ 短程事实题的省层收益≈0，质量方差反而更大；这里把判定写入 plan 供审计/提示。
    _route_pruning = None
    if _missing_layers:
        _full_ref = "0,1,both,all"
        _est_rounds = str(opts.get("rounds") or rounds or "auto")
        try:
            _dyn_kind = str(_sc1.get("kind") or "")
            _full_tok = _route_round_tokens(
                _full_ref, _est_rounds, engine_mode=engine_mode, web=web,
                kind=_dyn_kind)
            _cur_tok = _route_round_tokens(
                _dyn_route, _est_rounds, engine_mode=engine_mode, web=web,
                kind=_dyn_kind)
            _overhead = float(_CALIB.get("app_overhead") or 1.0)
            _saved = max(0.0, (_full_tok - _cur_tok) * _overhead)
            _base = max(1.0, _full_tok * _overhead)
            _pct = round(_saved / _base, 3)
        except Exception:  # noqa: BLE001
            _saved, _pct = 0.0, 0.0
        _short_fact = (str(_sc1.get("kind") or "") == "fact"
                       and _require_web
                       and _rounds_count(_est_rounds) <= 6)
        _dyn_kind_key = str(_sc1.get("kind") or "")
        _meas = _ROUTE_SAVINGS_EVIDENCE.get(_dyn_kind_key)
        if _short_fact:
            _advice = "keep_four_layers"
            _why = ("6 跑 A/B 显示短程事实题 route0/0,1/full 实际 tokens 61-67k 无显著差异"
                    "（省层收益≈0），质量方差主导 ⇒ 不值得为省层承担质量风险")
            _ev = "docs/route_subset_multisample_20261029.json"
            _pct = 0.0
            _saved = 0.0
        elif (_meas and _meas.get("high_rounds")
              and _rounds_count(_est_rounds) >= int(
                  _meas["high_rounds"].get("min_total_rounds") or 99)):
            _hr = _meas["high_rounds"]
            _advice = "keep_four_layers"
            _why = ("%s 高圈实测省层收益≈0（n=%d：%s）⇒ 全层不更贵，保持四层"
                    % (_dyn_kind_key, int(_hr.get("n") or 0), _hr.get("note")))
            _ev = str(_hr.get("evidence") or "")
            _pct = float(_hr.get("saved_pct") or 0.0)
            _saved = 0.0
        elif _meas and float(_meas.get("saved_pct") or 0) >= 0.10:
            _advice = "subset_may_save"
            _why = ("%s 题型实测省层约 %.0f%% tokens（n=%d：%s）；仍需质量证据才能自动砍层"
                    % (_dyn_kind_key, float(_meas.get("saved_pct") or 0) * 100,
                       int(_meas.get("n") or 0), _meas.get("note")))
            _ev = str(_meas.get("evidence") or "")
            _pct = float(_meas.get("saved_pct") or _pct)
            _saved = max(_saved, _base * _pct)
        elif _meas and float(_meas.get("saved_pct") or 0) < 0.05:
            _advice = "keep_four_layers"
            _why = ("%s 题型实测省层收益≈0（n=%d：%s）⇒ 不值得承担质量风险"
                    % (_dyn_kind_key, int(_meas.get("n") or 0), _meas.get("note")))
            _ev = str(_meas.get("evidence") or "")
            _pct = float(_meas.get("saved_pct") or 0.0)
            _saved = _base * _pct
        elif _pct >= 0.10:
            _advice = "subset_may_save"
            _why = "模型估算省层可省 %.1f%% tokens（仍需质量证据）" % (_pct * 100)
            _ev = "docs/route_subset_multisample_20261029.json"
        else:
            _advice = "keep_four_layers"
            _why = "模型估算省层收益仅 %.1f%%，低于 10%% 阈值" % (_pct * 100)
            _ev = "docs/route_subset_multisample_20261029.json"
        _route_pruning = {"advice": _advice,
                          "saved_tokens_estimate": int(_saved),
                          "saved_pct_estimate": _pct,
                          "kind": _dyn_kind_key,
                          "evidence": _ev,
                          "note": _why}
        dyn["route_pruning"] = _route_pruning
        warnings.append("省层收益判定：%s（估算省 %d tokens/%.1f%%）"
                        % (_advice, int(_saved), _pct * 100))
    # ★ [V2.2.27] 阶段动态路由：预算紧张时 dual_judge 走 cache（不牺牲项目/quality_first）
    plan_extra_djm = ""
    if (dyn.get("budget_level") in ("warn", "critical")
            and not _prj and not quality_first
            and opts.get("dual_judge_mode") in (None, "")):
        _dj_sup = bool((caps.get("supports") or {}).get("dual_judge_mode"))
        if _dj_sup:
            plan_extra_djm = "cache"
            dyn.setdefault("applied", {})["dual_judge_mode"] = "cache"
            dyn["stage_routing"] = {"dual_judge_mode": "cache",
                                    "why": "预算层级=%s ⇒ 评审走 cache 降本"
                                           % dyn.get("budget_level")}
            warnings.append("阶段动态路由：预算%s ⇒ dual_judge=cache"
                            % dyn.get("budget_level"))
    # ★ [V2.2.37] quality-retry 决策显式化（advisory；本轮不改变 server 实际行为）：
    #   项目/verified 需要背景证据；事实题仅在预算 ok 时才建议 web-retry；
    #   预算 warn/critical 建议关闭 retry 以省成本。
    _kind_qr = str(_sc1.get("kind") or "")
    _qr = {"policy": str(quality_policy or "auto:stable"), "retry": False,
           "why": "", "advisory": True}
    if _prj or str(quality_policy or "").startswith("auto:verified"):
        _qe3 = _QUALITY_EXPECTATION.get("project") or {}
        _qr.update({"policy": "verified", "retry": False,
                    "expected_verified_pct": (
                        round(float(_qe3.get("verified") or 0)
                              / max(1, int(_qe3.get("n") or 1)), 2)
                        if _qe3 else None),
                    "evidence": _qe3.get("evidence"),
                    "evidence_note": ("project 实测 verified %d/%d"
                                      % (int(_qe3.get("verified") or 0),
                                         int(_qe3.get("n") or 1)) if _qe3 else None),
                    "why": "项目/verified 依赖背景证据，不建议关闭验证"})
    elif _kind_qr == "fact":
        _qe = _QUALITY_RETRY_EVIDENCE.get("fact_web_on") or {}
        _qr.update({"expected_verified_pct": (
            round(float(_qe.get("verified") or 0) / max(1, int(_qe.get("n") or 1)), 2)
            if _qe else None),
            "evidence": _qe.get("evidence"),
            "evidence_note": _qe.get("note")})
        if dyn.get("budget_level") == "ok":
            _qr.update({"policy": "auto:web-retry", "retry": True,
                        "why": "事实题且预算 ok ⇒ 建议保留 web-retry"
                               "（实测 2/2 verified，加圈未提升质量）"})
        else:
            _qr.update({"policy": "auto:stable", "retry": False,
                        "why": "预算 %s ⇒ 建议关闭 web-retry 省成本"
                               % dyn.get("budget_level")})
    else:
        _qe2 = _QUALITY_EXPECTATION.get(_kind_qr) or {}
        _qr.update({"policy": "auto:stable", "retry": False,
                    "expected_verified_pct": (
                        round(float(_qe2.get("verified") or 0)
                              / max(1, int(_qe2.get("n") or 1)), 2)
                        if _qe2 else None),
                    "evidence": _qe2.get("evidence"),
                    "evidence_note": ("%s 实测 verified %d/%d；加圈未提升质量"
                                      % (_kind_qr, int(_qe2.get("verified") or 0),
                                         int(_qe2.get("n") or 1)) if _qe2 else None),
                    "why": "非事实题不需要 retry（且加圈未提升质量）"})
    # ★ [V2.2.49] 选档建议（advisory）：该题型实测 verified=0 且预算 ok 时，
    #   质量档未带来"已验证"收益（fast 更省 tokens），但不改变实际 tier。
    try:
        _pct_adv = _qr.get("expected_verified_pct")
        if (tier == "quality" and dyn.get("budget_level") == "ok"
                and _pct_adv is not None and float(_pct_adv) <= 0.0):
            _qr["tier_advice"] = "fast"
            _qr["tier_advice_why"] = (
                "%s 实测 verified 0 次；质量档未带来验证收益，fast 可省 tokens"
                % _kind_qr if _kind_qr else "该题型实测 verified 0 次")
        else:
            _qr["tier_advice"] = "current"
            _qr["tier_advice_why"] = ""
    except Exception:  # noqa: BLE001
        _qr["tier_advice"] = "current"
        _qr["tier_advice_why"] = ""
    dyn["quality_retry"] = _qr
    # ★ [V2.2.38] 续航预测（用最终 chosen 成本；余额未知 => None）
    _ch_cost = float((dyn.get("chosen") or {}).get(
        "est_cost_effective_cny")
        or (dyn.get("chosen") or {}).get("est_cost_cny") or 0)
    if isinstance(bg.get("balance_cny"), (int, float)) and _ch_cost > 0:
        _bal = float(bg.get("balance_cny"))
        _safe = int(_bal // _ch_cost)
        dyn["budget_forecast"] = {
            "balance_cny": round(_bal, 2),
            "est_cost_cny": round(_ch_cost, 3),
            "balance_after_cny": round(max(0.0, _bal - _ch_cost), 2),
            "safe_runs": _safe,
            "reserve_runs": _reserve_runs,
            "advice": ("ok" if _safe >= _reserve_runs else "low_reserve"),
        }
    else:
        dyn["budget_forecast"] = None
    # ★ [V2.2.37] 缓存 ROI 读数（exact 已按 10%% 成本计；语义命中率未知→只报能力）
    _cache_allow = bool(dyn.get("budget_level") in ("warn", "critical"))
    _cache_age = (72.0 if dyn.get("budget_level") == "critical"
                  else 24.0 if dyn.get("budget_level") == "warn" else 0.0)
    dyn["cache_policy"] = {
        "allow_unverified": _cache_allow,
        "max_age_h": _cache_age,
        "why": ("预算 %s ⇒ 允许同题未验证产物复用（省整单，新鲜度≤%.0fh）"
                % (dyn.get("budget_level"), _cache_age)
                if _cache_allow
                else "预算充足 ⇒ 只复用 verified 产物"),
    }
    _roi_any = bool((cache or {}).get("exact")
                    or (cache or {}).get("semantic_hit"))
    dyn["cache_roi"] = {
        "exact": bool((cache or {}).get("exact")),
        "semantic_hit": bool((cache or {}).get("semantic_hit")),
        "semantic_similarity": (cache or {}).get("semantic_similarity"),
        "semantic_from": (cache or {}).get("semantic_from"),
        "semantic_capable": bool((cache or {}).get("semantic_capable")),
        "expected_saving_pct": 0.9 if _roi_any else 0.0,
        "evidence": "docs/semantic_cache_hit_20261029.json",
        "note": ("精确命中：成本已按 10%% 计" if (cache or {}).get("exact")
                 else "语义缓存预判命中（BGE 余弦 %.3f）：成本按 10%% 计"
                 % float((cache or {}).get("semantic_similarity") or 0)
                 if (cache or {}).get("semantic_hit")
                 else "语义缓存可用但未命中；仅报能力不估算收益"
                 if (cache or {}).get("semantic_capable")
                 else "无缓存可用"),
    }
    memory = memory_summary(question, ds, project_related=_prj, history=history)
    context_injected: list[str] = []
    if _prj:
        context_injected.append("project_context:RAG")
    if memory.get("injected"):
        context_injected.append("memory:EML(%d字)" % int(memory.get("chars") or 0))

    engine_desc = {"ok": bool(caps.get("ok")), "path": caps.get("path") or "",
                   "version": caps.get("version") or "",
                   "supports": supports, "supports_config": supports_cfg}
    if is_mock:
        warnings.append("mock 任务：不启动真实引擎；新机制键仅记录于预设 profile"
                        "（App 不传 CLI flag）")
    if not caps.get("ok"):
        warnings.append("引擎能力探测失败 → 新机制键按「缺省」处理")
    if local.get("source") == "http":
        local_desc = {"available": True, "source": "http",
                      "route": local.get("route"), "rounds": local.get("rounds"),
                      "latency_ms": local.get("latency_ms"), "url": local.get("url"),
                      "metrics": _lm}
    elif local.get("source") == "subprocess":
        local_desc = {"available": True, "source": "subprocess",
                      "route": local.get("route"), "rounds": local.get("rounds"),
                      "metrics": _lm}
    else:
        local_desc = {"available": False, "source": "rules",
                      "route": local.get("route"), "rounds": local.get("rounds"),
                      "why": local.get("why"), "attempts": local.get("attempts"),
                      "metrics": _lm}
    m4_desc = {k: m4.get(k) for k in
               ("enabled", "ok", "first_mode", "first_reason",
                "quality_prediction", "quality_prediction_lower",
                "conformal", "scenario", "quality_guard", "error",
                # [V2.2.20] 统一模式体系：模式专属配置 + 最优性证据
                "first_config", "optimality", "policy")}
    hist_desc = {k: (history.get("episodes") or {}).get(k) for k in
                 ("n", "mode_counts", "tokens_med", "calls_med", "cut_rate",
                  "web_ratio", "tri_rate", "latest_run_id")}
    reasons = [resolved.get("reason") or "", mode_reason]
    if local_desc["available"]:
        reasons.append("本地模型 HTTP 可用→route=%s" % ",".join(local.get("route") or []))
    else:
        _lerr = " ".join(str((x or {}).get("error") or "")
                          for x in (local.get("attempts") or [])).lower()
        if "timed out" in _lerr or "timeout" in _lerr:
            reasons.append("本地 route 超时（预算过紧）→规则回退（route=%s）" % route)
        else:
            reasons.append("本地服务不可达→规则回退（route=%s）" % route)
    _sc2 = _scenario_of(m4)
    if _sc2.get("kind"):
        reasons.append("场景=%s → 推荐 %s（%s）"
                       % (_sc2.get("kind"), _sc2.get("mode"),
                          (_sc2.get("run") or {}).get("quality")))
    if m4.get("ok") and m4.get("quality_prediction"):
        pred = m4.get("quality_prediction") or {}
        reasons.append("M4 预测 " + "/".join("%s=%.3f" % (k, float(v))
                                             for k, v in pred.items()))
    if degrade_reason:
        reasons.append("预算守卫：" + degrade_reason)
    if memory.get("injected"):
        reasons.append("已注入 EML 记忆 %d 字" % int(memory.get("chars") or 0))
    if cache.get("exact"):
        reasons.append("精确缓存命中预判：%s" % cache.get("exact_from"))
    elif cache.get("semantic_hit"):
        reasons.append("语义缓存命中预判：%s（余弦 %.3f）"
                       % (cache.get("semantic_from"),
                          float(cache.get("semantic_similarity") or 0)))
    plan = {
        "policy": POLICY,
        "mode_id": resolved["id"],
        "requested": resolved.get("requested"),
        "mode_source": resolved.get("source"),
        "tier": tier,
        "engine_mode": engine_mode,
        # ★ [V2.2.21] 融合标记：道生模式即标准模式；requested 保留原始入口
        "fused": True,
        "fused_from": str(resolved.get("requested") or ""),
        # [V2.2.20 方案 A] 统一模式体系：引擎据此启用 MODE_CONFIGS + dynamic_adjust
        "mode": engine_mode,
        "unified_config": dict(_unified_cfg or {}),
        "rounds_locked": bool(rounds_locked),
        "mode_reason": mode_reason,
        "quality_first": bool(quality_first),
        "preset": str(preset_path()),
        "preset_info": preset_info(),
        "route": route,
        # [V2.2.23] route 安全门读数（可审计）
        "route_policy": _route_policy,
        "route_source": _route_source,
        "route_prediction": list(_route_pred),
        # [V2.2.24] 动态依赖调整 + 动态配置优化
        "route_dependency_added": list(_route_added),
        "dynamic_opt": dyn,
        "rounds": rounds,
        "parallel": parallel,
        "web": web,
        "thinking": thinking,
        "effort": effort,
        "self_check_mode": scm,
        "self_check_mode_via": scm_via,
        "dual_judge_mode": (plan_extra_djm or djm),
        # ★ [V2.2.28] 预算 warn/critical 时的运行期 token 硬上限（0=不限）
        "max_tokens": budget_max_tokens,
        # ★ [V2.2.29] 同期墙钟硬上限（分钟；0=不限）
        "max_minutes": budget_max_minutes,
        # ★ [V2.2.37] quality-retry 决策（advisory）
        "quality_retry": _qr,
        "tier_advice": _qr.get("tier_advice"),
        # ★ [V2.2.43] fact+web on 质量证据（2/2 verified；加圈无效）
        "quality_evidence": _qr.get("evidence"),
        # ★ [V2.2.44] 题型 verified 期望矩阵（真跑证据，加圈均未提升）
        "quality_expectation": {
            "kind": _kind_qr,
            "expected_verified_pct": _qr.get("expected_verified_pct"),
            "matrix": dict(_QUALITY_EXPECTATION),
        },
        # ★ [V2.2.39] 预算紧张时允许复用"未验证"产物缓存（同题精确匹配，省整单）
        "allow_unverified_cache": bool(
            dyn.get("budget_level") in ("warn", "critical")),
        # ★ [V2.2.40] 未验证复用新鲜度上限（小时；0=不限）
        "cache_max_age_h": float(
            (dyn.get("cache_policy") or {}).get("max_age_h") or 0.0),
        "dual_judge_mode_via": djm_via,
        "history_fusion": hf,
        "history_fusion_via": hf_via,
        "quality_policy": quality_policy,
        "project_related": _prj,
        "project_context": _prj,
        "context_injected": context_injected,
        "memory": memory,
        "local_llm": local_desc,
        "m4": m4_desc,
        "scenario": _scenario_of(m4),
        "history": hist_desc,
        "cache": cache,
        "budget_guard": bg,
        "engine": engine_desc,
        "warnings": warnings,
        "elapsed_ms": 0,
    }
    plan["reason"] = "；".join([r for r in reasons if r])
    plan["elapsed_ms"] = round((time.perf_counter() - t_begin) * 1000, 1)
    plan["applied_opts"] = {}
    return plan


def apply_plan(plan: dict, opts: dict) -> dict:
    """把 plan 落成引擎 opts（**只补不改**：显式 opts 永远优先）。

    值为 None/""/"auto" 的不写（build_cmd 也会跳 auto，写了只是噪音）。
    返回 applied_opts（供响应回显「实际生效」）。
    """
    applied: dict = {}
    if not isinstance(opts, dict):
        return applied
    for k in ("mode", "route", "rounds", "parallel", "web", "thinking",
              "effort", "self_check_mode", "dual_judge_mode",
              "history_fusion", "max_tokens", "max_minutes",
              "allow_unverified_cache", "cache_max_age_h"):
        v = plan.get(k)
        if v in (None, "", "auto"):
            continue
        if opts.get(k) in (None, ""):
            opts[k] = v
            applied[k] = v
    if not opts.get("profile"):
        try:
            p = preset_path()
            if p.is_file():
                opts["profile"] = PRESET_NAME
                applied["profile"] = PRESET_NAME
        except OSError:
            pass
    plan["applied_opts"] = applied
    return applied


def inject_prefix(project_text: str, memory_text: str) -> str:
    """拼接 prompt 前缀：项目背景 → EML 记忆 → 用户问题（空段自动省略）。"""
    parts: list[str] = []
    for x in (str(project_text or "").strip(), str(memory_text or "").strip()):
        if x:
            parts.append(x)
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\n【用户问题】\n"


def mode_summary(plan: dict | None) -> dict:
    """任务列表用的 mode 摘要（压缩 plan，避免 /api/tasks 返回被撑大）。"""
    if not isinstance(plan, dict) or not plan:
        return {}
    bg = plan.get("budget_guard") or {}
    _sc = plan.get("scenario") or {}
    return {"id": plan.get("mode_id") or "", "tier": plan.get("tier") or "",
            "policy": plan.get("policy") or "",
            "engine_mode": plan.get("engine_mode") or "",
            "scenario": _sc.get("kind") or "",
            "quality_policy": plan.get("quality_policy") or "",
            "budget_decision": bg.get("decision") or "",
            "budget_level": bg.get("budget_level") or "",
            "dynamic": {k: v for k, v in
                        ((plan.get("dynamic_opt") or {}).get("chosen") or {}).items()
                        if k in ("engine_mode", "web", "rounds",
                                 "est_quality", "est_cost_cny")},
            "reason": str(plan.get("reason") or "")[:300]}


# ── 离线自检 / CLI（证据可复现）─────────────────────────────────
def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="道生专属模式 · 离线计划生成（不跑引擎、不调 API）")
    ap.add_argument("--question", default="Meta-DGTF 道生三阶模型的项目当前状态如何？")
    ap.add_argument("--mode", default="auto", choices=list(VALID_MODES))
    ap.add_argument("--mock", action="store_true", help="模拟 mock 任务（跳过本地模型探测）")
    ap.add_argument("--balance", type=float, default=None,
                    help="显式余额（CNY，便于离线验证预算守卫）")
    ap.add_argument("--json", action="store_true", help="打印完整 plan JSON")
    args = ap.parse_args()
    kw = {}
    if args.balance is not None:
        kw["balance_cny"] = args.balance
    resolved = resolve_mode(args.mode, args.question)
    if resolved["id"] == "standard":
        out = {"mode": resolved,
               "plan": {"policy": "legacy.quality_policy",
                        "reason": "standard 模式不使用 daosheng plan"}}
    else:
        out = {"mode": resolved,
               "plan": build_plan(args.question, requested=resolved["id"],
                                  is_mock=bool(args.mock), **kw)}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
