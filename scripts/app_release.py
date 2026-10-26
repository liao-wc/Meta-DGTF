# -*- coding: utf-8 -*-
"""App 版本同步：更新 APP_VERSION、静态缓存串和当前版本文档。"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from safe_file_ops import atomic_write, snapshot  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--cache-tag", default="")
    a = ap.parse_args()
    new = str(a.version).strip()
    tag = str(a.cache_tag or (new + "-release")).strip()
    snap = snapshot(None, "before_app_release_" + new.replace(".", "_"))
    server_p = ROOT / "dgtf_app/server.py"
    server = server_p.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', server)
    old = m.group(1) if m else ""
    server = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "%s"' % new, server, count=1)
    atomic_write(server_p, server)
    index_p = ROOT / "dgtf_app/static/index.html"
    index = index_p.read_text(encoding="utf-8")
    index = re.sub(r'\?v=[^"\'&]+', "?v=" + tag, index)
    atomic_write(index_p, index)
    # 只改当前版本文档，不碰历史报告/发布说明
    for rel, pats in {
        "README.md": [("App " + old, "App " + new)],
        "dgtf_app/README.md": [("V" + old, "V" + new)],
        "PROJECT_LAYOUT.md": [("App：" + old, "App：" + new)],
        "dgtf_engine/dgtf_v2/NAMING.md": [
            ("__regex__", r"App\s*\|\s*2\.0\.\d+", "App | " + new),
            ("__regex__", r"app-V2\.0\.\d+", "app-V" + new)],
        "docs/index.html": [("__regex__", r"V\d+\.\d+\.\d+ \(App\)", "V" + new + " (App)")],
    }.items():
        p = ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for item in pats:
            if len(item) == 3 and item[0] == "__regex__":
                text = re.sub(item[1], item[2], text)
            else:
                x, y = item[0], item[1]
                text = text.replace(x, y)
        atomic_write(p, text)
    print("bumped", old, "->", new, "cache", tag, "backup", snap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
