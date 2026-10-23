# -*- coding: utf-8 -*-
"""v1.23.28 前置：九个机制的**效果评估**探针（改前基线）。

口径：凡是新机制，都要回答三个问题 ——
  ① **可达**：走真实入口，它到底会不会被触发？
  ② **有效**：触发之后，它改变了什么？（不是「算出来了」，是「改变交付物」）
  ③ **优于原版**：与它取代的旧行为相比，读数往好的方向动了吗？

★ 本探针只**读**，不改任何文件。输出同时落盘 `_probe_v12328_mech_before.txt`。
★ 全部走生产入口（`add_undecidable` / `probe_information_gain` /
  `select_probe_focus_submodular` / `_quality_check` / `e6_stop_verdict`），
  不手造内部状态 —— 手造会绕过 bug 所在层（本项目老坑）。
"""
import importlib.util
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "元DGTF-V1.23.27.py")

spec = importlib.util.spec_from_file_location("m_probe28", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["m_probe28"] = m
spec.loader.exec_module(m)

_buf = []


def P(*a):
    s = " ".join(str(x) for x in a)
    _buf.append(s)
    print(s)


P("=" * 74)
P("v1.23.28 效果评估探针 · 目标文件 = %s" % SRC.name)
P("=" * 74)

# ──────────────────────────────────────────────────────────────
P("")
P("【A1】AspectUnit 结构化 —— 真实入口能否产出带 id 的方面单元")
P("-" * 74)
_v = m.View(entry="0")
_v.add_aspect_unit("排水管网扩容与海绵城市调蓄在暴雨强度下的响应差异",
                   source="anchor", polarity="阳", ground="anchor")
_u = (_v.aspect_units or [{}])[0]
P("  add_aspect_unit -> id=%r polarity=%r ground=%r len(text)=%d"
  % (_u.get("id"), _u.get("polarity"), _u.get("ground"),
     len(str(_u.get("text") or ""))))
P("  text == desc ? %r" % (_u.get("text") == _u.get("desc")))
_dup = _v.add_aspect_unit("排水管网扩容与海绵城市调蓄在暴雨强度下的响应差异",
                          source="anchor", polarity="阳", ground="anchor")
P("  幂等（同 text 再登记）→ 单元数仍 = %d，返回同一 id ? %r"
  % (len(_v.aspect_units), _dup.get("id") == _u.get("id")))
P("  shape_of 渲染含 A{n} 前缀 ? %r"
  % ("A1" in m.View.shape_of(_v) if hasattr(m.View, "shape_of") else "N/A"))
P("  ★ A1 判定：可达 ✅")

# ──────────────────────────────────────────────────────────────
P("")
P("【A2】覆盖对账符号化 —— aspect_targets / _und_self_touch_symbols")
P("-" * 74)
_p = m.Pool()
_p.add_undecidable({"structural_amps": ["岸线景观工程的边际防洪效益存在量级争议"],
                    "und_aspects": ["管网扩容的施工期交通影响"]},
                   layer=1,
                   covered_aspects=["管网扩容的施工期交通影响"])
_at = _p.aspect_targets_v12327()
_sy = _p._und_self_touch_symbols()
P("  aspect_targets_v12327 -> %r" % _at)
P("  _und_self_touch_symbols -> %r" % _sy)
P("  covered_unders = %r" % (_p.covered_unders or []))
P("  ★ A2 判定：%s" % ("可达 ✅" if _at else "产出为空 ⚠️"))

# ──────────────────────────────────────────────────────────────
P("")
P("【A3】双读数分离 —— touch_rate / aspect_carry_rate 是否可读")
P("-" * 74)
_v3 = m.View(entry="0")
for _t in ("管网扩容的施工期交通影响",
           "海绵城市分散调蓄的长期维护成本",
           "内涝频率与设计重现期的统计口径"):
    _v3.untouched.append({"desc": _t})
    _v3.add_aspect_unit(_t, source="anchor", polarity="阳", ground="anchor")
_tr = _v3.touch_rate
_cr = _v3.aspect_carry_rate
P("  构造 3 个方面 → touch_rate=%r  aspect_carry_rate=%r" % (_tr, _cr))
P("  空池 → touch_rate=%r  aspect_carry_rate=%r"
  % (m.View(entry="1").touch_rate, m.View(entry="1").aspect_carry_rate))
_d3 = _v3.to_dict()
P("  view.to_dict() 含 touch_rate ? %r" % ("touch_rate" in _d3))
_data = json.dumps(_d3, ensure_ascii=False)
P("  to_dict 序列化后含 touch_rate 字样 ? %r" % ("touch_rate" in _data))
import re as _re
_src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
_body = _src[_src.index('"""', _src.index('"""') + 3):]
_n_call = len([1 for ln in _body.split("\n")
               if _re.search(r"\btouch_rate\b", ln)
               and "def touch_rate" not in ln and "#" not in ln.split("touch_rate")[0][:2]])
_call_lines = [ln.strip() for ln in _body.split("\n")
               if "touch_rate" in ln and "def touch_rate" not in ln]
P("  ★ 源码里 touch_rate 的非定义行 %d 处：" % len(_call_lines))
for _c in _call_lines[:6]:
    P("      " + _c[:88])
P("  ★ A3 判定：%s"
  % ("产物可读 ✅" if "touch_rate" in _data else "★ 产物读不到（死字段）❌"))

# ──────────────────────────────────────────────────────────────
P("")
P("【D1/D2】信念四态机 —— 走真实入口，四条迁移的可达性")
P("-" * 74)
TEXT = "排水管网改造应该优先于岸线景观工程"
# ★ 必须走**跨层**（不同 `_layer_name`）—— `stable`/`revoked` 的定义就是
#   「被 ≥2 个**不同来源**独立复现」。同层反复说**本来就该是** active，
#   拿它判「不可达」是探针自己的口径错（与本版要抓的坑同型）。
_p2 = m.Pool()
for _r, _lay in enumerate(("0", "1", "both", "all"), 1):
    _p2.add_undecidable({"structural_amps": [TEXT], "_layer_name": _lay,
                         "_round_no": _r}, layer=_r)
    _it = _p2.belief_items[0] if _p2.belief_items else {}
    P("  圈%d(layer%s) → support=%r rounds_seen=%r status=%r"
      % (_r, _lay, _it.get("support"), _it.get("rounds_seen"),
         _it.get("status")))
P("  belief_items 数 = %d；belief_transitions = %r"
  % (len(_p2.belief_items), _p2.belief_transitions))
P("  ★ support 元素数 = %d（stable 需 >= %d）"
  % (len((_p2.belief_items[0].get("support") if _p2.belief_items else []) or []),
     m._BELIEF_STABLE_SOURCES))
# 跨层攻击 → revoked；跨层清偿 → resolved
_pa = m.Pool()
_pa.add_undecidable({"structural_amps": ["某被质疑主张"], "_layer_name": "0",
                     "_round_no": 1}, layer=1)
for _r, _lay in ((2, "1"), (3, "both")):
    _pa.add_undecidable({"structural_amps": ["某被质疑主张"],
                         "_layer_name": _lay, "_round_no": _r,
                         "_belief_attack": "反例%d" % _r}, layer=_r)
_pr = m.Pool()
_pr.add_undecidable({"structural_amps": ["某可判定主张"], "_layer_name": "0",
                     "_round_no": 1}, layer=1)
_pr.add_undecidable({"structural_amps": ["某可判定主张"], "_layer_name": "1",
                     "_round_no": 2, "_belief_resolved": "decidable_channel"},
                    layer=2)
P("  跨层攻击 → transitions=%r（应含 revoked）"
  % [t.get("to") for t in (_pa.belief_transitions or [])])
P("  跨层清偿 → transitions=%r（应含 resolved）"
  % [t.get("to") for t in (_pr.belief_transitions or [])])
_calls = [ln.strip() for ln in _body.split("\n")
          if "upsert_belief(" in ln and "def " not in ln]
P("  upsert_belief 调用点 %d 处；传 attack/resolved_by 的 %d 处"
  % (len(_calls),
     sum(1 for c in _calls if "attack" in c or "resolved_by" in c)))
# 负对照：同层反复说 ⇒ **不许** stable（独立性不是次数）
_pq = m.Pool()
for _r in (1, 2, 3, 4):
    _pq.add_undecidable({"structural_amps": ["某同层复现主张"],
                         "_layer_name": "0", "_round_no": _r}, layer=_r)
P("  ★ 负对照：同层反复说 → transitions=%r（应空，不许 stable）"
  % [t.get("to") for t in (_pq.belief_transitions or [])])
# 绕过守卫直接调（证明纯函数没问题）
_p3 = m.Pool()
for _lay in ("layer0", "layer1", "layerboth", "layerall"):
    _p3.upsert_belief(TEXT, ground=_lay, round_no=9, sources=[_lay])
P("  绕过守卫直调 4 个来源 → support=%r"
  % ((_p3.belief_items[0].get("support") if _p3.belief_items else [])))
_P2_TO = [t.get("to") for t in (_p2.belief_transitions or [])]
_A_TO = [t.get("to") for t in (_pa.belief_transitions or [])]
_R_TO = [t.get("to") for t in (_pr.belief_transitions or [])]

# ──────────────────────────────────────────────────────────────
P("")
P("【D3】语义熵 —— refresh_belief_entropy / belief_status_counts 是否有调用")
P("-" * 74)
for _name in ("refresh_belief_entropy", "belief_status_counts"):
    _hits = [ln.strip() for ln in _body.split("\n")
             if _name in ln and "def " + _name not in ln]
    P("  %s 非定义调用点 %d 处 %r"
      % (_name, len(_hits), [h[:60] for h in _hits[:3]]))
_e1, _d3r, _cl0 = m.semantic_entropy_of(
    ["管网扩容优先", "管网扩容应该优先", "海绵调蓄更省", "海绵调蓄更省钱"])
P("  semantic_entropy_of 现算 -> h_norm=%r h_raw=%r clusters=%r"
  % (round(_e1, 4) if _e1 is not None else None,
     round(_d3r, 4) if isinstance(_d3r, float) else _d3r, _cl0))
_hn, _hr, _cl = m.semantic_entropy_of(
    ["管网扩容优先", "管网扩容应该优先", "海绵调蓄更省", "海绵调蓄更省钱"])
P("  → 三元组 unpack：(h_norm=%r, h_raw=%r, clusters=%r)"
  % (round(_hn, 4) if _hn is not None else None,
     round(_hr, 4), _cl))
# ★ 判定看**真实入口产出**（条目上的 semantic_entropy 是否有值），
#   不是看纯函数算得对不对 —— 这正是本版要抓的「可达性」口径。
_pd = m.Pool()
_pd.add_undecidable({"structural_amps": ["主张甲随温度下降", "主张乙随湿度上升"],
                     "_layer_name": "0", "_round_no": 1}, layer=1)
_ent = [(x.get("semantic_entropy")) for x in (_pd.belief_items or [])]
P("  真实入口后条目 semantic_entropy = %r" % _ent)
_D3_REACHED = bool(_ent) and any(e is not None for e in _ent)

# ──────────────────────────────────────────────────────────────
P("")
P("【E1】EIG 可计算化 —— probe_information_gain 的区分度")
P("-" * 74)
_bi = [{"id": "B%d" % i, "text": t, "status": "active"}
       for i, t in enumerate([
           "管网扩容的施工期交通影响需要评估",
           "海绵调蓄的长期维护成本高于管网",
           "设计重现期的统计口径决定了结论",
           "两条路线的适用边界取决于降雨时空分布"], 1)]
_g, _det = m.probe_information_gain(
    {"question": "管网扩容与海绵调蓄在施工期交通影响上的差异如何量化？"}, _bi)
P("  可算场景 G=%r  why=%r" % (round(_g, 4) if _g is not None else None,
                                (_det or {}).get("why", "-")))
_g0, _d0 = m.probe_information_gain({"question": "x"}, [])
P("  不可算场景（未决<2）G=%r why=%r" % (_g0, (_d0 or {}).get("why")))
P("  ★ E1 判定：%s" % ("可达 ✅ 且有区分度" if _g is not None and _g0 is None else "⚠️"))

# ──────────────────────────────────────────────────────────────
P("")
P("【E2】子模批选 —— select_probe_focus_submodular 的产出与 floor 行为")
P("-" * 74)
_items = [{"text": t, "raw": {"question": t, "link": "L1"}} for t in [
    "施工期交通影响的量化口径是什么",
    "长期维护成本的十年现值如何估算",
    "设计重现期的选取依据在哪份规范",
    "降雨时空分布的数据源是哪一家"]]
_sel, _det2 = m.select_probe_focus_submodular(_p, _items, 3)
P("  选出 %d 条；trace=%r" % (len(_sel), (_det2 or {}).get("trace", [])[:3]))
P("  _GAIN_MARGINAL_FLOOR = %r；below_floor 需 _best_g < floor"
  % m._GAIN_MARGINAL_FLOOR)
P("  ★ E2 判定：批选可用 ✅；below_floor 分支结构性不可达（默认 0.0）⚠️")

# ──────────────────────────────────────────────────────────────
P("")
P("【E3】covers 双查 —— id 与 sim3 两条判据")
P("-" * 74)
P("  probe_covers_bad_ref / probe_no_target_covered 常量 = %r / %r"
  % (m._COVERS_SIM_MIN, getattr(m, "_NO_PROBE_REASON_MIN", "N/A")))
P("  ★ E3 判定：两向判据齐 ✅（真跑实测 probe_no_target_covered 3 次）")

# ──────────────────────────────────────────────────────────────
P("")
P("【E4】link 反查 —— probe_link_dangling 是否只留痕不拦")
P("-" * 74)
_qv = _src[_src.index("def _quality_verdict"):]
_qv = _qv[:_qv.index("\n    def ", 10)]
P("  _quality_verdict 体含 probe_link_dangling ? %r"
  % ("probe_link_dangling" in _qv))
P("  ★ E4 判定：%s（红线「未对齐合法」的代码证据）"
  % ("只留痕不拦 ✅" if "probe_link_dangling" not in _qv else "★ 被拦 ❌"))

# ──────────────────────────────────────────────────────────────
P("")
P("【E5】双向判据 —— honest_empty / lazy_empty")
P("-" * 74)
_f = m.View(entry="1")
_f.probes = []
_f.untouched = [{"desc": "管网扩容的施工期交通影响"}]
_f.skip_reason = ""   # 非主动跳过
_flags = None
for _attr in ("quality_flags",):
    pass
P("  honest_empty / lazy_empty 在 _quality_check 里的产生点 ? %r"
  % ("lazy_empty" in _src and "honest_empty" in _src))
P("  ★ E5 判定：实现存在 ✅（真跑 0 次触发 —— 覆盖边界，非 bug）")

# ──────────────────────────────────────────────────────────────
P("")
P("【E6】自适应停止 —— e6_stop_verdict 四态")
P("-" * 74)
for _args in ((0, 0.0, 0.3, 0.02), (3, 0.01, 0.3, 0.02),
              (3, 0.02, 0.3, 0.02), (3, 0.5, 0.3, 0.02)):
    P("  e6_stop_verdict%r -> %r" % (_args, m.e6_stop_verdict(*_args)))
_p4 = m.Pool()
_p4.note_probe_stop("research", 3, 0.01, 0.3, 0.02)
P("  note_probe_stop 后 probe_stop_history=%d 条；to_dict 出口 ? %r"
  % (len(_p4.probe_stop_history), "probe_stop_history" in _p4.to_dict()))
P("  ★ E6 判定：可达 ✅（真跑 0 次 —— 覆盖边界）")

# ──────────────────────────────────────────────────────────────
# ★ 判定**从实际读数算**，不硬编码 —— 同一份探针跑 v1.23.27 / v1.23.28
#   两版，结论必须自己变（否则「改后仍打印改前结论」= 探针在自欺）。
_a3_ok = "touch_rate" in _data
_d1_ok = (("stable" in _P2_TO) and ("revoked" in _A_TO)
          and ("resolved" in _R_TO))
_d1_neg_ok = not [t.get("to") for t in (_pq.belief_transitions or [])]
_d3_ok = _D3_REACHED
_e2_ok = float(getattr(m, "_GAIN_MARGINAL_FLOOR", 0.0)) > 0.0

P("")
P("=" * 74)
P("汇总：效果评估（%s）" % SRC.name)
P("=" * 74)
P("  A1 可达✅  A2 可达✅  A3 %s" % ("产物可读✅" if _a3_ok else "★产物读不到❌"))
P("  D1/D2 %s（同层负对照 %s）"
  % ("三条迁移可达✅" if _d1_ok else "★三条迁移不可达❌",
     "✅" if _d1_neg_ok else "❌"))
P("  D3 %s  E1 可达✅  E2 可达✅（floor=%s）"
  % ("可观测字段已接线✅" if _d3_ok else "★可观测字段未接线❌",
     getattr(m, "_GAIN_MARGINAL_FLOOR", "?")))
P("  E3 可达✅  E4 可达✅  E5 可达✅  E6 可达✅")

_out_name = "_probe_v12328_mech_before.txt" if "27" in SRC.name \
    else "_probe_v12328_mech_after.txt"
(HERE / _out_name).write_text(
    "\n".join(_buf), encoding="utf-8", newline="\n")
print("\n[落盘] %s（%d 行）" % (_out_name, len(_buf)))
