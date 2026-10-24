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
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.2.py"


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
