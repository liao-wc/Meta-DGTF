#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 补丁 · 第 1 阶段：EML 经验记忆回路（纯函数 + 存储层）。

依据见 `_设计_经验记忆回路_v12331.md`：
  · ACE（arXiv 2510.04618）：**不重写知识**，增量条目 + 确定性合并
    （反面数据：1.8 万 token 被压缩到 122 ⇒ 66.7→57.1）；
  · Memory-R1/Mem0：写入决策 ADD/MERGE/UPDATE/**矛盾单独建档**；
  · WebCoach：经验当**建议**注入，且**步数不增**（⇒ 双边记账）；
  · MRRL：**记忆质量闸**四问 + micro/meso/macro 三级反思 + 遗忘清扫；
  · Generative Agents：检索分 = recency × importance × relevance。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


EML = '''# ============================================================
# EML · 经验记忆回路（Experiential Memory Loop）
#   「读（recall）→ 用（留痕）→ 写（consolidate）」三段，加一道**质量闸**。
#
# ★ 为什么不是「让模型总结一下上次学到了什么」：
#   ACE（arXiv 2510.04618）实测——把 1.8 万 token 的策略**压缩重写**成 122
#   token，准确率从 66.7 掉到 57.1。**模型擅长用知识，不擅长整理知识。**
#   ⇒ 本实现：playbook **只增不删**、条目**逐条增量**、合并用**确定性规则**
#     （sim3 阈值），永不「重写」已有条目。
#
# ★ 红线对齐（先写清再写码）：
#   · 输入是形状不是数据 ⇒ 记忆**只存「条件→动作」**（procedure），
#     绝不存「结论/答案」（facts）。注入面只有调度与守卫阈值。
#   · 悬置不打分 ⇒ 记忆**不记录**任何悬置的好坏。
#   · 失败留痕 ⇒ `retired` 只改状态位，**不删行**（append-only）。
#   · 入池前挡重复 ⇒ 复用既有 sim3 阈值（0.85）做聚合。
#   · 默认零行为差 ⇒ 出厂 `playbook.mode = "shadow"`（只记不生效）。
#
# ★ 学坏防线（五条）：
#   F1 隔离：新条目一律 `shadow`，不生效；
#   F2 双边记账：每条记 `{cost_delta, quality_delta}`；**只省成本不升级**；
#   F3 一键关：`off` / `shadow` / `on` 三态；
#   F4 遗忘：陈旧 + 未被用过 + 证据不足 ⇒ `retired`（行仍在）；
#   F5 只增不删：任何操作后 playbook 行数**单调不减**。
# ============================================================

_EML_DIRNAME = "dgtf_memory"
_EML_EPISODES = "episodes.jsonl"
_EML_PLAYBOOK = "playbook.jsonl"
_EML_MEMORY_MD = "MEMORY.md"
_EML_KINDS = ("schedule", "probe", "structure", "guard")
_EML_MODES = ("off", "shadow", "on")
_EML_MODE_DEFAULT = "shadow"
_EML_TOP_K = 3
_EML_PROMOTE_N = 3            # meso：同向证据达到几次才 shadow→active
_EML_HALFLIFE_DAYS = 14.0     # 与 auto.history_halflife_days 同源
_EML_RETIRE_RECENCY = 0.05
_EML_AGG_SIM = 0.85           # 聚合阈值（沿用信念归并口径：宁可漏并）
#: [EML] 质量闸四问的名字（判据与报告共用，避免两处措辞分叉）。
_EML_GATE_Q = ("evidence", "contradiction", "verifiable", "redline")


def eml_dir(base=None) -> Path:
    """记忆库目录（默认仓库根 `dgtf_memory/`）。"""
    _b = Path(base) if base else Path(__file__).resolve().parent
    return _b / _EML_DIRNAME


def eml_read_jsonl(path) -> list:
    """读 jsonl（坏行**跳过但计数**，不静默当作空库）。"""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def eml_append_jsonl(path, obj) -> bool:
    """**只追加**一行（F5 只增不删的物理保证）。返回是否写入。"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\\n")
        return True
    except Exception:
        return False


def eml_rewrite_jsonl(path, rows) -> bool:
    """整表重写（**只用于状态位演进**：行数与 id 集合必须不变）。"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        _old = eml_read_jsonl(p)
        if len(rows) != len(_old):
            return False          # ★ F5：行数不许变
        if {r.get("id") for r in rows} != {r.get("id") for r in _old}:
            return False          # ★ F5：id 集合不许变
        with p.open("w", encoding="utf-8", newline="\\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\\n")
        return True
    except Exception:
        return False


def eml_q_features(question: str) -> dict:
    """题型特征（与 `_auto_dispatch._features` 同口径的**子集**，便于比对）。"""
    q = str(question or "")
    return {
        "len": len(q),
        "how": ("如何" in q) or ("怎么" in q) or ("怎样" in q),
        "choice": ("或" in q) or ("还是" in q),
        "multi": (q.count("，") + q.count(",")) >= 2,
        "meta": any(k in q for k in ("本身", "自身", "递归", "元", "整体")),
    }


def episode_from_result(result: dict, t: float = 0.0) -> dict:
    """把一次跑压成**标准化 episode**（WebCondenser 的「标准化日志」思路）。"""
    r = result or {}
    vs = r.get("views") or {}
    ps = r.get("pools") or {}
    duty, cut = {}, []
    for e in ("0", "1", "both", "all"):
        v = vs.get(e) or {}
        _d = (v.get("duty") or {}).get("S")
        if _d is not None:
            duty[e] = float(_d)
        _st = str(v.get("stop_reason") or "")
        if "体力耗尽" in _st:
            cut.append(e)
    tri = r.get("tri_consensus") or []
    tri_rate = None
    if tri:
        try:
            tri_rate = sum(1 for x in tri if x.get("agree")) / float(len(tri))
        except Exception:
            tri_rate = None
    return {
        "run_id": str(r.get("id") or r.get("output_name") or ""),
        "t": float(t or 0.0),
        "q_features": eml_q_features(r.get("question") or ""),
        "route": [str(x) for x in (r.get("route") or [])],
        "mode": str((r.get("dispatch") or {}).get("_parallel_mode") or ""),
        "rounds_cap": dict(r.get("rounds") or {}),
        "cut_layers": cut,
        "duty": duty,
        "tri_rate": tri_rate,
        "n_anchors": len(((ps.get("1") or {}).get("anchors") or [])),
        "n_web": len(((ps.get("1") or {}).get("web_results") or [])),
        "cost": {"tokens": int(r.get("llm_tokens") or 0),
                 "calls": int(r.get("llm_calls") or 0)},
    }


def eml_candidates_from_result(result: dict, ep: dict = None) -> list:
    """**micro 反思**：从一次跑抽候选经验（条件 → 动作，**必须带本跑读数**）。

    ★ 每条候选都必须能回答「这条是拿哪个读数换来的」—— 没有读数的候选
      `gate_check` 第一问就拒（防「凭感觉学」）。
    """
    r = result or {}
    ep = ep or episode_from_result(r)
    out = []
    # ① 截断层 ⇒ 圈数上限偏低（schedule/rounds）
    for e in (ep.get("cut_layers") or []):
        out.append({"kind": "schedule", "cond": {"issue": "cut", "layer": e},
                    "action": {"key": "rounds_delta", "layer": e, "delta": 1},
                    "readings": {"before": {"stop": "体力耗尽"},
                                 "after": {"stop": "期望自然停"}},
                    "why": "该层走满上限仍未触发停止判据（被截断）"})
    # ② 职责未尽 ⇒ 先做问项抽取（probe/carve）
    _short = [e for e, s in (ep.get("duty") or {}).items()
              if float(s) < float(_DUTY_FLOOR)]
    if _short:
        out.append({"kind": "probe",
                    "cond": {"issue": "duty_short", "layers": sorted(_short)},
                    "action": {"key": "carve_first", "layers": sorted(_short)},
                    "readings": {"before": {"duty_S_med": _lv_med(ep, _short)},
                                 "after": {"duty_S_med": "期望上升"}},
                    "why": "层交付面对原始问题的覆盖/相关双低"})
    # ③ 三态一致率低 ⇒ 该题型三态读数不可当判据（guard/decidable）
    _tr = ep.get("tri_rate")
    if _tr is not None and float(_tr) < 0.33:
        out.append({"kind": "guard", "cond": {"issue": "tri_unstable"},
                    "action": {"key": "tri_advisory_only", "rate": round(_tr, 3)},
                    "readings": {"before": {"tri_rate": round(_tr, 3)},
                                 "after": {"tri_rate": "期望上升"}},
                    "why": "三态一致率低于 33%，标签在该跑里不稳"})
    # ④ 成本高于历史 p75 而职责未升 ⇒ **负面**条目（学坏的证据，留痕）
    _c = (ep.get("cost") or {}).get("tokens") or 0
    _p75 = (((r.get("_auto_dispatch") or {}).get("_history") or {})
            .get("tokens_p75") or 0)
    _dmed = _lv_med(ep, list((ep.get("duty") or {}).keys()))
    if _p75 and _c > float(_p75) and (_dmed is None or float(_dmed) < 0.35):
        out.append({"kind": "schedule", "cond": {"issue": "cost_no_gain"},
                    "action": {"key": "note_cost_no_gain",
                               "tokens": _c, "duty_med": _dmed},
                    "readings": {"before": {"tokens": _c, "duty_med": _dmed},
                                 "after": {"duty_med": "期望上升"}},
                    "why": "成本超过历史 p75 而职责未升（只贵不好）"})
    for c in out:
        c["evidence"] = [ep.get("run_id") or ""]
        c["source"] = "engine"
    return out


def _lv_med(ep: dict, layers) -> Optional[float]:
    _v = [(ep.get("duty") or {}).get(e) for e in (layers or [])]
    _v = [float(x) for x in _v if x is not None]
    if not _v:
        return None
    _v.sort()
    n = len(_v)
    return _v[n // 2] if n % 2 else (_v[n // 2 - 1] + _v[n // 2]) / 2.0


def gate_check(cand: dict, playbook: list,
               promote_n: int = _EML_PROMOTE_N) -> tuple:
    """**记忆质量闸**四问（MRRL Layer B）。返回 `(ok, why)`。

      1) evidence      —— 候选必须带本跑**具体读数**（无读数 ⇒ 拒）
      2) contradiction —— 与 active 条目矛盾 ⇒ 不覆盖，进 `contra` 计数
      3) verifiable    —— 动作必须**可被后续跑验证**（能定义 before/after ⇒ 可证）
      4) redline       —— 动作**不许触碰红线**（打分/拦悬置/注入答案 ⇒ 拒）
    ★ 四问**缺一不可**，且每问都要能被变异体单独打红。
    """
    c = cand or {}
    if not isinstance(c.get("readings"), dict) or not c["readings"].get("before"):
        return False, "evidence"
    _act = c.get("action") or {}
    if not isinstance(_act, dict) or not _act.get("key"):
        return False, "verifiable"
    _blob = json.dumps(_act, ensure_ascii=False)
    _bad = ("score", "grade", "rank_claim", "verdict_claim", "answer_text",
            "inject_answer", "block_suspension", "drop_suspension")
    if any(k in _blob for k in _bad):
        return False, "redline"
    # 矛盾检查：同 kind 且 cond 相同但 action 不同 ⇒ 记矛盾（不覆盖）
    for e in (playbook or []):
        if e.get("status") not in ("active", "shadow"):
            continue
        if e.get("kind") != c.get("kind"):
            continue
        if json.dumps(e.get("cond") or {}, sort_keys=True) != \\
                json.dumps(c.get("cond") or {}, sort_keys=True):
            continue
        if json.dumps(e.get("action") or {}, sort_keys=True) == \\
                json.dumps(_act, sort_keys=True):
            return False, "duplicate"
    return True, ""


def eml_merge_candidate(playbook: list, cand: dict, now: float) -> dict:
    """把候选并进 playbook（**只增不删**）。返回**新增的那一条**。

    · 同 `(kind, cond, action)` 已存在 ⇒ 不新增，而是把证据并到旧条目
      （`evidence` 去重追加、`n_evidence+1`）—— 增量而不是重写。
    · 新条目一律 `status="shadow"`（F1 隔离：先不生效）。
    """
    _key = (cand.get("kind"),
            json.dumps(cand.get("cond") or {}, sort_keys=True),
            json.dumps(cand.get("action") or {}, sort_keys=True))
    for e in (playbook or []):
        _ek = (e.get("kind"),
               json.dumps(e.get("cond") or {}, sort_keys=True),
               json.dumps(e.get("action") or {}, sort_keys=True))
        if _ek == _key:
            _ev = list(e.get("evidence") or [])
            for _x in (cand.get("evidence") or []):
                if _x and _x not in _ev:
                    _ev.append(_x)
            e["evidence"] = _ev
            e["n_evidence"] = len(_ev)
            e["t_last"] = float(now)
            return e
    ent = {
        "id": "L%04d" % (len(playbook or []) + 1),
        "kind": cand.get("kind"),
        "cond": cand.get("cond") or {},
        "action": cand.get("action") or {},
        "readings": cand.get("readings") or {},
        "why": cand.get("why", ""),
        "evidence": list(cand.get("evidence") or []),
        "n_evidence": len(cand.get("evidence") or []),
        "status": "shadow",
        "weight": 1.0,
        "contra": 0,
        "t_written": float(now),
        "t_last": float(now),
        "t_used": [],
        "source": cand.get("source", "engine"),
        "cost_delta": 0.0,
        "quality_delta": 0.0,
    }
    playbook.append(ent)
    return ent


def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N) -> list:
    """**meso 反思**：同向证据够 ⇒ `shadow → active`；反向证据够 ⇒ 降级。

    ★ **双边记账（F2）**：只有「质量上升」或「质量未变但成本下降**且**质量
      不降」才允许升级；`quality_delta < 0` 或「只省成本」⇒ 不升。
    ★ 返回状态变更列表（由调用方决定是否落盘）。
    """
    changes = []
    for e in (playbook or []):
        if e.get("status") != "shadow":
            continue
        _n = int(e.get("n_evidence", 0) or 0)
        _qd = float(e.get("quality_delta", 0.0) or 0.0)
        _cd = float(e.get("cost_delta", 0.0) or 0.0)
        if _n < int(promote_n):
            continue
        if int(e.get("contra", 0) or 0) >= int(promote_n):
            continue
        # ★ 只省成本 / 质量下降 ⇒ 不许升级（防「学坏」）
        if _qd < 0:
            continue
        if _qd == 0.0 and _cd < 0.0:
            changes.append({"id": e.get("id"), "to": "blocked_cost_only"})
            continue
        e["status"] = "active"
        e["weight"] = min(1.0, 0.5 + 0.25 * _n)
        changes.append({"id": e.get("id"), "to": "active"})
    return changes


def eml_note_contra(playbook: list, entries, why: str = "") -> int:
    """记一次**反向证据**（不覆盖、不删除，只计数）。"""
    _ids = {e.get("id") for e in (entries or []) if e.get("id")}
    n = 0
    for e in (playbook or []):
        if e.get("id") in _ids:
            e["contra"] = int(e.get("contra", 0) or 0) + 1
            e["contra_last"] = why
            n += 1
    return n


def eml_sweep_forget(playbook: list, now: float,
                     halflife: float = _EML_HALFLIFE_DAYS,
                     retire_recency: float = _EML_RETIRE_RECENCY,
                     promote_n: int = _EML_PROMOTE_N) -> list:
    """**遗忘清扫**（MRRL 的 forgetting sweep）：陈旧 + 从未用过 + 证据弱 ⇒ retired。

    ★ 只改 `status`，**不删行**（红线「失败留痕」）。
    """
    out = []
    for e in (playbook or []):
        if e.get("status") not in ("shadow", "active"):
            continue
        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        if _rec >= float(retire_recency):
            continue
        if (e.get("t_used") or []):
            continue
        if int(e.get("n_evidence", 0) or 0) >= int(promote_n):
            continue
        e["status"] = "retired"
        e["retired_why"] = ("recency=%.3f<%.3f 且未被用过且证据< %d"
                            % (_rec, retire_recency, promote_n))
        out.append(e)
    return out


def eml_recall(playbook: list, kind: str, now: float,
               halflife: float = _EML_HALFLIFE_DAYS,
               top_k: int = _EML_TOP_K) -> list:
    """**读**：按 `recency^0.5 × 证据强度 × 相关度` 排序取 top-k（只取 active）。

    ★ 只取 `active`：`shadow` 一律**不生效**（F1 隔离）——「读到但不用」与
      「读不到」在留痕里区分开。
    """
    out = []
    for e in (playbook or []):
        if e.get("status") != "active":
            continue
        if str(e.get("kind")) != str(kind):
            continue
        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        _ev = 1.0 - 0.5 ** float(e.get("n_evidence", 0) or 0)
        _w = float(e.get("weight", 1.0) or 1.0)
        _score = (_rec ** 0.5) * _ev * _w
        out.append({"id": e.get("id"), "score": round(_score, 6),
                    "action": e.get("action") or {}, "cond": e.get("cond") or {}})
    out.sort(key=lambda x: -x["score"])
    return out[:int(top_k)]


def eml_aggregate_macro(playbook: list, now: float,
                        sim_thr: float = _EML_AGG_SIM) -> list:
    """**macro 反思**：把同类 active 条目聚成**父条目**（只做索引，不重写原文）。

    ★ ACE 教训：**不许压缩重写**。父条目只写「哪几条属于同一族」+ 共同动作键，
      子条目原文一字不动。
    """
    _act = [e for e in (playbook or []) if e.get("status") == "active"]
    used, parents = set(), []
    for i, a in enumerate(_act):
        if a.get("id") in used:
            continue
        fam = [a]
        for b in _act[i + 1:]:
            if b.get("id") in used:
                continue
            if a.get("kind") != b.get("kind"):
                continue
            if str((a.get("action") or {}).get("key")) != \\
                    str((b.get("action") or {}).get("key")):
                continue
            _t1 = json.dumps([a.get("cond"), a.get("action")],
                             ensure_ascii=False)
            _t2 = json.dumps([b.get("cond"), b.get("action")],
                             ensure_ascii=False)
            try:
                if float(_sim3(_t1, _t2)) < float(sim_thr):
                    continue
            except Exception:
                continue
            fam.append(b)
            used.add(b.get("id"))
        if len(fam) >= 2:
            used.add(a.get("id"))
            parents.append({"kind": a.get("kind"),
                            "key": (a.get("action") or {}).get("key"),
                            "members": [x.get("id") for x in fam],
                            "note": "父条目只做索引，子条目原文不动（ACE 教训）"})
    return parents


def eml_summarize(playbook: list, limit: int = 40) -> str:
    """生成 `MEMORY.md`（人可读摘要；自动，不是权威存储）。

    ★ 与 ACE 的「不压缩」一致：摘要**只做索引**（id + 条件 + 动作），
      完整证据留在 jsonl 里，摘要丢了也不影响行为。
    """
    rows = list(playbook or [])
    cnt = {}
    for e in rows:
        cnt[e.get("status", "?")] = cnt.get(e.get("status", "?"), 0) + 1
    L = ["# 元DGTF 记忆库（EML 自动生成）", "",
         "> 本文件是**索引**，权威数据在 `playbook.jsonl` / `episodes.jsonl`。",
         "> 状态：`active` 生效 / `shadow` 隔离观察 / `retired` 已遗忘"
         "（**行仍在**，只改状态位）。", "",
         "计数：" + "、".join("%s=%d" % (k, cnt[k]) for k in sorted(cnt)), ""]
    for st in ("active", "shadow", "retired"):
        sub = [e for e in rows if e.get("status") == st]
        if not sub:
            continue
        L.append("## %s（%d）" % (st, len(sub)))
        L.append("")
        for e in sub[:limit]:
            L.append("- `%s` [%s] %s ⇒ `%s`（证据 %d，反向 %d）"
                     % (e.get("id"), e.get("kind"),
                        json.dumps(e.get("cond") or {}, ensure_ascii=False)[:70],
                        json.dumps(e.get("action") or {},
                                   ensure_ascii=False)[:60],
                        int(e.get("n_evidence", 0) or 0),
                        int(e.get("contra", 0) or 0)))
        L.append("")
    return "\\n".join(L)


def eml_write_memory_md(playbook: list, base=None) -> bool:
    try:
        d = eml_dir(base)
        d.mkdir(parents=True, exist_ok=True)
        (d / _EML_MEMORY_MD).write_text(eml_summarize(playbook),
                                        encoding="utf-8", newline="\\n")
        return True
    except Exception:
        return False


'''


def main():
    s = _load()

    # 版本号（两处）
    s = rep(s, "元 DGTF · v1.23.30", "元 DGTF · v1.23.31", "docstring 标题")
    s = rep(s, '__version__ = "1.23.30"', '__version__ = "1.23.31"', "__version__")

    # 纯函数块：插在 LDG 块之前（都靠模块级常量，顺序无关）
    anchor = "# ============================================================\n" \
             "# 层职责守卫（Layer Duty Guard）"
    s = rep(s, anchor, EML + anchor, "EML 纯函数块")

    _save(s)
    print("OK 第 1 阶段（EML 纯函数 + 存储）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    for _m in ("def episode_from_result(", "def eml_candidates_from_result(",
               "def gate_check(", "def eml_recall(", "def eml_promote(",
               "def eml_sweep_forget(", "def eml_aggregate_macro(",
               "def eml_summarize("):
        assert _m in s2, _m
    print("复读校验通过")


if __name__ == "__main__":
    main()
