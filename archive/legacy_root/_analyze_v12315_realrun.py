# -*- coding: utf-8 -*-
"""分析 v1.23.15 真跑对照实验的产物：停止行为 / 实际停圈 / 上限×成本 / 联网 / 调度表。

用法：python _analyze_v12315_realrun.py
产出：`_v12315_realrun_analysis.json` + 终端摘要。
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "outputs"
GROUPS = ["up2", "up6", "up10", "auto"]

RE_CALLS = re.compile(r"\*\*资源\*\*[:：]\s*(\d+) 次 LLM \| (\d+) tokens")
RE_SCHED = re.compile(r"\*\*调度\*\*[:：]\s*(.+)")
RE_LAYER = re.compile(r"([\u4e00-\u9fff]+)\((\d+)圈\)")
RE_MODE = re.compile(r"\*\*并行模式\*\*[:：]\s*([A-H]|严格串行)")
RE_PROF = re.compile(r"\*\*成本档位\*\*[:：]\s*(\w+)")
RE_STOP = re.compile(r"\*\*停止\*\*[:：]\s*自然\s*(\d+)\s*层\s*/\s*被截断（体力耗尽）\s*(\d+)\s*层")
RE_RUN = re.compile(r"\*\*实际停圈\*\*[:：]\s*(.+)")
RE_RUNL = re.compile(r"([\u4e00-\u9fff]+)\s*(\d+)\s*圈(?:（上限\s*(\d+)）)?")
RE_TRI = re.compile(r"\*\*三态判决一致率\*\*[:：]\s*(\d+)\s*/\s*(\d+)")
RE_WEB = re.compile(r"\*\*外部锚点 · 联网\*\*（`web_search`）[:：]\s*(.+)")
RE_AUTO = re.compile(r"\*\*自动调度\*\*（十二项逐项来源；(.+?)）")


def one(g):
    _d = ROOT / ("_v12315_" + g)
    mds = sorted(_d.glob("*.md")) if _d.is_dir() else []
    if not mds:
        return {"group": g, "md": None}
    f = mds[-1]
    t = f.read_text(encoding="utf-8", errors="replace")
    r = {"group": g, "md": f.name}
    m = RE_CALLS.search(t)
    if m:
        r["calls"], r["tokens"] = int(m.group(1)), int(m.group(2))
    m = RE_SCHED.search(t)
    if m:
        r["cap"] = {a: int(b) for a, b in RE_LAYER.findall(m.group(1))}
    m = RE_MODE.search(t)
    if m:
        r["mode"] = m.group(1)
    m = RE_PROF.search(t)
    if m:
        r["profile"] = m.group(1)
    m = RE_STOP.search(t)
    if m:
        r["nat"], r["cut"] = int(m.group(1)), int(m.group(2))
    m = RE_RUN.search(t)
    if m:
        r["rounds_run"] = {a: {"run": int(b), "cap": int(c) if c else None}
                           for a, b, c in RE_RUNL.findall(m.group(1))}
    m = RE_TRI.search(t)
    if m and int(m.group(2)):
        r["tri"] = round(int(m.group(1)) / int(m.group(2)), 3)
    m = RE_WEB.search(t)
    if m:
        r["web_line"] = m.group(1)[:120]
    m = RE_AUTO.search(t)
    if m:
        r["auto_head"] = m.group(1)
    r["has_auto_table"] = "**自动调度**（十二项" in t
    r["has_rounds_run_line"] = "**实际停圈**：" in t
    return r


def main():
    rows = [one(g) for g in GROUPS]
    SU = HERE / "_v12315_realrun_summary.json"
    if SU.is_file():
        try:
            _s = {x["group"]: x for x in json.loads(SU.read_text(encoding="utf-8"))}
            for r in rows:
                r.update({k: v for k, v in _s.get(r["group"], {}).items()
                          if k in ("rc", "secs", "args")})
        except Exception:  # noqa: BLE001
            pass
    print("%-6s %-6s %7s %9s %8s %-10s %-8s %s"
          % ("组", "rc", "秒", "calls", "tokens", "自然/截断", "模式", "实际停圈"))
    for r in rows:
        print("%-6s %-6s %7s %9s %8s %-10s %-8s %s"
              % (r["group"], r.get("rc", "—"), r.get("secs", "—"),
                 r.get("calls", "—"), r.get("tokens", "—"),
                 ("%s/%s" % (r.get("nat", "?"), r.get("cut", "?")))
                 if "nat" in r else "—",
                 r.get("mode", "—"),
                 json.dumps(r.get("rounds_run") or {}, ensure_ascii=False)))
    print()
    for r in rows:
        if r.get("web_line"):
            print("[%s] 联网行: %s" % (r["group"], r["web_line"]))
        if r.get("auto_head"):
            print("[%s] 调度表头: %s" % (r["group"], r["auto_head"]))
        print("[%s] 有调度表=%s 有实际停圈行=%s tri=%s"
              % (r["group"], r.get("has_auto_table"), r.get("has_rounds_run_line"),
                 r.get("tri")))
    out = HERE / "_v12315_realrun_analysis.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("\n已写:", out.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
