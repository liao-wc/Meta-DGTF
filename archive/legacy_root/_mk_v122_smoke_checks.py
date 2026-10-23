#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122] 把 `_v122_checks.py` 里的 `check_v122_phaseN` 同步进 smoke_test.py。

设计要点（踩过的坑都写在这）：
- **唯一事实源**：检查函数的正文只在 `_v122_checks.py` 里手写。本脚本负责搬运，
  不在脚本里内联副本 —— 内联过一版，结果两处开始分叉。
- **幂等**：已存在的同名函数用 ast 定位后**整体替换**（不是跳过），
  所以改了仓库再跑一次就同步，不会产生第二份。
- **接线**：main() 里按 phase 顺序补 `if not check_v122_phaseN(): return 1`。
- **写盘**：`write_bytes`，先断言纯 CRLF，替换完再断言一次（禁止 write_text）。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "smoke_test.py"
REPO = HERE / "_v122_checks.py"
SRC_NEW = "元DGTF-V1.22.0.py"   # [v122 定稿] 冒烟指向定稿版


def _func_src(path: Path, name: str) -> str:
    """按名字抠出顶层函数源码（含尾随空行分隔）。"""
    s = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    tree = ast.parse(s)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = s.split("\n")
            start = node.lineno - 1
            # 吃掉前面的装饰器和紧邻注释
            while start > 0 and lines[start - 1].strip().startswith(("#", "@")):
                start -= 1
            return "\n".join(lines[start:node.end_lineno]) + "\n"
    raise SystemExit(f"{path.name} 里没有 {name}")


def _repo_names() -> list[str]:
    """要搬进 smoke_test 的**全部**顶层函数名。

    不能只搬 `check_v122_phase*` —— 检查函数还依赖 `_v122_mod` /
    `_v122_src_text` 这类helper，漏搬会在冒烟里直接 NameError。
    """
    s = REPO.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [n.name for n in ast.parse(s).body
            if isinstance(n, ast.FunctionDef)
            and (n.name.startswith("check_v122_phase")
                 or n.name.startswith("_v122_"))]


def _guard_names() -> list[str]:
    """要接进 main() 的判据（按执行顺序）。

    `check_v122_phase*` 排前面，与阶段顺序一致；`check_v122_dup_dict_keys`
    这类**全局结构判据**放最后 —— 它扫全文件，先跑阶段判据能更快定位。
    """
    names = [n for n in _repo_names() if n.startswith("check_v122_phase")]
    names.sort(key=lambda s: int(s.rsplit("phase", 1)[1]))
    names += [n for n in _repo_names()
              if n.startswith("check_v122_") and n not in names]
    return names


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "smoke_test 不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "smoke_test 有 \\r\\r\\n"
    s = s.replace("\r\n", "\n")

    names = _repo_names()
    assert names, "_v122_checks.py 里没有可搬运的函数"
    guards = _guard_names()
    assert guards, "没有 check_v122_phase* 可接线"

    for name in names:
        block = _func_src(REPO, name)
        tree = ast.parse(s)
        exist = [n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == name]
        if exist:
            assert len(exist) == 1, f"{name} 在 smoke_test 里定义了 {len(exist)} 次"
            lines = s.split("\n")
            node = exist[0]
            start = node.lineno - 1
            while start > 0 and lines[start - 1].strip().startswith(("#", "@")):
                start -= 1
            lines[start:node.end_lineno] = block.rstrip("\n").split("\n")
            s = "\n".join(lines)
            print(f"  · {name}：已存在 → 用仓库版本替换")
        else:
            anchor = "\ndef main():\n"
            assert s.count(anchor) == 1, "main 定义锚点不唯一"
            s = s.replace(anchor, "\n" + block + "\n" + anchor, 1)
            print(f"  · {name}：新插入")

    # 接线：先把已有的 v122 守卫全部摘掉，再按阶段顺序统一插回去
    #   （否则先插的 phase2 会一直排在 phase1 前面，读日志时看着别扭）
    a_head = ('def main():\n'
              '    verbose = os.environ.get("SMOKE_VERBOSE", "0") == "1"\n')
    assert s.count(a_head) == 1, "main 首行锚点不唯一"
    for name in guards:
        s = s.replace(f"    if not {name}():\n        return 1\n", "")
    block_all = "".join(
        f"    if not {name}():\n        return 1\n" for name in guards)
    s = s.replace(a_head, a_head + block_all, 1)
    print(f"  · main() 接线顺序：{', '.join(guards)}")

    # SRC 指向当前版
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.[0-9]+\.[0-9]+(-rc[0-9]+)?\.py"')
    assert len(pat.findall(s)) == 1, "SRC 行不唯一"
    s = pat.sub(lambda _m: f'SRC = HERE / "{SRC_NEW}"', s, count=1)

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"✓ smoke_test 同步完成：SRC → {SRC_NEW}，检查 {len(names)} 条 "
          f"({', '.join(names)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
