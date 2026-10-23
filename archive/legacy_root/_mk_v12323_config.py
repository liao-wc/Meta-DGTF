#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.23 配置同步：只动**头部版本**（本版没有新增/改默认的配置键）。

本版改的是日志回显文本 ⇒ `DEFAULT_CONFIG` 一个键都没动 ⇒ 不需要新增升级段
（v1.23.19→20 / 20→21 / 21→22 三版同样没有升级段）。
判据（v1.23.2 审计的 C3）：yaml 头部版本必须 == 引擎 `__version__`。

yaml 是**纯 CRLF**：read_bytes -> 断言 -> 转 LF -> 改 -> 转回 -> write_bytes。

    python _mk_v12323_config.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
ENGINE = HERE / "元DGTF-V1.23.23.py"

OLD_HEAD = "# 元 DGTF · v1.23.22 配置文件"
NEW_HEAD = "# 元 DGTF · v1.23.23 配置文件"


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0 and b.count(b"\r") == b.count(b"\r\n")
    p.write_bytes(b)


def load_engine():
    spec = importlib.util.spec_from_file_location("dg_v12323", ENGINE)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    mod = load_engine()
    ver = mod.__version__
    assert ver == "1.23.23", "引擎版本不是 1.23.23：%s" % ver

    before = read_crlf(YAML).replace("\r\n", "\n")
    cfg_before = mod.load_config(str(YAML))

    if NEW_HEAD in before:
        print("  · 头部版本已是 v1.23.23")
        cur = before
    else:
        assert before.count(OLD_HEAD) == 1, "头部锚点命中 %d 次" % before.count(OLD_HEAD)
        cur = before.replace(OLD_HEAD, NEW_HEAD)
        print("  ✓ 头部版本：v1.23.22 -> v1.23.23")
        write_crlf(YAML, cur)

    after = read_crlf(YAML).replace("\r\n", "\n")
    cfg_after = mod.load_config(str(YAML))

    # ① 文本层：差异只允许是那一行
    diff_lines = [i for i, (a, b) in enumerate(zip(before.split("\n"), after.split("\n")))
                  if a != b]
    assert len(before.split("\n")) == len(after.split("\n")), "行数变了"
    assert diff_lines == [1], "文本差异不止头部一行：%s" % diff_lines

    # ② 语义层：load_config 逐字相等（json 归一化）
    a = json.dumps(cfg_before, sort_keys=True, ensure_ascii=False)
    b = json.dumps(cfg_after, sort_keys=True, ensure_ascii=False)
    assert a == b, "load_config 结果变了"

    # ③ 头部版本 == __version__
    m = re.search(r"^# 元 DGTF · v(\S+) 配置文件", after, re.M)
    assert m and m.group(1) == ver, "yaml 头部版本 %r != %r" % (m and m.group(1), ver)

    print("  ✓ 自检：文本差异 = 头部 1 行；load_config 逐字相等；头部版本 == %s" % ver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
