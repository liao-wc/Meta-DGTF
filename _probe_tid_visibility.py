# -*- coding: utf-8 -*-
"""离线（不联网）判定：元层 probe 的 prompt 里到底有没有给出 t_XXX 编号。

只 stub 掉 llm.call 并捕获它收到的 user 文本，然后看 tension_text 长什么样。
"""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("dgtf_t", "元DGTF-V1.21.62.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_t"] = mod
spec.loader.exec_module(mod)

captured = {}


class StubLLM:
    """最小替身：只记录，不联网。"""
    default_model = "x"
    reasoner_model = "x"
    thinking_reasoner = None
    SERVED_SEEN = set()

    def call(self, system, user, *a, **kw):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({"probes": [], "engagements": [], "suspensions": [],
                           "threads": [], "reconfirmations": [],
                           "revocations": []}, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


cfg = mod.load_config("__nonexistent__.yaml")
d = mod.DGTF("all", StubLLM(), cfg)

# ---- 上游：一个对撞 view + 对应 pool（带 t_XXX 编号，模拟真实产物）----
DUEL = [
    {"id": "t_005", "target": "接口被用掉那一轮，用掉动作本身有无痕迹",
     "status": "active", "quadrant": "③"},
    {"id": "t_006", "target": "接缝被先行命名时，命名动作落在哪一轮",
     "status": "active", "quadrant": "③"},
    {"id": "t_001", "target": "拆解动作占的格与回指新发声占的格是否同一",
     "status": "resolved", "quadrant": "③"},
]
both_pool = mod.Pool()
both_pool.duel_suspensions = [dict(x) for x in DUEL]
both_view = mod.View(entry="both")
both_view.duel_suspensions = [dict(x) for x in DUEL]

inp = mod.Input(question="冒烟：编号可见性",
                upstream_views=[both_view], upstream_pools=[both_pool])
v = mod.View(entry="all")
out = d._probe_meta(v, inp, mod.Pool())

u = captured.get("user", "")
print("=== 元层 probe 的 user 里，对撞张力清单 ===")
seg = u[u.find("对撞悬置的张力"):] if "对撞悬置的张力" in u else u
print(seg[:420] if seg else "（user 里没有『对撞悬置的张力』段）")
print()
print("清单里出现 t_005:", "[t_005]" in u)
print("清单里出现 t_006:", "[t_006]" in u)
print("清单里出现 resolved 的 t_001:", "[t_001]" in u)
print()
sysm = captured.get("system", "")
print("=== system 里的 JSON schema 示例 ===")
i = sysm.find('"engagements"')
print(sysm[i - 20:i + 200] if i >= 0 else "（没找到 schema）")
print()
print("system 里字面出现 \"t_001\" 次数:", sysm.count('"t_001"'))
