# -*- coding: utf-8 -*-
"""[V2.2.41] 语义缓存命中标定：verified 产物 + 近重复问法（BGE 余弦）。

零 API：本地链路 + 已存在 verified web-off packed（为什么在高原上煮饭更容易夹生？）。
证据 docs/semantic_cache_hit_20261029.json
"""
from __future__ import annotations

import glob
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUD = ROOT / "outputs" / "_lead_audit"
AUD.mkdir(parents=True, exist_ok=True)
BASE = "为什么在高原上煮饭更容易夹生？"
NEAR = "为什么高原上煮饭更容易夹生？"
OVER = {
    "api.base_url": "http://127.0.0.1:8773/v1",
    "api.key": "local-shim",
    "api.default_model": "local",
    "api.reasoner_model": "local",
    "web_search.enabled": False,
    "output.answer_gates.enabled": True,
    "output.answer_gates.block": False,
    "output.save_dir": "outputs/_e2e_local/semantic_cache",
}


def _req(url, token, data=None, timeout=60):
    h = {"Content-Type": "application/json; charset=utf-8",
         "Cookie": "dgtf_token=" + str(token)}
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=h,
                               method="POST" if body is not None else "GET")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))


def _kill(pid):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        pass


def _free_port(prefer=8829):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", prefer))
        return prefer
    except OSError:
        return 0
    finally:
        s.close()


def main():
    port = _free_port()
    token = "sem_%d" % os.getpid()
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "DGTF_ACCESS_TOKEN": token,
                "DGTF_DAOSHENG_BALANCE_CNY": "50.0"})
    cmd = [sys.executable, "-u", str(ROOT / "dgtf_app" / "server.py"),
           "--port", str(port), "--http", "--no-agent-daemon",
           "--local-chain-watchdog", "off", "--token", token]
    proc = None
    rows = []
    try:
        with (AUD / "sem_cache.out.log").open("w", encoding="utf-8") as fo, \
                (AUD / "sem_cache.err.log").open("w", encoding="utf-8") as fe:
            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo, stderr=fe, env=env)
        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                s, _ = _req(base + "/api/health?t=" + token, token, timeout=3)
                if s == 200:
                    ready = True
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1.0)
        if not ready:
            raise SystemExit("server not ready")
        for tag, q in (("exact", BASE), ("semantic", NEAR)):
            body = {"question": q, "mode": "auto",
                    "opts": {"mock": False, "timeout_s": 600,
                             "route": "0", "rounds": "0:1",
                             "web": "off", "parallel": "serial",
                             "overrides": OVER}}
            t0 = time.time()
            s1, r1 = _req(base + "/api/tasks", token, body, timeout=120)
            rows.append({"tag": tag, "question": q,
                         "status": s1,
                         "cache_hit": bool((r1 or {}).get("cache_hit")),
                         "semantic_cache": bool((r1 or {}).get("semantic_cache")),
                         "cache_similarity": (r1 or {}).get("cache_similarity"),
                         "cached_from": (r1 or {}).get("cached_from"),
                         "id": (r1 or {}).get("id"),
                         "wall_s": round(time.time() - t0, 2)})
            print("[sem]", json.dumps(rows[-1], ensure_ascii=False)[:400], flush=True)
        out = {"schema": "metadgtf.semantic_cache_calibration.v1",
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "base_question": BASE, "near_question": NEAR,
               "embed": {"model": "bge-small-zh-v1.5", "port": 8771},
               "cache_pack": "outputs/20261025_143654_为什么在高原上煮饭更容易夹生.packed.json",
               "rows": rows,
               "note": ("exact 复用 verified 产物；semantic 用近重复问法命中同一产物"
                        "（证据为本次本地链路零 API 标定）")}
        (ROOT / "docs" / "semantic_cache_hit_20261029.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("evidence -> docs/semantic_cache_hit_20261029.json")
        bad = [x for x in rows if not x.get("cache_hit")]
        raise SystemExit(1 if bad else 0)
    finally:
        if proc is not None and proc.poll() is None:
            _kill(proc.pid)


if __name__ == "__main__":
    main()
