# -*- coding: utf-8 -*-
"""题型判定回归：解释型「为什么」不得被当成事实短题。

背景（2026-10-24 真跑实测）：问「为什么城市热岛效应在夜间比白天更明显？」被
`_auto_features` 判成 fact+short ⇒ 事实预检 + 收紧圈数 + 事实卡未 answered ⇒
四层过程已达标仍 answer_ready=False / answer_quality=needs_evidence。

本判据锁：why 题 fact=False、why=True、决策回执类型=reasoning；并留事实题 /
决策题 / 空题 / 普通边界题的负对照。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.4.py"


def _load():
    spec = importlib.util.spec_from_file_location("metadgtf_qtype", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_qtype"] = mod
    spec.loader.exec_module(mod)
    return mod


ENG = _load()
P = []
F = []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if info and not ok else ""))


def main():
    why_q = "为什么城市热岛效应在夜间比白天更明显？"
    feat = ENG._auto_features(why_q)
    ck("why 题标记 why=True", feat.get("why") is True, feat)
    ck("why 题不再算 fact 短题", feat.get("fact") is False, feat)
    ck("why 题决策回执=reasoning",
       ENG.question_type_from_features(feat) == "reasoning", feat)
    ck("why 题不进 short-fact 分支",
       not (feat.get("fact") and feat.get("short")), feat)

    fq = "Python 中 len 函数的作用是什么？"
    ff = ENG._auto_features(fq)
    ck("事实短题仍判 fact",
       ff.get("fact") is True and ENG.question_type_from_features(ff) == "fact",
       ff)

    fq = "AI Agent 会先取代哪类工作？"
    ff = ENG._auto_features(fq)
    ck("forecast 题标记 forecast=True", ff.get("forecast") is True, ff)
    ck("forecast 题不算 fact 短题", ff.get("fact") is False, ff)
    ck("forecast 题决策回执=reasoning",
       ENG.question_type_from_features(ff) == "reasoning", ff)

    iq = "首例确凿的黑洞重复潮汐瓦解恒星事件说明了什么？"
    iff = ENG._auto_features(iq)
    ck("interpret 题标记 interpret=True", iff.get("interpret") is True, iff)
    ck("interpret 题不算 fact 短题", iff.get("fact") is False, iff)
    ck("interpret 题决策回执=reasoning",
       ENG.question_type_from_features(iff) == "reasoning", iff)

    eq = "扩内需与新质生产力会改变哪些行业？"
    ef = ENG._auto_features(eq)
    ck("经济预测题标记 forecast=True", ef.get("forecast") is True, ef)
    ck("经济预测题不算 fact 短题", ef.get("fact") is False, ef)
    ck("经济预测题决策回执=reasoning",
       ENG.question_type_from_features(ef) == "reasoning", ef)

    fq2 = "智能体终端会怎样改变工作？"
    ff2 = ENG._auto_features(fq2)
    ck("未来题标记 forecast=True", ff2.get("forecast") is True, ff2)
    ck("未来题不算 fact 短题", ff2.get("fact") is False, ff2)
    ck("未来题决策回执=reasoning",
       ENG.question_type_from_features(ff2) == "reasoning", ff2)

    dq = "如何在社区推广垃圾分类才能长期见效？"
    df = ENG._auto_features(dq)
    ck("决策题判 decision", ENG.question_type_from_features(df) == "decision", df)

    ck("空题判 boundary（兼容旧口径：short=False ⇒ 不进 fact）",
       ENG.question_type_from_features(ENG._auto_features("")) == "boundary")

    ck("_is_why_question 正例", ENG._is_why_question("为什么会发生热岛效应"))
    ck("_is_why_question 负例",
       not ENG._is_why_question("Python 中 len 的作用是什么"))

    bq = "城市热岛效应的定义是什么"
    bf = ENG._auto_features(bq)
    ck("普通边界题=fact 或 boundary",
       ENG.question_type_from_features(bf) in ("boundary", "fact"), bf)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
