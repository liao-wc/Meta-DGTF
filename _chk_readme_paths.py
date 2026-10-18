# -*- coding: utf-8 -*-
"""自查：README 里用反引号包起来的**路径型**引用，是不是都真存在。

★ 这条是给"门面文档"用的：README 写错一个路径，比代码写错更难发现
  （没人跑它）。v1.23.61 的报告就栽过一次（写成 `server.py`，实际在 `dgtf_app/`）。
"""
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
txt = (HERE / "README.md").read_text(encoding="utf-8")

# 只挑"像路径"的：含 / 或 .py/.md/.yaml 或已知命令名
cand = set(re.findall(r"`([^`\n]+)`", txt))
skip = {"content", "context", "self", "both", "all", "0", "1", "paused", "None",
        "outputs/", "0:6,both:5", "serial", "auto", "on", "off", "pre", "a..h"}
bad, checked = [], 0
for c in sorted(cand):
    if c in skip or c.startswith("--") or " " in c:
        continue
    if "*" in c:          # 通配（`_mk_v1*.py` 之类）不是确定路径，跳过
        continue
    if not re.search(r"(\.py|\.md|\.yaml|/)", c):
        continue
    checked += 1
    p = HERE / c.rstrip("/")
    if not p.exists():
        bad.append(c)
print("检查 %d 个路径型引用" % checked)
for b in bad:
    print("  ✗ 不存在：%s" % b)
print("判红 %d 项" % len(bad))
raise SystemExit(1 if bad else 0)
