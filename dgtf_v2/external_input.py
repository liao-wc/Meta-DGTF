# -*- coding: utf-8 -*-
"""统一外部输入：锚点文件 / 外部文件 / 联网检索隔离，锚点缺失时联网兜底。"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable


class ExternalInput:
    VERSION = "external_input/v1"

    def __init__(self, *, anchor_path=None, file_paths=None,
                 search: Callable | None = None):
        self.anchor_path = Path(anchor_path) if anchor_path else None
        self.file_paths = [Path(p) for p in (file_paths or [])]
        self.search = search
        self.anchors = []
        self.files = []
        self._loaded = False

    def load(self) -> dict:
        if self._loaded:
            return self.stats()
        self._loaded = True
        if self.anchor_path and self.anchor_path.is_file():
            try:
                d = json.loads(self.anchor_path.read_text(encoding="utf-8"))
                items = d.get("items") if isinstance(d, dict) else d
                self.anchors = [dict(x) for x in (items or []) if isinstance(x, dict)]
            except Exception:
                self.anchors = []
        for p in self.file_paths:
            if p.is_file():
                try:
                    self.files.append({"path": str(p), "text": p.read_text(encoding="utf-8")})
                except Exception:
                    pass
        return self.stats()

    def stats(self) -> dict:
        return {"version": self.VERSION, "anchors": len(self.anchors),
                "files": len(self.files), "web_available": callable(self.search),
                "channels": ["anchor", "file", "web"]}

    def resolve(self, query: str, *, role: str = "fact",
                limit: int = 6) -> dict:
        """按需取外部输入；anchor 优先，缺失则 web 兜底；file 独立通道。"""
        self.load()
        out = {"query": str(query or ""), "role": role,
               "anchor": [], "file": [], "web": [],
               "source": "", "fallback": False}
        if self.anchors:
            out["anchor"] = list(self.anchors)[:limit]
            out["source"] = "anchor"
        elif self.files:
            out["file"] = [f for f in self.files][:limit]
            out["source"] = "file"
        elif callable(self.search):
            try:
                hits = self.search(query) or []
                out["web"] = [dict(x) for x in hits][:limit]
                out["source"] = "web"
                out["fallback"] = True
            except Exception as e:
                out["error"] = "%s: %s" % (type(e).__name__, e)
        return out

    def as_prompt(self, query: str, *, role: str = "fact", limit: int = 3) -> str:
        d = self.resolve(query, role=role, limit=limit)
        bits = []
        if d["anchor"]:
            bits.append("[锚点证据] " + "；".join(
                str(x.get("claim") or x.get("text") or "")[:120]
                for x in d["anchor"][:limit]))
        if d["file"]:
            bits.append("[外部文件] " + "；".join(
                str(x.get("text") or "")[:120] for x in d["file"][:limit]))
        if d["web"]:
            bits.append("[联网兜底] " + "；".join(
                str(x.get("claim") or x.get("title") or "")[:120]
                for x in d["web"][:limit]))
        return "\n".join(bits)


__all__ = ["ExternalInput"]
