# -*- coding: utf-8 -*-
"""[v1.23.0 W5] 缩减版全量回归（按本项目口径：**每题只跑 2 次、不做全量跑题**）。

做三件事：
  ① 真后端单点验证：真的打一次 tavily（证明真检索路径可用 + 缓存生效）；
  ② ON / OFF 各 1 跑（共 2 跑）：web_search 开 / 关 的对照；
  ③ 把逐跑读数落 `_v1230_w5_consistency.json`。

用法：python _run_v1230_w5.py [元DGTF-V1.23.0.py] [--skip-live]
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
    else HERE / "元DGTF-V1.23.0.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
SKIP_LIVE = "--skip-live" in sys.argv
_ARMS = next((a.split("=", 1)[1] for a in sys.argv
              if a.startswith("--arms=")), "WOFF,WON").split(",")
_JFP = HERE / "_v1230_w5_consistency.json"
if _JFP.is_file() and _ARMS != ["WOFF", "WON"]:
    try:
        out = json.loads(_JFP.read_text(encoding="utf-8"))
    except Exception:
        pass

spec = importlib.util.spec_from_file_location("dgtf_w5", str(SRC))
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_w5"] = m
spec.loader.exec_module(m)

if "out" not in dir():
    out = {"real_backend": None, "runs": []}

# ---------------- ① 真后端单点 ----------------
_key = os.environ.get("TAVILY_API_KEY", "") or ""
print("[1] 真后端单点：KEY 长度 %d" % len(_key), flush=True)
if _key:
    cl = m.WebSearchClient("tavily", _key, timeout=30, max_retries=1,
                           backoff=1.0,
                           cache=m.WebSearchCache(24, root="cache/websearch"))
    _q = "GB 50014 室外排水设计标准 雨水管渠设计重现期"
    t0 = time.time()
    res, kind = cl.search(_q, max_n=3)
    dt = round(time.time() - t0, 1)
    print("[1] 首次：kind=%r n=%d calls=%d %.1fs" % (kind, len(res), cl.calls, dt),
          flush=True)
    res2, kind2 = cl.search(_q, max_n=3)
    print("[1] 二次：kind=%r n=%d calls=%d cache_hits=%d"
          % (kind2, len(res2), cl.calls, cl.cache_hits), flush=True)
    out["real_backend"] = {
        "key_len": len(_key), "query": _q, "kind": kind, "n": len(res),
        "calls_after_first": 1, "calls_total": cl.calls,
        "cache_hits": cl.cache_hits, "secs": dt,
        "first_claim": (res[0]["claim"][:200] if res else ""),
        "first_url": (res[0]["url"] if res else "")}
else:
    print("[1] 没有 TAVILY_API_KEY，跳过真后端单点", flush=True)

# ---------------- ② ON / OFF 各 1 跑 ----------------
if not SKIP_LIVE:
    q = ("老城区排水管网的现有设计标准是多少年一遇？"
         "该不该整体提标改造、按什么顺序做？")
    for arm, web in [("WOFF", False), ("WON", True)]:
        if arm not in _ARMS:
            continue
        d = HERE / "outputs" / "v1230_w5" / arm
        d.mkdir(parents=True, exist_ok=True)
        cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["save_dir"] = str(d)
        cfg["output"]["verbose"] = False
        cfg.setdefault("web_search", {})
        cfg["web_search"] = dict(m.DEFAULT_CONFIG["web_search"])
        cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
        cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
        if web:
            cfg["web_search"]["enabled"] = True
            cfg["web_search"]["as_evidence"] = "evidence"
            cfg["web_search"]["quota"] = {
                "per_stage_round": 2, "per_stage_total": 4, "per_run_total": 8}
        t0 = time.time()
        meta = m.MetaDGTF(cfg)
        res = meta.run(q, route=["0", "1"], rounds={"0": 2, "1": 2},
                       parallel_mode="serial", orientation="auto")
        p = m.save_result(res, str(d))
        _p1 = (res.get("pools") or {}).get("1") or {}
        _w = list(_p1.get("web_results") or [])
        _e = list(_p1.get("web_errors") or [])
        subs = _p1.get("sub_questions") or []
        rows = {"arm": arm, "web_enabled": web, "secs": round(time.time() - t0, 1),
                "llm_calls": res.get("llm_calls"), "n_subs": len(subs),
                "stability": [s.get("stability") for s in subs],
                "vote_mode": sorted({str(s.get("_vote_mode")) for s in subs}),
                "web_results": len(_w), "web_ids": [x["id"] for x in _w][:8],
                "web_errors": len(_e),
                "web_err_kinds": sorted({x.get("kind") for x in _e}),
                "web_stages": sorted({x.get("stage") for x in _w}),
                "web_as_evidence": bool(_p1.get("web_as_evidence")),
                "gate": (meta._web_gate.summary()
                         if getattr(meta, "_web_gate", None) else {}),
                "md": str(p)}
        out["runs"].append(rows)
        print("[2] %s：subs=%d web=%d ids=%s errors=%s stages=%s calls=%s %.0fs"
              % (arm, len(subs), len(_w), rows["web_ids"], len(_e),
                 rows["web_stages"], res.get("llm_calls"), rows["secs"]),
              flush=True)

jf = HERE / "_v1230_w5_consistency.json"
jf.write_bytes(json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8"))
print("已写 " + jf.name, flush=True)
