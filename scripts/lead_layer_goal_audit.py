# -*- coding: utf-8 -*-
"""四层目标读数的离线普查（V2.2.12 goal_now/verdict 落盘 + 历史包只读复算）。

回答的问题（每层分别回答，不许混）
-----------------------------------
  1) 跑了没跑：views 里有该层 key 不等于该层跑了。判据 = view.rounds_run > 0；
     route 短跑时上游层也会被携带进 views（如 --route 1 会带 layer 0 的 view），
     它的 rounds_run 缺失/为 0，记为「仅携带，没跑」。
  2) 读数有没有：主读数（_LG_KEYS 那一条）从哪来 —— 落盘 goal_now / 旧版
     verdict 文本 / 用当前最高版引擎对该 view 的只读复算（旧包无 goal_now 出口）。
  3) 读数是多少：主读数数值 + 逐层依据字段（excavate_basis / settlement /
     n_new,n_upstream / crystallize_detail）。
  4) 够不够达到目标：用引擎自己的 layer_goal_stop_signal（四层目标 -> 停因）判定：
     达成 / 受阻 / 未达成 / 判据样本不足（结构不可达）/ 未测出。
     另列「当时停因是否命中」（stop_reason 文本里的「目标已达成 / 目标受阻」），
     它是运行中判据真的触发过的直接证据。

只读：本脚本不写产物、不跑引擎、不调 LLM。--selfcheck 在内存里造变异体，证明
关键护栏有牙（落盘读数 vs 独立复算不一致 / verdict 空 / goal_now 缺 / 未测出
原因为空 / 零 LLM 产物被判达成 / 零 LLM 未测出原因为空）。变异体没被抓到 => 退出码 1。

★ 「离线复算」是本脚本内的独立实现（recompute_layer_goal，同公式、独立代码），
  刻意不调用引擎的 layer_goal_readings / _lg_* —— 否则引擎改了公式、落盘还是旧值，
  自己校验自己永远绿。引擎只提供 _LG_KEYS / _LG_LABELS 与停止判据（目标定义），
  不参与读数复算。
★ 零 LLM 产物判据：llm_calls==0 的跑次里，跑过的层不许判「达成」，verdict 必须
  非空、未测出必须带可指认原因（12:55 shim 死掉那类跑次不能被读成「模型能力不足」
  或「挖尽」）。

用法
----
  python scripts/lead_layer_goal_audit.py
  python scripts/lead_layer_goal_audit.py --json
  python scripts/lead_layer_goal_audit.py --selfcheck
  python scripts/lead_layer_goal_audit.py --packs outputs --packs outputs/_e2e_local
退出码：0 = 普查完成（这是读数报告，不是门禁）；1 = --selfcheck 有护栏没牙；
        2 = 没有产物可普查（没跑不等于通过）；3 = 引擎加载失败（拒绝假装有读数）。
"""
from __future__ import annotations

import argparse
import copy
import glob
import importlib.util
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENG_DIR = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
OUTPUTS = ROOT / "outputs"
E2E = ROOT / "outputs" / "_e2e_local"

LAYERS = ("0", "1", "both", "all")
LAYER_CN = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}
#: 目标读数「落盘 -> 离线复算」一致性护栏的起始版本（V2.2.12 引入 goal_now 出口）。
V_GOALNOW = (2, 2, 12)
TARGET_STATES = ("achieved", "blocked", "not_achieved",
                 "not_judgeable", "unmeasured", "no_reading", "not_run")
TARGET_CN = {
    "achieved": "达成", "blocked": "受阻", "not_achieved": "未达成",
    "not_judgeable": "判据样本不足", "unmeasured": "未测出",
    "no_reading": "读数键缺失", "not_run": "没跑",
}
#: 「应为 0」的硬异常（真缺陷信号）；其余 id 归入历史口径/观察。
HARD_ANOMALIES = {
    "verdict_empty_new", "goal_now_missing_new", "recompute_mismatch",
    "unmeasured_reason_empty", "verdict_label_key_mismatch",
    "goal_trace_bad", "verdict_inconsistent", "route_layer_missing_view",
    "pack_parse_error",
    # 零 LLM 产物判据（12:55 那类跑次不许被读成「模型能力不足」或「挖尽」）
    "zero_llm_achieved", "zero_llm_verdict_empty",
    "zero_llm_unmeasured_reason_missing",
}
# ============================ 引擎（唯一口径来源） ============================
def latest_engine_path() -> Path:
    cands = []
    for p in ENG_DIR.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            cands.append((tuple(int(x) for x in m.groups()), p))
    if not cands:
        raise SystemExit("找不到引擎文件（无法复算口径）")
    return sorted(cands)[-1][1]


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("_lg_audit_engine", path)
    if spec is None or spec.loader is None:
        raise SystemExit("引擎 spec 加载失败：%s" % path)
    mod = importlib.util.module_from_spec(spec)
    # dataclass/typing 内省要求模块先注册进 sys.modules（同 tests_layer_goal.py）。
    sys.modules["_lg_audit_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


# ================================ 小工具 ================================
def vtuple(s: str):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(s or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _fmtval(x) -> str:
    v = _num(x)
    return "—" if v is None else "%.3f" % v


def _deep_same(a, b, tol: float = 1e-9) -> bool:
    """读数一致性：float 容差；None/缺失严格区分（未测不等于 0）。"""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(_deep_same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_deep_same(x, y, tol)
                                        for x, y in zip(a, b))
    fa, fb = _num(a), _num(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= tol
    return a == b


def _is_synthetic(name: str) -> bool:
    """文件名不是 YYYYMMDD_HHMMSS_* 即非真跑（如 *_replay.packed.json）。"""
    return re.match(r"^\d{8}_\d{6}_", Path(name).name) is None


def _route_list(route) -> list:
    """route 在产物里两种形态都出现过：list（新版）与 "0,1,both,all"（旧版）。"""
    if isinstance(route, (list, tuple)):
        return [str(x).strip() for x in route if str(x).strip()]
    return [x.strip() for x in str(route or "").split(",") if x.strip()]


def _brief_vals(counter: Counter, top: int = 8) -> dict:
    return dict(counter.most_common(top))


# ======================= 单层解析（每层都回答四问） =======================
_HEAD_RE = re.compile(r"^本层目标（(?P<label>[^）]*)）：(?P<rest>.*)$")


def parse_verdict(text: str) -> dict:
    """解析 goal_verdict 文本（V2.2.12 起格式固定，但**数值后可带方向提示**）。

    形态：本层目标（<label>）：<key>=<数值><方向提示> 或
         本层目标（<label>）：<key>=未测出（<可指认原因>）
    ★ 方向提示（_LG_HINT，如「（边际新增率·趋零即挖尽）」）挂在数值后面
      —— 旧正则要求数值收尾，会把带提示的 verdict 误判 malformed。
    返回 {state, key, label, value, why, raw}；state ∈ absent / unmeasured /
    valued / malformed。
    """
    raw = str(text or "").strip()
    if not raw:
        return {"state": "absent", "raw": ""}
    hm = _HEAD_RE.match(raw)
    if not hm:
        return {"state": "malformed", "raw": raw}
    label = hm.group("label")
    rest = hm.group("rest")
    if "=" not in rest:
        return {"state": "malformed", "raw": raw}
    key, _, val = rest.partition("=")
    key = key.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return {"state": "malformed", "raw": raw}
    if val.startswith("未测出（") and val.endswith("）"):
        return {"state": "unmeasured", "key": key, "label": label,
                "value": None, "why": val[len("未测出（"):-1].strip(),
                "raw": raw}
    m = re.match(r"^(-?\d+(?:\.\d+)?)(?:（.*）)?$", val)
    if m:
        return {"state": "valued", "key": key, "label": label,
                "value": float(m.group(1)), "why": "", "raw": raw}
    return {"state": "malformed", "raw": raw}


def classify_target(L: str, goal, trace, eng, ran: bool) -> tuple:
    """用引擎的 layer_goal_stop_signal 判「够不够达到目标」；不可判给原因。"""
    if not ran:
        return "not_run", "该层本轮没跑（rounds_run=0/缺）"
    if not goal:
        return "no_reading", "无 goal_now 且离线复算不出读数明细"
    main = _num(goal.get(eng._LG_KEYS[L]))
    if main is None:
        return "unmeasured", "主读数 %s 为 None" % eng._LG_KEYS[L]
    try:
        hit, why = eng.layer_goal_stop_signal(L, goal, list(trace or []))
    except Exception as e:  # noqa: BLE001
        return "no_reading", "停因判据异常：%s: %s" % (type(e).__name__, e)
    if hit:
        if L == "both" and "受阻" in str(why):
            return "blocked", str(why)
        return "achieved", str(why)
    # 未命中：区分「真没达标」与「判据结构不可达（样本不足）」——两回事。
    if L == "0":
        n_aspects = _num(goal.get("n_aspects")) or 0
        if n_aspects <= 0:
            return "not_judgeable", ("excavate=%s 但 n_aspects=0："
                                     "「挖尽」需先有层面存量" % _fmtval(main))
        return "not_achieved", ("excavate=%.3f >= %.2f（边际新增未趋零）"
                                % (main, eng._LG_STOP_MARGIN))
    if L == "1":
        if len(list(trace or [])) < int(eng._LG_STOP_FLAT_N) + 1:
            return "not_judgeable", (
                "settle=%.3f 有值，但「连续 %d 圈不涨」需 %d 个逐圈点，实有 %d 个"
                % (main, eng._LG_STOP_FLAT_N, eng._LG_STOP_FLAT_N + 1,
                   len(list(trace or []))))
        return "not_achieved", ("settle=%.3f 仍在涨（未连续 %d 圈不涨）"
                                % (main, eng._LG_STOP_FLAT_N))
    if L == "both":
        st = _num(goal.get("sem_stagnation"))
        if st is not None and st >= eng._LG_STOP_STAG:
            return "blocked", ("sem_stagnation=%.2f >= %.2f（复读上游，"
                               "没融合出新层面）" % (st, eng._LG_STOP_STAG))
        if len(list(trace or [])) < int(eng._LG_STOP_FLAT_N) + 1:
            return "not_judgeable", (
                "fuse=%.3f 有值，但「连续 %d 圈不涨」需 %d 个逐圈点，实有 %d 个"
                % (main, eng._LG_STOP_FLAT_N, eng._LG_STOP_FLAT_N + 1,
                   len(list(trace or []))))
        return "not_achieved", ("fuse=%.3f 仍在涨（未连续 %d 圈不涨）"
                                % (main, eng._LG_STOP_FLAT_N))
    return "not_achieved", ("crystallize=%.3f < 1.0（四件事留痕 %s/4）"
                            % (main, goal.get("n_hits")))


# ============ 独立复算（同公式、独立代码；不调用引擎内部函数） ============
#: ★ 为什么不用引擎的 layer_goal_readings 来复算：
#:   「自己校验自己」没有牙 —— 引擎公式改了，落盘值和新公式一起漂，比对永远一致。
#:   这里按引擎 docstring 的**口径**独立实现一遍，与落盘 goal_now 对不上就报
#:   recompute_mismatch（护栏见 --selfcheck M1）。
def _ind_num(x):
    """同 _at_num：非有限数 / 不可转 => None（不把「没有」当 0）。"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _ind_ratio(num, den):
    """安全比率：分母 <=0 或任一侧非数 => None（不是 0）。"""
    n, d = _ind_num(num), _ind_num(den)
    if n is None or d is None or d <= 0:
        return None
    return max(0.0, min(1.0, n / d))


def _ind_aspect_margin(hist):
    """Heaps 边际新增率：>=3 点 halves 口径；恰 2 点 2pt 口径 (V2-V1)/V1。"""
    xs = [_ind_num(x) for x in (hist or [])]
    xs = [x for x in xs if x is not None]
    if len(xs) >= 3:
        gains = [max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs))]
        if not gains:
            return None
        half = max(1, len(gains) // 2)
        late = sum(gains[-half:]) / float(half)
        early = sum(gains[:half]) / float(half)
        if early <= 1e-12:
            return 0.0 if late <= 1e-12 else None
        return max(0.0, min(1.0, late / early))
    if len(xs) == 2 and xs[0] > 1e-12:
        return max(0.0, min(1.0, (xs[1] - xs[0]) / xs[0]))
    return None


def _ind_stag_ratio(items, ups):
    """产出层面与上游文本的字符集 Jaccard 重合率（>=0.8 记复读）；算不出 None。"""
    its = [str((x or {}).get("target") or (x or {}).get("desc")
               or (x or {}).get("text") or "").strip()
           for x in (items or [])]
    its = [x for x in its if x]
    ups = [str(x).strip() for x in (ups or []) if str(x).strip()]
    if not its or not ups:
        return None

    def _toks(s):
        return {c for c in s if not c.isspace()}

    hit = 0
    for s in its:
        ts = _toks(s)
        if not ts:
            continue
        best = 0.0
        for u in ups:
            tu = _toks(u)
            if not tu:
                continue
            best = max(best, len(ts & tu) / float(len(ts | tu)))
        if best >= 0.8:
            hit += 1
    return hit / float(len(its))


def _ind_diverge_state(v) -> str:
    return str(((v or {}).get("divergence") or {}).get("state") or "").strip()


def recompute_layer_goal(view, L: str) -> dict:
    """四层目标主读数的独立复算（V2.2.12+ 口径，供 goal_now 对账用）。

    公式依据 = 引擎 layer_goal_readings 的 docstring 与同源注释（照口径实现，
    不复用引擎代码）。缺产物 => 该层返回 {}（与引擎「没东西就不进结果」一致）。
    """
    if not isinstance(view, dict) or not view:
        return {}
    d = {}
    if L == "0":
        units = len(view.get("aspect_units") or [])
        rr = int(_ind_num(view.get("rounds_run")) or 0)
        hist = [_ind_num(x) for x in (view.get("aspect_hist") or [])]
        hist = [x for x in hist if x is not None]
        m = _ind_aspect_margin(hist)
        d["excavate"] = m
        d["excavate_closed"] = None if m is None else round(1.0 - m, 4)
        d["excavate_basis"] = ("halves" if len(hist) >= 3
                               else ("2pt" if len(hist) == 2 else None))
        d["n_hist"] = len(hist)
        d["n_aspects"] = units
        d["rounds_run"] = rr
        st = _ind_diverge_state(view)
        d["conv_state"] = st
        d["converging"] = st in ("收敛", "停滞")
    elif L == "1":
        co = view.get("settlement") or view.get("covered_answer") or {}
        ans, tot = co.get("answered"), co.get("total")
        if ans is None:
            ca = view.get("covered_aspects") or []
            ua = view.get("uncovered_aspects") or []
            if ca or ua:
                ans, tot = len(ca), len(ca) + len(ua)
        d["settle"] = _ind_ratio(ans, tot)
        nz = _ind_num(ans) or 0.0
        d["non_degenerate"] = (nz > 0) if tot else None
        bs = view.get("belief_status_counts") or {}
        tot_b = sum(int(x or 0) for x in bs.values()) if bs else 0
        res_b = (int(bs.get("resolved", 0) or 0)
                 + int(bs.get("settled", 0) or 0))
        d["belief_resolved_rate"] = _ind_ratio(res_b, tot_b)
        st = _ind_diverge_state(view)
        d["conv_state"] = st
        d["converging"] = st == "收敛"
        d["pseudo_convergence"] = bool(st in ("收敛", "停滞") and tot and not nz)
    elif L == "both":
        _duel = view.get("duel_suspensions") or []
        _bel = view.get("belief_items") or []
        _new = len(_duel) + len(_bel)
        _up = int(_ind_num(view.get("upstream_layers")) or 0)
        if _up <= 0:
            _bm = view.get("both_quota") or {}
            _up = int(_ind_num(_bm.get("upstream")) or 0)
        _stag = _ind_num(view.get("sem_stagnation"))
        if _stag is None:
            _stag = _ind_stag_ratio(_duel + _bel,
                                    view.get("upstream_texts") or [])
        _raw = _ind_ratio(_new, _up) if _up > 0 else None
        if _raw is None:
            _fuse = None
        elif _stag is None:
            _fuse = _raw
        else:
            _fuse = round(_raw * (1.0 - min(1.0, _stag)), 4)
        d["fuse_raw"] = _raw
        d["fuse"] = _fuse
        d["sem_stagnation"] = None if _stag is None else round(_stag, 4)
        d["n_new"] = _new
        d["n_upstream"] = _up
    elif L == "all":
        _clo = view.get("meta_closure") or {}
        _hits = 0
        if _clo:
            _hits += 1
            if _clo.get("total") is not None:
                _hits += 1
        if view.get("engagements") or []:
            _hits += 1
        if view.get("suspensions") or []:
            _hits += 1
        d["crystallize"] = round(_hits / 4.0, 4)
        d["n_hits"] = _hits
        d["meta_clean"] = bool(_clo.get("clean")) if _clo else None
        d["crystallize_detail"] = {
            "closure": bool(_clo),
            "lookback_items": (None if not _clo
                               else _ind_num(_clo.get("total"))),
            "engagements": len(view.get("engagements") or []),
            "suspensions": len(view.get("suspensions") or []),
        }
    return d

def layer_row(view, L: str, eng) -> dict:
    """单层一行：跑了没跑 / 读数有没有 / 是多少 / 够不够目标。"""
    main_key = eng._LG_KEYS[L]
    row = {"layer": L, "view_present": isinstance(view, dict),
           "ran": False, "rounds_run": None, "trace_len": 0, "trace_ok": None,
           "goal_now_present": False, "verdict_state": "absent",
           "verdict": "", "verdict_why": "", "verdict_value": None,
           "label_ok": None, "key_ok": None, "main_key": main_key,
           "stored_value": None, "stored_source": None,
           "fresh_value": None, "main_value": None, "reading_source": None,
           "judge_source": None, "reading_consistency": None,
           "legacy_verdict_stale": None,
           "target_status": "not_run", "target_why": "views 无该层",
           "historic_stop": None, "detail": {}, "trace_main": [],
           "trace_max": None, "note": ""}
    if not isinstance(view, dict):
        return row

    row["rounds_run"] = int(_num(view.get("rounds_run")) or 0)
    row["ran"] = row["rounds_run"] > 0
    trace = view.get("goal_trace") or []
    row["trace_len"] = len(trace) if isinstance(trace, list) else 0
    pv = parse_verdict(view.get("goal_verdict"))
    row["verdict_state"] = pv["state"]
    row["verdict"] = pv["raw"]
    row["verdict_why"] = pv.get("why", "")
    row["verdict_value"] = pv.get("value")
    if pv["state"] in ("valued", "unmeasured"):
        row["label_ok"] = (pv.get("label") == eng._LG_LABELS.get(L))
        row["key_ok"] = (pv.get("key") == main_key)
    gn = view.get("goal_now")
    stored = gn if isinstance(gn, dict) and gn else None
    row["goal_now_present"] = bool(stored)

    # 独立复算：本文件自己按口径实现（不调用引擎内部函数），旧包只能靠这条。
    fresh = None
    try:
        fresh = recompute_layer_goal(view, L)
    except Exception as e:  # noqa: BLE001
        row["note"] = "独立复算异常：%s: %s" % (type(e).__name__, e)

    # ── 读数：落盘（goal_now / 旧 verdict）与复算**分开**，不混口径 ──
    stored_value = None
    stored_source = None
    if stored is not None:
        stored_value = _num(stored.get(main_key))
        stored_source = "goal_now" if stored_value is not None else "goal_now(None)"
    if stored_value is None and pv["state"] == "valued":
        stored_value = pv["value"]
        stored_source = "verdict"
    fresh_value = None if fresh is None else _num(fresh.get(main_key))
    row["stored_value"] = stored_value
    row["stored_source"] = stored_source
    row["fresh_value"] = fresh_value
    if stored_value is not None:
        row["main_value"] = stored_value
        row["reading_source"] = ("goal_now" if stored_source == "goal_now"
                                 else "verdict")
    elif fresh_value is not None:
        row["main_value"] = fresh_value
        row["reading_source"] = "recomputed"
    # 目标判定用的 goal：有 goal_now 用 goal_now（新版落盘即最终视图），
    # 旧包用当前口径复算（并标注来源，避免与旧 verdict 混读）。
    if stored is not None:
        row["judge_source"] = "goal_now"
        judge_goal = stored
    elif fresh:
        row["judge_source"] = "recomputed"
        judge_goal = fresh
    else:
        judge_goal = None

    # 一致性：落盘 goal_now vs 离线复算（V2.2.12+ 的核心护栏）。
    if stored is not None and fresh is not None:
        row["reading_consistency"] = _deep_same(stored, fresh)
    elif stored is None and fresh:
        row["reading_consistency"] = None      # 旧包无 goal_now 出口，不适用
    else:
        row["reading_consistency"] = True      # 两边都没读数（一致的未测出）
    # 旧引擎时序缺陷观察：旧 verdict（收尾前渲染）与最终视图复算不同。
    if (stored is None and pv["state"] == "valued"
            and fresh_value is not None and pv["value"] is not None):
        row["legacy_verdict_stale"] = abs(pv["value"] - fresh_value) > 1e-6

    # 逐层依据字段（读数是哪些物理量算出来的）。
    d = stored if stored is not None else (fresh or {})
    if L == "0":
        hist = view.get("aspect_hist") or []
        row["detail"] = {
            "aspect_hist": hist,
            "n_hist": len(hist) if isinstance(hist, list) else 0,
            "n_units": len(view.get("aspect_units") or []),
            "excavate_basis": d.get("excavate_basis"),
            "n_aspects": d.get("n_aspects",
                               len(view.get("aspect_units") or [])),
            "conv_state": d.get("conv_state"),
        }
    elif L == "1":
        co = view.get("settlement") or view.get("covered_answer") or {}
        row["detail"] = {
            "settlement": {"answered": co.get("answered"),
                           "total": co.get("total")},
            "non_degenerate": d.get("non_degenerate"),
            "belief_resolved_rate": d.get("belief_resolved_rate"),
            "pseudo_convergence": d.get("pseudo_convergence"),
        }
    elif L == "both":
        row["detail"] = {"n_new": d.get("n_new"),
                         "n_upstream": d.get("n_upstream"),
                         "fuse_raw": d.get("fuse_raw"),
                         "sem_stagnation": d.get("sem_stagnation"),
                         # 直读 view 原字段，用于核对分母口径（层数 vs 层面数）。
                         "view_upstream_layers": view.get("upstream_layers")}
    else:
        row["detail"] = {"crystallize": d.get("crystallize"),
                         "n_hits": d.get("n_hits"),
                         "crystallize_detail": d.get("crystallize_detail")}

    # goal_trace 形态：是 list、每条 dict、round 单调严格递增。
    if row["trace_len"]:
        rounds_ok = all(isinstance(t, dict) and _num(t.get("round")) is not None
                        for t in trace)
        nums = [int(_num(t.get("round"))) for t in trace] if rounds_ok else []
        row["trace_ok"] = bool(rounds_ok and nums == sorted(nums)
                               and len(set(nums)) == len(nums))
    elif row["ran"]:
        row["trace_ok"] = False
    # 逐圈主读数形态（None 用 — 表示）：证明「同层连续 N 圈读数」真落了盘。
    row["trace_main"] = [_fmtval((t or {}).get(main_key))
                         for t in trace if isinstance(t, dict)]
    _tr_vals = [_num((t or {}).get(main_key)) for t in trace
                if isinstance(t, dict)]
    _tr_vals = [x for x in _tr_vals if x is not None]
    row["trace_max"] = max(_tr_vals) if _tr_vals else None

    row["target_status"], row["target_why"] = classify_target(
        L, judge_goal, trace, eng, ran=row["ran"])

    sr = str(view.get("stop_reason") or "")
    if "目标已达成" in sr:
        row["historic_stop"] = "achieved"
    elif "目标受阻" in sr:
        row["historic_stop"] = "blocked"
    return row


# ======================== 单包解析 + 异常/观察（纯读） ========================
def analyze_parsed(d: dict, path: Path, eng) -> dict:
    """从已解析的 packed dict 计算行与异常（analyze_pack 与自检共用同一实现）。"""
    pv = d.get("provenance") or {}
    ver = str(pv.get("engine_version") or "")
    vt = vtuple(ver)
    views = d.get("views") or {}
    rows = {L: layer_row(views.get(L), L, eng) for L in LAYERS}
    route = d.get("route") or ""
    route_layers = _route_list(route)
    meta = {
        "file": str(path), "name": path.name,
        "dir": "outputs/_e2e_local" if path.parent.name == "_e2e_local"
               else "outputs",
        "synthetic": _is_synthetic(path.name),
        "mtime": path.stat().st_mtime if path.exists() else 0.0,
        "engine_version": ver, "engine_tuple": vt,
        "engine_file": str(pv.get("engine_file") or ""),
        "app_version": str(pv.get("app_version") or ""),
        "has_provenance": bool(pv),
        "route": route, "route_layers": route_layers,
        "rounds": d.get("rounds"),
        "llm_calls": d.get("llm_calls"), "llm_tokens": d.get("llm_tokens"),
        "llm_cb_opened": d.get("llm_cb_opened"),
        "llm_cb_skipped": d.get("llm_cb_skipped"),
        "views_keys": sorted(views.keys()),
        "question": str(d.get("question") or "")[:40],
    }
    an: list[dict] = []

    # A. route 要求但 views 缺该层（接线/落盘缺口）。
    for L in route_layers:
        if L not in views:
            an.append({"id": "route_layer_missing_view", "layer": L,
                       "detail": "route=%s 要求该层，views 里没有"
                                 % str(route)[:40]})

    # B. 逐层判据（V2.2.12+ 才要求「跑了必有说法/明细」）。
    for L, r in rows.items():
        if not r["view_present"] or not r["ran"]:
            continue
        if vt is not None and vt >= V_GOALNOW:
            if r["verdict_state"] == "absent":
                an.append({"id": "verdict_empty_new", "layer": L,
                           "detail": "V2.2.12+ 跑过的层 verdict 空"})
            if not r["goal_now_present"]:
                an.append({"id": "goal_now_missing_new", "layer": L,
                           "detail": "V2.2.12+ 跑过的层 goal_now 未落盘"})
            if r["reading_consistency"] is False:
                an.append({"id": "recompute_mismatch", "layer": L,
                           "detail": "落盘 goal_now 与离线复算不一致"})
            if r["verdict_state"] == "unmeasured" and not r["verdict_why"]:
                an.append({"id": "unmeasured_reason_empty", "layer": L,
                           "detail": "未测出原因为空（不可指认）"})
            if r["label_ok"] is False or r["key_ok"] is False:
                an.append({"id": "verdict_label_key_mismatch", "layer": L,
                           "detail": "verdict 标签/键与 _LG_LABELS/_LG_KEYS "
                                     "不一致：%s" % r["verdict"][:60]})
            if not r["trace_ok"]:
                an.append({"id": "goal_trace_bad", "layer": L,
                           "detail": "goal_trace 缺失或圈号非严格递增"})
            if (r["verdict_state"] == "valued"
                    and r["verdict_value"] is not None
                    and r["main_value"] is not None
                    and abs(r["verdict_value"] - r["main_value"]) > 5e-4):
                an.append({"id": "verdict_inconsistent", "layer": L,
                           "detail": "verdict 数值(%s) 与 goal_now(%s) 不一致"
                                     % (_fmtval(r["verdict_value"]),
                                        _fmtval(r["main_value"]))})
        else:
            # 旧引擎：verdict 空白是历史事实（V2.2.12 前没有「跑了必有说法」），
            # 但「旧 verdict 与最终视图复算不同」是旧引擎时序缺陷的直接证据。
            if r["verdict_state"] == "absent":
                an.append({"id": "verdict_empty_legacy", "layer": L,
                           "detail": "旧引擎 verdict 空（历史事实）"})
            if r["legacy_verdict_stale"]:
                an.append({"id": "legacy_verdict_stale", "layer": L,
                           "detail": "旧 verdict=%s 与最终视图复算=%s 不同"
                                     "（收尾产物落定前渲染）"
                                     % (_fmtval(r["verdict_value"]),
                                        _fmtval(r["fresh_value"]))})
        if r["reading_source"] and not r["trace_len"]:
            an.append({"id": "ran_without_goal_trace", "layer": L,
                       "detail": "跑了且有读数，但 goal_trace 为空"})
        if L == "all":
            det = r["detail"].get("crystallize_detail") or {}
            n_hits = _num(r["detail"].get("n_hits")) or 0
            if det and n_hits >= 2 and not (_num(det.get("lookback_items")) or 0) \
                    and not (_num(det.get("engagements")) or 0) \
                    and not (_num(det.get("suspensions")) or 0):
                an.append({"id": "crystallize_zero_amount_hits", "layer": L,
                           "detail": "n_hits=%s 全靠「字段存在」计数，量都是 0：%s"
                                     % (int(n_hits), dict(det))})

    # C. 零 LLM 跑次：四层自动调度白跑（链路/服务问题，不是模型能力问题）。
    calls = _num(meta["llm_calls"])
    if calls is not None and calls == 0 and any(r["ran"] for r in rows.values()):
        an.append({"id": "zero_llm_run", "layer": "",
                   "detail": "llm_calls=0 但层跑了（llm_cb_opened=%s, "
                             "llm_cb_skipped=%s）"
                             % (meta["llm_cb_opened"], meta["llm_cb_skipped"])})
    # C2. 零 LLM 产物判据：这类跑次（如 12:55 shim 死掉）不许被读成
    #     「模型能力不足」或「挖尽」—— verdict 必须有说法、未测出必须有原因、
    #     **不许判「达成」**（没调用就没证据）。
    if calls is not None and calls == 0:
        for L, r in rows.items():
            if not (r["view_present"] and r["ran"]):
                continue
            if r["verdict_state"] == "absent":
                an.append({"id": "zero_llm_verdict_empty", "layer": L,
                           "detail": "零 LLM 跑次里跑过的层 verdict 空"})
            elif r["verdict_state"] == "unmeasured" and not r["verdict_why"]:
                an.append({"id": "zero_llm_unmeasured_reason_missing",
                           "layer": L,
                           "detail": "零 LLM 未测出但原因空（不可指认）"})
            if r["target_status"] == "achieved":
                an.append({"id": "zero_llm_achieved", "layer": L,
                           "detail": "零 LLM 跑次却判「达成」：%s"
                                     % str(r["target_why"])[:120]})
    return {"meta": meta, "layers": rows, "anomalies": an}


def analyze_pack(path: Path, eng) -> dict:
    """解析一个 packed 文件；解析失败也留痕（不静默跳过）。"""
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        empty = {"layer": "", "view_present": False, "ran": False,
                 "rounds_run": None, "trace_len": 0, "trace_ok": None,
                 "goal_now_present": False, "verdict_state": "absent",
                 "verdict": "", "verdict_why": "", "verdict_value": None,
                 "label_ok": None, "key_ok": None, "main_key": "",
                 "stored_value": None, "stored_source": None,
                 "fresh_value": None, "main_value": None,
                 "reading_source": None, "judge_source": None,
                 "reading_consistency": None, "legacy_verdict_stale": None,
                 "target_status": "not_run", "target_why": "解析失败",
                 "historic_stop": None, "detail": {}, "trace_main": [],
                 "trace_max": None, "note": ""}
        return {"meta": {"file": str(path), "name": path.name,
                         "dir": str(path.parent), "synthetic": False,
                         "mtime": 0.0, "engine_version": "", "engine_tuple": None,
                         "engine_file": "", "app_version": "",
                         "has_provenance": False, "route": "", "route_layers": [],
                         "rounds": None, "llm_calls": None, "llm_tokens": None,
                         "llm_cb_opened": None, "llm_cb_skipped": None,
                         "views_keys": [], "question": ""},
                "layers": {L: dict(empty, layer=L) for L in LAYERS},
                "parse_error": "%s: %s" % (type(e).__name__, e),
                "anomalies": [{"id": "pack_parse_error", "layer": "",
                               "detail": str(e)[:160]}]}
    return analyze_parsed(d, path, eng)


# ============================== 汇总统计 ==============================
def _trace_vs_final(ran: list) -> dict:
    """逐圈主读数最大值 vs 收尾主读数：一致 / 不同 / 只在一边有值。"""
    eq = diff = t_only = f_only = 0
    for r in ran:
        a, b = r["trace_max"], r["main_value"]
        if a is None and b is None:
            continue
        if a is None:
            f_only += 1
        elif b is None:
            t_only += 1
        elif abs(a - b) <= 1e-6:
            eq += 1
        else:
            diff += 1
    return {"equal": eq, "different": diff,
            "trace_only": t_only, "final_only": f_only}


def _layer_stats(rows: list) -> dict:
    out = {}
    for L in LAYERS:
        rs = [r["layers"][L] for r in rows]
        ran = [r for r in rs if r["ran"]]
        st = Counter(r["target_status"] for r in rs)
        stored_vals = Counter("%.3f" % r["stored_value"] for r in ran
                              if r["stored_value"] is not None)
        fresh_vals = Counter("%.3f" % r["fresh_value"] for r in ran
                             if r["fresh_value"] is not None)
        out[L] = {
            "main_key": rs[0]["main_key"] if rs else "",
            "view_present": sum(1 for r in rs if r["view_present"]),
            "ran": len(ran),
            "reading": sum(1 for r in ran if r["main_value"] is not None),
            "stored_reading": sum(1 for r in ran
                                  if r["stored_value"] is not None),
            "fresh_reading": sum(1 for r in ran
                                 if r["fresh_value"] is not None),
            "only_recomputed": sum(1 for r in ran
                                   if r["stored_value"] is None
                                   and r["fresh_value"] is not None),
            "target": {k: st.get(k, 0) for k in TARGET_STATES},
            "historic_achieved": sum(1 for r in rs
                                     if r["historic_stop"] == "achieved"),
            "historic_blocked": sum(1 for r in rs
                                    if r["historic_stop"] == "blocked"),
            "values_stored": _brief_vals(stored_vals),
            "values_fresh": _brief_vals(fresh_vals),
            "verdict": dict(Counter(r["verdict_state"] for r in rs)),
            "goal_now": sum(1 for r in rs if r["goal_now_present"]),
            "judge_sources": dict(Counter(r["judge_source"] for r in ran)),
            "trace_lens": dict(Counter(r["trace_len"] for r in ran)),
            "stale_legacy_verdicts": sum(1 for r in ran
                                         if r["legacy_verdict_stale"]),
            "unmeasured_reasons": _brief_vals(Counter(
                (r["verdict_why"][:24] if r["verdict_why"]
                 else "（verdict 空：旧版本无未测出原因出口）")
                for r in ran if r["target_status"] == "unmeasured"), 4),
            "trace_signatures": _brief_vals(Counter(
                "|".join(r["trace_main"]) if r["trace_main"]
                else "（无 goal_trace）" for r in ran), 4),
            "trace_max_values": _brief_vals(Counter(
                _fmtval(r["trace_max"]) for r in ran), 4),
            # 逐圈判据读到的读数 vs 收尾落盘读数：两把尺子是否一致。
            "trace_vs_final": _trace_vs_final(ran),
        }
        if L == "0":
            out[L]["basis"] = dict(Counter(
                str((r["detail"] or {}).get("excavate_basis")) for r in ran))
            out[L]["hist_lens"] = dict(Counter(
                (r["detail"] or {}).get("n_hist") for r in ran))
        elif L == "1":
            out[L]["settlement"] = dict(Counter(
                "%s/%s" % ((r["detail"].get("settlement") or {}).get("answered"),
                           (r["detail"].get("settlement") or {}).get("total"))
                for r in ran))
        elif L == "both":
            out[L]["upstream_layers_values"] = dict(Counter(
                str((r["detail"] or {}).get("view_upstream_layers"))
                for r in ran))
            out[L]["stag_top"] = _brief_vals(Counter(
                _fmtval((r["detail"] or {}).get("sem_stagnation"))
                for r in ran
                if (r["detail"] or {}).get("sem_stagnation") is not None), 5)
        else:
            out[L]["n_hits"] = dict(Counter(
                str((r["detail"] or {}).get("n_hits")) for r in ran))
    return out


def aggregate(rows: list) -> OrderedDict:
    real = [r for r in rows if not r["meta"]["synthetic"]]
    synth = [r for r in rows if r["meta"]["synthetic"]]
    out = OrderedDict()
    out["totals"] = {
        "packs": len(rows),
        "real_runs": len(real),
        "synthetic": len(synth),
        "synthetic_files": [r["meta"]["name"] for r in synth],
        "by_dir": dict(Counter(r["meta"]["dir"] for r in rows)),
        "parse_errors": sum(1 for r in rows if "parse_error" in r),
        "by_engine_version": dict(Counter(
            r["meta"]["engine_version"] or "(无 provenance)" for r in rows)),
        "route_layer_sets": dict(Counter(
            "+".join(r["meta"]["route_layers"]) for r in real)),
        "views_key_sets": dict(Counter(
            "+".join(r["meta"]["views_keys"]) for r in real)),
        "with_provenance": sum(1 for r in real if r["meta"]["has_provenance"]),
    }
    out["by_layer"] = _layer_stats(real)

    # 按引擎版本分层（任务要求：只陈述读数 + 可复算）。
    groups: dict = {}
    for r in real:
        groups.setdefault(r["meta"]["engine_version"] or "(无 provenance)",
                          []).append(r)
    order = sorted(groups, key=lambda k: (vtuple(k) or (0, 0, 0)), reverse=True)
    out["by_version"] = OrderedDict()
    for k in order:
        g = groups[k]
        out["by_version"][k] = {
            "n": len(g),
            "views": dict(Counter("+".join(r["meta"]["views_keys"]) for r in g)),
            "llm_calls_zero": sum(1 for r in g
                                  if _num(r["meta"]["llm_calls"]) == 0),
            "layers": _layer_stats(g),
        }

    # 停因命中历史（运行中判据触发过的直接证据）。
    hist = []
    for r in real:
        for L in LAYERS:
            lr = r["layers"][L]
            if lr["historic_stop"]:
                hist.append({"file": r["meta"]["name"], "layer": L,
                             "hit": lr["historic_stop"],
                             "why": str(lr["target_why"] or "")[:90]})
    out["historic_stop_hits"] = hist

    # 异常汇总。
    an_counter = Counter()
    an_detail: dict = {}
    for r in rows:
        for a in r["anomalies"]:
            an_counter[a["id"]] += 1
            if len(an_detail.setdefault(a["id"], [])) < 12:
                an_detail[a["id"]].append(
                    {"file": r["meta"]["name"], "layer": a["layer"],
                     "detail": a["detail"]})
    out["anomalies"] = {"counts": dict(an_counter.most_common()),
                        "hard_ids": sorted(HARD_ANOMALIES),
                        "samples": an_detail}

    # 零 LLM 跑次明细。
    zero = []
    for r in real:
        if _num(r["meta"]["llm_calls"]) == 0 and any(
                r["layers"][L]["ran"] for L in LAYERS):
            zero.append({"file": r["meta"]["name"],
                         "engine": r["meta"]["engine_version"],
                         "route": str(r["meta"]["route"])[:30],
                         "layers_ran": [L for L in LAYERS
                                        if r["layers"][L]["ran"]],
                         "cb": {"opened": r["meta"]["llm_cb_opened"],
                                "skipped": r["meta"]["llm_cb_skipped"]}})
    out["zero_llm_runs"] = zero

    # 逐包行（可复算；--json 时给消费者）。
    brief = []
    for r in rows:
        m = r["meta"]
        brief.append({
            "file": m["name"], "dir": m["dir"], "synthetic": m["synthetic"],
            "engine": m["engine_version"], "route": _route_list(m["route"]),
            "llm_calls": m["llm_calls"],
            "layers": {L: {"view": r["layers"][L]["view_present"],
                           "ran": r["layers"][L]["ran"],
                           "stored_value": r["layers"][L]["stored_value"],
                           "stored_source": r["layers"][L]["stored_source"],
                           "fresh_value": r["layers"][L]["fresh_value"],
                           "reading_source": r["layers"][L]["reading_source"],
                           "judge_source": r["layers"][L]["judge_source"],
                           "verdict_state": r["layers"][L]["verdict_state"],
                           "target_status": r["layers"][L]["target_status"],
                           "historic_stop": r["layers"][L]["historic_stop"]}
                       for L in LAYERS},
            "anomalies": [a["id"] for a in r["anomalies"]],
        })
    out["rows"] = brief
    return out


# ========================= 抽样核对（人工可核） =========================
def pick_samples(rows: list, n: int = 5) -> list:
    """确定性抽样：覆盖「四层全跑零 LLM / 四层全跑真调用 / V2.2.12+ 有数值 /
    短 route e2e / 无 provenance 历史」五类，供人工按产物字段核对。"""
    real = sorted([r for r in rows if not r["meta"]["synthetic"]],
                  key=lambda r: (r["meta"]["mtime"], r["meta"]["name"]),
                  reverse=True)
    picks = []
    used = set()

    def take(pred, why):
        for r in real:
            if r["meta"]["file"] in used:
                continue
            try:
                if pred(r):
                    used.add(r["meta"]["file"])
                    picks.append((r, why))
                    return
            except Exception:  # noqa: BLE001
                continue

    def ran_all(r):
        return all(r["layers"][L]["ran"] for L in LAYERS)

    def has_num(r, L):
        return r["layers"][L]["main_value"] is not None

    take(lambda r: ran_all(r) and _num(r["meta"]["llm_calls"]) == 0,
         "最新四层全跑（零 LLM：链路故障，不是模型能力）")
    take(lambda r: ran_all(r) and _num(r["meta"]["llm_calls"]) not in (None, 0)
         and has_num(r, "0") and has_num(r, "1"),
         "最新四层全跑且 LLM 真调用（云档历史样本）")
    take(lambda r: (r["meta"]["engine_tuple"] or (0, 0, 0)) >= V_GOALNOW
         and any(r["layers"][L]["ran"] and has_num(r, L) for L in LAYERS),
         "V2.2.12+ 跑出数值读数")
    take(lambda r: r["meta"]["dir"] == "outputs/_e2e_local"
         and len([L for L in LAYERS if r["layers"][L]["ran"]]) == 1,
         "最新 e2e 单层短 route（本地档）")
    take(lambda r: not r["meta"]["has_provenance"],
         "最新无 provenance 历史包（旧口径）")
    for r in real:
        if len(picks) >= n:
            break
        if r["meta"]["file"] not in used:
            picks.append((r, "兜底（最新）"))
            used.add(r["meta"]["file"])
    return picks[:n]


# ========================== 有牙自检（变异体） ==========================
def selfcheck(rows: list, eng) -> int:
    """在内存里造 4 个变异体，证明异常护栏真的会报错（没抓到 => 退出码 1）。"""
    ok, total, missed = 0, 0, []

    def load_raw(row):
        try:
            return json.loads(Path(row["meta"]["file"]).read_text(
                encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            return None

    def run_mut(tag, want, choose, mutate):
        nonlocal ok, total
        total += 1
        cand = None
        for r in rows:
            if "parse_error" in r:
                continue
            try:
                if choose(r):
                    cand = r
                    break
            except Exception:  # noqa: BLE001
                continue
        if cand is None:
            print("· SKIP %s：真实产物里找不到可构造变异体的样本"
                  "（没测出，不冒充通过）" % tag)
            return
        raw = load_raw(cand)
        if raw is None:
            print("· SKIP %s：读不到原产物" % tag)
            return
        try:
            base = analyze_pack(Path(cand["meta"]["file"]), eng)
        except Exception:  # noqa: BLE001
            base = {"anomalies": []}
        clean = not any(a["id"] == want for a in base["anomalies"])
        try:
            mutate(raw)
        except Exception as e:  # noqa: BLE001
            print("✗ %s 变异体构造失败：%s: %s" % (tag, type(e).__name__, e))
            missed.append(tag)
            return
        got = analyze_parsed(raw, Path(cand["meta"]["file"]), eng)
        caught = any(a["id"] == want for a in got["anomalies"])
        if caught and clean:
            print("✓ %s：变异体被抓到（%s），原包无该异常（护栏有牙）"
                  % (tag, want))
            ok += 1
        else:
            print("✗ %s：没抓到（caught=%s clean=%s）—— 护栏没牙"
                  % (tag, caught, clean))
            missed.append(tag)

    def pick_new(d):
        if (d["meta"]["engine_tuple"] or (0, 0, 0)) < V_GOALNOW:
            return False
        return any(d["layers"][L]["ran"] and d["layers"][L]["goal_now_present"]
                   and d["layers"][L]["main_value"] is not None for L in LAYERS)

    def mut_reading(raw):
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            gn = v.get("goal_now") or {}
            for k, val in list(gn.items()):
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    gn[k] = float(val) + 0.5
                    return
        raise ValueError("没有数值型 goal_now 字段")

    def pick_new_verdict(d):
        if (d["meta"]["engine_tuple"] or (0, 0, 0)) < V_GOALNOW:
            return False
        return any(d["layers"][L]["ran"]
                   and d["layers"][L]["verdict_state"] != "absent"
                   for L in LAYERS)

    def mut_verdict(raw):
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            if v.get("goal_verdict"):
                v["goal_verdict"] = ""
                return
        raise ValueError("没有非空 goal_verdict")

    def pick_new_goalnow(d):
        if (d["meta"]["engine_tuple"] or (0, 0, 0)) < V_GOALNOW:
            return False
        return any(d["layers"][L]["ran"] and d["layers"][L]["goal_now_present"]
                   for L in LAYERS)

    def mut_goalnow(raw):
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            if v.get("goal_now"):
                v.pop("goal_now", None)
                return
        raise ValueError("没有 goal_now")

    def pick_unmeasured(d):
        return any(d["layers"][L]["verdict_state"] == "unmeasured"
                   for L in LAYERS)

    def mut_why(raw):
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            gv = str(v.get("goal_verdict") or "")
            if "=未测出（" in gv:
                v["goal_verdict"] = gv.split("=未测出（", 1)[0] + "=未测出（）"
                return
        raise ValueError("没有「未测出」verdict")

    def pick_zero(d):
        return (_num(d["meta"]["llm_calls"]) == 0
                and any(d["layers"][L]["ran"] and d["layers"][L]["goal_now_present"]
                        for L in LAYERS))

    def mut_zero_achieved(raw):
        """零 LLM 产物被伪造成「修行层挖尽」=> zero_llm_achieved 必报。"""
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            gn = v.get("goal_now")
            if not isinstance(gn, dict) or not v.get("rounds_run"):
                continue
            if L != "0":
                continue
            gn["excavate"] = 0.0
            gn["excavate_closed"] = 1.0
            gn["excavate_basis"] = "2pt"
            gn["n_aspects"] = 3
            gn["n_hist"] = 2
            v["goal_verdict"] = ("本层目标（修行·挖尽）：excavate=0.000"
                                 "（边际新增率·趋零即挖尽）")
            return
        raise ValueError("零 LLM 产物里没有 layer0 的 goal_now 可伪造")

    def mut_zero_why(raw):
        """零 LLM 产物的未测出原因被清空 => 专用硬异常必报。"""
        for L in LAYERS:
            v = (raw.get("views") or {}).get(L) or {}
            gv = str(v.get("goal_verdict") or "")
            if "=未测出（" in gv and v.get("rounds_run"):
                v["goal_verdict"] = gv.split("=未测出（", 1)[0] + "=未测出（）"
                return
        raise ValueError("零 LLM 产物里没有「未测出」verdict")

    run_mut("M1 落盘读数被改(+0.5)", "recompute_mismatch", pick_new, mut_reading)
    run_mut("M2 V2.2.12+ verdict 被清空", "verdict_empty_new",
            pick_new_verdict, mut_verdict)
    run_mut("M3 V2.2.12+ goal_now 被删", "goal_now_missing_new",
            pick_new_goalnow, mut_goalnow)
    run_mut("M4 未测出原因被清空", "unmeasured_reason_empty",
            pick_unmeasured, mut_why)
    run_mut("M5 零 LLM 产物被伪造成「挖尽」", "zero_llm_achieved",
            pick_zero, mut_zero_achieved)
    run_mut("M6 零 LLM 未测出原因被清空",
            "zero_llm_unmeasured_reason_missing", pick_zero, mut_zero_why)
    print("-" * 60)
    if ok == total:
        print("自检 %d/%d 通过：六道护栏都能抓到对应变异体" % (ok, total))
        return 0
    print("自检 %d/%d 通过；没抓到：%s" % (ok, total, missed))
    return 1


# ================================ 打印 ================================
def print_report(rows: list, agg: OrderedDict, eng_name: str) -> None:
    t = agg["totals"]
    print("=" * 78)
    print("四层目标读数离线普查 · scripts/lead_layer_goal_audit.py")
    print("复算口径引擎：%s" % eng_name)
    print("产物：%d 个 packed（outputs/ %d + outputs/_e2e_local/ %d）| 真跑 %d | "
          "合成 %d | 解析失败 %d"
          % (t["packs"], t["by_dir"].get("outputs", 0),
             t["by_dir"].get("outputs/_e2e_local", 0), t["real_runs"],
             t["synthetic"], t["parse_errors"]))
    print("引擎版本分布：%s"
          % ", ".join("%s=%d" % (k, v)
                      for k, v in t["by_engine_version"].items()))
    if t["synthetic_files"]:
        print("合成样本（不计入下面统计）：%s" % t["synthetic_files"])
    print("=" * 78)

    # A1. 读数通道：视图存在 -> 跑了 -> 有落盘读数 / 仅复算 / 未测出 / 没跑。
    print("\nA1. 读数通道（全部真跑样本 n=%d；视图存在 != 跑了）" % t["real_runs"])
    print("%-6s %8s %6s %10s %10s %8s %8s %6s"
          % ("层", "视图存在", "跑了", "落盘读数", "仅复算", "未测出",
             "读数键缺", "没跑"))
    for L in LAYERS:
        s = agg["by_layer"][L]
        print("%-6s %8d %6d %10d %10d %8d %8d %6d"
              % (L, s["view_present"], s["ran"], s["stored_reading"],
                 s["only_recomputed"], s["target"]["unmeasured"],
                 s["target"]["no_reading"], s["target"]["not_run"]))
    print("  注 落盘读数 = goal_now 或旧 verdict 里的主读数；仅复算 = 旧包无落盘"
          "读数，用当前最高版引擎对 view 重算；两者不混口径。")

    # A2. 目标判定：引擎自己的 stop_signal。
    print("\nA2. 够不够达到目标（引擎 layer_goal_stop_signal；判据=引擎停因判据）")
    print("%-6s %6s %10s %6s %8s %12s %8s %6s"
          % ("层", "达成", "其中当时命中", "受阻", "未达成", "判据样本不足",
             "未测出", "没跑"))
    for L in LAYERS:
        s = agg["by_layer"][L]
        print("%-6s %6d %10d %6d %8d %12d %8d %6d"
              % (L, s["target"]["achieved"], s["historic_achieved"],
                 s["target"]["blocked"], s["target"]["not_achieved"],
                 s["target"]["not_judgeable"], s["target"]["unmeasured"],
                 s["target"]["not_run"]))
    print("  注 达成 = 用「落盘 goal_now（新版）/当前口径对最终视图复算（旧版）」"
          "跑引擎停因判据命中；")
    print("     其中当时命中 = 该次真跑的 stop_reason 里真的写过「目标已达成」。")
    print("     两列不同 = 判据在运行中没触发（时序/接线），不是读数不存在 —— 见 E 节。")

    # B. 读数是多少。
    print("\nB. 读数是多少（落盘值 / 复算值分开列；分布 top8）")
    for L in LAYERS:
        s = agg["by_layer"][L]
        print("  %-4s(%s) 主读数=%s" % (L, LAYER_CN[L], s["main_key"]))
        print("       落盘值：%s" % (s["values_stored"] or "（无）"))
        print("       复算值：%s" % (s["values_fresh"] or "（无）"))
        if L == "0":
            print("       excavate_basis=%s | 逐圈点 n_hist=%s"
                  % (s.get("basis"), s.get("hist_lens")))
        elif L == "1":
            print("       settlement(answered/total)=%s"
                  % dict(list((s.get("settlement") or {}).items())[:6]))
        elif L == "both":
            print("       view.upstream_layers=%s | sem_stagnation_top=%s"
                  % (s.get("upstream_layers_values"), s.get("stag_top")))
        else:
            print("       n_hits=%s" % (s.get("n_hits"),))
        print("       逐圈主读数形态=%s"
              % (s.get("trace_signatures"),))
        print("       逐圈主读数最大值分布=%s"
              % (s.get("trace_max_values"),))
        print("       逐圈 vs 收尾读数=%s" % (s.get("trace_vs_final"),))
        if s.get("unmeasured_reasons"):
            print("       未测出原因 top=%s" % (s.get("unmeasured_reasons"),))

    # C. 按引擎版本分层。
    print("\nC. 按引擎版本分层（只陈述读数；视图/跑了/读数/达成 口径同 A）")
    for ver, g in agg["by_version"].items():
        print("  [%s] n=%d 零LLM=%d views=%s"
              % (ver, g["n"], g["llm_calls_zero"], g["views"]))
        for L in LAYERS:
            s = g["layers"][L]
            print("      %-4s 视图%3d 跑了%3d 落盘读数%3d 复算读数%3d 达成%3d "
                  "受阻%2d 未达成%3d 样本不足%3d 未测出%3d"
                  % (L, s["view_present"], s["ran"], s["stored_reading"],
                     s["fresh_reading"], s["target"]["achieved"],
                     s["target"]["blocked"], s["target"]["not_achieved"],
                     s["target"]["not_judgeable"], s["target"]["unmeasured"]))

    # D. goal_now 复算一致性。
    new_rows = [r for r in rows if not r["meta"]["synthetic"]
                and (r["meta"]["engine_tuple"] or (0, 0, 0)) >= V_GOALNOW]
    bad, checked = [], 0
    for r in new_rows:
        for L in LAYERS:
            lr = r["layers"][L]
            if lr["ran"] and lr["goal_now_present"]:
                checked += 1
                if lr["reading_consistency"] is False:
                    bad.append((r["meta"]["name"], L))
    print("\nD. 落盘 goal_now vs **独立复算**（V2.2.12+ 护栏；复算为审计脚本独立实现）")
    print("  V2.2.12+ 包 %d 个；跑过且落盘 goal_now 的层 %d 个；不一致 %d 个%s"
          % (len(new_rows), checked, len(bad),
             ("：" + str(bad[:5]) if bad else "")))

    # E. 运行中停因命中。
    hh = agg["historic_stop_hits"]
    print("\nE. 运行中停因命中（stop_reason 文本，判据真触发过的直接证据）")
    cnt = Counter("%s:%s" % (h["layer"], h["hit"]) for h in hh)
    print("  计数：%s" % (dict(cnt) or "（无）"))
    for h in hh[:12]:
        print("    · %-56s [%s] %s" % (h["file"][:56], h["layer"], h["hit"]))

    # F. 异常/观察。
    counts = agg["anomalies"]["counts"]
    hard = {k: v for k, v in counts.items() if k in HARD_ANOMALIES}
    soft = {k: v for k, v in counts.items() if k not in HARD_ANOMALIES}
    print("\nF. 异常 / 观察")
    print("  硬异常（应为 0，非 0 = 真缺陷信号）：%s" % (hard or "（无）"))
    print("  历史口径 / 观察（解释见报告文档）：%s" % (soft or "（无）"))

    # G. 零 LLM 跑次。
    print("\nG. 零 LLM 跑次（层跑了但 llm_calls=0：链路/服务故障，不是模型能力）")
    if not agg["zero_llm_runs"]:
        print("  无")
    for z in agg["zero_llm_runs"]:
        print("  · %-56s %s route=%s 跑了=%s cb=%s"
              % (z["file"][:56], z["engine"], z["route"],
                 "+".join(z["layers_ran"]), z["cb"]))

    # H. 抽样核对。
    print("\nH. 抽样核对（5 个包，可按 packed 字段逐条核对；--json 有全部行）")
    for d, why in pick_samples(rows, 5):
        m = d["meta"]
        print("  ▸ %s" % m["name"])
        print("     目录=%s 版本=%s route=%s llm_calls=%s | 抽样理由：%s"
              % (m["dir"], m["engine_version"] or "(无)",
                 "+".join(_route_list(m["route"]))[:24], m["llm_calls"], why))
        for L in LAYERS:
            lr = d["layers"][L]
            if not lr["view_present"]:
                continue
            print("     [%-4s] 跑了=%s rounds=%s | 读数来源=%s 落盘=%s "
                  "复算=%s 主读数(%s)=%s"
                  % (L, lr["ran"], lr["rounds_run"], lr["reading_source"],
                     _fmtval(lr["stored_value"]), _fmtval(lr["fresh_value"]),
                     lr["main_key"], _fmtval(lr["main_value"])))
            print("            verdict=%s" % ((lr["verdict"] or "（空）")[:78]))
            print("            目标判定=%s（%s）| 当时停因=%s | 复算一致=%s"
                  % (TARGET_CN[lr["target_status"]],
                     str(lr["target_why"])[:70], lr["historic_stop"],
                     lr["reading_consistency"]))
            print("            依据=%s" % json.dumps(lr["detail"],
                                                    ensure_ascii=False)[:170])

    print("\n" + "=" * 78)
    print("口径说明：只陈述产物读数与可复算结论；未测出 不等于 0，")
    print("判据样本不足 不等于 未达成 —— 三者分列，互不冒充。")


def _markdown_table(agg: OrderedDict) -> str:
    """给报告文档用的 markdown 表（与 --json 同源，报告数字可脚本复算）。"""
    lines = ["| 层 | 视图存在 | 跑了 | 落盘读数 | 仅复算 | 达成 | 其中当时命中 | "
             "受阻 | 未达成 | 判据样本不足 | 未测出 | 没跑 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for L in LAYERS:
        s = agg["by_layer"][L]
        lines.append("| %s %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | "
                     "%d | %d |"
                     % (L, LAYER_CN[L], s["view_present"], s["ran"],
                        s["stored_reading"], s["only_recomputed"],
                        s["target"]["achieved"], s["historic_achieved"],
                        s["target"]["blocked"], s["target"]["not_achieved"],
                        s["target"]["not_judgeable"],
                        s["target"]["unmeasured"], s["target"]["not_run"]))
    return "\n".join(lines)


def _payload(agg: OrderedDict, eng_path: Path, packs: list) -> OrderedDict:
    payload = OrderedDict()
    payload["meta"] = {
        "script": "scripts/lead_layer_goal_audit.py",
        "engine": {"file": str(eng_path.relative_to(ROOT)),
                   "version": "V%d.%d.%d" % tuple(vtuple(eng_path.name))},
        "packs_dirs": packs,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "layers": list(LAYERS),
    }
    payload.update(agg)
    return payload


# ================================ main ================================
def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        description="四层目标读数离线普查（只读，零 API/零 GPU）")
    ap.add_argument("--packs", action="append", default=None,
                    help="产物目录（可重复；默认 outputs + outputs/_e2e_local）")
    ap.add_argument("--json", action="store_true",
                    help="只输出 JSON 到 stdout（给报告复算用）")
    ap.add_argument("--json-out", default="",
                    help="另存 JSON 到指定路径（可选）")
    ap.add_argument("--markdown", action="store_true",
                    help="输出 A 节 markdown 表（与报告同源）")
    ap.add_argument("--selfcheck", action="store_true",
                    help="跑 4 个变异体自检（证明异常护栏有牙）")
    args = ap.parse_args(argv)

    packs = args.packs or [str(OUTPUTS), str(E2E)]
    files: list = []
    for p in packs:
        pp = Path(p)
        pat = str(pp / "*.packed.json") if pp.is_dir() else str(pp)
        files.extend(Path(f) for f in sorted(glob.glob(pat)))
    if not files:
        print("没有 packed 产物可普查（没跑不等于通过）：%s" % packs)
        return 2

    eng_path = latest_engine_path()
    try:
        eng = load_engine(eng_path)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("引擎加载失败（无法复算口径，拒绝假装有读数）：%s: %s"
              % (type(e).__name__, e))
        return 3

    rows = [analyze_pack(Path(f), eng) for f in files]
    if args.selfcheck:
        return selfcheck(rows, eng)

    agg = aggregate(rows)
    if args.markdown:
        print(_markdown_table(agg))
        return 0
    if args.json:
        text = json.dumps(_payload(agg, eng_path, packs), ensure_ascii=False,
                          indent=1, default=str)
        if args.json_out:
            out = Path(args.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print("JSON -> %s" % out)
        else:
            print(text)
        return 0

    print_report(rows, agg, eng_path.name)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(_payload(agg, eng_path, packs),
                                  ensure_ascii=False, indent=1, default=str),
                       encoding="utf-8")
        print("JSON -> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
