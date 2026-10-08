# -*- coding: utf-8 -*-
"""R3：把顶层「孤儿」临时文件按版本归档到 _archive/vXXXX/。

硬规则（宁少动不多动）：
  1. **只移动，绝不删除**（且此前已有 git 首次提交 + v1.23.5 提交，完全可逆）。
  2. 判定「孤儿」的引用源是**全库**（所有顶层 .py / .md / .yaml / .json），
     不是只看当前版 —— 只要**任何**脚本或文档提到过这个文件名，就不动。
  3. `_mk_*`（补丁链，skill 记为唯一事实源）、`_bak_*`（回滚点）、
     `_baseline_*`（AST 对照基线）**一律留在顶层**。
  4. 扩到版本子目录；无法判版本的进 `_archive/_misc/`。
  5. 跑完之后要能重跑冒烟证明没破坏（由调用方做）。

用法：python _archive_top.py --dry    # 只看清单
      python _archive_top.py --go     # 真移
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH = HERE / "_archive"

KEEP_PREFIX = ("_mk_", "_bak_", "_baseline_", "_archive", "_idem_")
CURRENT = "v1235"        # 当前版的证据文件（冒烟日志 / 探针 before-after）留顶层
EXTS = (".py", ".log", ".json", ".txt")


def all_mentions():
    """全库（.py/.md/.yaml/.json）文本里出现过的文件名集合。"""
    blob = []
    for p in HERE.glob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".py", ".md", ".yaml", ".json", ".txt"):
            continue
        try:
            blob.append(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    for d in ("docs", ".workbuddy"):
        for p in (HERE / d).rglob("*"):
            if p.is_file() and p.suffix.lower() in (".py", ".md", ".yaml",
                                                    ".json", ".txt"):
                try:
                    blob.append(p.read_text(encoding="utf-8",
                                            errors="replace"))
                except Exception:
                    pass
    return "\n".join(blob)


BLOB = all_mentions()


def ver_of(name: str):
    m = re.search(r"(v1\.21\.\d+|v1\.22(?:\.\d+)?|v1\.23\.\d+|v12\d\d|v\d{2})",
                  name)
    if m:
        return m.group(1).replace(".", "")
    return None


def main():
    go = "--go" in sys.argv
    cand = []
    for p in sorted(HERE.glob("_*")):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        if p.name.startswith(KEEP_PREFIX):
            continue
        if p.name in BLOB:          # 被任何脚本/文档提到 → 不动
            continue
        if (ver_of(p.name) or "") == CURRENT:   # 当前版自己的证据留在顶层
            continue
        cand.append(p)

    groups = {}
    for p in cand:
        v = ver_of(p.name) or "_misc"
        groups.setdefault(v, []).append(p)

    total = 0
    print("=== 归档候选（只移不删）===")
    for v in sorted(groups):
        fs = groups[v]
        sz = sum(f.stat().st_size for f in fs) / 1024
        print("  %-10s %3d 个  %.0f KB" % (v, len(fs), sz))
        total += len(fs)
    print("  ---- 合计 %d 个" % total)
    print()
    print("=== 被引用/受保护而**留下**的同类文件 ===")
    kept = 0
    for p in sorted(HERE.glob("_*")):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        if p.name in BLOB or not p.name.startswith(KEEP_PREFIX):
            kept += 1
    print("  %d 个（含全部 _mk_ / _bak_ / _baseline_）" % kept)

    if not go:
        print()
        print("★ dry-run，未移动任何文件。加 --go 真移。")
        return 0

    moved = 0
    for v in sorted(groups):
        d = ARCH / v
        d.mkdir(parents=True, exist_ok=True)
        for f in groups[v]:
            dst = d / f.name
            if dst.exists():
                print("  ! 目标已存在，跳过：%s" % dst)
                continue
            shutil.move(str(f), str(dst))
            moved += 1
    print()
    print("已移动 %d 个文件到 %s/" % (moved, ARCH.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
