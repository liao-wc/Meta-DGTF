# -*- coding: utf-8 -*-
"""Step11 真跑产物核对：检查 v1.23.27 新机制是否落盘。

用法：
    python _verify_v12327_artifacts.py <packed.json 路径>
不带参数时自动取「最新且属于本版真跑」的 packed.json（排除并行线产物）。
"""
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(".")


def _pick() -> Path:
    """挑最新 packed.json；排除 selftest / 手动终止产物。"""
    cand = []
    for p in ROOT.glob("outputs/*.packed.json"):
        n = p.name
        if "验收" in n or "手动终止" in n:
            continue
        cand.append((p.stat().st_mtime, p))
    if not cand:
        raise SystemExit("找不到 packed.json")
    cand.sort(reverse=True)
    return cand[0][1]


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else _pick()
    print("=" * 68)
    print("核对产物：%s" % p)
    print("大小：%d bytes / 修改：%s"
          % (p.stat().st_size,
             datetime.fromtimestamp(p.stat().st_mtime)
             .strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 68)

    d = json.loads(p.read_text(encoding="utf-8"))
    views = d.get("views") or {}
    pools = d.get("pools") or {}

    hits = {k: 0 for k in (
        "aspect_units", "aspect_targets", "belief_items",
        "belief_transitions", "probe_stop_history", "covered_unders")}

    def scan(obj, depth=0):
        if depth > 12:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in hits and v:
                    hits[k] += 1
                scan(v, depth + 1)
        elif isinstance(obj, list):
            for it in obj[:400]:
                scan(it, depth + 1)

    scan(d)

    print("\n【A1/A2/D1/D2/E6 新字段落盘命中】")
    for k, v in hits.items():
        mark = "✅" if v else "⚠️ "
        print("  %s %-20s 命中 %d 处" % (mark, k, v))

    # ── A1：aspect_units 是否在 view 里（预期缺失，见报告 §3.2） ──
    print("\n【A1 明细】")
    found_au = []
    for ek, v in (views or {}).items():
        au = (v or {}).get("aspect_units")
        if au:
            found_au.append((ek, len(au)))
    if found_au:
        for ek, n in found_au:
            print("  ✅ view[%s].aspect_units = %d 条" % (ek, n))
    else:
        print("  ⚠️  所有 view 都无 aspect_units（预期：本版无 to_dict 出口）")

    # ── D1：四态计数 ──
    print("\n【D1 四态计数】")
    tot = {}
    for pk, pool in (pools or {}).items():
        bis = (pool or {}).get("belief_items") or []
        if not bis:
            continue
        c = {}
        for b in bis:
            s = str(b.get("status") or "?")
            c[s] = c.get(s, 0) + 1
        tot[pk] = c
        print("  pool[%s] 共 %d 条：%s" % (pk, len(bis), c))
    if not tot:
        print("  ⚠️  pools 里没有 belief_items")

    # ── E6：停止历史 ──
    print("\n【E6 停止历史】")
    n_stop = 0
    for pk, pool in (pools or {}).items():
        h = (pool or {}).get("probe_stop_history") or []
        if h:
            n_stop += len(h)
            print("  pool[%s]：%d 条 %s"
                  % (pk, len(h), [x.get("reason") for x in h]))
    if not n_stop:
        print("  ⚠️  无 probe_stop_history（预期：真跑每层都有探针，"
              "不进 `if not out` 分支 —— 见报告 §3.2）")

    # ── E1/E2：探针的引擎增益 ──
    print("\n【E1/E2 探针增益（引擎算的 G）】")
    n_probe = 0
    n_engine = 0
    n_model = 0
    for pk, pool in (pools or {}).items():
        for p in (pool or {}).get("probes") or []:
            n_probe += 1
            src = str(p.get("gain_source") or "")
            if src == "engine" or p.get("expected_gain_engine") is not None:
                n_engine += 1
            elif src == "model":
                n_model += 1
    print("  探针总数 %d；gain_source=engine %d；=model %d"
          % (n_probe, n_engine, n_model))
    if n_probe and not n_engine:
        print("  ⚠️  无引擎算的增益（E1/E2 未生效或池未决 <2）")
    elif n_engine:
        print("  ✅ 引擎算的 G 已落在探针上（E1/E2 生效）")

    # ── view 层探针与覆盖 ──
    print("\n【A2 覆盖对账】")
    n_cov = 0
    n_unc = 0
    for ek, v in (views or {}).items():
        c = len((v or {}).get("covered_aspects") or [])
        u = len((v or {}).get("uncovered_aspects") or [])
        n_cov += c
        n_unc += u
        if c or u:
            print("  view[%s]：covered=%d uncovered=%d" % (ek, c, u))
    if not (n_cov or n_unc):
        print("  ⚠️  无覆盖对账字段")

    print("\n" + "=" * 68)
    print("核对完成。")
    print("=" * 68)


if __name__ == "__main__":
    main()
