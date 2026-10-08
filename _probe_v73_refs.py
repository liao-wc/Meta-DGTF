# -*- coding: utf-8 -*-
"""单次调用探针：外判 _assess_decidability 到底返不返 anchor_refs？"""
import importlib.util, io, json, os, sys, contextlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.73.py"
ANCHORS = HERE / "anchors" / "up_biz_anchors.json"

def load_dotenv(p):
    if not p.exists(): return
    for line in p.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_dotenv(HERE/".env")
spec=importlib.util.spec_from_file_location("dgtf73p", str(SRC))
mod=importlib.util.module_from_spec(spec); sys.modules["dgtf73p"]=mod
spec.loader.exec_module(mod)

cfg=mod.load_config(str(HERE/"dgtf_config.yaml"))
cfg["external_anchor"]={"enabled": True, "path": str(ANCHORS), "max_items": 12, "crosscheck": True}
m=mod.MetaDGTF(cfg); m.verbose=False
anchors=m._load_anchors()
print(f"载入锚点 {len(anchors)} 条")

d=mod.DGTF("1", m.llm, cfg); d.verbose=False
Q="现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？"
for tag,A in (("带锚点", anchors), ("不带锚点", None)):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        r=d._assess_decidability(Q, anchors=A)
    print(f"\n=== {tag} ===")
    print("  keys:", sorted(r.keys()))
    print("  anchor_refs      =", r.get("anchor_refs"))
    print("  _anchors_given   =", r.get("_anchors_given"))
    print("  decidability     =", r.get("decidability"))
    print("  理由             =", str(r.get("reason"))[:200])
