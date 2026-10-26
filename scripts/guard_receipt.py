# -*- coding: utf-8 -*-
"""DSH 守卫完成回执：每轮巡检最后一步写回执，守卫读取后标记完成。"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dgtf_memory" / "guard_receipt.json"


def _run(script, args=None, timeout=120):
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)] + list(args or []),
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def verify_gates(report: str = "") -> list[str]:
    """完成回执前独立复核：版本/完整性/报告/审计证据新鲜度。"""
    errs = []
    ok, out = _run("app_version_check.py", timeout=60)
    if not ok:
        errs.append("app_version_check 未通过：" + out[-800:])
    ok, out = _run("file_integrity_check.py", timeout=90)
    if not ok:
        errs.append("file_integrity_check 未通过：" + out[-800:])
    if report:
        rp = Path(report)
        if not rp.is_absolute():
            rp = ROOT / rp
        if not rp.is_file():
            errs.append("报告不存在：" + str(report))
        else:
            ok, out = _run("check_patrol_report.py", ["--report", str(rp), "--check"], timeout=60)
            if not ok:
                errs.append("巡检报告门禁未通过：" + out[-800:])
    else:
        errs.append("completed 回执必须提供 --report")
    now = time.time()
    for rel in ("docs/app_audit_latest.json", "docs/outputs_audit_latest.json",
                "docs/system_audit_latest.json"):
        fp = ROOT / rel
        if not fp.is_file():
            errs.append("缺少审计证据：" + rel)
            continue
        age = now - fp.stat().st_mtime
        if age > 6 * 3600:
            errs.append("审计证据过旧（>6h）：%s" % rel)
        if rel == "docs/app_audit_latest.json":
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
                if d.get("fails"):
                    errs.append("App 审计存在硬失败：%s" % d.get("fails"))
            except Exception as exc:
                errs.append("App 审计不可读：%s" % exc)
    return errs


def write_receipt(dispatch_id: str, status="completed", report="", checks=None, notes="", out=None):
    rec = {
        "dispatch_id": str(dispatch_id or ""),
        "status": str(status or "completed"),
        "completed_at": time.time(),
        "completed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "report": str(report or ""),
        "checks": list(checks or []),
        "notes": str(notes or "")[:2000],
        "agent": "dsh",
    }
    target = Path(out) if out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(target))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dispatch-id", required=True)
    ap.add_argument("--status", default="completed", choices=["completed", "failed", "blocked"])
    ap.add_argument("--report", default="")
    ap.add_argument("--checks", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    checks = [x.strip() for x in str(a.checks or "").split(",") if x.strip()]
    if a.status == "completed":
        errs = verify_gates(a.report)
        if errs:
            print(json.dumps({"ok": False, "error": "gate check failed, receipt not written",
                              "details": errs}, ensure_ascii=False, indent=1))
            return 1
    rec = write_receipt(a.dispatch_id, a.status, a.report, checks, a.notes, out=(a.out or None))
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return 0 if a.status == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
