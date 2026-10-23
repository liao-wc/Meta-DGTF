# -*- coding: utf-8 -*-
import importlib.util, sys, threading, types
from pathlib import Path
import yaml

SRC = Path("元DGTF-V1.23.66.py")
spec = importlib.util.spec_from_file_location("dgtf66", str(SRC))
m = importlib.util.module_from_spec(spec); sys.modules["dgtf66"] = m
spec.loader.exec_module(m)

ok = 0; bad = []
def ck(name, cond, detail=""):
    global ok
    if cond: ok += 1
    else: bad.append(name + ((" — " + str(detail)) if detail else ""))

ck("version", m.__version__ == "1.23.66", m.__version__)

# anytime: stagnation vs growth
ck("anytime 全停滞=停", m.anytime_stagnant_decided([0] * 12)[0] is True)
ck("anytime 全在长=不停", m.anytime_stagnant_decided([1] * 12)[0] is False)
ck("anytime 样本不足=不停", m.anytime_stagnant_decided([0] * 3)[0] is False)
ck("anytime 混合=不停", m.anytime_stagnant_decided([0, 0, 1, 0, 0, 0])[0] is False)

# pool shape_limit
d = object.__new__(m.DGTF)
d.config = {"spiral": {"shape_limit": 4}}
d.use_content = True
p = m.Pool()
for i in range(8):
    p.amps.append({"desc": "amp%d" % i, "polarity": "0"})
txt = d._pool_text(p)
ck("pool 只列 4 条", txt.count("amp") == 4, txt.count("amp"))

# json repair with fake client
class _Msg:
    content = '{"ok": true}'
class _Choice:
    message = _Msg()
class _Resp:
    choices = [_Choice()]
    usage = types.SimpleNamespace(total_tokens=12)
class _Comp:
    def create(self, **kw):
        return _Resp()
class _Chat:
    completions = _Comp()
class _Client:
    chat = _Chat()

llm = object.__new__(m.LLM)
llm.client = _Client()
llm.default_model = "deepseek-flash"
llm.json_repair = True
llm.json_repaired = 0
llm.json_repair_failed = 0
llm.total_calls = 0
llm.total_tokens = 0
llm.ops_calls = 0
llm.ops_tokens = 0
llm.stage_calls = {}
llm.stage_tokens = {}
llm.stage_ms = {}
llm._lock = threading.Lock()
llm.parse_json = m.LLM.parse_json
fixed = llm._repair_json("{bad json", "test")
ck("json 自修复返回合法 JSON", bool(fixed) and llm.parse_json(fixed) is not None, fixed)
ck("json 自修复计数", llm.json_repaired == 0 and llm.ops_calls == 1 and llm.total_tokens == 12,
   (llm.ops_calls, llm.total_tokens))
st = llm.stage_stats()
ck("stage_stats 含 json_repair", any(r["stage"] == "json_repair" and r["tokens"] == 12 for r in st), st)

# quality report
class _V:
    quality_flags = ["x"]
    rounds_run = 2
    stop_primary = "test"
    quality_verdict = "ok"
    divergence = {"state": "收敛"}
d2 = object.__new__(m.MetaDGTF)
d2.pools = {"1": m.Pool()}
d2.config = {}
d2._tri_agree = 3
d2._tri_total = 5
d2._extract_actions = lambda v: []
d2._extract_not_do = lambda v: []
q = d2._quality_report({"1": _V()})
ck("quality 键齐", set(["coverage", "tri_state", "decision_actions", "layers", "flags"]) <= set(q), q)
ck("quality 三态", q["tri_state"] == [3, 5], q["tri_state"])

# config
cfg = yaml.safe_load(Path("dgtf_config.yaml").read_text(encoding="utf-8"))
ck("yaml json_repair=true", (cfg.get("api") or {}).get("json_repair") is True)
ck("yaml argumentation=true", ((cfg.get("playbook") or {}).get("argumentation") or {}).get("enabled") is True)
ck("yaml 版本头 66", "v1.23.66" in Path("dgtf_config.yaml").read_text(encoding="utf-8")[:120])

print("PASS", ok, "FAIL", len(bad))
for b in bad: print(" ✗", b)
raise SystemExit(1 if bad else 0)
