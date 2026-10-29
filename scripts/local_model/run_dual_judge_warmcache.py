# -*- coding: utf-8 -*-
"""[V2.2.29] dual_judge 热缓存验证：同配置连续两跑（cache 模式），比较 tokens/calls。

成本有界：每跑 max_tokens=150000，route=0/rounds=0:1/fast/web off；预计总 <= ¥0.15。
证据：docs/dual_judge_warmcache_20261029.json
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVE = ROOT / "outputs" / "_e2e_local" / "dj_warm"
SAVE.mkdir(parents=True, exist_ok=True)
CFG = ROOT / "outputs" / "_e2e_local" / "dj_warm_config.yaml"
ENGINE = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.28.py"
QUESTION = "成年人正常心率是多少次每分钟？"
CACHE = ROOT / "dgtf_memory" / "dual_judge_cache.json"


def _cache_entries():
    try:
        d = json.loads(CACHE.read_text(encoding="utf-8"))
        return len(d.get("entries") or d or {})
    except Exception:  # noqa: BLE001
        return 0


def run_once(tag):
    before = set(glob.glob(str(SAVE / "*.packed.json")))
    cmd = [sys.executable, "-u", str(ENGINE), QUESTION,
           "--config", str(CFG), "--route", "0", "--rounds", "0:1",
           "--parallel", "B", "--thinking", "off", "--mode", "fast",
           "--web", "off", "--dual-judge-mode", "cache",
           "--max-tokens", "150000", "--quiet"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    wall = round(time.time() - t0, 1)
    new = [p for p in glob.glob(str(SAVE / "*.packed.json")) if p not in before]
    d = {}
    if new:
        d = json.loads(Path(sorted(new, key=os.path.getmtime)[-1])
                       .read_text(encoding="utf-8", errors="replace"))
    return {"tag": tag, "rc": r.returncode, "wall_s": wall,
            "calls": d.get("llm_calls"), "tokens": d.get("llm_tokens"),
            "quality": (d.get("quality") or {}).get("answer_quality"),
            "cache_entries": _cache_entries(),
            "packed": Path(new[0]).name if new else ""}


def main():
    src = (ROOT / "dgtf_config.yaml").read_text(encoding="utf-8")
    old = '  save_dir: "outputs"'
    assert src.count(old) == 1
    CFG.write_text(src.replace(
        old, '  save_dir: "outputs/_e2e_local/dj_warm"'), encoding="utf-8")
    first = run_once("run1-cold")
    second = run_once("run2-warm")
    delta = {"tokens": (second.get("tokens") or 0) - (first.get("tokens") or 0),
             "calls": (second.get("calls") or 0) - (first.get("calls") or 0)}
    out = {"schema": "metadgtf.dual_judge_warmcache.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": QUESTION, "engine": ENGINE.name,
           "fixed": {"route": "0", "rounds": "0:1", "fast": True,
                     "web": "off", "dual_judge_mode": "cache",
                     "max_tokens": 150000},
           "runs": [first, second], "delta": delta,
           "note": "负值=第二跑（热缓存）更省；单题单次，受 judge cache 命中影响"}
    (ROOT / "docs" / "dual_judge_warmcache_20261029.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in (first, second):
        print(json.dumps(r, ensure_ascii=False)[:400])
    print("delta:", json.dumps(delta, ensure_ascii=False))
    print("evidence -> docs/dual_judge_warmcache_20261029.json")


if __name__ == "__main__":
    main()
