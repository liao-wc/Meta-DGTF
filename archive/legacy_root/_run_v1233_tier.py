#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留3] tier **确认表**真跑旁证（两阶段 + 负对照）。

【为什么必须真跑】
`web_search.tier_confirmed`（人工确认 → 生效）在 v1.23.2 只通了机制：
**表是空的**，生效路径只有离线判据（`check_v1232_tier`）的证据，
没有一次真跑真的让「人工确认」改变过引用表。本脚本补这一条。

【两阶段】
  ① `--phase=collect`：web 开、`tier_floor=2`、确认表**空**。
     记录真实检索到的域名 + 每条的 tier，并算引用表（预期：**一条 W# 都进不去**，
     因为未确认的 tier=3 > floor=2）。
  ② `--phase=apply`：把①观察到的域名写进确认表（**操作者按观察确认**：
     出现最多的域 → 1，其余 → 4），同题同配置重跑。
     预期：确认成 1 的那个域的 W# **进**引用表（离线基线进不去）；
     确认成 4 的域**被排除**（即使它自带 tier=3）。
  ③ **负对照**：`apply` 那一跑里，若出现**①没见过的新域名** ⇒ 它
     **不挂 `tier_effective`**（加性），且按自带 tier 走。

用法：
  python _run_v1233_tier.py [src.py] --phase=collect
  python _run_v1233_tier.py [src.py] --phase=apply
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(_args[0]) if _args else HERE / "元DGTF-V1.23.3.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
PHASE = next((a.split("=", 1)[1] for a in sys.argv
              if a.startswith("--phase=")), "collect")
COLL = HERE / "_v1233_tier_collect.json"
APPLY = HERE / "_v1233_tier_apply.json"

QUESTION = ("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
            "怎么权衡？")
FLOOR = 2


def _load(src: Path):
    spec = importlib.util.spec_from_file_location("dgtf_tier1233", src)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_tier1233"] = m
    spec.loader.exec_module(m)
    return m


def _cfg(m, out_dir: Path, confirmed: dict) -> dict:
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["web_search"] = dict(m.DEFAULT_CONFIG["web_search"])
    cfg["web_search"].update({"enabled": True, "as_evidence": "evidence",
                              "tier_floor": FLOOR,
                              "tier_confirmed": dict(confirmed)})
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(out_dir)
    cfg["output"]["verbose"] = False
    cfg["external_anchor"] = dict(cfg["external_anchor"])
    cfg["external_anchor"].update({"enabled": True,
                                   "path": "_test_anchors.json",
                                   "as_evidence": "evidence", "tier_floor": 2})
    return cfg


def _snap(m, meta, res, md, cfg, secs) -> dict:
    p1 = (res.get("pools") or {}).get("1") or {}
    pool = meta.pools.get("1")
    items = list(p1.get("web_results") or [])
    try:
        pool._web_cfg = m._web_cfg_of(cfg)
        tbl = [str(a) for a, _ in (m._citation_table(None, pool) or [])]
    except Exception as exc:  # noqa: BLE001
        tbl = ["<引用表计算失败:%s>" % exc]
    metas = [str(x) for x in (p1.get("meta") or [])]
    return {
        "secs": secs, "md": str(md), "n_web": len(items),
        "items": [{"id": x.get("id"), "domain": m._web_domain_of(x.get("url", "")),
                   "tier": x.get("tier"),
                   "tier_effective": x.get("tier_effective"),
                   "enters": bool(m._web_enters_citation(x, {"tier_floor": FLOOR}))}
                  for x in items],
        "citation_table": tbl,
        "w_in_table": [t for t in tbl if t.startswith("W")],
        "tier_meta": [x for x in metas if "[W-TIER" in x],
        "tier_confirmed_used": cfg["web_search"]["tier_confirmed"],
        "tier_floor": FLOOR,
        "anchor_triage": (res.get("external_anchor") or {}).get(
            "triage_downgrades"),
        "calls": res.get("llm_calls"),
    }


def _run(m, confirmed: dict, tag: str) -> dict:
    d = HERE / "outputs" / ("v1233_tier_" + tag)
    d.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(m, d, confirmed)
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        meta = m.MetaDGTF(cfg)
        res = meta.run(QUESTION, route=["0", "1"], rounds={"0": 1, "1": 1},
                       parallel_mode="serial", orientation="auto")
        md = m.save_result(res, str(d))
    return _snap(m, meta, res, md, cfg, round(time.time() - t0, 1))


def main() -> int:
    m = _load(SRC)
    print("[tier] src=%s phase=%s floor=%d" % (SRC.name, PHASE, FLOOR),
          flush=True)
    if PHASE == "collect":
        rec = _run(m, {}, "collect")
        COLL.write_bytes(json.dumps({"src": SRC.name, "run": rec},
                                    ensure_ascii=False, indent=1,
                                    default=str).encode("utf-8"))
        doms: dict = {}
        for it in rec["items"]:
            doms[it["domain"]] = doms.get(it["domain"], 0) + 1
        print("[tier] collect 完成 %.0fs W#=%d 域名=%s"
              % (rec["secs"], rec["n_web"], doms), flush=True)
        print("[tier] 引用表里的 W#：%s（预期：空 —— floor=%d 而 tier 未确认=3）"
              % (rec["w_in_table"], FLOOR), flush=True)
        return 0

    # ---- apply ----
    _c = json.loads(COLL.read_text(encoding="utf-8"))
    doms: dict = {}
    for it in (_c.get("run") or {}).get("items", []):
        doms[it["domain"]] = doms.get(it["domain"], 0) + 1
    doms = {d: c for d, c in doms.items() if d}
    if not doms:
        print("[tier] collect 没记录到域名，无法 apply", flush=True)
        return 2
    top = max(doms, key=lambda k: doms[k])
    # 操作者按观察确认：出现最多的域 → 1（权威/常用），其余 → 4（低质）
    confirmed = {d: (1 if d == top else 4) for d in doms}
    print("[tier] 人工确认表：%s" % confirmed, flush=True)
    rec = _run(m, confirmed, "apply")
    out = {"src": SRC.name, "confirmed": confirmed, "run": rec,
           "baseline": _c.get("run")}
    APPLY.write_bytes(json.dumps(out, ensure_ascii=False, indent=1,
                                 default=str).encode("utf-8"))
    print("[tier] apply 完成 %.0fs W#=%d" % (rec["secs"], rec["n_web"]),
          flush=True)
    print("[tier] 引用表里的 W#：%s" % rec["w_in_table"], flush=True)
    print("[tier] 留痕：%s" % rec["tier_meta"], flush=True)
    _toc = [it for it in rec["items"] if it.get("tier_effective") is not None]
    _non = [it for it in rec["items"] if it.get("tier_effective") is None]
    print("[tier] 挂了 tier_effective 的：%d 条；没挂的（负对照）：%d 条"
          % (len(_toc), len(_non)), flush=True)
    print("TIER_RUNS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
