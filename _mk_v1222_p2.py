# -*- coding: utf-8 -*-
"""[v1.22.2 P2] schema 加 not_do —— 打补丁脚本（唯一事实源）。

据 _taskbook_audit_v1222.md 的 #6/#7 改过：
  · rubric 第三项**不用改**（score_actions 早已 `if nd: s += 1`）；
    真正要做的是让 `_not_do` 非空。
  · `dec_norm` 是**显式白名单 dict** —— 不列 not_do，模型产了也会被静默
    吞掉，现象与「模型不产」一模一样。必须同步加白名单。
四处（prompt schema → 归一化白名单 → 抽取函数 → 渲染）缺一即静默失败。
幂等：哨兵串。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.2.py"
SENTINEL = "[v1.22.2 P2]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 v1.22.2 P2 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# ---------------------------------------------------------- 1. prompt 约束段
NOTDO_BLOCK = r'''                "\n"
                "【★ not_do 段 · decision 取向必须产出】\n"
                "  - 至少 1 条，最多 3 条。\n"
                "  - what 必须是一件**明确不做的事**（不是\"暂缓\"、不是\"待定\"）。\n"
                "    例：\"不在成因判定缺席时启动物探\"\"不优先改造非瓶颈段\"。\n"
                "  - why 必须能指向一个**可核对的事实**或一条**可指认的判据**\n"
                "    （不是\"资源有限\"这种套话）。\n"
                "  - 若本次确实没有明确不做的事，写空数组并在 answer 里说明；\n"
                "    不要硬凑。\n"
'''
P1_OLD = (
    '                "    给空数组并在 answer 里说明，不要硬凑。\\n"\n'
    '                "\\n"\n'
    '                "【B. undecidable_product 要求】\\n"\n'
)
P1_NEW = (
    '                "    给空数组并在 answer 里说明，不要硬凑。\\n"\n'
    + NOTDO_BLOCK
    + '                "\\n"\n'
    '                "【B. undecidable_product 要求】\\n"\n'
)
src = sub_once(src, P1_OLD, P1_NEW, "prompt-约束段")

# ---------------------------------------------------------- 2. prompt schema
P2_OLD = (
    '                \'       "fallback": "≤40字，失败时的退路"}\\n\'\n'
    '                \'    ]\\n\'\n'
    '                "  },\\n"\n'
)
P2_NEW = (
    '                \'       "fallback": "≤40字，失败时的退路"}\\n\'\n'
    '                \'    ],\\n\'\n'
    '                \'    "not_do": [\\n\'\n'
    '                \'      {"what": "≤40字，明确不做的事",\\n\'\n'
    '                \'       "why": "≤40字，理由"}\\n\'\n'
    '                \'    ]\\n\'\n'
    '                "  },\\n"\n'
)
src = sub_once(src, P2_OLD, P2_NEW, "prompt-schema")

# ---------------------------------------------------------- 3. dec_norm 白名单
P3_OLD = (
    '                "actions": _norm_schema_actions(dec.get("actions")),\n'
    '                "distance": 0.0,\n'
)
P3_NEW = (
    '                "actions": _norm_schema_actions(dec.get("actions")),\n'
    '                # [v1.22.2 P2] ★ 必须同步加白名单：dec_norm 是**显式** dict，\n'
    '                #   不列 not_do 就等于把模型产的整段静默吞掉（本项目踩过\n'
    '                #   「dict 白名单无声吞新字段」）。缺这一行时现象与「模型\n'
    '                #   不产」一模一样，永远查不出来。\n'
    '                "not_do": _norm_schema_not_do(dec.get("not_do")),\n'
    '                "distance": 0.0,\n'
)
src = sub_once(src, P3_OLD, P3_NEW, "dec_norm-白名单")

# ---------------------------------------------------------- 4. 归一化函数
P4_OLD = (
    'def _norm_schema_actions(raw) -> list:\n'
)
P4_NEW = (
    'def _norm_schema_not_do(raw) -> list:\n'
    '    """[v1.22.2 P2] 把模型给的 `decidable_product.not_do` 归一成 what/why。\n'
    '\n'
    '    与 `_norm_schema_actions` 同款：非 list → 空；非 dict 条目丢弃；\n'
    '    **`what` 为空 → 丢弃**（空 what 不算一条，否则 rubric 第三项会假通过）。\n'
    '    """\n'
    '    out: list = []\n'
    '    if not isinstance(raw, list):\n'
    '        return out\n'
    '    for i, a in enumerate(raw[:6], 1):\n'
    '        if not isinstance(a, dict):\n'
    '            continue\n'
    '        w = str(a.get("what", "") or "").strip()\n'
    '        if not w:\n'
    '            continue\n'
    '        out.append({\n'
    '            "id": str(a.get("id") or f"N{i}")[:12],\n'
    '            "what": w[:80],\n'
    '            "why": str(a.get("why", "") or "").strip()[:80],\n'
    '        })\n'
    '    return out\n'
    '\n'
    '\n'
    'def _norm_schema_actions(raw) -> list:\n'
)
src = sub_once(src, P4_OLD, P4_NEW, "归一化函数")

# ---------------------------------------------------------- 5. 抽取函数
P5_OLD = (
    'def _extract_not_do(view) -> list:\n'
    '    """抽「不做什么」。抽不到 → 空列表 → 收尾环节标 `not_do_missing`。"""\n'
)
P5_NEW = (
    'def _extract_not_do(view) -> list:\n'
    '    """[v1.22.2 P2] 优先读 schema 产出的 not_do；缺失时才回退词法抽取。\n'
    '\n'
    '    入参两形态：View 对象 / packed 里的 dict。已抽过的（dict 里带\n'
    '    `_not_do`）直接返回，避免落地层再抽一次抽成两份。\n'
    '    · schema 结果带 `_source="schema"`（每条 {what, why}）；\n'
    '    · 词法兜底带 `_source="lexical"`（老产物 / 未升级 schema 的跑批）。\n'
    '\n'
    '    ★ 负对照（写进冒烟）：空 view 必须返回 **0 条** ——\n'
    '      否则「有没有不做的事」永远为真，`not_do_missing` 就永远不亮。\n'
    '    """\n'
    '    if isinstance(view, dict) and isinstance(view.get("_not_do"), list):\n'
    '        return list(view["_not_do"])\n'
    '    if isinstance(view, dict):\n'
    '        dp = view.get("decidable_product") or {}\n'
    '    else:\n'
    '        dp = getattr(view, "decidable_product", None) or {}\n'
    '    dp = dp if isinstance(dp, dict) else {}\n'
    '    _schema = dp.get("not_do")\n'
    '    if isinstance(_schema, list) and _schema:\n'
    '        out: list = []\n'
    '        for a in _schema:\n'
    '            if not isinstance(a, dict):\n'
    '                continue\n'
    '            _w = str(a.get("what", "") or "").strip()\n'
    '            if not _w:\n'
    '                continue\n'
    '            out.append({"what": _w[:80],\n'
    '                        "why": str(a.get("why", "") or "").strip()[:80],\n'
    '                        "_source": "schema"})\n'
    '        if out:\n'
    '            return out\n'
    '    # 兜底：词法（老路径语义不变，只改成 dict + `_source` 标签）\n'
    '    return [{"what": str(_s)[:120], "why": "", "_source": "lexical"}\n'
    '            for _s in _extract_not_do_lexical(view)]\n'
    '\n'
    '\n'
    'def _extract_not_do_lexical(view) -> list:\n'
    '    """[v1.22.2 P2] 原 `_extract_not_do` 的词法版（正文一字未动）。\n'
    '\n'
    '    只在 schema 路径抽不到时兜底 —— 老产物 / 未升级 schema 的跑批。\n'
    '    """\n'
)
src = sub_once(src, P5_OLD, P5_NEW, "抽取函数")

# ---------------------------------------------------------- 6. not_do_missing 语义
P6_OLD = (
    '            _nd_d = _extract_not_do(view)\n'
    '            if not _nd_d:\n'
    '                view.errors.append(\n'
    '                    "decision 模式未交代「不做什么」，需补该清单")\n'
    '                view.quality_flags.append("not_do_missing")\n'
)
P6_NEW = (
    '            # [v1.22.2 P2] 本 flag 语义 = **模型没按 schema 产出 not_do**，\n'
    '            #   不是「词法没抽到」。只认 `_source == "schema"`。\n'
    '            _nd_d = _extract_not_do(view)\n'
    '            _nd_schema = [x for x in _nd_d\n'
    '                          if isinstance(x, dict)\n'
    '                          and x.get("_source") == "schema"]\n'
    '            if not _nd_schema:\n'
    '                view.errors.append(\n'
    '                    "decision 取向 not_do 段缺失：schema 未产出。"\n'
    '                    "请在 _he 的 decidable_product 里补 not_do[]。")\n'
    '                view.quality_flags.append("not_do_missing")\n'
)
src = sub_once(src, P6_OLD, P6_NEW, "not_do_missing 语义")

# ---------------------------------------------------------- 7. 渲染兼容 dict
P7_OLD = (
    '    not_do = _extract_not_do(v1)\n'
    '    if not_do:\n'
    '        for s in not_do:\n'
    '            out.append(f"- {s}\\n")\n'
)
P7_NEW = (
    '    not_do = _extract_not_do(v1)\n'
    '    if not_do:\n'
    '        for s in not_do:\n'
    '            # [v1.22.2 P2] not_do 现在是 {what, why, _source} 或裸串\n'
    '            #   （老产物 / 词法兜底仍是串）—— 两形态都要渲染。\n'
    '            if isinstance(s, dict):\n'
    '                _w = str(s.get("what", "") or "")\n'
    '                _y = str(s.get("why", "") or "")\n'
    '                out.append(f"- {_w}"\n'
    '                           + (f"（{_y}）" if _y else "") + "\\n")\n'
    '            else:\n'
    '                out.append(f"- {s}\\n")\n'
)
src = sub_once(src, P7_OLD, P7_NEW, "渲染兼容")

# ---------------------------------------------------------- 写回
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.22.2 P2 补丁已写入")
print("  prompt schema 加 not_do[] / 约束段 / dec_norm 白名单 / "
      "_norm_schema_not_do / _extract_not_do 双路径 / not_do_missing 语义 / 渲染兼容")
