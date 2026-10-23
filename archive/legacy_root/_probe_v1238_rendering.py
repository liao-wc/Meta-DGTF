# -*- coding: utf-8 -*-
"""v1.23.8 渲染层守卫 before/after 对表探针。

三处改动全部在**渲染层**，所以探针直接驱动生产入口
（`render_landing` / `save_result` 的源码），**离线、零 LLM、零成本**。

用法：python _probe_v1238_rendering.py <目标文件.py>
输出：stdout（对齐后 before / after 两列同形，逐行 diff）
"""
import importlib.util
import inspect
import re
import sys


def _load(path):
    spec = importlib.util.spec_from_file_location("dgtf_v1238probe", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_v1238probe"] = m
    spec.loader.exec_module(m)
    return m


def _sections(txt):
    """把 markdown 切成 (标题, 该节正文字符数)。用于判「有标题无内容」。"""
    parts = re.split(r"(?m)^(#{3,4} .*)$", txt)
    out = []
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i].strip(), len(parts[i + 1].strip())))
    return out


def _empty_sections(txt):
    return [s for s, n in _sections(txt) if n == 0]


def main():
    path = sys.argv[1]
    m = _load(path)
    res = {}

    # ── A 空节守卫（decision 模板）──────────────────────────────
    # A1 无 actions：真跑实测该形态留下「### 三、所需数据清单」空节
    _r1 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {}, "decidability": {}}
    t1 = m.render_landing(_r1)
    res["A1_空节"] = _empty_sections(t1)
    res["A1_节数"] = len(_sections(t1))
    # ★ 负对照：不许靠「把标题删掉」来消灭空节（首版补丁正是这么错的，
    #   这个读数当场抓到）。
    res["A1_六节标题在"] = "### 六、如果只能做一件事" in t1
    res["A1_三节标题在"] = "### 三、所需数据清单" in t1

    # A2 有 actions（冒烟同款输入）：不许把有内容的节一起删掉（负对照）
    _r2 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {"1": {"decidable_product": {
               "answer": "指派 排水公司 核查 内涝点位，汛期前完成，"
                         "否则回退人工排查。"}}},
           "decidability": {}}
    t2 = m.render_landing(_r2)
    res["A2_空节"] = _empty_sections(t2)
    res["A2_有行动清单"] = "### 二、行动清单" in t2
    res["A2_有落地层头"] = "落地层（decision 模式）" in t2

    # ── B 停止原因汇总 ─────────────────────────────────────────
    res["B_有函数"] = hasattr(m, "_stop_kind_summary")
    if res["B_有函数"]:
        _cut = ("体力耗尽（1 圈走满，未触发任何停止判据，"
                "是被截断不是自然停止）")
        res["B_四层被截断"] = m._stop_kind_summary(
            {k: {"stop_reason": _cut} for k in ("0", "1", "both", "all")}
        ).strip()
        res["B_混合"] = m._stop_kind_summary({
            "0": {"stop_reason": _cut},
            "1": {"stop_reason": "连续 2 轮无新 &，螺旋停止"},
        }).strip()
        res["B_空输入"] = repr(m._stop_kind_summary({}))
        res["B_全无停因"] = repr(m._stop_kind_summary({"0": {}, "1": {}}))
    # 接线（走生产路径才不是死代码）
    _ss = inspect.getsource(m.save_result)
    res["B_接线"] = "_stop_kind_summary(" in _ss

    # ── C suspensions 渲染去重 ──────────────────────────────────
    res["C_有函数"] = hasattr(m, "_dedup_suspensions_for_render")
    if res["C_有函数"]:
        _items = [
            {"target": "用途场景未显形，精度三档无判据",
             "reason": "提问者用途未出现，年、年月日、时刻无共同判据。"},
            {"target": "用途场景未显形，精度三档无判据；元层决定不消解。",
             "reason": "用途未显形，精度三档无共同判据"},
            {"target": "日期同压事件发生与被命名，分离口缺席",
             "reason": "没有格式同时装两层"},
            {"target": "日期同压事件发生与被命名，分离口缺席；元层决定不消解。",
             "reason": "无格式同装两层"},
            {"target": "共同纲领、政府成立、开国大典效力层级排序",
             "reason": "缺共同层级标准"},
        ]
        _kept, _dup = m._dedup_suspensions_for_render(_items)
        res["C_真跑形态_保留"] = len(_kept)
        res["C_真跑形态_合并"] = _dup
        # 负对照：不同 target 一条都不许合
        _k2, _d2 = m._dedup_suspensions_for_render(
            [{"target": "甲甲甲甲甲甲"}, {"target": "乙乙乙乙乙乙"}])
        res["C_异target_保留"] = len(_k2)
        res["C_异target_合并"] = _d2
        # 负对照：单条输入不许被吞
        _k3, _d3 = m._dedup_suspensions_for_render([{"target": "丙丙丙丙丙丙"}])
        res["C_单条_保留"] = len(_k3)
    _ss2 = inspect.getsource(m.save_result)
    res["C_接线"] = "_dedup_suspensions_for_render(" in _ss2

    for k in sorted(res):
        print(f"{k} = {res[k]}")


main()
