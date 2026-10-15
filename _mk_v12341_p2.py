# -*- coding: utf-8 -*-
"""v1.23.41 · P2：`excavate` 方向口径统一（文档/声明 + 显示）。

**口径矛盾**：模块声明（3253）说「每条读数越大越接近目标」、docstring（3353）说
「读数 = 1 − 边际新增」；但实现（3377）= 原始边际新增率、冒烟判据⑫（还在挖 > 已挖尽）
都取「**小=好**」。⇒ 声明/docstring 与 实现/判据 矛盾。

**修法（不改值、不改判据钉住的口径）**：
  ① 模块声明改为**方向不统一**的准确表述（三轴越大越好，excavate 距离型越小越好）；
  ② docstring 改准确（顺带修「分子=aspect_units/分母=圈数」的旧公式残留）；
  ③ 加 `_LG_HINT`，让 `goal_verdict` 对 excavate 给方向提示（防「挖尽：excavate=0.000」
     被误读成「一分没挖」）。
★ 零行为差：只动**注释/文档/显示文案**，读数取值与停止/指引判据**一字不动**。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.41.py")


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    out = s2.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(out)
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return out


# ── ① 模块声明 ──────────────────────────────────────────────────────
DECL_OLD = ("#:   ★ 每条读数都是「**越大越接近该层目标**」，但**各自独立成轴** ——\n"
            "#:     绝不合成一个总分（红线「未对齐合法」：不同层的目标本就不在同一尺度）。")
DECL_NEW = ("#:   ★ 读数**方向不统一**（守「未对齐合法」）：`settle`/`fuse`/`crystallize`\n"
            "#:     是「**越大越接近**该层目标」；`excavate` 是**距离型**（**越小** =\n"
            "#:     边际新增越低 = 越接近挖尽）⇒ 消费方**不可**用「越大越好」一刀切。\n"
            "#:   ★ 各行**独立成轴**，绝不合成一个总分（不同层的目标本就不在同一尺度）。")

# ── ② docstring ─────────────────────────────────────────────────────
DOC_OLD = ("      · `0` 修行 —— `excavate` = 层面挖掘的**边际新增趋零度**。\n"
           "        分子 = `aspect_units` 数，分母 = 实际跑的圈数（`rounds_run`）。\n"
           "        ★ 语义：修行层要在**最少圈数**里把层面挖尽。若圈数多而层面不再增长\n"
           "          （比值趋 0）⇒ 已「挖到不能再挖」⇒ **趋近无穷收敛**。\n"
           "          故本读数 = **1 − 归一化边际新增**：边际新增越低 ⇒ 读数越高。\n"
           "        辅读：`divergence.state == \"收敛\"/\"停滞\"` ⇒ 属于「趋近收敛」。")
DOC_NEW = ("      · `0` 修行 —— `excavate` = 层面挖掘的**边际新增率**（Heaps 饱和 ΔV/Δn）。\n"
           "        来源：`aspect_hist`（逐圈累计层面数）⇒ 末段新增 / 上段新增\n"
           "        （`_lg_aspect_margin`）。\n"
           "        ★ 语义：修行层要在**最少圈数**里把层面挖尽。边际新增率趋 0 ⇒ 已\n"
           "          「挖到不能再挖」⇒ **趋近无穷收敛**。\n"
           "        ★ **方向：本读数越小越接近挖尽**（与 settle/fuse/crystallize 的\n"
           "          「越大越好」**相反**）—— 消费方不可一刀切判它。\n"
           "          `excavate_closed = 1 − 该值` 是「已挖尽度」（越大越好）。\n"
           "        辅读：`divergence.state == \"收敛\"/\"停滞\"` ⇒ 属于「趋近收敛」。")

# ── ③ _LG_HINT 常量 ─────────────────────────────────────────────────
LBL_OLD = ('_LG_LABELS = {"0": "修行·挖尽", "1": "研究·收敛",\n'
           '              "both": "对撞·融合", "all": "元·结晶"}')
LBL_NEW = (LBL_OLD + "\n"
           "#: [层目标] `goal_verdict` 的**方向提示**：只给「方向与多数轴相反」的轴，\n"
           "#:   免得产物印出「修行·挖尽：excavate=0.000」被误读成「一分没挖」。\n"
           '_LG_HINT = {"excavate": "（边际新增率·趋零即挖尽）"}')

# ── ④ 显示：writer 追加 hint（P1 的收尾刷新是唯一写入点）────────────
W_OLD = ('                    view.goal_verdict = "本层目标（%s）：%s=%.3f" % (\n'
         '                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,\n'
         '                        float(_gv_f))')
W_NEW = ('                    view.goal_verdict = "本层目标（%s）：%s=%.3f%s" % (\n'
         '                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,\n'
         '                        float(_gv_f), _LG_HINT.get(_gk_f, ""))')


def apply(s):
    for nm, old, new in (("声明", DECL_OLD, DECL_NEW),
                         ("docstring", DOC_OLD, DOC_NEW),
                         ("_LG_HINT", LBL_OLD, LBL_NEW),
                         ("writer", W_OLD, W_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（要求 1）" % (nm, n)
        s = s.replace(old, new)
    # 自检：旧口径必须消失
    assert "每条读数都是「**越大越接近该层目标**」" not in s
    assert "故本读数 = **1 − 归一化边际新增**" not in s
    assert s.count("_LG_HINT = {") == 1
    assert s.count("_LG_HINT.get(_gk_f") == 1
    return s


if __name__ == "__main__":
    out = _rw(TGT, apply)
    print("[ok] P2 补丁已落 | 行数", out.count(b"\n"), "| 纯 CRLF | AST OK")
