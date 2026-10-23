# -*- coding: utf-8 -*-
"""v1.23.58 开发期验证：晋升门槛 `_eff_n` 与 shadow 拦截原因**真出口**。

判据（纯函数，零成本）：
  A 自适应 + 小库 ⇒ `eff_n` 从 3 降到 1，且 trace 里写着它
  B 不自适应 ⇒ `eff_n == promote_n`（3），逐字不变
  C 五类 verdict 各命中一条（n_short / contra / quality_down / cost_only / promoted）
  D 不传 trace ⇒ 行为与旧版**逐字相同**（返回值一样、条目状态一样）
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("p58_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


new = load(HERE / "元DGTF-V1.23.58.py")


def mkpb():
    """5 条 shadow，各卡在不同闸上（顺序与判定顺序一致）。"""
    return [
        {"id": "S1", "status": "shadow", "n_evidence": 0},                      # n_short
        {"id": "S2", "status": "shadow", "n_evidence": 5, "contra": 3},         # contra
        {"id": "S3", "status": "shadow", "n_evidence": 5, "quality_delta": -0.2},  # quality_down
        {"id": "S4", "status": "shadow", "n_evidence": 5,
         "quality_delta": 0.0, "cost_delta": -1.0},                             # cost_only
        {"id": "S5", "status": "shadow", "n_evidence": 4, "quality_delta": 0.1},  # promoted
    ]


print("=" * 62)
print("【A】自适应 + 小库 ⇒ eff_n 降到 1（且 trace 写着）")
pb = mkpb()
tr = {}
ch = new.eml_promote(pb, promote_n=3, adaptive=True, trace=tr)
ck(tr.get("eff_n") == 1, "eff_n=%r（期望 1：库 5 < 冷启 %r）"
   % (tr.get("eff_n"), tr.get("cold_lib")))
ck(tr.get("promote_n") == 3 and tr.get("adaptive") is True,
   "promote_n=%r / adaptive=%r" % (tr.get("promote_n"), tr.get("adaptive")))

print("\n【B】不自适应 ⇒ eff_n == promote_n（逐字不变）")
pb2 = mkpb()
tr2 = {}
new.eml_promote(pb2, promote_n=3, adaptive=False, trace=tr2)
ck(tr2.get("eff_n") == 3, "eff_n=%r（期望 3）" % (tr2.get("eff_n"),))
ck(tr2.get("shadow_verdicts", {}).get("n_short") == 1,
   "不自适应时 S1 仍卡 n_short（%r）" % (tr2.get("shadow_verdicts"),))

print("\n【C】五类 verdict 各命中一条")
vd = tr.get("shadow_verdicts") or {}
for k, want in (("n_short", 1), ("contra", 1), ("quality_down", 1),
                ("cost_only", 1), ("promoted", 1)):
    ck(vd.get(k) == want, "%-14s = %r（期望 %d）" % (k, vd.get(k), want))
_verdicts = {r["id"]: r["verdict"] for r in (tr.get("shadow") or [])}
ck(_verdicts == {"S1": "n_short", "S2": "contra", "S3": "quality_down",
                 "S4": "cost_only", "S5": "promoted"},
   "逐条 verdict 全对：%r" % (_verdicts,))
ck([x.get("id") for x in ch] == ["S4", "S5"],
   "变更列表只有 S4(blocked_cost_only)/S5(active)：%r" % (ch,))
ck([e["status"] for e in pb] == ["shadow", "shadow", "shadow", "shadow", "active"],
   "只有 S5 真变成 active")
ck(tr.get("n_lib") == 5, "n_lib=%r" % (tr.get("n_lib"),))

print("\n【D】不传 trace ⇒ 与旧版逐字相同")
old = load(HERE / "元DGTF-V1.23.57.py")
pa, pb3 = mkpb(), mkpb()
ca = new.eml_promote(pa, promote_n=3, adaptive=True)
cb = old.eml_promote(pb3, promote_n=3, adaptive=True)
ck(ca == cb, "返回值逐字相同：%r vs %r" % (ca, cb))
ck(pa == pb3, "条目状态逐字相同（含 weight）：%r" % ([e.get("weight") for e in pa],))

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
