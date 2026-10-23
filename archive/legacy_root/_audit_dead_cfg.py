# -*- coding: utf-8 -*-
"""审计：`DEFAULT_CONFIG` 里**声明了但全文件只出现一次**的键（疑似死参数）。

做法：
  1. AST 取 `DEFAULT_CONFIG = {...}` 的字面量，递归摊平成点路径；
  2. 对每个**叶子键名**，在全文件里数它作为字符串字面量出现的次数；
  3. 只出现 1 次（就是定义那处）⇒ 没有任何读取点 ⇒ 疑似死键。

★ 这是启发式，不是定罪：
  · 有的键被 `cfg.get(leaf)` 之外的方式读（如 `**cfg`、整体传递）⇒ 会漏判；
  · 所以结果叫"疑似"，要人看一眼再定性。
"""
import ast
import collections
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.60.py"
s = SRC.read_text(encoding="utf-8")
tree = ast.parse(s)


def flatten(node, prefix=""):
    out = []
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                continue
            path = "%s.%s" % (prefix, k.value) if prefix else k.value
            if isinstance(v, ast.Dict):
                out.extend(flatten(v, path))
            else:
                out.append((path, k.value))
    return out


cfg = None
for n in tree.body:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == "DEFAULT_CONFIG":
                cfg = n.value
assert cfg is not None, "找不到 DEFAULT_CONFIG"

leaves = flatten(cfg)
print("DEFAULT_CONFIG 叶子键：%d 个" % len(leaves))

# 全文件字符串字面量出现次数
cnt = collections.Counter()
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        cnt[node.value] += 1

dead = [(p, k) for p, k in leaves if cnt.get(k, 0) <= 1]
print("疑似死键（字面量只出现 ≤1 次）：%d 个" % len(dead))
for p, k in dead:
    print("  · %-46s （出现 %d 次）" % (p, cnt.get(k, 0)))

# 反向：字符串里在用、但 DEFAULT_CONFIG 里没有的键（可能是漏声明）
print("\n（参考）字面量出现很多次但不在 DEFAULT_CONFIG 的键名，见下 —— 只列 5 次以上的：")
paths = {k for p, k in leaves}
for k, c in cnt.most_common():
    if k in paths or c < 5:
        continue
    if "." in k or len(k) < 4 or " " in k:
        continue
    print("  · %-40s %d 次" % (k, c))
