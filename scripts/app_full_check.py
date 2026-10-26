# -*- coding: utf-8 -*-
"""DSH 守护用的 App 全方位只读检查。

用法：
  python scripts/app_full_check.py
  python scripts/app_full_check.py --json-out docs/app_audit_latest.json
"""
from __future__ import annotations
import argparse, json, os, re, ssl, subprocess, sys, time
from pathlib import Path
from urllib import request, error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "dgtf_memory" / ".access_token"
BASE = "https://127.0.0.1:8765"
LOCAL = "http://127.0.0.1:8772"
CTX = ssl._create_unverified_context()


def _req(url: str, headers=None, timeout=20):
    t = time.time()
    try:
        with request.urlopen(request.Request(url, headers=headers or {}), timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace"), (time.time() - t) * 1000
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300], (time.time() - t) * 1000
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e), (time.time() - t) * 1000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    tok = TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.is_file() else ""
    checks = []
    warns = []
    fails = []

    def ck(name, ok, detail="", hard=True):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            (fails if hard else warns).append(name + (": " + str(detail)[:180] if detail else ""))

    # 1 auth
    code, body, ms = _req(BASE + "/api/health")
    ck("无 token /api/health 被拒绝", code == 401, "code=%s" % code)
    # 2 endpoints
    paths = ["/api/health", "/api/config", "/api/dashboard", "/api/tasks",
             "/api/agent/knowledge", "/api/agent/hot-topics",
             "/api/status/activity", "/api/status/sidebar", "/api/schedule/v2", "/api/schedule/v2/online",
             "/api/schedule/v2/pareto", "/api/schedule/policy",
             "/api/dsh/guard", "/api/dsh/proposals"]
    payloads = {}
    for path in paths:
        url = BASE + path + ("&t=" if "?" in path else "?t=") + tok
        code, body, ms = _req(url, {"X-DGTF-Token": tok})
        ok = code == 200
        ck("GET " + path, ok, "code=%s %.0fms" % (code, ms))
        if ok:
            try:
                payloads[path] = json.loads(body)
            except Exception:
                ck("JSON " + path, False, "invalid json")
    # 3 static cache versions
    idx = ROOT / "dgtf_app" / "static" / "index.html"
    vers = set()
    if idx.is_file():
        _txt = idx.read_text(encoding="utf-8", errors="replace")
        vers = set(re.findall(r"\?v=([0-9A-Za-z._-]+)", _txt))
    ck("静态缓存版本一致", len(vers) == 1, ",".join(sorted(vers)))
    for u in ("/static/index.html", "/static/app.js", "/static/style.css", "/static/desktop-icon-64.png"):
        code, body, ms = _req(BASE + u + "?t=" + tok, {"X-DGTF-Token": tok})
        ck("GET " + u, code == 200, "code=%s" % code)
    # 4 traversal
    for u in ("/api/agent/knowledge/pdf?name=..%2FREADME.md",
              "/api/agent/knowledge/pdf?name=..%2Fdgtf_memory%2F.access_token",
              "/api/archive/..%2FREADME.md"):
        _sep = "&t=" if "?" in u else "?t="
        code, body, ms = _req(BASE + u + _sep + tok, {"X-DGTF-Token": tok})
        ck("路径穿越拦截 " + u.split("?")[0], code in (400, 403, 404), "code=%s" % code)
    # 5 task/proposal summary (warnings only)
    tasks = (payloads.get("/api/tasks") or {}).get("tasks") or []
    running = [t for t in tasks if str(t.get("status")) in ("running", "queued")]
    ck("无 running/queued 任务", not running, "running=%d" % len(running), hard=False)
    props = (payloads.get("/api/dsh/proposals") or {}).get("proposals") or []
    pending = [p for p in props if str(p.get("status")) in ("pending", "high", "confirmed")]
    ck("无 pending 提案", not pending, "pending=%d" % len(pending), hard=False)
    # 6 local service
    code, body, ms = _req(LOCAL + "/health", timeout=3)
    ck("本地模型服务 /health", code == 200, "code=%s" % code, hard=False)
    if code == 200:
        try:
            d = json.loads(body)
            ck("本地模型服务 ready", str(d.get("status")) == "ready", str(d.get("status")), hard=False)
        except Exception:
            ck("本地模型服务 JSON", False, "invalid json")
    # 7 guard prompt wiring (static, no task dispatch)
    srv_txt = (ROOT / "dgtf_app" / "server.py").read_text(encoding="utf-8", errors="replace")
    ck("守护提示包含 App 全方位检查", "【App 全方位检查】" in srv_txt
       and "scripts/app_full_check.py" in srv_txt)
    ck("App 检查脚本存在", (ROOT / "scripts" / "app_full_check.py").is_file())
    ck("守护提示包含全产物库分析", "【全产物库分析】" in srv_txt
       and "scripts/outputs_library_audit.py" in srv_txt)
    ck("产物库审计脚本存在", (ROOT / "scripts" / "outputs_library_audit.py").is_file())
    ck("人工确认提案脚本存在", (ROOT / "scripts" / "propose_outputs_confirmations.py").is_file())
    ck("提案详细说明脚本存在", (ROOT / "scripts" / "enrich_audit_proposals.py").is_file())
    ck("提案复评脚本存在", (ROOT / "scripts" / "reassess_audit_proposals.py").is_file())
    ck("通用人工确认提案脚本存在", (ROOT / "scripts" / "create_proposal.py").is_file())
    ck("App 系统整体检查脚本存在", (ROOT / "scripts" / "app_system_check.py").is_file())
    ck("守护提示要求系统整体检查", "app_system_check.py" in srv_txt)
    ck("守护提示要求每轮复评提案", "reassess_audit_proposals.py" in srv_txt)
    ck("守护提示要求人工确认落提案", "propose_outputs_confirmations.py" in srv_txt
       and "修复提案" in srv_txt)
    ck("安全文件操作脚本存在", (ROOT / "scripts" / "safe_file_ops.py").is_file())
    ck("文件完整性检查脚本存在", (ROOT / "scripts" / "file_integrity_check.py").is_file())
    ck("守卫完成回执脚本存在", (ROOT / "scripts" / "guard_receipt.py").is_file())
    ck("守护提示要求完成回执", "guard_receipt.py" in srv_txt and "【完成回执】" in srv_txt)
    ck("守护提示要求安全文件操作", "safe_file_ops.py" in srv_txt and "file_integrity_check.py" in srv_txt)
    ck("守护提示包含热点抓取", "【本轮热门话题实时抓取】" in srv_txt)
    ck("守护提示包含技术知识学习", "【本轮技术知识学习】" in srv_txt)
    ck("守护提示包含真跑轮换", "【本轮真跑轮换】" in srv_txt)
    ck("守护提示包含报告留存", "【巡检报告留存】" in srv_txt and "check_patrol_report.py" in srv_txt)
    ck("守护提示包含 App 版本同步", "【App 版本同步】" in srv_txt and "app_release.py" in srv_txt)
    ck("App 发布工具存在", (ROOT / "scripts" / "app_release.py").is_file()
       and (ROOT / "scripts" / "app_version_check.py").is_file())
    try:
        _ir = subprocess.run([sys.executable, str(ROOT / "scripts" / "file_integrity_check.py")],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=90)
        ck("关键文件完整性", _ir.returncode == 0, (_ir.stderr or _ir.stdout or "")[-600:])
    except Exception as _exc:
        ck("关键文件完整性", False, "%s: %s" % (type(_exc).__name__, _exc))
    try:
        _vr = subprocess.run([sys.executable, str(ROOT / "scripts" / "app_version_check.py")],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        ck("App 版本一致性", _vr.returncode == 0, (_vr.stderr or _vr.stdout or "")[-600:])
    except Exception as _exc:
        ck("App 版本一致性", False, "%s: %s" % (type(_exc).__name__, _exc))
    if os.environ.get("DGTF_UI_TEST", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            _ui = subprocess.run([sys.executable, str(ROOT / "scripts" / "ui_automation_check.py"),
                                  "--json-out", "docs/ui_audit_latest.json"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=120)
            ck("UI 自动化回归", _ui.returncode == 0, (_ui.stderr or _ui.stdout or "")[-800:])
        except Exception as _exc:
            ck("UI 自动化回归", False, "%s: %s" % (type(_exc).__name__, _exc))
    # 8 logs
    for name in ("_app_err_8765.log", "_app_out_8765.log"):
        p = ROOT / name
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            ck(name + " 无 Traceback", "Traceback" not in txt, "traceback found")
    # 8 V2 auto-apply dry-run (only if endpoint exists)
    try:
        body = json.dumps({"prefer": "balanced", "dry_run": True}).encode()
        req = request.Request(BASE + "/api/schedule/v2/auto-apply?t=" + tok, data=body,
                              headers={"Content-Type": "application/json", "X-DGTF-Token": tok},
                              method="POST")
        with request.urlopen(req, timeout=30, context=CTX) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        _v2_ok = bool(d.get("ok")) or bool(d.get("frozen"))
        ck("V2 auto-apply dry-run", _v2_ok, str(d.get("error") or ""))
        if d.get("frozen"):
            warns.append("V2 自动策略按设计冻结：" + str(d.get("error") or ""))
    except Exception as exc:
        ck("V2 auto-apply dry-run", False, "%s: %s" % (type(exc).__name__, exc))

    out = {"ok": not fails, "app": str(BASE), "ts": time.time(),
           "n": len(checks), "fails": fails, "warnings": warns,
           "checks": checks}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json_out:
        op = ROOT / args.json_out
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("JSON_OUT", op)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
