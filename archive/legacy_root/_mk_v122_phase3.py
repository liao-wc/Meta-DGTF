#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段3] decision 模式强制行动闭环（任务书 Step 3.1~3.6）。

- 3.1 `DEFAULT_CONFIG["actions"]["landing_decision"] = True`
- 3.2 `render_landing` 退成分流壳；老实现整体改名 `_render_landing_boundary`
- 3.3 `_render_landing_decision(res)`（六段模板）
- 3.4 `_extract_actions` + 五字段猜测 + `_guess_*`
- 3.5 硬约束 `action_incomplete` / `not_do_missing`（进 view.errors +
       view.quality_flags）
- 3.6 行动清单 / 不做什么 落进 packed，供 bench_score rubric 读

★ 两处「按任务书照抄会出问题」的地方，按意图改、并在报告里写明：
  1) `_extract_actions(view)` 任务书传的是 View 对象，但落地层渲染拿到的是
     **dict**（packed 里的 views.1）→ 两形态都要吃（同 `_classify_unsaid`）。
  2) 任务书 3.3 的「五、不做什么」段是空的，而 3.5 又要求 `not_do_missing`
     能被判 —— 按字面实现会让**每一份** decision 产物都缺 not_do。
     所以「不做什么」从结论文本里抽（含 不做/不要/暂不… 的句子）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

# ---------------------------------------------------------------- 3.1 开关
A_SWITCH = '        "tri_multi_vote": True,\n'
B_SWITCH = ('        "tri_multi_vote": True,\n'
            '        # [v122 P3 G3.1] decision 取向走「行动闭环」落地层；\n'
            '        #   boundary 取向仍走原五块模板（这里给开关不是给行为，\n'
            '        #   分流判断在 render_landing 里）。\n'
            '        "landing_decision": True,\n')

# ------------------------------------------------------------ 3.2 取向落字段
A_ORI = "        route = self._route_by_decidability(question, route, orientation)\n"
B_ORI = ("        # [v122 P3 G3.5] 取向要留给收尾环节用：decision 模式\n"
         "        #   强制行动闭环（action_incomplete / not_do_missing）。\n"
         "        self._orientation = str(orientation or \"auto\")\n"
         + A_ORI)

# ---------------------------------------------------------------- 3.4 抽取器
EXTRACT = '''
# ============================================================
# [v122 阶段3 G3.4] decision 模式的行动抽取
# ============================================================
# 【为什么是抽不是让模型填】产物里已经有结论文本了；再要一次 JSON 会让
#   「结论」与「行动」变成两份可能互相矛盾的抽样。先抽，抽不出来就如实
#   标 `action_incomplete` —— 那正是这一阶段要暴露的问题。
_ACTION_VERB_WHITELIST = (
    "指派", "指定", "核查", "测量", "提交", "申请", "封堵",
    "清淤", "试点", "备案", "签发", "复核", "排查", "改造",
    "扩容", "委托", "报审", "谈判", "调取",
)

_ACTION_ROLES = ("区防汛办", "排水公司", "信息科", "医务科",
                 "法务", "财务", "项目组", "上级部门")

_ACTION_DEADLINES = ("汛期前", "本月内", "30 天内", "本季度", "下一财年",
                     "本月底", "下周", "一季内")

# 「不做什么」的标记词。少了这一项，decision 产物就只剩"要做什么"，
# 而决策的风险恰恰在于没说清"不做什么"。
_NOT_DO_MARKS = ("不做", "不要", "不采取", "不走", "不先", "禁止",
                 "暂不", "不得", "不宜", "避免")


def _act_text(view) -> str:
    """取结论文本。View 或 dict（packed 里的 views.N）都要吃。"""
    if isinstance(view, dict):
        dp = view.get("decidable_product") or {}
        return str(dp.get("answer") or "")
    dp = getattr(view, "decidable_product", None) or {}
    return str(dp.get("answer") or "")


def _und_text(view) -> str:
    if isinstance(view, dict):
        dp = view.get("undecidable_product") or {}
        return str(dp.get("answer") or "")
    dp = getattr(view, "undecidable_product", None) or {}
    return str(dp.get("answer") or "")


def _guess_role(s: str) -> str:
    for role in _ACTION_ROLES:
        if role in s:
            return role
    return "（未指定）"


def _guess_deadline(s: str) -> str:
    for hint in _ACTION_DEADLINES:
        if hint in s:
            return hint
    return "（未指定）"


def _guess_acceptance(s: str) -> str:
    if "验收" in s:
        return s.split("验收", 1)[1][:60]
    return "（未指定）"


def _guess_fallback(s: str) -> str:
    if "回退" in s or "否则" in s:
        return s.split("否则", 1)[-1][:60]
    return "（未指定）"


def _extract_actions(view) -> list:
    """从结论文本里抽行动条目，每条补齐 6 个字段。

    入参两形态：View 对象 / packed 里的 dict。
    已抽过的（dict 里带 `_actions`）直接返回，避免落地层再抽一次抽成两份。

    ★ 负对照（写进冒烟）：空结论必须返回 **0 条** ——
      否则「有没有行动」这件事永远为真，`action_incomplete` 就永远不亮。
    """
    import re as _re
    if isinstance(view, dict) and isinstance(view.get("_actions"), list):
        return list(view["_actions"])
    text = _act_text(view)
    if not text:
        return []
    out: list = []
    # 按句号/分号切，逐句看有没有白名单里的动词。
    for m in _re.finditer(r"[。；;]([^。；;]{4,120})", "。" + text):
        s = m.group(1).strip()
        _v = next((v for v in _ACTION_VERB_WHITELIST if v in s), "")
        if not _v:
            continue
        out.append({
            "id": f"A{len(out) + 1}",
            "verb": _v,
            "object": s,
            "owner_role": _guess_role(s),
            "deadline_hint": _guess_deadline(s),
            "acceptance": _guess_acceptance(s),
            "fallback": _guess_fallback(s),
        })
        if len(out) >= 5:
            break
    return out


def _extract_not_do(view) -> list:
    """抽「不做什么」。抽不到 → 空列表 → 收尾环节标 `not_do_missing`。"""
    text = (_act_text(view) or "") + "\\n" + (_und_text(view) or "")
    if not text.strip():
        return []
    out: list = []
    for seg in text.replace("；", "。").replace(";", "。").split("。"):
        s = seg.strip()
        if len(s) < 4:
            continue
        if any(k in s for k in _NOT_DO_MARKS):
            out.append(s[:120])
        if len(out) >= 5:
            break
    return out

'''

# ------------------------------------------------------- 3.3 渲染 + 3.2 分流
RENDER = '''def _render_landing_decision(res: dict) -> str:
    """[v122 阶段3 G3.3] decision 模式的落地层：六段行动闭环。

    ★ 与 boundary 版的关系：老实现整体改名 `_render_landing_boundary`，
      一行没删。分流在 `render_landing` 里做，两个模板都能被单独调用，
      所以旧断言/旧探针只要直接点老名字就还能跑。
    """
    out = []
    views = res.get("views") or {}
    v1 = views.get("1") or {}
    dp = (v1.get("decidable_product") or {}) if isinstance(v1, dict) else {}
    out.append("## 落地层（decision 模式）\\n\\n")

    out.append("### 一、决议书\\n")
    ans = dp.get("answer") or "（未产出可执行结论）"
    out.append(f"- **主结论**：{ans}\\n")

    actions = _extract_actions(v1)

    out.append("\\n### 二、行动清单\\n")
    if not actions:
        out.append("（未抽出 action，rubric 扣分）\\n")
    for a in actions:
        out.append(f"- **{a.get('id', 'A?')}**：{a.get('verb', '')} "
                   f"{a.get('object', '')}\\n")
        out.append(f"  - 负责人：{a.get('owner_role', '（未指定）')}\\n")
        out.append(f"  - 时限：{a.get('deadline_hint', '（未指定）')}\\n")
        out.append(f"  - 验收：{a.get('acceptance', '（未指定）')}\\n")
        out.append(f"  - 回退：{a.get('fallback', '（未指定）')}\\n")

    out.append("\\n### 三、所需数据清单\\n")
    _dd = [a.get("object", "") for a in actions
           if a.get("deadline_hint") == "（未指定）"]
    if _dd:
        out.append("（以下行动缺时限，通常是因为缺一次现场量测）\\n")
        for s in _dd[:3]:
            out.append(f"- {s[:80]}\\n")

    out.append("\\n### 四、失败模式与回退\\n")
    _nf = [a for a in actions if a.get("fallback") == "（未指定）"]
    if _nf:
        out.append(f"- ⚠️ {len(_nf)} 条行动**没有回退**："
                   + "、".join(a.get("id", "?") for a in _nf) + "\\n")
    else:
        out.append("- 所有行动都带回退路径。\\n")

    out.append("\\n### 五、不做什么\\n")
    not_do = _extract_not_do(v1)
    if not_do:
        for s in not_do:
            out.append(f"- {s}\\n")
    else:
        out.append("（未指定「不做什么」—— 这是 decision 产物的缺口）\\n")

    out.append("\\n### 六、如果只能做一件事\\n")
    if actions:
        a1 = actions[0]
        out.append(f"- {a1.get('verb', '')} {a1.get('object', '')}\\n")
    return "".join(out)


def render_landing(res: dict) -> str:
    """[v122 阶段3 G3.2] 落地层分流壳：boundary / 关掉开关 → 老五块模板；
    decision → 行动闭环模板。壳里不写任何渲染逻辑。"""
    cfg = res.get("_config") or {}
    orientation = str(res.get("orientation") or "auto").strip().lower()
    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):
        return _render_landing_boundary(res)
    return _render_landing_decision(res)


def _render_landing_boundary(res: dict) -> str:
'''

# ------------------------------------------------------- 3.5 硬约束
A_CONSTRAINT = "        # ---- 1. 把跨圈累积回填到 view ----\n"
B_CONSTRAINT = '''        # [v122 阶段3 G3.5] decision 模式的硬约束：结论必须能落成行动。
        #   两条判据分别对应两种失败：
        #     · action_incomplete —— 抽出的行动不足 3 条（清单撑不起执行）；
        #     · not_do_missing    —— 没交代「不做什么」（决策只说了做什么，
        #                            等于没划边界）。
        #   ★ 只在 decision 取向、且是研究层时判；boundary 取向不受影响。
        if entry == "1" and str(getattr(self, "_orientation", "auto")) \\
                .strip().lower() == "decision":
            _acts_d = _extract_actions(view)
            if len(_acts_d) < 3:
                view.errors.append(
                    f"decision 模式行动清单不足（{len(_acts_d)} < 3），"
                    f"需补 A1~A3")
                view.quality_flags.append("action_incomplete")
            _nd_d = _extract_not_do(view)
            if not _nd_d:
                view.errors.append(
                    "decision 模式未交代「不做什么」，需补该清单")
                view.quality_flags.append("not_do_missing")

''' + A_CONSTRAINT

# ------------------------------------------------------- 3.6 落 packed
A_PACK = ('            "layer_contribution": self._layer_contribution(results),\n'
          '        }\n')
B_PACK = ('            "layer_contribution": self._layer_contribution(results),\n'
          '            # [v122 P3 G3.2/G3.6] 分流要读的两样：取向 + 开关快照。\n'
          '            "orientation": str(getattr(self, "_orientation", "auto")),\n'
          '            "_config": {"actions": dict(self.config.get("actions")'
          ' or {})},\n'
          '        }\n'
          '        # [v122 P3 G3.6] 行动清单 / 不做什么 落进 packed：\n'
          '        #   落地层是纯函数，只读 packed；抽一次挂上去，别在渲染里\n'
          '        #   再抽一次（两份抽样会不一致）。\n'
          '        try:\n'
          '            _v1p = results.get("1")\n'
          '            if _v1p is not None:\n'
          '                _pack["views"].setdefault("1", {})["_actions"] = \\\n'
          '                    _extract_actions(_v1p)\n'
          '                _pack["views"]["1"]["_not_do"] = _extract_not_do(_v1p)\n'
          '        except Exception as _e3:\n'
          '            logger.warning("行动清单落 packed 失败: %s", _e3)\n')

REPS = [
    ("switch", A_SWITCH, B_SWITCH, 1),
    ("orientation", A_ORI, B_ORI, 1),
    ("render_landing", "def render_landing(res: dict) -> str:\n",
     RENDER, 1),
    ("pack_meta", A_PACK, B_PACK, 1),
    ("constraints", A_CONSTRAINT, B_CONSTRAINT, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")

    # 3.4 抽取器插到 _classify_unsaid 之前（同位：都是「收尾前的小工具」）
    anchor = "def _classify_unsaid(block) -> str:\n"
    assert s.count(anchor) == 1, "classify 锚点不唯一"
    s = s.replace(anchor, EXTRACT.lstrip("\n") + "\n" + anchor, 1)
    print("  ✓ extractors")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段3 补丁完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
