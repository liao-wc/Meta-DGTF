# -*- coding: utf-8 -*-
"""源码自修复审批门：patch 落盘/路径校验/显式 approve/审计，不自动改源码。"""
from __future__ import annotations
import json, subprocess
from pathlib import Path

PATCH_DIR = "dgtf_memory/patches"
AUDIT = "dgtf_memory/agent_patch_audit.jsonl"
ALLOWED = ("元DGTF-", "dgtf_v2/", "dgtf_app/", "smoke_test.py",
           "fast_gate.py", "v1", "v2", "docs/")


def stage_patch(task_id: str, patch_text: str, files, path: str = PATCH_DIR) -> dict:
    pid = str(task_id or "").strip() or "unknown"
    d = Path(path); d.mkdir(parents=True, exist_ok=True)
    p = d / (pid + ".patch")
    p.write_text(str(patch_text or ""), encoding="utf-8")
    bad = []
    for f in (files or []):
        s = str(f)
        if not any(s.startswith(a) for a in ALLOWED):
            bad.append(s)
    rec = {"task_id": pid, "patch": str(p), "files": list(files or []),
           "path_ok": not bad, "bad_paths": bad, "status": "staged"}
    _audit(rec)
    return rec


def _audit(rec: dict) -> None:
    p = Path(AUDIT); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def check_patch(patch: str, repo: str = ".") -> dict:
    p = Path(patch)
    if not p.exists():
        return {"ok": False, "error": "patch_missing"}
    try:
        r = subprocess.run(["git", "apply", "--check", str(p)], cwd=repo,
                           capture_output=True, text=True, timeout=30)
        return {"ok": r.returncode == 0, "stderr": (r.stderr or "")[-800:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def apply_patch(patch: str, approve_token: str = "", repo: str = ".") -> dict:
    if str(approve_token or "") != "APPROVE":
        rec = {"patch": str(patch), "status": "refused",
               "why": "缺显式 APPROVE"}
        _audit(rec); return rec
    chk = check_patch(patch, repo)
    if not chk.get("ok"):
        rec = {"patch": str(patch), "status": "refused",
               "why": "git apply --check 失败", "check": chk}
        _audit(rec); return rec
    r = subprocess.run(["git", "apply", str(patch)], cwd=repo,
                       capture_output=True, text=True, timeout=30)
    rec = {"patch": str(patch), "status": "applied" if r.returncode == 0
           else "failed", "stderr": (r.stderr or "")[-800:]}
    _audit(rec); return rec


__all__ = ["stage_patch", "check_patch", "apply_patch", "PATCH_DIR", "AUDIT"]
