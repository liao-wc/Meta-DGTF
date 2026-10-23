# -*- coding: utf-8 -*-
import glob, json
from pathlib import Path
from dgtf_v2.replay import replay
fs = sorted(glob.glob("outputs/*.packed.json"))[-20:]
o = replay(fs, 20)
summary = {
    "runs": o["runs"], "routes": o["routes"],
    "quality_mean": o["quality_mean"],
    "priors_n": len(o["priors"]["templates"]),
    "decisions": [d["action"] for d in o["trace"]["decisions"]],
    "stop": o["trace"]["stop_reason"],
    "closure": bool(o["closure"].get("decision")),
    "memory": o["memory"],
}
Path("audits/v2_replay_20.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
