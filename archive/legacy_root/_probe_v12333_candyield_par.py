#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：**并行模式**下 `candidate_yield` 是否也能落盘（防「一处有一处没有」）。

本项目高频事故：同一条逻辑在 serial 与并行（B/C）两条通道各写一份 ⇒ 漂移。
`candidate_yield` 的接线在 `DGTF.run` 内部（两条通道共用 `DGTF`）⇒ 理论上都该有，
但 `inp.pool` 是否在**所有**通道都被赋上，必须实测（不是「看代码觉得有」）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location("smoke_par", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_par"] = st
    spec.loader.exec_module(st)
    mod = st.mod

    ok = True
    for _mode in ("serial", "B", "C"):
        cfg = st.build_cfg(False)
        try:
            res = mod.MetaDGTF(cfg).run("意识能否被还原为信息处理过程？",
                                        route=["0", "1"], rounds={"0": 3, "1": 3},
                                        parallel_mode=_mode)
        except Exception as e:
            print("[%s] run 抛错：%r" % (_mode, e))
            ok = False
            continue
        hits = {}
        for _L, _v in (res.get("views") or {}).items():
            _vd = _v.to_dict() if hasattr(_v, "to_dict") else (_v or {})
            _qr = (_vd or {}).get("quant_readings") or {}
            if "candidate_yield" in _qr:
                hits[_L] = _qr["candidate_yield"]
        print("[%-6s] 落盘层 = %r | 值 = %r"
              % (_mode, sorted(hits.keys()), hits.get("0")))
        if "0" not in hits:
            print("   ⚠ %s 模式下层 0 未落盘 —— 两条通道漂移！" % _mode)
            ok = False
    print("\n%s" % ("[OK] serial / B / C 三通道一致可达"
                    if ok else "[FAIL] 存在通道不一致（漂移）"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
