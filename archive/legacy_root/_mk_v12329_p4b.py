#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 4b 阶段：D2 配置下发接线。

`belief.merge_semantic` / `belief.merge_sim` 必须像 `sem_entropy_thr` 一样
在构造时显式下发到每个池 —— 否则配置键不读 = 埋坑（同 D3 的教训）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def repl_text(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    old = """        for _p in self.pools.values():
            _p.sem_entropy_thr = _se
        self.verbose = config["output"].get("verbose", True)"""
    new = """        for _p in self.pools.values():
            _p.sem_entropy_thr = _se
        # [D2 可配] 语义归并开关/阈值同样显式下发（默认关 / 0.85）。
        try:
            _mg = bool((config.get("belief") or {}).get(
                "merge_semantic", False))
        except (TypeError, ValueError):
            _mg = False
        try:
            _ms = float((config.get("belief") or {}).get(
                "merge_sim", _BELIEF_MERGE_SIM))
        except (TypeError, ValueError):
            _ms = _BELIEF_MERGE_SIM
        for _p in self.pools.values():
            _p.merge_semantic = _mg
            _p.merge_sim = _ms
        self.verbose = config["output"].get("verbose", True)"""
    s = repl_text(s, old, new, "D2 配置下发")

    _save(s)
    print("OK 第 4b 阶段（D2 配置下发）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("_p.merge_semantic = _mg") == 1
    assert s2.count("_p.merge_sim = _ms") == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
