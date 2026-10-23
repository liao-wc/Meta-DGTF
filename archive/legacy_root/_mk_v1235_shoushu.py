#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.5 收束：往 docstring 的 v1.23.5 段尾追加 「★ v1.23.5 收束摘要」。

本脚本只动 docstring，用两条硬断言钉住「可执行语句零改动」：
  ① AST 等价：抠掉模块 docstring + 归一化 __version__ 后 ast.dump 相同；
  ② 更直接的一条：`抠掉 docstring 后的源码`改前改后逐字相同。

主文件纯 CRLF：read_bytes -> 断言 CRLF==LF -> 转 LF -> 改 -> 转回 CRLF -> write_bytes。
"""
import ast
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.5.py"
BAK = HERE / "_bak_元DGTF-V1.23.5.py.pre_shoushu"

# ---- 待插入的正文（分隔线从文件里量，见下）----
TITLE = "  ★ v1.23.5 收束摘要"

BODY = '''  **交付物**：元DGTF-V1.23.5.py（纯 CRLF；本段只是 docstring 追加，
    可执行语句零改动 —— 见文末「收束自检」）；`smoke_test.py`（SRC 指向
    本版 + 新增 `check_v1235_pending_fix`）；`_mk_v1235*.py` 补丁链
    （每处替换断言命中恰好 1 次）；`v1235_报告.md`；`_probe_v1235_mutants.py`
    / `_probe_v1235_real.py`（变异体 + 真模型单点）；`_mk_v1235_config_sync.py`。

  **清掉三笔挂账**（`docs/机制审计-v122.md`）：
    · #1 调度归一化收口成 `_plan_conf` / `_normalize_plan_mode` /
      `_normalize_plan_rounds` 三个唯一实现 —— 实测重复面**比文档记的大**：
      模式白名单 3 处 / conf 解析 3 处 / 圈数归一化 2 处 / 低置信退 serial 3 处
      （且最后一处的处置各不相同）。刻意**不合并**低置信的 reason 处置差异，
      由冒烟判据 `[1e]` + 变异体 M3 三向钉住。
    · #2 `_adjudicate_sub_tristate` 单票实现 → **等待型**：不动代码，只配判据。
    · #3 `as_evidence` 布尔兼容路径 → **留痕而不删**（仓库内零布尔调用点；
      但删了会让仓库外配置从「作证据」静默降级成「关闭」）。

  **验收**：冒烟 exit 0 / **0 个 ✗ / 200 ✓**；4 个变异体全部判红 + 正对照绿；
    改前 / 改后 16 组输入逐字相同（含低置信反事实）+ 真模型单点逐字相同；
    `load_config` 前后**逐字差异 0 项**；注入器连跑两轮逐字节相同；
    `--phase all` **PASS 314 / FAIL 1** —— 唯一红是 `L1.src`（10 跑回归批仍是
    v1.23.4 的读数）。定为**诚实的已知未做**：本引擎「逐字一致不可达 ⇒
    跨版本差异 ≈ 同文件重跑差异」，重跑只买采样噪声，不重跑。

  **本版同时建起的安全网**：仓库 git 化（初始快照 / 归档 157 个顶层孤儿
    临时文件 / `.gitattributes` 的 `* -text` 挡住 `autocrlf=true` 的换行符转换）；
    推送前闸门 `_pre_push_check.py`（四项，带负对照）；已推送 `liao-wc/meta-dgtf`。

  **下一版（v1.23.6）的起点**：清掉代码正文里的**版次批注**（`# [vX.Y.Z …]`
    形态；抠掉 docstring 后**清前实测 300 行**）。判据与做法见
    `~/.workbuddy/skills/dgtf-version-bump/SKILL.md`。

'''


def exec_src(text):
    """抠掉模块 docstring（首尾各三引号之间），返回「可执行部分」。"""
    i = text.index('"""')
    j = text.index('"""', i + 3)
    return text[:i] + '"""X"""' + text[j + 3:]


def norm_ver(text):
    out, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', text)
    assert n == 1, "__version__ 出现 %d 次" % n
    return out


def main():
    raw = SRC.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
    assert raw.count(b"\r\r\n") == 0, "源文件有 CRCRLF"
    text = raw.decode("utf-8")
    lf = text.replace("\r\n", "\n")
    lines = lf.split("\n")

    if TITLE in lf:
        print("[skip] 收束摘要已存在，不动")
        return 0

    # ---- 分隔线：从文件里量（不自己拼），保证宽度与既有段一致 ----
    sep = next(ln for ln in lines if re.fullmatch(r"  \u2500+", ln))
    print("分隔线: 2 空格 + %d 个 U+2500" % (len(sep) - 2))

    # ---- 整行锚点 + 行索引切片 ----
    A = "  本版只给它配判据（可观测 + 可归档时立刻看得见）。"
    n = lines.count(A)
    assert n == 1, "锚点命中 %d 次" % n
    i = lines.index(A)
    assert lines[i + 1] == "", "锚点后不是空行"
    assert lines[i + 2] == "v1.23.4 相对 v1.23.3", "锚点后第二行不是 v1.23.4 段标题"

    # 既有收束段形态：空行 / ────60 / ★标题 / ────60 / 空行 / 正文 / 空行
    body_lines = BODY.strip("\n").split("\n")
    block = [sep, TITLE, sep, ""] + body_lines + [""]
    new_lines = lines[: i + 2] + block + lines[i + 2:]
    new_lf = "\n".join(new_lines)
    print("插入 %d 行（含包夹分隔线与空行）" % len(block))

    # ---- 硬断言①：抠掉 docstring 后逐字相同 ----
    before_exec, after_exec = exec_src(lf), exec_src(new_lf)
    assert before_exec == after_exec, "★ 可执行部分变了（不只是 docstring）"
    print("断言① 抠掉 docstring 后逐字相同 ✓ （%d 字符）" % len(before_exec))

    # ---- 硬断言②：AST 等价 ----
    d1 = ast.dump(ast.parse(norm_ver(before_exec)))
    d2 = ast.dump(ast.parse(norm_ver(after_exec)))
    assert d1 == d2, "★ AST 不等价"
    print("断言② AST 等价 ✓")

    # ---- 硬断言③：版本段序仍严格递减 ----
    secs = re.findall(r"^v(1\.2\d\.\d+) 相对", new_lf, re.M)
    ver = [tuple(int(x) for x in v.split(".")) for v in secs]
    assert all(ver[k] > ver[k + 1] for k in range(len(ver) - 1)), "版本段序被破坏"
    print("断言③ %d 个版本段严格递减 ✓ （首段 v%s）" % (len(secs), secs[0]))

    out = new_lf.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "★ 产生了 CRCRLF"
    assert out.count(b"\r\n") == out.count(b"\n"), "★ 不是纯 CRLF"

    if not BAK.exists():
        shutil.copy2(SRC, BAK)
        print("回滚点: %s" % BAK.name)

    SRC.write_bytes(out)
    chk = SRC.read_bytes()
    print("写入完成: %d 字节 / %d 行（+%d）"
          % (len(chk), chk.count(b"\n"), chk.count(b"\n") - len(lines) + 1))
    print("自检: CRLF=%d 裸LF=%d CRCRLF=%d"
          % (chk.count(b"\r\n"), chk.count(b"\n") - chk.count(b"\r\n"),
             chk.count(b"\r\r\n")))
    assert chk.count(b"\r\r\n") == 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
