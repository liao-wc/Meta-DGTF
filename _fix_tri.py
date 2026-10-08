# -*- coding: utf-8 -*-
"""[v1.23.3] 补丁：triage 频度批 —— answers 加长（≥6 字，否则被过滤）
+ 加**负对照**锚点集（覆盖不到 ⇒ 必须 0 触发）。
"""
from pathlib import Path
import ast

P = Path("_run_v1233_triage.py")
s = P.read_text(encoding="utf-8")

O = '''        {"id": "a1", "tier": 1, "kind": "standard",
         "source": "GB50014-2021《室外排水设计标准》",
         "claim": ("GB50014-2021 规定：雨水管渠设计重现期，特大城市中心城区"
                   "应取 3~5 年，重要地区 10~50 年；内涝防治设计重现期"
                   "应按城市规模取 20~100 年。"),
         "answers": ["国家现行标准", "现行国标", "设计重现期", "内涝防治标准",
                     "国标的具体指标", "国家标准规定", "标准指标口径"]},
        {"id": "a2", "tier": 1, "kind": "dataset",
         "source": "住建部内涝防治年度报告（示意）",
         "claim": ("公开报告显示：老城区内涝成因以「管网能力不足 + 低洼地形"
                   "汇水」为主，占比约七成；局部强降雨与排水口顶托次之。"),
         "answers": ["历史内涝成因", "成因分布", "内涝成因数据", "近十年内涝",
                     "历史数据", "成因分布资料", "本市内涝点位"]},
        {"id": "a3", "tier": 1, "kind": "standard",
         "source": "《海绵城市建设技术指南（试行）》",
         "claim": ("年径流总量控制率按降雨与土壤渗透条件分区确定；老城区"
                   "改造以源头减排 + 过程控制为主，管网扩容需与调蓄同步。"),
         "answers": ["海绵城市技术指南", "年径流总量控制率", "源头减排"]},
        {"id": "a4", "tier": 1, "kind": "standard",
         "source": "行业规范（示意）",
         "claim": ("行业规范要求：改造前应完成管网漏损分区计量与压力管理，"
                   "漏损率验收以分区计量数据为准。"),
         "answers": ["管网漏损", "漏损率验收", "分区计量", "行业规范参数",
                     "规范的具体参数", "该规范的具体参数"]},
        {"id": "a5", "tier": 1, "kind": "dataset",
         "source": "该市统计年鉴（示意）",
         "claim": ("该市管网漏损历史统计显示：近五年漏损率由 18% 降至 12%，"
                   "老旧管段集中在 1990 年代敷设区域。"),
         "answers": ["漏损历史统计", "该市管网漏损的历史统计", "漏损率",
                     "历史统计", "老旧管段"]},
    ],
}'''
N = '''        {"id": "a1", "tier": 1, "kind": "standard",
         "source": "GB50014-2021《室外排水设计标准》",
         "claim": ("GB50014-2021 规定：雨水管渠设计重现期，特大城市中心城区"
                   "应取 3~5 年，重要地区 10~50 年；内涝防治设计重现期"
                   "应按城市规模取 20~100 年。"),
         "answers": ["国家现行标准的具体指标口径", "现行国标的具体指标",
                     "雨水管渠设计重现期", "内涝防治设计重现期",
                     "国标的具体指标口径", "国家现行标准规定"]},
        {"id": "a2", "tier": 1, "kind": "dataset",
         "source": "住建部内涝防治年度报告（示意）",
         "claim": ("公开报告显示：老城区内涝成因以「管网能力不足 + 低洼地形"
                   "汇水」为主，占比约七成；局部强降雨与排水口顶托次之。"),
         "answers": ["本市近十年内涝点的成因分布", "历史内涝成因分布",
                     "内涝成因分布资料", "近十年内涝点成因占比",
                     "本市现状管网能力参数"]},
        {"id": "a3", "tier": 1, "kind": "standard",
         "source": "《海绵城市建设技术指南（试行）》",
         "claim": ("年径流总量控制率按降雨与土壤渗透条件分区确定；老城区"
                   "改造以源头减排 + 过程控制为主，管网扩容需与调蓄同步。"),
         "answers": ["海绵城市建设技术指南", "年径流总量控制率要求",
                     "源头减排与过程控制"]},
        {"id": "a4", "tier": 1, "kind": "standard",
         "source": "行业规范（示意）",
         "claim": ("行业规范要求：改造前应完成管网漏损分区计量与压力管理，"
                   "漏损率验收以分区计量数据为准。"),
         "answers": ["上级最新规范的具体参数", "规范限值与强制条款",
                     "漏损率验收阈值", "管网漏损分区计量"]},
        {"id": "a5", "tier": 1, "kind": "dataset",
         "source": "该市统计年鉴（示意）",
         "claim": ("该市管网漏损历史统计显示：近五年漏损率由 18% 降至 12%，"
                   "老旧管段集中在 1990 年代敷设区域。"),
         "answers": ["该市管网漏损的历史统计", "分区级管段级漏损台账",
                     "该市管网漏损历史数据"]},
    ],
}

# ★ 负对照锚点集：同样条数、同样 tier，但**与题目无关** ⇒ 一条都命中不了。
#   它回答的是「triage 是不是只要开锚点就会触发」——必须 0。
ANCHORS_NEG = {
    "question": QUESTIONS[0][1],
    "retrieved_at": "2026-10-06T00:00:00+08:00",
    "retriever": "manual-tier1-negctl",
    "anchors": [
        {"id": "n1", "tier": 1, "kind": "standard",
         "source": "无关领域规范（负对照）",
         "claim": ("某行业规范规定：冷链运输车厢温度应保持在零下十八度"
                   "以下，装卸货时长不超过三十分钟。"),
         "answers": ["冷链运输车厢温度控制", "装卸货时长限制"]},
        {"id": "n2", "tier": 1, "kind": "dataset",
         "source": "无关数据集（负对照）",
         "claim": ("某平台统计显示：咖啡豆年度进口量同比增长百分之七，"
                   "其中阿拉比卡占比六成。"),
         "answers": ["咖啡豆年度进口量统计", "阿拉比卡占比数据"]},
        {"id": "n3", "tier": 1, "kind": "standard",
         "source": "无关规程（负对照）",
         "claim": "某规程规定：高空作业必须佩戴双钩安全带并设置生命线。",
         "answers": ["高空作业安全带要求", "生命线设置规程"]},
    ],
}'''
assert s.count(O) == 1, s.count(O)
s = s.replace(O, N)


O2 = '''    ANCH.write_bytes(json.dumps(ANCHORS, ensure_ascii=False, indent=1)
                     .encode("utf-8"))'''
N2 = '''    _use = ANCHORS_NEG if MODE == "negctl" else ANCHORS
    ANCH.write_bytes(json.dumps(_use, ensure_ascii=False, indent=1)
                     .encode("utf-8"))'''
assert s.count(O2) == 1
s = s.replace(O2, N2)

O3 = '''    RUNS.write_bytes(json.dumps(out, ensure_ascii=False, indent=1,
                                default=str).encode("utf-8"))'''
N3 = '''    if MODE == "negctl":
        (HERE / "_v1233_triage_negctl.json").write_bytes(
            json.dumps(out, ensure_ascii=False, indent=1,
                       default=str).encode("utf-8"))
    RUNS.write_bytes(json.dumps(out, ensure_ascii=False, indent=1,
                                default=str).encode("utf-8"))'''
assert s.count(O3) == 1
s = s.replace(O3, N3)

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("triage 批：answers 加长 + 负对照锚点集已加")
