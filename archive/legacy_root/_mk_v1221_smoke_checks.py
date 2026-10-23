#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1] 把 `_v1221_checks.py` 里的 `check_v1221_pN` 同步进 smoke_test.py。

与 `_mk_v122_smoke_checks.py` 的差别（照抄它的设计，只换仓库与命名）：
- 源仓库是 `_v1221_checks.py`，搬 `check_v1221_*` / `_v1221_*`；
- 接线顺序：**先 v122 六阶段守卫，后 v1221 各档** —— 统一由本脚本重排，
  所以本脚本必须排在 `_mk_v122_smoke_checks.py` **之后**再跑。
- `SRC_NEW` 指向当前工作版（定稿后改 `元DGTF-V1.22.1.py`）。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "smoke_test.py"
REPO = HERE / "_v1221_checks.py"
SRC_NEW = "元DGTF-V1.22.1.py"   # [第三档] 定稿

GUARD_RE = re.compile(r"    if not (check_[A-Za-z0-9_]+)\(\):\n        return 1\n")


def _func_src(path: Path, name: str) -> str:
    s = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    tree = ast.parse(s)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = s.split("\n")
            start = node.lineno - 1
            while start > 0 and lines[start - 1].strip().startswith(("#", "@")):
                start -= 1
            return "\n".join(lines[start:node.end_lineno]) + "\n"
    raise SystemExit(f"{path.name} 里没有 {name}")


def _repo_names() -> list[str]:
    s = REPO.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [n.name for n in ast.parse(s).body
            if isinstance(n, ast.FunctionDef)
            and (n.name.startswith("check_v1221_")
                 or n.name.startswith("_v1221_"))]


def _p_key(name: str) -> int:
    m = re.search(r"_p(\d+)", name)
    return int(m.group(1)) if m else 99


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "smoke_test 不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "smoke_test 有 \\r\\r\\n"
    s = s.replace("\r\n", "\n")

    names = _repo_names()
    assert names, "_v1221_checks.py 里没有可搬运的函数"

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

    # ---- 接线：**只碰自己管的那几条** ----
    # ★ 事故记录：第一版用 `GUARD_RE.sub("", s)` 把**全部**守卫摘掉再重排，
    #   结果 69 条老守卫（v63~v1217x）被清空、只剩 4 条 —— 冒烟从 158 ✓
    #   掉到 21 ✓，而且因为 EXIT=0 所以「全绿」。教训：接线器只能动自己
    #   负责的名字，别人的守卫一律不碰。
    v1221 = [n for n in names if n.startswith("check_v1221_")]
    v1221.sort(key=_p_key)
    for name in v1221:
        s = s.replace(f"    if not {name}():\n        return 1\n", "")
    a_head = ('def main():\n'
              '    verbose = os.environ.get("SMOKE_VERBOSE", "0") == "1"\n')
    assert s.count(a_head) == 1, "main 首行锚点不唯一"
    hits = list(GUARD_RE.finditer(s))
    block = "".join(f"    if not {n}():\n        return 1\n" for n in v1221)
    if hits:
        s = s[:hits[-1].end()] + block + s[hits[-1].end():]
        print(f"  · 接线：v1221 {len(v1221)} 条接在已有守卫之后"
              f"（原有 {len(hits)} 条保持不变）")
    else:
        s = s.replace(a_head, a_head + block, 1)
        print(f"  · 接线：v1221 {len(v1221)} 条（main 里原本没有守卫）")

    # 只把 v1221 的函数插到 main 之前；v122 的函数不归本脚本管

    # ★ 正则要认 `-rc1b` 这种带字母的候选版：原来写 `-rc[0-9]+`，第一次
    #   把 rc1 改成 rc1b 之后**第二次就匹配不到**（`b` 落在 `.py` 前），
    #   findall 变 0 → 断言「SRC 行不唯一」误报。改成宽松的 `[\w.\-]*`。
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.[0-9]+\.[0-9]+[\w.\-]*\.py"')
    assert len(pat.findall(s)) == 1, "SRC 行不唯一"
    s = pat.sub(lambda _m: f'SRC = HERE / "{SRC_NEW}"', s, count=1)

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    n_guard = len(GUARD_RE.findall(s))
    assert n_guard >= 74, (
        f"守卫数掉到 {n_guard}（基线 74）—— 接线器只许增不许减，"
        f"掉数说明它动了不该动的守卫")
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"✓ smoke_test 同步完成：SRC → {SRC_NEW}，搬运 {len(names)} 条，"
          f"守卫 {n_guard} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
