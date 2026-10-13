#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.25 隔离存档：只提交**本版相关文件**，不碰 `dgtf_app/`。

为什么需要它（而不用 `_git_save.py`）：
  `_git_save.py` 走 `git add -A`。但此刻工作区里 `dgtf_app/`（server.py / app.js /
  index.html / style.css / selftest.py / library.py / _accept*.html）有**另一个进程
  正在实时写入**（实测 app.js 大小两次读取间 145259 → 148210，`git diff --stat`
  在 545 ↔ 3280 行间跳变）。那批改动与本版 v1.23.25（结构覆盖率）无关，
  卷进来会把**半成品**落库。

  ⇒ 本脚本**只显式 add 本版文件白名单**；`_git_save.py` 的**四项防呆照跑**
    （少一项都不算数），只是把 `add -A` 换成 `add <白名单>`。
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---- 本版 v1.23.25 白名单（**只列这些**）----
WHITELIST = [
    "元DGTF-V1.23.25.py",
    "smoke_test.py",
    "dgtf_config.yaml",
    "CHANGELOG.md",
    "v12325_报告.md",
    "_mk_v12325_patch.py",
    "_mk_v12325_smoke.py",
    "_mk_v12325_config_sync.py",
    "_mk_v12325_changelog.py",
    "_cmp_v12325_structcov.py",
    "_mut_v12325.py",
    # ★ 三个 .log **不进库**：`.gitignore` 第 24 行 `/*.log` 是既有口径
    #   （「本地证据，公开仓库里是噪音」）。v1.23.24 那批也是这样存下来的
    #   （`git ls-files "*_smoke_*.log"` 历史命中 0 个）。
    #   —— `_git_save.py` 的防呆第 2 项读的是**本地文件**，与 git 跟踪无关，自洽。
    "_bak_smoke.pre_v12325.py",
    "_bak_dgtf_config.pre_v12325.yaml",
    "_bak_changelog.pre_v12325.md",
]
MSG_FILE = "_commitmsg_v12325.txt"


def git(*args, check=True):
    p = subprocess.run(["git"] + list(args), cwd=str(HERE), capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", errors="replace")
    if check and p.returncode != 0:
        raise SystemExit("git %s 失败：\n%s" % (" ".join(args), out))
    return p.returncode, out.strip()


def die(msg):
    print("✗ 拒绝存档：%s" % msg)
    sys.exit(1)


# ---- 找版本号（从文件名推导，不硬编码）----
main = HERE / "元DGTF-V1.23.25.py"
m = re.search(r"元DGTF-V(\d+\.\d+\.\d+)", main.name)
if not m:
    die("主文件名推不出版本号")
ver = m.group(1)
print("版本（从文件名推导）= v%s" % ver)

# ---- 防呆 1：.git ----
if not (HERE / ".git").is_dir():
    die("没有 .git")

# ---- 防呆 2：本版冒烟日志存在、0 个 ✗、✓ ≥ 100 ----
log = HERE / ("_smoke_v%s.log" % ver.replace(".", ""))
if not log.is_file():
    die("找不到本版冒烟日志：%s" % log.name)
txt = log.read_text(encoding="utf-8", errors="replace")
n_bad, n_ok = txt.count("\u2717"), txt.count("\u2713")
if n_bad:
    die("冒烟日志里有 %d 个 ✗ —— 先修绿再存档" % n_bad)
if n_ok < 100:
    die("冒烟日志只有 %d 个 ✓（明显没跑完/被截断）" % n_ok)

# ---- 防呆 3：outputs/ 与 .env 不许被纳入（含将要纳入的）----
rc, tracked = git("ls-files")
bad = [ln for ln in tracked.split("\n")
       if ln.startswith("outputs/") or ln == ".env"]
if bad:
    die("已跟踪里不该有的：%s" % bad[:3])
for w in WHITELIST:
    if w.startswith("outputs/") or w == ".env":
        die("白名单里混进了禁区：%s" % w)

# ---- 防呆 4：主文件纯 CRLF 且无 CRCRLF ----
b = main.read_bytes()
if b.count(b"\r\r\n"):
    die("%s 含 CRCRLF（%d 处）" % (main.name, b.count(b"\r\r\n")))
if b.count(b"\r\n") != b.count(b"\n"):
    die("%s 不是纯 CRLF" % main.name)

# ---- 防呆 5（本脚本附加）：白名单里的文件必须存在 ----
missing = [w for w in WHITELIST if not (HERE / w).exists()]
if missing:
    die("白名单里的文件不存在：%s" % missing)

# ---- 防呆 6（本脚本附加）：白名单里不许有被 .gitignore 忽略的路径 ----
#   否则 `git add` 会报 "paths are ignored" 直接失败（第一版就栽在这）。
ignored = []
for w in WHITELIST:
    rc_, out_ = git("check-ignore", "-q", "--", w, check=False)
    if rc_ == 0:
        ignored.append(w)
if ignored:
    die("白名单里有被 .gitignore 忽略的路径：%s\n"
        "    —— 要么从白名单拿掉（本地保留、不进库），要么先改 .gitignore。"
        % ignored)

print("前置检查通过：")
print("  主文件      %s（%d 行 / 纯 CRLF）" % (main.name, b.count(b"\n")))
print("  冒烟        %d ✓ / %d ✗" % (n_ok, n_bad))
print("  已纳入       %d 个文件（git 全库）" % len(tracked.split("\n")))
print("  本版白名单   %d 个文件" % len(WHITELIST))

# ---- 提交（显式 add，不碰 dgtf_app/）----
# ★ 先记录 dgtf_app/ 的当前摘要，提交后复核「没被带进去」
rc, pre_app = git("status", "--short", "--", "dgtf_app/")

git("-c", "commit.gpgsign=false", "add", "--", *WHITELIST)
rc, staged = git("diff", "--cached", "--name-only")
staged_list = [x for x in staged.split("\n") if x]
leak = [x for x in staged_list if x.startswith("dgtf_app/")]
if leak:
    git("reset", "-q", "--", "dgtf_app/")
    die("暂存区里混进了 dgtf_app/：%s —— 已 reset，请检查白名单" % leak[:5])

print("\n待提交 %d 个条目（全部在白名单内）：" % len(staged_list))
for x in staged_list:
    print("  ·", x)

if not staged_list:
    print("\n暂存区为空 —— 没有新改动，跳过提交。")
    sys.exit(0)

git("-c", "commit.gpgsign=false", "commit", "-q", "-F", str(HERE / MSG_FILE))

# ---- 提交后复核 ----
rc, post_app = git("status", "--short", "--", "dgtf_app/")
if post_app != pre_app:
    print("⚠️ dgtf_app/ 状态在提交期间变化了（那是并行进程在写，不是本提交造成的）")
    print("   pre :", pre_app[:200])
    print("   post:", post_app[:200])

rc, lg = git("log", "--oneline", "-3")
print("\n存档完成：")
print(lg)
rc, still = git("status", "--short")
print("\n剩余未提交（应只有 dgtf_app/ 与临时说明文件）：")
print(still or "（干净）")
