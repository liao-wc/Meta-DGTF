# -*- coding: utf-8 -*-
"""⑤ 预算验证：不再覆盖 rounds，用配置里那套「按证据调过」的预算跑。

背景（历史样本分析，n=44，同一天内对照，版本相同）：
  · 同一天内 大预算 vs 小预算：质量线索 2.10→1.20（09-26）、1.83→0.83（09-27）
    → 圈数给够，系统自己挂的问题标记少一半。
  · 最近一天(09-28, 预算 12)各层的自然停止点：
    修行 3–4（偶发 10–11）、研究 2–3、对撞 5–6（偶发 11）、元 3–4
  · 配置里 per_entry."0".hard_max=6、per_entry."both".soft_max=5，
    本来就是按这些证据调的；但**前几轮真跑显式传了 rounds=3**，
    把它覆盖了 —— 那才是「19 次体力耗尽只有 1 次真停止」的直接原因。

所以本轮**不传 rounds**（rounds=0 → 走 spiral.hard_max 与 per_entry 覆盖），
看各层在自己的判据下停在哪一圈、代价多少。
"""
import importlib.util
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv(".env")

PROFILE = "balanced"
MODE = "serial"
QUESTION = ("复杂问题被拆成几个部分分别研究之后，"
            "剩下的那个「整体」到底是什么？")

spec = importlib.util.spec_from_file_location("dgtf58", "元DGTF-V1.21.58.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf58"] = mod
spec.loader.exec_module(mod)

cfg = mod.load_config("dgtf_config.yaml")
cfg["cost_profile"] = PROFILE
cfg.setdefault("output", {})["verbose"] = True

sp = cfg.get("spiral") or {}
print("[BUDGET] 不传 rounds，用配置：hard_max=" + str(sp.get("hard_max"))
      + " soft_max=" + str(sp.get("soft_max")))
print("[BUDGET] per_entry=" + repr(sp.get("per_entry")))
print("[COST] profile=" + PROFILE + " mode=" + MODE)
print("[QUESTION] " + QUESTION)
print(f"[KEY] 载入={bool(os.getenv('DGTF_API_KEY'))}")

meta = mod.MetaDGTF(cfg)
t0 = time.time()
res = meta.run(QUESTION, route=["0", "1", "both", "all"],
               parallel_mode=MODE)          # rounds 不传 → 0
elapsed = time.time() - t0

path = mod.save_result(res, "outputs")
print(f"[CALLS] llm_calls={res.get('llm_calls')} tokens={res.get('llm_tokens')}")
print(f"[COST] 耗时 {elapsed:.0f}s  (不覆盖 rounds)")
print(f"[OUTPUT] {path}")
