# -*- coding: utf-8 -*-
"""一次性恢复：单进程内建索引 → 提交 → 当场校验。

★ 为什么必须写在同一个进程里：本机沙箱 overlay 不稳定 —— 不同命令调用可能
  看到不同的文件系统视图（本轮多次出现「刚写的对象下一句就没了」）。
  所以恢复不能分多步做，必须在**一次执行**里完成并**立刻回读校验**。
★ 用「删掉索引 + `git add -A` 从工作区重建」而不是 `git reset --mixed`：
  索引本身已被 overlay 搞脏（引用不存在的对象），重建比修补可靠。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "e095d24eb6b17609acf37fcec56996202aaca7ad"   # 唯一完整的快照


def sh(*a, check=False):
    p = subprocess.run(["git"] + list(a), cwd=str(HERE),
                       capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    if check and p.returncode != 0:
        print("  ! git %s -> %d\n%s" % (" ".join(a), p.returncode, out))
    return p.returncode, out.strip()


print("== 0. 起始状态 ==")
rc, out = sh("cat-file", "-e", BASE + "^{tree}")
print("  基准快照可用:", rc == 0)
rc, out = sh("rev-list", "--objects", BASE, "--missing=print")
missing = [x for x in out.split("\n") if x.startswith("?")]
print("  基准快照缺失对象: %d" % len(missing))
if missing:
    print("  ★ 基准也不完整，中止（不要在半坏的基础上写）")
    sys.exit(1)

print()
print("== 1. 删掉被搞脏的索引，指向基准快照 ==")
idx = HERE / ".git" / "index"
if idx.exists():
    idx.unlink()
    print("  已删除旧索引")
sh("update-ref", "refs/heads/main", BASE, check=True)
sh("symbolic-ref", "HEAD", "refs/heads/main", check=True)
rc, out = sh("rev-parse", "--short", "HEAD")
print("  HEAD ->", out)

print()
print("== 2. 从工作区重建索引（.gitignore 生效）==")
rc, out = sh("add", "-A", check=True)
if rc != 0:
    sys.exit(1)
rc, out = sh("status", "--short", "--untracked-files=no")
print("  已暂存条目数:", len([x for x in out.split("\n") if x.strip()]))

print()
print("== 3. 提交 ==")
msg = HERE / "_recover_msg.txt"
rc, out = sh("-c", "commit.gpgsign=false", "commit", "-q", "-F", str(msg))
print("  提交退出码:", rc)
if rc != 0:
    print(out[:800])
    sys.exit(1)

print()
print("== 4. 当场校验（同一进程视图内）==")
rc, head = sh("rev-parse", "HEAD")
print("  新 HEAD:", head[:12])
rc, _ = sh("cat-file", "-e", head + "^{commit}")
print("  commit 对象可读:", rc == 0)
rc, out = sh("rev-list", "--objects", head, "--missing=print")
miss = [x for x in out.split("\n") if x.startswith("?")]
print("  缺失对象: %d" % len(miss))
rc, out = sh("ls-tree", "-r", head)
print("  树里的文件数:", len([x for x in out.split("\n") if x.strip()]))
rc, out = sh("log", "--oneline")
print("  历史:")
for ln in out.split("\n"):
    print("    ", ln)
print()
print("== 5. 落盘再读一遍（防 overlay 假象）==")
rc, head2 = sh("rev-parse", "HEAD")
rc, _ = sh("cat-file", "-e", head2 + "^{commit}")
print("  二次读取仍可解:", rc == 0 and head2 == head)
sys.exit(0 if (not miss and rc == 0) else 1)
