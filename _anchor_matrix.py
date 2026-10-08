# -*- coding: utf-8 -*-
"""
锚点对照总表 —— 把**所有**跑臂（v73arm/v74arm/v75arm_*）汇总成一张表。

为什么单独做一份：原来 `_anchor_report.py` 只比一对 ON/OFF。
评审要求 n>=5，逐对看会看不出整体分布，而且容易只挑好看的那对。

口径（改动前先读）：
  · 三态（印证/冲突/无对应）来自 packed 的 external_anchor.summary。
  · `pooled` 是 v1.21.75 起的入池条数（**无条件写**，0 也写）；
    v1.21.73/74 没有这个键 → 标 "—（无此字段）"，**不填 0** —— 分不清
    「没入池」和「没这个字段」是本项目反复踩的坑。
  · `anchor_used == 0` 表示一条锚点都没用上，踩预注册的「接入失败线」。
  · 耗时从跑臂日志里的 elapsed 取（取不到标 —）。

用法：
  python _anchor_matrix.py              # 扫全部
  python _anchor_matrix.py v75arm       # 只扫某一版
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_arm(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def elapsed_of(tag: str, prefix: str) -> str:
    lp = HERE / f"{prefix}_{tag}.log"
    if not lp.exists():
        return "—"
    try:
        txt = lp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "—"
    m = re.findall(r"耗时\s*([\d.]+)\s*(?:分钟|min)", txt)
    if m:
        return f"{m[-1]} min"
    m = re.findall(r"elapsed\s*[=:]\s*([\d.]+)", txt)
    if m:
        return f"{m[-1]}s"
    return "—"


def row_of(prefix: str, tag: str) -> dict:
    p = HERE / f"{prefix}_{tag}.full.json"
    d = load_arm(p)
    if "_err" in d:
        return {"tag": tag, "err": d["_err"]}
    ea = d.get("external_anchor")
    sm = (ea or {}).get("summary") or {}
    dec = d.get("decidability") or {}
    r = {
        "tag": tag,
        "question": str(d.get("question", ""))[:26],
        "calls": d.get("llm_calls"),
        "tokens": d.get("llm_tokens"),
        "elapsed": elapsed_of(tag, prefix),
        "decidability": dec.get("decidability", "—"),
        "anchors": (ea or {}).get("anchors"),
        "pooled": (ea or {}).get("pooled"),
        "as_evidence": (ea or {}).get("as_evidence"),
        "anchor_calls": (ea or {}).get("anchor_calls"),
        "claims": sm.get("claims"),
        "supported": sm.get("supported"),
        "conflicted": sm.get("conflicted"),
        "unmatched": sm.get("unmatched"),
        "anchor_used": sm.get("anchor_used"),
        "error": (ea or {}).get("error") or "",
    }
    return r


def fmt(v, dash="—（无此字段）"):
    if v is None:
        return dash
    return str(v)


def main() -> int:
    prefixes = sys.argv[1:] or ["v73arm", "v74arm", "v75arm"]
    all_rows = []
    for pfx in prefixes:
        files = sorted(HERE.glob(f"{pfx}_*.full.json"))
        for f in files:
            tag = f.name[len(pfx) + 1:-len(".full.json")]
            r = row_of(pfx, tag)
            r["_pfx"] = pfx
            all_rows.append(r)

    if not all_rows:
        print("没找到任何跑臂 JSON")
        return 1

    print("## 锚点对照总表\n")
    hdr = ("版本/臂", "题面", "calls", "tokens", "耗时", "三态判定",
           "锚点数", "入池", "作证据", "锚点调用", "claims",
           "印证", "冲突", "无对应", "用到锚点")
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    for r in all_rows:
        if "err" in r:
            print(f"| {r['_pfx']}/{r['tag']} | ✗ {r['err']} | | | | | | | "
                  f"| | | | | | |")
            continue
        print("| " + " | ".join([
            f"{r['_pfx']}/{r['tag']}",
            r["question"],
            fmt(r["calls"]),
            fmt(r["tokens"]),
            r["elapsed"],
            fmt(r["decidability"]),
            fmt(r["anchors"]),
            fmt(r["pooled"]),
            fmt(r["as_evidence"]),
            fmt(r["anchor_calls"]),
            fmt(r["claims"]),
            fmt(r["supported"]),
            fmt(r["conflicted"]),
            fmt(r["unmatched"]),
            fmt(r["anchor_used"]),
        ]) + " |")

    print("\n## 判读\n")
    # 接入失败线
    failed = [r for r in all_rows
              if "err" not in r
              and r.get("anchors")
              and r.get("anchor_used") == 0]
    if failed:
        print("**踩「接入失败线」的臂**（有锚点却一条没用上 → "
              "三态数字判无效，不得读成「没有冲突」）：")
        for r in failed:
            print(f"- {r['_pfx']}/{r['tag']}：锚点 {r['anchors']} 条，"
                  f"claims {r['claims']} 条，用到 0")
    else:
        print("没有臂踩接入失败线。")

    # pooled 可用性
    nosup = [r for r in all_rows if "err" not in r and r.get("pooled") is None]
    if nosup:
        print(f"\n**没有 `pooled` 字段的臂**（{len(nosup)} 个，"
              f"v1.21.73/74 老数据，不是 0）：")
        print("  " + "、".join(f"{r['_pfx']}/{r['tag']}" for r in nosup))

    out = HERE / "_anchor_matrix.md"
    out.write_text("\n".join(
        ["（由 _anchor_matrix.py 生成）", ""]
        + [l for l in []]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
