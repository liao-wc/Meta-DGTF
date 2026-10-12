#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.23 探针：日志回显「按字符硬砍」-> 「按整行截断」。

对表口径：同一支探针跑**两版**（改前 v1.23.22 / 改后 v1.23.23）。
每组都带负对照；样例取自**真实日志**（`outputs/20261012_121240_….run.log:817-821`）。

    python _probe_v12323_echo.py 元DGTF-V1.23.22.py
    python _probe_v12323_echo.py 元DGTF-V1.23.23.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── 真实回显（run.log:818-821 逐字；被砍断那行的全文取自同次产物 md）──
RAW = "\n".join([
    "- [thread] C1 点名方向已耗尽，本体层此处未生；本圈只列避开后的可判定侧残留：定义、痕迹、论证结构。",
    "- [concept] 空间离散化若被观测，只支持底层自由度截断，不支持外部模拟器；因此该痕迹不能单独判决“世界是虚拟的”。",
    "- [concept] 全息投影若无边界与体—边界字典，科学上不可检验；“一切是全息投影”作为字面命题当前不可判定。",
    "- [concept] 纠缠熵面积律不能单独支持全息，因为普通局域场论也满足；需比较对数修正系数与符号。",
])
CUT_TAIL = "不能单独支持全息"      # 旧实现下被砍掉的那一段


def load(path: Path):
    spec = importlib.util.spec_from_file_location("dg_" + path.stem.replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.23.py"
    src = target.read_text(encoding="utf-8", newline="")
    mod = load(target)
    rows = []
    bad = []

    def rep(name, val, want=None, ok=None):
        good = (val == want) if ok is None else bool(ok)
        rows.append((name, val if not isinstance(val, str) else val.replace("\n", "\\n")[:70], good))
        if not good:
            bad.append(name)
        return good

    has_helper = hasattr(mod, "_vp_preview")
    # ★ 不查「`raw[:200]` 这个串在不在文件里」—— 新函数的 docstring 按纪律引述了
    #   旧写法（供下一位读者理解为什么长这样），那样查会**把自己判红**。
    #   查的是**四处调用点本身**。
    OLD_SITES = ('self.vp(f"   {raw[:200]}")',
                 'self.vp(f"   {(raw or \'\')[:160]}")',
                 'self.vp(f"   [{i}] {c.desc[:50]}")',
                 "f\"      · [{s['decidability']}] {s['question'][:50]}\"")
    rep("A0 新函数 _vp_preview 存在", has_helper, True, has_helper)
    rep("A1 四处旧调用点（硬砍）已全部消失",
        sum(1 for k in OLD_SITES if k in src), 0,
        all(k not in src for k in OLD_SITES))
    rep("A2 四处回显都走 _vp_preview（1 定义 + 4 调用）",
        src.count("_vp_preview("), 5, src.count("_vp_preview(") == 5)

    if not has_helper:
        print("★ 目标版没有 `_vp_preview`（改前版），下面只跑「旧实现」那半边对照")
        old_out = RAW[:200]
    else:
        pv = mod._vp_preview
        new_out = pv(RAW)
        old_out = RAW[:200]

        # ── B 组：真实样例上的行为差 ─────────────────────────────────
        rep("B1 真实正文 >200 字（样例有效）", len(RAW), None, len(RAW) > 200)
        rep("B2 新实现：4 行逐字保留（== 原文）", new_out, RAW, new_out == RAW)
        rep("B3 旧实现：砍在行中间（末行是原文某行的真前缀且不相等）",
            "ok", None,
            (not old_out.endswith("\n"))
            and any(l.startswith(old_out.rsplit("\n", 1)[-1])
                    and l != old_out.rsplit("\n", 1)[-1]
                    for l in RAW.split("\n")))
        rep("B4 被砍掉的那段：旧实现找不到、新实现找得到",
            "old=%s new=%s" % (CUT_TAIL in old_out, CUT_TAIL in new_out),
            "old=False new=True",
            (CUT_TAIL not in old_out) and (CUT_TAIL in new_out))
        rep("B5 新实现不再丢行：末行 == 原文末行", new_out.rsplit("\n", 1)[-1],
            RAW.rsplit("\n", 1)[-1], new_out.rsplit("\n", 1)[-1] == RAW.rsplit("\n", 1)[-1])

        # ── C 组：短文本零改动（幂等 / 无副作用）─────────────────────
        rep("C1 短文本逐字返回", pv("载入调度配置：dgtf_config.yaml（出厂） + 无用户覆盖"),
            "载入调度配置：dgtf_config.yaml（出厂） + 无用户覆盖")
        rep("C2 空串 / None 不抛错", pv("") + "|" + pv(None), "|", pv("") == "" and pv(None) == "")
        rep("C3 单行候选（20-80 字）原样", pv("- [concept] 短候选：三十字以内拿来验不截断的行为"),
            "- [concept] 短候选：三十字以内拿来验不截断的行为")

        # ── D 组：真截断时的行为（含可见痕）──────────────────────────
        long_multi = "\n".join("- [concept] 第%d行候选：%s" % (i, "字" * 60)
                               for i in range(1, 6))
        out2 = pv(long_multi, limit=200)
        head = out2.split("\n   …（预览到此")[0]
        tail = out2[len(head):]
        dropped = len(long_multi) - len(head)
        rep("D1 超长多行：切点正好落在换行上（原文该位置就是 \\n）",
            "next=%r" % long_multi[len(head)], "next='\\n'",
            long_multi.startswith(head) and long_multi[len(head)] == "\n")
        rep("D2 超长多行：带可见痕「另有 N 字未显示」", "ok", None,
            tail.startswith("\n   …（预览到此") and tail.rstrip().endswith("字未显示）"))
        rep("D3 超长多行：标记里的 N == 真丢掉的字数",
            "dropped=%d" % dropped, None,
            tail == "\n   …（预览到此，另有 %d 字未显示）" % dropped)
        rep("D4 超长多行：保留的每一行都是**完整行**（逐行 == 原文对应行）", "ok", None,
            long_multi.split("\n")[:head.count("\n") + 1] == head.split("\n"))
        rep("D5 超长单行（无换行）：退化成按 limit 硬切且不抛错",
            "ok", None, len(pv("字" * 9000, limit=100)) > 100
            and pv("字" * 9000, limit=100).startswith("字" * 100))
        rep("D6 limit 可覆盖（limit=50）", "ok", None,
            pv(long_multi, limit=50).split("\n   …")[0].count("\n") <= 1)
        rep("D7 真跑量级（6 行 / 约 300 字）不触发截断", "ok", None,
            pv("\n".join("- [concept] " + "字" * 45 for _ in range(6))).find("另有") < 0)

    # ── 输出 ────────────────────────────────────────────────────────────
    print("目标：%s" % target.name)
    for n, v, ok in rows:
        print("  %s %s -> %s" % ("✓" if ok else "✗", n, v))
    print("PASS %d / FAIL %d" % (len(rows) - len(bad), len(bad)))
    (HERE / ("_probe_v12323_echo.%s.txt" % target.stem.split("-")[-1])).write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
