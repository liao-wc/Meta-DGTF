# -*- coding: utf-8 -*-
"""V2 在线自动策略：正常任务内的小比例探索 + 后验收敛 + exploit。

不做单独人工 A/B；每次真实 App 任务按 epsilon/UCB 选择臂，执行后由 watcher 写入 outcome。
只改 route/rounds；默认 10% 探索，其余按后验下界 exploit。配置见
dgtf_memory/v2_online_config.json。
"""
from __future__ import annotations
import json, math, os, random, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "dgtf_memory" / "v2_online.jsonl"
CONFIG = ROOT / "dgtf_memory" / "v2_online_config.json"
_LOCK = threading.Lock()

ARMS = {
    "baseline_all2": {
        "route": ["0", "1", "both", "all"],
        "rounds": {"0": 2, "1": 2, "both": 2, "all": 2},
        "note": "四层 2 圈基线",
    },
    "explore_all3": {
        "route": ["0", "1", "both", "all"],
        "rounds": {"0": 3, "1": 3, "both": 3, "all": 3},
        "note": "四层 3 圈探索",
    },
    "explore_lean3": {
        "route": ["0", "1"],
        "rounds": {"0": 3, "1": 3},
        "note": "两层 3 圈低成本探索",
    },
}


def _cfg() -> dict:
    try:
        d = json.loads(CONFIG.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {"enabled": True, "exploration_rate": 0.10, "min_exploit_n": 2}


def _append(row: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with STATE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _load() -> tuple[list[dict], dict]:
    rows = []
    if STATE.is_file():
        for ln in STATE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(ln)
                if isinstance(d, dict):
                    rows.append(d)
            except Exception:
                pass
    outcomes = {}
    for r in rows:
        if r.get("type") == "outcome":
            aid = str(r.get("assignment_id") or "")
            if aid:
                outcomes[aid] = r
    return rows, outcomes


def _stats(rows: list[dict], outcomes: dict) -> dict:
    out = {}
    for r in rows:
        if r.get("type") != "assignment":
            continue
        aid = str(r.get("id") or "")
        arm = str(r.get("arm") or "")
        if not aid or not arm:
            continue
        s = out.setdefault(arm, {"n": 0, "quality": [], "tokens": []})
        o = outcomes.get(aid)
        if o:
            s["n"] += 1
            try:
                s["quality"].append(float(o.get("quality") or 0))
                s["tokens"].append(float(o.get("tokens") or 0))
            except Exception:
                pass
    summary = {}
    for arm, s in out.items():
        qs = s["quality"]
        n = len(qs)
        mean = sum(qs) / n if n else 0.0
        sd = (sum((x - mean) ** 2 for x in qs) / (n - 1)) ** 0.5 if n > 1 else 0.0
        summary[arm] = {"n": n, "quality": round(mean, 4), "sd": round(sd, 4),
                        "tokens": round(sum(s["tokens"]) / max(1, len(s["tokens"])), 1),
                        "low": round(mean - 1.96 * sd / math.sqrt(n), 4) if n > 1 else None}
    return summary


def choose(question: str, opts: dict | None = None, force: bool = False,
           base_arm: dict | None = None) -> dict | None:
    opts = dict(opts or {})
    cfg = _cfg()
    if not bool(cfg.get("enabled", True)):
        return None
    if opts.get("mock") or opts.get("_is_mock") or opts.get("quality_retry"):
        return None
    if not force and (opts.get("route") or opts.get("rounds")
                      or opts.get("profile")):
        return None
    if opts.get("_v2_online"):
        return None
    rows, outcomes = _load()
    if any(r.get("type") == "assignment" and str(r.get("task_id") or "") == str(opts.get("_task_id") or "x")
           for r in rows):
        return None
    stat = _stats(rows, outcomes)
    total_n = sum(int(v.get("n") or 0) for v in stat.values())
    rate = float(cfg.get("exploration_rate") or 0.10)
    rate = max(0.0, min(0.5, rate))
    arms = dict(ARMS)
    default_arm = "baseline_all2"
    if isinstance(base_arm, dict) and base_arm.get("route") and base_arm.get("rounds"):
        arms["base_plan"] = {"route": list(base_arm["route"]),
                             "rounds": dict(base_arm["rounds"]),
                             "note": str(base_arm.get("note") or "当前计划")}
        default_arm = "base_plan"
    names = list(arms)
    # 前几个样本：优先未探索臂，保证覆盖；否则用基线。
    untried = [a for a in names if int((stat.get(a) or {}).get("n") or 0) == 0]
    if untried and total_n < 6:
        arm = random.choice(untried)
        exploration = arm != default_arm
    elif random.random() < rate:
        arm = min(names, key=lambda a: int((stat.get(a) or {}).get("n") or 0))
        exploration = True
    else:
        min_n = int(cfg.get("min_exploit_n") or 2)
        eligible = [a for a in names
                    if int((stat.get(a) or {}).get("n") or 0) >= min_n]
        if not eligible:
            arm = default_arm
            exploration = False
        else:
            # 后验下界 + 成本轻微惩罚；无 low 的用均值。
            def _score(a):
                s = stat.get(a) or {}
                q = s.get("low")
                if q is None:
                    q = s.get("quality") or 0.0
                cost = float(s.get("tokens") or 0) / 600000.0
                return float(q) - 0.05 * cost
            arm = max(eligible, key=_score)
            exploration = arm != default_arm
    aid = "v2o-%s-%04d" % (time.strftime("%Y%m%d%H%M%S"), random.randint(0, 9999))
    a = arms[arm]
    rec = {"type": "assignment", "ts": time.time(), "id": aid, "arm": arm,
           "route": a["route"], "rounds": a["rounds"], "exploration": bool(exploration),
           "qhash": str(abs(hash(str(question or ""))) % 10**12)}
    _append(rec)
    return {"id": aid, "arm": arm, "route": list(a["route"]),
            "rounds": dict(a["rounds"]), "exploration": bool(exploration)}


def bind_task(assignment_id: str, task_id: str) -> None:
    if assignment_id and task_id:
        _append({"type": "bind", "ts": time.time(),
                 "assignment_id": str(assignment_id), "task_id": str(task_id)})


def reconcile(tasks: list[dict], pack_dir: Path) -> int:
    """把已完成但 watcher 漏记的任务补写 outcome；由 API/守护调用。"""
    rows, outcomes = _load()
    assignment_ids = {str(r.get("id")) for r in rows if r.get("type") == "assignment"}
    binds = {str(r.get("assignment_id")): str(r.get("task_id"))
             for r in rows if r.get("type") == "bind"}
    task_by_id = {str(t.get("id")): t for t in (tasks or [])}
    fixed = 0
    for r in rows:
        if r.get("type") != "assignment":
            continue
        aid = str(r.get("id") or "")
        if not aid or aid in outcomes or aid not in assignment_ids:
            continue
        tid = binds.get(aid, "")
        if not tid:
            for t in (tasks or []):
                o = t.get("opts") or {}
                if str((o.get("_v2_online") or {}).get("id") or "") == aid:
                    tid = str(t.get("id") or "")
                    break
        t = task_by_id.get(tid)
        if not t or str(t.get("status")) != "done":
            continue
        name = str(t.get("output_name") or "")
        if not name:
            continue
        pack = Path(pack_dir) / ((name[:-3] + ".packed.json")
                                if name.lower().endswith(".md")
                                else (name + ".packed.json"))
        try:
            d = json.loads(pack.read_text(encoding="utf-8"))
            q, tokens, verified = quality_of_packed(d)
            record_outcome(aid, tid, q, tokens, verified)
            fixed += 1
        except Exception:
            continue
    return fixed


def record_outcome(assignment_id: str, task_id: str, quality: float,
                   tokens: float, verified: bool = False) -> dict:
    rows, outcomes = _load()
    if assignment_id in outcomes:
        return {"ok": True, "deduped": True}
    rec = {"type": "outcome", "ts": time.time(), "assignment_id": assignment_id,
           "task_id": str(task_id or ""), "quality": round(float(quality), 4),
           "tokens": int(float(tokens or 0)), "verified": bool(verified)}
    _append(rec)
    return {"ok": True}


def quality_of_packed(packed: dict) -> tuple[float, int, bool]:
    q = packed.get("quality") or {}
    cov = float(q.get("coverage") or 0.0)
    tri = q.get("tri_consistency", q.get("tri_ratio"))
    try:
        tri = float(tri or 0.0)
    except (TypeError, ValueError):
        tri = 0.0
    quality = 0.55 * cov + 0.45 * tri
    tokens = int(packed.get("llm_tokens") or 0)
    verified = str(q.get("answer_quality") or "") == "verified"
    return round(quality, 4), tokens, verified


def summary() -> dict:
    rows, outcomes = _load()
    stat = _stats(rows, outcomes)
    assignments = [r for r in rows if r.get("type") == "assignment"]
    return {"ok": True, "enabled": bool(_cfg().get("enabled", True)),
            "exploration_rate": float(_cfg().get("exploration_rate") or 0.10),
            "assignments": len(assignments),
            "outcomes": len(outcomes),
            "pending": max(0, len(assignments) - len(outcomes)),
            "arms": stat, "state": str(STATE), "config": str(CONFIG)}
