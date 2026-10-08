# -*- coding: utf-8 -*-
"""对照实验：证明 .gitattributes 的 `* -text` 真的挡住 autocrlf 的转换。

设计（同一份 CRLF 文件，只换一个变量）：
  臂 A：core.autocrlf=true，无 .gitattributes  -> 预期 blob 里 CR 被吃掉
  臂 B：core.autocrlf=true + `* -text`         -> 预期 blob 保留 CR（= 保护生效）
  臂 C：core.autocrlf=false（本仓库现状）       -> 预期保留 CR

★ 只测「仓库里存的字节」，不看工作区 —— 工作区永远是 CRLF，
  被吃掉的是 commit 那一侧，这正是本项目断言会炸的地方。
"""
import os
import shutil
import subprocess
import tempfile

GIT = r"C:\Program Files\Git\cmd\git.exe"
PAYLOAD = "行一\r\n行二\r\n行三\r\n"


def sh(*a, cwd):
    p = subprocess.run([GIT] + list(a), capture_output=True, text=True,
                       cwd=cwd)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def trial(autocrlf, gitattributes):
    d = tempfile.mkdtemp(prefix="_crlf_arm_")
    try:
        sh("init", "-q", cwd=d)
        sh("config", "user.name", "t", cwd=d)
        sh("config", "user.email", "t@t", cwd=d)
        sh("config", "core.autocrlf", autocrlf, cwd=d)
        if gitattributes:
            with open(os.path.join(d, ".gitattributes"), "wb") as f:
                f.write(gitattributes.encode("utf-8"))
        with open(os.path.join(d, "sample.txt"), "wb") as f:
            f.write(PAYLOAD.encode("utf-8"))
        sh("add", "-A", cwd=d)
        sh("commit", "-q", "-m", "t", cwd=d)
        rc, blob, err = sh("cat-file", "-p", "HEAD:sample.txt", cwd=d)
        # blob 是以文本方式返回的，用 -p 会按字节给；数一下 CR
        raw = subprocess.run([GIT, "show", "HEAD:sample.txt"], cwd=d,
                             capture_output=True).stdout
        return raw.count(b"\r\n"), len(raw)
    finally:
        try:
            shutil.rmtree(d)
        except OSError:
            pass


print("同一份内容：'行一\\r\\n行二\\r\\n行三\\r\\n'（3 个 CRLF）")
print()
arms = [
    ("A  autocrlf=true，无 .gitattributes", "true", None),
    ("B  autocrlf=true + `* -text`", "true", "* -text\n"),
    ("C  autocrlf=false（本仓库现状）", "false", None),
]
results = {}
for name, ac, ga in arms:
    crlf, size = trial(ac, ga)
    results[name] = crlf
    verdict = "保留 CRLF ✓" if crlf == 3 else "★ CR 被吃掉（blob 只有 LF）"
    print("  %-36s 仓库里 CRLF=%d  -> %s" % (name, crlf, verdict))

print()
ok = (results[arms[0][0]] == 0 and results[arms[1][0]] == 3
      and results[arms[2][0]] == 3)
print("结论：%s" % ("A 会损坏、B 与 C 都保住 —— `* -text` 确实有保护作用，"
                    "且保护强度等同 autocrlf=false"
                    if ok else "★ 与预期不符，需要重新查"))
