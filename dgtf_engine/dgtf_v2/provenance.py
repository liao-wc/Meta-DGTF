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
def _engine_path():
    """真正在跑的引擎文件路径（缓存）。

    本模块由引擎 import ⇒ `__main__.__file__` 就是那个引擎脚本（最准）；
    取不到（pytest / 被别的主程序 import）⇒ 退回「引擎目录里的最高版本」。
    ★ 绝不写死版本号：写死会立刻过期，而且 `engine_file` 与 `engine_version`
      会各写各的 —— 实测出现过两个字段相差一个版本的自相矛盾，
      而这个模块存在的理由就是「质量能归因到版本」。
    """
    if "engine_path" in _CACHE:
        return _CACHE["engine_path"]
    p = None
    try:
        import __main__
        _mf = str(getattr(__main__, "__file__", "") or "")
        if "Meta-DGTF-V" in _mf:
            p = Path(_mf)
    except Exception:  # noqa: BLE001
        p = None
    if p is None:
        best = None
        for f in (ROOT / "dgtf_engine" / "dgtf_v2" / "engine").glob(
                "Meta-DGTF-V*.py"):
            m = re.search(r"V(\d+)\.(\d+)\.(\d+)", f.name)
            if not m:
                continue
            key = tuple(int(x) for x in m.groups())
            if best is None or key > best[0]:
                best = (key, f)
        p = best[1] if best else None
    _CACHE["engine_path"] = p
    return p


def engine_file() -> str:
    """当前引擎相对仓库根的路径；取不到时明确写 unknown（不编造）。"""
    p = _engine_path()
    if p is None:
        return "unknown"
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:  # noqa: BLE001
        return p.as_posix()


def engine_version() -> str:
    """引擎版本 —— 从**与 engine_file 同一个文件名**推导，不可能对不上。"""
    p = _engine_path()
    if p is None:
        return "unknown"
    m = re.search(r"V(\d+\.\d+\.\d+)", p.name)
    return ("V" + m.group(1)) if m else "unknown"
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
        "engine_file": engine_file(),
        "engine_version": engine_version(),
        "git_sha": git_short_sha(),
        "app_version": app_version(),
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "config_hash": config_hash(config),
    }
