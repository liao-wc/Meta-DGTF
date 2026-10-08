# -*- coding: utf-8 -*-
"""[_probe_packed_vs_md.py] 只读探针：产物 md 到底漏了 packed 里的什么。

做法（离线、用冒烟已有的桩，不联网）：
  1. 复用 smoke_test 的 `fake_call` 桩与 `build_cfg`；
  2. 跑一次 route 0,1（各 1 圈）；
  3. 递归枚举 packed 的**叶子路径**；
  4. 把渲染出的 md 文本读进来，逐条判断「该字段名是否在 md 里出现过」；
  5. 顺便量 packed 的 JSON 体积（决定"全量附录"要怎么落）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("smoke_probe", HERE / "smoke_test.py")
sm = importlib.util.module_from_spec(spec)
sys.modules["smoke_probe"] = sm
spec.loader.exec_module(sm)          # 装好 mod.LLM.call = fake_call 桩

mod = sm.mod
cfg = sm.build_cfg(False)
meta = mod.MetaDGTF(cfg)
res = meta.run("审计探针用题：AI 在数字 IC 设计里能做什么",
               route=["0", "1"], rounds={"0": 1, "1": 1},
               parallel_mode="serial")
print(f"[run] llm_calls={res.get('llm_calls')} views={sorted(res.get('views') or {})}")

md_path = mod.save_result(res, cfg["output"]["save_dir"])
md = md_path.read_text(encoding="utf-8")
print(f"[md] {md_path.name}  {len(md)} chars")

# ---- packed 体积 ----
dump = json.dumps(res, ensure_ascii=False, default=str)
print(f"[packed] json {len(dump)} chars  top-level keys={len(res)}")

# ---- 叶子路径枚举 ----
leaves = []


def walk(obj, path):
    if isinstance(obj, dict):
        if not obj:
            leaves.append((path, "{}"))
            return
        for k, v in obj.items():
            walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        if not obj:
            leaves.append((path, "[]"))
            return
        for i, v in enumerate(obj[:3]):
            walk(v, f"{path}[{i}]")
        if len(obj) > 3:
            leaves.append((f"{path}[…{len(obj)}]", ""))
    else:
        leaves.append((path, repr(obj)[:40]))


walk(res, "")

# ---- 逐条查：字段名在 md 里出现过吗 ----
miss = []
for path, val in leaves:
    key = path.split(".")[-1].split("[")[0]
    if key and key in md:
        continue
    miss.append((path, val))

print(f"\n[leaves] 共 {len(leaves)} 条叶子路径，其中 {len(miss)} 条的**字段名在 md 里找不到**")
print("（注意：名字找不到 ≠ 一定没渲染 —— 有些字段是用派生文本渲染的，需人工过一遍）\n")
for p, v in miss[:120]:
    print(f"  · {p}  =  {v}")

# ---- 顶层键逐个查 ----
print("\n[top-level] 顶层键是否在 md 出现：")
for k in res:
    print(f"  {'✓' if k in md else '·'} {k}")
