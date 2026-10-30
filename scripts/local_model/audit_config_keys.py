#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置键卫生审计（V2.2.94）。

对照最高版引擎的 DEFAULT_CONFIG + 源码引用，找出 configs/*.yaml 里
**真正未被引擎/App 读取**的陈旧键（忽略 App 自管段 app_daosheng.*）。
用法：python scripts/local_model/audit_config_keys.py
证据：docs/config_key_audit_20261031.json
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

import lead_layer_goal_audit as lga  # noqa: E402

#: App 自管配置段（引擎不认识但 App 会读），不参与「陈旧键」判定。
APP_SECTIONS = ("app_daosheng.", "app_ui.", "app.")
OUT = ROOT / "docs" / "config_key_audit_20261031.json"


def _flat(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = prefix + k
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def main() -> int:
    eng_path = lga.latest_engine_path()
    src = Path(eng_path).read_text(encoding="utf-8", errors="replace")
    eng = lga.load_engine(eng_path)
    known = set(_flat(eng.DEFAULT_CONFIG))
    rows = []
    for f in sorted(glob.glob(str(ROOT / "configs" / "*.yaml"))):
        d = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        stale = []
        for k in _flat(d):
            if k in known or k.startswith(APP_SECTIONS):
                continue
            leaf = k.split(".")[-1]
            pat = r"[\"']" + re.escape(leaf) + r"[\"']"
            if re.search(pat, src) or re.search(r"\b" + re.escape(leaf) + r"\b", src):
                continue
            stale.append(k)
        if stale:
            rows.append({"preset": Path(f).name, "keys": sorted(stale)})
    out = {"schema": "metadgtf.config_key_audit.v1",
           "ts": "2026-10-31 03:00", "engine": eng_path.name,
           "presets_scanned": len(glob.glob(str(ROOT / "configs" / "*.yaml"))),
           "presets_with_stale_keys": len(rows), "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("presets scanned: %d | with stale keys: %d"
          % (out["presets_scanned"], len(rows)))
    for r in rows:
        print("  %s: %s" % (r["preset"], r["keys"]))
    print("evidence -> %s" % OUT.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
