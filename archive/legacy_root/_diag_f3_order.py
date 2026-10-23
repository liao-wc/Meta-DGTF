# -*- coding: utf-8 -*-
"""F3 时序修正的**构造性验证**：直接驱动真实入口，断言论产出。

★ 为什么必须这样验：这一条的失败形态恰恰是「纯函数/静态判据全绿、
  真实入口恒空」。所以这里**不测 F3 的匹配逻辑（那是纯函数）**，
  而是跑 `_apply_view_to_pool_locked` 本身，断言
  `view.belief_items` **在调用返回后非空**。

驱动方式：不跑整条引擎（贵），而是
  ① `object.__new__(MetaDGTF)` 绕过 __init__（学 `_probe_v1234_runtime` 的 T5）
  ② 造一个含 `_und_prod` 触发条件的 view + 空池
  ③ 调 `_apply_view_to_pool_locked` → 断言 view.belief_items 非空
"""
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.28.py"

spec = importlib.util.spec_from_file_location("modx", str(SRC))
mod = importlib.util.module_from_spec(spec)
sys.modules["modx"] = mod
spec.loader.exec_module(mod)

ok = True


def chk(name, cond, detail=""):
    global ok
    mark = "OK " if cond else "NG "
    if not cond:
        ok = False
    print("  %s %s  %s" % (mark, name, detail))


meta = object.__new__(mod.MetaDGTF)
meta.config = {
    "sim": {},
    "belief": {"revoke_sources": 2, "sem_entropy_thr": 0.30},
    "thinking": {"default": "disabled"},
}
# ★ 夹具补齐：`_apply_view_to_pool_locked` 会读这些属性（学
#   `_probe_v1234_runtime.py` 的 T5 做法，逐个显式给初值）。
meta.decidability_result = None
meta._anchor_report = None
meta._ext_assess_cache = {}

pool = mod.Pool()
view = mod.View(entry="0")

# 造「本圈看到了什么」：amp 的 desc 就是随后会被 upsert 进池的主张文本
_TEXT_A = "介质只保存可区分的物理状态，不保存这是四态字段这句话"
_TEXT_B = "解码失败状态必须作为持久化判定结果存在否则读写错位"
view.amps = [{"type": "&", "desc": _TEXT_A}, {"type": "&", "desc": _TEXT_B}]
view.anchor_touched = []

# 造 add_undecidable 的输入：upsert 读的是 product["structural_amps"]
view.undecidable_product = {
    "question": "验证",
    "structural_amps": [_TEXT_A, _TEXT_B],
    "clarity": 0.4,
    "_layer_name": "0",
    "_round_no": 1,
}
view.suspensions = [{"target": _TEXT_A, "reason": "证据不足", "status": "active"}]

print("=== 调用前 ===")
print("  pool.belief_items n=%d" % len(pool.belief_items))
print("  view.belief_items n=%d" % len(view.belief_items))

# 真实入口
meta._apply_view_to_pool_locked(view, pool, "entry-x", layer=1)

print("=== 调用后 ===")
print("  pool.belief_items n=%d" % len(pool.belief_items))
print("  view.belief_items n=%d" % len(view.belief_items))
for x in (view.belief_items or []):
    print("      * %s | occ_n=%s | H=%s"
          % (repr(str(x.get("text"))[:34]), x.get("occurrence_n"),
             x.get("semantic_entropy")))

chk("P1 池里确实产出了信念条目（前置条件）",
    len(pool.belief_items) >= 1, "pool n=%d" % len(pool.belief_items))
chk("P2 ★ view.belief_items 在**真实入口**下非空（时序修正生效）",
    len(view.belief_items) >= 1, "view n=%d" % len(view.belief_items))
chk("P3 回填的是**与 view 相关**的条目（text 命中 amps.desc）",
    all(str(x.get("text", "")).strip() in
        {str(a.get("desc", "")).strip() for a in view.amps}
        for x in (view.belief_items or [])),
    repr([str(x.get("text"))[:20] for x in (view.belief_items or [])]))

# ---- 负对照①：逻辑本身没被削（匹配不到时仍须保持空）----
view2 = mod.View(entry="0")
view2.amps = [{"type": "&", "desc": "与池内任何条目都无关的一句话XYZQ"}]
view2.undecidable_product = {
    "question": "无关", "structural_amps": ["另有一条无关主张PQRS"],
    "clarity": 0.2, "_layer_name": "0", "_round_no": 2,
}
meta._apply_view_to_pool_locked(view2, pool, "entry-y", layer=1)
chk("N1 负对照：text 对不上时必须保持 []（不猜、不倒全池）",
    len(view2.belief_items) == 0, "view2 n=%d" % len(view2.belief_items))

print()
print("=== RESULT: %s ===" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
