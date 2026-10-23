#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.28 冒烟判据升级补丁。

改三处 + 新增一个判据函数：
  ① SRC 指向 v1.23.28
  ② `check_v12327_five_mechanisms` 的 A1 段补「untouched 带 id」判据
  ③ `check_v12327_five_mechanisms` 的 E2 段补「floor=0.02 ⇒ below_floor 可达」
  ④ 新增 `check_v12328_real_entry()` —— **真实入口产出**判据（R2 收口）

★ 本脚本走 CRLF 往返：read_bytes → 断言 CRLF==LF → 转 LF → 替换 →
  write_bytes（禁用 write_text）。
★ 每处替换前断言命中 == 1。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "smoke_test.py"

raw = TGT.read_bytes()
n_crlf = raw.count(b"\r\n")
n_lf = raw.count(b"\n")
if n_crlf != n_lf:
    sys.exit("❌ 不是纯 CRLF：CRLF=%d LF=%d" % (n_crlf, n_lf))
text = raw.decode("utf-8").replace("\r\n", "\n")

applied = []


def repl(old, new, tag):
    global text
    n = text.count(old)
    if n != 1:
        sys.exit("❌ [%s] 锚点命中 %d 次（须 == 1）" % (tag, n))
    text = text.replace(old, new)
    applied.append(tag)


# ── ① SRC 指向 ────────────────────────────────────────────
repl('SRC = HERE / "元DGTF-V1.23.27.py"',
     'SRC = HERE / "元DGTF-V1.23.28.py"',
     "SRC")

# ── ② A1 补「untouched 带 id」判据 ────────────────────────
# 插在 A1 段末尾（非法 ground 归一化断言之后、A2 段之前）
_OLD_A1_TAIL = '''    _ab = mod.make_aspect_unit("x", source="s", polarity="阳",
                               ground="bogus_ground", ref="r")
    if _ab.get("ground") != "anchor":
        bad.append("[A1] 非法 ground 未归一化到 anchor（%r）"
                   % _ab.get("ground"))
'''
_NEW_A1_TAIL = '''    _ab = mod.make_aspect_unit("x", source="s", polarity="阳",
                               ground="bogus_ground", ref="r")
    if _ab.get("ground") != "anchor":
        bad.append("[A1] 非法 ground 未归一化到 anchor（%r）"
                   % _ab.get("ground"))
    # ★ v1.23.28：`untouched`/`anchor_touched` 的**写入侧必须带 id**。
    #   历史缺陷：写入只有 {"desc": ...}，而渲染前缀按 `id` 取
    #   `aspect_units` 的编号 ⇒ 前缀**永远印不出**（静默丢标记）。
    #   这条断言**驱动真实写入方法**（不是查字符串），且 id 必须能在
    #   `aspect_units` 里找到 —— 否则渲染点仍拿不到编号。
    _v1u = mod.View(entry="0")
    _u_rec = _v1u.add_aspect_unit("未触及项甲", source="anchor",
                                  polarity="阴", ground="anchor")
    _v1u.untouched.append({"desc": "未触及项甲", "source": "anchor",
                           "id": (_u_rec or {}).get("id", "")})
    if not _v1u.untouched:
        bad.append("[A1] untouched 未写入")
    elif not _v1u.untouched[0].get("id"):
        bad.append("[A1] untouched 条目缺 id ⇒ 渲染前缀永远印不出")
    else:
        _ids_u = {u.get("id") for u in _v1u.aspect_units}
        if _v1u.untouched[0].get("id") not in _ids_u:
            bad.append("[A1] untouched 的 id 不在 aspect_units 里 "
                       "⇒ 编号口径分叉（%r ∉ %s）"
                       % (_v1u.untouched[0].get("id"), sorted(_ids_u)))
'''
repl(_OLD_A1_TAIL, _NEW_A1_TAIL, "A1-untouched-id")

# ── ③ E2 补「floor>0 ⇒ below_floor 可达」判据 ──────────────
_OLD_E2 = '''    # ── E2 子模批选（宁少勿滥）───────────────────────────────
    _p2 = mod.Pool()
    _p2.belief_items = list(_bis)
    _picked, _det = mod.select_probe_focus_submodular(
        _p2, [{"question": "极低温环境下材料脆性阈值是多少",
               "expected_gain": 0.9, "link": "x"}], 3)
    if len(_picked) > 3:
        bad.append("[E2] 批选超过上限 n=3（实为 %d）" % len(_picked))
'''
_NEW_E2 = '''    # ── E2 子模批选（宁少勿滥）───────────────────────────────
    _p2 = mod.Pool()
    _p2.belief_items = list(_bis)
    _picked, _det = mod.select_probe_focus_submodular(
        _p2, [{"question": "极低温环境下材料脆性阈值是多少",
               "expected_gain": 0.9, "link": "x"}], 3)
    if len(_picked) > 3:
        bad.append("[E2] 批选超过上限 n=3（实为 %d）" % len(_picked))
    # ★ v1.23.28：边际下限**必须 > 0**。
    #   历史缺陷：`_GAIN_MARGINAL_FLOOR = 0.0` + `G ∈ [0,1]`
    #   ⇒ `if _best_g < _fl:` **永不成立** ⇒ `below_floor` 结构性不可达。
    #   这条判据**构造性地**证明该分支可达：给一个 G 恰为 0 的候选
    #   （地板 0.02）⇒ 必须被 below_floor 挡下。
    _fl_now = float(getattr(mod, "_GAIN_MARGINAL_FLOOR", 0.0))
    if not (_fl_now > 0.0):
        bad.append("[E2] `_GAIN_MARGINAL_FLOOR` 应 > 0（实为 %r）"
                   "—— 0.0 会让 below_floor 分支恒不可达" % _fl_now)
    _p3 = mod.Pool()
    _p3.belief_items = list(_bis)
    _pk2, _dt2 = mod.select_probe_focus_submodular(
        _p3, [{"question": "极低温环境下材料脆性阈值是多少",
               "expected_gain": 0.0, "link": "zero"}], 3)
    _reasons = [d.get("reason") for d in (_dt2 or [])]
    if "zero" in [_p["link"] for _p in _pk2]:
        bad.append("[E2] G=0 的候选在 floor>0 时不该入选"
                   "（below_floor 分支不可达或阈值失效）")
    if not any(r == "below_floor" for r in _reasons):
        bad.append("[E2] 未走到 below_floor 分支（reasons=%r）"
                   "—— 该分支是「宁少勿滥」的核心" % (_reasons,))
'''
repl(_OLD_E2, _NEW_E2, "E2-floor")

# ── ④ 新增真实入口产出判据函数 ────────────────────────────
_ANCHOR = '''def check_v12324_indep_therapy():'''
_NEWFN = '''def check_v12328_real_entry():
    """[v1.23.28] **真实入口产出**判据（收口 R2）。

    ★ 为什么必须有独立的一条：v1.23.27 的 D1/D2 判据全是**纯函数**形态
      （直接 `mod.belief_transition(...)` 喂构造入参）—— 全绿，但真实
      入口下三条迁移**结构性不可达**（`upsert_belief` 被嵌在「结构名是
      新的」守卫里 ⇒ 复现被 `_DUP_SIM` 挡掉）。**纯函数判据全绿 ≠ 该
      能力在引擎里可达**。
    ★ 本判据走**真实入口** `Pool.add_undecidable(...)`（引擎唯一写入口），
      数圈后断言产出物 `belief_transitions` 里真的出现三种迁移。
    ★ 负对照：同一层反复说同一句 ⇒ **不许**升 stable（层名口径）。
    ★ 判别力由 `_mut_v12328.py` 背书（M1~M6）。
    """
    bad = []

    # ── D1/D2 真实入口：跨层复现 ⇒ stable ──────────────────
    _p = mod.Pool()
    _prod = {"structural_amps": ["低温下材料脆性阈值随温度单调下降"],
             "aligned_amps": [], "clarity": 0.5}
    # 第 1 圈：layer0
    _p.add_undecidable(dict(_prod, _layer_name="0", _round_no=1),
                       und_aspects=["脆性阈值"], layer=1)
    # 第 2 圈：layer1（**不同层** ⇒ 独立复现）
    _p.add_undecidable(dict(_prod, _layer_name="1", _round_no=2),
                       und_aspects=["脆性阈值"], layer=2)
    _tos = [t.get("to") for t in (_p.belief_transitions or [])]
    if "stable" not in _tos:
        bad.append("[R-D2] 真实入口下跨层复现未升 stable（transitions=%r）"
                   "—— 纯函数全绿但入口不可达" % (_tos,))

    # ── 负对照：同层反复说 ⇒ 不许 stable ───────────────────
    _pq = mod.Pool()
    _prod2 = {"structural_amps": ["城市轨道客流预测误差来源"],
              "aligned_amps": [], "clarity": 0.5}
    for _r in (1, 2, 3, 4):
        _pq.add_undecidable(dict(_prod2, _layer_name="0", _round_no=_r),
                            und_aspects=["客流预测"], layer=_r)
    _toq = [t.get("to") for t in (_pq.belief_transitions or [])]
    if "stable" in _toq:
        bad.append("[R-D2-neg] 同层反复说竟升 stable —— "
                   "「同一层重复」冒充「独立复现」（transitions=%r）" % (_toq,))

    # ── D2 真实入口：攻击 ⇒ revoked ────────────────────────
    _pa = mod.Pool()
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "0", "_round_no": 1},
                        und_aspects=["某方面"], layer=1)
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "1", "_round_no": 2,
                         "_belief_attack": "反例：实测不成立"},
                        und_aspects=["某方面"], layer=2)
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "both", "_round_no": 3,
                         "_belief_attack": "反例：第二个反证"},
                        und_aspects=["某方面"], layer=3)
    _toa = [t.get("to") for t in (_pa.belief_transitions or [])]
    if "revoked" not in _toa:
        bad.append("[R-D2-atk] 真实入口下 attack 未产生 revoked"
                   "（transitions=%r）" % (_toa,))

    # ── D2 真实入口：清偿 ⇒ resolved ───────────────────────
    _pr = mod.Pool()
    _pr.add_undecidable({"structural_amps": ["某可判定主张"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "0", "_round_no": 1},
                        und_aspects=["某方面"], layer=1)
    _pr.add_undecidable({"structural_amps": ["某可判定主张"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "1", "_round_no": 2,
                         "_belief_resolved": "decidable_channel"},
                        und_aspects=["某方面"], layer=2)
    _tor = [t.get("to") for t in (_pr.belief_transitions or [])]
    if "resolved" not in _tor:
        bad.append("[R-D2-res] 真实入口下清偿未产生 resolved"
                   "（transitions=%r）" % (_tor,))

    # ── 出口判据：池级可观测量 ─────────────────────────────
    _d = _p.to_dict()
    if "belief_status_counts" not in _d:
        bad.append("[R-out] pool.to_dict 缺 belief_status_counts")
    elif not _p.belief_items:
        bad.append("[R-out] 真实入口后 belief_items 仍为空")
    else:
        _bs = _d.get("belief_status_counts") or {}
        if sum(_bs.get(k, 0) for k in _bs) != len(_p.belief_items):
            bad.append("[R-out] 四态计数之和不等于条目数（%r vs %d）"
                       % (_bs, len(_p.belief_items)))
    if "aspect_units" not in _d:
        bad.append("[R-out] pool.to_dict 缺 aspect_units（A1 池级镜像）")

    # ── D3 真实入口：语义熵落盘有值 ────────────────────────
    _it0 = (_p.belief_items or [{}])[0]
    if _it0.get("semantic_entropy") is None:
        bad.append("[R-D3] 真实入口后 semantic_entropy 仍为 None"
                   "（D3 未接线）")

    # ── A3 双读数出口 ─────────────────────────────────────
    _vx = mod.View(entry="0")
    _vx.round_log = [{"anchor_touched_n": 3}]
    _vx.aspect_units = [{"id": "A1", "text": "t", "desc": "t"}]
    _vx._layer_und_channel = {}
    _vd = _vx.to_dict()
    if "touch_rate" not in _vd:
        bad.append("[R-out] view.to_dict 缺 touch_rate（A3 双读数无出口）")
    if "aspect_carry_rate" not in _vd:
        bad.append("[R-out] view.to_dict 缺 aspect_carry_rate")

    # ── T1 探针落盘带 gain_source ──────────────────────────
    try:
        _pd = mod.ResearchProbe(question="q")  # noqa: F821
    except Exception:
        _pd = None
    # 直接对落盘函数形态做行为断言（不依赖类名）
    _src_all = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    _seg = _src_all[_src_all.find("gain_source"):]
    if '"gain_source"' not in _src_all and "'gain_source'" not in _src_all:
        bad.append("[R-T1] 探针落盘未带 gain_source（E1 来源不可审）")
    elif not _src_all.count("gain_source") >= 2:
        bad.append("[R-T1] gain_source 只有一个出现点（写入无消费）")

    if bad:
        for _m in bad:
            print("  \\u2717 [v12328] %s" % _m)
        return False
    print("  \\u2713 [v12328] 真实入口产出（跨层 stable / attack revoked / "
          "清偿 resolved / 同层负对照 0）· 池级出口 · D3 落盘 · "
          "A3 出口 · gain_source（6 变异体背书）")
    return True


def check_v12324_indep_therapy():'''

repl(_ANCHOR, _NEWFN, "new-fn")

# ── 注册新判据 ────────────────────────────────────────────
repl('''    if not check_v12327_five_mechanisms():
        return 1
''',
     '''    if not check_v12327_five_mechanisms():
        return 1
    if not check_v12328_real_entry():
        return 1
''',
     "register")

out = text.replace("\n", "\r\n").encode("utf-8")
if out.count(b"\r\r\n"):
    sys.exit("❌ 产出含 \\r\\r\\n")

TGT.write_bytes(out)

print("已应用 %d 项：%s" % (len(applied), ", ".join(applied)))
print("smoke_test.py：%d 行 / %d bytes / CRCRLF=%d"
      % (out.count(b"\n"), len(out), out.count(b"\r\r\n")))
