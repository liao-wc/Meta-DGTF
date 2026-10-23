#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 6 阶段：merge_sim 出口（前向守卫抓漏）。

`check_v123_pool_export` 按 `__dataclass_fields__` 逐个查出口 —— merge_sim
是字段就必须出口（实际生效值），否则读的人不知道这批 merge_log 按哪个
阈值判的。merge_semantic / merge_log 已有出口，唯独 merge_sim 漏了。
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


def main():
    s = _load()
    old = '''        d["merge_log"] = list(getattr(self, "merge_log", []) or [])'''
    new = '''        d["merge_log"] = list(getattr(self, "merge_log", []) or [])
        # ★ merge_sim 同样出口**实际生效值**（前向守卫按字段名逐个查）。
        d["merge_sim"] = float(getattr(self, "merge_sim", 0.0) or 0.0)'''
    n = s.count(old)
    assert n == 1, "merge_log 出口锚点命中 %d 次" % n
    s = s.replace(old, new)
    _save(s)
    print("OK 第 6 阶段（merge_sim 出口）完成")


if __name__ == "__main__":
    main()
