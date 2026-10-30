# -*- coding: utf-8 -*-
"""[V2.2.87] App 透传 flag ↔ 当前引擎 argparse 对齐审计（纯函数，零 API）。

engine_alignment 只保证「查的文件 == App 选中的引擎」；本审计进一步保证
engine_runner 会透传的每个 flag 在**当前引擎源码**里真的存在：
  - 任一 _ARG_SPEC / _BOOL_FLAGS 的 flag 不在引擎源码 ⇒ 引擎 argparse 会报错；
  - gated flag 的 engine_capabilities 结果必须与源码探测一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (str(ROOT), str(ROOT / "dgtf_engine"), str(ROOT / "dgtf_app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_runner as ER  # noqa: E402


def main() -> int:
    eng = ER.find_engine()
    src = eng.read_text(encoding="utf-8", errors="replace")
    flags = {}
    for key, flag in ER._ARG_SPEC.items():
        flags[flag] = key
    for key, flag in ER._BOOL_FLAGS.items():
        flags[flag] = "bool:" + key
    bad = []
    rows = []
    for flag, key in sorted(flags.items()):
        present = flag in src
        rows.append({"flag": flag, "key": key, "present": present})
        if not present:
            bad.append("引擎源码缺 %s（App 会透传；argparse 将报错）" % flag)
    caps = ER.engine_capabilities(force=True)
    _flag2key = {v: k for k, v in ER._CAPABILITY_FLAGS.items()}
    for flag in sorted(ER._GATED_FLAGS):
        if flag not in flags:
            bad.append("gated flag 不在映射表：%s" % flag)
            continue
        _key = _flag2key.get(flag)
        if _key is None:
            # engine_supports_flag 对不在 _CAPABILITY_FLAGS 的 flag 返回 True（源码探测兜底）
            if flag not in src:
                bad.append("gated flag %s 不在引擎源码（会被透传）" % flag)
            continue
        if not bool((caps.get("supports") or {}).get(_key, False)):
            bad.append("能力门控未识别 %s（supports 缺失）" % flag)
    out = {"schema": "metadgtf.flag_alignment.v1", "engine": str(eng),
           "engine_version": caps.get("version"), "flags": rows,
           "violations": bad, "n": len(rows), "n_bad": len(bad)}
    ev = ROOT / "docs" / "flag_alignment_20261030.json"
    ev.write_text(json.dumps(out, ensure_ascii=False, indent=1) + chr(10),
                  encoding="utf-8")
    print("engine:", eng.name, "| flags:", len(rows), "| violations:", len(bad))
    for b in bad[:10]:
        print("BAD", b)
    print("evidence ->", ev.relative_to(ROOT))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
