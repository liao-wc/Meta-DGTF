#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3 遗留5] triage 触发频度**专项批**（不是顺手捞读数）。

【为什么必须专项】
`v1232_报告.md` §十 第 5 条：本版 10 份产物里 triage 只命中 1 份 —— 那是
**顺手**得到的读数（那 10 跑本来是为别的事跑的），既不是频度估计，
也没有区间。修法：定制题 + 定向锚点，专门跑 N 跑，报 k/N + Wilson 区间。

【机制回顾】triage 降级要同时满足：
  ① `decidability_result["undecidable_aspects"]` 里有**属「缺外部材料」类**的
     侧面（结构前缀 `[外]` 或语义关键词「信息不足/缺数据/需要外部/…」）；
  ② 该侧面被一条 **tier ≤ external_anchor.tier_floor** 的锚点命中
     （`answers` 重叠系数 ≥ 0.6 或 `claim` 相似度 ≥ 0.6）。
⇒ 题目要**逼出「缺外部材料」型**的不可判定侧面；锚点要**覆盖这些材料**
  （这是 `external_anchor` 的设计用法：操作者按题供给外部事实）。
  ★ 频度测的是「在锚点覆盖到位的条件下，该机制能否稳定触发」——
    报告里必须写明这个前提，不能当成无条件频度。

用法：
  python _run_v1233_triage.py [src.py] --mode=collect --n=3
  python _run_v1233_triage.py [src.py] --mode=measure --n=8
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
MODE = next((a.split("=", 1)[1] for a in sys.argv
             if a.startswith("--mode=")), "measure")
N = int(next((a.split("=", 1)[1] for a in sys.argv
              if a.startswith("--n=")), 3))
ANCH = HERE / "_v1233_anchors_triage.json"
COLL = HERE / "_v1233_triage_collect.json"
RUNS = HERE / "_v1233_triage_runs.json"

QUESTIONS = [
    ("外部标准缺依据",
     "本市要在 2028 年前把老城区内涝防治能力提到国家现行标准的要求，"
     "但现行国标的具体指标口径、本市近十年内涝点的成因分布资料都不在手上。"
     "请给出排水系统重建与局部改造加海绵措施的取舍方案。"),
    ("外部规范+历史数据双缺",
     "某三线城市要按上级最新的行业规范改造老旧供水管网，"
     "但该规范的具体参数、该市管网漏损的历史统计都不在手上。"
     "请给出改造优先级与验收口径的取舍。"),
]

# 定向锚点：**只写外部事实本身**（claim）+ 关键词密集的 answers。
#   ★ answers 要短而关键词密：`_overlap_coef` 的分母是 min(|A|,|B|)，
#     长句作 answer 会因为并集被稀释而命中不了。
ANCHORS = {
    "question": QUESTIONS[0][1],
    "retrieved_at": "2026-10-06T00:00:00+08:00",
    "retriever": "manual-tier1",
    "anchors": [
        {"id": "a1", "tier": 1, "kind": "standard",
         "source": "GB50014-2021《室外排水设计标准》",
         "claim": ("GB50014-2021 规定：雨水管渠设计重现期，特大城市中心城区"
                   "应取 3~5 年，重要地区 10~50 年；内涝防治设计重现期"
                   "应按城市规模取 20~100 年。"),
         "answers": ["国家现行标准的具体指标口径", "现行国标的具体指标",
                     "雨水管渠设计重现期", "内涝防治设计重现期",
                     "国标的具体指标口径", "国家现行标准规定"]},
        {"id": "a2", "tier": 1, "kind": "dataset",
         "source": "住建部内涝防治年度报告（示意）",
         "claim": ("公开报告显示：老城区内涝成因以「管网能力不足 + 低洼地形"
                   "汇水」为主，占比约七成；局部强降雨与排水口顶托次之。"),
         "answers": ["本市近十年内涝点的成因分布", "历史内涝成因分布",
                     "内涝成因分布资料", "近十年内涝点成因占比",
                     "本市现状管网能力参数"]},
        {"id": "a3", "tier": 1, "kind": "standard",
         "source": "《海绵城市建设技术指南（试行）》",
         "claim": ("年径流总量控制率按降雨与土壤渗透条件分区确定；老城区"
                   "改造以源头减排 + 过程控制为主，管网扩容需与调蓄同步。"),
         "answers": ["海绵城市建设技术指南", "年径流总量控制率要求",
                     "源头减排与过程控制"]},
        {"id": "a4", "tier": 1, "kind": "standard",
         "source": "行业规范（示意）",
         "claim": ("行业规范要求：改造前应完成管网漏损分区计量与压力管理，"
                   "漏损率验收以分区计量数据为准。"),
         "answers": ["上级最新规范的具体参数", "规范限值与强制条款",
                     "漏损率验收阈值", "管网漏损分区计量"]},
        {"id": "a5", "tier": 1, "kind": "dataset",
         "source": "该市统计年鉴（示意）",
         "claim": ("该市管网漏损历史统计显示：近五年漏损率由 18% 降至 12%，"
                   "老旧管段集中在 1990 年代敷设区域。"),
         "answers": ["该市管网漏损的历史统计", "分区级管段级漏损台账",
                     "该市管网漏损历史数据"]},
    ],
}

# ★ 负对照锚点集：同样条数、同样 tier，但**与题目无关** ⇒ 一条都命中不了。
#   它回答的是「triage 是不是只要开锚点就会触发」——必须 0。
ANCHORS_NEG = {
    "question": QUESTIONS[0][1],
    "retrieved_at": "2026-10-06T00:00:00+08:00",
    "retriever": "manual-tier1-negctl",
    "anchors": [
        {"id": "n1", "tier": 1, "kind": "standard",
         "source": "无关领域规范（负对照）",
         "claim": ("某行业规范规定：冷链运输车厢温度应保持在零下十八度"
                   "以下，装卸货时长不超过三十分钟。"),
         "answers": ["冷链运输车厢温度控制", "装卸货时长限制"]},
        {"id": "n2", "tier": 1, "kind": "dataset",
         "source": "无关数据集（负对照）",
         "claim": ("某平台统计显示：咖啡豆年度进口量同比增长百分之七，"
                   "其中阿拉比卡占比六成。"),
         "answers": ["咖啡豆年度进口量统计", "阿拉比卡占比数据"]},
        {"id": "n3", "tier": 1, "kind": "standard",
         "source": "无关规程（负对照）",
         "claim": "某规程规定：高空作业必须佩戴双钩安全带并设置生命线。",
         "answers": ["高空作业安全带要求", "生命线设置规程"]},
    ],
}


def _load(src: Path):
    spec = importlib.util.spec_from_file_location("dgtf_tri1233", src)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_tri1233"] = m
    spec.loader.exec_module(m)
    return m


def _cfg(m, out_dir: Path, path: Path) -> dict:
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["external_anchor"] = dict(cfg["external_anchor"])
    cfg["external_anchor"].update({
        "enabled": True, "path": str(path), "as_evidence": "evidence",
        "tier_floor": 2,
    })
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(out_dir)
    cfg["output"]["verbose"] = False
    return cfg


def main() -> int:
    m = _load(SRC)
    _use = ANCHORS_NEG if MODE == "negctl" else ANCHORS
    ANCH.write_bytes(json.dumps(_use, ensure_ascii=False, indent=1)
                     .encode("utf-8"))
    print("[tri] src=%s mode=%s n=%d anchors=%d"
          % (SRC.name, MODE, N, len(ANCHORS["anchors"])), flush=True)
    rows = []
    for rep in range(1, N + 1):
        tag, q = QUESTIONS[(rep - 1) % len(QUESTIONS)]
        d = HERE / "outputs" / ("v1233_tri_%s_r%d" % (
            "std" if tag.startswith("外部标准") else "pipe", rep))
        d.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        t0 = time.time()
        rec = {"rep": rep, "tag": tag, "ok": False, "error": ""}
        try:
            with contextlib.redirect_stdout(buf):
                meta = m.MetaDGTF(_cfg(m, d, ANCH))
                res = meta.run(q, route=["0", "1"], rounds={"0": 1, "1": 1},
                               parallel_mode="serial", orientation="auto")
                md = m.save_result(res, str(d))
            ea = res.get("external_anchor") or {}
            dec = res.get("decidability") or {}
            p1 = (res.get("pools") or {}).get("1") or {}
            rec.update({
                "ok": True, "triage": len(ea.get("triage_downgrades")
                                          if isinstance(ea.get("triage_downgrades"), (list, tuple))
                                          else ([0] * int(ea.get("triage_downgrades") or 0))),
                "triage_n": ea.get("triage_downgrades") if not isinstance(
                    ea.get("triage_downgrades"), (list, tuple))
                else len(ea.get("triage_downgrades")),
                "triage_items": ea.get("triage_items") or [],
                "claims": ea.get("claims"),
                "anchor_error": ea.get("error") or "",
                "und_aspects": dec.get("undecidable_aspects") or [],
                "anchor_calls": ea.get("anchor_calls"),
                "n_subs": len(p1.get("sub_questions") or []),
                "calls": res.get("llm_calls"),
                "secs": round(time.time() - t0, 1),
                "md": str(md),
            })
        except Exception as exc:  # noqa: BLE001
            rec["error"] = "%s: %s" % (type(exc).__name__, exc)
            rec["secs"] = round(time.time() - t0, 1)
        if isinstance(rec.get("triage_n"), (list, tuple)):
            rec["triage_n"] = len(rec["triage_n"])
        rows.append(rec)
        print("[tri] rep %d/%d %s ok=%s triage=%s claims=%s secs=%s err=%s"
              % (rep, N, tag, rec["ok"], rec.get("triage_n"),
                 rec.get("claims"), rec.get("secs"), rec.get("error")[:60]),
              flush=True)

    if MODE == "collect":
        COLL.write_bytes(json.dumps({"src": SRC.name, "runs": rows},
                                    ensure_ascii=False, indent=1,
                                    default=str).encode("utf-8"))
        print("[tri] collect 已写 %s" % COLL.name, flush=True)
        for r in rows:
            print("[tri]   未判侧面：%s"
                  % json.dumps(r.get("und_aspects") or [], ensure_ascii=False),
                  flush=True)
        return 0

    # ---- Wilson 区间 ----
    def wilson(k, n, z=1.96):
        if not n:
            return (None, None)
        p = k / n
        dd = 1 + z * z / n
        c = (p + z * z / (2 * n)) / dd
        h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / dd
        return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))

    ok = [r for r in rows if r["ok"]]
    k = sum(1 for r in ok if (r.get("triage_n") or 0) >= 1)
    lo, hi = wilson(k, len(ok))
    out = {"src": SRC.name, "n": N, "runs": rows, "hit": k, "n_ok": len(ok),
           "rate": (round(k / len(ok), 3) if ok else None),
           "wilson": [lo, hi]}
    # ★ 负对照批**不能**写 `_v1233_triage_runs.json` —— 那会把主批的读数
    #   覆盖掉（本机实踩：验收档 V5.e 立刻报 n_ok=3 rate=0.0）。
    #   「同名文件被两种模式共用」是这一族坑的通式。
    _out_name = ("_v1233_triage_negctl.json" if MODE == "negctl"
                 else "_v1233_triage_runs.json")
    (HERE / _out_name).write_bytes(
        json.dumps(out, ensure_ascii=False, indent=1,
                   default=str).encode("utf-8"))
    print("[tri] 已写 %s" % _out_name, flush=True)
    print("[tri] 频度 = %d / %d = %s（Wilson 95%% [%s, %s]）"
          % (k, len(ok), out["rate"], lo, hi), flush=True)
    print("TRIAGE_RUNS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
