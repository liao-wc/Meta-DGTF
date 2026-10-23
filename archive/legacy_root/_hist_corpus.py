# -*- coding: utf-8 -*-
"""历史真跑语料分析：从产物 md / packed / 跑批 JSON 抽统一记录并算分位数。

★ 用途：v1.23.13 的自适应阈值全是「拍脑袋」的（40 万 token、截断率 0.5、
空结果 ≥3 次…）。本脚本把**真实历史**扫一遍，给出实测分位，用来校准。

数据源（按可信度排序）：
  ① `outputs/**/*.packed.json` —— 全量字段（最准，含 dispatch/tri_state/web_results）
  ② `outputs/**/*.md`        —— 头部行（覆盖最广：`**资源**` / `**调度**` /
                                `**并行模式**` / `**成本档位**` / `**停止**`）
  ③ 跑批 JSON（`_v1230_w6_runs.json` 等）—— 富字段但样本少

用法：python _hist_corpus.py [--json <输出路径>]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

RE_CALLS = re.compile(r"\*\*资源\*\*[:：]\s*(\d+) 次 LLM \| (\d+) tokens")
RE_MODE = re.compile(r"\*\*并行模式\*\*[:：]\s*([A-H]) ·")
RE_MODE_SER = re.compile(r"\*\*并行模式\*\*[:：]\s*(严格串行)")
RE_PROF = re.compile(r"\*\*成本档位\*\*[:：]\s*(\w+)")
RE_ROUTE = re.compile(r"\*\*调度\*\*[:：]\s*(.+)")
RE_LAYER = re.compile(r"([\u4e00-\u9fff]+)\((\d+)圈\)")
RE_STOP = re.compile(r"\*\*停止\*\*[:：]\s*自然 (\d+) 层 / 被截断（体力耗尽）(\d+) 层")
RE_ORI = re.compile(r"\*\*取向\*\*[:：]\s*(auto|boundary|decision)")
RE_DEC = re.compile(r"\*\*可判定性\*\*[:：]\s*(\w+)")
RE_Q = re.compile(r"^# 元 DGTF · (.+)$", re.M)
LAYER2E = {"修行": "0", "研究": "1", "对撞": "both", "元": "all"}

_META = ("本身", "自身", "递归", "元", "整体", "到底")


def _fact(q):
    """同 `_has_decision_context` 的反面（此处自带一份纯规则近似，避免加载引擎）。"""
    return not any(k in q for k in ("如何", "怎么", "怎样", "方案", "落地",
                                    "选", "该做", "权衡", "要不要", "建议"))


def rec_from_md(p: Path) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace")
    m = RE_CALLS.search(t)
    if not m:
        return {}
    r = {"src": "md", "file": p.name,
         "calls": int(m.group(1)), "tokens": int(m.group(2))}
    mm = RE_MODE.search(t) or RE_MODE_SER.search(t)
    r["mode"] = mm.group(1) if mm else ""
    mp = RE_PROF.search(t)
    r["profile"] = mp.group(1) if mp else ""
    mo = RE_ORI.search(t)
    r["orientation"] = mo.group(1) if mo else ""
    md = RE_DEC.search(t)
    r["decidability"] = md.group(1) if md else ""
    mr = RE_ROUTE.search(t)
    if mr:
        layers = RE_LAYER.findall(mr.group(1))
        r["rounds"] = {LAYER2E.get(a, a): int(b) for a, b in layers}
        r["route"] = list(r["rounds"])
    ms = RE_STOP.search(t)
    if ms:
        r["nat"], r["cut"] = int(ms.group(1)), int(ms.group(2))
    mq = RE_Q.search(t)
    r["q"] = mq.group(1).strip() if mq else ""
    if r.get("q"):
        r["fact"] = _fact(r["q"])
        r["meta"] = any(k in r["q"] for k in _META)
        r["short"] = len(r["q"]) <= 40
    r["mtime"] = p.stat().st_mtime
    return r


def rec_from_packed(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(d, dict):
        return {}
    r = {"src": "packed", "file": p.name,
         "calls": int(d.get("llm_calls") or 0),
         "tokens": int(d.get("llm_tokens") or 0),
         "mode": str(((d.get("dispatch") or {}).get("_parallel_mode")) or ""),
         "profile": str(d.get("cost_profile") or ""),
         "orientation": str(d.get("orientation") or ""),
         "q": str(d.get("question") or "")}
    _t = d.get("tri_state") or [0, 0]
    try:
        r["tri"] = (int(_t[0]) / int(_t[1])) if int(_t[1]) else None
    except Exception:  # noqa: BLE001
        r["tri"] = None
    nat = cut = 0
    lr = {}
    for e, v in (d.get("views") or {}).items():
        sr = str((v or {}).get("stop_reason") or "")
        if sr:
            if ("体力耗尽" in sr) or ("被截断" in sr):
                cut += 1
            else:
                nat += 1
        rn = (v or {}).get("rounds")
        if isinstance(rn, int) and rn > 0:
            lr[e] = rn
    r["nat"], r["cut"] = nat, cut
    r["rounds"] = lr
    r["route"] = list(d.get("route") or [])
    web_hit = web_fail = web_empty = 0
    for pp in (d.get("pools") or {}).values():
        if not isinstance(pp, dict):
            continue
        web_hit += len(pp.get("web_results") or [])
        web_fail += len(pp.get("web_errors") or [])
        web_empty += sum(1 for x in (pp.get("meta") or [])
                         if "[W-EMPTY]" in str(x))
    r.update(web_hit=web_hit, web_fail=web_fail, web_empty=web_empty)
    r["fact"] = _fact(r["q"]) if r["q"] else None
    r["meta"] = any(k in (r["q"] or "") for k in _META)
    r["short"] = 0 < len(r["q"] or "") <= 40
    r["mtime"] = p.stat().st_mtime
    return r


def rec_from_batch(p: Path) -> list:
    out = []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    runs = d.get("runs") if isinstance(d, dict) else None
    if not isinstance(runs, list):
        return out
    for x in runs:
        if not isinstance(x, dict) or not x.get("ok"):
            continue
        q = str(x.get("question") or "")
        r = {"src": "batch:" + p.name, "file": str(x.get("job") or ""),
             "calls": int(x.get("llm_calls") or x.get("calls") or 0),
             "tokens": int(x.get("tokens") or 0),
             "mode": "", "profile": "", "orientation": "", "q": q,
             "web_hit": int(x.get("web_n") or 0),
             "web_fail": int(x.get("web_errors_n") or 0),
             "web_empty": int(x.get("web_empty_n") or 0),
             "secs": x.get("secs")}
        r["fact"] = _fact(q) if q else None
        r["meta"] = any(k in q for k in _META)
        r["short"] = 0 < len(q) <= 40
        r["mtime"] = p.stat().st_mtime
        out.append(r)
    return out


def quant(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def collect():
    recs = []
    for f in sorted(OUT.rglob("*.packed.json")):
        r = rec_from_packed(f)
        if r:
            recs.append(r)
    for f in sorted(OUT.rglob("*.md")):
        r = rec_from_md(f)
        if r:
            recs.append(r)
    for f in sorted(HERE.glob("*_runs.json")):
        if f.name.startswith("_bak_"):
            continue
        recs.extend(rec_from_batch(f))
    return recs


def summarize(recs):
    s = {"n": len(recs)}
    for k in ("calls", "tokens", "secs"):
        xs = [r.get(k) for r in recs
              if (r.get(k) or 0) > 0 or k == "calls"]
        s[k] = {q: quant(xs, q) for q in (0.1, 0.5, 0.9)} if any(
            x for x in xs) else None
    cut = nat = 0
    for r in recs:
        cut += int(r.get("cut") or 0)
        nat += int(r.get("nat") or 0)
    s["stop_layers"] = {"natural": nat, "cut": cut,
                        "cut_rate": (cut / (cut + nat)) if (cut + nat) else None}
    for k in ("mode", "profile", "orientation"):
        h = {}
        for r in recs:
            v = str(r.get(k) or "")
            if v:
                h[v] = h.get(v, 0) + 1
        s[k + "_hist"] = dict(sorted(h.items(), key=lambda x: -x[1]))
    lr = {}
    for r in recs:
        for e, v in (r.get("rounds") or {}).items():
            lr.setdefault(e, []).append(v)
    s["layer_rounds"] = {e: {"n": len(v), "p50": quant(v, 0.5),
                             "p90": quant(v, 0.9)} for e, v in lr.items()}
    for grp, pred in (("fact", lambda r: r.get("fact") is True),
                      ("nonfact", lambda r: r.get("fact") is False),
                      ("meta", lambda r: r.get("meta") is True),
                      ("short", lambda r: r.get("short") is True)):
        sub = [r for r in recs if pred(r)]
        if not sub:
            continue
        s[grp] = {"n": len(sub),
                  "calls_p50": quant([r.get("calls") for r in sub], 0.5),
                  "tokens_p50": quant([r.get("tokens") for r in sub], 0.5),
                  "tokens_p90": quant([r.get("tokens") for r in sub], 0.9),
                  "cut_rate": (sum(int(r.get("cut") or 0) for r in sub)
                               / max(1, sum(int(r.get("cut") or 0)
                                            + int(r.get("nat") or 0)
                                            for r in sub)))}
    web = {"hit": sum(int(r.get("web_hit") or 0) for r in recs),
           "fail": sum(int(r.get("web_fail") or 0) for r in recs),
           "empty": sum(int(r.get("web_empty") or 0) for r in recs),
           "runs_with_web": sum(1 for r in recs if (r.get("web_hit") or 0) > 0)}
    s["web"] = web
    return s


if __name__ == "__main__":
    recs = collect()
    sm = summarize(recs)
    # 按来源统计
    by_src = {}
    for r in recs:
        by_src[r["src"]] = by_src.get(r["src"], 0) + 1
    sm["by_source"] = by_src
    txt = json.dumps(sm, ensure_ascii=False, indent=1, default=str)
    print(txt)
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        Path(sys.argv[i + 1]).write_text(txt, encoding="utf-8")
        print("\n已写:", sys.argv[i + 1])
