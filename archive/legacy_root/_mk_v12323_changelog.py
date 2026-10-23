#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v1.23.23 的变更记录插进仓库根 `CHANGELOG.md`（最新在最前）。

CHANGELOG.md 是**纯 CRLF**：read_bytes -> 断言 -> 转 LF -> 插 -> 转回 -> write_bytes。
幂等：哨兵盯**已有段标题**。

    python _mk_v12323_changelog.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "CHANGELOG.md"

HEAD = "v1.23.23 相对 v1.23.22"
ANCHOR = "v1.23.22 相对 v1.23.21"

SECTION = """v1.23.23 相对 v1.23.22

【要解决的问题】工作台的日志窗口里，**阴阳视角那一块的最后一行被砍在半句上**
  （实测 `- [concept] 纠缠熵面积律不能单`）。查下来**不是前端裁的** ——
  `outputs/<tid>.run.log` 里就是这行：引擎有**六处**日志回显写死了字符上限，
  而模型返回的是**多行正文**，字符数一到就停在某一行中间；完整正文又不在这一层
  的日志里（`view 全文` 折叠块只覆盖 view 条那一段）⇒ 读者看到的就是半截话。

【改了哪几处】
  1. 新增模块级纯函数 `_vp_preview(text, limit=4000)`：**按整行截断** —— 切点取
     `limit` 之前最后一个换行；真被截断时补一行 `…（预览到此，另有 N 字未显示）`，
     **不静默丢内容**（与 `dump_round`「不挑字段、不截断」同一条纪律）。
     `limit` 默认 4000 对视图正文（4~8 行 / 200~600 字）等于不截断。
  2. **六处**回显统一走它，原来各写一个上限：
     · `_expand_view_once`          `raw[:200]`        （阴阳视角正文，用户实测的那处）
     · `_expand_pair_merged_once`   `(raw or '')[:160]`（阴阳合并版）
     · 候选清单                      `c.desc[:50]`
     · 未判子问题清单                `s['question'][:50]`
     · 回流硬执行拦下的重现候选       `d[:40]`
     · 子问题推进的目标              `e['target'][:40]`

【影响面】只改**日志文本**：产物 md / packed.json / 检索行为 / 判定行为**逐字未变**；
  日志会变长，多出的正是原先被砍掉的那部分。无新增配置键。
【怎么退回旧行为】把六处 `_vp_preview(x)` 换回原来的切片即可（没有配置开关）。
【未做】`[{i}] {c.desc}` 这类**清单**仍然是「一条一行」的格式，不做换行折行 ——
  那是渲染格式，不是截断。

"""

SUMMARY = """★ v1.23.23 收束摘要
  ────────────────────────────────────────────────────────────
  **交付物**：元DGTF-V1.23.23.py（18385 行 CRLF）+ 本段 changelog + 冒烟判据
    `check_v12323_view_echo_full`。
  **改了什么**：新增 `_vp_preview`（按整行截断 + 可见痕），六处日志回显的上限
    （`raw[:200]` / `[:160]` / `c.desc[:50]` / `s['question'][:50]` / `d[:40]` /
    `e['target'][:40]`）全部取消 —— 「阴阳视角内容没显示完全」的**根因在引擎**，
    不在前端。
  **验收**：探针 `_probe_v12323_echo.py` 改前 0/3、改后 18/18（含真实日志样例）；
    变异体 8/8 被判红；全套冒烟 exit 0 / 0 ✗ / ✓ 见 `_smoke_v12323.log`。
  **未做**：清单类（候选项逐条）不做折行；`show_dual` 的条数上限不动。
"""


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0 and b.count(b"\r") == b.count(b"\r\n")
    p.write_bytes(b)


def main() -> int:
    cur = read_crlf(LOG).replace("\r\n", "\n")

    if HEAD in cur:
        print("  · v1.23.23 段已存在，跳过插入")
    else:
        assert cur.count("\n" + ANCHOR + "\n") == 1, \
            "锚点 %r 命中 %d 次" % (ANCHOR, cur.count("\n" + ANCHOR + "\n"))
        cur = cur.replace("\n" + ANCHOR + "\n", "\n" + SECTION + ANCHOR + "\n")
        print("  ✓ 插入 v1.23.23 段（在 v1.23.22 段之前）")

    if "★ v1.23.23 收束摘要" in cur:
        print("  · 收束摘要已存在")
    else:
        cur = cur.rstrip("\n") + "\n"
        # 收束摘要落在**本版段尾**：插在下一个段标题之前
        nxt = "\n" + ANCHOR + "\n"
        assert cur.count(nxt) == 1
        cur = cur.replace(nxt, "\n" + SUMMARY + "\n" + ANCHOR + "\n")
        print("  ✓ 追加 ★ v1.23.23 收束摘要（落在本版段尾）")

    write_crlf(LOG, cur)

    # 结构性自检
    back = read_crlf(LOG).replace("\r\n", "\n")
    heads = re.findall(r"^v(\d+(?:\.\d+)+) 相对", back, re.M)
    assert heads[0] == "1.23.23", "首段不是 v1.23.23：%s" % heads[:3]
    assert heads[:4] == ["1.23.23", "1.23.22", "1.23.21", "1.23.20"], \
        "段序不是严格递减：%s" % heads[:6]
    sums = re.findall(r"^★ v\d+(?:\.\d+)+ 收束摘要", back, re.M)
    assert len(sums) == len(set(sums)), "收束摘要标题重复"
    assert "★ v1.23.23 收束摘要" in sums, "本版收束摘要没写进去"
    # 收束摘要必须在本版段内（v1.23.22 段标题之前）
    assert back.index("★ v1.23.23 收束摘要") < back.index("\n" + ANCHOR + "\n")
    print("  ✓ 自检：段数 %d、首段 %s、段序递减、收束摘要 %d 条不重复"
          % (len(heads), heads[0], len(sums)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
