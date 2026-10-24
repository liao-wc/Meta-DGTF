# -*- coding: utf-8 -*-
"""DeepSeek API 能力 → 元DGTF 阶段映射（只读矩阵，不产生调用）。"""

MATRIX = [
    {"feature": "Chat Completions", "stages": "全部四层/EML/预检",
     "status": "used", "why": "所有推理调用的基础协议"},
    {"feature": "Thinking", "stages": "逐环节 24 档",
     "status": "used", "why": "api.thinking.stages + EML thinking_hint"},
    {"feature": "JSON Output", "stages": "结构化产物/裁决",
     "status": "used", "why": "json_mode + 本地修复 + bad_json 留痕"},
    {"feature": "Vision", "stages": "预检 -> 四层",
     "status": "used", "why": "vision_input 图片描述一次，作为证据入池"},
    {"feature": "Search", "stages": "全部授权联网环节",
     "status": "used", "why": "/v1/tools/search；三档配额"},
    {"feature": "Fetch", "stages": "预检 + _web_search 主路径",
     "status": "used", "why": "/v1/tools/fetch；每跑上限，失败留痕"},
    {"feature": "Context Disk Cache", "stages": "全部调用",
     "status": "auto", "why": "服务端自动缓存，客户端不显式开关"},
    {"feature": "Multi-turn", "stages": "适配器可用",
     "status": "adapted", "why": "LLM.call(history=...)/run_turns 已通；默认层循环仍一跑一呼"},
    {"feature": "Tool Calls", "stages": "事实预检",
     "status": "used", "why": "_tool_preflight 真跑 tools_calls=4"},
    {"feature": "Files API", "stages": "视觉大图/复用",
     "status": "used", "why": "files_api upload/delete/list；file_id 进 vision blocks"},
    {"feature": "FIM Completion", "stages": "不适用",
     "status": "n/a", "why": "四层是推理/证据闭环，不是代码补全"},
    {"feature": "Chat Prefix Completion", "stages": "不适用",
     "status": "n/a", "why": "会破坏层间独立性与可审计性"},
    {"feature": "Responses API", "stages": "协议替代",
     "status": "n/a", "why": "引擎统一使用 Chat Completions"},
    {"feature": "Anthropic API", "stages": "协议替代",
     "status": "n/a", "why": "引擎统一使用 OpenAI 兼容协议"},
]


def summary() -> dict:
    counts = {}
    for r in MATRIX:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"n": len(MATRIX), "counts": counts,
            "matrix": [dict(r) for r in MATRIX]}


__all__ = ["MATRIX", "summary"]
