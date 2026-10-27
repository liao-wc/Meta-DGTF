# -*- coding: utf-8 -*-
"""路径1 v2：packed 候选重建 + 富特征 logistic SGD 分类器（无 sklearn）。

特征：desc 3-gram 哈希 + kind/attribute/position/yin/yang/source/anchored/amp
      + why 字段非空/关键词 + 位置/总数/entry。
训练：手动 logistic SGD（正类加权）；阈值在 train 20% 调，val 90 评估，
并给出 val 前 30 行（与 v9b 生成式 0.033/0.141 直接可比）。
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "llm_sft" / "dgtf_stage"
HASH_DIM = 20000
random.seed(42)
np.random.seed(42)


def load_rows(split: str) -> list[dict]:
    return [json.loads(x) for x in (DATA / f"self_check_min_{split}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def build_packed_index() -> dict:
    idx = {}
    for p in glob.glob(str(ROOT / "outputs" / "**" / "*.packed.json"), recursive=True):
        idx.setdefault(Path(p).name, p)
    return idx


def h(tok: str, mod: int) -> int:
    return int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16) % mod


def feats_for_cand(c: dict, i: int, n: int, entry: str) -> list[int]:
    desc = str(c.get("desc") or "")
    out: list[int] = []
    s = desc[:400]
    for k in (2, 3, 4):
        for j in range(0, max(0, len(s) - k + 1)):
            out.append(h(s[j:j + k], HASH_DIM))
    # 结构化字段（放到独立 offset，避免与 ngram 冲突）
    off = HASH_DIM
    for key in ("kind", "attribute", "position", "yin", "yang", "source"):
        out.append(off + h(key + "=" + str(c.get(key) or ""), 200)); off += 200
    out.append(off + (1 if c.get("attribute_anchored") else 0)); off += 4
    out.append(off + (1 if c.get("is_amp_candidate") else 0)); off += 4
    # why 字段非空/关键词
    for key in ("why_attribute", "why_position", "why_0", "why_1"):
        txt = str(c.get(key) or "")
        out.append(off + (1 if txt.strip() else 0)); off += 4
    for kw, w in (("补", 1), ("区分", 2), ("未复述", 3), ("此处未生", 4),
                  ("不可判定", 5), ("ing", 6), ("amp", 7), ("&", 8)):
        blob = desc + " " + " ".join(str(c.get(k) or "") for k in
                                     ("why_attribute", "why_position", "why_0", "why_1"))
        if kw in blob:
            out.append(off + w)
    off += 16
    pos = min(9, int(10 * i / max(1, n)))
    out.append(off + pos); off += 12
    out.append(off + (1 if entry == "0" else 0))
    return out


def load_examples(rows, packed_idx):
    ex = []
    stats = {"rows": 0, "missing": 0, "bad_idx": 0, "cands": 0}
    for ri, r in enumerate(rows):
        base = Path(str(r.get("packed") or "")).name
        p = packed_idx.get(base)
        if not p:
            stats["missing"] += 1
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            views = d.get("views") or {}
            entry = str(r.get("entry") or "0")
            v = views.get(entry)
            if not isinstance(v, dict):
                stats["missing"] += 1
                continue
            cands = v.get("candidates") or []
            gold = json.loads(r["messages"][-1]["content"])
            gidx = {int(x) for x in (gold.get("suspicious_candidates") or []) if str(x).isdigit()}
            if gidx and max(gidx) > len(cands):
                stats["bad_idx"] += 1
                continue
            stats["rows"] += 1
            stats["cands"] += len(cands)
            for i, c in enumerate(cands):
                ex.append((ri, feats_for_cand(c, i, len(cands), entry), 1 if (i + 1) in gidx else 0))
        except Exception:
            stats["missing"] += 1
    return ex, stats


def train_logistic(ex, dim, lr=0.15, epochs=12, pos_w=3.0):
    w = np.zeros(dim, dtype=np.float32)
    b = 0.0
    idx_pos = [i for i, (_, _, y) in enumerate(ex) if y]
    for ep in range(epochs):
        order = list(range(len(ex)))
        random.shuffle(order)
        for n, k in enumerate(order):
            ri, fs, y = ex[k]
            z = float(w[fs].sum()) + b
            p = 1.0 / (1.0 + math.exp(-max(-20, min(20, z))))
            g = (y - p) * (pos_w if y else 1.0)
            w[fs] += lr * g
            b += lr * g
        # 每轮在训练前半部分粗估
        if ep % 3 == 2:
            print("epoch", ep + 1, "done", flush=True)
    return w, b


def score(w, b, fs):
    z = float(w[fs].sum()) + b
    return 1.0 / (1.0 + math.exp(-max(-20, min(20, z))))


def eval_examples(ex, w, b, tau):
    by_row = {}
    for ri, fs, y in ex:
        by_row.setdefault(ri, []).append((score(w, b, fs), y))
    exact = f1s = p_sum = r_sum = 0.0
    for ri, items in by_row.items():
        pred = {i + 1 for i, (s, _) in enumerate(items) if s >= tau}
        gold = {i + 1 for i, (_, y) in enumerate(items) if y}
        exact += 1.0 if pred == gold else 0.0
        tp = len(pred & gold)
        prec = tp / len(pred) if pred else (1.0 if not gold else 0.0)
        rec = tp / len(gold) if gold else (1.0 if not pred else 0.0)
        f1s += (2 * prec * rec / (prec + rec) if prec + rec else 0.0)
        p_sum += prec
        r_sum += rec
    n = len(by_row)
    return {"n_rows": n, "set_acc": round(exact / max(1, n), 3),
            "set_f1": round(f1s / max(1, n), 3),
            "prec": round(p_sum / max(1, n), 3), "rec": round(r_sum / max(1, n), 3)}


def main() -> int:
    packed_idx = build_packed_index()
    tr_rows = load_rows("train")
    va_rows = load_rows("val")
    tr_ex, tr_stats = load_examples(tr_rows, packed_idx)
    va_ex, va_stats = load_examples(va_rows, packed_idx)
    print("train", tr_stats, "val", va_stats,
          "pos_rate", round(sum(y for _, _, y in tr_ex) / max(1, len(tr_ex)), 4))
    rids = sorted({ri for ri, _, _ in tr_ex})
    random.shuffle(rids)
    cut = int(len(rids) * 0.8)
    fit_ids = set(rids[:cut])
    fit = [e for e in tr_ex if e[0] in fit_ids]
    tune = [e for e in tr_ex if e[0] not in fit_ids]
    w, b = train_logistic(fit, HASH_DIM + 4096)
    best = None
    for tau in [i / 100 for i in range(5, 96, 5)]:
        m = eval_examples(tune, w, b, tau)
        if best is None or m["set_f1"] > best[1]["set_f1"]:
            best = (tau, m)
    print("tuned", best)
    # 全量重训
    w, b = train_logistic(tr_ex, HASH_DIM + 4096)
    res90 = eval_examples(va_ex, w, b, best[0])
    # val 前 30 行
    va30 = [e for e in va_ex if e[0] < 30]
    res30 = eval_examples(va30, w, b, best[0])
    print("VAL90", res90)
    print("VAL30", res30)
    out = {"tau": best[0], "tune": best[1], "val90": res90, "val30": res30,
           "train_stats": tr_stats, "val_stats": va_stats}
    (ROOT / "_audit_tmp" / "cand_classifier_v2_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
