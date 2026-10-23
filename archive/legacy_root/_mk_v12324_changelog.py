#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 顶部插入 v1.23.24 段。幂等、CRLF 往返、分隔线从文件里量。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
MARK = "v1.23.24 相对 v1.23.23"
ANCHOR = "v1.23.23 相对 v1.23.22"

SEP60 = "  " + "\u2500" * 60

SECTION = """v1.23.24 相对 v1.23.23

【要解决的问题】两个「读数 / 文案」在说假话，而且都活了很久：

  一、不可判定通道的**结构覆盖率**：7 份近期产物里 **6 份恒 0.00**（另 1 份 0.60）。
     根因不是质量差，是**两侧口径反着来** —— 喂模型的提示词要求 `structural_amps`
     「独立提炼、**不得直接复述** und_aspects 的原话」，而这个读数用
     「跟 und_aspects 一致的比例」打分。一个要求「别跟它一致」，一个奖励「跟它一致」
     ⇒ 只要模型照办，读数必然是 0。而 0.00 是个**合法值**，所以它静静活了很久，
     读者还会以为这条通道不及格。

  二、修行层停因里有两个借来的东西：
     ① 印成 `ing 连续 N 圈复述` ——「ing」是**对撞层**的输入名，修行 / 研究 / 元层
        根本没有这个输入；
     ② sat 判「无新维度」时会把 `idle_stall` **顶到门槛上**，而那一刻 `stall_why`
        是空串 ⇒ 停因印成 `连续 1 轮有新增但无推进（）`（真跑产物
        `outputs/20261013_050650_普通人应该做些什么来迎接AI时代的到来.md` 就这么印的）。

【改了哪几处】
  1. **独立度**取代结构覆盖率（换口径，不只是改名）：
     独立度 = 不与任何 `und_aspects` 重合（`_overlap_coef < 0.3`）的
     `structural_amps` 条数 ÷ `structural_amps` 总条数。分母换成**结构条数**，
     于是「越高越合规」。空池记 `None`（不可计算），**不印 0.00** 冒充读数。
     · 新增键 `last_indep_ratio` / `last_indep_pool` / `last_indep_free` /
       `indep_history`（`Pool.add_undecidable`）。
     · 旧键 `last_struct_coverage` / `struct_coverage_history` / `last_struct_hit`
       **一字未动** —— 历史 packed 与命中轨迹照旧解析。
     · 渲染点跟着改：产物 `_und_channel_line`、终端 `_update_trackers`、
       喂模型的 `_pool_shape`、视图 dump 与 md 附录的「计入覆盖率」字样。
     · 渲染到**只有旧键**的 dict（历史 packed 重渲染）时走旧口径分支并显式标
       「旧口径」—— 不丢信息、也不误导。
     · 「对齐覆盖率」**保留原名**：`aligned_amps` 的定义就是「正好对应」，
       用覆盖率是自洽的；只有「独立」这一路名字错了。
     · **提示词没动** —— 保留「独立提炼 / 不得复述」，它现在与新读数同向。
  2. 修行层停因文案去借词：条件 1 改成 `{层名}层连续 N 圈复述`。
     ★ 条件 1 **仍对四层生效**（v1.23.17 的设计不变）。
  3. 修空括号：`_stop_reasons` 新增关键字参数 `stall_is_sat: bool = False`
     （带默认值 ⇒ 旧调用点与旧夹具不受影响），两条跑圈通道各算一次
     `_stall_is_sat = bool(sat_verdict is False and not stalled)`；这一支印
     `连续 N 轮无新结构维度（结构饱和度判定，不是新增停滞）`。
     ★ 不是给空串兜默认词 —— 那样 `stall_why` 会变成万金油，下次真 stall 时分不清。
  4. 修行层**任何**停止都补「本轮显形 + 未生质量」（原来只在「体力耗尽」截断时补），
     让「停得合理」可核。
  5. 红线表述：「修行层不追求收敛」→「修行层**本来就能停**，要的是**停得合理**」；
     并在 `_stop_reasons` docstring 写一张**修行层适用停止条件显式清单**
     （逐条标适用 / 不适用及理由），改条件前先看表。

【影响面】
  · ★ **运行期可见变化**：`_pool_shape` 那一行由「不可判定结构覆盖 X」改成
    「不可判定独立度 X」。旧口径下值为 0.00 时该行**本来就不出现**
    （`if value:` 是真值门）⇒ 这是**新增一条提示**，不是把旧提示换掉。
  · 产物的第七节、修行层停因文案会变；`packed.json` 新增 4 个键（加性）。
  · 出厂配置**无新增键、无默认值改动** —— `load_config` 改前 / 改后逐字差异 0 项。
  · 判据：`smoke_test.py` 的 `SRC` 指本版；新增 `check_v12324_indep_therapy`
    （带负对照，判别力由 8 个变异体证明）；`check_v69_abcde` 的 B 段落点跟着改；
    v1.22 阶段1 与 `_v122_verify.py` 的红线锚点由旧句换成新句。

【怎么退回旧行为】没有配置开关（改的是口径与文案）；退回 = 用 v1.23.23 的主文件。

【未做】P2 停圈相位（属调参，需先在看真跑数据）；P3 清单后补（引擎只标记不处置）；
  两条通道对 sat 推计数的**持久化口径不一致**（串行留到下一圈、并行只影响本圈）——
  属实现细节待定，本版只保证两边都修到空括号；提示词里的「ing」不动（属另一主题）。

★ v1.23.24 收束摘要
  ────────────────────────────────────────────────────────────
  **交付物**：元DGTF-V1.23.24.py（18491 行 CRLF）+ 本段 changelog + 升级段
    （dgtf_config.yaml）+ 判据 `check_v12324_indep_therapy` + 变异体 `_mut_v12324.py`。
  **改了什么**：主文件 37 个改动块（删 33 行 / 增 139 行）；结构覆盖率 → 独立度
    换口径 + 旧键不变式；修行层停因去「ing」、修 sat 空括号、任何停止都附体检、
    红线表述与适用条件清单。
  **验收**：探针 before/after 对表（旧键逐数不变 / 空池 None / legacy 回退 /
    shape 已换）；8 变异体全判红 + 正对照判绿；真实产物离线复算（旧口径 5/6 行
    = 0.000 → 独立度 5/6 行 = 1.000）；出厂配置逐字差异 0 项；全套冒烟
    exit 0 / 0 ✗ / ✓ 见 `_smoke_v12324.log`；真跑同题同参对照见 `v12324_报告.md`。
  **未做**：P2 停圈相位、P3 清单后补、两条通道 sat 持久化的口径分歧、
    提示词里的「ing」。

"""


def main():
    raw = CL.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "CHANGELOG 不是纯 CRLF"
    assert raw.count(b"\r\r\n") == 0, "CHANGELOG 含 CRCRLF"
    s = raw.decode("utf-8").replace("\r\n", "\n")

    if MARK in s:
        print("· v1.23.24 段已存在，跳过")
    else:
        n = s.count(ANCHOR)
        assert n == 1, "锚点 %r 命中 %d 次" % (ANCHOR, n)
        s = s.replace(ANCHOR, SECTION + ANCHOR)
        print("· 已插入 v1.23.24 段")

    assert s.count(MARK) == 1, "新段出现次数 != 1"
    assert s.count(SEP60) >= 1
    # 段序：新段必须在最前（在第一个 "v1.2x 相对" 里）
    import re
    heads = re.findall(r"(?m)^v(\d+(?:\.\d+)+) 相对", s)
    assert heads and heads[0] == "1.23.24", "段序最前不是本版：%r" % heads[:3]
    assert heads[:4] == ["1.23.24", "1.23.23", "1.23.22", "1.23.21"], heads[:6]

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    assert out.count(b"\n") == out.count(b"\r\n")
    assert out.count(b"\r") == out.count(b"\r\n")
    CL.write_bytes(out)
    assert CL.read_bytes() == out
    print("OK CHANGELOG.md：段序 %s  ; 共 %d 段" % (heads[:4], len(heads)))


if __name__ == "__main__":
    main()
