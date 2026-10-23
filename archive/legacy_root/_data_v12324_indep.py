#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「不可判定结构覆盖率（旧）」与「独立度（新）」的数据全量摊开。

产物：`_数据_独立度_v12324.md`
  · 表 1  全部产物 × 不可判定通道读数（旧口径 vs 独立度）
  · 表 2  新真跑产物的**逐圈序列**（两种口径并列）
  · 表 3  新真跑终端的逐圈打印（`📘 不可判定独立度 …`）
  · 表 4  口径定义与不可复算说明
零 LLM 调用。取产物按 st_mtime，最新在后。
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.24.py"
OUT = HERE / "_数据_独立度_v12324.md"
RUNLOG = HERE / "_realrun_v12324.log"


def load_mod():
    spec = importlib.util.spec_from_file_location("dgtf_data", str(TGT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_data"] = m
    spec.loader.exec_module(m)
    return m


def walk(packs):
    """逐产物 × 逐层，产出读数行。"""
    rows = []
    for p in packs:
        try:
            d = json.loads(p.read_bytes().decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for entry, pool in sorted((d.get("pools") or {}).items()):
            uc = (pool or {}).get("undecidable_channel") or {}
            if not uc or not (uc.get("structural_amps") or uc.get("und_aspects")):
                continue
            rows.append((p, entry, uc))
    return rows


def main():
    m = load_mod()
    packs = sorted((HERE / "outputs").glob("*.packed.json"),
                   key=lambda x: x.stat().st_mtime)
    rows = walk(packs)
    L = []
    L.append("# 不可判定通道读数数据 · 旧口径（结构覆盖率） vs 新口径（独立度）")
    L.append("")
    L.append("- 被验引擎：`%s`" % TGT.name)
    L.append("- 数据来源：`outputs/` 下各产物的 packed（**真跑产物**，非 mock）")
    L.append("- 旧口径 = `|被 structural_amps 命中的 und_aspects| / |und_aspects|`")
    L.append("- 独立度 = `|不与任何 und_aspects 重合（overlap<0.3）的 structural_amps|"
             " / |structural_amps|`")
    L.append("")

    # ---------------- 表 1 ----------------
    L.append("## 表 1 · 逐产物（末圈读数）")
    L.append("")
    L.append("| # | 产物 | 层 | 方面数 | 结构数 | 旧：命中 | 旧：**结构覆盖率** | "
             "新：独立数 | 新：**独立度** |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, (p, entry, uc) in enumerate(rows, 1):
        amps = [str(x) for x in (uc.get("structural_amps") or [])]
        asps = [str(x) for x in (uc.get("und_aspects") or [])]
        free = [a for a in amps
                if not any(m._overlap_coef(x, a) >= 0.3 for x in asps)]
        indep = (len(free) / len(amps)) if amps else None
        old = uc.get("last_struct_coverage")
        L.append("| %d | %s | %s | %d | %d | %s | **%s** | %d | **%s** |" % (
            i, p.name.replace(".packed.json", "")[:52], entry, len(asps),
            len(amps), uc.get("last_struct_hit", "-"),
            ("%.3f" % old) if isinstance(old, (int, float)) else "-",
            len(free), ("%.3f" % indep) if indep is not None else "-"))
    L.append("")

    # ---------------- 表 2 ----------------
    L.append("## 表 2 · 新真跑产物的**逐圈序列**（同一次跑，两种口径并列）")
    L.append("")
    has_series = False
    for p, entry, uc in rows:
        ih = uc.get("indep_history")
        if not ih:
            continue
        has_series = True
        L.append("产物：`%s`（层 %s）" % (p.name.replace(".packed.json", ""), entry))
        L.append("")
        olds = list(uc.get("struct_coverage_history") or [])
        n = max(len(olds), len(ih))
        L.append("| 圈 | 旧：结构覆盖率 | 新：独立度 |")
        L.append("|---|---|---|")
        for k in range(n):
            o = olds[k] if k < len(olds) else None
            v = ih[k] if k < len(ih) else None
            L.append("| %d | %s | %s |" % (
                k + 1,
                ("%.2f" % o) if isinstance(o, (int, float)) else "-",
                ("%.2f" % v) if isinstance(v, (int, float)) else "—（不可计算）"))
        L.append("")
        tr = uc.get("struct_trace") or []
        if tr:
            L.append("同一次跑的命中轨迹（旧口径的分母是方面数）："
                     + "、".join("第 %s 圈 %s/%s" % (t.get("layer"), t.get("hit"),
                                                    t.get("total")) for t in tr))
            L.append("")
    if not has_series:
        L.append("（无：只有 v1.23.24 起的产物才写 `indep_history`）")
        L.append("")

    # ---------------- 表 3 ----------------
    L.append("## 表 3 · 新真跑终端逐圈打印（`_realrun_v12324.log`）")
    L.append("")
    if RUNLOG.is_file():
        txt = RUNLOG.read_text(encoding="utf-8", errors="replace")
        hits = [ln.strip() for ln in txt.splitlines()
                if "不可判定独立度" in ln or "独立度分母" in ln
                or "不可判定结构覆盖" in ln or "不可判定对齐覆盖率" in ln]
        if hits:
            L.append("```")
            for ln in hits:
                L.append(ln)
            L.append("```")
        else:
            L.append("（日志里没有这类行）")
    else:
        L.append("（找不到 %s）" % RUNLOG.name)
    L.append("")

    # ---------------- 表 4 ----------------
    L.append("## 表 4 · 口径说明与不可复算的部分")
    L.append("")
    L.append("1. **两种口径的分母不同**：旧的分母是**方面数**（`und_aspects`），"
             "新的分母是**结构条数**（`structural_amps`）。所以两列**不可互推**，"
             "只能各自读。")
    L.append("2. **旧口径为什么恒 0**：提示词要求 `structural_amps`「独立提炼、"
             "**不得直接复述** und_aspects 的原话」；旧口径却奖励「跟它一致」"
             "⇒ 模型照办就必然 0。新口径下同一批数据读成 1.00。")
    L.append("3. **逐圈序列只有新产物有**：`indep_history` 从 v1.23.24 起才写；"
             "历史 packed 只有 `struct_coverage_history`。"
             "历史产物的**逐圈独立度不可复算** —— packed 只存**累计**的 "
             "`structural_amps`（已跨圈去重），拿不到每圈的结构池。"
             "表 1 的「新：独立度」列是用**末圈累计池**复算的。")
    L.append("4. **空池记 `None`**（渲染成 `—`），不印 `0.00` —— "
             "「不可计算」与「比例是 0」是两件事。")
    L.append("5. **方面数为 0 时该值不可证伪**（真实语料里有这种行）："
             "按定义成立，但不构成证据；见报告 §二-2.1。")

    text = "\n".join(L) + "\n"
    sys.stdout.write(text)
    OUT.write_bytes(text.encode("utf-8"))
    sys.stdout.write("\n[out] %s (%d bytes)\n" % (OUT.name, OUT.stat().st_size))


if __name__ == "__main__":
    main()
