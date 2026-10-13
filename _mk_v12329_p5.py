#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 5 阶段：DEFAULT_CONFIG 新增 belief.merge_* 键。"""
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
    old = '''        "sem_entropy_thr": 0.30,
    },'''
    new = '''        "sem_entropy_thr": 0.30,
        # [D2 修正] 语义归并开关（默认**关** ⇒ 出厂零行为差）。
        #   开 ⇒ 「几乎同一句话」的换说法重提记为已存在条目的一次复现
        #   （进 occurrences），留痕 merge_log。见 Pool.merge_semantic。
        "merge_semantic": False,
        # [D2 修正] 语义归并阈值。★ 0.85 是**刻意的高门槛**（红线
        #   「入池前挡重复」：不同主张实测 0.00~0.79，够不到它）。
        #   宁可漏并，不可错并。
        "merge_sim": 0.85,
    },'''
    s = repl_text(s, old, new, "DEFAULT_CONFIG belief.merge_*")

    _save(s)
    print("OK 第 5 阶段（DEFAULT_CONFIG）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count('"merge_semantic": False') == 1
    assert s2.count('"merge_sim": 0.85') == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
