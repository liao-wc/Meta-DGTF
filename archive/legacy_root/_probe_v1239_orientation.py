# -*- coding: utf-8 -*-
"""v1.23.9 取向分流守卫 before/after 对表探针（离线、零 LLM 调用）。

驱动生产入口 `render_landing`，量「题面 + 取向」→ 走哪套模板。
用法：python _probe_v1239_orientation.py <目标文件.py>
"""
import importlib.util
import sys

FACT_Q = "新中国的成立时间是什么时候"
DEC_Q = "老城区暴雨内涝频发，排水系统重建还是局部修补，该不该统一规划"


def _load(path):
    spec = importlib.util.spec_from_file_location("dgtf_v1239probe", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_v1239probe"] = m
    spec.loader.exec_module(m)
    return m


def _kind(txt):
    return "decision" if "落地层（decision 模式）" in txt else "boundary"


def main():
    m = _load(sys.argv[1])
    res = {}

    def run(orientation, question, landing_on=True):
        return _kind(m.render_landing({
            "orientation": orientation,
            "_config": {"actions": {"landing_decision": landing_on}},
            "views": {}, "decidability": {}, "question": question}))

    res["auto+事实题"] = run("auto", FACT_Q)
    res["auto+决策题"] = run("auto", DEC_Q)
    res["decision+事实题"] = run("decision", FACT_Q)
    res["boundary+决策题"] = run("boundary", DEC_Q)
    res["auto+空题面"] = run("auto", "")
    # 没有 question 键（老调用形态）：不许因为取不到题面就静默换模板
    res["auto+无question键"] = _kind(m.render_landing({
        "orientation": "auto",
        "_config": {"actions": {"landing_decision": True}},
        "views": {}, "decidability": {}}))
    res["关开关+决策题"] = run("decision", DEC_Q, landing_on=False)

    res["有函数"] = hasattr(m, "_has_decision_context")
    if res["有函数"]:
        for q in (FACT_Q, DEC_Q,
                  "1949年10月1日的开国大典有多少人参加",
                  "这个方案怎么落地",
                  "我要不要现在买",
                  "《共同纲领》是哪一年通过的",
                  "三条路径的利弊取舍"):
            res["ctx|" + q[:14]] = m._has_decision_context(q)

    for k in sorted(res):
        print(f"{k} = {res[k]}")


main()
