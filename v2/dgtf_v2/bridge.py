# -*- coding: utf-8 -*-
"""V1 → V2 的双写桥与契约体检。

- 双写：V1 继续写 episodes/playbook；这里把结构读数与 outcome 追加到
  dgtf_memory/v2_events.jsonl。只写计数/质量，不写答案正文。
- 契约体检：把 packed 里的 View/Pool 映射成 V2 LayerResult，逐层 validate；
  warn（默认）只报，raise（opt-in）才抛。它不改变 V1 执行。
"""
from __future__ import annotations

from pathlib import Path

from .contracts import (ContractViolation, LayerResult, LayerState,
                        LAYER_CONTRACTS, validate_result)
from .memory import MemoryLake


DEFAULT_EML_PATH = "dgtf_memory/v2_events.jsonl"


def _view(packed: dict, entry: str) -> dict:
    return ((packed.get("views") or {}).get(entry) or {})


def _pool(packed: dict, entry: str) -> dict:
    return ((packed.get("pools") or {}).get(entry) or {})


def _quality(packed: dict) -> tuple[float, float, int, int]:
    """返回 (coverage, tri_ratio, answered, answerable_total)，缺项给 0。"""
    q = packed.get("quality") or {}
    cov = float(q.get("coverage") or 0.0)
    tri = float(q.get("tri_ratio") or 0.0)
    ans = int(q.get("answered") or 0)
    tot = int(q.get("answerable_total") or 0)
    if not q:
        subs = list(_pool(packed, "1").get("sub_questions") or [])
        tot = len(subs)
        ans = sum(1 for s in subs if s.get("status") == "answered")
        cov = (ans / tot) if tot else 0.0
        t = packed.get("tri_state") or [0, 0]
        try:
            tri = (int(t[0]) / int(t[1])) if int(t[1]) else 0.0
        except (TypeError, ValueError, IndexError):
            tri = 0.0
    return cov, tri, ans, tot


class V2MemoryBridge:
    def __init__(self, path: str | Path | None = DEFAULT_EML_PATH,
                 enabled: bool = True, allow_anon: bool = False):
        self.enabled = bool(enabled)
        self.allow_anon = bool(allow_anon)
        self.path = str(path or DEFAULT_EML_PATH)
        self.memory = MemoryLake(self.path if self.enabled else None)

    def record_packed(self, packed: dict) -> dict:
        """把一次 V1 跑次写成 V2 事件（结构 + outcome），不写答案文本。"""
        if not self.enabled:
            return {"enabled": False, "events": 0}
        rid = str(packed.get("id") or "").strip()
        if not rid and not self.allow_anon:
            return {"enabled": True, "skipped": "anon",
                    "why": "无 run_id 的测试/匿名跑次不写生产 V2 记忆"}
        _test_prefix = ("E2E_", "test", "smoke", "pytest", "v2-")
        if rid.startswith(_test_prefix) and not self.allow_anon:
            return {"enabled": True, "skipped": "test_id",
                    "why": "测试跑次不写生产 V2 记忆：%s" % rid}
        rid = rid or "v1-anon"
        cov, tri, ans, tot = _quality(packed)
        q = 0.55 * cov + 0.45 * tri
        rounds = packed.get("rounds") or {}
        n = 0
        for entry in ("0", "1", "both", "all"):
            v = _view(packed, entry)
            if not v:
                continue
            self.memory.append(
                run_id=rid, plane="semantic", layer=entry,
                kind="structure", key="structure:%s" % entry,
                payload={"candidates": len(v.get("candidates") or []),
                         "amps": len(v.get("amps") or []),
                         "threads": len(v.get("threads") or []),
                         "suspensions": len(v.get("suspensions") or []),
                         "probes": len(v.get("probes") or []),
                         "tier": 3},
                provenance=[str(packed.get("id") or "v1")],
                confidence=0.6)
            n += 1
            try:
                r = int(rounds.get(entry, 1) or 1)
            except (TypeError, ValueError):
                r = 1
            self.memory.record_outcome(
                run_id=rid, template="%s:r%d" % (entry, r),
                quality=q, calls=1,
                tokens=max(1, int(packed.get("llm_tokens") or 1)
                           // max(1, len(packed.get("route") or ["0", "1", "both", "all"]))),
                success=True)
            n += 1
        return {"enabled": True, "events": n, "path": self.path,
                "coverage": round(cov, 4), "tri_ratio": round(tri, 4),
                "answered": ans, "answerable_total": tot}

    def priors(self) -> dict:
        return self.memory.scheduler_priors()

    def stats(self) -> dict:
        return self.memory.stats()

    # ── 契约体检 ────────────────────────────────────────────
    def packed_to_layer_results(self, packed: dict) -> dict[str, LayerResult]:
        # 先做职责修复：evidence→citations、1 层 actions→all、all 四件套补齐。
        from .core_duty import repair_packed
        packed, _ = repair_packed(packed)
        qcov, qtri, qans, qtot = _quality(packed)
        route = [str(x) for x in (packed.get("route") or [])]
        out: dict[str, LayerResult] = {}
        for entry in route:
            v = _view(packed, entry)
            if not v:
                continue
            rounds = int((packed.get("rounds") or {}).get(entry, 0) or 0)
            if entry == "0":
                aspects = []
                for i, c in enumerate(v.get("candidates") or [], 1):
                    aspects.append({"id": "C%d" % i, "aspect": str(c.get("desc", ""))[:80],
                                    "polarity": str(c.get("position", "")), "novelty": 0.5})
                for i, a in enumerate(v.get("amps") or [], 1):
                    aspects.append({"id": "A%d" % i, "aspect": str(a.get("desc", ""))[:80],
                                    "polarity": str(a.get("polarity", "")), "novelty": 0.6})
                art = {"aspect_map": aspects,
                       "suspensions": list(v.get("suspensions") or []),
                       "probe_queue": list(v.get("probes") or []),
                       "novelty_curve": []}
                st = LayerState("0", rounds=rounds, status="done")
            elif entry == "1":
                subs = list(_pool(packed, "1").get("sub_questions") or [])
                answers = []
                # 研究层真正交付的是 decidable_product（answer + evidence），
                # 不是每个 sub_question 都带 citations；按实际产物映射。
                dp = v.get("decidable_product") or {}
                if str(dp.get("answer") or "").strip():
                    answers.append({
                        "id": "DP", "label": "decidable",
                        "citations": list(dp.get("evidence") or []),
                        "answer": str(dp.get("answer") or "")[:240],
                    })
                else:
                    for s in subs:
                        label = str(s.get("decidability") or s.get("status")
                                    or "undecidable")
                        if label not in ("decidable", "partial", "undecidable"):
                            label = "undecidable"
                        answers.append({"id": s.get("id"), "label": label,
                                        "citations": list(s.get("citations")
                                                          or s.get("evidence") or []),
                                        "answer": str(s.get("answer") or "")[:120]})
                art = {"answer_set": answers,
                       "abstentions": [a for a in answers if a["label"] == "undecidable"],
                       "coverage": float(qcov),
                       "citations": [c for a in answers for c in a["citations"]],
                       "debt_set": [a for a in answers if a["label"] != "decidable"]}
                st = LayerState("1", rounds=rounds, coverage=float(qcov),
                                debt=max(0, qtot - qans), status="done")
            elif entry == "both":
                adjs = list(v.get("adjudications") or [])
                art = {"synthesis": str(v.get("manifest") or v.get("collision") or "")[:200],
                       "argument_graph": {"defeated": [str(x)[:60] for x in adjs],
                                          "undecided": [str(t.get("desc", ""))[:60]
                                                         for t in (v.get("threads") or [])]},
                       "tension_set": list(v.get("threads") or []),
                       "defeated_claims": [str(x)[:60] for x in adjs]}
                st = LayerState("both", rounds=rounds, status="done")
            else:
                _acts = []
                for a in (v.get("actions") or []):
                    if not isinstance(a, dict):
                        continue
                    b = dict(a)
                    b.setdefault("owner", a.get("owner_role") or "")
                    b.setdefault("deadline", a.get("deadline_hint") or "")
                    b.setdefault("rollback", a.get("fallback") or "")
                    _acts.append(b)
                cl = {"decision": str(v.get("decision")
                                      or v.get("decidable_product") or v.get("manifest") or "")[:240],
                      "actions": _acts,
                      "not_do": list(v.get("not_do") or v.get("suspensions") or []),
                      "residual_risks": [(str(t.get("desc") or "") if isinstance(t, dict)
                                            else str(t))[:80]
                                         for t in (v.get("residual_risks")
                                                   or v.get("threads") or [])],
                      "provenance": list(v.get("provenance") or ["v1:packed"]),
                      "confidence": float(v.get("confidence") or qtri)}
                art = cl
                st = LayerState("all", rounds=rounds, status="done")
            out[entry] = LayerResult(entry=entry, artifacts=art, state=st,
                                     calls=0, tokens=0,
                                     provenance=["v1:packed"])
        return out

    def contract_report(self, packed: dict, gate: str = "warn") -> dict:
        gate = str(gate or "warn").lower()
        results = self.packed_to_layer_results(packed)
        violations: dict[str, list[str]] = {}
        for entry, r in results.items():
            try:
                validate_result(LAYER_CONTRACTS[entry], r)
            except ContractViolation as e:
                violations[entry] = [str(e)]
            except Exception as e:
                violations[entry] = ["%s: %s" % (type(e).__name__, e)]
        if gate == "raise" and violations:
            raise ContractViolation("; ".join(
                "%s: %s" % (k, "；".join(v)) for k, v in violations.items()))
        return {"gate": gate, "violations": violations,
                "checked": sorted(results), "ok": not violations}
