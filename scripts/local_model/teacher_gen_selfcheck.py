# -*- coding: utf-8 -*-
"""教师蒸馏数据生成：对 self_check_train 抽样行调用 DeepSeek 生成高质量 JSON 标签。

输出 _audit_tmp/teacher_data/self_check_train.jsonl（messages=[system,user,teacher]），
并把 self_check_val.jsonl 原样复制用于 val loss。
支持断点续跑；进度每 20 条打印。
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_audit_tmp" / "teacher_data"
OUT.mkdir(parents=True, exist_ok=True)
TRAIN_OUT = OUT / "self_check_train.jsonl"
N_TARGET = 400
API = "https://api.deepseek.com/chat/completions"


def load_key() -> str:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env["DGTF_API_KEY"]


def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def main() -> int:
    key = load_key()
    rows = [json.loads(x) for x in (ROOT / "llm_sft/dgtf_stage/self_check_train.jsonl")
            .read_text(encoding="utf-8").splitlines() if x.strip()]
    idx = list(range(len(rows)))
    random.Random(42).shuffle(idx)
    idx = idx[:min(N_TARGET, len(idx))]
    done_keys = set()
    if TRAIN_OUT.exists():
        for line in TRAIN_OUT.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    done_keys.add(str(json.loads(line).get("id")))
                except Exception:
                    pass
    print(f"[teacher] rows={len(rows)} target={len(idx)} done={len(done_keys)}", flush=True)
    n_new = 0
    t0 = time.time()
    for n, i in enumerate(idx):
        r = rows[i]
        rid = str(r.get("id") or i)
        if rid in done_keys:
            continue
        msgs = r.get("messages") or []
        system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        body = json.dumps({"model": "deepseek-chat",
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                           "temperature": 0.0, "max_tokens": 450,
                           "response_format": {"type": "json_object"}},
                          ensure_ascii=False).encode()
        last_err = None
        data = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(API, data=body, headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + key})
                with urllib.request.urlopen(req, timeout=120) as f:
                    d = json.loads(f.read().decode())
                txt = d["choices"][0]["message"]["content"]
                data = extract_json(txt)
                if isinstance(data, dict) and data:
                    break
            except Exception as e:  # noqa: BLE001
                last_err = str(e)[:120]
                time.sleep(1.5)
        if not isinstance(data, dict) or not data:
            print(f"[teacher] skip {rid} err={last_err}", flush=True)
            continue
        rec = {"id": rid, "stage": r.get("stage"), "variant": r.get("variant"),
               "question": r.get("question"), "meta": r.get("meta"),
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user},
                            {"role": "assistant",
                             "content": json.dumps(data, ensure_ascii=False)}]}
        with TRAIN_OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n_new += 1
        if n_new % 20 == 0:
            print(f"[teacher] new={n_new} total={len(done_keys)+n_new} "
                  f"elapsed={round(time.time()-t0)}s", flush=True)
    # 验证集原样复制
    import shutil
    shutil.copyfile(ROOT / "llm_sft/dgtf_stage/self_check_val.jsonl",
                    OUT / "self_check_val.jsonl")
    print(f"[teacher] DONE new={n_new} elapsed={round(time.time()-t0)}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
