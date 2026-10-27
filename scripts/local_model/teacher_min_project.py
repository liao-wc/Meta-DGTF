# -*- coding: utf-8 -*-
"""把 full 教师输出投影为 min 训练数据（零 API）：同 user 匹配 min 行，抽取 3 决策字段。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_audit_tmp" / "teacher_data" / "self_check_train.jsonl"
MIN_TRAIN = ROOT / "llm_sft" / "dgtf_stage" / "self_check_min_train.jsonl"
MIN_VAL = ROOT / "llm_sft" / "dgtf_stage" / "self_check_min_val.jsonl"
OUT = ROOT / "_audit_tmp" / "teacher_min_data"
OUT.mkdir(parents=True, exist_ok=True)
FIELDS = ("suspicious_candidates", "ing_rephrased", "unsaid_is_escape")


def norm(s: str) -> str:
    return " ".join((s or "").split())


def main() -> int:
    min_rows = [json.loads(x) for x in MIN_TRAIN.read_text(encoding="utf-8").splitlines() if x.strip()]
    by_user = {}
    for r in min_rows:
        msgs = r.get("messages") or []
        u = next((m.get("content") for m in msgs if m.get("role") == "user"), "")
        by_user.setdefault(norm(u), r)
    teacher = [json.loads(x) for x in SRC.read_text(encoding="utf-8").splitlines() if x.strip()]
    out, miss = [], 0
    for t in teacher:
        u = next((m.get("content") for m in t["messages"] if m.get("role") == "user"), "")
        r = by_user.get(norm(u))
        if r is None:
            miss += 1
            continue
        try:
            gold = json.loads(t["messages"][-1]["content"])
        except Exception:
            miss += 1
            continue
        if not isinstance(gold, dict):
            miss += 1
            continue
        tgt = {k: gold.get(k) for k in FIELDS}
        msgs = r.get("messages") or []
        system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        out.append({"id": r.get("id"), "stage": "self_check",
                    "variant": "min", "question": r.get("question"),
                    "meta": r.get("meta"),
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user},
                                 {"role": "assistant",
                                  "content": json.dumps(tgt, ensure_ascii=False)}]})
    with (OUT / "self_check_min_train.jsonl").open("w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    shutil.copyfile(MIN_VAL, OUT / "self_check_min_val.jsonl")
    print("matched", len(out), "miss", miss, "min_rows", len(min_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
