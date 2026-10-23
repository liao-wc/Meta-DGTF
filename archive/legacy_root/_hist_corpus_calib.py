# -*- coding: utf-8 -*-
"""历史真跑语料分析（校准版）：分组用**引擎自己的判据**，cap 与实际停圈分开。

与 `_hist_corpus.py` 的关系：前者是快速版（自带近似题型规则）；本版
import 引擎，用 `_has_decision_context` 做权威分组，并把
「种子圈数上限（md 的 `**调度**` 行）」与「实际停圈（packed 的 `views.*.rounds`）」
**分开统计** —— 两者混在一起会让「历史停圈」这个读数虚高。

用法：python _hist_corpus_calib.py [引擎文件.py] [--json 输出]
"""
import importlib.util
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


def load_engine(p):
    spec = importlib.util.spec_from_file_location("m_calib", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["m_calib"] = m
    spec.loader.exec_module(m)
    return m


def quant(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def qs(xs, label):
    return {label: {"n": len([x for x in xs if x is not None]),
                    "p25": quant(xs, .25), "p50": quant(xs, .50),
                    "p75": quant(xs, .75), "p90": quant(xs, .90)}}


def main():
    eng = load_engine(sys.argv[1] if len(sys.argv) > 1 and
                      sys.argv[1].endswith(".py") else "元DGTF-V1.23.13.py")
    has_dec = getattr(eng, "_has_decision_context", None)

    def fact_of(q):
        return None if not q else (not has_dec(q))

    recs = []
    for f in sorted(OUT.rglob("*.packed.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        q = str(d.get("question") or "")
        nat = cut = 0
        actual = {}
        for e, v in (d.get("views") or {}).items():
            sr = str((v or {}).get("stop_reason") or "")
            if sr:
                cut += 1 if (("体力耗尽" in sr) or ("被截断" in sr)) else 0
                nat += 0 if (("体力耗尽" in sr) or ("被截断" in sr)) else 1
            rn = (v or {}).get("rounds")
            if isinstance(rn, int) and rn > 0:
                actual[e] = rn
        _t = d.get("tri_state") or [0, 0]
        try:
            tri = (int(_t[0]) / int(_t[1])) if int(_t[1]) else None
        except Exception:  # noqa: BLE001
            tri = None
        wh = wf = we = 0
        for pp in (d.get("pools") or {}).values():
            if isinstance(pp, dict):
                wh += len(pp.get("web_results") or [])
                wf += len(pp.get("web_errors") or [])
                we += sum(1 for x in (pp.get("meta") or [])
                          if "[W-EMPTY]" in str(x))
        recs.append({"src": "packed", "q": q, "fact": fact_of(q),
                     "meta": any(k in q for k in
                                 ("本身", "自身", "递归", "元", "整体", "到底")),
                     "calls": int(d.get("llm_calls") or 0),
                     "tokens": int(d.get("llm_tokens") or 0),
                     "mode": str(((d.get("dispatch") or {}).get(
                         "_parallel_mode")) or ""),
                     "profile": str(d.get("cost_profile") or ""),
                     "nat": nat, "cut": cut, "actual_rounds": actual,
                     "tri": tri, "web_hit": wh, "web_fail": wf,
                     "web_empty": we})

    for f in sorted(OUT.rglob("*.md")):
        t = f.read_text(encoding="utf-8", errors="replace")
        m = RE_CALLS.search(t)
        if not m:
            continue
        q = (RE_Q.search(t).group(1).strip() if RE_Q.search(t) else "")
        r = {"src": "md", "q": q, "fact": fact_of(q),
             "meta": any(k in q for k in
                         ("本身", "自身", "递归", "元", "整体", "到底")),
             "calls": int(m.group(1)), "tokens": int(m.group(2)),
             "mode": (RE_MODE.search(t) or RE_MODE_SER.search(t)).group(1)
             if (RE_MODE.search(t) or RE_MODE_SER.search(t)) else "",
             "profile": (RE_PROF.search(t).group(1)
                         if RE_PROF.search(t) else ""),
             "cap_rounds": {}, "actual_rounds": {}}
        mr = RE_ROUTE.search(t)
        if mr:
            r["cap_rounds"] = {LAYER2E.get(a, a): int(b)
                               for a, b in RE_LAYER.findall(mr.group(1))}
        ms = RE_STOP.search(t)
        if ms:
            r["nat"], r["cut"] = int(ms.group(1)), int(ms.group(2))
        recs.append(r)

    for f in sorted(HERE.glob("*_runs.json")):
        if f.name.startswith("_bak_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for x in (d.get("runs") if isinstance(d, dict) else []) or []:
            if not isinstance(x, dict) or not x.get("ok"):
                continue
            q = str(x.get("question") or "")
            recs.append({"src": "batch:" + f.name,
                         "q": q, "fact": fact_of(q),
                         "meta": any(k in q for k in
                                     ("本身", "自身", "递归", "元", "整体", "到底")),
                         "calls": int(x.get("llm_calls") or x.get("calls") or 0),
                         "tokens": int(x.get("tokens") or 0),
                         "mode": "", "profile": "", "actual_rounds": {},
                         "web_hit": int(x.get("web_n") or 0),
                         "web_fail": int(x.get("web_errors_n") or 0),
                         "web_empty": int(x.get("web_empty_n") or 0),
                         "secs": x.get("secs")})

    S = {"n": len(recs)}
    S["by_source"] = {}
    for r in recs:
        S["by_source"][r["src"]] = S["by_source"].get(r["src"], 0) + 1

    def grp(name, pred):
        sub = [r for r in recs if pred(r)]
        if not sub:
            return
        g = {"n": len(sub)}
        g.update(qs([r.get("calls") for r in sub], "calls"))
        g.update(qs([r.get("tokens") if (r.get("tokens") or 0) > 0 else None
                     for r in sub], "tokens"))
        _cut = sum(int(r.get("cut") or 0) for r in sub)
        _nat = sum(int(r.get("nat") or 0) for r in sub)
        g["cut_rate"] = round(_cut / (_cut + _nat), 3) if (_cut + _nat) else None
        for e in ("0", "1", "both", "all"):
            xs = [(r.get("actual_rounds") or {}).get(e) for r in sub]
            if any(xs):
                g["actual_rounds_" + e] = qs(xs, e)
        S[name] = g

    grp("all", lambda r: True)
    grp("fact", lambda r: r.get("fact") is True)
    grp("nonfact", lambda r: r.get("fact") is False)
    grp("meta", lambda r: r.get("meta") is True)
    grp("nomemeta", lambda r: r.get("meta") is False)

    # 种子圈数上限（md 的 `**调度**` 行）
    caps = {}
    for r in recs:
        for e, v in (r.get("cap_rounds") or {}).items():
            caps.setdefault(e, []).append(v)
    S["cap_rounds"] = {e: qs(v, e) for e, v in caps.items()}

    # 模式 / 档位 / 取向
    for k in ("mode", "profile"):
        h = {}
        for r in recs:
            v = str(r.get(k) or "")
            if v:
                h[v] = h.get(v, 0) + 1
        S[k + "_hist"] = dict(sorted(h.items(), key=lambda x: -x[1]))
    web = {"runs_total": len(recs),
           "hit": sum(int(r.get("web_hit") or 0) for r in recs),
           "fail": sum(int(r.get("web_fail") or 0) for r in recs),
           "empty": sum(int(r.get("web_empty") or 0) for r in recs),
           "runs_with_web": sum(1 for r in recs if (r.get("web_hit") or 0) > 0),
           "runs_with_empty": sum(1 for r in recs
                                  if (r.get("web_empty") or 0) > 0),
           "runs_with_fail": sum(1 for r in recs
                                 if (r.get("web_fail") or 0) > 0)}
    S["web"] = web
    tq = [r.get("tri") for r in recs if r.get("tri") is not None]
    S["tri_rate"] = {"n": len(tq), "p25": quant(tq, .25),
                     "p50": quant(tq, .50), "p75": quant(tq, .75)}

    txt = json.dumps(S, ensure_ascii=False, indent=1, default=str)
    print(txt)
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        Path(sys.argv[i + 1]).write_text(txt, encoding="utf-8")
        print("\n已写:", sys.argv[i + 1])


if __name__ == "__main__":
    main()
