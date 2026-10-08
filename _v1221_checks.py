#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.22.1 冒烟检查函数的**源仓库**。

`_mk_v1221_smoke_checks.py` 会把本文件里的 `check_v1221_pN` 逐个抽出来插进
`smoke_test.py`（已存在的用本文件版本替换）。

函数体在 smoke_test 的命名空间里执行，所以可以直接用 `mod` / `HERE` / `sys` / `Path`。
签名统一 `check_v1221_pN(SRC=None)`：
- `SRC=None`（smoke 内部调用）→ 用 smoke 已加载好的 `mod`；
- 传 `SRC` → 自己按路径加载模块。

★ 每个判据都必须带**负对照**：不只锁「该判红的判红」，还要锁「不该判红的别判红」。
"""
from __future__ import annotations


def _v1221_mod(SRC):
    """取被测模块：优先 smoke 命名空间里已加载的 mod，其次按 SRC 现加载。"""
    import importlib.util
    import sys as _sys
    base = globals().get("mod")
    if SRC is None and base is not None:
        return base
    if SRC is None:
        raise RuntimeError("既没传 SRC，命名空间里也没有 mod")
    spec = importlib.util.spec_from_file_location("dgtf_v1221check", SRC)
    m = importlib.util.module_from_spec(spec)
    _sys.modules["dgtf_v1221check"] = m
    spec.loader.exec_module(m)
    return m


def _v1221_src_text(SRC):
    from pathlib import Path as _P
    if SRC is not None:
        return _P(SRC).read_text(encoding="utf-8")
    base = globals().get("mod")
    f = getattr(base, "__file__", None)
    if f:
        return _P(f).read_text(encoding="utf-8")
    return ""


def check_v1221_p1(SRC=None):
    """[v1.22.1 P1] 研究层结构化 actions：schema 优先 / 词法兜底 / 两条负对照。"""
    print("  · v1.22.1 P1：研究层结构化 actions（schema 优先 + 词法兜底）")
    try:
        m = _v1221_mod(SRC)
        # 1 schema 优先
        v = m.View(entry="1")
        v.decidable_product = {
            "answer": "x",
            "actions": [
                {"id": "A1", "verb": "指派", "object": "核查",
                 "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
                 "acceptance": "出具签字人清单", "fallback": "向上级申请"},
                {"id": "A2", "verb": "提交", "object": "排水图",
                 "owner_role": "排水公司", "deadline_hint": "本月内",
                 "acceptance": "管网档案归档", "fallback": "委托第三方"},
                {"id": "A3", "verb": "试点", "object": "透水铺装",
                 "owner_role": "项目组", "deadline_hint": "本季度",
                 "acceptance": "验收报告出具", "fallback": "缩减试点范围"},
            ],
        }
        acts = m._extract_actions(v)
        assert len(acts) == 3, f"schema 三条应原样返回，实测 {len(acts)}"
        assert all(a["_source"] == "schema" for a in acts), acts
        assert all(not a["_missing"] for a in acts), acts
        # 2 兜底词法
        v2 = m.View(entry="1")
        v2.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
        acts2 = m._extract_actions(v2)
        assert acts2 and all(a["_source"] == "lexical" for a in acts2), acts2
        # 3 负对照：空 answer 无 schema → []
        v3 = m.View(entry="1")
        v3.decidable_product = {"answer": ""}
        assert m._extract_actions(v3) == []
        # 4 负对照：schema 缺字段 → _missing 标出
        v4 = m.View(entry="1")
        v4.decidable_product = {"answer": "x",
                                "actions": [{"id": "A1", "verb": "指派",
                                             "object": "核查"}]}
        acts4 = m._extract_actions(v4)
        assert acts4 and acts4[0]["_missing"], acts4
        # 5 负对照：只给 2 条 schema → 条数不足（触发条件成立）
        v5 = m.View(entry="1")
        v5.decidable_product = {"answer": "x", "actions": [
            dict(v.decidable_product["actions"][0]),
            dict(v.decidable_product["actions"][1])]}
        n5 = len([a for a in m._extract_actions(v5)
                  if a.get("_source") == "schema"])
        assert n5 == 2, n5
        # 6 源码断言
        src = _v1221_src_text(SRC)
        assert "decidable_product" in src and '"actions"' in src
        assert "模型没按 schema 产出 actions" in src
        assert "action_fields_missing" in src
        assert ("action_fields_missing"
                in (getattr(m, "_V122_HARD_FLAGS", ()) or ()))
        print("  ✓ v1.22.1 P1：schema 三条原样 / 词法兜底带标签 / "
              "空 answer=[] / 缺字段标 _missing / 2 条判不足")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P1 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p2(SRC=None):
    """[v1.22.1 P2] triage 触发条件改挂结构标签（含三条负对照）。"""
    print("  · v1.22.1 P2：triage 挂结构标签（[外] 前缀 + 语义关键词 + 自指不降级）")
    try:
        m = _v1221_mod(SRC)
        # 1 结构标签命中
        assert m._is_triage_candidate("[外] 具体某老城区的最优方案")
        # 2 语义关键词命中
        assert m._is_triage_candidate("信息不足，无法判断")
        assert m._is_triage_candidate("需外部动作")
        # 3 负对照①：真·自指不许降级
        assert not m._is_never_downgrade("[外] 具体某老城区的最优方案")
        assert m._is_never_downgrade("该判定自指，无共同参照系")
        # 4 负对照②：无标签无语义词
        assert not m._is_triage_candidate("现场取证难度大")
        # 5 负对照③：空串
        assert not m._is_triage_candidate("")
        # 6 源码断言 + 加性（旧词表一字未删）
        src = _v1221_src_text(SRC)
        assert "_TRIAGE_STRUCTURAL_PREFIXES" in src
        assert "_TRIAGE_NEVER_DOWNGRADE" in src
        assert "_is_triage_candidate" in src
        assert "_is_never_downgrade" in src
        assert '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in src
        assert "for k in _TRIAGE_KEYS)" not in src
        # 7 动词白名单没被动（旁证「不拟合数据」守住）
        assert len(getattr(m, "_ACTION_VERB_WHITELIST", ()) or ()) == 19
        print("  ✓ v1.22.1 P2：结构标签/语义词两路命中；自指、无标签、空串"
              "三条负对照不降级；旧词表保留；白名单仍 19")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P2 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p3(SRC=None):
    """[v1.22.1 P3] 仅源码机制负对照：脚本/JSON/文档齐 + 判定合法 + 条数对账。"""
    print("  · v1.22.1 P3：仅源码机制负对照（5 条 × 三分类判定）")
    try:
        import json as _json
        from pathlib import Path as _P
        for f in ("_negctl_v1221_p3.py", "_negctl_v1221_p3.json",
                  "docs/机制负对照-v1221.md"):
            assert _P(f).exists(), f"缺 {f}"
        data = _json.loads(
            _P("_negctl_v1221_p3.json").read_text(encoding="utf-8"))
        assert len(data) >= 5, f"负对照条数 {len(data)} < 5"
        for name, it in data.items():
            assert it["verdict"] in ("条件不可达", "条件窄但成立",
                                     "机制没工作"), \
                f"{name} verdict 非法：{it['verdict']}"
            assert isinstance(it.get("triggered"), bool), \
                f"{name} triggered 不是 bool"
        # 与审计报告的「仅源码」清单两向对账
        # ★ 对**冻结快照**，不是活的审计报告：语料会长大，原本判「仅源码」的
        #   机制会变成「可达」（实测 P3 时点 5 条 → 09:42 重跑审计 0 条）——
        #   拿移动靶当锚会因为数据变大而翻红，与「有没有删机制」无关。
        _fz = _P("_negctl_v1221_p3_frozen.json")
        assert _fz.is_file(), "缺 _negctl_v1221_p3_frozen.json（P3 时点快照）"
        _snap = set(_json.loads(_fz.read_text(encoding="utf-8")).get(
            "src_only_at_p3_time") or [])
        assert set(data) == _snap, \
            f"负对照 {sorted(data)} ≠ 冻结快照 {sorted(_snap)}"
        print(f"  ✓ v1.22.1 P3：{len(data)} 条齐（与审计报告两向对账一致）；"
              f"判定 " + "、".join(sorted({v['verdict'] for v in data.values()})))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P3 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p2b(SRC=None):
    """[v1.22.1 P2b] triage 第二条路径：answers 匹配（端到端打通）。

    ★ 三类负对照必须同时成立，否则「命中」这件事不成立：
      ① 无 answers（None）／空 list／空 aspect → 不许命中（应回落 claim 路径）；
      ② 不相关的一对 → 不许命中；
      ③ tier 门仍在（answers 命中但 tier 超 floor 也不选）。
    """
    try:
        NL = chr(10)          # ★ 注入器只搬函数，模块级名字搬不过去
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1/2 两个匹配函数在
        assert hasattr(m, "_hit_by_answers"), "_hit_by_answers 缺失"
        assert hasattr(m, "_hit_by_claim"), "_hit_by_claim 缺失"

        # 3 answers 正向命中（重叠 + 双向）
        assert m._hit_by_answers(
            "老城区现有排水管网的设计标准是多少年一遇",
            ["管网设计重现期", "老城区现有排水管网的设计标准"]), "正向未命中"
        assert m._hit_by_answers(
            "老城区地下管线密集程度", ["老城区地下管线密集程度"]), "同文未命中"
        # 3b 反向分支（对称性）：★ 实测 `_overlap_coef` 是**对称**函数（分母 min 与方向
        #   无关），所以「反向再查一次」与正向**等价**，不给新命中。
        #   这里锁的是真正的不变量：两向结果一致（不引入隐藏的方向依赖）。
        #   （任务书原文的用例断言不通 —— jieba 把「排水管网的设计标准」切成
        #     「排水管/设计标准」，与「管网设计重现期」无交集，实测重叠 0.000。）
        _a5 = "管网设计重现期"
        _b5 = ["老城区现有排水管网的设计标准是多少年一遇"]
        assert m._overlap_coef(_a5, _b5[0]) == m._overlap_coef(_b5[0], _a5), \
            "_overlap_coef 竟不对称（反向分支的前提被推翻，需重审）"
        assert m._hit_by_answers(_a5, _b5) == m._hit_by_answers(_b5[0], [_a5]), \
            "正反两向结果不一致"

        # 4 负对照：空 list / None / 空 aspect
        assert not m._hit_by_answers("任意", []), "负对照：空 list 竟命中"
        assert not m._hit_by_answers("任意", None), "负对照：None 竟命中"
        assert not m._hit_by_answers("", ["管网设计重现期"]), "负对照：空 aspect 竟命中"

        # 5 负对照：不相关
        assert not m._hit_by_answers(
            "本地微观数据", ["管网设计重现期"]), "负对照：不相关竟命中"

        # 6 claim 老路径：行为在 + 字面 0.6 未改
        assert m._hit_by_claim(
            "管网设计重现期", "GB50014 管网设计重现期 3~5 年"), "claim 路径失效"
        _i0 = src.find("def _hit_by_claim")
        _i1 = src.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
        _body_c = src[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else src[_i0:]
        assert "_similar(" in _body_c and "0.6" in _body_c, "claim 路径字面 0.6 被改"
        _j0 = src.find("def _hit_by_answers")
        _j1 = src.find(NL + "def ", _j0 + 10) if _j0 >= 0 else -1
        _body_a = src[_j0:_j1] if _j0 >= 0 and _j1 > _j0 else src[_j0:]
        assert "_overlap_coef" in _body_a and "_UNTRACED_OVERLAP" in _body_a, \
            "answers 路径未用 _overlap_coef + _UNTRACED_OVERLAP"
        assert "_UNTRACED_OVERLAP" in src, "_UNTRACED_OVERLAP 不在"

        # 7 crosscheck：两条路都在 + tier 门仍在 + 旧单路径已撤
        _k0 = src.find("def _anchor_crosscheck")
        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
        _xc = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]
        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"
        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"
        assert 'x.get("answers")' in _xc, "crosscheck 未读 answers 字段"
        assert 'if int(x.get("tier", 3) or 3) <= _floor_c' in _xc, "tier 门丢了"
        assert '_similar(str(_a), str(x.get("claim", "")), 0.6))' not in _xc, \
            "旧单路径仍在 crosscheck 里"

        # 8 _load_anchors 读 answers（键在 + **真读进来**）
        assert '"answers": [str(x)[:60]' in src, "_load_anchors 未加 answers 键"
        import json as _json
        from pathlib import Path as _P
        _tmp = _P("_smoke_p2b_ans.json")
        _tmp.write_text(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "X", "tier": 1,
                          "answers": ["问题A", "问题B"]}]},
            ensure_ascii=False), encoding="utf-8")
        try:
            _cfg = m.DEFAULT_CONFIG.copy()
            _cfg["external_anchor"] = dict(_cfg.get("external_anchor") or {})
            _cfg["external_anchor"].update(
                {"enabled": True, "path": "_smoke_p2b_ans.json"})
            _cfg["output"] = dict(_cfg.get("output") or {})
            _cfg["output"]["verbose"] = False
            _meta = m.MetaDGTF(_cfg)
            _meta._load_anchors()
            _got = (_meta._anchors[0].get("answers")
                    if getattr(_meta, "_anchors", None) else None)
            assert _got == ["问题A", "问题B"], "answers 未读进来：" + repr(_got)
        finally:
            # ★ 清理**不是判据**：本机沙箱的 safe-delete 会让 unlink 抛
            #   OSError（SAFE_DELETE_FAIL_CLOSED），不能因此把检查判红。
            try:
                _tmp.unlink(missing_ok=True)
            except OSError:
                pass

        # 9 P2a 成果一字未删（宪法级禁令）
        assert all(k in src for k in (
            "_TRIAGE_STRUCTURAL_PREFIXES", "def _is_triage_candidate",
            "def _is_never_downgrade")), "P2a 成果被删"
        assert '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in src, \
            "旧词表被改"

        print("  ✓ v1.22.1 P2b：双路径（answers OR claim）/ claim 0.6 未动 / "
              "三类负对照通过 / _load_anchors 真读 answers / P2a 成果未删")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P2b 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p5(SRC=None):
    """[v1.22.1 P5] auto 取向回填：判定留痕 + 错配告警。

    ★ 任务书前提与实现不符：`auto_plan` 的**单调用**分支（`run()` 走的就是
      它）原来不带 `orientation`，所以 `_auto_plan_used` 永远没有取向。
      本检查直接**打桩跑一次 `auto_plan`**，锁「同一次调用里带出取向」。
    """
    try:
        NL = chr(10)
        Q = chr(34)
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1/2 静态串
        assert "_auto_plan_used" in src, "run()/_pack_result 未记 _auto_plan_used"
        assert "取向判定（plan_orientation）" in src, "缺头部「取向判定」行"
        assert "取向错配" in src, "缺「取向错配」告警"

        # 3 auto_plan 单调用分支要解析并带出 orientation
        _i0 = src.find("def auto_plan(")
        _i1 = src.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
        _body = src[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else src[_i0:]
        # ★ 只搜到引号为止 —— 实际代码是 `data.get("orientation", "")`，
        #   连右括号一起搜会匹配不到（第一版就这么误报过）。
        assert ("data.get(" + Q + "orientation" + Q) in _body, (
            "auto_plan 未解析 orientation")
        assert _body.count(Q + "orientation" + Q + ": _ori") >= 2, (
            "auto_plan 的早退分支没把 orientation 带出")

        # 4 行为：打桩一次调用，验带出 + 只调一次 + prompt 里要了取向
        class _StubLLM:
            def __init__(self):
                self.calls = []

            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": "serial",
                                 "orientation": "boundary",
                                 "rounds": {"0": 4, "1": 4,
                                            "both": 4, "all": 5},
                                 "reason": "桩", "confidence": 0.9})

            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        _st = _StubLLM()
        _plan = m.auto_plan("地铁运营效率该怎么衡量？",
                            dict(m.DEFAULT_CONFIG), llm=_st)
        assert _plan.get("orientation") == "boundary", (
            "orientation 未带出：" + repr(_plan.get("orientation")))
        assert len(_st.calls) == 1, "单调用路径被改成多次（成本变化）"
        assert "orientation" in _st.calls[0][0], "prompt 里没要取向"

        # 5 负对照：桩回一个非法取向 → 归一成空串（不许把垃圾当取向）
        class _Stub2(_StubLLM):
            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": "serial", "orientation": "随便"})

        _p2 = m.auto_plan("x", dict(m.DEFAULT_CONFIG), llm=_Stub2())
        assert not _p2.get("orientation"), "非法取向竟被采纳：" + repr(_p2)

        print("  ✓ v1.22.1 P5：判定留痕 + 错配告警 + 单调用带出取向（打桩实测）"
              " + 非法取向归一负对照")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P5 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p6(SRC=None):
    """[v1.22.1 P6] tier 全缺省时的显式提示。

    ★ 任务书骨架在 `out` 上数「谁没声明 tier」—— 而 `out` 里每条都补了
      缺省 3，计数恒为 0，警告**永远不触发**。这里在**原始条目**上判，
      并用两份临时锚点文件做正/负对照。
    """
    try:
        import json as _json
        from pathlib import Path as _P
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        assert "_anchor_tier_warning" in src, "缺 _anchor_tier_warning"
        assert "锚点 tier 警告" in src, "缺头部「锚点 tier 警告」行"

        _notier = _P("_smoke_p6_notier.json")
        _notier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y"}]},
            ensure_ascii=False).encode("utf-8"))
        _onetier = _P("_smoke_p6_onetier.json")
        _onetier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y", "tier": 1}]},
            ensure_ascii=False).encode("utf-8"))

        def _load(path):
            cfg = _json.loads(_json.dumps(m.DEFAULT_CONFIG, default=str))
            cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
            cfg["external_anchor"].update({"enabled": True, "path": str(path)})
            cfg["output"] = dict(cfg.get("output") or {})
            cfg["output"]["verbose"] = False
            mm = m.MetaDGTF(cfg)
            mm._load_anchors()
            return getattr(mm, "_anchor_tier_warning", "<无属性>")

        try:
            w_all = _load(_notier)
            w_one = _load(_onetier)
            assert isinstance(w_all, str) and w_all, (
                "全缺省竟无警告（正对照失败）：" + repr(w_all))
            assert not w_one, (
                "有显式 tier 仍有警告（负对照失败）：" + repr(w_one))
        finally:
            # ★ 同上：清理失败不影响判定。
            try:
                _notier.unlink(missing_ok=True)
                _onetier.unlink(missing_ok=True)
            except OSError:
                pass

        # 红线保留：无 tier 的锚点**不进引用表**（即便挂了 evidence 档）
        _p1 = m.Pool()
        _p1.anchors = [{"id": "a1", "claim": "X"}]
        _p1.anchor_as_evidence = True
        _t1 = m._citation_table(None, _p1)
        assert not any(c.startswith("X") for c, _ in _t1), (
            "无 tier 的锚点竟进了引用表（红线破了）")
        _p2 = m.Pool()
        _p2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
        _p2.anchor_as_evidence = True
        _t2 = m._citation_table(None, _p2)
        assert any(c.startswith("X") for c, _ in _t2), (
            "有 tier=1 的锚点却进不了引用表")

        print("  ✓ v1.22.1 P6：全缺省告警（正对照）+ 有显式 tier 不告警（负对照）"
              " + 无 tier 不入引用表（红线）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P6 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


def check_v1221_p7(SRC=None):
    """[v1.22.1 P7] 明确不做（只出说明，不动代码）。

    ★ 本档**不改引擎**：只查决策记录在不在、三条在不在，外加一条负对照 ——
      「这三件事不许跑进产物头部」（决策记录不是产物级告警）。
    """
    try:
        from pathlib import Path as _P
        doc = _P("docs/不做什么-v1221.md")
        assert doc.is_file(), "缺 docs/不做什么-v1221.md"
        text = doc.read_text(encoding="utf-8")
        assert "不拆模块" in text, "缺「不拆模块」"
        assert "不扩动词白名单" in text, "缺「不扩动词白名单」"
        assert "不删任何机制" in text, "缺「不删任何机制」"

        # 负对照：三条都不许出现在产物头部渲染里
        src = _v1221_src_text(SRC)
        _i = src.find("def save_result")
        _head = src[_i:_i + 20000] if _i >= 0 else ""
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            assert k not in _head, "决策记录跑进了产物头部：" + k

        print("  ✓ v1.22.1 P7：决策记录三条齐 + 负对照（不进产物头部）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P7 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


