#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 第三档] 接 `check_v1221_p7` 与 `phase_p7`，并写版本定稿脚本。

本脚本做三件事：
  ① 往 `_v1221_checks.py` 追加 `check_v1221_p7`（幂等：已存在则替换）；
  ② 把 `_v122_verify.py` 里的 `phase_p7 = _phase_todo("p7")` **直接替换**成
     真实现（同名替换，PHASES 那几行不用动）；
  ③ 生成 `元DGTF-V1.22.1.py`（= rc3 + 版本号 + v1.22.1 changelog 三段分段），
     并自检「除版本号与 changelog 外与 rc3 无差异」。

★ 不写反斜杠：换行用 chr(10)，引号用 chr(34)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)
Q = chr(34)

REPO = Path("_v1221_checks.py")
VERIFY = Path("_v122_verify.py")
RC3 = Path("元DGTF-V1.22.1-rc3.py")
FINAL = Path("元DGTF-V1.22.1.py")

CHECK7 = '''def check_v1221_p7(SRC=None):
    """[v1.22.1 P7] 明确不做（只出说明，不动代码）。

    ★ 本档**不改引擎**：只查决策记录在不在、三条在不在，外加一条负对照 ——
      「这三件事不许跑进产物头部」（决策记录不是产物级告警）。
    """
    try:
        from pathlib import Path as _P
        doc = _P("docs/不做什么-v1221.md")
        assert doc.is_file(), "缺 docs/不做什么-v1221.md"
        text = doc.read_text(encoding="utf-8")
        assert "不拆模块" in text, "缺「不拆模块」"
        assert "不扩动词白名单" in text, "缺「不扩动词白名单」"
        assert "不删任何机制" in text, "缺「不删任何机制」"

        # 负对照：三条都不许出现在产物头部渲染里
        src = _v1221_src_text(SRC)
        _i = src.find("def save_result")
        _head = src[_i:_i + 20000] if _i >= 0 else ""
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            assert k not in _head, "决策记录跑进了产物头部：" + k

        print("  ✓ v1.22.1 P7：决策记录三条齐 + 负对照（不进产物头部）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P7 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


'''

PHASE7 = '''def phase_p7(src, mod):
    """[v1.22.1 P7] 明确不做：只查决策记录，不动代码。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    doc = HERE / "docs" / "不做什么-v1221.md"
    check("P7.1.a", doc.is_file(), "docs/不做什么-v1221.md 存在")
    if doc.is_file():
        t = doc.read_text(encoding="utf-8")
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            check("P7.1.b." + k, k in t, "决策记录含「" + k + "」")
    else:
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            check("P7.1.b." + k, False, "文档不存在")
    # P7 的骨架检查（与 smoke 同口径）
    try:
        check("P7.2", bool(mod) and hasattr(mod, "__version__"),
              "模块可加载（__version__ = " + str(getattr(mod, "__version__", "?")) + "）")
    except Exception as e:  # noqa: BLE001
        check("P7.2", False, type(e).__name__ + ": " + str(e))
    # 负对照：三条不许进产物头部
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)
    _i = txt.find("def save_result")
    _head = txt[_i:_i + 20000] if _i >= 0 else ""
    _leak = [k for k in ("不拆模块", "不扩动词白名单", "不删任何机制")
             if k in _head]
    check("P7.3", not _leak, "决策记录不进产物头部（泄漏 " + str(_leak) + "）")


'''

CHANGELOG = NL.join([
 "v1.22.1 ── 三档收尾（P1 行动闭环 / P2 triage / P3 负对照 / P4 对照 / P5 取向 / P6 tier / P7 不做）",
 "  本版是 v1.22.0 的**三档加性**收尾：第一档（P1/P2/P3）→ P2b（第一档续做）→",
 "  第二档（P4/P5/P6）→ 第三档（P7 只出说明）+ 全局收尾。",
 "  ★ 第一档的 P2 **单档未通过**（触发条件修通、效果判据未达标），按任务书",
 "  停在第一档；续做 P2b 换匹配对象后打通，P2 才**重判为通过（P2a + P2b 合并）**。",
 "  红线守住：rc1 起累计纯删除行 0、AST 符号消失 0 项、新增 6 项逐条登记",
 "  （见 _v122_ast_registry.json）。逐档报告见 v1221_p1~p6_报告.md + v1221_报告.md。",
 "",
 "  【第一档（无前置）】",
 "  P1 研究层直接产出结构化 actions（本档通过）",
 "    · `_he` schema 加 `decidable_product.actions[]` + 约束段；",
 "    · ★ `dec_norm` 白名单加 `actions` —— 不加就是**静默吞字段**（新函数",
 "      `_norm_schema_actions` 立据）；",
 "    · `_extract_actions` 改「schema 优先 + 词法兜底」：原词法版改名",
 "      `_extract_actions_lexical`（正文一字未动），兜底结果带 `_source` 标签；",
 "    · `action_incomplete` 语义改「没按 schema 产出」；新增 `action_fields_missing`",
 "      并**同时进 `_V122_HARD_FLAGS`** —— 这条是读真跑 packed 才抓到的真 bug：",
 "      flag 写进了 errors，却被 19 行后的 quality_flags 整体重算冲掉。",
 "    实测：三题真跑 action 5/6/4（全 ≥3）；rubric 平均 2.00；`action_incomplete`",
 "    从改前 4/4 份全触发 → 改后 0/3。动词白名单仍 19 条（未拟合数据）。",
 "",
 "  P2 triage 触发条件改挂结构标签（**本档未通过**，由 P2b 补齐）",
 "    · 新增 `_TRIAGE_STRUCTURAL_PREFIXES`（`[外]`）/ `_is_triage_candidate`",
 "      （结构标签 ∪ 语义关键词）/ `_is_never_downgrade`（真·自指不许降级）；",
 "      旧词表 `_TRIAGE_KEYS` 一字未删（加性）。",
 "    · 机制判据 15 项全绿，但三题真跑 triage = [0, 0, 0]：触发条件已修通，",
 "      卡在下游 `_similar(aspect, anchor.claim, 0.6)`（14 条侧面最高词重叠",
 "      0.167 / 中位 0.000 / ≥0.6 的 0 条）——根因是**语义类型不匹配**：",
 "      `undecidable_aspects` 说「缺什么材料」，`anchor.claim` 说「是什么事实」。",
 "",
 "  P3 仅源码机制做负对照（本档通过；本版不删任何机制）",
 "    · 对审计判「仅源码」的 5 条各写负对照：4 条**能触发**（条件窄但成立，",
 "      保留）、1 条 `_all_settle_streak` 判**条件不可达**（内联在 `_run_layer`",
 "      的圈循环里、无宿主可调用）→ 归档 `pending_fix`。",
 "    · 与审计报告「仅源码」5 项做**两向对账**（集合相等判据）。",
 "    · `no_push_when_idle` 用**差分**负对照（同输入换开关看分支是否真变），",
 "      不是「函数返回了东西就算工作」。",
 "  ⇒ 第一档整体：P1 通过 / P2 未通过 / P3 通过 → 按任务书禁令停在第一档。",
 "",
 "  【P2b（第一档续做，单点）→ P2 重判通过】",
 "    · **不改阈值、不改触发条件，只换匹配对象**：锚点快照加 `answers`",
 "      （「我能回答哪些侧面」）；新增 `_hit_by_answers`（`_overlap_coef` +",
 "      `_UNTRACED_OVERLAP`=0.6，双向）与 `_hit_by_claim`（老路径，`0.6` 字面",
 "      **一字不动**），两条取 OR，都在 tier 门内；`_load_anchors` 加 `answers`",
 "      键（不加仍是静默吞字段）；`_anchor_crosscheck` 的 `_hit` 改双路径。",
 "    · 实测：三题真跑 triage **[1, 0, 0]** → 主判据达标；命中的是**语义轴**",
 "      而非某串写死的字（P2a 那条侧面原文与本次措辞不同，仍被 a2 命中）。",
 "    · ★ 顺带查清两件事：① `_overlap_coef` **是对称函数**（分母取 min，与方向",
 "      无关）→ 任务书的「反向再查一次」与正向**等价**（冗余，留待下一版）；",
 "      ② triage 只出**建议清单**、**没有任何写 `decidability_log` 的路径**",
 "      （crosscheck 里 `apply_decidability_change` 只出现在注释里、`append` 0 次）",
 "      → 「triage 引起的 und→partial」结构上恒为 0，P2.4.b 降为观察项是对的。",
 "    · 附带把 `base` 加了 `answers_all_missing` 留痕键（answers 全缺时提示）。",
 "  ⇒ **P2 重判为「通过（P2a + P2b 合并）」**，第一档解冻。`--phase p2` 的",
 "    15/2 保留为 P2a 单档历史，不改写；该档输出里加了一行非判定性说明防误读。",
 "",
 "  【第二档（前置：第一档通过）】",
 "  P4 一致率 ON/OFF 对照（本档判据全绿；**结论「无结论」**）",
 "    · 每臂 3 次、同题同配置（route 1 / rounds 1:4 / 默认 profile）。",
 "    · ★ 任务书指定的口径（产物 md 的「三态多票：high/medium/low」行）在",
 "      **OFF 臂不可用**：那一行读每条子问题的 `stability`，而 `stability`",
 "      **只有多票路径才写** —— OFF 臂子问题里连键都没有，引擎照 `(0+0)/n`",
 "      印出「一致率 0% ⚠️ unstable（＜50%）」。**那是「没算」，不是测量值。**",
 "      照抄口径会得出「多票更好 +100%」这个建立在不存在读数上的结论。",
 "    · 改用**两臂都可得**的口径 `tri_state = [agree, total]`：",
 "      ON 80/80/80%（组内极差 0.0%）、OFF 50/80/60%（组内极差 30.0%）、",
 "      组间差 +16.7% → 按 P4.4 自己的两向规则（组内极差 ≥ 组间差 → 无结论）",
 "      ⇒ **无结论**。",
 "    · P4.1 要的运行时开关在 v1.22.0 就已存在（`_action_on(config,",
 "      \"tri_multi_vote\")` + `DEFAULT_CONFIG.actions.tri_multi_vote=True`）",
 "      → 本档**未改引擎**，rc2 与 rc1b **逐字节相同**。",
 "  P5 auto 取向回填（本档通过）",
 "    · ★ 任务书前提不成立：`auto_plan` 的**单调用**分支（`run()` 走的就是它）",
 "      原来不带 `orientation` → `_auto_plan_used` 永远拿不到取向、头部那行",
 "      一行都印不出来。修法：在**同一次调用**的 prompt 里一并要取向",
 "      （schema 加 `orientation` 段），三处 return 都带出，**成本不变**",
 "      （冒烟用打桩断言 `len(calls) == 1` 钉住）。",
 "    · 头部加「**取向判定（plan_orientation）**」+「⚠️ **取向错配**」告警",
 "      （触发条件：声明 auto 且判定非 decision）。",
 "    · 真跑：auto 判 boundary → 两行双双命中；显式 boundary → 无错配告警",
 "      （负对照）。",
 "    · ★ 顺带看到：**取向判定本身有噪声** —— 同题两次 auto 跑判出一 boundary",
 "      一 decision。P5 的价值就是让它**可见**；要下「稳不稳」的结论需同条件",
 "      ≥3 次重复（本档只跑 2 次，不下结论）。",
 "  P6 tier 缺省时的显式提示（本档通过）",
 "    · ★ 任务书骨架**恒不触发**：`sum(1 for a in out if \"tier\" in a and",
 "      a[\"tier\"] is not None)` 的 `out` 里每条都已被补过缺省 `tier`，两个",
 "      条件恒真 → 计数恒等于总数 → 警告永不出现。正解是在**补默认值之前的",
 "      原始条目**上数（`_n_explicit_tier`），并加冒烟断言钉住这一点。",
 "    · 全缺省 → 头部「⚠️ **锚点 tier 警告**」（**不阻断**：tier 没写只等于",
 "      「对照会空转」，把它升级成致命错误是没必要的失败）。",
 "    · 真跑：全缺省快照有警告、有一条 `tier=1` 的无警告（负对照）；",
 "      红线保留 —— 无 tier 的锚点仍**不进引用表**。",
 "  ⇒ 第二档整体：P4 通过 / P5 通过 / P6 通过。",
 "",
 "  【第三档（前置：第二档通过）】",
 "  P7 明确不做（只出说明，不动代码）",
 "    · 决策记录 `docs/不做什么-v1221.md`：不拆模块 / 不扩动词白名单·不放宽",
 "      `min_actions` / 不删任何机制。三条都写了依据与前置条件。",
 "    · **不进产物头部**（决策记录不是产物级告警）；冒烟带负对照钉住。",
 "",
 "  【全局收尾】",
 "  F.1 20 题全量回归（economy + 每层 2~3 圈；降档如实写在报告头与 index.json）；",
 "  F.2 版本号 + 本 changelog（三档分段）；F.3 v1221_报告.md 十节；",
 "  F.4 交付物清单核对。",
 "",
 "  【新增符号 6 项，逐条登记在 _v122_ast_registry.json】",
 "  `_norm_schema_actions` / `_extract_actions_lexical` / `_is_triage_candidate`",
 "  / `_is_never_downgrade` / `_hit_by_answers` / `_hit_by_claim`",
 "",
])


def main() -> int:
    # ---- ① 检查仓库 ----
    t = REPO.read_bytes().decode("utf-8").replace(CR + LF, LF)
    i = t.find("def check_v1221_p7")
    if i >= 0:
        t = t[:i]
    REPO.write_bytes((t.rstrip(NL) + NL + NL + NL + CHECK7)
                     .replace(NL, CR + LF).encode("utf-8"))
    ast.parse(REPO.read_bytes().decode("utf-8").replace(CR + LF, LF))
    print("  ✓ _v1221_checks.py += check_v1221_p7")

    # ---- ② phase_p7 ----
    v = VERIFY.read_bytes().decode("utf-8")
    assert v.count(CR + LF) == v.count(NL) and (CR + CR + LF) not in v
    vt = v.replace(CR + LF, NL)
    old = 'phase_p7 = _phase_todo("p7")' + NL
    assert vt.count(old) == 1, vt.count(old)
    vt = vt.replace(old, PHASE7, 1)
    ast.parse(vt)
    out = vt.replace(NL, CR + LF)
    assert out.count(NL) == out.count(CR + LF) and (CR + CR + LF) not in out
    VERIFY.write_bytes(out.encode("utf-8"))
    print("  ✓ _v122_verify.py: phase_p7 已换成真实现")

    # ---- ③ 定稿 ----
    if FINAL.exists():
        print("  · " + FINAL.name + " 已存在（跳过生成）")
        return 0
    s = RC3.read_bytes().decode("utf-8")
    assert s.count(CR + LF) == s.count(NL) and (CR + CR + LF) not in s
    f = s.replace(CR + LF, NL)
    reps = [
        ("元 DGTF · v1.22.0", "元 DGTF · v1.22.1", "docstring 标题"),
        ('__version__ = "1.22.0"', '__version__ = "1.22.1"', "__version__"),
        ("v1.22.0 ── 六阶段改造", CHANGELOG + "v1.22.0 ── 六阶段改造", "changelog 段"),
    ]
    for old_s, new_s, name in reps:
        got = f.count(old_s)
        assert got == 1, "[" + name + "] 锚点 " + str(got) + " 次"
        f = f.replace(old_s, new_s, 1)
        print("  ✓ " + name)
    ast.parse(f)
    fo = f.replace(NL, CR + LF)
    assert fo.count(NL) == fo.count(CR + LF) and (CR + CR + LF) not in fo
    FINAL.write_bytes(fo.encode("utf-8"))
    print("  ✓ 写回 " + FINAL.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
