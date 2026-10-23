#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.21.69] 补真跑验收证据进 changelog（**只动 docstring**）。

为什么单独一个脚本：真跑（8 次）是 smoke 之后做的，changelog 里那句
「未做真跑」会变成过期陈述 —— 本项目对过期陈述零容忍（判据自己变成
噪声源）。但改主文件又必须证明**没有动到任何可执行语句**，所以这里加一条
硬断言：把 docstring 抠掉之后，改前改后两段源码必须逐字相同。
"""
import importlib.util
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.69.py"

OLD = '''  **未做真跑**：C 动的是 prompt 分支（不可达支）、D 动的是判定输入，
  两者都属"要真跑对照才敢宣称效果"的改动。本版只做到「量出方向 +
  冒烟锁住语义 + 负对照」，真跑对照（同题、route 0,1）留给下一轮。
'''

NEW = '''  ────────────────────────────────────────────────────────
  真跑验收（补做 · 同题同参数：route 0,1 / rounds 0:2,1:2 / serial）
  ────────────────────────────────────────────────────────

  题面与 V68 完全一致（老城区暴雨内涝…怎么权衡？）。共 8 次：
  V68 原跑 + V68 重复 3 + V69 单跑 + V69 重复 2 + V69 mode B 1。

  **[A] 要并行通道才有判别力** —— 原 V68/V69 都是 serial：`_run_layer`
  里累加本来就在体外，新旧输出**必然相同**（实测 V68 serial 两层
  Σcount = 11 / 12，与该层 `[P3]` 行的 N **逐层相等**）。补跑一次
  `mode=B`（Jacobi，走 `_b_merge`）：
    · entry 0：各圈 `_amp_cand_count` = 3/3 → Σ=6，`[P3]` 实测 **6**
      （旧实现预测 Σ(count×len(amps)) = **24**）
    · entry 1：各圈 = 6/2 → Σ=8，`[P3]` 实测 **8**（旧实现预测 **32**）
  即真实并行路径上，N 与 Σcount 严格相等，而旧实现会给出 4 倍值。

  **[B] 日志渲染点 ✅**：V69 真跑出现
  `📘 不可判定对齐覆盖率 0%（0/3 und_aspects 命中）` 2 次（V68 为 0 次），
  并把「对齐结构 N 条（另计）」改成「（计入对齐覆盖率）」。
  ★ **可达性限制（既有行为，非本轮改动）**：产物 md 那行
  `研究层不可判定通道：…` 由 `_coverage_segment` 产出，而它只在
  `entry == "all"` 时被追加 ⇒ route 不含 `all` 的运行**整个第七节都不
  出现**（V68/V69 产物实测都是 0 行）。备查。

  **[C] ✅**：V69 真跑 ing 正文 153 行里含「各个局部」**0 行**；含
  「上游」3 行全是模型自己的水文措辞（「下游水位反超上游出口」等），
  与标签无关 —— 与「0/1 层走 is_base 分支」的结论一致。

  **[D] ✅（本批多数运行没触发到）**：把每一跑的 (池内 und_aspects,
  evidence) 分别喂给 V68 码与 V69 码做**反事实对照**：
    · 原 V68 那一跑：V68 码判 2 条无追溯（全是误报）→ V69 码 0 条 ✅
    · 其余 7 跑：池子**自列 und_aspects 为空**（只剩 `[外]`）⇒ 两版结果
      都是 0 条，D 在这些运行上是**可证明的无操作**。
  即：D 的修在被触发的数据上确实生效，且**没有**改变其余运行。

  **[E] ✅**：V69 真跑出现「收尾留痕」**2 段**（entry 0 / 1），增量省略
  **40/54** 与 **38/53**，`round_log` 2/2 项、`roles_run` 2/2 项、
  `carry_checks` 1/1 项；V68 同题同参为 0 段，四个累积字段在 4 段圈留痕里
  **每段 0 项**。

  **同题同参的横向指标**（V68 原跑 vs V69 单跑）：43 / 43 calls；
  194993 / 185901 tokens；9.7 / 8.9 min；dispatch 都是
  order=['0','1'] missing=[]；views errors 都是空；日志 123313 →
  152825 字符（多出的是 2 段收尾留痕 + 更多 ing 行）。

  **一项无法归因的观测（按纪律定性，不硬说）**：`tri_state`（三态二次
  判决的「一致条数」）V68 原跑 4/6、V69 单跑 0/6。补做同条件重复后：
    · V68（n=4）：4 / 1 / 3 / 2 → 均值 2.50，组内极差 **3**
    · V69（n=3）：0 / 2 / 2    → 均值 1.33，组内极差 **2**
  组间差 1.17 **小于**组内极差 3 ⇒ 按「组内极差 < 组间差才有判别力」这条
  纪律，本轮样本量**不支持**把它归给本版改动。并且 A/B/C/E 对 serial +
  route 0,1 是**可证明的无操作**（A 走 `_run_layer`；B 只改渲染与新增键，
  `_pool_shape` 喂模型的仍是 `last_struct_coverage` 原值；C 是不可达支；
  E 只写 stdout），D 又在上列 7 跑上无操作。故记在**引擎自身的采样抖动**
  名下。要坐实需更大样本，本轮止步于此、如实记数。
'''

OLD2 = '''  **交付物**：元DGTF-V1.21.69.py（纯 CRLF）；smoke_test.py
    +`check_v69_abcde`；`_probe_v69_abcde.py`（改前/改后同一支探针）；
    `v69_报告.md`。
'''

NEW2 = '''  **交付物**：元DGTF-V1.21.69.py（纯 CRLF）；smoke_test.py
    +`check_v69_abcde`；`_probe_v69_abcde.py`（改前/改后同一支探针）；
    `_cmp_v68_v69.py`（真跑对照 + A 的不变量校验）；`v69_报告.md`；
    8 次真跑的 sidecar（`verif_V69*.log/.json/.full.json`）。
'''

OLD3 = '''  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不动 `_fix83_block` 的措辞、不改 `_pool_shape`、不做真跑。
'''

NEW3 = '''  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不动 `_fix83_block` 的措辞、不改 `_pool_shape`（把对齐口径也喂模型
    等于改模型输入，要另起一轮真跑对照）。
'''


def main():
    raw = SRC.read_bytes()
    src = raw.decode("utf-8")
    assert src.count("\r\n") == src.count("\n"), "不是纯 CRLF"
    src_lf = src.replace("\r\n", "\n")

    # 抠 docstring：用加载模块拿到的 __doc__（与 smoke_test 同一手法）
    spec = importlib.util.spec_from_file_location("dgtf_doc", str(SRC))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_doc"] = mod
    spec.loader.exec_module(mod)
    old_doc = mod.__doc__ or ""
    assert src_lf.count(old_doc) == 1, "旧 docstring 在源码里不是唯一一份"
    body_before = src_lf.replace(old_doc, "")

    for tag, o, n in (("验证·真跑", OLD, NEW),
                      ("收束·交付物", OLD2, NEW2),
                      ("收束·刻意不做", OLD3, NEW3)):
        c = src_lf.count(o)
        if c != 1:
            raise SystemExit(f"[{tag}] 查找块出现 {c} 次（要求 1 次），拒绝改")
        src_lf = src_lf.replace(o, n)
        print(f"  ✓ [{tag}] 命中 1 次")

    new_doc = src_lf.split('"""', 2)[1]
    body_after = src_lf.replace(new_doc, "")
    if body_before != body_after:
        raise SystemExit("✗ 抠掉 docstring 后源码不一致 —— 动到了可执行语句")
    print("  ✓ 除 docstring 外，源码逐字未变（可执行语句零改动）")

    out = src_lf.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and \
        out.count("\r") == out.count("\r\n"), "CRLF 断言失败"
    SRC.write_bytes(out.encode("utf-8"))
    print(f"写出 {SRC.name}：{len(out.encode('utf-8'))} 字节 / "
          f"{out.count(chr(10))} 行")


if __name__ == "__main__":
    main()
