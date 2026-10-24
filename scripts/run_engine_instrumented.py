# -*- coding: utf-8 -*-
"""运行 Meta-DGTF 引擎并注入 LLM 用量探针（不改引擎文件）。

用途：测量 DeepSeek 上下文缓存命中 tokens、重复 prompt 数，为 V2.2.3 的
KV cache / 去重优化提供数据。脚本只 monkeypatch OpenAI SDK 的 create 方法，
再调用引擎 main()；产物 JSON 写到 --probe-out。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
_STATS = {
    "calls": 0, "total_tokens": 0,
    "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0,
    "dup_prompts": 0, "unique_prompts": 0,
    "usage_has_cache_fields": False,
}


def _load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("metadgtf_probe", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def _patch(probe_out: Path):
    import openai.resources.chat.completions as occ
    orig = occ.Completions.create
    seen = set()

    def create(self, *args, **kwargs):
        resp = orig(self, *args, **kwargs)
        try:
            usage = getattr(resp, "usage", None)
            hit = miss = 0
            if usage is not None:
                extra = getattr(usage, "model_extra", None) or {}
                hit = int(extra.get("prompt_cache_hit_tokens") or 0)
                miss = int(extra.get("prompt_cache_miss_tokens") or 0)
                if not hit and not miss:
                    hit = int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0)
                    miss = int(getattr(usage, "prompt_cache_miss_tokens", 0) or 0)
                if hit or miss:
                    _STATS["usage_has_cache_fields"] = True
            msgs = kwargs.get("messages") or []
            raw = json.dumps(msgs, ensure_ascii=False, sort_keys=True)
            h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            with _LOCK:
                _STATS["calls"] += 1
                _STATS["total_tokens"] += int(
                    getattr(usage, "total_tokens", 0) or 0)
                _STATS["prompt_cache_hit_tokens"] += hit
                _STATS["prompt_cache_miss_tokens"] += miss
                if h in seen:
                    _STATS["dup_prompts"] += 1
                else:
                    seen.add(h)
                _STATS["unique_prompts"] = len(seen)
        except Exception:
            pass
        return resp

    occ.Completions.create = create
    return orig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py"))
    ap.add_argument("--probe-out", required=True)
    ap.add_argument("engine_args", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    argv = list(args.engine_args)
    if argv and argv[0] == "--":
        argv = argv[1:]
    mod = _load_engine(Path(args.engine))
    _patch(Path(args.probe_out))
    sys.argv = ["Meta-DGTF", *argv]
    code = 0
    try:
        if hasattr(mod, "main"):
            mod.main()
    except SystemExit as e:
        code = int(e.code or 0)
    finally:
        total = _STATS["prompt_cache_hit_tokens"] + _STATS["prompt_cache_miss_tokens"]
        _STATS["cache_hit_ratio"] = round(
            _STATS["prompt_cache_hit_tokens"] / total, 4) if total else 0.0
        _STATS["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = Path(args.probe_out)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(_STATS, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print("PROBE", json.dumps(_STATS, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
