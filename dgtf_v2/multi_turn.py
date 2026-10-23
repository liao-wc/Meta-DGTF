# -*- coding: utf-8 -*-
"""Multi-turn 与 Tool Calls 的通用适配器（供引擎/EML/证据环节调用）。"""
from __future__ import annotations
import json


def run_turns(llm, system, turns, *, history=None, **kw):
    """顺序多轮：每轮的 assistant 输出进入下一轮 history。"""
    hist = list(history or [])
    out = []
    for user in (turns or []):
        text = llm.call(system, str(user), history=hist, **kw)
        out.append(text)
        hist.append({"role": "assistant", "content": str(text)})
    return {"turns": out, "last": out[-1] if out else "", "history": hist}


def run_tool_loop(llm, system, user, tools, executor, *,
                  history=None, max_rounds: int = 4, **kw):
    """OpenAI 风格 tool_calls 循环；executor(name,args)->str。"""
    hist = list(history or [])
    trace = []
    for _ in range(max(1, int(max_rounds))):
        msg = llm.call(system, str(user), history=hist, tools=tools,
                       return_message=True, **kw)
        calls = list(getattr(msg, "tool_calls", None) or [])
        if not calls:
            return {"text": str(getattr(msg, "content", "") or ""),
                    "trace": trace, "history": hist}
        hist.append({"role": "assistant", "content":
                     str(getattr(msg, "content", "") or ""),
                     "tool_calls": [{"id": c.id, "type": "function",
                                     "function": {"name": c.function.name,
                                                  "arguments": c.function.arguments}}
                                    for c in calls]})
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except Exception:
                args = {}
            try:
                res = executor(c.function.name, args)
            except Exception as e:
                res = "ERROR: %s: %s" % (type(e).__name__, e)
            hist.append({"role": "tool", "tool_call_id": c.id,
                         "content": str(res)[:4000]})
            trace.append({"name": c.function.name, "args": args,
                          "result": str(res)[:300]})
    return {"text": "", "trace": trace, "history": hist,
            "error": "max_rounds"}


__all__ = ["run_turns", "run_tool_loop"]
