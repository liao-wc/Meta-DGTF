# -*- coding: utf-8 -*-
"""整理：把「内部数据 / 运行日志 / 杂物间 / 运行数据库」移出**版本控制**。

★ 只移出跟踪，**不删文件** —— 文件全部原地保留在磁盘上，
  只在 git 里消失（`git status` 看不到，`ls` 看得到）。
★ 方向选的是「首次公开保守」：没进公开仓库的东西以后随时能加进去；
  反过来的方向不可逆（推上去再删，历史里仍然有）。
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIT = "git"


def run(*a, check=True):
    p = subprocess.run([GIT] + list(a), cwd=str(HERE),
                       capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    if check and p.returncode != 0:
        raise SystemExit("git %s 失败：\n%s" % (" ".join(a), out))
    return out.strip()


def size_of(paths):
    tot = 0
    for rel in paths:
        fp = HERE / rel
        if fp.is_file():
            tot += fp.stat().st_size
    return sum(1 for p in paths if (HERE / p).is_file()), tot


before = [x for x in run("ls-files").split("\n") if x.strip()]
n0, s0 = size_of(before)
print("处理前：%d 个文件，%.2f MB" % (n0, s0 / 1048576))

# ---- 1. 补 .gitignore ----
NEW = """
# ── 以下四类**不进公开仓库**（文件仍在本地，只是不被 git 跟踪）──────────
# 判断口径 = 「源码/文档 保留，内部数据/运行记录 排除」。
# ★ 与项目自己的「产物 vs 证据」口径不冲突：这里是**是否公开**的取舍，
#   不是「是否删除」—— 所有文件原地保留，本地照常用。

# 内部工作记忆与自动化配置（皮皮的笔记，不适合公开）
.workbuddy/

# 顶层运行日志（306 个 60 MB）—— 本地证据，公开仓库里是噪音
# ★ 只匹配顶层：_archive/ 里的 .log 由下一条整体排除，不冲突
/*.log

# 已经归档的旧临时文件（157 个）
_archive/

# 运行记录数据库
runs.sqlite3
"""
gi = HERE / ".gitignore"
txt = gi.read_bytes().decode("utf-8")
if ".workbuddy/" not in txt:
    gi.write_bytes((txt.rstrip("\n") + "\n" + NEW).encode("utf-8"))
    print("已补 .gitignore")
else:
    print("[skip] .gitignore 已含这些规则")

# ---- 2. 移出跟踪 ----
for pat in (".workbuddy", "_archive", "runs.sqlite3"):
    run("rm", "-r", "--cached", "-q", "--ignore-unmatch", pat)
# 顶层 .log：用 pathspec 精确限定，不动子目录
logs = [x for x in before if x.endswith(".log") and "/" not in x]
if logs:
    run("rm", "--cached", "-q", "--ignore-unmatch", "--", *logs)

after_tracked = [x for x in run("ls-files").split("\n") if x.strip()]
n1, s1 = size_of(after_tracked)
print("处理后：%d 个文件，%.2f MB（移出 %d 个 / %.2f MB）"
      % (n1, s1 / 1048576, n0 - n1, (s0 - s1) / 1048576))

print()
print("移出的分类计数：")
for g, f in ((".workbuddy/", lambda r: r.startswith(".workbuddy/")),
             ("顶层 *.log", lambda r: r.endswith(".log") and "/" not in r),
             ("_archive/", lambda r: r.startswith("_archive/")),
             ("runs.sqlite3", lambda r: r == "runs.sqlite3")):
    print("   %-14s %d 个" % (g, sum(1 for r in before if f(r))))

print()
print("★ 文件是否还在磁盘上（抽 3 个验证）：")
for c in (".workbuddy/memory/MEMORY.md", "_archive/v1234",
          "运行日志示例"):
    pass
import os
checks = [".workbuddy/memory/MEMORY.md", "runs.sqlite3"]
for c in checks:
    print("   %-38s %s" % (c, "在" if os.path.exists(HERE / c) else "★ 不见了"))
print("   %-38s %s" % ("_archive/ 目录",
                       "在" if os.path.isdir(HERE / "_archive") else "★ 不见了"))
print("   %-38s %s" % ("顶层 .log 例子",
                       "在" if os.path.isfile(HERE / "v60_batch.log")
                       else "(换一个看)"))
