# -*- coding: utf-8 -*-
"""参考记忆：可持久化正文特征，但绝不把原文注入 prompt / 照搬。"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def digest(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:24]


def terms(text: str, limit: int = 12) -> list:
    out = []
    for t in str(text or "").split():
        t = t.strip()
        if len(t) >= 2 and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


class ReferenceMemory:
    """只存 digest/terms/结构读数；read_for_prompt 永不返回正文。"""

    VERSION = "reference_memory/v1"

    def __init__(self, path=None, enabled=True):
        self.path = Path(path) if path else None
        self.enabled = bool(enabled)

    def record(self, *, run_id, layer, kind, text, metrics=None):
        text = str(text or "").strip()
        row = {"run_id": str(run_id or ""), "layer": str(layer or ""),
               "kind": str(kind or "manifest"), "digest": digest(text),
               "terms": terms(text),
               "term_hashes": [digest(x)[:12] for x in terms(text)],
               "length": len(text),
               "metrics": dict(metrics or {}), "no_copy": True,
               "contains_content": False}
        if self.enabled and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def load(self):
        if not (self.enabled and self.path and self.path.exists()):
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def read_for_prompt(self):
        """给 EML/调度看的参考：只有 digest/terms/metrics，无正文。"""
        return [{"run_id": r.get("run_id"), "layer": r.get("layer"),
                 "kind": r.get("kind"), "digest": r.get("digest"),
                 "term_hashes": list(r.get("term_hashes") or []),
                 "metrics": dict(r.get("metrics") or {}),
                 "no_copy": True} for r in self.load()]

    def prompt_hint(self, limit: int = 5) -> str:
        """按需注入 prompt 的参考特征：只给短关键词，不给正文。"""
        rows = self.read_for_prompt()
        terms = []
        for r in rows:
            for t in (r.get("term_hashes") or []):
                if t not in terms:
                    terms.append(t)
            if len(terms) >= int(limit):
                break
        if not terms:
            return ""
        return "参考记忆特征（哈希）: " + "、".join(terms[:int(limit)])

    def stats(self):
        rows = self.load()
        return {"version": self.VERSION, "n": len(rows),
                "layers": sorted({r.get("layer") for r in rows if r.get("layer")}),
                "contains_content": False, "no_copy": True}


__all__ = ["ReferenceMemory", "digest", "terms"]
