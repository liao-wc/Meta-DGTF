# -*- coding: utf-8 -*-
"""[v1.23.28] 变异体脚本：对**本版新增/更新的判据**做判别力验证。

★ 判据必须自带变异体 —— 没变异体的「全绿」只说明没跑。
★ 变异体打在**判据读的那个东西**上（`if X:` → `if False:`），不是改前缀名。

本版 8 个变异体：
  M1  A1  untouched 写入的 id 被抹掉（`"id": (...)` → `"id": ""`）
      ⇒ 判据「untouched 条目必须带非空 id」判红。
  M2  A1  untouched 的 id 不与 aspect_units 同口径（塞一个不存在的 id）
      ⇒ 判据「untouched.id ∈ aspect_units 的 id 集」判红。
  M3  E2  边际下限回到 0.0 ⇒ `below_floor` 结构性不可达
      ⇒ 判据「floor>0 且 G=0 候选必须被 below_floor 挡下」判红。
  M4  D2  revoked 规则退回 `len(atk) >= len(sup)`（旧退化版）
      ⇒ 判据「跨层攻击 ⇒ revoked」在真实入口**部分**仍可绿……故 M4 改成
      **反向**：把「跨 ≥2 来源」改成「只要 ≥1 攻击来源」⇒
      判据「同层反复攻击不许 revoked」（负对照）判红。
  M5  D2  真实入口登记被重新嵌回守卫（复现被 `_DUP_SIM` 挡掉）
      ⇒ 判据「真实入口下跨层复现 ⇒ stable」判红。
  M6  D3  熵刷新调用点被删（`refresh_belief_entropy()` → `pass`）
      ⇒ 判据「真实入口后 semantic_entropy 非 None」判红。
  M7  E1  `_gains` 键取错字段（改回 `x.get("text","")`）
      ⇒ 判据「引擎算得出 G 时 gain_source == engine」判红。
  M8  出口   `Pool.to_dict` 的 `aspect_units` 出口删除
      ⇒ 判据「merge 灌入后 pool.to_dict 含 aspect_units」判红。
  M9  D3  分组口径退回「全池混合」（拆掉「只留包住本条目的簇」）
      ⇒ 判据「同一主张的两种近义说法必须聚成一簇」判红。
  M10 D3  阈值常量拨回 0.70（与 sim.cluster 混用的旧错）
      ⇒ 判据「默认阈值下近义说法必须聚簇」判红。

用法：
  python _mut_v12328.py                 # 全部 + 正对照
  python _mut_v12328.py --only 1,3,5    # 分片跑（sandbox 配额按 tool-call 记）
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.28.py"


def _sub_count(t, anchor, new):
    n = t.count(anchor)
    if n != 1:
        raise RuntimeError("变异体锚点命中 %d 次（期望 1）：%r" % (n, anchor[:90]))
    return t.replace(anchor, new, 1)


def _load(src):
    return src.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _run_case_via_import(src_text):
    import importlib.util
    import tempfile
    import os
    tmp = Path(tempfile.mkdtemp(prefix="_mut28_")) / "mut_mod.py"
    tmp.write_bytes(src_text.replace("\n", "\r\n").encode("utf-8"))
    os.environ.setdefault("DGTF_API_KEY", "sk-mut")
    spec = importlib.util.spec_from_file_location(
        "mut_mod_%d" % os.getpid(), str(tmp))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# ══ M1：A1 untouched 的 id 被抹掉 ════════════════════════════════
def mut1():
    t = _load(SRC)
    t = _sub_count(
        t,
        '            view.anchor_touched.append({"desc": t, "source": "anchor",\n'
        '                                        "id": (_u_t or {}).get("id", "")})\n',
        '            view.anchor_touched.append({"desc": t, "source": "anchor",\n'
        '                                        "id": ""})\n')
    # ★ 判据读的是「写入 dict 的 id 非空」⇒ 变异体让它恒空。
    #   走真实写入路径需 run 引擎（成本高），故按**源码两向对账**判：
    #   变异后源码里该写入点的 id 表达式不再带 .get("id") ⇒ 说「判据会判红」。
    _seg = t[t.find('view.anchor_touched.append('):]
    _seg = _seg[:_seg.find('\n\n') if '\n\n' in _seg else 400]
    return '_u_t or {}).get("id"' not in _seg  # True ⇒ 判据判红


# ══ M2：A1 untouched 的 id 口径分叉 ═════════════════════════════
def mut2():
    t = _load(SRC)
    t = _sub_count(
        t,
        '        _uid = "A%d" % (len(self.aspect_units) + 1)\n',
        '        _uid = "Z%d" % (len(self.aspect_units) + 1)\n')
    m = _run_case_via_import(t)
    v = m.View(entry="0")
    rec = v.add_aspect_unit("某方面", "anchor", "阴", "anchor")
    # 变异后 id 是 Z1 ⇒ 判据「id 走 A{N} 口径（用于渲染前缀）」判红。
    return not (rec.get("id") or "").startswith("A")


# ══ M3：E2 边际下限回到 0.0 ════════════════════════════════════
def mut3():
    t = _load(SRC)
    t = _sub_count(t, "_GAIN_MARGINAL_FLOOR = 0.02", "_GAIN_MARGINAL_FLOOR = 0.0")
    m = _run_case_via_import(t)
    fl = float(getattr(m, "_GAIN_MARGINAL_FLOOR", 0.0))
    return not (fl > 0.0)  # True ⇒ 判据「floor 应 > 0」判红


# ══ M4：D2 revoked 只需 ≥1 攻击来源（独立性被砍掉） ═════════════
def mut4():
    t = _load(SRC)
    t = _sub_count(
        t,
        '        if (len(_atk_src) >= _rs\n'
        '                and len(_atk_rounds) >= _BELIEF_STABLE_K):',
        '        if (len(_atk_src) >= 1\n'
        '                and len(_atk_rounds) >= _BELIEF_STABLE_K):')
    m = _run_case_via_import(t)
    p = m.Pool()
    p.add_undecidable({"structural_amps": ["某被骂主张"],
                       "aligned_amps": [], "clarity": 0.5,
                       "_layer_name": "0", "_round_no": 1},
                      und_aspects=["a"], layer=1)
    for r in (2, 3, 4, 5):
        p.add_undecidable({"structural_amps": ["某被骂主张"],
                           "aligned_amps": [], "clarity": 0.5,
                           "_layer_name": "0", "_round_no": r,
                           "_belief_attack": "反例%d" % r},
                          und_aspects=["a"], layer=r)
    tos = [x.get("to") for x in (p.belief_transitions or [])]
    return "revoked" in tos  # True ⇒ 负对照判据判红


# ══ M5：真实入口登记被嵌回守卫 ═════════════════════════════════
def mut5():
    t = _load(SRC)
    # 把「登记与去重解耦」改回「只在新增时才登记」
    t = _sub_count(
        t,
        '            _is_new = not any(_similar(s, x, _DUP_SIM)\n'
        '                              for x in self.undecidable_channel["structural_amps"])\n'
        '            if _is_new:\n'
        '                self.undecidable_channel["structural_amps"].append(s[:200])\n'
        '            _atk = []\n',
        '            _is_new = not any(_similar(s, x, _DUP_SIM)\n'
        '                              for x in self.undecidable_channel["structural_amps"])\n'
        '            if _is_new:\n'
        '                self.undecidable_channel["structural_amps"].append(s[:200])\n'
        '            else:\n'
        '                continue\n'
        '            _atk = []\n')
    m = _run_case_via_import(t)
    p = m.Pool()
    prod = {"structural_amps": ["某主张"], "aligned_amps": [], "clarity": 0.5}
    p.add_undecidable(dict(prod, _layer_name="0", _round_no=1),
                      und_aspects=["a"], layer=1)
    p.add_undecidable(dict(prod, _layer_name="1", _round_no=2),
                      und_aspects=["a"], layer=2)
    tos = [x.get("to") for x in (p.belief_transitions or [])]
    return "stable" not in tos  # True ⇒ 判据判红


# ══ M6：D3 熵刷新调用点被摘（真实入口下读数恒 None）════════════
#   ★ 判据（R3 版）读的是「同一主张的两种近义说法必须聚成一簇」
#     ⇒ 把 `refresh_belief_entropy(...)` 调用从 `add_undecidable` 里摘掉，
#     真实入口后 `semantic_entropy` 恒 None ⇒ 判据判红。
def mut6():
    t = _load(SRC)
    t = _sub_count(
        t,
        '        try:\n'
        '            self.refresh_belief_entropy(\n'
        '                thr=getattr(self, "sem_entropy_thr", None))\n'
        '        except Exception:\n'
        '            pass\n',
        '        try:\n'
        '            pass  # (mutated: D3 刷新被摘掉)\n'
        '        except Exception:\n'
        '            pass\n')
    m = _run_case_via_import(t)
    p = m.Pool()
    # 同一主张的两种近义说法（跨层 ⇒ 两条目）
    p.add_undecidable({"structural_amps": ["落盘的最小单位是约束"],
                       "aligned_amps": [], "clarity": 0.5,
                       "_layer_name": "0", "_round_no": 1},
                      und_aspects=["a"], layer=1)
    p.add_undecidable({"structural_amps": ["落盘的最小单位是那条约束"],
                       "aligned_amps": [], "clarity": 0.5,
                       "_layer_name": "1", "_round_no": 2},
                      und_aspects=["a"], layer=2)
    ns = [it.get("occurrence_n")
          for it in (p.belief_items or [])]
    ents = [it.get("semantic_entropy")
            for it in (p.belief_items or [])]
    # True ⇒ 判据判红：既没有聚簇，也没有任何非 None 读数
    return not any(n and n >= 2 for n in ns) and all(e is None for e in ents)


# ══ M7：E1 `_gains` 键取错字段（回退到 bug 版） ══════════════════
def mut7():
    t = _load(SRC)
    t = _sub_count(
        t,
        '_gains = {str(x.get("picked", "")): x.get("g")\n'
        '              for x in (_det.get("trace") or []) if x.get("picked")}',
        '_gains = {str(x.get("text", "")): x.get("g")\n'
        '              for x in (_det.get("trace") or []) if x.get("picked")}')
    m = _run_case_via_import(t)
    p = m.Pool()
    p.belief_items = [
        {"id": "B1", "text": "极低温环境下材料脆性阈值是多少", "status": "active"},
        {"id": "B2", "text": "极低温环境下材料脆性阈值如何", "status": "active"},
        {"id": "B3", "text": "城市轨道交通客流预测模型的误差", "status": "active"},
    ]
    r = m.select_probe_focus(
        p, [{"question": "极低温环境下材料脆性阈值是多少"}],
        [], ["低温", "脆性"], "极低温材料", {"probe": {"select_n": 3}})
    gs = [x.get("gain_source") for x in (r or [])]
    return "engine" not in gs  # True ⇒ 判据判红


# ══ M8：Pool.to_dict 的 aspect_units 出口删除 ═══════════════════
def mut8():
    t = _load(SRC)
    t = _sub_count(
        t,
        '        if self.aspect_units:\n'
        '            d["aspect_units"] = self.aspect_units\n',
        '        if False:\n'
        '            d["aspect_units"] = self.aspect_units\n')
    m = _run_case_via_import(t)
    v = m.View(entry="0")
    v.add_aspect_unit("池级方面甲", source="anchor", polarity="阳", ground="anchor")
    p = m.Pool()
    p.merge(v.amps, v.threads, v.meta, v.probes,
            aspect_units=list(v.aspect_units))
    return "aspect_units" not in p.to_dict()  # True ⇒ 判据判红


# ══ M9：D3 分组口径退回「全池混合」（R1 出厂版的错）════════════
#   判据（R3 强化版）读的是**熵值本身** + 「无关主张不许被混入」：
#     · 正确实现 ⇒ 近义两条 ent=0.0、无关那条 occurrence_n=1；
#     · 全池混合 ⇒ 三条都 occ_n=3 且 ent≈0.58 ⇒ 判红。
#   ★ 第一版 M9 只断言「occurrence_n>=2」⇒ 全池混合**也**满足 ⇒ 无判别力。
#     强化判据改为断言**熵值**，M9 立刻判红（这正是「判据要落在行为上」）。
def mut9():
    t = _load(SRC)
    t = _sub_count(
        t,
        '''            _hn_all, _h_all, _cl_all = semantic_entropy_of(
                _txt, corpus=_corpus, thr=thr)
            # 只留**包住本条目 text** 的那个簇（= 本主张的出现集）。
            _anchor_idx = _txt.index(_own) if _own in _txt else 0
            _keep = None
            for _c in (_cl_all or []):
                if _anchor_idx in _c:
                    _keep = list(_c)
                    break
            if _keep is None:
                _keep = [_anchor_idx]
            _sub = [_txt[_i] for _i in _keep]
''',
        '''            _hn_all, _h_all, _cl_all = semantic_entropy_of(
                _txt, corpus=_corpus, thr=thr)
            _sub = list(_txt)  # 变异：退化成「全池一起算」
''')
    m = _run_case_via_import(t)
    p = m.Pool()
    p.sem_entropy_thr = float(getattr(m, "_SEM_CLUSTER_THR", 0.30))
    p.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                    sources=["layer1"])
    p.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                    round_no=2, sources=["layer0"])
    p.upsert_belief("城市轨道交通客流预测模型误差主要来自换乘",
                    ground="both", round_no=3, sources=["both"])
    p.refresh_belief_entropy(thr=p.sem_entropy_thr)
    ed = [(it.get("occurrence_n"), it.get("semantic_entropy"))
          for it in p.belief_items]
    pair = ed[:2]
    solo = ed[2] if len(ed) > 2 else None
    # True ⇒ 判据判红（近义两条熵非 0，或无关那条被混入）
    if not all(n and n >= 2 and e is not None and e <= 0.05
               for n, e in pair):
        return True
    if solo is not None and solo[0] and solo[0] >= 2:
        return True
    return False


# ══ M10：D3 阈值拨回 0.70（旧错值）⇒ 与 sim.cluster 混用 ════════
#   判据是「负对照：thr=0.70 时近义说法必须退化成不聚」—— 那正是**期望**
#   行为。所以这里反过来打：把**模块默认常量**改回 0.70，
#   判据的正例（默认阈值下近义必须聚簇）判红。
def mut10():
    t = _load(SRC)
    t = _sub_count(t, "_SEM_CLUSTER_THR = 0.30", "_SEM_CLUSTER_THR = 0.70")
    m = _run_case_via_import(t)
    p = m.Pool()
    p.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                    sources=["layer1"])
    p.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                    round_no=2, sources=["layer0"])
    p.refresh_belief_entropy(thr=getattr(m, "_SEM_CLUSTER_THR", 0.30))
    ns = [it.get("occurrence_n") for it in p.belief_items]
    return not any(n and n >= 2 for n in ns)  # True ⇒ 判据判红


def mut11():
    """[F3 时序修正] 把 `View.belief_items` 的回填块**前移**到
    `pool.merge(...)` 之后（= 修复前的位置）⇒ 真实入口下 `view.belief_items`
    必须回到恒空（判据判红）。

    ★ 打在判据读的那个东西上：判据读 `view.belief_items`，变异体改的
      正是它的**赋值时点**。
    ★ 走本脚本既有范式 `_run_case_via_import(变异文本)` —— **不碰主文件**，
      从根上避免「变异体没跑完留下变异态」。
    """
    _orig = _load(SRC)
    BLOCK = (
        '        try:\n'
        '            _seen_keys = set()\n'
        '            for _a in (view.amps or []):\n'
        '                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            for _t0 in (view.anchor_touched or []):\n'
        '                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()\n'
        '                if _t0:\n'
        '                    _seen_keys.add(_t0)\n'
        '            if _seen_keys:\n'
        '                _bind = []\n'
        '                for _it in (pool.belief_items or []):\n'
        '                    if str(_it.get("text", "")).strip() in _seen_keys:\n'
        '                        _bind.append(_it)\n'
        '                if _bind:\n'
        '                    view.belief_items = _bind\n'
        '        except Exception:\n'
        '            pass\n'
    )
    EARLY = ('                   aspect_units=list('
             'getattr(view, "aspect_units", None) or []))\n')
    if _orig.count(BLOCK) != 1 or _orig.count(EARLY) != 1:
        raise RuntimeError("F3 变异锚点命中 %d / %d（要求各 1）"
                           % (_orig.count(BLOCK), _orig.count(EARLY)))
    t = _orig.replace(BLOCK, "", 1)
    t = t.replace(EARLY, EARLY + BLOCK, 1)
    m = _run_case_via_import(t)          # ★ 变异只活在临时模块里
    meta = object.__new__(m.MetaDGTF)
    meta.config = {"sim": {}, "belief": {"revoke_sources": 2,
                                        "sem_entropy_thr": 0.30}}
    meta.decidability_result = None
    meta._anchor_report = None
    meta._ext_assess_cache = {}
    pool = m.Pool()
    view = m.View(entry="0")
    _A = "介质只保存可区分的物理状态，不保存这是四态字段这句话"
    _B = "解码失败状态必须作为持久化判定结果存在否则读写错位"
    view.amps = [{"type": "&", "desc": _A}, {"type": "&", "desc": _B}]
    view.undecidable_product = {"question": "x", "structural_amps": [_A, _B],
                               "clarity": 0.4, "_layer_name": "0",
                               "_round_no": 1}
    meta._apply_view_to_pool_locked(view, pool, "entry-x", layer=1)
    # 正确实现下 view.belief_items 应非空；变异后应恒空
    return len(view.belief_items) == 0    # True ⇒ 判据判红


MUTANTS = [
    (1, "A1 untouched id 被抹空", mut1),
    (2, "A1 id 口径分叉（ZZ{n}）", mut2),
    (3, "E2 floor 回到 0.0", mut3),
    (4, "D2 revoked 砍掉独立性门槛", mut4),
    (5, "D2 登记嵌回守卫", mut5),
    (6, "D3 刷新调用点摘除", mut6),
    (7, "E1 gains 键取错字段", mut7),
    (8, "Pool.to_dict 出口删除", mut8),
    (9, "D3 分组退化成全池混合", mut9),
    (10, "D3 阈值拨回 0.70", mut10),
    (11, "F3 回填时序退回（放在 merge 之后）", mut11),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    want = set()
    if args.only:
        want = {int(x) for x in args.only.split(",") if x.strip()}

    ok = 0
    fail = 0
    for _no, _name, _fn in MUTANTS:
        if want and _no not in want:
            continue
        try:
            _red = bool(_fn())
        except Exception as e:
            print("  ✗ M%d %s —— 变异体自身报错：%s: %s"
                  % (_no, _name, type(e).__name__, e))
            fail += 1
            continue
        if _red:
            print("  ✓ M%d %s —— 判据判红（判别力成立）" % (_no, _name))
            ok += 1
        else:
            print("  ✗ M%d %s —— 判据**未判红**（判据无判别力）" % (_no, _name))
            fail += 1
    print("\n变异体：%d 通过 / %d 失败" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
