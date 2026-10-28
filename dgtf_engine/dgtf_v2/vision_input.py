# -*- coding: utf-8 -*-
"""Vision 输入：本地图片/URL -> OpenAI 兼容 image_url block；跑前描述一次。"""
from __future__ import annotations
import base64
from pathlib import Path

_MAGIC = ((b"\x89PNG", "image/png"), (b"\xff\xd8", "image/jpeg"),
          (b"GIF8", "image/gif"), (b"RIFF", "image/webp"))
MAX_BYTES = 32 * 1024 * 1024


def _mime(path: Path) -> str:
    try:
        head = path.read_bytes()[:12]
    except Exception:
        return "image/jpeg"
    for sig, m in _MAGIC:
        if head.startswith(sig):
            return m
    return "image/jpeg"


def blocks(images, detail: str = "auto") -> list:
    out = []
    for raw in (images or []):
        s = str(raw or "").strip()
        if not s:
            continue
        if s.startswith("file-api-"):
            out.append({"type": "file", "file_id": s})
            continue
        if s.startswith(("http://", "https://", "data:image/")):
            out.append({"type": "image_url",
                        "image_url": {"url": s, "detail": detail}})
            continue
        p = Path(s)
        try:
            if not p.is_file() or p.stat().st_size > MAX_BYTES:
                continue
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            out.append({"type": "image_url",
                        "image_url": {"url": "data:%s;base64,%s"
                                      % (_mime(p), b64), "detail": detail}})
        except Exception:
            continue
    return out


def describe(llm, images, question: str, *, model=None, max_tokens=1200) -> str:
    bs = blocks(images)
    if not bs or llm is None:
        return ""
    system = ("你是元DGTF的视觉预检器。只陈述图片中可见的事实："
              "文字、表格、日期、界面状态、图表读数。"
              "不确定就写不确定；禁止编造；输出中文短报告。")
    user = ("结合问题：%s\n\n请给出图片可见证据，"
            "按「1) 关键文字 2) 日期/数字 3) 图表/界面 4) 不确定处」输出。"
            % str(question or ""))
    try:
        return str(llm.call(system, user, 0.2, max_tokens,
                            model=model, images=bs,
                            stage="vision_input") or "")
    except Exception:
        return ""


__all__ = ["blocks", "describe"]
