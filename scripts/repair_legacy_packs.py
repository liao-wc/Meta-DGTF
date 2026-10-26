# -*- coding: utf-8 -*-
"""历史产物一致性修复（Round 130，授权处理审计 P0）。

背景：7 条历史 pack 的 answer_quality / answer_ready 自相矛盾；其中 2+2 题被网页梗
答案污染且 verified。策略（用户已授权改写历史包）：
  1. 2+2 类纯算术题：用确定性 `_arithmetic_answer` 重算 fact_card（2+2=4），
     置 verified + ready，并在 md 追加修复说明；
  2. verified 但 !ready：有非空 fact_card 答案 ⇒ ready=True（verdict 为 verified 应可用）；
     无答案 ⇒ answer_quality=unverified / ready=False（verified 不能没有答案）；
  3. unverified 但 ready：ready=False。
  所有被改文件先备份到 outputs/_repair_backup_20261027/（gitignored），原状可追溯。
用法：
  python scripts/repair_legacy_packs.py            # dry-run
  python scripts/repair_legacy_packs.py --apply
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))
from dgtf_v2.evidence import EvidenceReport  # noqa: E402
from dgtf_v2.fact_flow import build_fact_card  # noqa: E402

BACKUP = ROOT / "outputs" / "_repair_backup_20261027"
NOTE = "【Round 130 一致性修复】"


def _is_contradiction(aq, ready) -> bool:
    return ((aq == "verified" and ready is False)
            or (aq == "unverified" and ready is True))


def _set_ready(pack, ready: bool) -> None:
    q = pack.setdefault("quality", {})
    q["answer_ready"] = bool(ready)
    for key in ("answer_summary",):
        if isinstance(q.get(key), dict):
            q[key]["answer_ready"] = bool(ready)
    if isinstance(pack.get(key if False else ""), dict):  # noqa: E712
        pass
    if isinstance(pack.get("answer_summary"), dict):
        pack["answer_summary"]["answer_ready"] = bool(ready)


def repair(pack: dict) -> tuple[bool, str]:
    q = pack.setdefault("quality", {})
    aq = q.get("answer_quality")
    ready = q.get("answer_ready")
    # 已带人工理由的 verified+!ready 属合法状态（展示/截断门），不重复修复
    if (_is_contradiction(aq, ready)
            and str(q.get("answer_ready_reason") or q.get("repair_note") or "").strip()):
        return False, ""
    asum = q.get("answer_summary") or pack.get("answer_summary") or {}
    qt = str(asum.get("question_type") or "unknown")
    card = (pack.get("decision_trace") or {}).get("fact_card") or {}
    # ★ [Round 133] 截断门：体力耗尽不应 ready
    if "体力耗尽" in str(asum.get("stop_reason") or "") and ready is True:
        _set_ready(pack, False)
        q["repair_note"] = NOTE + "体力耗尽（预算截断）⇒ ready=False"
        return True, "truncated_ready_false"
    # ★ [Round 133] 展示门：事实题 verified 但无展示答案 ⇒ ready=False
    if (qt == "fact" and aq == "verified"
            and not str(card.get("answer_display") or "").strip()):
        _set_ready(pack, False)
        q["repair_note"] = NOTE + "事实 verified 但无展示答案 ⇒ ready=False"
        return True, "fact_verified_no_display_ready_false"
    if not _is_contradiction(aq, ready):
        return False, ""
    question = str(pack.get("question") or "")
    dt = pack.setdefault("decision_trace", {})
    card = dt.get("fact_card") or {}
    if aq == "verified" and ready is False:
        # ① 纯算术题：确定性重算
        ar = build_fact_card(question, EvidenceReport(question=question, queries=[],
                                                      searches=0, items=[]))
        if ar.status == "answered" and "=" in str(ar.answer):
            card = ar.to_dict()
            dt["fact_card"] = card
            q["answer_quality"] = "verified"
            _set_ready(pack, True)
            q["raw_answer_ready"] = True
            if isinstance(pack.get("answer_summary"), dict):
                pack["answer_summary"]["answer"] = str(ar.answer)[:2000]
            q["repair_note"] = NOTE + "纯算术题按确定性结果修正为 %s" % ar.answer
            return True, "arithmetic:%s" % ar.answer
        # ② 有答案 ⇒ ready=True；无答案 ⇒ 降级 unverified
        ans = str(card.get("answer_display") or card.get("answer") or "").strip()
        if card.get("status") == "answered" and ans:
            _set_ready(pack, True)
            q["repair_note"] = NOTE + "verified 且有非空答案 ⇒ ready=True"
            return True, "ready_true_with_answer"
        q["answer_quality"] = "unverified"
        _set_ready(pack, False)
        q["repair_note"] = NOTE + "verified 但无答案 ⇒ 降级 unverified/ready=False"
        return True, "downgrade_verified_no_answer"
    if aq == "unverified" and ready is True:
        _set_ready(pack, False)
        q["repair_note"] = NOTE + "unverified ⇒ ready=False"
        return True, "ready_false_unverified"
    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    changed = []
    for f in sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json"))):
        try:
            pack = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        ok, why = repair(pack)
        if not ok:
            continue
        changed.append((os.path.basename(f), why))
        if args.apply:
            BACKUP.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, BACKUP / os.path.basename(f))
            Path(f).write_text(json.dumps(pack, ensure_ascii=False),
                               encoding="utf-8")
            md = Path(f[:-len(".packed.json")] + ".md")
            if md.exists():
                try:
                    md.write_text(md.read_text(encoding="utf-8")
                                  + "\n\n" + NOTE + " 该历史产物已按审计修复（详见 pack.repair_note；"
                                  + "原文件备份于 outputs/_repair_backup_20261027/）。\n",
                                  encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass
    print("changed:", len(changed))
    for b, w in changed:
        print(" ", b, "->", w)
    if not args.apply:
        print("DRY-RUN（未写盘；--apply 执行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
