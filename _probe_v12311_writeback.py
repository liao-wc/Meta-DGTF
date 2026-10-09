# -*- coding: utf-8 -*-
"""v1.23.11 两项（自省回写 / 事实题自动联网）before/after 对表探针。

★ 用 **v1.23.9 真跑产物的 packed 原文**驱动 `save_result`（零 LLM），
  另加合成负对照与源码接线断言。
用法：python _probe_v12311_writeback.py <目标文件.py>
"""
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKED = HERE / "_packed_v1239.json"


def _load(path):
    spec = importlib.util.spec_from_file_location("dgtf_v1211probe", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_v1211probe"] = m
    spec.loader.exec_module(m)
    return m


def main():
    m = _load(sys.argv[1])
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    packed = json.loads(PACKED.read_text(encoding="utf-8"))
    res = {}

    # ── A 自省回写：真实 packed 驱动 ─────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        out = m.save_result(copy.deepcopy(packed), td)
        t = Path(out).read_text(encoding="utf-8")
    res["A_真实产物_自省回写"] = ("**自省回写**" in t)
    res["A_真实产物_条数"] = t.count("- [all] ⚠") + t.count("- [0] ⚠") \
        + t.count("- [1] ⚠") + t.count("- [both] ⚠")
    res["A_真实产物_形态声明"] = ("**形态声明**" in t)

    # 负对照：没有高置信诊断时不许渲染
    _clean = {"orientation": "decision",
              "_config": {"actions": {"landing_decision": True}},
              "views": {"all": {"self_check": {"unsaid_is_escape": False},
                                "quality_flags": []}},
              "decidability": {}, "question": "这份方案怎么落地"}
    _ct = m.render_landing(_clean)
    res["A_负对照_无诊断不渲染"] = ("**自省回写**" not in _ct)
    # 正对照：有诊断时必须渲染
    _dirty = {"orientation": "decision",
              "_config": {"actions": {"landing_decision": True}},
              "views": {"all": {"self_check": {"unsaid_is_escape": True,
                                               "unsaid_where": "用未生收尾"},
                                "quality_flags": ["unsaid_overused(8)"]}},
              "decidability": {}, "question": "这份方案怎么落地"}
    _dt = m.render_landing(_dirty)
    res["A_正对照_有诊断渲染"] = ("**自省回写**" in _dt)

    # ── B 事实题自动联网 ────────────────────────────────────────
    res["B_有函数"] = hasattr(m, "_web_auto_for_facts")
    if res["B_有函数"]:
        res["B_事实题"] = m._web_auto_for_facts("新中国的成立时间是什么时候")
        res["B_决策题"] = m._web_auto_for_facts("这份方案怎么落地")
    res["B_main接线"] = ('_web_auto_for_facts(" ".join(args.question))' in src
                       and '"web": _web' in src)

    for k in res:
        print(f"{k} = {res[k]}")


main()
