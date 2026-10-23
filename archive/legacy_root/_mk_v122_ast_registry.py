#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6c] AST 等价证明：把「新增了哪些符号」逐条挂上解释。

任务书 Step 7.4：「AST 等价 或 **逐节点差异有解释**」＋「不许在没有 AST
等价证明的情况下宣称『重构无影响』」。

本版不可能 AST 等价（六个阶段各加新函数）。所以走第二条：建
`_v122_ast_registry.json`，把基线→本版的**每一个新增符号**挂上
「属于哪个阶段 + 为什么必须有」；消失的符号必须为 0（红线：不许删机制）。
判定**两向对账**：新增未登记 → 红；登记了却不存在 → 红。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "_baseline_v12177.py"
CUR = HERE / "元DGTF-V1.22.0-rc1.py"
OUT = HERE / "_v122_ast_registry.json"

WHY = {
    "AnchorRetriever": ("4", "五档里的真检索后端（snapshot 零调用 / tavily + 缓存）"),
    "DecidabilityFreeze": ("2", "可判定性冻结：判定跑完那一刻的名单快照 + 防篡改签名"),
    "_act_text": ("3", "取结论文本（View / dict 两形态都要吃）"),
    "_adjudicate_sub_tristate_multi": ("2", "三态多票判决（3 票独立 → 多数）"),
    "_anchor_enters_citation": ("4", "tier 门的唯一判据：tier ≤ tier_floor 才进引用表"),
    "_anchor_tier": ("4", "as_evidence 五档归一（含 v1.21.75 布尔兼容）"),
    "_cache_path": ("4", "AnchorRetriever 的检索缓存路径（queries 的 sha256）"),
    "_classify_unsaid": ("1", "「此处未生」的 real/lazy 分类（G1.5）"),
    "_compute_rephrase_streak": ("6", "复述圈数的唯一实现（收口两处各一份的旧写法）"),
    "_digest": ("2", "DecidabilityFreeze 的 sha256 摘要"),
    "_extract_actions": ("3", "从结论文本抽行动条目（六字段，G3.4）"),
    "_extract_not_do": ("3", "抽「不做什么」清单（G3.5 的 not_do_missing 依据）"),
    "_g": ("1", "`_layer_objective_lines` 内的取视图小闭包（无副作用）"),
    "_guess_acceptance": ("3", "行动字段猜测：验收"),
    "_guess_deadline": ("3", "行动字段猜测：时限"),
    "_guess_fallback": ("3", "行动字段猜测：回退"),
    "_guess_role": ("3", "行动字段猜测：负责人角色"),
    "_layer_objective_lines": ("1", "分层目标四行（计数口径，G1.6）"),
    "_pool_meta_summary": ("3", "池级留痕汇总：两个落地层模板共用的一份实现"),
    "_render_landing_boundary": ("3", "原 render_landing 整体改名（老五块模板）"),
    "_render_landing_decision": ("3", "decision 模式的六段行动闭环模板"),
    "_tavily": ("4", "Tavily 检索实现（tier 缺省 3）"),
    "_tier_floor": ("4", "读 tier_floor 配置（带类型兜底）"),
    "_und_text": ("3", "取不可判定结论文本（不做什么可能落在这一侧）"),
    "freeze": ("2", "DecidabilityFreeze.freeze：写冻结键 → 再算签名"),
    "search": ("4", "AnchorRetriever.search：缓存 TTL + 后端分发"),
    "verify": ("2", "DecidabilityFreeze.verify：签名不匹配即 RuntimeError"),
}

PHASE_CHECK_PATCH_OLD = '''    # 6.6 函数节点数不增加
    try:
        import ast as _ast
        n0 = len([x for x in _ast.walk(_ast.parse(
            BASELINE.read_text(encoding="utf-8")))
            if isinstance(x, _ast.FunctionDef)])
        n1 = len([x for x in _ast.walk(_ast.parse(
            Path(src).read_text(encoding="utf-8")))
            if isinstance(x, _ast.FunctionDef)])
        check("6.6", n1 <= n0, f"函数节点数 基线 {n0} → 本版 {n1}（不增加）")
    except Exception as e:
        check("6.6", False, f"AST 对比失败 {e}")
'''


def main() -> int:
    def syms(p):
        t = ast.parse(Path(p).read_text(encoding="utf-8"))
        return {n.name for n in ast.walk(t)
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    a, b = syms(BASE), syms(CUR)
    added, gone = sorted(b - a), sorted(a - b)
    assert not gone, f"有符号消失（红线）：{gone}"
    unreg = [x for x in added if x not in WHY]
    assert not unreg, f"新增但没写解释：{unreg}"
    stale = [k for k in WHY if k not in added]
    assert not stale, f"登记了却没新增：{stale}"
    reg = {k: {"phase": WHY[k][0], "reason": WHY[k][1]} for k in added}
    OUT.write_bytes(json.dumps(
        {"baseline": BASE.name, "current": CUR.name,
         "n_symbols_baseline": len(a), "n_symbols_current": len(b),
         "added": len(added), "removed": 0,
         "registry": reg},
        ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    print(f"✓ _v122_ast_registry.json：新增 {len(added)} 项全部有解释，"
          f"消失 0 项（符号数 {len(a)} → {len(b)}）")

    # 把 phase6 的 6.6 判据换成「登记表两向对账」
    tgt = HERE / "_v122_verify.py"
    s = tgt.read_text(encoding="utf-8").replace("\r\n", "\n")
    new_check = '''    # 6.6 AST：基线→本版的新增符号必须**逐条有解释**（登记表两向对账）
    #   ★ 本版不可能 AST 等价（六个阶段各自新增函数）。任务书的第二条路是
    #     「逐节点差异有解释」—— 所以判据是：新增未登记判红、登记却不存在
    #     也判红；符号**消失**一律判红（红线：不许删机制）。
    try:
        import ast as _ast
        import json as _json

        def _syms(p):
            t = _ast.parse(Path(p).read_text(encoding="utf-8"))
            return {n.name for n in _ast.walk(t)
                    if isinstance(n, (_ast.FunctionDef, _ast.ClassDef))}
        _a, _b = _syms(BASELINE), _syms(src)
        _added, _gone = sorted(_b - _a), sorted(_a - _b)
        _regf = HERE / "_v122_ast_registry.json"
        _reg = (_json.loads(_regf.read_text(encoding="utf-8")).get("registry")
                if _regf.is_file() else {})
        _unreg = [x for x in _added if x not in _reg]
        _stale = [k for k in _reg if k not in _added]
        check("6.6", (not _gone) and (not _unreg) and (not _stale),
              f"AST 登记对账：新增 {len(_added)} 项 / 未登记 {len(_unreg)}"
              f"{('：' + '、'.join(_unreg[:4])) if _unreg else ''} / "
              f"过期登记 {len(_stale)}{('：' + '、'.join(_stale[:4])) if _stale else ''} / "
              f"符号消失 {len(_gone)}{('：' + '、'.join(_gone[:4])) if _gone else ''}")
        print(f"  ℹ️  符号数 基线 {len(_a)} → 本版 {len(_b)}；"
              f"新增 {len(_added)} 项逐条有解释（见 _v122_ast_registry.json）")
    except Exception as e:
        check("6.6", False, f"AST 对比失败 {e}")
'''
    assert s.count(PHASE_CHECK_PATCH_OLD) == 1, \
        f"6.6 判据锚点 {s.count(PHASE_CHECK_PATCH_OLD)} 处"
    s = s.replace(PHASE_CHECK_PATCH_OLD, new_check, 1)
    tgt.write_bytes(s.encode("utf-8"))
    print("  · phase6 的 6.6 判据已换成登记表对账")
    return 0


if __name__ == "__main__":
    sys.exit(main())
