#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P1] 探针：研究层结构化 actions 段的 before / after。

用法：python _probe_v1221_p1.py <src.py> > _probe_v1221_p1_before.txt

判据全部是「能自答的事实」：
- 不依赖 LLM：schema 键在不在、prompt 里六字段在不在、约束段在不在、
  `_extract_actions` 对三种输入的返回形态、白名单有没有被扩、
  归一化白名单里有没有 `actions`（漏了就是**静默吞字段**）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.1-rc1.py")
if not SRC.is_absolute():
    SRC = HERE / SRC

FIELDS = ("verb", "object", "owner_role", "deadline_hint",
          "acceptance", "fallback")


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:110]}"


def main() -> int:
    txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("dgtf_p1_probe", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p1_probe"] = m
    spec.loader.exec_module(m)

    out = {}

    # ---------- 源码侧 ----------
    _sk = _skeleton(txt)          # decidable_product 的 JSON 骨架段
    _req = _req_block(txt)        # 【A. decidable_product 要求】..【B. 】
    out["A0_取样区域长度"] = {"skeleton": len(_sk), "req_block": len(_req)}
    out["A1_src_骨架里有_actions 键"] = '"actions"' in _sk
    out["A2_src_骨架里六字段"] = {f: (f'"{f}"' in _sk) for f in FIELDS}
    out["A3_src_约束段"] = "decision 取向必须产出" in _req
    out["A4_src_约束段六条要点"] = {
        k: (k in _req) for k in
        ("全部必填", "相关部门", "尽早", "第三方核对",
         "失败时的退路", "不要硬凑")}
    out["A4b_src_要求段里提 actions"] = "actions" in _req
    out["A5_src_flag 语义注释"] = "模型没按 schema 产出 actions" in txt
    out["A6_src_action_fields_missing"] = "action_fields_missing" in txt
    out["A7_src_lexical 函数"] = "def _extract_actions_lexical" in txt
    out["A8_src_归一化白名单含 actions"] = _norm_keeps_actions(txt)
    out["A9_V122_HARD_FLAGS"] = list(
        getattr(m, "_V122_HARD_FLAGS", ()) or ())
    out["A10_动词白名单"] = list(getattr(m, "_ACTION_VERB_WHITELIST", ()) or ())
    out["A11_动词白名单条数"] = len(getattr(m, "_ACTION_VERB_WHITELIST", ()) or ())
    out["A12_min_actions 常量"] = _find_const(txt, "min_actions")

    # ---------- 功能侧：三种输入 ----------
    def _view(dp):
        v = m.View(entry="1")
        v.decidable_product = dp
        return v

    def _schema_probe():
        v = _view({"answer": "x", "actions": [
            {"id": "A1", "verb": "指派", "object": "核查",
             "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
             "acceptance": "出具签字人清单", "fallback": "向上级申请"},
            {"id": "A2", "verb": "提交", "object": "排水图",
             "owner_role": "排水公司", "deadline_hint": "本月内",
             "acceptance": "管网档案归档", "fallback": "委托第三方"},
            {"id": "A3", "verb": "试点", "object": "透水铺装",
             "owner_role": "项目组", "deadline_hint": "本季度",
             "acceptance": "验收报告出具", "fallback": "缩减试点范围"},
        ]})
        acts = m._extract_actions(v)
        return {"n": len(acts),
                "sources": sorted({a.get("_source", "<无>") for a in acts}),
                "missing": [a.get("_missing") for a in acts]}

    def _lexical_probe():
        v = _view({"answer": "先指派区防汛办核查。否则回退上级。"})
        acts = m._extract_actions(v)
        return {"n": len(acts),
                "sources": sorted({a.get("_source", "<无>") for a in acts})}

    def _empty_probe():
        v = _view({"answer": ""})
        return len(m._extract_actions(v))

    def _missing_probe():
        v = _view({"answer": "x",
                   "actions": [{"id": "A1", "verb": "指派", "object": "核查"}]})
        acts = m._extract_actions(v)
        return {"n": len(acts), "missing": acts[0].get("_missing") if acts else None}

    out["B1_schema 三字段全给"] = _try(_schema_probe)
    out["B2_仅 answer 走词法"] = _try(_lexical_probe)
    out["B3_空 answer（负对照）"] = _try(_empty_probe)
    out["B4_schema 缺字段（负对照）"] = _try(_missing_probe)

    # ---------- 硬约束语义（源码侧） ----------
    out["C1_源码_缺 X 未给 actions 提示"] = "需补 A1~A3" in txt
    out["C2_源码_actions 段不足措辞"] = "actions 段不足" in txt

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _skeleton(txt: str) -> str:
    """抠 `_he` 里 decidable_product 的 JSON 骨架段（按源码字面串取样）。

    ★ 为什么不整文件 grep：`"actions"` / 六字段名在别处也有
      （配置键、_extract_actions 的词法实现）—— 整文件判定在 before
      就会是 True，探针失去判别力。实测第一版就是这么误报的。
    """
    a = txt.find('  "decidable_product": {')
    b = txt.find('  "undecidable_product": {')
    return txt[a:b] if a >= 0 and b > a else ""


def _req_block(txt: str) -> str:
    """抠【A. decidable_product 要求】到【B. undecidable_product 要求】之间。"""
    a = txt.find("【A. decidable_product 要求】")
    b = txt.find("【B. undecidable_product 要求】")
    return txt[a:b] if a >= 0 and b > a else ""


def _norm_keeps_actions(txt: str) -> bool:
    """`_he` 里 dec_norm 是显式白名单 dict —— 不把 actions 列进去就是静默吞字段。"""
    i = txt.find("dec_norm = {")
    if i < 0:
        return False
    seg = txt[i:i + 900]
    return '"actions"' in seg


def _find_const(txt: str, name: str):
    return [ln.strip() for ln in txt.split("\n") if name in ln and "=" in ln][:4]


if __name__ == "__main__":
    sys.exit(main())
