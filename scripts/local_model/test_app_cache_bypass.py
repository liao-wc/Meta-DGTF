# -*- coding: utf-8 -*-
"""App 缓存/去重绕过判据（Round 125，零成本）。

L1：`_no_cache_requested` 识别 no_cache / force_rerun。
L2：有匹配 packed 时 `_find_cached_pack` 命中；带 no_cache/force_rerun ⇒ None。
L3：同题 running 任务 `_find_running_duplicate` 命中；带 no_cache ⇒ None。
L4：app_fast_e2e.py 支持 DGTF_E2E_NO_CACHE 并回显 cache_hit。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def _load_server():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "dgtf_engine"))
    sys.path.insert(0, str(ROOT / "dgtf_app"))
    spec = importlib.util.spec_from_file_location(
        "app_server_cache_test", str(ROOT / "dgtf_app" / "server.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app_server_cache_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    srv = _load_server()
    ck("L1 no_cache/force_rerun 识别",
       srv._no_cache_requested({"no_cache": True})
       and srv._no_cache_requested({"force_rerun": True})
       and not srv._no_cache_requested({})
       and not srv._no_cache_requested({"use_cache": False}))

    tmp = Path(tempfile.mkdtemp(prefix="app_cache_test_"))
    q = "测试缓存题：1+1 等于几？"
    pack = tmp / "20260101_000000_testq.packed.json"
    pack.write_text(json.dumps({
        "id": "p1", "question": q,
        "quality": {"answer_ready": True, "answer_quality": "verified",
                    "answer_summary": {"question_type": "fact"}},
        "api_usage": {"web_enabled": False},
        "dispatch": {},
    }, ensure_ascii=False), encoding="utf-8")
    old_dir = srv.oi.OUTPUTS_DIR
    try:
        srv.oi.OUTPUTS_DIR = tmp
        base_opts = {"web": "off"}
        hit = srv._find_cached_pack(q, dict(base_opts))
        ck("L2 默认命中缓存", bool(hit), hit)
        ck("L2 no_cache 不命中",
           srv._find_cached_pack(q, {**base_opts, "no_cache": True}) is None)
        ck("L2 force_rerun 不命中",
           srv._find_cached_pack(q, {**base_opts, "force_rerun": True}) is None)
    finally:
        srv.oi.OUTPUTS_DIR = old_dir

    old_tasks = srv.runner.list_tasks
    try:
        srv.runner.list_tasks = lambda: [{"status": "running", "question": q,
                                          "opts": {"web": "off"}}]
        want = srv._task_sig({"web": "off"}, "")
        ck("L3 默认去重命中",
           srv._find_running_duplicate(q, {"web": "off"}, "") is not None,
           want)
        ck("L3 no_cache 不命中去重",
           srv._find_running_duplicate(q, {"web": "off", "no_cache": True},
                                       "") is None)
    finally:
        srv.runner.list_tasks = old_tasks

    e2e = (ROOT / "scripts" / "app_fast_e2e.py").read_text(encoding="utf-8")
    ck("L4 e2e 支持 DGTF_E2E_NO_CACHE 且回显 cache_hit",
       "DGTF_E2E_NO_CACHE" in e2e and 'result["cache_hit"]' in e2e)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
