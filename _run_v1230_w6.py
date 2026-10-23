#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.1 遗留1+4] 三场景 × 2 跑（web ON）+ 三题 × 1 跑（web OFF，供 P2.4）。

为什么两件事一个脚本：
  · 遗留4 要 `outputs/p2_run{1,2,3}` 在**当代码**上重新为真 —— 这三题就是
    P2/P2b 的三题（`_run_v1221_p2b.py` 的原文），配置也照 P2b（锚点
    as_evidence=evidence + answers 路径），所以判据与历史可比。
  · 遗留1 要 3 场景 × 2 跑的联网读数 —— 同一批题正好当场景。
  两件事共用题目 ⇒ 一次跑批同时服务两条遗留（省一半时间）。

臂与落盘：
  OFF rep1 → `outputs/p2_run{i}`（**P2.4 的判据锚**，rounds 3:3，与 P2b 同构）
  ON  rep1 → `outputs/w6_<tag>_on1`
  ON  rep2 → `outputs/w6_<tag>_on2`
  （ON 臂 rounds 2:2 —— 三票判决在研究层，与圈数无关，缩短只为省时）

用法：
  python _run_v1230_w6.py [src.py]                 # 全套 9 跑
  python _run_v1230_w6.py [src.py] --only=1        # 只跑第 1 题（3 跑）
  python _run_v1230_w6.py [src.py] --jobs=W6_1_ON  # 只跑指定作业
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(_args[0]) if _args else HERE / "元DGTF-V1.23.1.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
ONLY = next((int(a.split("=", 1)[1]) for a in sys.argv
             if a.startswith("--only=")), 0)
JOBS = next((a.split("=", 1)[1] for a in sys.argv
             if a.startswith("--jobs=")), "")
JOBF = HERE / "_v1230_w6_runs.json"

# 三场景：按「外部材料与本决策的关系」分档（这就是「三场景命中率」的场景定义）
SCEN = [
    (1, "老城区内涝", "外部规范可查",
     "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"),
    (2, "中小制造", "外部无定论",
     "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？"),
    (3, "社区医院", "外部有材料但不可作证据",
     "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？"),
]


def _cfg(m, web: bool, out_dir: Path, tier_prop: bool = False) -> dict:
    """P2b 同构配置 + 联网开关（web OFF = 与历史 P2b 配置逐字一致）。"""
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["external_anchor"] = dict(cfg["external_anchor"])
    cfg["external_anchor"].update({
        "enabled": True, "path": "_test_anchors.json",
        "as_evidence": "evidence", "tier_floor": 2,
    })
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(out_dir)
    cfg["output"]["verbose"] = False
    cfg["web_search"] = dict(m.DEFAULT_CONFIG["web_search"])
    cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
    cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
    cfg["web_search"]["domain_tier_rules"] = list(
        cfg["web_search"].get("domain_tier_rules") or [])
    if web:
        cfg["web_search"]["enabled"] = True
        cfg["web_search"]["as_evidence"] = "evidence"
        cfg["web_search"]["tier_proposal"] = bool(tier_prop)
    return cfg


def _snap(m, meta, res, md, arm, tag, rep, scen, secs) -> dict:
    p1 = (res.get("pools") or {}).get("1") or {}
    subs = p1.get("sub_questions") or []
    w = list(p1.get("web_results") or [])
    e = list(p1.get("web_errors") or [])
    metas = [str(x) for x in (p1.get("meta") or [])]
    return {
        "arm": arm, "tag": tag, "rep": rep, "scenario": scen,
        "secs": secs, "llm_calls": res.get("llm_calls"),
        "n_subs": len(subs),
        "subs": [{"id": s.get("id"), "decidability": s.get("decidability"),
                  "first_label": s.get("first_label"),
                  "stability": s.get("stability"),
                  "vote_mode": s.get("_vote_mode"),
                  "votes": s.get("votes"),
                  "agreement": s.get("agreement")} for s in subs],
        "tri_consensus": res.get("tri_consensus"),
        "web_n": len(w),
        "web_ids": [x.get("id") for x in w],
        "web_stages": sorted({str(x.get("stage")) for x in w}),
        "web_rounds": sorted({int(x.get("round", -1)) for x in w}),
        "web_round_kinds": sorted({str(x.get("round_kind")) for x in w}),
        # ★ 逐条的 (round, round_kind) 配对 —— 聚合集看不出「前置条是不是
        #   真的 0」，而判据要的正是这个一致性（round_kind 与 round 必须自洽）。
        "web_items": [{"id": x.get("id"), "stage": x.get("stage"),
                       "round": x.get("round"),
                       "round_kind": x.get("round_kind"),
                       "pre_seq": x.get("pre_seq"),
                       # ★ used_as 是「这条给谁用」的标签：W4 三票的
                       #   research_evidence 走 arbitration、圈内钩子走
                       #   evidence —— 只看 stage 名两者分不开。
                       "used_as": x.get("used_as"),
                       "tier": x.get("tier")} for x in w],
        "web_tiers": sorted({int(x.get("tier", -1)) for x in w}),
        "web_errors_n": len(e),
        "web_err_kinds": sorted({str(x.get("kind")) for x in e}),
        "web_empty_n": sum(1 for x in metas if "[W-EMPTY]" in x),
        "web_skip_n": sum(1 for x in metas if "[W-SKIP]" in x),
        "web_ok_n": sum(1 for x in metas if "[W-OK]" in x),
        "web_tier_lines": [x for x in metas if "[W-TIER" in x],
        "tier_proposals_n": len(p1.get("web_tier_proposals") or []),
        "web_as_evidence": bool(p1.get("web_as_evidence")),
        "gate": (meta._web_gate.summary()
                 if getattr(meta, "_web_gate", None) else {}),
        "ea_triage": _as_n((res.get("external_anchor") or {})
                           .get("triage_downgrades")),
        "drift": _drift(res),
        "md": str(md),
    }


def _as_n(v) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple)):
        return len(v)
    return 0


def _drift(res: dict) -> dict:
    seen, un2p, applied = set(), 0, 0
    for _pn, pool in (res.get("pools") or {}).items():
        for ent in ((pool or {}).get("decidability_log") or []):
            if not isinstance(ent, dict) or str(ent.get("status")) != "applied":
                continue
            key = (ent.get("sub_id"), ent.get("from"), ent.get("to"))
            if key in seen:
                continue
            seen.add(key)
            applied += 1
            if (str(ent.get("from")) == "undecidable"
                    and str(ent.get("to")) == "partial"):
                un2p += 1
    return {"und_to_partial": un2p, "applied_total": applied,
            "ratio": round(un2p / applied, 3) if applied else None}


def main() -> int:
    spec = importlib.util.spec_from_file_location("dgtf_w6", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_w6"] = m
    spec.loader.exec_module(m)
    print("[w6] src=%s key_len=%d" % (SRC.name,
                                      len(os.environ.get("TAVILY_API_KEY", ""))),
          flush=True)

    out = {"src": SRC.name, "runs": []}
    if JOBF.is_file():
        try:
            out = json.loads(JOBF.read_text(encoding="utf-8"))
            out["src"] = SRC.name
        except Exception:  # noqa: BLE001
            pass

    todo = []
    for i, tag, scen, q in SCEN:
        if ONLY and i != ONLY:
            continue
        todo.append((i, tag, scen, q, "OFF", 1))
        todo.append((i, tag, scen, q, "ON", 1))
        todo.append((i, tag, scen, q, "ON", 2))
    # 第 10 跑：全路由（0/1/both/all）—— 只有它会真的走到 W3 的对撞仲裁与
    #   元层核对，是「遗留3 的 W3 部分在真跑里也换了真圈号」的唯一证据。
    if not ONLY or ONLY == 1:
        i, tag, scen, q = SCEN[0]
        todo.append((i, tag, scen, q, "ONFULL", 1))

    for i, tag, scen, q, arm, rep in todo:
        jid = ("W6_FULL_ON1" if arm == "ONFULL"
               else "W6_%d_%s%d" % (i, arm, rep))
        if JOBS and jid not in JOBS.split(","):
            continue
        if arm == "OFF":
            d = HERE / "outputs" / ("p2_run%d" % i)
            rnds, route = {"0": 3, "1": 3}, ["0", "1"]
        elif arm == "ONFULL":
            d = HERE / "outputs" / "w6_full_on1"
            rnds, route = ({"0": 2, "1": 2, "both": 2, "all": 2},
                           ["0", "1", "both", "all"])
        else:
            d = HERE / "outputs" / ("w6_%s_on%d" % (tag, rep))
            rnds, route = {"0": 2, "1": 2}, ["0", "1"]
        d.mkdir(parents=True, exist_ok=True)
        cfg = _cfg(m, web=(arm in ("ON", "ONFULL")), out_dir=d,
                   tier_prop=(arm in ("ON", "ONFULL")))
        buf = io.StringIO()
        t0 = time.time()
        rec = {"job": jid, "arm": arm, "tag": tag, "scenario": scen, "rep": rep,
               "question": q, "ok": False, "error": ""}
        try:
            with contextlib.redirect_stdout(buf):
                meta = m.Meta-DGTF(cfg)
                res = meta.run(q, route=route, rounds=rnds,
                               parallel_mode="serial", orientation="auto")
                md = m.save_result(res, str(d))
            rec.update(_snap(m, meta, res, md, arm, tag, rep, scen,
                             round(time.time() - t0, 1)))
            rec["ok"] = True
        except Exception as exc:  # noqa: BLE001
            rec["error"] = "%s: %s" % (type(exc).__name__, exc)
            rec["secs"] = round(time.time() - t0, 1)
        # 同名作业覆盖（重跑即更新）
        out["runs"] = [r for r in out["runs"] if r.get("job") != jid] + [rec]
        try:
            (d / "w6_meta.json").write_bytes(
                json.dumps(rec, ensure_ascii=False, indent=2,
                           default=str).encode("utf-8"))
            (d / "w6_stdout.log").write_bytes(
                buf.getvalue().encode("utf-8", "replace"))
        except OSError:
            pass
        JOBF.write_bytes(json.dumps(out, ensure_ascii=False,
                                    indent=2, default=str).encode("utf-8"))
        print("[%s] ok=%s subs=%s W#=%s stages=%s rounds=%s kinds=%s "
              "empty=%s skip=%s err=%s triage=%s drift=%s %.0fs"
              % (jid, rec["ok"], rec.get("n_subs"), rec.get("web_n"),
                 rec.get("web_stages"), rec.get("web_rounds"),
                 rec.get("web_round_kinds"), rec.get("web_empty_n"),
                 rec.get("web_skip_n"), rec.get("web_err_kinds"),
                 rec.get("ea_triage"), (rec.get("drift") or {}).get("ratio"),
                 rec.get("secs") or 0), flush=True)
    print("W6_RUNS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
