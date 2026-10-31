# -*- coding: utf-8 -*-
"""[V2.2.113] main 配置（dgtf_config.yaml）陈旧键审计（追加到 config_keys 门禁）。

对照最高版引擎 DEFAULT_CONFIG + 源码引用，找 dgtf_config.yaml 中真正无人读取的键；
App 自管段（app_* / mode. / scheduler. / budget. / daosheng.）排除。
有陈旧键 => 退出码 1（门禁判红，强制清理）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

import lead_layer_goal_audit as lga  # noqa: E402

APP_SECTIONS = ("app_daosheng.", "app_ui.", "app.", "mode.", "scheduler.",
                "budget.", "daosheng.")
OUT = ROOT / "docs" / "config_key_audit_main_20261031.json"


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
    for _m in sorted((ROOT / "dgtf_engine" / "dgtf_v2").glob("*.py")):
        try:
            src += chr(10) + _m.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    eng = lga.load_engine(eng_path)
    known = set(_flat(eng.DEFAULT_CONFIG))
    f = ROOT / "dgtf_config.yaml"
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    stale = []
    for k in _flat(d):
        if k in known or k.startswith(APP_SECTIONS):
            continue
        leaf = k.split(".")[-1]
        pat = r"[\"']" + re.escape(leaf) + r"[\"']"
        if re.search(pat, src) or re.search(r"\b" + re.escape(leaf) + r"\b", src):
            continue
        stale.append(k)
    out = {"schema": "metadgtf.config_key_audit_main.v1",
           "ts": "2026-10-31 14:05", "engine": Path(eng_path).name,
           "stale_keys": sorted(stale), "stale_count": len(stale)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("main config stale keys: %d" % len(stale))
    for k in sorted(stale):
        print("  " + k)
    print("evidence -> %s" % OUT.relative_to(ROOT).as_posix())
    return 0 if not stale else 1


if __name__ == "__main__":
    raise SystemExit(main())
