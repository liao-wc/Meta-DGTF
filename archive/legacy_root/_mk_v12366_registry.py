# -*- coding: utf-8 -*-
import collections, json
from pathlib import Path
p=Path("_v122_ast_registry.json")
raw=p.read_bytes(); crlf=b"\r\n" in raw
d=json.loads(raw.decode("utf-8"), object_pairs_hook=collections.OrderedDict)
d["current"]="元DGTF-V1.23.66.py"
d["added"]=352
d["n_symbols_current"]=641
reg=d["registry"]
add={
 "_quality_report":"质量闭环读数：覆盖率/三态/决策完整度/各层质量线索（只读，不改输出）",
 "_repair_json":"严格 JSON 解析失败时一次低温自修复：只修格式、不改语义；成本计 ops",
 "anytime_stagnant_decided":"anytime-valid 停滞判据：生长序列取反后判「多数不再长」，纠 v1.23.63 判据反向",
 "stage_stats":"分环节成本读数：按 stage 汇总 calls/tokens/ms，线程安全",
}
for k,v in add.items():
    reg[k]=collections.OrderedDict([("phase","F"),("reason",v)])
out=json.dumps(d,ensure_ascii=False,indent=1)
if crlf: out=out.replace("\n","\r\n")
p.write_bytes((out+("\r\n" if crlf else "\n")).encode("utf-8"))
print("current",d["current"],"added",d["added"],"n",d["n_symbols_current"],"entries",len(reg))
