# -*- coding: utf-8 -*-
"""① max_uncovered_pushes 1 vs 0 的真模型 A/B 对照。

调法：python _run_ab.py A   → max_uncovered_pushes=1（现状/基线）
      python _run_ab.py B   → max_uncovered_pushes=0（第一次触发就停）

同题、同档（balanced）、serial、四层、各 3 圈——唯一变量就是这个值。
题沿用第 7 次真跑那道（已知它会触发 fix-88b 推迟与真实停止），
这样两个 arm 才有差别可测。
"""
import importlib.util
import os
import sys
import time

from dotenv import load_dotenv

TAG = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
assert TAG in ("A", "B"), TAG

load_dotenv(".env")

PUSH = {"A": 1, "B": 0}[TAG]
PROFILE = "balanced"
MODE = "serial"
ROUNDS = {"0": 3, "1": 3, "both": 3, "all": 3}
QUESTION = ("复杂问题被拆成几个部分分别研究之后，"
            "剩下的那个「整体」到底是什么？")

spec = importlib.util.spec_from_file_location("dgtf58", "元DGTF-V1.21.58.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf58"] = mod
spec.loader.exec_module(mod)

cfg = mod.load_config("dgtf_config.yaml")
cfg["cost_profile"] = PROFILE
cfg.setdefault("output", {})["verbose"] = True
# 唯一变量
cfg.setdefault("spiral", {})["max_uncovered_pushes"] = PUSH

print(f"[ARM] {TAG}  max_uncovered_pushes={PUSH}")
print(f"[COST] profile={PROFILE} mode={MODE} rounds={ROUNDS}")
print(f"[QUESTION] {QUESTION}")
print(f"[KEY] 载入={bool(os.getenv('DGTF_API_KEY'))}")

meta = mod.MetaDGTF(cfg)
t0 = time.time()
res = meta.run(QUESTION, route=["0", "1", "both", "all"],
               rounds=ROUNDS, parallel_mode=MODE)
elapsed = time.time() - t0

path = mod.save_result(res, "outputs")
print(f"[CALLS] llm_calls={res.get('llm_calls')} tokens={res.get('llm_tokens')}")
print(f"[COST] 耗时 {elapsed:.0f}s  arm={TAG}  max_uncovered_pushes={PUSH}")
print(f"[OUTPUT] {path}")
