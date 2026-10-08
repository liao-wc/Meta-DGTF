# -*- coding: utf-8 -*-
"""合并远程已存在的 Initial commit，让推送成为**快进**（无需 force）。

远程 liao-wc/meta-dgtf 上有一个 GitHub Desktop 自动生成的 Initial commit
（127b60b，仅含 README.md），与本仓库历史不相干。合并它 → 推送变成 fast-forward。

★ 同样必须在**单进程**内完成 + 当场校验（本机 overlay 不稳定）。
★ 远程那个 commit 从本机脚手架 meta-dgtf/ 取（不走网络、不需要认证）。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = str(HERE / "meta-dgtf")
REMOTE_SHA = "127b60b83b362bd7ca907d3678bf995f6dfd2732"


def sh(*a, check=False):
    p = subprocess.run(["git"] + list(a), cwd=str(HERE),
                       capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    if check and p.returncode != 0:
        print("  ! git %s -> %d\n%s" % (" ".join(a), p.returncode, out))
    return p.returncode, out.strip()


print("== 0. 确认 meta-dgtf/ 没被跟踪 ==")
rc, out = sh("ls-files", "meta-dgtf")
print("  被跟踪的 meta-dgtf 文件数:", len([x for x in out.split("\n") if x.strip()]),
      "(应为 0)")

print()
print("== 1. 从脚手架取回远程初始提交 ==")
rc, out = sh("fetch", SCAFFOLD, REMOTE_SHA, check=True)
rc, _ = sh("cat-file", "-e", REMOTE_SHA)
print("  127b60b 已在对象库:", rc == 0)
if rc != 0:
    sys.exit(1)

print()
print("== 2. 合并（允许无关历史，保留远程 README）==")
rc, out = sh("merge", "--allow-unrelated-histories", "--no-ff",
             "--no-commit", REMOTE_SHA)
print("  merge 退出码:", rc)
if rc != 0:
    print(out[:600])
    sys.exit(1)
rc, out = sh("-c", "commit.gpgsign=false", "commit", "-q",
             "-m", "合并 GitHub 自动生成的 Initial commit（保留 README）\n\n"
                   "liao-wc/meta-dgtf 由 GitHub Desktop 于 05:30 创建，远程 main 上有一个\n"
                   "自动生成的 Initial commit（127b60b，仅含 README.md：\n"
                   "「# meta-dgtf / 道生三阶模型」）。\n\n"
                   "本仓库与它历史不相干。选择**合并**而不是强推覆盖：\n"
                   "  · 保留远程已有内容；\n"
                   "  · 让推送变成普通快进，不需要 --force。\n\n"
                   "★ 远程那个 commit **不含** .gitattributes（脚手架里那份带\n"
                   "  `* text=auto` 的没有被提交），所以本仓库的 `* -text`\n"
                   "  （字节保真）不会被覆盖 —— 这点很关键：`* text=auto` 会打开\n"
                   "  换行符自动转换，直接打穿本项目所有「纯 CRLF」断言。\n\n"
                   "本次合并只新增 README.md 一个文件。")
print("  commit 退出码:", rc)
if rc != 0:
    print(out[:600])
    sys.exit(1)

print()
print("== 3. 当场校验 ==")
rc, head = sh("rev-parse", "HEAD")
print("  新 HEAD:", head[:12])
rc, out = sh("rev-list", "--objects", "HEAD", "--missing=print")
miss = [x for x in out.split("\n") if x.startswith("?")]
print("  缺失对象:", len(miss))
rc, out = sh("ls-tree", "-r", "HEAD")
files = [x for x in out.split("\n") if x.strip()]
print("  树里的文件数:", len(files))
rc, out = sh("show", "--stat", "--oneline", "--format=%h %s", "HEAD", "-1")
print("  本次合并引入的文件:")
for ln in out.split("\n")[:4]:
    print("    ", ln[:100])
rc, out = sh("rev-list", "--left-right", "--count", REMOTE_SHA + "...HEAD")
print("  远程独有 / 本地独有:", out)

print()
print("== 4. 是否已是快进关系（推送不需要 force）==")
rc, _ = sh("merge-base", "--is-ancestor", REMOTE_SHA, "HEAD")
print("  远程初始提交是本地的祖先:", rc == 0, "→",
      "快进推送 ✓" if rc == 0 else "★ 需要 force")

print()
print("== 5. 试推一次（无认证，预期失败；只看错在哪）==")
import os
env = dict(os.environ)
env["GIT_TERMINAL_PROMPT"] = "0"
p = subprocess.run(["git", "push", "--dry-run", "-u", "origin", "main"],
                   cwd=str(HERE), capture_output=True, env=env, timeout=120)
err = (p.stderr or b"").decode("utf-8", "replace").strip()
print("  退出码:", p.returncode)
print("  报错:", err[:300] if err else "(无)")
sys.exit(0)
