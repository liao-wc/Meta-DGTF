# -*- coding: utf-8 -*-
"""**链后**：把 V1.23.37 的工作做成**独立分支**（用户授权用分支并行不同任务）。

## 分支策略（对应用户口径「等上一次验收完再并入」）
```
main              验证版（V1.23.36）—— 保持可跑、可验收
  └─ feat/v12337  V1.23.37 的工作（按需协议 + 圈级心跳 + app 同步）
```
· **不直接并入 main**：V1.23.37 要**先跑完全套测试 + 自己的真跑验收**，
  确认无误再合（这正是「等上一次验收完再并入」的落地）；
· **推分支不推 main**（默认）—— 避免把未验收的东西弄到主线上。

## 保护（很重要：git 操作是不可逆的）
1. 断言**当前在 main**（不在就停手，不乱切）；
2. 断言 **`feat/v12337` 不存在**（或显式允许覆盖）—— 不悄悄改已有分支；
3. **不自动 push**：要推就显式 `BR_PUSH=1`；
4. 每一步打印结果；任一步失败**立刻停**。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "feat/v12337"


def sh(args, check=True):
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    _out = (r.stdout or "").strip()
    _err = (r.stderr or "").strip()
    print("  $ %s" % " ".join(args))
    if _out:
        print("    " + _out.replace("\n", "\n    ")[:600])
    if _err:
        print("    [stderr] " + _err.replace("\n", "\n    ")[:400])
    if check and r.returncode != 0:
        raise SystemExit("✗ 命令失败（%s）：%s" % (r.returncode, " ".join(args)))
    return r


def main():
    # ① 保护：必须在 main
    _cur = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          cwd=HERE, capture_output=True, text=True).stdout.strip()
    print("当前分支：%s" % _cur)
    if _cur != "main":
        raise SystemExit("✗ 不在 main（在 %s）⇒ 停手，不乱切分支" % _cur)

    # ② 保护：目标分支不该已存在（除非显式允许）
    _brs = subprocess.run(["git", "branch", "--list", BRANCH],
                          cwd=HERE, capture_output=True, text=True).stdout.strip()
    if _brs and os.environ.get("BR_FORCE") != "1":
        raise SystemExit("✗ 分支 %s 已存在 ⇒ 停手（要覆盖设 BR_FORCE=1）" % BRANCH)

    # ③ 建分支（**带上当前工作区改动**：`checkout -b` 保留它们）
    print("\n① 建分支 %s（工作区改动一并带过去）" % BRANCH)
    sh(["git", "checkout", "-b", BRANCH])

    # ④ 提交（说明走文件，避免命令行转义问题）
    print("\n② 提交 V1.23.37 的工作")
    _msg = os.path.join(HERE, "_commitmsg_v12337.txt")
    if not os.path.isfile(_msg):
        print("  ⚠ 缺 %s ⇒ 先不要提交；本次只切分支" % os.path.basename(_msg))
    else:
        sh(["git", "add", "-A"])
        sh(["git", "commit", "-F", _msg])

    # ⑤ 可选推送
    if os.environ.get("BR_PUSH") == "1":
        print("\n③ 推送分支到 origin")
        sh(["git", "push", "-u", "origin", BRANCH])
    else:
        print("\n③ 未推送（要推就 BR_PUSH=1）—— 符合「未验收不上主线」")

    # ⑥ 回到 main（保持验证版工作区可用）
    print("\n④ 切回 main（**注意**：V1.23.37 的改动此刻已提交在分支上，"
          "main 的工作区会回到最后一次提交的状态）")
    sh(["git", "checkout", "main"])
    print("\n完成。分支 %s 上是 V1.23.37 的工作；main 仍是验证版。" % BRANCH)


if __name__ == "__main__":
    sys.exit(main())
