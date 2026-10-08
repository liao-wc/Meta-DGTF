#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1 G1.9 / 阶段3 G3.6] bench 打分。

用法：
    python bench/bench_score.py bench/runs/<tag>/eng_001
    python bench/bench_score.py <某个产物.md>

输出：JSON（practice / research / decision / boundary 四组）。
每个打分函数都是**纯函数**（输入 md 文本），不给分时如实标 None，
不脑补、不用兜底值冒充满分。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _text(target: str) -> str:
    p = Path(target)
    if p.is_dir():
        mds = sorted(p.glob("*.md"))
        if not mds:
            return ""
        p = mds[-1]
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def score_practice(md: str) -> dict:
    """修行层：求显形不求答案。"""
    if not md:
        return {"score": None, "why": "无产物"}
    layers = re.findall(r"- \*\*(修行层|研究层|对撞层|元层)\*\*：objective=`(\w+)`",
                        md)
    prac = dict(layers).get("修行层")
    susp = len(re.findall(r"^- ⏸", md, re.M))
    unsaid = md.count("此处未生")
    ok = (prac == "manifest")
    return {"score": 1.0 if ok else 0.0,
            "objective": prac, "suspensions": susp, "unsaid_marks": unsaid,
            "why": "修行层 objective=manifest" if ok else f"objective={prac}"}


def score_research(md: str) -> dict:
    """研究层：求可判定的真（覆盖率是这一层的分母）。"""
    if not md:
        return {"score": None, "why": "无产物"}
    layers = dict(re.findall(
        r"- \*\*(修行层|研究层|对撞层|元层)\*\*：objective=`(\w+)`", md))
    obj = layers.get("研究层")
    cov = re.search(r"可判定覆盖率\s*([\d.]+%|N/A)", md)
    tri = re.search(r"三态判决一致率\*\*：(\d+)/(\d+)", md)
    ratio = (int(tri.group(1)) / int(tri.group(2))) if tri and int(tri.group(2)) else None
    return {"score": 1.0 if obj == "truth" else 0.0,
            "objective": obj,
            "coverage": cov.group(1) if cov else None,
            "tri_ratio": round(ratio, 3) if ratio is not None else None,
            "why": "研究层 objective=truth" if obj == "truth" else f"objective={obj}"}


def score_decision_rubric(md: str) -> dict:
    """[阶段3 G3.6] decision 题 rubric（0~3 分）。

    三条判据各自独立，缺一条扣一分：
      1. 有行动清单段且 action 数 ≥ 3；
      2. 每条 action 六字段齐全（verb/object/owner_role/deadline_hint/
         acceptance/fallback）；
      3. 有「不做清单」（not_do）或回退路径至少一条。
    """
    if not md:
        return {"score": None, "why": "无产物"}
    acts = re.findall(r"^- \*\*(A\d+)\*\*\s*(.+)$", md, re.M)
    n = len(acts)
    keys = ("verb", "object", "owner_role", "deadline_hint", "acceptance",
            "fallback")
    complete = 0
    for _aid, body in acts:
        if all(re.search(rf"{k}\s*=", body) for k in keys):
            complete += 1
    has_notdo = ("不做清单" in md) or ("## 不做" in md) or ("fallback=" in md)
    s = 0
    if n >= 3:
        s += 1
    if n > 0 and complete == n:
        s += 1
    if has_notdo and n > 0:
        s += 1
    return {"score": s, "actions": n, "complete_actions": complete,
            "not_do": has_notdo,
            "why": f"action={n} 齐全={complete} 不做/回退={has_notdo}"}


def score_boundary(md: str) -> dict:
    """boundary 题：要的是边界清单，不能退化成行动清单。"""
    if not md:
        return {"score": None, "why": "无产物"}
    has_boundary = ("边界 —— 判不出 / 决定不碰" in md
                    or "### 四、边界" in md)
    has_action = ("### 二、行动清单" in md)
    return {"score": 1.0 if (has_boundary and not has_action) else 0.0,
            "boundary_block": has_boundary, "action_block": has_action,
            "why": "走边界模板" if has_boundary and not has_action
                   else f"boundary={has_boundary} action={has_action}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    a = ap.parse_args()
    md = _text(a.target)
    out = {
        "target": a.target,
        "practice": score_practice(md),
        "research": score_research(md),
        "decision": score_decision_rubric(md),
        "boundary": score_boundary(md),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ============================================================
# [v122 G1.9 / G3.6 结构化输入版]
# ============================================================
# 为什么与上面的 md 版并存：两者**测的不是同一个对象** ——
#   · md 版读**读者看到的那份文本**；
#   · 下面这组读 `packed.json` 里的**结构化字段**。
# 本项目的老坑正是「日志侧与产物侧标记串不同，照一侧数另一侧得 0」，
# 所以两侧都留着、互相核对；报告以结构化侧为主判据。
# 它们不是「同一条逻辑两条通道各写一份」——那说的是同一对象写两遍。

def score_practice_packed(res) -> dict:
    v = (res.get("views") or {}).get("0") or {}
    return {"amps": len(v.get("amps") or []),
            "threads": len(v.get("threads") or []),
            "suspensions": len(v.get("suspensions") or []),
            "probes": len(v.get("probes") or [])}


def score_research_packed(res) -> dict:
    v = (res.get("views") or {}).get("1") or {}
    st = v.get("settlement") or {}
    dp = v.get("decidable_product") or {}
    return {"coverage": st.get("coverage"),
            "answered_xy": f"{st.get('answered', '?')}/{st.get('total', '?')}",
            "distance": dp.get("distance")}


def score_meta(res) -> dict:
    v = (res.get("views") or {}).get("all") or {}
    clo = v.get("meta_closure") or {}
    return {"clean": clo.get("clean"), "unsettled": clo.get("unsettled")}


def score_actions(actions, not_do, min_actions: int = 3) -> dict:
    """decision rubric（结构化）：三项各 1 分，上限 3。

      ① 行动条数 ≥ min_actions
      ② 每条都带回退（非「（未指定）」）
      ③ 有「不做什么」清单
    ★ 负对照（冒烟里）：`actions=[]` 且 `not_do=[]` 必须得 **0 分** ——
      否则这份 rubric 永远给分，等于没判。
    """
    acts = list(actions or [])
    nd = list(not_do or [])
    s = 0
    if len(acts) >= min_actions:
        s += 1
    if acts and all(a.get("fallback") and a["fallback"] != "（未指定）"
                    for a in acts):
        s += 1
    if nd:
        s += 1
    return {"score": s, "max": 3, "n_actions": len(acts), "n_not_do": len(nd)}

