#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P1] 研究层直接产出结构化 actions 段。

四件事（加性，不删旧行）：
1. `_he` 的 is_research system：decidable_product 骨架加 `actions[]` +
   加【★ actions 段 · decision 取向必须产出】约束段；
2. `_he` 的 dec_norm 白名单加 `actions` —— ★ 不加就是**静默吞字段**；
3. `_extract_actions` 改名 `_extract_actions_lexical`（正文一字不动），
   新增 schema 优先的 `_extract_actions`（兜底仍走词法，补 `_source` 标签）；
4. `_finalize_layer_common` 的 action_incomplete 改成「按 schema 条数判」，
   新增 `action_fields_missing`；并把新 flag 加进 `_V122_HARD_FLAGS`
   （否则会被 quality_flags 重算冲掉 —— v1.22 踩过同一个坑）。

★ 反斜杠一律用占位符拼，绝不在命令/脚本里直接敲：
    @B@ → 单个反斜杠（行尾续行符）  @Q@ → 反斜杠+双引号  @N@ → 反斜杠+n
  `@N@` **只用于提示词字符串块**（那里源码里要的就是字面的 \n 两个字符）；
  普通代码行不能带 `@N@` —— 第一版把两者混用，锚点全部 0 命中。
★ 锚点一律整行/整块相等，不用子串。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.1-rc1.py"

BS = chr(92)


def L(s: str) -> str:
    return (s.replace("@N@", BS + "n")
             .replace("@Q@", BS + '"')
             .replace("@B@", BS))


# ------------------------------------------------------------------
# 1. decidable_product 骨架（提示词字符串块 → 用 @N@）
# ------------------------------------------------------------------
OLD_SKELETON = L(
    "                '  \"decidable_product\": {@N@'\n"
    "                '    \"answer\": \"...\",@N@'\n"
    "                '    \"answered_sub_ids\": [1],@N@'\n"
    "                '    \"evidence\": [\"...\"],@N@'\n"
    "                '    \"distance\": 0.0-1.0@N@'\n"
    "                \"  },@N@\"\n")

NEW_SKELETON = L(
    "                '  \"decidable_product\": {@N@'\n"
    "                '    \"answer\": \"...\",@N@'\n"
    "                '    \"answered_sub_ids\": [1],@N@'\n"
    "                '    \"evidence\": [\"...\"],@N@'\n"
    "                '    \"distance\": 0.0-1.0,@N@'\n"
    "                '    \"actions\": [@N@'\n"
    "                '      {\"id\": \"A1\",@N@'\n"
    "                '       \"verb\": \"指派|核查|测量|提交|申请|封堵|清淤|试点|备案|\"@N@'\n"
    "                '               \"签发|复核|排查|改造|扩容|委托|报审|谈判|调取\",@N@'\n"
    "                '       \"object\": \"≤40字，动作对象\",@N@'\n"
    "                '       \"owner_role\": \"≤20字，具名角色或部门\",@N@'\n"
    "                '       \"deadline_hint\": \"≤20字，具体时限或触发条件\",@N@'\n"
    "                '       \"acceptance\": \"≤40字，怎么算完成\",@N@'\n"
    "                '       \"fallback\": \"≤40字，失败时的退路\"}@N@'\n"
    "                '    ]@N@'\n"
    "                \"  },@N@\"\n")

# ------------------------------------------------------------------
# 2. 【A】要求段补 actions 行 + 约束段（提示词字符串块 → 用 @N@）
# ------------------------------------------------------------------
OLD_REQTAIL = L(
    "                \"  - distance：距离完整回答全部可判定子问题还有多远（0-1）@N@\"\n"
    "                \"@N@\"\n"
    "                \"【B. undecidable_product 要求】@N@\"\n")

NEW_REQTAIL = L(
    "                \"  - distance：距离完整回答全部可判定子问题还有多远（0-1）@N@\"\n"
    "                \"  - actions：回答若落在「该做什么」（decision 取向），@N@\"\n"
    "                \"    **必须**同时给 @Q@actions@Q@ 段，而不是只给结论段落。@N@\"\n"
    "                \"@N@\"\n"
    "                \"【★ actions 段 · decision 取向必须产出】@N@\"\n"
    "                \"  - 研究层的回答若落在@Q@该做什么@Q@，必须同时给 actions 段。@N@\"\n"
    "                \"  - 每条 action 六字段**全部必填**，缺一格视为无效条目。@N@\"\n"
    "                \"  - owner_role 必须是一个**具体的角色 / 部门 / 岗位**，@N@\"\n"
    "                \"    不许写@Q@相关部门@Q@@Q@有关方面@Q@。@N@\"\n"
    "                \"  - deadline_hint 必须是**可指认的时限或触发条件**@N@\"\n"
    "                \"    （如@Q@汛期前 30 天@Q@@Q@下一次暴雨后 24h@Q@），@N@\"\n"
    "                \"    不许写@Q@尽早@Q@@Q@适时@Q@。@N@\"\n"
    "                \"  - acceptance 必须能**被第三方核对**@N@\"\n"
    "                \"    （如@Q@出具签字人清单@Q@@Q@泵站流量记录入档@Q@）。@N@\"\n"
    "                \"  - fallback 必须写**失败时的退路**，@N@\"\n"
    "                \"    不许写@Q@重新评估@Q@这类空动作。@N@\"\n"
    "                \"  - 若确实给不出 actions（纯事实题 / 边界题），@N@\"\n"
    "                \"    给空数组并在 answer 里说明，不要硬凑。@N@\"\n"
    "                \"@N@\"\n"
    "                \"【B. undecidable_product 要求】@N@\"\n")

# ------------------------------------------------------------------
# 3. dec_norm 白名单加 actions（普通代码 → 不带 @N@）
# ------------------------------------------------------------------
OLD_DECNORM = (
    "            dec_norm = {\n"
    "                \"answer\": str(dec.get(\"answer\", \"\"))[:800],\n"
    "                \"answered_sub_ids\": list(dec.get(\"answered_sub_ids\") or [])[:20],\n"
    "                \"evidence\": [str(e)[:200]\n"
    "                             for e in (dec.get(\"evidence\") or [])][:5],\n"
    "                \"distance\": 0.0,\n"
    "            }\n")

NEW_DECNORM = (
    "            dec_norm = {\n"
    "                \"answer\": str(dec.get(\"answer\", \"\"))[:800],\n"
    "                \"answered_sub_ids\": list(dec.get(\"answered_sub_ids\") or [])[:20],\n"
    "                \"evidence\": [str(e)[:200]\n"
    "                             for e in (dec.get(\"evidence\") or [])][:5],\n"
    "                # [v1.22.1 P1] ★ 这是**显式白名单**：不列 actions 就等于把\n"
    "                #   模型产的整段静默吞掉（本项目踩过「dict 白名单无声吞新字段」）。\n"
    "                \"actions\": _norm_schema_actions(dec.get(\"actions\")),\n"
    "                \"distance\": 0.0,\n"
    "            }\n")

# ------------------------------------------------------------------
# 4. 新函数（普通代码 → 不带 @N@）
# ------------------------------------------------------------------
NEW_FUNCS = '''def _norm_schema_actions(raw) -> list:
    """[v1.22.1 P1] 把模型给的 `decidable_product.actions` 归一成六字段 dict。

    放在这里（而不是内联在 `_he` 里）是为了让 `_he` 的 dec_norm 只写一行。
    归一策略：非 list → 空；非 dict 条目丢弃；每条按字段截断；最多 6 条。
    """
    out: list = []
    if not isinstance(raw, list):
        return out
    for i, a in enumerate(raw[:6], 1):
        if not isinstance(a, dict):
            continue
        out.append({
            "id": str(a.get("id") or f"A{i}")[:12],
            "verb": str(a.get("verb", ""))[:20],
            "object": str(a.get("object", ""))[:80],
            "owner_role": str(a.get("owner_role", ""))[:40],
            "deadline_hint": str(a.get("deadline_hint", ""))[:40],
            "acceptance": str(a.get("acceptance", ""))[:80],
            "fallback": str(a.get("fallback", ""))[:80],
        })
    return out


def _extract_actions(view) -> list:
    """优先读 schema 产出的 actions；schema 缺失时才回退词法抽取。

    [v1.22.1 P1] 语义变更：从「从结论段落里猜动作」变成「读研究层已产出的
    结构化 actions」。词法路径保留（`_extract_actions_lexical`），仅作兜底
    （老产物 / 未升级 schema 的跑批）。

    入参两形态：View 对象 / packed 里的 dict。
    已抽过的（dict 里带 `_actions`）直接返回，避免落地层再抽一次抽成两份。

    ★ 负对照（写进冒烟）：空结论必须返回 **0 条** ——
      否则「有没有行动」这件事永远为真，`action_incomplete` 就永远不亮。
    """
    if isinstance(view, dict) and isinstance(view.get("_actions"), list):
        return list(view["_actions"])
    if isinstance(view, dict):
        dp = view.get("decidable_product") or {}
    else:
        dp = getattr(view, "decidable_product", None) or {}
    dp = dp if isinstance(dp, dict) else {}
    _schema_actions = dp.get("actions")
    if isinstance(_schema_actions, list) and _schema_actions:
        out: list = []
        for a in _schema_actions:
            if not isinstance(a, dict):
                continue
            _act = {
                "id": str(a.get("id") or f"A{len(out) + 1}"),
                "verb": str(a.get("verb", "")).strip(),
                "object": str(a.get("object", "")).strip(),
                "owner_role": str(a.get("owner_role", "")).strip(),
                "deadline_hint": str(a.get("deadline_hint", "")).strip(),
                "acceptance": str(a.get("acceptance", "")).strip(),
                "fallback": str(a.get("fallback", "")).strip(),
            }
            # 六字段全空视为无效；留一条空字段也收，但标 incomplete
            if not any(_act[k] for k in ("verb", "object")):
                continue
            _act["_source"] = "schema"
            _act["_missing"] = [k for k in
                                ("verb", "object", "owner_role",
                                 "deadline_hint", "acceptance", "fallback")
                                if not _act[k]]
            out.append(_act)
        if out:
            return out
    # 兜底：词法（老路径一字不动，只补 `_source` 标签）
    out2: list = []
    for _a in _extract_actions_lexical(view):
        if isinstance(_a, dict):
            _a = dict(_a)
            _a["_source"] = "lexical"
        out2.append(_a)
    return out2


'''

# ------------------------------------------------------------------
# 5. _finalize_layer_common 硬约束段（普通代码 → 不带 @N@；续行符用 @B@）
# ------------------------------------------------------------------
OLD_FIN = L(
    "        # [v122 阶段3 G3.5] decision 模式的硬约束：结论必须能落成行动。\n"
    "        #   两条判据分别对应两种失败：\n"
    "        #     · action_incomplete —— 抽出的行动不足 3 条（清单撑不起执行）；\n"
    "        #     · not_do_missing    —— 没交代「不做什么」（决策只说了做什么，\n"
    "        #                            等于没划边界）。\n"
    "        #   ★ 只在 decision 取向、且是研究层时判；boundary 取向不受影响。\n"
    "        if entry == \"1\" and str(getattr(self, \"_orientation\", \"auto\")) @B@\n"
    "                .strip().lower() == \"decision\":\n"
    "            _acts_d = _extract_actions(view)\n"
    "            if len(_acts_d) < 3:\n"
    "                view.errors.append(\n"
    "                    f\"decision 模式行动清单不足（{len(_acts_d)} < 3），\"\n"
    "                    f\"需补 A1~A3\")\n"
    "                view.quality_flags.append(\"action_incomplete\")\n")

NEW_FIN = L(
    "        # [v122 阶段3 G3.5 / v1.22.1 P1.3] decision 模式的硬约束：结论要能落成行动。\n"
    "        #   两条判据分别对应两种失败：\n"
    "        #     · action_incomplete —— **模型没按 schema 产出 actions**\n"
    "        #       （v1.22.1 起语义变更：不再是「词法没抽到」，而是 schema 空/不足）；\n"
    "        #     · not_do_missing    —— 没交代「不做什么」（决策只说了做什么，\n"
    "        #                            等于没划边界）。\n"
    "        #   ★ 只在 decision 取向、且是研究层时判；boundary 取向不受影响。\n"
    "        if entry == \"1\" and str(getattr(self, \"_orientation\", \"auto\")) @B@\n"
    "                .strip().lower() == \"decision\":\n"
    "            _acts_d = _extract_actions(view)\n"
    "            _schema_acts_d = [a for a in _acts_d\n"
    "                              if a.get(\"_source\") == \"schema\"]\n"
    "            if len(_schema_acts_d) < 3:\n"
    "                view.errors.append(\n"
    "                    f\"decision 取向 actions 段不足：schema 产出 \"\n"
    "                    f\"{len(_schema_acts_d)} 条（< 3）。请在 _he 的 \"\n"
    "                    f\"decidable_product 里补 schema actions。\")\n"
    "                view.quality_flags.append(\"action_incomplete\")\n"
    "            for _a_d in _schema_acts_d:\n"
    "                if _a_d.get(\"_missing\"):\n"
    "                    view.errors.append(\n"
    "                        f\"action {_a_d.get('id')} 缺字段：{_a_d['_missing']}\")\n"
    "                    view.quality_flags.append(\"action_fields_missing\")\n"
    "                    break\n"
    "            _dp_d = getattr(view, \"decidable_product\", None) or {}\n"
    "            _ans_d = str(_dp_d.get(\"answer\") or \"\")\n"
    "            if any(k in _ans_d for k in (\"缺主体\", \"无主体\", \"无承接者\",\n"
    "                                        \"缺承接者\")) and not _schema_acts_d:\n"
    "                view.errors.append(\n"
    "                    \"结论落在'缺 X'但 schema 未给 actions，需补 A1~A3\")\n")

REPS = [
    ("骨架加 actions[]", OLD_SKELETON, NEW_SKELETON),
    ("约束段", OLD_REQTAIL, NEW_REQTAIL),
    ("dec_norm 加 actions", OLD_DECNORM, NEW_DECNORM),
    ("硬约束段改 schema 判", OLD_FIN, NEW_FIN),
    ("_extract_actions 改名",
     "def _extract_actions(view) -> list:\n",
     "def _extract_actions_lexical(view) -> list:\n"),
    ("词法函数 docstring 标注",
     '    """从结论文本里抽行动条目，每条补齐 6 个字段。\n',
     '    """[v1.22.1 P1] 词法兜底：从结论文本里抽行动条目，每条补齐 6 个字段。\n'),
    ("新函数插入",
     "def _extract_not_do(view) -> list:\n",
     NEW_FUNCS + "def _extract_not_do(view) -> list:\n"),
    ("_V122_HARD_FLAGS 加新 flag",
     '_V122_HARD_FLAGS = ("action_incomplete", "not_do_missing")\n',
     '_V122_HARD_FLAGS = ("action_incomplete", "not_do_missing",\n'
     '                    "action_fields_missing")\n'),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "TARGET 不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "TARGET 有 \\r\\r\\n"
    s = s.replace("\r\n", "\n")

    for name, old, new in REPS:
        got = s.count(old)
        assert got == 1, f"[{name}] 锚点 {got} 次，期望 1"
        s = s.replace(old, new, 1)
        print(f"  ✓ {name}")

    ast.parse(s)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))

    chk = TARGET.read_bytes().decode("utf-8")
    for must in ('"actions": [', "decision 取向必须产出", "_norm_schema_actions",
                 "def _extract_actions_lexical", "模型没按 schema 产出 actions",
                 "action_fields_missing", "actions 段不足"):
        assert must in chk, f"自检缺：{must}"
    print("✓ P1 补丁完成；ast OK；纯 CRLF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
