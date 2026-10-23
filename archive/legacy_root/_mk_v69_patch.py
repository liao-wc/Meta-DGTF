#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.21.69] 打补丁脚本：从 V1.21.68 复制出 V1.21.69，改 A/B/C/D/E 五项。

本项目纪律（写在长期记忆里，这里逐条兑现）：
  · 不覆盖源文件 —— 复制出下一版；
  · 纯 CRLF，禁用 sed/awk；脚本里先归一成 LF，再换回 CRLF，并断言
    `count("\\n") == count("\\r\\n")`；
  · 每个查找块**断言出现次数 == 1**（重复插入是真实事故，不是理论风险）；
  · docstring 里的样例代码**不写单反斜杠**（会被转义，导致"摘 docstring
    再扫源码"的断言失效）—— 本脚本的新增文本里没有一个反斜杠；
  · 改完打印各版本段的起始行号，确认块顺序（最新在最前）。
"""
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.68.py"
DST = HERE / "元DGTF-V1.21.69.py"

CHANGELOG = '''  ════════════════════════════════════════════════════════════
v1.21.69 相对 v1.21.68 的改动（A/B/C/D/E 五项：先量后改）
════════════════════════════════════════════════════════════

  来源：一份**外部评审**（对 v1.21.68 一次真跑 V68 的结构分析）列出 A-E
  五项。本版**不照单全收** —— 每一项都先用生产入口量出改前基线
  （`_probe_v69_abcde.py`，可重复运行），量出来与评审不一致的地方照实写。
  五项里 **2 项真 bug**（A/B）、**1 项潜在串层**（C，现网不可达）、
  **1 项判据误报**（D）、**1 项评审诊断反了**（E）。

  ────────────────────────────────────────────────────────
  [A] `_b_merge` 的 `all_amp_cands` 缩进错（真 bug · 会算错数）
  ────────────────────────────────────────────────────────

  **病灶**：并行通道（B/C/D-H）的 `_b_merge` 里，逐圈累加候选数那几行
  写在 `for a in (view.amps or [])` 的**循环体内**：
    · `view.amps` 为空 → 那一圈的 `_amp_cand_count` **漏累加**；
    · `view.amps` 有 N 条 → 同一个数被**重复累加 N 次**。
  而串行通道（`_run_layer`）里同名的累加本来就在体外。同一条逻辑两条
  通道各写一份、只错一份，且没有任何断言看住 —— 本项目第 N 次的老毛病。

  **实测**（`_probe_v69_abcde.py`，改前）：
    · amps=3 条、`_amp_cand_count`=5 → `all_amp_cands`=**15**（应为 5）；
    · amps=0 条、`_amp_cand_count`=7 → `all_amp_cands`=**0**（应为 7）。

  **影响面**（改之前先查下游）：`all_amp_cands` 只有两个出口 ——
  ① 产物 packed 里的同名键；② `_finalize_layer_common` 里那行
  「[P3] & 候选（各圈累计）N 条 / 本层 amps M 条（比值 …）」的**分母**。
  分母虚高 3 倍（或漏算）会把这行观测直接带偏；修完才是与 `all_amps`
  真正同口径。

  **改法**：累加移出循环体，与 `_run_layer` 对齐。

  ────────────────────────────────────────────────────────
  [B] 不可判定覆盖率算错了输入（真 bug · 口径内部矛盾）
  ────────────────────────────────────────────────────────

  **病灶**：`Pool.add_undecidable` 拿 `structural_amps` 去撞
  `und_aspects` 算「结构覆盖率」。但喂模型的 schema 里
  `structural_amps` 明确要求**「不得直接复述 und_aspects 的原话」**，
  而 `aligned_amps` 才是要求**「正好对应 und_aspects 中的某一项」**的
  那一列。拿前者算命中 —— **结构性必为 0**：这个数指向的不是"模型没
  做到"，是"它永远算不出别的值"。

  **实测**（V68 真产物 / `_probe_v69_abcde.py`）：
    · `und_aspects` 8 条；`structural_amps` 8 条 → 旧口径 **0/8 = 0.000**
      （产物里记的就是 `last_struct_coverage = 0.0`）；
    · `aligned_amps` 3 条（三条与 und_aspects 前三条同义）→
      **3/8 = 0.375**。也就是说 aligned 这一列**早就算出来了，却没有出口**。

  **改法**：两个覆盖率**分开算、都留出口**。
    · `last_struct_coverage` / `last_struct_hit` **语义一个字不改** ——
      它是 `_pool_shape` 喂给模型的输入，改它的值等于改模型输入，
      那要真跑对照，不在本版范围；
    · 新增 `last_aligned_coverage` / `last_aligned_hit` /
      `aligned_coverage_history`，只在**产物 md**（`_und_channel_line`）
      与**日志**（`_update_trackers` 那一行）两个渲染点出现；
    · 渲染**加性**：旧产物 / 手工 dict 里没有 `aligned_coverage_history`
      时不打这一行 —— v1.21.57 的冒烟断言（"结构覆盖率 0.60"、
      "已对上 6/10"）因此原样通过，不必改旧断言。

  ────────────────────────────────────────────────────────
  [C] `object_desc` 的兜底分支串层（潜在 · 现网不可达）
  ────────────────────────────────────────────────────────

  **评审的说法**：研究层（entry=1）落到 `else` 分支，拿到「整体与每一个
  局部」当对撞对象。**实测：不成立。** 三条独立证据：
    ① 生产入口 `_build_inp_base` 必定带 `question` ⇒ `Input.is_base`
       恒为 True ⇒ 0/1 层永远走第一个分支；并且 `_ENTRY_CONTENT_DEPS`
       里 0/1 的内容依赖都是**空表**，本来也不会有上游 view；
    ② 探针按生产构造逐组合跑（entry 0/1/both/all × is_base 真/假），
       0/1 只出现「这个问题里的 0 和 1」；
    ③ V68 日志里 135 行 ing 正文，含「各个局部」**0 行**、含「上游」
       **0 行** —— 模型从没收到过那句话。

  **但分支本身确有隐患**：`else` 同时兜住「元层(all)」与「修行/研究层
  (0/1)」，两者的对撞对象根本不同。这正是本项目反复栽的「兜底分支混层」。
  **改法**：对象映射写成**显式四支**（is_base / both / all / 0-1），
  不可达的那一支也不再给错标签。
  **刻意不动**：`_fix83_block` 的 `_upstream_label` 对 0/1 仍写
  「上游 view」——那是措辞瑕疵不是错误，改它要真跑对照，留给下一版。

  ────────────────────────────────────────────────────────
  [D] `_untraced_undecidable` 的误报（判据自己变成噪声源）
  ────────────────────────────────────────────────────────

  **病灶**：`_similar` 的分母取 **max**。不可判定条目句长、evidence 里的
  aspect 句短，同一语义被写成「长句 ⊃ 短句」时比值被长句拉低，
  于是**有追溯的被判成无追溯**。

  **实测**（V68 真产物 / `_probe_v69_abcde.py`）两条误报：
    · 「时间尺度（一场雨/汛期/管网寿命）结论相反且无仲裁规则」
      ↔ evidence「时间尺度无仲裁规则」：_similar 够不着 0.55，
      包含度 **1.000**；
    · 「行政档案与居民记忆两份留痕之差不能被对撞消掉」
      ↔ evidence「两份留痕之差不可对撞消减」：包含度 **0.667**。
  改前 `_und_untraced` 记的 2 条（合并路径已滤掉 [外]）**全是误报**。

  **改法**：再加一层 `_overlap_coef(...) >= _UNTRACED_OVERLAP`（0.6）——
  它的分母取 **min**，短句被长句包住时接近 1，正是需要的方向。
  阈值定 0.6：实测 0.667 能救回、0.75 就救不回，再低会把泛化同义也算成
  追溯。

  **影响面（必须记）**：`_untraced` 是 `_normalize_decidability` 的输入
  —— **误报少了，采信就多了**，decidable 更可能被拉成 partial。方向是
  刻意的（探针实证那 2 条本来就是采样抖动），但它动的是**三态判定**，
  属运行期可见变化，不能只当"日志好看了"。V68 这两条剔除后判值仍是
  partial（`_und_traced` 由 2 条变 4 条，都非空）。

  ────────────────────────────────────────────────────────
  [E] 累积型字段的出口（评审诊断反了 · 换成真问题）
  ────────────────────────────────────────────────────────

  **评审/上一版的说法**：v1.21.68 遗留 1 ——「每圈留痕含 `round_log` 等
  **累积型**字段，同一信息随圈重复出现（n 圈约 n(n+1)/2 份）」。
  **实测：不成立。** 直接数 `verif_V68.log` 的 4 段留痕：`round_log` /
  `roles_run` / `carry_checks` / `carry_dropped_all` **每段都是 0 项**；
  每段 26k-31k 字符全由 `candidates` / `rendered` / `untouched` 撑着
  （逐圈内容，不是累积）。
  **真正的问题正相反**：这些字段是**回填**的，回填发生在最后一次
  `dump_round` **之后** ⇒ 它们在任何一段留痕里都恒为空 ——「全量留痕」
  对这几个字段**从来没兑现过**。上一版把"没出口"误诊成了"重复"。
  （教训：**"某指标很稳/很吵"要先确认它不是被下游机制压出来的**，
  这里连"有没有出口"都该先数一遍再下结论。）

  **改法**：跑圈 + 回填都结束后，补一段**收尾留痕**：
    · `DGTF.dump_final(view)`，头是「收尾留痕 · entry · 共 N 圈 · 角色」；
    · **增量模式**：只打与上一圈 dump 有差异的字段，并交代省略了几个 ——
      差分是**算**出来的，**不维护**"哪些字段是累积型"的清单
      （那种清单一定会漏，本项目「无渲染点」事故就是这么来的）；
    · 差分基准是 `dump_round` 打完那一刻挂在 `view._dump_canon` 上的
      规范化快照 —— 必须取在**那一圈真打出来的时刻**；取在收尾之前会把
      圈后的后处理（`carry_checks` 等）算进基准，于是又漏掉一次；
    · 字段落盘收口成模块级 `dump_view_fields()`（唯一实现），
      `DGTF.dump_round` 与 `dump_final` 共用 —— 同一件事两条通道各写一份
      也是本项目反复栽的坑；
    · `_dump_canon` 是**内部账**：`_view_field_map` 与 `View.to_dict`
      （`asdict`）都不带它，产物 packed 不受影响。

  ────────────────────────────────────────────────────────
  验证
  ────────────────────────────────────────────────────────

  **冒烟**：`SRC` → v1.21.69；新增 `check_v69_abcde`，A-E 各若干条，
  并带**负对照**（证明判据有判别力，不是随口放宽）：
    · D：真·凭空一条仍须被抓出；带来源后缀的仍须判为有追溯；
    · B：旧键 `last_struct_coverage` 仍须原样渲染；
    · E：增量模式必须**真省略**掉没变的字段（省略数 > 0），
      且 `round_log` 必须出现在收尾段。
  **前置量化**：`_probe_v69_abcde.py`（接受目标 py 作参数），改前/改后
  各跑一次对表 —— 没有对照的"修好了"不算数。
  **未做真跑**：C 动的是 prompt 分支（不可达支）、D 动的是判定输入，
  两者都属"要真跑对照才敢宣称效果"的改动。本版只做到「量出方向 +
  冒烟锁住语义 + 负对照」，真跑对照（同题、route 0,1）留给下一轮。

  ────────────────────────────────────────────────────────
  ★ v1.21.69 收束摘要
  ────────────────────────────────────────────────────────

  **交付物**：元DGTF-V1.21.69.py（纯 CRLF）；smoke_test.py
    +`check_v69_abcde`；`_probe_v69_abcde.py`（改前/改后同一支探针）；
    `v69_报告.md`。

  **改了 6 处代码 + 1 个模块级常量**：A 缩进；B 覆盖率口径 + 2 个渲染点；
    C 对象映射四支；D 追溯判据 + 阈值常量；E 留痕收口 + 收尾增量。

  **刻意不做**：不动 `last_struct_coverage` 的语义（保模型输入不变）、
    不动 `_fix83_block` 的措辞、不改 `_pool_shape`、不做真跑。

  '''


def _rep(src: str, old: str, new: str, tag: str) -> str:
    """唯一性断言 + 替换。出现次数 != 1 直接炸，不做"尽力而为"。"""
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"[{tag}] 查找块出现 {n} 次（要求 1 次），拒绝改")
    print(f"  ✓ [{tag}] 命中 1 次")
    return src.replace(old, new)


# ============================================================
# A
# ============================================================
A_OLD = '''        for a in (view.amps or []):
            d = str(a.get("desc", "")).strip()
            if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                             for x in state["all_amps"]):
                state["all_amps"].append(dict(a))
            # [v1.21.63 P3修] 逐圈累加候选数（B/C/D-H 通道）
            try:
                state["all_amp_cands"] += int(
                    getattr(view, "_amp_cand_count", 0) or 0)
            except Exception:
                pass
        for t in (view.threads or []):
'''

A_NEW = '''        for a in (view.amps or []):
            d = str(a.get("desc", "")).strip()
            if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                             for x in state["all_amps"]):
                state["all_amps"].append(dict(a))
        # [v1.21.69 A修] 累加**移出 for 循环体**。原来它在体内，两个后果：
        #   ① view.amps 为空时，那一圈的 _amp_cand_count **漏累加**；
        #   ② view.amps 有 N 条时，同一个数被**重复累加 N 次**。
        #   实测（_probe_v69_abcde.py 改前）：amps=3、_amp_cand_count=5 →
        #   15（应 5）；amps=0、_amp_cand_count=7 → 0（应 7）。
        #   serial 通道（_run_layer 里同名累加）本来就在体外 —— 同一条逻辑
        #   两条通道各写一份、只错一条，是本项目反复栽的坑。
        try:
            state["all_amp_cands"] += int(
                getattr(view, "_amp_cand_count", 0) or 0)
        except Exception:
            pass
        for t in (view.threads or []):
'''

# ============================================================
# B-1 通道初始化补键
# ============================================================
B0_OLD = '''                "aligned_amps": [], "last_struct_hit": 0,
'''

B0_NEW = '''                "aligned_amps": [], "last_struct_hit": 0,
                # [v1.21.69 B修] 对齐覆盖率的三个键。与 struct_* 分开：
                #   struct_* 撞的是 structural_amps（prompt 要求"不得复述
                #   原话"），aligned_* 撞的是 aligned_amps（prompt 要求
                #   "正好对应某一项"）—— 后者才算得出非零值。
                "last_aligned_hit": 0, "aligned_coverage_history": [],
                "last_aligned_coverage": 0.0,
'''

# ============================================================
# B-2 覆盖率计算
# ============================================================
B1_OLD = '''        aspects = self.undecidable_channel.get("und_aspects", [])
        hit_aspects: List[str] = []
        if aspects:
            # 注意：structural_amps 只增不减，所以 hit 是单调不减的
            hit_aspects = [
                asp for asp in aspects
                if any(_overlap_coef(asp, sa) >= 0.3
                       for sa in self.undecidable_channel["structural_amps"])
            ]
            struct_cov = len(hit_aspects) / len(aspects)
            self.undecidable_channel["last_struct_hit"] = len(hit_aspects)
        else:
            struct_cov = 0.0
            self.undecidable_channel["last_struct_hit"] = 0
        self.undecidable_channel["struct_coverage_history"].append(struct_cov)
        self.undecidable_channel["last_struct_coverage"] = struct_cov
'''

B1_NEW = '''        aspects = self.undecidable_channel.get("und_aspects", [])
        # [v1.21.69 B修] 两个覆盖率**分开算**，不再只算一个（而且算错了输入）。
        #   实测（_probe_v69_abcde.py，V68 真产物）：
        #     · 旧口径 struct_cov = structural_amps 撞 und_aspects → **0/8**
        #       —— 结构性必为 0：prompt 明确要求 structural_amps
        #       「不得直接复述 und_aspects 的原话」，拿它撞原话站不住。
        #     · aligned_amps 才是 prompt 要求「正好对应 und_aspects 中的
        #       某一项」的那一列 → **3/8 = 0.375**，旧口径把它算出来却
        #       **没有任何出口**。
        #   ★ 旧值一个字不改：last_struct_coverage / last_struct_hit 的语义
        #     与数值都不动（_pool_shape 仍把它喂给模型，改值等于改模型输入，
        #     那要真跑对照）。这里只**加**对齐口径。
        #   ★ 两个池都只增不减，所以两个 hit 都是单调不减的。
        def _hit_of(_pool):
            if not aspects or not _pool:
                return []
            return [asp for asp in aspects
                    if any(_overlap_coef(asp, sa) >= 0.3 for sa in _pool)]

        hit_aspects: List[str] = _hit_of(
            self.undecidable_channel["structural_amps"])
        aligned_hits: List[str] = _hit_of(
            self.undecidable_channel.get("aligned_amps") or [])
        if aspects:
            struct_cov = len(hit_aspects) / len(aspects)
            aligned_cov = len(aligned_hits) / len(aspects)
        else:
            struct_cov = 0.0
            aligned_cov = 0.0
        self.undecidable_channel["last_struct_hit"] = len(hit_aspects)
        self.undecidable_channel["last_aligned_hit"] = len(aligned_hits)
        self.undecidable_channel["struct_coverage_history"].append(struct_cov)
        self.undecidable_channel["last_struct_coverage"] = struct_cov
        self.undecidable_channel.setdefault(
            "aligned_coverage_history", []).append(aligned_cov)
        self.undecidable_channel["last_aligned_coverage"] = aligned_cov
'''

# ============================================================
# B-3 产物 md 渲染（加性）
# ============================================================
B2_OLD = '''        cl_hist = list(ch.get("clarity_history") or [])
        sc_hist = list(ch.get("struct_coverage_history") or [])
        if not cl_hist and not sc_hist:
            return ""
        parts = []
        if cl_hist:
            parts.append(f"清晰度 {cl_hist[-1]:.2f}"
                         f"（模型自评，累计 {len(cl_hist)} 次记录）")
        if sc_hist:
            aspects = list(ch.get("und_aspects") or [])
            hit = int(ch.get("last_struct_hit", 0) or 0)
            _hard = (f"，已对上 {hit}/{len(aspects)} 个不可判定方面"
                     if aspects else "")
            parts.append(f"结构覆盖率 {sc_hist[-1]:.2f}"
                         f"（代码实算{_hard}）")
        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"
'''

B2_NEW = '''        cl_hist = list(ch.get("clarity_history") or [])
        sc_hist = list(ch.get("struct_coverage_history") or [])
        ac_hist = list(ch.get("aligned_coverage_history") or [])
        if not cl_hist and not sc_hist and not ac_hist:
            return ""
        parts = []
        if cl_hist:
            parts.append(f"清晰度 {cl_hist[-1]:.2f}"
                         f"（模型自评，累计 {len(cl_hist)} 次记录）")
        if sc_hist:
            aspects = list(ch.get("und_aspects") or [])
            hit = int(ch.get("last_struct_hit", 0) or 0)
            _hard = (f"，已对上 {hit}/{len(aspects)} 个不可判定方面"
                     if aspects else "")
            parts.append(f"结构覆盖率 {sc_hist[-1]:.2f}"
                         f"（代码实算{_hard}）")
        # [v1.21.69 B修] 对齐覆盖率**加性**渲染：只有算过才打这一行。
        # 旧产物 / 手工 dict 里没有 aligned_coverage_history ⇒ 不出现，
        # 于是 v1.21.57 起的旧断言（"结构覆盖率 0.60" / "已对上 6/10"）
        # 原样成立。（改产物格式优先加性、新段写成可选组。）
        if ac_hist:
            aspects = list(ch.get("und_aspects") or [])
            ahit = int(ch.get("last_aligned_hit", 0) or 0)
            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"
                      if aspects else "")
            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"
                         f"（代码实算{_hard2}）")
        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"
'''

# ============================================================
# B-4 日志渲染
# ============================================================
B3_OLD = '''            self.vp(f"   📘 不可判定结构覆盖率 "
                    f"{struct_cov:.0%}"
                    f"（{n_hit}/{n_aspects} und_aspects 命中）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（计入覆盖率），"
                    f"对齐结构 {n_aligned} 条（另计）")
'''

B3_NEW = '''            self.vp(f"   📘 不可判定结构覆盖率 "
                    f"{struct_cov:.0%}"
                    f"（{n_hit}/{n_aspects} und_aspects 命中）")
            # [v1.21.69 B修] 对齐覆盖率补上出口：aligned_amps 才是 prompt
            #   要求「正好对应 und_aspects 中某一项」的那一列。
            #   加性渲染：老产物 / 老 dict 没这个键时不打。
            _acov = ch.get("last_aligned_coverage")
            if _acov is not None:
                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"
                        f"（{int(ch.get('last_aligned_hit', 0) or 0)}"
                        f"/{n_aspects} und_aspects 命中）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（计入结构覆盖率），"
                    f"对齐结构 {n_aligned} 条（计入对齐覆盖率）")
'''

# ============================================================
# C 对撞对象：显式四支
# ============================================================
C_OLD = '''        if inp.is_base:
            object_desc = "这个问题里的 0 和 1"
        elif self.entry == "both":
            object_desc = "两个已经完成的形状"
        else:
            object_desc = "整体与每一个局部"

        if inp.is_base:
            speech_text = ""
        elif self.entry == "both":
            intro = "以下是要相撞的两端各自说过的话：\\n\\n"
            speech_text = (intro
                           + "\\n\\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        else:
            intro = "以下是这个整体所包含的各个局部说过的话：\\n\\n"
            speech_text = (intro
                           + "\\n\\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
'''

C_NEW = '''        # [v1.21.69 C修] 对撞对象的**显式四支**。原来只有三支，else 同时
        #   兜住「元层(all)」与「修行/研究层(0/1)」—— 两者的对撞对象根本
        #   不同，这是本项目反复栽的「兜底分支混层」。
        #   ★ 实测：生产入口下 0/1 **永远** is_base=True（_build_inp_base
        #     必带 question；且 _ENTRY_CONTENT_DEPS 里 0/1 的内容依赖是空表，
        #     本来也没有上游 view），所以除此之外的 else 分支对 0/1 不可达；
        #     V68 日志 135 行 ing 正文里含「各个局部」的 0 行、含「上游」的
        #     0 行 —— 研究层拿到的是「这个问题里的 0 和 1」，与分支一致。
        #   只把不可达的那一支改对，措辞不再混层；prompt 其余部分刻意不动。
        if inp.is_base:
            object_desc = "这个问题里的 0 和 1"
        elif self.entry == "both":
            object_desc = "两个已经完成的形状"
        elif self.entry == "all":
            object_desc = "整体与每一个局部"
        else:
            # entry 0/1 却带着上游 view —— 当前通道不可达，留给将来的接线。
            object_desc = "上游留下的形状与本圈的候选"

        if inp.is_base:
            speech_text = ""
        elif self.entry == "both":
            intro = "以下是要相撞的两端各自说过的话：\\n\\n"
            speech_text = (intro
                           + "\\n\\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        elif self.entry == "all":
            intro = "以下是这个整体所包含的各个局部说过的话：\\n\\n"
            speech_text = (intro
                           + "\\n\\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        else:
            intro = "以下是上游留下的形状各自说过的话：\\n\\n"
            speech_text = (intro
                           + "\\n\\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
'''

# ============================================================
# D-1 阈值常量
# ============================================================
D0_OLD = '''def _untraced_undecidable(und_aspects, evidences) -> List[str]:
'''

D0_NEW = '''# [v1.21.69 D修] 「有池内追溯」的**包含度**阈值（见 _untraced_undecidable
#   内的实证）。分母取 min，短句被长句包住时接近 1 —— 与 _similar 的
#   max 分母方向相反，正好补住"长句 ⊃ 短句"这种同义写法。
#   取 0.6：实测误报的两条包含度是 1.000 与 0.667（0.75 就救不回）；再低
#   会把只是"泛化同义"的也算成追溯。
_UNTRACED_OVERLAP = 0.6


def _untraced_undecidable(und_aspects, evidences) -> List[str]:
'''

# ============================================================
# D-2 判据
# ============================================================
D1_OLD = '''        if not any(_similar(bs, x, 0.55) or _similar(x, bs, 0.55)
                   or (bs and x and (bs in x or x in bs))
                   for x in srcs):
            out.append(s)
'''

D1_NEW = '''        # [v1.21.69 D修] 再加一层**包含度**判据。实证（V68 真产物）：
        #   _similar 的分母取 max，长句（und_aspect）里含一个短句
        #   （evidence.aspect）时比值被长句拉低 → 明明有追溯却报"无追溯"。
        #   两条误报的包含度是 1.000 / 0.667，而 _similar 分别是 0.33 / 0.50
        #   （阈值 0.55），都够不着。
        #   ★ 这一条动的是 _normalize_decidability 的输入：误报少了，采信就
        #     多了（decidable 更可能被拉成 partial）。方向是刻意的，但属
        #     运行期可见变化，不是"日志好看了"。
        if not any(_similar(bs, x, 0.55) or _similar(x, bs, 0.55)
                   or (bs and x and (bs in x or x in bs))
                   or _overlap_coef(bs, x) >= _UNTRACED_OVERLAP
                   for x in srcs):
            out.append(s)
'''

# ============================================================
# E-1 字段落盘收口（模块级唯一实现）
# ============================================================
E1_OLD = '''# ============================================================
# DGTF · 单层执行器（纯生成器）
# ============================================================
class DGTF:
'''

E1_NEW = '''# ============================================================
# 全量留痕 · 字段落盘（唯一实现）
# ============================================================
# 挂在 view 上的**内部账**：差分基准的快照。它不是 view 的字段，
# 所以 _view_field_map 与 View.to_dict（asdict）都不带它 —— 产物不受影响。
_VIEW_INTERNAL = ("_dump_canon",)


def _canon(v) -> str:
    """字段值的**规范化可比较**形式：JSON 串（键序无关）。"""
    try:
        return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(v)


def _view_field_map(view) -> dict:
    """view 的「字段名 → 值」：dataclass 字段 + 动态属性，asdict 的容错版。"""
    try:
        d = dict(asdict(view))
    except Exception:
        d = {}
    for _k, _v in vars(view).items():
        if _k.startswith("__") or _k in _VIEW_INTERNAL or _k in d:
            continue
        d[_k] = _v                    # 动态属性（asdict 覆盖不到）
    return d


def dump_view_fields(view, emit, *, prev=None, remember=False) -> None:
    """把 view 的**全部字段**逐条写进 emit（真跑时即日志）。

    [v1.21.68] 建立：不挑字段、机械全量 —— 新增字段自动被覆盖，不会因为
      漏写一行 print 而丢。
    [v1.21.69] 从 DGTF.dump_round 提出来给「收尾增量留痕」复用：同一件事
      两条通道各写一份，是本项目反复栽的坑。

    prev 非 None 时走**增量模式**：只打与 prev 有差异的字段。
      ★ 不维护「哪些字段是累积型」的清单 —— 那种清单一定会漏，
        本项目「无渲染点」事故就是这么来的。差异是**算**出来的。
    remember=True 时把「这一刻打出来的内容」的规范化快照挂到
      view._dump_canon 上，供收尾留痕差分。必须取在**真打出来的时刻**：
      取晚了（收尾前）会把圈后的后处理算进基准，于是那部分又漏一次。
    """
    try:
        _d = _view_field_map(view)
    except Exception as _e:
        emit(f"   ✗ 全量留痕失败：{type(_e).__name__}: {_e}")
        return
    _keys = sorted(_d.keys())
    if prev is not None:
        _same = [k for k in _keys if _canon(_d[k]) == prev.get(k)]
        _keys = [k for k in _keys if _canon(_d[k]) != prev.get(k)]
        emit(f"   （增量模式：{len(_same)}/{len(_d)} 个字段与上一圈留痕"
             f"完全相同、已省略；下面只列**变了的**）")
    for _k in _keys:
        _v = _d[_k]
        if isinstance(_v, (list, tuple, dict, set)):
            _v = list(_v)
            emit(f"   ├ {_k}：{type(_d[_k]).__name__} {len(_v)} 项")
            if _v:
                _js = json.dumps(_v, ensure_ascii=False, indent=1,
                                 default=str)
                for _ln in _js.splitlines():
                    emit("   │ " + _ln)
        elif isinstance(_v, str) and "\\n" in _v:
            emit(f"   ├ {_k}：str {len(_v)} 字")
            for _ln in _v.splitlines():
                emit("   │ " + _ln)
        else:
            emit(f"   ├ {_k}：{'' if _v is None else _v}")
    emit("   └ 全量留痕结束")
    if remember:
        try:
            view._dump_canon = {k: _canon(v) for k, v in _d.items()}
        except Exception:
            pass


# ============================================================
# DGTF · 单层执行器（纯生成器）
# ============================================================
class DGTF:
'''

# ============================================================
# E-2 dump_round 收口 + dump_final
# ============================================================
E2_OLD = '''    def dump_round(self, view, inp) -> None:
        """[v1.21.68] 每层每圈的**全量留痕**：把本圈 view 的所有字段写进日志。

        为什么要有它：此前每圈只打**摘要** —— 候选只报条数、ing 只报
        **字数**、悬置/债务/清算只报计数。正文与明细都不落日志，出问题只能
        从产物反推（而产物只留**最后一圈**的 view）。

        ★ 与产物 md 的「全量字段」附录同一条哲学：**不挑字段、机械全量** ——
          用 dataclasses.asdict 逐字段输出、**不截断**，动态挂上去的属性
          （如 `_expanded_descs` 去重账）也一并带上。新增字段自动被覆盖，
          不会因为漏写一行 print 而丢。
        """
        if not self.verbose:
            return
        _rnd = getattr(inp, "round_no", 0) or 0
        _role = (getattr(inp, "round_role", "") or "").strip()
        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 圈全量留痕 · entry={self.entry} · 第 {_rnd} 圈"
                f" · {_role or '（无角色）'}")
        self.vp("╚" + "═" * 58 + "╝")
        try:
            _d = asdict(view)
        except Exception as _e:
            self.vp(f"   ✗ 全量留痕失败（asdict）：{type(_e).__name__}: {_e}")
            return
        for _k, _v in vars(view).items():
            if _k.startswith("__") or _k in _d:
                continue
            _d[_k] = _v                    # 动态属性（asdict 覆盖不到）
        for _k in sorted(_d.keys()):
            _v = _d[_k]
            if isinstance(_v, (list, tuple, dict, set)):
                _v = list(_v)
                self.vp(f"   ├ {_k}：{type(_d[_k]).__name__} {len(_v)} 项")
                if _v:
                    _js = json.dumps(_v, ensure_ascii=False, indent=1,
                                     default=str)
                    for _ln in _js.splitlines():
                        self.vp("   │ " + _ln)
            elif isinstance(_v, str) and "\\n" in _v:
                self.vp(f"   ├ {_k}：str {len(_v)} 字")
                for _ln in _v.splitlines():
                    self.vp("   │ " + _ln)
            else:
                self.vp(f"   ├ {_k}：{'' if _v is None else _v}")
        self.vp("   └ 圈全量留痕结束")
'''

E2_NEW = '''    def dump_round(self, view, inp) -> None:
        """[v1.21.68] 每层每圈的**全量留痕**：把本圈 view 的所有字段写进日志。

        为什么要有它：此前每圈只打**摘要** —— 候选只报条数、ing 只报
        **字数**、悬置/债务/清算只报计数。正文与明细都不落日志，出问题只能
        从产物反推（而产物只留**最后一圈**的 view）。

        ★ 与产物 md 的「全量字段」附录同一条哲学：**不挑字段、机械全量** ——
          逐字段输出、**不截断**，动态挂上去的属性（如 `_expanded_descs`
          去重账）也一并带上。新增字段自动被覆盖，不会因为漏写一行
          print 而丢。

        [v1.21.69] 字段落盘收口到模块级 `dump_view_fields()`（唯一实现），
          本方法与 `dump_final` 共用；打完把这一刻的规范化快照挂到
          `view._dump_canon`，供收尾留痕做**增量**差分。
        """
        if not self.verbose:
            return
        _rnd = getattr(inp, "round_no", 0) or 0
        _role = (getattr(inp, "round_role", "") or "").strip()
        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 圈全量留痕 · entry={self.entry} · 第 {_rnd} 圈"
                f" · {_role or '（无角色）'}")
        self.vp("╚" + "═" * 58 + "╝")
        dump_view_fields(view, self.vp, remember=True)

    def dump_final(self, view) -> None:
        """[v1.21.69 E修] **收尾留痕**：跑圈 + 回填之后补一段**增量**留痕。

        ★ 为什么需要它：每圈的 dump 发生在 `DGTF.run` 里，而
          `round_log` / `roles_run` / `carry_checks` / `carry_dropped_all`
          是**回填**的，回填发生在最后一圈 dump **之后** ⇒ 这几个字段
          在任何一段留痕里都恒为 0 项 ——「全量留痕」对它们从来没兑现过。
          实测 verif_V68.log 的 4 段留痕：这四个字段每段都是 0 项；
          每段 26k-31k 字符全由 candidates / rendered / untouched 撑着
          （逐圈内容，不是累积）。所以 v1.21.68 遗留 1 说的
          「n 圈约 n(n+1)/2 份重复」**不存在**，真问题正相反：没出口。

        ★ 增量而非全量：只打与上一圈 dump 有差异的字段，并交代省略了几个。
          差分基准 = `dump_round` 挂在 view 上的 `_dump_canon`。
        """
        if not self.verbose:
            return
        _rounds = int(getattr(view, "rounds_run", 0) or 0) or int(
            getattr(view, "rounds_cap", 0) or 0)
        _roles = " → ".join(str(r) for r in (getattr(view, "roles_run", [])
                                             or []))
        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 收尾留痕 · entry={self.entry} · 共 {_rounds} 圈"
                f" · {_roles or '（无角色记录）'}")
        self.vp("╚" + "═" * 58 + "╝")
        dump_view_fields(view, self.vp,
                         prev=getattr(view, "_dump_canon", None))
'''

# ============================================================
# E-3 收尾调用点
# ============================================================
E3_OLD = '''            else:
                view.closure_reason = (
                    f"soft_max_unsettled（{stl['leftover']} 项债务未清算）")
                self.vp(f"   ⚠️ 终局清算：{stl['leftover']} 项未清算"
                        f"（不是停止理由，单列）")
'''

E3_NEW = '''            else:
                view.closure_reason = (
                    f"soft_max_unsettled（{stl['leftover']} 项债务未清算）")
                self.vp(f"   ⚠️ 终局清算：{stl['leftover']} 项未清算"
                        f"（不是停止理由，单列）")

        # ---- 8. 收尾增量留痕（跨圈累积的字段只有这里看得到）----
        # [v1.21.69 E修] 两条跑圈通道都汇到这里，所以只挂一处就全覆盖。
        #   `_dg` 是本节前面为质量检查建的那个实例，复用它、把 verbose
        #   还原成主开关。
        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)
        except Exception as _e:
            self.vp(f"   ✗ 收尾留痕失败：{type(_e).__name__}: {_e}")
'''

# ============================================================
# 版本号 + changelog 头
# ============================================================
V_OLD = "元 DGTF · v1.21.68"
V_NEW = "元 DGTF · v1.21.69"
VER_OLD = '__version__ = "1.21.68"'
VER_NEW = '__version__ = "1.21.69"'

HEAD_OLD = '''  v1.21.68 是本轮留痕版：每层每圈把 view 的**全部字段**机械打进日志
  （`DGTF.dump_round`），并让 **ing 正文**就地可见 —— 此前每圈只打摘要。
'''
HEAD_NEW = '''  v1.21.68 是本轮留痕版：每层每圈把 view 的**全部字段**机械打进日志
  （`DGTF.dump_round`），并让 **ing 正文**就地可见 —— 此前每圈只打摘要。
  v1.21.69 是本轮修正版：A/B/C/D/E 五项（两处真 bug + 一处口径错 +
  一处潜在串层 + 一处"没出口"误诊成"重复"），**每项先量后改**，
  冒烟带负对照；外部评审有两项诊断与实际不符，照实写。
'''

INS_OLD = '''  ════════════════════════════════════════════════════════════
v1.21.67 相对 v1.21.66 的改动（日志收全 + 产物全量附录）
════════════════════════════════════════════════════════════
'''


def main():
    raw = SRC.read_bytes()
    src = raw.decode("utf-8")
    assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF？"
    n_crlf = src.count("\r\n")
    src = src.replace("\r\n", "\n")
    print(f"读入 {SRC.name}：{len(raw)} 字节 / {n_crlf} 行（纯 CRLF）")

    # 版本段行号序列（改之前）
    def _vseq(s):
        return [(m.group(1), s[:m.start()].count("\n") + 1)
                for m in re.finditer(r"^v(1\.21\.\d+) 相对", s, re.M)]
    print("改前版本段顺序：", _vseq(src))

    print("\n[打补丁]")
    src = _rep(src, A_OLD, A_NEW, "A")
    src = _rep(src, B0_OLD, B0_NEW, "B-1")
    src = _rep(src, B1_OLD, B1_NEW, "B-2")
    src = _rep(src, B2_OLD, B2_NEW, "B-3")
    src = _rep(src, B3_OLD, B3_NEW, "B-4")
    src = _rep(src, C_OLD, C_NEW, "C")
    src = _rep(src, D0_OLD, D0_NEW, "D-1")
    src = _rep(src, D1_OLD, D1_NEW, "D-2")
    src = _rep(src, E1_OLD, E1_NEW, "E-1")
    src = _rep(src, E2_OLD, E2_NEW, "E-2")
    src = _rep(src, E3_OLD, E3_NEW, "E-3")
    src = _rep(src, V_OLD, V_NEW, "版本·标题")
    src = _rep(src, VER_OLD, VER_NEW, "版本·__version__")
    src = _rep(src, HEAD_OLD, HEAD_NEW, "changelog 头")
    src = _rep(src, INS_OLD, CHANGELOG.rstrip("\n") + "\n\n" + INS_OLD,
               "changelog 正文")

    print("\n[换回 CRLF]")
    assert "\r" not in src, "归一后仍有裸 CR"
    out = src.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n"), "CRLF 断言失败"
    assert out.count("\r") == out.count("\r\n"), "有裸 CR"
    DST.write_bytes(out.encode("utf-8"))
    print(f"写出 {DST.name}：{len(out.encode('utf-8'))} 字节 / "
          f"{out.count(chr(10))} 行")
    print("改后版本段顺序：", _vseq(src))
    print("\n完成。下一步：改 smoke_test.py 的 SRC，跑冒烟。")


if __name__ == "__main__":
    sys.exit(main())
