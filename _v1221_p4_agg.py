#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P4.3] 汇总 ON/OFF 两条臂的一致率读数。

读 `runs/v1221/p4_{ON,OFF}_{1..3}/meta.json`（由 `_run_v1221_p4.py` 产出），
写 `_v1221_p4_consistency.json`。

★ 本脚本要处理一个**实测发现的方法学问题**：
  任务书指定的口径是产物 md 里的「三态多票：high N / medium N / low N」行。
  而那一行读的是每条子问题的 `stability` 字段 —— **只有多票路径（ON）才写它**。
  OFF 臂的子问题里 `stability` **键都不存在**，于是引擎那一行照 `(0+0)/5` 印出
  「一致率 0%　⚠️ unstable（＜50%）」—— 这是**非读数**（没算），不是测量值。

  所以本脚本给两份 summary：
    · `summary`（md 口径，任务书口径）—— 附 `md_metric.usable` 标注可用性；
    · `fair`（tri_state 一致率，**两臂都可得**）—— 才是可比的对照。
  判定以 `fair` 为准，`summary` 保留在文件里供核对。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs" / "v1221"
OUT = HERE / "_v1221_p4_consistency.json"


def _packed_of(md_path: str) -> dict:
    p = Path(md_path or "")
    if not p.is_file():
        return {}
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        return {}
    for blk in re.findall(r"```json\s*(.*?)```", t, re.S):
        try:
            d = json.loads(blk)
            if isinstance(d, dict):
                return d
        except Exception:
            continue
    return {}


def _load(arm: str, i: int):
    mf = RUNS / ("p4_" + arm + "_" + str(i)) / "meta.json"
    if not mf.is_file():
        return None
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return None


def _avg(v):
    return sum(v) / len(v) if v else None


def _spread(v):
    return (max(v) - min(v)) if v else None


def _verdict(diff, sp_on, sp_off):
    if diff is None or sp_on is None or sp_off is None:
        return None, None
    no_concl = max(sp_on, sp_off) >= abs(diff)
    if diff >= 0.10:
        v = "多票更好"
    elif abs(diff) < 0.05:
        v = "多票没做坏，也没做出改善"
    elif diff <= -0.05:
        v = "多票拖后腿"
    else:
        v = "灰带（+5%~+10%，P4.4 未给档）"
    return ("无结论（组内极差 ≥ 组间差）" if no_concl else v), no_concl


def main() -> int:
    out = {"ON": [], "OFF": [], "items": {"ON": [], "OFF": []},
           "tri_state": {"ON": [], "OFF": []}, "alerts": []}
    _stab_present = {"ON": [], "OFF": []}
    for arm in ("ON", "OFF"):
        for i in (1, 2, 3):
            d = _load(arm, i)
            if not d or not d.get("ok"):
                out["alerts"].append(arm + "_" + str(i) + " 未完成")
                continue
            md = d.get("md_reading")
            if md:
                out[arm].append(md)
            pk = _packed_of(d.get("md") or "")
            sq = (((pk.get("pools") or {}).get("1") or {})
                  .get("sub_questions") or [])
            if sq:
                _stab_present[arm].append("stability" in sq[0])
            ts = pk.get("tri_state")
            if isinstance(ts, list) and len(ts) == 2:
                try:
                    out["tri_state"][arm].append(
                        [int(ts[0]), int(ts[1])])
                except (TypeError, ValueError):
                    pass
            out["items"][arm].append({
                "rep": i, "calls": d.get("calls"), "tokens": d.get("tokens"),
                "md_reading": md, "structured": d.get("structured"),
                "tri_consensus": d.get("tri_consensus"), "tri_state": ts})

    # ---- md 口径（任务书口径）----
    _on = [x["consistency"] for x in out["ON"]
           if x.get("consistency") is not None]
    _off = [x["consistency"] for x in out["OFF"]
            if x.get("consistency") is not None]
    s = {"n_on": len(_on), "n_off": len(_off),
         "on_avg": _avg(_on), "off_avg": _avg(_off),
         "diff": (None if not (_on and _off) else _avg(_on) - _avg(_off)),
         "on_spread": _spread(_on), "off_spread": _spread(_off)}
    s["verdict"], s["no_conclusion"] = _verdict(
        s["diff"], s["on_spread"], s["off_spread"])
    out["summary"] = s

    # ---- 可用性判定：OFF 臂的 stability 键在不在 ----
    _off_stab = _stab_present["OFF"]
    _usable = bool(_off_stab) and all(_off_stab)
    out["md_metric"] = {
        "name": "md 行「三态多票：high/medium/low」一致率",
        "usable": _usable,
        "stability_key_present": {"ON": _stab_present["ON"],
                                  "OFF": _stab_present["OFF"]},
        "reason": ("两臂都写了 stability，md 口径可比" if _usable else
                   "OFF 臂子问题**没有 stability 键** → 引擎那一行按 (0+0)/n "
                   "印成「一致率 0%」，那是**非读数**（没算），不是测量值。"
                   "该口径在 OFF 臂上不可用。")}
    if not _usable:
        out["alerts"].append(
            "md 口径在 OFF 臂不可用（缺 stability 键）→ 不能用它得出"
            "「多票更好 +100%」这类结论")

    # ---- 公平口径：tri_state 一致率（两臂都可得）----
    def _rates(arm):
        v = []
        for a, t in out["tri_state"][arm]:
            if t:
                v.append(a / t)
        return v

    _ron, _roff = _rates("ON"), _rates("OFF")
    f = {"metric": "tri_state 一致率（agree/total，两臂都可得）",
         "on": _ron, "off": _roff,
         "on_avg": _avg(_ron), "off_avg": _avg(_roff),
         "diff": (None if not (_ron and _roff) else _avg(_ron) - _avg(_roff)),
         "on_spread": _spread(_ron), "off_spread": _spread(_roff)}
    f["verdict"], f["no_conclusion"] = _verdict(
        f["diff"], f["on_spread"], f["off_spread"])
    out["fair"] = f

    OUT.write_bytes(json.dumps(out, ensure_ascii=False, indent=2)
                    .encode("utf-8"))
    print("✓ " + OUT.name)
    print("  md 口径（任务书）   ON " + str([round(x, 3) for x in _on])
          + " / OFF " + str([round(x, 3) for x in _off])
          + "  可用=" + str(_usable))
    print("  tri_state 公平口径  ON " + str([round(x, 3) for x in _ron])
          + " / OFF " + str([round(x, 3) for x in _roff]))
    print("  fair: " + json.dumps(
        {k: (round(v, 4) if isinstance(v, float) else v)
         for k, v in f.items() if k not in ("on", "off")}, ensure_ascii=False))
    if out["alerts"]:
        print("  ⚠️ alerts: " + json.dumps(out["alerts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
