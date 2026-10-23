# -*- coding: utf-8 -*-
"""[诊断] 单层跑一圈，打印 LLM 收到的 system 头 80 字符 —— 找候选提示的标识串。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

SYSTEMS = []
_fake = st.mod.LLM.call


def rec(self, system, user, temperature=0.6, max_tokens=3000,
        json_mode=False, model=None, thinking=None, stage=None):
    SYSTEMS.append(("sys", str(system or "")[:80].replace("\n", "⏎")))
    SYSTEMS.append(("usr", str(user or "")[:80].replace("\n", "⏎")))
    return _fake(self, system, user, temperature=temperature,
                 max_tokens=max_tokens, json_mode=json_mode, model=model,
                 thinking=thinking, stage=stage)


st.mod.LLM.call = rec
meta = st.mod.MetaDGTF(st.build_cfg(False))
meta.run("测试：设计一个让群体协作保持活力的制度",
         route=["1"], rounds={"1": 1}, run_id="")
seen = set()
for kind, s in SYSTEMS:
    if s not in seen:
        seen.add(s)
        print("%s | %s" % (kind, s))
