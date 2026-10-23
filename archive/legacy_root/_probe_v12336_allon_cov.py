#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[只读探针] `_ALL_ON_ITEMS` 的**覆盖面**对账。

依据（用户口径）：
  「所有最终真跑验收默认都是配置开关全开或者针对性设置配置，不仅可以检验本次
   改动，还方便检查之前的改动有没有生效、或者发现新问题。」
  ⇒ 「全开」必须**真的全**。若某个可切换的能力开关不在 `_ALL_ON_ITEMS` 里，
    全开真跑就**验不到它**，且**没有任何判据会发现**（清单自称单一真相源）。

本探针做两向对账（只读，不改任何文件）：
  ① `_ALL_ON_ITEMS` 里每一项的路径必须在 `DEFAULT_CONFIG` 里**真实存在**；
  ② 引擎里所有 `_action_on(..., "x")` / `actions.*` 能力开关，逐个列出
     「在清单里 / 不在清单里」。

★ 判据纪律：不预设「应该几项」（那是会变的），只报**差异表**。
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.36.py"


def flatten(cfg, prefix=""):
    out = []
    for k, v in (cfg or {}).items():
        p = "%s.%s" % (prefix, k) if prefix else str(k)
        if isinstance(v, dict):
            out.extend(flatten(v, p))
        else:
            out.append((p, v))
    return out


def main():
    txt = SRC.read_text(encoding="utf-8", errors="replace")
    sp = importlib.util.spec_from_file_location("m", SRC)
    m = importlib.util.module_from_spec(sp)
    sys.modules["m"] = m
    sp.loader.exec_module(m)

    all_on = [(p, v, w) for p, v, w in (m._ALL_ON_ITEMS or ())]
    flat = dict(flatten(m.DEFAULT_CONFIG))
    print("=== ① 清单项在配置里是否存在（%d 项）===" % len(all_on))
    bad = []
    for p, v, w in all_on:
        hit = p in flat
        if not hit:
            bad.append(p)
        print("   %-28s %s  当前出厂=%r" % (p, "OK " if hit else "**缺失**",
                                            flat.get(p, "<无此键>")))
    print("   → 不存在的项：%r" % (bad,))

    # ── ② 所有 _action_on 的目标键 ──
    keys = sorted(set(re.findall(r'_action_on\(\s*[^,()]+,\s*"([^"]+)"', txt)))
    print("\n=== ② `_action_on(..., \"x\")` 目标键共 %d 个 ===" % len(keys))
    acts = m.DEFAULT_CONFIG.get("actions") or {}
    in_allon = {p for p, _v, _w in all_on}
    miss, ok = [], []
    for k in keys:
        # _action_on 的键默认落在 actions 段（见 DEFAULT_CONFIG["actions"]）
        cand = "actions." + k
        if cand in in_allon:
            ok.append(k)
        else:
            miss.append(k)
    print("   在清单里（%d）：%r" % (len(ok), ok))
    print("   不在清单里（%d）：%r" % (len(miss), miss))

    # ── ②b actions 段里默认 **False** 的项（= 默认关的能力开关）──
    off_acts = {k: v for k, v in acts.items() if v is False}
    print("\n=== ②b `DEFAULT_CONFIG['actions']` 中默认 False 的键（%d）==="
          % len(off_acts))
    for k in sorted(off_acts):
        print("   %-24s 在全开清单？%s" % (k, "是" if ("actions." + k) in in_allon
                                        else "**否**"))

    print("\n[小结] 清单 %d 项；`_action_on` 目标键 %d 个；其中不在清单 %d 个"
          % (len(all_on), len(keys), len(miss)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
