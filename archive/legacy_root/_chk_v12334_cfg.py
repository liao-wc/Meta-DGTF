#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查：配置键里哪些是**死键**（只写不读 / 只定义不用）。

## 为什么这么查
用户诉求：「检查哪些是不必要的开关，给它清掉」。
本项目已有红线「每个键都要有读点」，但**没有自动化判据**（审计里没有这一类）
⇒ 死键可以悄悄堆积。

## 方法（两向）
  · **正向**：AST 取出 `DEFAULT_CONFIG` 的全部**叶子路径**；
  · **查读点**：对每个叶子键的**末段名**，在源码里数「非注释、非定义处」的出现：
      `X.get("<key>"` / `["<key>"]` / `, "<key>")` / `_action_on(…, "<key>"` …
    只在 `DEFAULT_CONFIG` 里出现一次 ⇒ **死键候选**。
  ★ 局限性（写明）：末段名相同但路径不同的键会互相「蹭」读点 ⇒ 本检查是
    **候选清单**，最终要人逐条确认（所以输出里给出每键的出现行号便于核对）。
"""
import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.34.py"


def leaves(d, pre=""):
    out = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = "%s.%s" % (pre, k) if pre else str(k)
        if isinstance(v, dict):
            out.update(leaves(v, key))
        else:
            out[key] = v
    return out


def walk_cfg(node, pre=""):
    """AST 版：`DEFAULT_CONFIG` 里有**函数调用**（`literal_eval` 会炸），
    所以手工遍历 `ast.Dict`，遇到非字面量就当叶子（记下源码文本）。"""
    out = {}
    if not isinstance(node, ast.Dict):
        return out
    for k, v in zip(node.keys, node.values):
        if not isinstance(k, ast.Constant):
            continue
        key = "%s.%s" % (pre, k.value) if pre else str(k.value)
        if isinstance(v, ast.Dict):
            out.update(walk_cfg(v, key))
        else:
            try:
                out[key] = ast.unparse(v)
            except Exception:
                out[key] = "<unparse失败>"
    return out


def main():
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    # ── 1) 取 DEFAULT_CONFIG 的叶子 ──
    cfg_leaves = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG":
                    cfg_leaves = walk_cfg(n.value)
    if not cfg_leaves:
        print("没找到 DEFAULT_CONFIG（换名字了？）")
        return 2

    # ── 2) 去注释的源码（死键判定不许被注释蹭到）──
    no_comment = "\n".join(
        re.sub(r"#.*$", "", ln) for ln in src.splitlines())

    # ── 3) 定义处出现次数（DEFAULT_CONFIG 区块内部）──
    _i = no_comment.find("DEFAULT_CONFIG = ")
    _j = no_comment.find("\n_ALL_ON_ITEMS", _i)
    _cfg_zone = no_comment[_i:_j if _j > 0 else _i + 200000]

    dead, weak = [], []
    for path, val in sorted(cfg_leaves.items()):
        leaf = path.split(".")[-1]
        pats = ('"%s"' % leaf, "'%s'" % leaf)
        n_all = sum(no_comment.count(p) for p in pats)
        n_cfg = sum(_cfg_zone.count(p) for p in pats)
        n_out = n_all - n_cfg
        if n_out <= 0:
            dead.append((path, val, n_all, n_cfg))
        elif n_out <= 1:
            weak.append((path, val, n_out))

    print("=== 配置叶子键 %d 个 ===" % len(cfg_leaves))
    print("\n【死键候选】（定义外**一次都没出现**）—— %d 个：" % len(dead))
    for path, val, a, b in dead:
        print("   %-46s 默认=%-22r 总出现=%d(定义区=%d)" % (path, val, a, b))
    print("\n【弱读点】（定义外只出现 1 次，可能只被注释/日志蹭到）—— %d 个："
          % len(weak))
    for path, val, n in weak:
        print("   %-46s 默认=%-22r 定义外=%d" % (path, val, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
