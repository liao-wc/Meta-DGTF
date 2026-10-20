# -*- coding: utf-8 -*-
import importlib.util, json, io, sys, shutil
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("dgtf_main", root / "元DGTF-V1.30.0.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_main"] = mod
spec.loader.exec_module(mod)
p = root / "outputs" / "20261020_154010_DeepSeek-V41-Flash-.packed.json"
res = json.loads(p.read_text(encoding="utf-8"))
outdir = root / ".dsh_tmp" / "replay_out"
if outdir.exists():
    shutil.rmtree(outdir)
outdir.mkdir(parents=True, exist_ok=True)
md = mod.save_result(res, save_dir=str(outdir))
text = md.read_text(encoding="utf-8")
print("MD:", md)
print("HAS_FACT:", "事实答案" in text)
print("HAS_NEG:", ("不存在" in text) or ("虚构" in text))
for i, line in enumerate(text.splitlines(), 1):
    if "输入自检" in line or "不存在" in line or "虚构" in line:
        print(i, line)
print("SAN:", json.dumps(res.get("input_sanity"), ensure_ascii=False)[:1200])
