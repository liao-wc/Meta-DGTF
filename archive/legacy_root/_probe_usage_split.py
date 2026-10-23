# -*- coding: utf-8 -*-
"""[成本实测探针] 采集每次 API 调用的 token 拆分（input/output/缓存命中）。

为什么需要它：引擎只把 `usage.total_tokens` 汇总进 `llm.total_tokens`
（元DGTF-V1.21.72.py:7005-7009），产物与日志里**没有** input/output 拆分，
所以「一次跑多少钱」只能靠估算。本探针在**类层面**包一次
`openai.resources.chat.completions.Completions.create`，把每次调用的
prompt_tokens / completion_tokens / prompt_cache_hit_tokens /
prompt_cache_miss_tokens 记下来 —— 不改引擎任何一行逻辑。

用法：
  python _probe_usage_split.py <rounds_0> <rounds_1>
  例：python _probe_usage_split.py 2 2

产出：
  _probe_usage_split.json  —— 逐调用记录 + 汇总比率
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RECORDS = []


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def patch_client():
    """类层面包装 create，记录 usage。返回 (已包装?) """
    from openai.resources.chat.completions import Completions
    if getattr(Completions.create, "_cost_probe", False):
        return True
    orig = Completions.create

    def patched(self, *a, **k):
        r = orig(self, *a, **k)
        try:
            u = getattr(r, "usage", None)
            if u is not None:
                RECORDS.append({
                    "model": getattr(r, "model", None),
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None),
                    "total_tokens": getattr(u, "total_tokens", None),
                    "cache_hit": getattr(u, "prompt_cache_hit_tokens", None),
                    "cache_miss": getattr(u, "prompt_cache_miss_tokens", None),
                })
        except Exception:
            pass
        return r

    patched._cost_probe = True
    Completions.create = patched
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    r0, r1 = int(sys.argv[1]), int(sys.argv[2])
    question = (sys.argv[3] if len(sys.argv) > 3 else
                "订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？")
    load_dotenv(HERE / ".env")
    patch_client()

    spec = importlib.util.spec_from_file_location(
        "dgtf72probe", HERE / "元DGTF-V1.21.72.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf72probe"] = mod
    spec.loader.exec_module(mod)

    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    meta = mod.MetaDGTF(cfg)
    meta.verbose = False
    res = meta.run(question, route=["0", "1"], rounds={"0": r0, "1": r1},
                   parallel_mode="serial")

    tin = sum((r.get("prompt_tokens") or 0) for r in RECORDS)
    tout = sum((r.get("completion_tokens") or 0) for r in RECORDS)
    tot = sum((r.get("total_tokens") or 0) for r in RECORDS)
    hit = sum((r.get("cache_hit") or 0) for r in RECORDS)
    miss = sum((r.get("cache_miss") or 0) for r in RECORDS)
    summary = {
        "n_calls_recorded": len(RECORDS),
        "engine_calls": res.get("llm_calls"),
        "engine_tokens": res.get("llm_tokens"),
        "sum_prompt": tin, "sum_completion": tout, "sum_total": tot,
        "cache_hit": hit, "cache_miss": miss,
        "out_share": (tout / tot) if tot else None,
        "cache_hit_share_of_prompt": (hit / (hit + miss)) if (hit + miss) else None,
        "per_call_avg_total": (tot / len(RECORDS)) if RECORDS else None,
    }
    out = HERE / "_probe_usage_split.json"
    out.write_text(json.dumps({"summary": summary, "records": RECORDS},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
