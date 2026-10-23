# -*- coding: utf-8 -*-
"""诊断：复现冒烟 line 15838 `mod.auto_plan(q, cfg)` 返回 mode=serial 的路径。

只读不写：加载 smoke_test（含引擎 + 全局 LLM 打桩），spy 一层 LLM.call，
打印规则层判定 / 每次调用的 stage / 最终 plan。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import smoke_test as S  # noqa: E402  （加载引擎 + 打桩）

q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"
cfg = S.build_cfg(False)

print("== 规则层直判 ==")
print("  mode_rule       :", S.mod.mode_rule(q))
print("  orientation_rule:", S.mod.orientation_rule(q))

calls = []
orig = S.mod.LLM.call


def spy(self, system, user, temperature=0.6, max_tokens=3000,
        json_mode=False, model=None, thinking=None, stage=None):
    out = orig(self, system, user, temperature=temperature,
               max_tokens=max_tokens, json_mode=json_mode,
               model=model, thinking=thinking, stage=stage)
    calls.append((stage, (system or "")[:24].replace("\n", "|"),
                  str(out)[:110].replace("\n", "|")))
    return out


S.mod.LLM.call = spy
try:
    p = S.mod.auto_plan(q, cfg)
finally:
    S.mod.LLM.call = orig

print("== plan ==")
print(json.dumps(p, ensure_ascii=False, indent=1)[:2500])
print("== LLM 调用轨迹（stage / system头 / 返回头）==")
for c in calls:
    print("  ", c)
