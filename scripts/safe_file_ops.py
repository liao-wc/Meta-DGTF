# -*- coding: utf-8 -*-
"""安全文件操作：备份、原子写、语法校验、按清单恢复。

用法：
  python scripts/safe_file_ops.py snapshot --tag before_x
  python scripts/safe_file_ops.py verify
  python scripts/safe_file_ops.py restore --backup dgtf_memory/edit_backups/<dir>

关键源码禁止直接 Path.write_text；先 snapshot，再通过本工具写入。
"""
from __future__ import annotations
import argparse, hashlib, json, os, py_compile, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = ROOT / "dgtf_memory" / "edit_backups"
CRITICAL = [
    "dgtf_app/server.py", "dgtf_app/engine_runner.py",
    "dgtf_app/static/app.js", "dgtf_app/static/style.css",
    "dgtf_app/static/index.html", "dgtf_app/v2_online.py",
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _node_exe() -> str:
    p = os.environ.get("DSH_NODE") or ""
    if p and Path(p).is_file():
        return p
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DeepSeek Harness" / "resources"
    for x in base.glob("**/node.exe") if base.exists() else []:
        if x.is_file():
            return str(x)
    for x in (ROOT / "node_modules" / ".bin").glob("node*") if (ROOT / "node_modules" / ".bin").exists() else []:
        if x.is_file():
            return str(x)
    return ""


def validate(path: Path) -> tuple[bool, str]:
    try:
        if path.suffix == ".py":
            py_compile.compile(str(path), doraise=True)
        elif path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".js":
            node = _node_exe()
            if node:
                r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=60)
                if r.returncode != 0:
                    return False, (r.stderr or r.stdout or "node --check failed")[:800]
        if path.stat().st_size < 1:
            return False, "empty file"
        return True, "ok"
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def snapshot(paths=None, tag="before_edit") -> Path:
    files = [ROOT / p for p in (paths or CRITICAL) if (ROOT / p).is_file()]
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_" + str(time.time_ns() % 1000000).zfill(6)
    dst = BACKUP_ROOT / ("%s_%s" % (tag, stamp))
    dst.mkdir(parents=True, exist_ok=False)
    manifest = {"created_at": stamp, "tag": tag, "files": {}}
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        manifest["files"][rel] = {"size": out.stat().st_size, "sha256": _sha(out)}
    (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst


def atomic_write(file_path, text: str, encoding="utf-8"):
    """先临时文件 + 语法校验 + replace；失败自动回滚原文件。"""
    p = Path(file_path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    old = p.read_bytes() if p.is_file() else None
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    os.close(fd)
    tmp = Path(tmp)
    try:
        tmp.write_text(text, encoding=encoding)
        check = p.with_name(p.name + ".tmp_check" + p.suffix)
        check.write_text(text, encoding=encoding)
        ok, err = validate(check)
        check.unlink(missing_ok=True)
        if not ok:
            raise RuntimeError("validation failed: " + err)
        os.replace(str(tmp), str(p))
        return True
    except Exception:
        if old is not None:
            p.write_bytes(old)
        raise
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def verify(paths=None) -> list[dict]:
    files = [ROOT / p for p in (paths or CRITICAL) if (ROOT / p).is_file()]
    out = []
    for p in files:
        ok, err = validate(p)
        out.append({"file": p.relative_to(ROOT).as_posix(), "ok": ok,
                    "size": p.stat().st_size, "error": "" if ok else err})
    return out


def restore(backup: Path, files=None):
    """全量预检通过后才替换；任何一份备份损坏都不会写半套文件。"""
    man = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    rels = files or list(man.get("files") or {})
    prepared = []
    results = []
    for rel in rels:
        src = backup / rel
        dst = ROOT / rel
        meta = (man.get("files") or {}).get(rel) or {}
        if not src.is_file():
            results.append({"file": rel, "ok": False, "error": "backup missing"})
            continue
        if meta.get("sha256") and _sha(src) != str(meta["sha256"]):
            results.append({"file": rel, "ok": False, "error": "backup hash mismatch"})
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        check = dst.with_name(dst.name + ".restore_check" + dst.suffix)
        shutil.copy2(src, check)
        ok, err = validate(check)
        if not ok:
            check.unlink(missing_ok=True)
            results.append({"file": rel, "ok": False, "error": err})
            continue
        prepared.append((rel, check, dst))
        results.append({"file": rel, "ok": True, "error": ""})
    if any(not x["ok"] for x in results):
        for _, check, _ in prepared:
            check.unlink(missing_ok=True)
        raise RuntimeError(json.dumps(results, ensure_ascii=False))
    for rel, check, dst in prepared:
        os.replace(str(check), str(dst))
    return results


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot"); sp.add_argument("--tag", default="before_edit"); sp.add_argument("--files", nargs="*")
    vp = sub.add_parser("verify"); vp.add_argument("--files", nargs="*")
    rp = sub.add_parser("restore"); rp.add_argument("--backup", required=True); rp.add_argument("--files", nargs="*")
    a = ap.parse_args()
    if a.cmd == "snapshot":
        print(snapshot(a.files, a.tag)); return 0
    if a.cmd == "verify":
        out = verify(a.files); print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if all(x["ok"] for x in out) else 1
    if a.cmd == "restore":
        print(json.dumps(restore(Path(a.backup), a.files), ensure_ascii=False, indent=1)); return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
