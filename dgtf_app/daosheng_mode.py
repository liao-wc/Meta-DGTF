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
               "raw_max_tokens_fallback": 2000000},
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
        out["reason"] = ("余额未知（%s）→ fail-open：不拒绝任务，按质量档继续"
                         % ("mock 跳过查询" if src == "mock-skip" else "查询失败"))
        return out
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


# ── 缓存命中预判 ───────────────────────────────────────────────
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
    if out["exact"]:
        out["note"] = "同题已完成的精确缓存候选：%s（真实任务会直接复用产物）" % out["exact_from"]
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

    route = ",".join((local.get("route") or _norm_route(ds.get("route"))))
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

    memory = memory_summary(question, ds, project_related=_prj, history=history)
    context_injected: list[str] = []
    if _prj:
        context_injected.append("project_context:RAG")
    if memory.get("injected"):
        context_injected.append("memory:EML(%d字)" % int(memory.get("chars") or 0))

    cache = cache_prediction(question, opts)
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
        "rounds": rounds,
        "parallel": parallel,
        "web": web,
        "thinking": thinking,
        "effort": effort,
        "self_check_mode": scm,
        "self_check_mode_via": scm_via,
        "dual_judge_mode": djm,
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
              "history_fusion"):
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
