# -*- coding: utf-8 -*-
"""每版定稿的固定存档步骤（版本迭代流程第 11 步）。

为什么要有这一步：在 v1.23.5 之前，本项目的「版本管理」是 39 份主文件全量
拷贝 + 8 份 `_bak_*` 手工备份 —— 任何一次误删主文件或产物都不可逆。
现在每一版定稿都留一个 git 落点，所有改动可逆。

用法：
    python _git_save.py                  # 说明自动从最新主文件推导
    python _git_save.py "v1.23.6：<主题>"

行为：
  · 前置防呆（**任一不通过就拒绝提交**）：
      1. `.git` 存在；
      2. 冒烟日志 `_smoke_<ver>.log` 存在且 0 个 ✗（没跑绿不存档）；
      3. `outputs/` 与 `.env` **不在**已纳入清单里（防把 64MB 产物 / 密钥提交进去）；
      4. 主文件纯 CRLF 且无 CRCRLF。
  · `git add -A` + `git commit`（无改动则跳过，不算失败）。
  · 打印最近 3 条历史。
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ★ 本机没有系统级 git（Windows PATH 里没有任何含 git.exe 的目录）。唯一的
#   git 是 WorkBuddy 自带的 PortableGit。所以「找不到 git」不是异常，是常态 ——
#   这里给出一条能直接照抄的修法，而不是抛一个英文 traceback。
_GIT_HINT = """\
找不到 git —— 本机 Windows PATH 里没有 git.exe。

三种走法：
  ① 让皮皮跑（最省事）：把命令告诉它，它在项目目录里执行。
  ② 用 WorkBuddy 自带的 Git Bash（临时用）：
       打开  "C:\\Users\\18432\\.workbuddy\\binaries\\PortableGit\\versions\\1.2.0\\bin\\bash.exe"
       然后  cd /c/Users/18432/Desktop/元DGTF-多模并行架构
     缺点：那是 WorkBuddy 的内部目录，随它升级/清理可能变动。
  ③ 把 git 永久加进 PATH（推荐）：
       Win 键 → 搜「环境变量」→ 编辑用户环境变量 → Path → 新建 →
       粘贴  C:\\Users\\18432\\.workbuddy\\binaries\\PortableGit\\versions\\1.2.0\\cmd
       → 确定 → **重开终端** → git --version 验证。
     缺点：路径里带版本号，WorkBuddy 升级后要重加。
     更稳的是装独立的 Git for Windows（git-scm.com），装完自动进 PATH 且带右键菜单。
"""


def usage():
    print("""用法：
    python _git_save.py                  说明自动从最新主文件推导
    python _git_save.py "v1.23.NN：<主题>"
    python _git_save.py -F <说明文件>      ← 多行 / 含反引号或反斜杠时**用这个**
    python _git_save.py --help

  ★ 为什么要有 -F：命令行参数会先过一遍 bash。说明里的**反引号会被当命令替换
    执行**（实测 stderr 冒出「__pycache__: command not found」，因为 `* -text`
    里的 `*` 展开了目录名），Windows 路径的反斜杠也会被 MSYS 转掉。
    多行说明一律写成文件再传。

它会先做四项防呆（任一不过就拒绝提交）：
    1. .git 存在
    2. 本版冒烟日志存在且 0 个 ✗（且 ✓ >= 100，防日志被截断）—— 没跑绿不存档
    3. outputs/ 与 .env 不在 git ls-files 里
    4. 主文件纯 CRLF 且 CRCRLF == 0
工作区本来就干净时**跳过而不是报错**。

手动常敲的几条（都要**在项目目录里**跑，git 靠目录里的 .git 认仓库）：
    git status                      # 改了哪些文件
    git log --oneline               # 历次存档，最新在最上
    git show --stat HEAD            # 最近这次存档动了哪些文件
    git diff --stat                 # 还没存档的改动，只看文件与行数
    git checkout <commit> -- <文件>  # 从某次存档里捞回一个文件
    git -C "C:\\Users\\18432\\Desktop\\元DGTF-多模并行架构" status   # 不在目录里时

绝不能碰：
    git clean -fdx        # 会连 outputs/（64MB 真跑产物）一起删 —— 最危险的一条
    git reset --hard      # 丢弃全部未存档改动
    git checkout -- .     # 同上，整区重置
""")


def git(*args, check=True):
    if shutil.which("git") is None:
        print(_GIT_HINT)
        sys.exit(1)
    p = subprocess.run(["git"] + list(args), cwd=str(HERE),
                       capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8",
                                                        errors="replace")
    if check and p.returncode != 0:
        raise SystemExit("git %s 失败：\n%s" % (" ".join(args), out))
    return p.returncode, out.strip()


def die(msg):
    print("✗ 拒绝存档：%s" % msg)
    sys.exit(1)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        usage()
        return 0

    # ---- 找最新主文件 ----
    vers = []
    for p in HERE.glob("元DGTF-V1.*.py"):
        m = re.search(r"元DGTF-V(\d+\.\d+\.\d+)", p.name)
        if m and "rc" not in p.name:
            vers.append((tuple(int(x) for x in m.group(1).split(".")),
                         m.group(1), p))
    if not vers:
        die("找不到主文件 元DGTF-V1.x.y.py")
    vers.sort()
    _, ver, main = vers[-1]

    # ---- 1. .git ----
    if not (HERE / ".git").is_dir():
        die("没有 .git —— 先 git init")

    # ---- 2. 冒烟必须已跑绿 ----
    _digits = ver.replace(".", "")
    log = HERE / ("_smoke_v%s.log" % _digits)
    if not log.is_file():
        log = HERE / ("_smoke_v%s_final.log" % _digits)
    if not log.is_file():
        die("找不到本版冒烟日志（期望 _smoke_v%s.log）—— 先跑 smoke_test.py"
            % _digits)
    txt = log.read_text(encoding="utf-8", errors="replace")
    n_bad = txt.count("\u2717")
    n_ok = txt.count("\u2713")
    if n_bad:
        die("冒烟日志里有 %d 个 ✗ —— 先修绿再存档" % n_bad)
    if n_ok < 100:
        die("冒烟日志只有 %d 个 ✓（明显没跑完/被截断）" % n_ok)

    # ---- 3. outputs/ 与 .env 不许被纳入 ----
    rc, tracked = git("ls-files")
    bad = [ln for ln in tracked.split("\n")
           if ln.startswith("outputs/") or ln == ".env"]
    if bad:
        die("这些不该进版本库：%s" % bad[:3])

    # ---- 4. 主文件 CRLF 体检 ----
    b = main.read_bytes()
    if b.count(b"\r\r\n"):
        die("%s 含 CRCRLF（%d 处）" % (main.name, b.count(b"\r\r\n")))
    if b.count(b"\r\n") != b.count(b"\n"):
        die("%s 不是纯 CRLF" % main.name)

    print("前置检查通过：")
    print("  主文件      %s（%d 行 / 纯 CRLF）" % (main.name, b.count(b"\n")))
    print("  冒烟        %d ✓ / %d ✗" % (n_ok, n_bad))
    print("  已纳入       %d 个文件" % len(tracked.split("\n")))

    # ---- 提交 ----
    rc, st = git("status", "--short")
    if not st:
        print("\n工作区本来就是干净的 —— 没有新改动，跳过提交。")
        rc, lg = git("log", "--oneline", "-3")
        print(lg)
        return 0

    changed = len(st.split("\n"))
    msg_file = None
    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] in ("-F", "--msg-file"):
        msg_file = argv[1]
    elif len(argv) == 1 and Path(argv[0]).is_file():
        msg_file = argv[0]

    if msg_file is not None:
        p_msg = Path(msg_file)
        if not p_msg.is_file():
            die("说明文件不存在：%s" % msg_file)
        msg = p_msg.read_text(encoding="utf-8")
        print("\n待提交 %d 个条目，说明取自文件：%s" % (changed, p_msg.name))
    else:
        msg = argv[0] if argv else "%s：定稿存档" % ver
        print("\n待提交 %d 个条目，说明：%s" % (changed, msg))
        if any(c in msg for c in ("`", "\\")):
            print("  ⚠️ 说明里含反引号或反斜杠 —— bash 会先处理它们（反引号会被当\n"
                  "     命令替换执行、反斜杠会被 MSYS 转义），多行说明请写成文件后用\n"
                  "     `python _git_save.py -F <文件>` 传入。")

    if msg_file is not None:
        # ★ 说明文件自己不该被提交进去 —— 否则每用一次 -F 就多跟踪一个临时
        #   文件（自指：提交它自己的那条提交把它带进去）。
        _mf = Path(msg_file)
        try:
            _rel = _mf.resolve().relative_to(HERE).as_posix()
        except Exception:
            _rel = _mf.name
        git("-c", "commit.gpgsign=false", "add", "-A", "--",
            ":(exclude)" + _rel)
        git("-c", "commit.gpgsign=false", "commit", "-q", "-F", str(msg_file))
    else:
        git("-c", "commit.gpgsign=false", "add", "-A")
        git("-c", "commit.gpgsign=false", "commit", "-q", "-m", msg)
    rc, lg = git("log", "--oneline", "-3")
    print("\n存档完成：")
    print(lg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
