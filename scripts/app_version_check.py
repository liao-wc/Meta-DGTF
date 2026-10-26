# -*- coding: utf-8 -*-
"""App 版本一致性检查：APP_VERSION / 静态缓存串 / README / 发布说明 / CHANGELOG。"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def main():
    server = _read("dgtf_app/server.py")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', server)
    version = m.group(1) if m else ""
    index = _read("dgtf_app/static/index.html")
    tags = sorted(set(re.findall(r'\?v=([^"\'&]+)', index)))
    expected_tag_prefix = version + "-"
    checks = []
    def ck(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    ck("APP_VERSION 可读", bool(version), version)
    ck("静态查询串同版本", bool(tags) and all(t == version or t.startswith(expected_tag_prefix) for t in tags), tags)
    ck("根 README 当前版本", ("App " + version) in _read("README.md"), version)
    ck("App README 当前版本", ("V" + version) in _read("dgtf_app/README.md"), version)
    ck("PROJECT_LAYOUT 当前版本", ("App：" + version) in _read("PROJECT_LAYOUT.md"), version)
    ck("发布说明存在", (ROOT / "docs" / "releases" / ("app-V" + version + ".md")).is_file(), version)
    ck("CHANGELOG 含当前 App 版本", ("App " + version) in _read("CHANGELOG.md"), version)
    _naming = _read("dgtf_engine/dgtf_v2/NAMING.md")
    ck("NAMING 当前 App 版本", ("App | " + version) in _naming, version)
    ck("NAMING App 发布标签", ("app-V" + version) in _naming, version)
    doc = {"ok": all(x["ok"] for x in checks), "version": version,
           "cache_tags": tags, "checks": checks}
    dst = ROOT / "docs" / "app_version_latest.json"
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
