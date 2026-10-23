# -*- coding: utf-8 -*-
"""盘点：reflog 里每个提交的对象是否真的存在。

不猜「丢了什么」，逐个 `git cat-file -e <sha>` 验。
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh(*a):
    p = subprocess.run(["git"] + list(a), cwd=str(HERE),
                       capture_output=True)
    return p.returncode, ((p.stdout or b"") + (p.stderr or b"")).decode(
        "utf-8", "replace")


# 从 reflog 取出全部提交（新→旧）
_, log = sh("reflog", "--date=iso")
shas = []
for ln in log.split("\n"):
    parts = ln.split()
    if len(parts) >= 2 and len(parts[0]) == 40:
        if parts[0] not in shas:
            shas.append(parts[0])
    if len(parts) >= 2 and len(parts[1]) == 40:
        if parts[1] not in shas:
            shas.append(parts[1])

print("reflog 里的提交候选：%d 个" % len(shas))
print()
ok, bad = [], []
for s in shas:
    rc, _ = sh("cat-file", "-e", s + "^{commit}")
    rc2, msg = sh("log", "-1", "--format=%h %ad %s", "--date=short", s)
    label = msg.strip() if rc2 == 0 else "(对象缺失)"
    (ok if rc == 0 else bad).append((s, label))
    print("  %s  %s" % ("✓" if rc == 0 else "✗", label[:90]))

print()
print("对象存在 %d 个 / 缺失 %d 个" % (len(ok), len(bad)))

# 逐个 ref 与 HEAD
print()
print("== 引用与 HEAD ==")
for r in ("HEAD", "refs/heads/main"):
    rc, out = sh("rev-parse", "--verify", r)
    print("  %-16s -> %s" % (r, out.strip().split("\n")[0] if rc == 0
                             else "读不到"))

print()
print("== 对象库 ==")
for c in (".git/objects/pack", ".git/objects"):
    p = HERE / c
    if p.is_dir():
        fs = [f for f in p.rglob("*") if f.is_file()]
        print("  %-26s %d 个文件" % (c, len(fs)))
for f in sorted((HERE / ".git/objects/pack").glob("*.pack")):
    print("  pack: %s  %.1f MB" % (f.name, f.stat().st_size / 1048576))

print()
print("== 工作区文件是否完好（抽查）==")
for f in ("元DGTF-V1.23.5.py", "smoke_test.py", "dgtf_config.yaml",
          ".gitignore", ".gitattributes", "_git_save.py"):
    fp = HERE / f
    print("  %-24s %s" % (f, ("%.1f KB" % (fp.stat().st_size / 1024))
                          if fp.is_file() else "★ 不见了"))
