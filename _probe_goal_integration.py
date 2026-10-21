# -*- coding: utf-8 -*-
"""Goal round 1 integration probe: mapping / EML / new API / engine-app roundtrip."""
import json, os, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8765"
P, F = [], []
def ck(name, ok, info=""):
    (P if ok else F).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + str(info)) if (info and not ok) else ""))

def req(method, path, payload=None, timeout=60):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode("utf-8"))
        except Exception: body = {}
        return e.code, body

# 1) health / mapping
st, h = req("GET", "/api/health", timeout=30)
ck("health 200", st == 200, st)
ck("health ok", bool(h.get("ok")), h.get("checks"))
ck("engine mapping", h.get("engine", {}).get("file", "").endswith(".py") and h.get("engine", {}).get("layers") == ["0","1","both","all"], h.get("engine"))
ck("EML modules", all((h.get("modules") or {}).values()), h.get("modules"))
ck("dependency chain", bool(h.get("checks", {}).get("fact_flow") and h.get("checks", {}).get("scheduler")), h.get("checks"))
ck("app mapping", "EML_self_feedback" in (h.get("mapping") or {}), h.get("mapping"))
st, eml = req("GET", "/api/agent/eml", timeout=30)
ck("EML status mapped", st == 200 and eml.get("ok")
   and (eml.get("playbook") or {}).get("n", 0) >= 0
   and (eml.get("v2_shadow") or {}).get("n", 0) >= 0, (st, eml))
st, rep = req("POST", "/api/agent/eml/replay", {"limit": 20, "dry_run": True}, timeout=90)
ck("EML replay dry-run", st == 200 and rep.get("ok") and rep.get("replayed", 0) > 0
   and bool((rep.get("priors") or {}).get("templates")), (st, rep))

# 2) schedule preview flexibility + precedence
st, p0 = req("POST", "/api/schedule/preview", {"question": "调度预览"})
ck("preview default", st == 200 and p0.get("ok") and p0.get("layers") == ["0","1","both","all"], p0)
st, p1 = req("POST", "/api/schedule/preview", {"question": "调度预览",
    "opts": {"route": "0,1", "parallel": "serial", "rounds": "1"}})
ck("preview opts", st == 200 and p1.get("effective", {}).get("route") == "0,1"
   and p1.get("effective", {}).get("parallel") == "serial"
   and p1.get("precedence", {}).get("route") == "opts", p1.get("effective"))
ck("preview cli flags", "--route" in p1.get("cli", []) and "0,1" in p1.get("cli", []), p1.get("cli"))
st, pareto = req("GET", "/api/schedule/pareto?prefer=balanced", timeout=60)
ck("pareto frontier", st == 200 and pareto.get("ok") and bool(pareto.get("frontier")), (st, pareto))
st, prof = req("GET", "/api/schedule/profiles", timeout=30)
profiles = (prof or {}).get("profiles") or []
ck("profiles list", st == 200 and bool(profiles), prof)
pareto = next((x for x in profiles if x.get("recommended")), None)
ck("pareto profile", bool(pareto and "帕累托" in str(pareto.get("name"))), pareto)
st, p2 = req("POST", "/api/schedule/preview", {"question": "profile预览",
    "profile": (pareto or {}).get("id", "")})
ck("preview profile", st == 200 and p2.get("ok") and p2.get("profile") and any("--config" in p2.get("cli", []) for _ in [0]), p2)
st, pbad = req("POST", "/api/schedule/preview", {"question": "bad", "opts": "bad"})
ck("preview invalid opts", st == 200 and pbad.get("ok") is False, (st, pbad))
st, pol = req("POST", "/api/schedule/pareto/apply", {"prefer": "balanced"}, timeout=90)
ck("pareto policy apply", st == 200 and pol.get("ok")
   and bool((pol.get("policy") or {}).get("profile")), (st, pol))
st, polget = req("GET", "/api/schedule/policy", timeout=30)
ck("pareto policy persisted", st == 200 and polget.get("ok")
   and (polget.get("policy") or {}).get("profile"), (st, polget))
st, v2 = req("GET", "/api/schedule/v2", timeout=30)
ck("v2 shadow mapped", st == 200 and v2.get("ok") and v2.get("n", 0) > 0, (st, v2))
ck("v2 A/B templates", bool(v2.get("by_template"))
   and any((x or {}).get("n", 0) > 0 for x in (v2.get("by_template") or {}).values()), v2.get("by_template"))

# 3) read API contract
reads = ["/api/config", "/api/chats", "/api/outputs", "/api/outputs/facets",
         "/api/dashboard", "/api/agent/tasks", "/api/agent/results",
         "/api/agent/knowledge", "/api/dsh/proposals", "/api/dsh/sessions",
         "/api/dsh/artifacts", "/api/params"]
for path in reads:
    st, d = req("GET", path, timeout=30)
    ck("read " + path, st == 200 and isinstance(d, dict), (st, str(d)[:160]))

# 4) write API validation (flexibility, no 500)
st, d = req("POST", "/api/tasks", {"question": ""})
ck("task empty 400", st == 400, (st, d))
st, d = req("POST", "/api/dsh/chat", {"task": ""})
ck("chat empty 400", st == 400, (st, d))
st, d = req("POST", "/api/agent/knowledge/dedupe", {})
ck("dedupe idempotent", st == 200 and d.get("removed", 0) >= 0, (st, d))

# 5) auto job flexibility (consumer only, no network LLM)
st, j = req("POST", "/api/agent/auto/start", {"stage": "consumer"})
ck("auto job start", st == 200 and j.get("job_id"), (st, j))
jid = j.get("job_id", "")
job = None
if jid:
    idx = 0
    for _ in range(30):
        time.sleep(1)
        st, job = req("GET", "/api/agent/auto/job/%s?since=%s" % (jid, idx), timeout=30)
        idx = job.get("next", idx)
        if job.get("status") in ("done", "error"):
            break
ck("auto job done", bool(job and job.get("status") == "done"), job)
st, jobs = req("GET", "/api/agent/auto/jobs", timeout=30)
ck("auto job persisted/list", st == 200 and any(
    x.get("id") == jid and x.get("status") == "done"
    for x in (jobs.get("jobs") or [])), (st, jobs))

# 6) engine -> app mock roundtrip + four layers
st, t = req("POST", "/api/tasks", {"question": "元DGTF app 集成探针：四层为什么要互相校验？",
                                   "opts": {"mock": True, "auto_pareto": True}})
ck("mock task create", st == 201 and t.get("id") and t.get("auto_pareto") and "帕累托" in str(t.get("profile")), (st, t))
tid = t.get("id", "")
task = None
if tid:
    for _ in range(90):
        time.sleep(1)
        st, task = req("GET", "/api/tasks/" + tid, timeout=30)
        if task.get("status") in ("done", "error", "interrupted"):
            break
ck("mock task done", bool(task and task.get("status") == "done"), task and task.get("status"))
if task and task.get("status") == "done":
    st, layers = req("GET", "/api/tasks/%s/layers" % tid, timeout=30)
    keys = set((layers.get("layers_by_id") or {}).keys()) if isinstance(layers, dict) else set()
    ck("four layers mapped", {"0","1","both","all"}.issubset(keys), layers if not keys else keys)
    st, result = req("GET", "/api/tasks/%s/result" % tid, timeout=30)
    ck("result body", st == 200 and bool(result.get("body")), str(result)[:160])

# 7) EML unit suites
env = dict(os.environ); env["PYTHONPATH"] = str(ROOT); env["PYTHONUTF8"] = "1"
suites = ["tests_self_feedback.py", "tests_agent_bridge.py", "tests_llm_feedback.py",
          "tests_online_adapt.py", "tests_unified_memory.py"]
for name in suites:
    cp = subprocess.run([sys.executable, str(ROOT / "dgtf_v2" / name)], cwd=str(ROOT),
                        env=env, text=True, encoding="utf-8", errors="replace",
                        capture_output=True, timeout=120)
    tail = (cp.stdout or "")[-400:]
    ok = cp.returncode == 0 and "FAIL 0" in tail
    ck("EML " + name, ok, tail)

print()
print("PROBE PASS %d / FAIL %d" % (len(P), len(F)))
sys.exit(1 if F else 0)
