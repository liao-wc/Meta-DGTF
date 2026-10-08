#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P3] 对 `audit_v122_dead_mechanisms.md` 判「仅源码」的 5 条机制各喂一个
「该触发的输入」，看它触不触发。判定三分类：

    条件窄但成立（triggered） / 机制没工作（语义正确却不触发） / 条件不可达（走不到）

清单以审计报告为准（5 项）：escalate_starve_rounds、no_push_when_idle、
_reopen_closed_debt、both_tighten_ratio、_all_settle_streak。

★ **本版不删任何机制**：判「不可达」的也只进 pending_fix。
★ 每条尽量做**差分负对照**（同输入换一个开关，看分支是否真的变），
  避免把「函数返回了东西」当成「机制工作了」。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / (sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.1-rc1.py")
OUT_JSON = HERE / "_negctl_v1221_p3.json"


def _load():
    spec = importlib.util.spec_from_file_location("dgtf_p3", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p3"] = m
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- 1
def negctl_escalate_starve_rounds(m) -> dict:
    """连续 N 圈无进展 + 名下有挂着的账 → 迁向不可判定。"""
    pool = m.Pool()
    sq = {"id": 1, "question": "Q1", "decidability": "decidable",
          "status": "open", "_starve_rounds": 1}
    pool.sub_questions = [sq]
    pool.deferrals = [{"id": "d_001", "sub_id": 1, "status": "deferred",
                       "revisit_condition": "当 X 出现后"}]
    view = m.View(entry="1")
    stats = {"reclassified": 0, "escalated": 0, "rejected": 0,
             "_transitions": []}
    N = int(((m.DEFAULT_CONFIG.get("spiral") or {})
             .get("escalate_starve_rounds", 2) or 0))
    m._starve_escalation(pool, view, {1: sq}, 3, m.DEFAULT_CONFIG, stats)
    return {
        "triggered": stats["escalated"] > 0,
        "differential": {"N": N, "starve_in": 1, "starve_after":
                         sq.get("_starve_rounds")},
        "evidence": (f"stats.escalated={stats['escalated']}，"
                     f"decidability_log 条数={len(pool.decidability_log)}，"
                     f"sq.decidability={sq.get('decidability')}"),
        "input": "1 条 decidable 未答子问题 + 1 笔 deferred 账 + 无任何 touched",
    }


# ---------------------------------------------------------------- 2
class _Stub:
    """`_uncovered_gate` 只需要 `_check_uncovered_directions` 与 `vp`。"""
    verbose = False

    def vp(self, *a, **k):
        return None

    def _check_uncovered_directions(self, view):
        return ["低垂果实 A", "低垂果实 B"]


def negctl_no_push_when_idle(m) -> dict:
    """停止判据是「层内空转」时**不推迟**（差分负对照：换开关看分支是否变）。"""
    gate = m.MetaDGTF._uncovered_gate
    stub = _Stub()
    view = m.View(entry="1")
    reasons = ["连续 2 轮有新增但无推进（修行层无新增或无推进）"]

    def _run(flag):
        sp = {"no_push_when_idle": flag, "max_uncovered_pushes": 1}
        return gate(stub, view, list(reasons), 0, None, False, sp)

    on = _run(1)
    off = _run(0)
    # 机制「工作」的定义：ON 不推迟（note 空）、OFF 推迟（note 非空）
    trig = (on[3] == "") and (off[3] != "")
    return {
        "triggered": trig,
        "differential": {"no_push_when_idle=1 → note": on[3][:40],
                         "no_push_when_idle=0 → note": off[3][:40],
                         "off_streak": off[1], "on_streak": on[1]},
        "evidence": (f"ON: reasons 原样={on[0] == reasons} note={on[3]!r}；"
                     f"OFF: note={off[3][:30]!r} streak={off[1]}"),
        "input": "1 条「有新增但无推进」空转判据 + 2 条未深入方向（首测）",
    }


# ---------------------------------------------------------------- 3
def negctl_reopen_closed_debt(m) -> dict:
    """分类被推翻 + 曾有关掉的账 → 重新挂一笔（新 id，不复活旧条）。"""
    pool = m.Pool()
    pool.sub_questions = [{"id": 7, "question": "Q7", "decidability": "partial",
                           "status": "open"}]
    pool.deferrals = [{"id": "d_001", "sub_id": 7, "status": "escalated",
                       "revisit_condition": "当 Y 出现后",
                       "resolved_at": "L2", "resolution_reason": "迁向 und"}]
    sq = pool.sub_questions[0]
    new_id = m._reopen_closed_debt(pool, sq, 7, layer=3)
    # 差分负对照：本来没欠过账的子问题不该凭空开
    new_id2 = m._reopen_closed_debt(pool, {"id": 9, "question": "Q9"}, 9, 3)
    return {
        "triggered": bool(new_id),
        "differential": {"有 escalated 记录 → 新 id": new_id,
                         "无任何记录 → 新 id": new_id2},
        "evidence": (f"新增债务 {new_id}（status="
                     f"{pool.deferrals[-1].get('status') if new_id else '—'}，"
                     f"reopened_from="
                     f"{pool.deferrals[-1].get('reopened_from') if new_id else '—'}）；"
                     f"负对照（没欠过账）返回 {new_id2!r}"),
        "input": "sub 7 名下有一笔 status=escalated 的旧账、且当前无 deferred 账",
    }


# ---------------------------------------------------------------- 4
def negctl_both_tighten_ratio(m) -> dict:
    """both 占比超阈值 → 按两端理由对称性改判回 0/1。"""
    def _c(i):
        return {"position": "both",
                "why_0": f"甲侧理由{i}：成本可控且短期见效，但覆盖范围有限",
                "why_1": f"乙侧理由{i}：长期根治但投入大、周期长、扰民",
                "desc": f"cand{i}"}
    cands = [_c(i) for i in range(1, 6)]
    before = sum(1 for c in cands if c.get("position") == "both")
    out = m._tighten_both([dict(c) for c in cands], max_ratio=0.3)
    after = sum(1 for c in out if c.get("position") == "both")
    # 差分负对照：占比不超阈值时不该动
    two = [dict(c) for c in cands[:2]]
    out2 = m._tighten_both(two, max_ratio=0.3)
    return {
        "triggered": after < before,
        "differential": {"超阈值 both": f"{before} → {after}",
                         "不超阈值 both": f"{sum(1 for c in out2 if c.get('position') == 'both')} 原样"},
        "evidence": (f"max_ratio=0.3、5 条全 both → 改判后 both={after}"
                     f"（positions={[c.get('position') for c in out]}）"),
        "input": "5 条候选全部 position=both，why_0/why_1 各 ≥12 字且不重合",
    }


# ---------------------------------------------------------------- 5
def negctl_all_settle_streak(m) -> dict:
    """元层清算未下降 → 不再推迟停止。

    ★ 这段判据**内联**在 `_run_layer` 的圈循环里，没有可单独调用的宿主
      函数（不像 no_push_when_idle 有 `_uncovered_gate`）。所以本项给的是
      **守卫链分析 + 实测 0 命中**，不是一次真实触发 —— 如实标注。
    """
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    guards = {
        "内联在 _run_layer 圈循环": "_all_settle_streak" in src,
        "入口守卫 entry == 'all'": 'stop and entry == "all"' in src,
        "层圈未满 layer_no < _total_rounds": "layer_no < _total_rounds" in src,
        "要求 clean=False 且 unsettled>0": "not _clo_pre.get(\"clean\", True)" in src,
        "要求 unsettled 不下降": "_cur_uns < _last_unsettled" in src,
    }
    return {
        "triggered": False,
        "reachable": False,
        "differential": {"可单独调用的宿主函数": "无（内联）"},
        "evidence": ("守卫链五项齐备：" + "；".join(
            f"{k}={v}" for k, v in guards.items())
            + "。要触达必须同时满足「元层产生停止判据 + 未跑满预定圈数 + "
              "_settle_meta 报未清算 + 连续两次 unsettled 不下降」；"
              "审计语料 316 日志 / 296 产物里 0 命中。"),
        "input": "（无法构造可直接调用的输入 —— 判据内联在圈循环里）",
        "note": "本项是**分析式判定**，不是实测触发；按任务书第三类归档。",
    }


FNS = [("escalate_starve_rounds", negctl_escalate_starve_rounds),
       ("no_push_when_idle", negctl_no_push_when_idle),
       ("_reopen_closed_debt", negctl_reopen_closed_debt),
       ("both_tighten_ratio", negctl_both_tighten_ratio),
       ("_all_settle_streak", negctl_all_settle_streak)]


def _verdict(triggered: bool, reachable: bool) -> str:
    if triggered:
        return "条件窄但成立"
    return "机制没工作" if reachable else "条件不可达"


NEXT = {"条件窄但成立": "保留（不删）",
        "机制没工作": "修（进 pending_fix）",
        "条件不可达": "归档（进 pending_fix，本版不删）"}


def main() -> int:
    m = _load()
    data = {}
    for name, fn in FNS:
        try:
            r = fn(m)
        except Exception as e:  # noqa: BLE001
            r = {"triggered": False, "differential": {},
                 "evidence": f"{type(e).__name__}: {e}",
                 "input": "（构造失败）"}
        trig = bool(r.get("triggered"))
        reach = bool(r.get("reachable", True))
        v = _verdict(trig, reach)
        r["verdict"] = v
        r["next"] = NEXT[v]
        data[name] = r
        print(f"  {name:26s} triggered={trig!s:5s} → {v}")
    OUT_JSON.write_bytes(json.dumps(data, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    print(f"✓ 写入 {OUT_JSON.name}（{len(data)} 条）")
    print("P3_NEGCTL_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
