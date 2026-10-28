# -*- coding: utf-8 -*-
"""App 系统整体状态检查（DSH 守护每轮运行）。

用法：
  python scripts/app_system_check.py
  python scripts/app_system_check.py --repair
  python scripts/app_system_check.py --json-out docs/system_audit_latest.json
"""
from __future__ import annotations
import argparse, json, os, re, shutil, socket, ssl, subprocess, sys, time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent.parent
TOKEN = (ROOT / "dgtf_memory" / ".access_token")
BASE = "https://127.0.0.1:8765"
LOCAL = "http://127.0.0.1:8772"
BGE = "http://127.0.0.1:8771"
CTX = ssl._create_unverified_context()


def _tok():
    try:
        return TOKEN.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _req(url, timeout=8, ctx=None, headers=None):
    try:
        with request.urlopen(request.Request(url, headers=headers or {}),
                             timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode("utf-8", "replace"), ""
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300], ""
    except Exception as e:
        return None, "", "%s: %s" % (type(e).__name__, e)


def _port_open(port):
    s = socket.socket(); s.settimeout(0.7)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        s.close()


def _size(path):
    try:
        if path.is_file():
            return path.stat().st_size
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    except Exception:
        return 0


def _repair_local():
    py = ROOT / "local_model" / "envs" / "dgtf_llm_env" / "Scripts" / "python.exe"
    svc = ROOT / "dgtf_local_llm" / "service.py"
    if not py.is_file() or not svc.is_file():
        return False, "local env/service missing"
    log = ROOT / "outputs" / "_lead_audit" / "local_llm_system_repair.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    try:
        f = log.open("a", encoding="utf-8", errors="replace")
        f.write(chr(10) + "[system-check] start " + time.strftime("%Y-%m-%d %H:%M:%S") + chr(10))
        f.flush()
        subprocess.Popen([str(py), str(svc), "--port", "8772"], cwd=str(ROOT),
                         env=env, stdout=f, stderr=subprocess.STDOUT,
                         creationflags=0x08000000 if os.name == "nt" else 0,
                         close_fds=False)
        return True, str(log)
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--json-out", default="")
    ap.add_argument("--wait", type=float, default=45.0)
    args = ap.parse_args()
    checks, fails, warns, repairs = [], [], [], []
    tok = _tok()

    def ck(name, ok, detail="", hard=True):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
        if not ok:
            (fails if hard else warns).append(name + (": " + str(detail)[:200] if detail else ""))

    # App HTTP
    code, body, err = _req(BASE + "/api/health?t=" + tok, ctx=CTX, headers={"X-DGTF-Token": tok})
    ck("App 8765 /api/health", code == 200, "code=%s %s" % (code, err))
    code2, body2, err2 = _req(BASE + "/api/status/sidebar?t=" + tok, ctx=CTX, headers={"X-DGTF-Token": tok})
    ck("App /api/status/sidebar", code2 == 200, "code=%s %s" % (code2, err2))
    code3, body3, err3 = _req(BASE + "/api/dsh/guard?t=" + tok, ctx=CTX, headers={"X-DGTF-Token": tok})
    try:
        g = json.loads(body3) if code3 == 200 else {}
    except Exception:
        g = {}
    ck("DSH guard", code3 == 200 and bool(g.get("enabled")),
       "code=%s enabled=%s" % (code3, g.get("enabled")))

    # local LLM + watchdog
    codeL, bodyL, errL = _req(LOCAL + "/health", timeout=4)
    ck("本地 LLM 8772 /health", codeL == 200, "code=%s %s" % (codeL, errL), hard=False)
    local_ready = False
    try:
        local_ready = json.loads(bodyL).get("status") == "ready"
    except Exception:
        pass
    ck("本地 LLM ready", local_ready, "status=%s" % (codeL if not bodyL else "unknown"), hard=False)
    try:
        sb = json.loads(body2) if code2 == 200 else {}
        wd = bool((sb.get("llm") or {}).get("watchdog_ok"))
    except Exception:
        wd = False
    ck("本地 LLM watchdog 状态", wd, "watchdog_ok=%s" % wd, hard=False)

    # BGE
    codeB, bodyB, errB = _req(BGE + "/health", timeout=4)
    ck("BGE 8771 /health", codeB == 200, "code=%s %s" % (codeB, errB), hard=False)

    # ports
    ck("App 8765 监听", _port_open(8765), "port closed")
    ck("本地 LLM 8772 监听", _port_open(8772), "port closed", hard=False)

    # disk / size
    try:
        du = shutil.disk_usage(str(ROOT))
        free_gb = du.free / (1024 ** 3)
    except Exception:
        free_gb = 0.0
    ck("磁盘剩余 >= 2GB", free_gb >= 2.0, "free=%.1fGB" % free_gb)
    ck("outputs 可写", os.access(ROOT / "outputs", os.W_OK), str(ROOT / "outputs"))
    ck("dgtf_memory 可写", os.access(ROOT / "dgtf_memory", os.W_OK), str(ROOT / "dgtf_memory"))

    # task/proposal from sidebar/API
    try:
        tcode, tbody, _ = _req(BASE + "/api/tasks?t=" + tok, ctx=CTX, headers={"X-DGTF-Token": tok})
        tasks = (json.loads(tbody).get("tasks") if tcode == 200 else []) or []
        running = [t for t in tasks if str(t.get("status")) in ("running", "queued")]
        ck("无 running/queued 任务", not running, "running=%d" % len(running), hard=False)
    except Exception:
        running = []
    try:
        pcode, pbody, _ = _req(BASE + "/api/dsh/proposals?t=" + tok, ctx=CTX, headers={"X-DGTF-Token": tok})
        props = (json.loads(pbody).get("proposals") if pcode == 200 else []) or []
        pending = [p for p in props if str(p.get("status")) == "pending"]
        ck("提案 pending <= 20", len(pending) <= 20, "pending=%d" % len(pending), hard=False)
    except Exception:
        pending = []

    # log sizes / temp
    for name in ("_app_out_8765.log", "_app_err_8765.log"):
        p = ROOT / name
        sz = _size(p)
        ck(name + " < 10MB", sz < 10 * 1024 * 1024, "size=%dB" % sz, hard=False)
    tmp = ROOT / "_audit_tmp"
    ck("_audit_tmp 大小 < 100MB", _size(tmp) < 100 * 1024 * 1024,
       "size=%dB" % _size(tmp), hard=False)

    # audit freshness
    now = time.time()
    for rel in ("docs/app_audit_latest.json", "docs/outputs_audit_latest.json",
                "docs/proposals_reassess_latest.json"):
        p = ROOT / rel
        age = now - p.stat().st_mtime if p.is_file() else 1e9
        ck(rel + " 新鲜(<2h)", age < 7200, "age=%.0fs" % age, hard=False)

    # static cache consistency
    idx = ROOT / "dgtf_app" / "static" / "index.html"
    versions = set()
    if idx.is_file():
        versions = set(re.findall(r"\?v=([0-9A-Za-z._-]+)", idx.read_text(encoding="utf-8", errors="replace")))
    ck("静态缓存版本一致", len(versions) == 1, ",".join(sorted(versions)))

    # auto repair
    if args.repair and not local_ready and not _port_open(8772):
        ok, info = _repair_local()
        repairs.append({"action": "start_local_llm", "ok": bool(ok), "detail": str(info)})
        deadline = time.time() + max(5.0, float(args.wait))
        while time.time() < deadline:
            time.sleep(3)
            c2, b2, _ = _req(LOCAL + "/health", timeout=3)
            try:
                if c2 == 200 and json.loads(b2).get("status") == "ready":
                    local_ready = True
                    break
            except Exception:
                pass
        ck("本地 LLM 自动修复", local_ready, "repair=%s" % info)

    out = {"ok": not fails, "ts": time.time(), "root": str(ROOT),
           "checks": checks, "fails": fails, "warnings": warns,
           "repairs": repairs, "free_gb": round(free_gb, 1),
           "outputs_size_mb": round(_size(ROOT / "outputs") / 1024 / 1024, 1),
           "memory_size_mb": round(_size(ROOT / "dgtf_memory") / 1024 / 1024, 1)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json_out:
        op = ROOT / args.json_out
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("JSON_OUT", op)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
