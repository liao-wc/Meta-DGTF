# -*- coding: utf-8 -*-
"""Lead 分阶段用量探针（真跑，但只花一次任务的钱）。

为什么要它：llm_by_stage 只给「每阶段 calls/tokens/ms」合计，看不出
token 花在「输入上下文」还是「推理/输出」。要判断该压缩 prompt 还是该关
thinking，必须先量出来。

做法：进程内加载引擎模块，双层 monkeypatch（不改引擎文件）：
  · LLM.call 包装：把 stage 放进线程局部（引擎在并发下多线程调用）；
  · openai Completions.create 包装：抓到 usage（prompt/completion/
    reasoning/cache 命中）与本次调用墙钟，归属到 stage。
最后按 stage 汇总，写 JSON；同时记录余额前后，算真实花费。

用法：
  python scripts/lead_probe_run.py --engine <引擎.py> --probe-out <out.json> \
      -- --route 0 --rounds 1 --web off --behavior-fusion off "问题"
  python scripts/lead_probe_run.py --engine <引擎.py> --dry-run -- --route 0 "问题"
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TLS = threading.local()
RECORDS: list[dict] = []
REC_LOCK = threading.Lock()


def read_env() -> dict:
    out = {}
    p = ROOT / ".env"
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_balance() -> float | None:
    import urllib.request
    env = read_env()
    base = env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    root = base[:-3] if base.endswith("/v1") else base
    try:
        req = urllib.request.Request(
            root + "/user/balance",
            headers={"Authorization": "Bearer " + env.get("DGTF_API_KEY", "")})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        return float((d.get("balance_infos") or [{}])[0].get("total_balance") or 0)
    except Exception:  # noqa: BLE001
        return None


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("metadgtf_probe2", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_probe2"] = mod
    spec.loader.exec_module(mod)
    return mod


def _num(obj, name, default=0):
    try:
        return int(getattr(obj, name, default) or default)
    except Exception:  # noqa: BLE001
        return default


def patch(engine_mod) -> None:
    import openai.resources.chat.completions as occ

    LLM = engine_mod.LLM
    orig_call = LLM.call

    def call_wrapper(self, system, user, *a, **kw):
        TLS.stage = str(kw.get("stage") or (a[5] if len(a) > 5 else "unknown"))
        TLS.json_mode = bool(kw.get("json_mode") or (a[4] if len(a) > 4 else False))
        TLS.sys_chars = len(str(system or ""))
        TLS.user_chars = len(str(user or ""))
        TLS.history_n = len(kw.get("history") or [])
        return orig_call(self, system, user, *a, **kw)

    LLM.call = call_wrapper
    orig_create = occ.Completions.create

    def create_wrapper(self, *a, **kw):
        t0 = time.monotonic()
        resp = orig_create(self, *a, **kw)
        ms = int((time.monotonic() - t0) * 1000)
        usage = getattr(resp, "usage", None)
        details = getattr(usage, "completion_tokens_details", None)
        extra = getattr(usage, "model_extra", None) or {}
        th = ((kw.get("extra_body") or {}).get("thinking") or {})
        rec = {
            "stage": getattr(TLS, "stage", "unknown"),
            "model": str(getattr(resp, "model", "") or kw.get("model") or ""),
            "thinking": str(th.get("type") or "none"),
            "effort": th.get("effort"),
            "json_mode": bool(getattr(TLS, "json_mode", False)),
            "ms": ms,
            "prompt_tokens": _num(usage, "prompt_tokens"),
            "completion_tokens": _num(usage, "completion_tokens"),
            "reasoning_tokens": _num(details, "reasoning_tokens")
            if details is not None else _num(usage, "reasoning_tokens"),
            "total_tokens": _num(usage, "total_tokens"),
            "cache_hit_tokens": _num(extra, "prompt_cache_hit_tokens")
            if isinstance(extra, dict) else 0,
            "cache_miss_tokens": _num(extra, "prompt_cache_miss_tokens")
            if isinstance(extra, dict) else 0,
            "max_tokens": kw.get("max_tokens"),
            "sys_chars": getattr(TLS, "sys_chars", 0),
            "user_chars": getattr(TLS, "user_chars", 0),
            "history_n": getattr(TLS, "history_n", 0),
        }
        with REC_LOCK:
            RECORDS.append(rec)
        return resp

    occ.Completions.create = create_wrapper


def summarize() -> dict:
    agg: dict[str, dict] = {}
    for r in RECORDS:
        s = agg.setdefault(r["stage"], {
            "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "reasoning_tokens": 0, "total_tokens": 0, "ms": 0,
            "cache_hit_tokens": 0, "cache_miss_tokens": 0,
            "thinking_calls": 0, "sys_chars": 0, "user_chars": 0})
        s["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens",
                  "total_tokens", "ms", "cache_hit_tokens", "cache_miss_tokens",
                  "sys_chars", "user_chars"):
            s[k] += int(r.get(k) or 0)
        s["thinking_calls"] += int(r.get("thinking") not in ("none", "", None))
    for s in agg.values():
        n = max(1, s["calls"])
        s["avg_prompt"] = round(s["prompt_tokens"] / n, 1)
        s["avg_completion"] = round(s["completion_tokens"] / n, 1)
        s["avg_reasoning"] = round(s["reasoning_tokens"] / n, 1)
        s["avg_ms"] = round(s["ms"] / n, 1)
        s["cache_hit_ratio"] = round(
            s["cache_hit_tokens"] / max(1, s["cache_hit_tokens"] + s["cache_miss_tokens"]), 4)
    tot = {k: sum(int(r.get(k) or 0) for r in RECORDS)
           for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens",
                     "total_tokens", "ms", "cache_hit_tokens", "cache_miss_tokens")}
    tot["calls"] = len(RECORDS)
    tot["by_stage"] = agg
    tot["records"] = RECORDS
    return tot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--probe-out", default="")
    ap.add_argument("--min-balance", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("engine_args", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    argv = list(args.engine_args)
    if argv and argv[0] == "--":
        argv = argv[1:]
    bal0 = get_balance()
    print("余额 %.2f CNY；引擎 %s" % (-1 if bal0 is None else bal0, args.engine))
    if bal0 is not None and bal0 < args.min_balance and not args.dry_run:
        print("拒绝：余额低于 %.2f" % args.min_balance)
        return 2
    if args.dry_run:
        print("dry-run：引擎参数 =", argv)
        return 0
    t0 = time.time()
    mod = load_engine(Path(args.engine))
    patch(mod)
    sys.argv = ["Meta-DGTF", *argv]
    code = 0
    try:
        mod.main()
    except SystemExit as e:  # noqa: PERF203
        code = int(e.code or 0)
    finally:
        wall = round(time.time() - t0, 1)
        bal1 = get_balance()
        out = summarize()
        out["balance_before"] = bal0
        out["balance_after"] = bal1
        out["cost_cny"] = None if (bal0 is None or bal1 is None) else round(bal0 - bal1, 4)
        out["wall_s"] = wall
        out["argv"] = argv
        out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if args.probe_out:
            p = Path(args.probe_out)
            if not p.is_absolute():
                p = ROOT / p
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            print("PROBE ->", p)
        print("== 总览 ==")
        print("calls=%d prompt=%d completion=%d reasoning=%d total=%d wall=%ss cost=%s CNY"
              % (out["calls"], out["prompt_tokens"], out["completion_tokens"],
                 out["reasoning_tokens"], out["total_tokens"], wall,
                 out["cost_cny"]))
        print("%-26s %4s %9s %9s %9s %8s %8s %7s"
              % ("stage", "calls", "prompt", "compl", "reason", "avg_ms", "cached%", "think"))
        for name, s in sorted(out["by_stage"].items(),
                              key=lambda kv: -kv[1]["total_tokens"]):
            print("%-26s %4d %9d %9d %9d %8.0f %8.1f %7s"
                  % (name, s["calls"], s["prompt_tokens"], s["completion_tokens"],
                     s["reasoning_tokens"], s["avg_ms"],
                     100 * s["cache_hit_ratio"], s["thinking_calls"]))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
