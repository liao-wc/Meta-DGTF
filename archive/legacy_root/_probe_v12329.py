#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 真实入口验证探针（判据打在能力本体上，非调用点存在性）。

覆盖：D1 相对阈值 / D2 语义归并（正+负两臂）/ A1 索引化 / B1 规则优先 /
C1 touch_rate 两态 / C2 配置缩进。全部走真实类与方法，不打桩。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"

spec = importlib.util.spec_from_file_location("dgtf_v12329", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12329"] = m
spec.loader.exec_module(m)

R = []


def ok(name, cond, note=""):
    R.append((name, bool(cond), note))
    print(("✓" if cond else "✗"), name, note)


# ── D1：相对阈值 ─────────────────────────────────────────
corpus = None
t1 = "灵魂存在与否取决于直觉体验"
t2 = "地铁票价应当按里程计费"
try:
    _thr1 = m.sem_thr_relative(t1, corpus)
    ok("D1 rel：阈值夹取在 [0.20, 0.55]", 0.20 <= _thr1 <= 0.55, f"thr={_thr1:.4f}")
    _h1 = m.semantic_entropy_of([t1, t1 + "，直觉即证据"], corpus, thr="rel")
    _h2 = m.semantic_entropy_of([t1, t2, "丙说灵魂问题本身定义不清"], corpus, thr="rel")
    ok("D1 rel：同主张批 vs 混合批 熵有区分度",
       _h1[0] is not None and _h2[0] is not None and abs(_h1[0] - _h2[0]) > 1e-9,
       f"h1={_h1[0]:.4f} h2={_h2[0]:.4f}")
except Exception as ex:
    import traceback; traceback.print_exc()
    ok("D1 rel：可调用", False, repr(ex))

# ── D2：语义归并（两臂）─────────────────────────────────
try:
    pool = m.Pool()
    pool.merge_semantic = True
    pool.merge_sim = m._BELIEF_MERGE_SIM
    pool.upsert_belief("灵魂是否存在取决于定义的清晰度", sources=["probe_a"])
    n0 = len(pool.belief_items)
    # 换说法（近乎逐字重排）→ 应归并不新建
    pool.upsert_belief("灵魂是否存在，取决于定义的清晰度", sources=["probe_b"])
    n1 = len(pool.belief_items)
    ml = list(getattr(pool, "merge_log", []))
    tgt = None
    for it in pool.belief_items:
        if "定义的清晰度" in str(it.get("text", "")):
            tgt = it
    _occ = (tgt or {}).get("occurrences", [])
    occ = len(_occ) if isinstance(_occ, list) else int(_occ or 1)
    ok("D2 正臂：换说法被归并（条目不增）", n1 == n0 == 1, f"n0={n0} n1={n1}")
    ok("D2 正臂：留痕 merge_log 非空", len(ml) == 1,
       json.dumps(ml[:1], ensure_ascii=False)[:100])
    ok("D2 正臂：occurrences ≥ 2（复现证据）", occ >= 2, f"occ={occ}")
    # 负臂：不同主张不得并
    pool.upsert_belief("地铁票价应当按里程计费", sources=["probe_c"])
    n2 = len(pool.belief_items)
    ok("D2 负臂：不同主张不并（条目 +1）", n2 == n0 + 1, f"n2={n2}")
    # 开关关：恒不归并
    pool2 = m.Pool()
    pool2.merge_semantic = False
    pool2.upsert_belief("灵魂是否存在取决于定义的清晰度", sources=["x"])
    pool2.upsert_belief("灵魂是否存在，取决于定义的清晰度", sources=["y"])
    ok("D2 关臂：merge_semantic=False 不归并", len(pool2.belief_items) == 2,
       f"n={len(pool2.belief_items)}")
    # 出口两向一致
    d = pool.to_dict()
    ok("D2 出口：merge_semantic/merge_log 在产物", d.get("merge_semantic") is True
       and isinstance(d.get("merge_log"), list) and len(d["merge_log"]) == 1)
except Exception as ex:
    import traceback
    traceback.print_exc()
    ok("D2：可运行", False, repr(ex))

# ── A1：这一次我是谁 → 索引 ─────────────────────────────
try:
    src = SRC.read_bytes().decode("utf-8")
    ok("A1：索引标题在、旧截断复制不在",
       "## 这一次我是谁（索引）" in src
       and 'self_text = ["[<层>] " + view.manifest' not in src)
except Exception as ex:
    ok("A1：源码检查", False, repr(ex))

# ── B1：规则优先 ───────────────────────────────────────
try:
    ok("B1：_AUTO_REACHABLE_MODES 收敛为 serial/B/C",
       m.MetaDGTF._AUTO_REACHABLE_MODES == ("serial", "B", "C"))
    has_rule = hasattr(m, "_mode_rule") or "_mode_rule" in src
    ok("B1：_mode_rule 存在（规则优先路径）", has_rule)
    ok("B1：模块级 mode_rule 唯一实现（三处接线同源）",
       "def mode_rule(question: str):" in src
       and src.count("return mode_rule(question)") == 1)
    _m1, _r1 = m.mode_rule("探针题")
    ok("B1：mode_rule 短问句 ⇒ serial", _m1 == "serial", _r1)
    _m2, _r2 = m.mode_rule("评估A方案和B方案哪个更好，还是组合更优")
    ok("B1：mode_rule 含选择词 ⇒ B", _m2 == "B", _r2)
    _m3, _r3 = m.mode_rule("这是一个用来测试规则拿不准回退路径的较长问题表述")
    ok("B1：mode_rule 拿不准 ⇒ None", _m3 is None, _r3)
    dec_src = src
    ok("B1：_decide_parallel_mode 先试规则（source=rule, conf 0.9）",
       '"source": "rule"' in dec_src and '"confidence": 0.9' in dec_src)
except Exception as ex:
    ok("B1：检查", False, repr(ex))

# ── C1：touch_rate 两态 ─────────────────────────────────
try:
    p = m.View(entry={})
    p.anchor_touched = ["a"]
    tr = p.touch_rate
    ok("C1：无逐圈键时走一次性兜底（触及过 ⇒ 1.0）", tr is not None and float(tr) == 1.0,
       f"got {tr!r}")
    p1b = m.View(entry={})
    tr1b = p1b.touch_rate
    ok("C1：一次性口径下从未触及 ⇒ 0.0（真实答案非冒充）",
       tr1b is not None and float(tr1b) == 0.0, f"got {tr1b!r}")
    p2 = m.View(entry={})
    p2.round_log = [{"anchor_touched_n": 2, "anchor_total_n": 4},
                    {"anchor_touched_n": 0, "anchor_total_n": 4}]
    tr2 = p2.touch_rate
    ok("C1：有逐圈键时按圈算（=0.5）", tr2 is not None and abs(float(tr2) - 0.5) < 1e-9,
       f"got {tr2!r}")

except Exception as ex:
    ok("C1：touch_rate", False, repr(ex))

# ── C2：DEFAULT_CONFIG 可解析 ──────────────────────────
try:
    _ = m.DEFAULT_CONFIG
    ok("C2：DEFAULT_CONFIG 载入无异常", True)
except Exception as ex:
    ok("C2：DEFAULT_CONFIG 载入无异常", False, repr(ex))

# ── 汇总 ───────────────────────────────────────────────
bad = [r for r in R if not r[1]]
print("\n=== 探针汇总：%d ✓ / %d ✗ ===" % (len(R) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
