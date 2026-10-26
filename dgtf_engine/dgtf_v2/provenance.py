# -*- coding: utf-8 -*-
"""产物溯源（Round 132）：engine/app 版本、git SHA、配置指纹、问题指纹。

历史 359 个 packed 中 0 个带版本指纹 → 质量问题无法归因。新产物统一写入
``packed["provenance"]`` 与 ``packed["question_hash"]``。
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE_FILE = "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py"
_CACHE: dict = {}


def git_short_sha() -> str:
    """当前仓库 HEAD 短 SHA；git 不可用/非仓库时用 DGTF_GIT_SHA，否则 unknown。"""
    if "git_sha" in _CACHE:
        return _CACHE["git_sha"]
    sha = ""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(ROOT), capture_output=True, text=True,
                             timeout=3, encoding="utf-8", errors="replace")
        sha = (out.stdout or "").strip()
    except Exception:  # noqa: BLE001
        sha = ""
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha or ""):
        sha = str(os.environ.get("DGTF_GIT_SHA") or "unknown").strip()[:40] or "unknown"
    _CACHE["git_sha"] = sha
    return sha


def app_version() -> str:
    if "app_version" in _CACHE:
        return _CACHE["app_version"]
    ver = "unknown"
    try:
        t = (ROOT / "dgtf_app" / "server.py").read_text(encoding="utf-8", errors="replace")
        m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', t)
        if m:
            ver = m.group(1)
    except Exception:  # noqa: BLE001
        pass
    _CACHE["app_version"] = ver
    return ver


def config_hash(config) -> str:
    try:
        raw = json.dumps(config or {}, sort_keys=True, ensure_ascii=False,
                         default=str)
    except Exception:  # noqa: BLE001
        raw = "{}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def question_fingerprint(question: str) -> str:
    """问题指纹：去空白/标点、小写后的 sha256 前 16 位（去重/缓存/保留策略用）。"""
    q = re.sub(r"\s+", "", str(question or "")).lower()
    q = re.sub(r"[？?。.!！,，、;；:：\"\'“”‘’()（）\[\]【】]", "", q)
    return hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]


def artifact_provenance(config=None) -> dict:
    """一次产物该带的版本指纹（轻量、可缓存）。"""
    return {
        "schema": 1,
        "engine_file": ENGINE_FILE,
        "engine_version": "V2.2.3",
        "git_sha": git_short_sha(),
        "app_version": app_version(),
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "config_hash": config_hash(config),
    }
