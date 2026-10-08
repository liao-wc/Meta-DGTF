#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[G] 反事实对照：把**真产物里的真实 touched/untouched** 分别喂给 v69 码与 v70
码的同一个纯函数（`DGTF._re_anchor` 的 `_clean` 段），看这一跑到底用没用到修复，
并证明"没触发的跑是零影响"。

★ 判活要按数据走：V70 那一跑锚点侧本来就没吐占位符 ⇒ 对它是**可证明的无操作**；
  真正被 G 影响的证据只能来自 V68 那份真产物（它记着 desc="此处未生"）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACE = {"此处未生", "（此处未生）", "(此处未生)", "无", "（无）", "(无)",
         "暂无", "未知", "n/a", "N/A"}


def _load(fn, name):
    spec = importlib.util.spec_from_file_location(name, str(HERE / fn))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


M = {"v69": _load("元DGTF-V1.21.69.py", "d69"),
     "v70": _load("元DGTF-V1.21.70.py", "d70")}


class _Stub:
    def __init__(self, payload):
        self.payload = payload

    def call(self, *a, **k):
        return json.dumps(self.payload, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def run(ver, payload):
    mod = M[ver]
    cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    cfg["api"]["key"] = "sk-probe"
    cfg["output"]["verbose"] = False
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = False
    dg.llm = _Stub(payload)
    inp = mod.Input(question="原始问题", round_role="摊开", round_no=1)
    inp.pool = mod.Pool()
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return dg._re_anchor(inp)


print("=" * 70)
print("## 案例来源：各真跑产物里**真实存在**的 touched / untouched")
print("=" * 70)
cases = {}
for tag in ("V68", "V69", "V70"):
    p = HERE / f"verif_{tag}.full.json"
    if not p.exists():
        print(f"  （{tag} 无 full.json，跳过）")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    for e in ("0", "1"):
        vv = (d.get("views") or {}).get(e) or {}
        tou = [str(x.get("desc", "")) for x in (vv.get("anchor_touched") or [])]
        unt = [str(x.get("desc", "")) for x in (vv.get("untouched") or [])]
        if not tou and not unt:
            continue
        cases[f"{tag}/view{e}"] = {"anchor": "（真产物锚点）",
                                   "touched": tou, "untouched": unt}

rows = []
for name, payload in cases.items():
    out = {}
    for ver in ("v69", "v70"):
        try:
            _a, t, u = run(ver, payload)
        except Exception as ex:
            t, u = [f"EXC {type(ex).__name__}"], []
        out[ver] = (t, u)
    raw_t = payload["touched"]
    raw_u = payload["untouched"]
    rows.append((name, raw_t, raw_u, out))

print(f"\n{'案例':<14}{'原始条目':>8}{'v69 输出':>8}{'v70 输出':>8}   说明 / 差异条目")
for name, raw_t, raw_u, out in rows:
    n_raw = len(raw_t) + len(raw_u)
    t69 = list(out["v69"][0]) + list(out["v69"][1])
    t70 = list(out["v70"][0]) + list(out["v70"][1])
    gone = [x for x in t69 if x not in t70]
    if not gone:
        note = "零影响（这批数据里没有占位符）"
    elif len(gone) == len(t69) - len(t70) or True:
        note = f"★ 挡掉 {gone}（计数因 [：n] 截断可能不变，**内容**变了）"
    print(f"{name:<14}{n_raw:>8}{len(t69):>8}{len(t70):>8}   {note}")

print("\n被 v70 挡掉的具体条目：")
any_hit = False
for name, raw_t, raw_u, out in rows:
    t69 = list(out["v69"][0]) + list(out["v69"][1])
    t70 = list(out["v70"][0]) + list(out["v70"][1])
    gone = [x for x in t69 if x not in t70]
    if gone:
        any_hit = True
        print(f"   {name}: {gone}")
if not any_hit:
    print("   （本轮三份产物里都没有占位符 ⇒ G 对它们是可证明的无操作）")

print("\n" + "=" * 70)
print("## 对照：把占位符**塞进**同一份真数据（V68 那条）")
print("=" * 70)
if "V68/view0" in cases:
    p = dict(cases["V68/view0"])
    print("   V68/view0 的真实 untouched[0] =", repr(p["untouched"][0]))
    for ver in ("v69", "v70"):
        _a, t, u = run(ver, p)
        bad = [x for x in (t + u)
               if x in PLACE or x.replace("（", "(").replace("）", ")") in PLACE]
        print(f"   {ver}: 输出 {len(t) + len(u)} 条，其中占位符 {len(bad)} 条 {bad}")
