#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.22 冒烟检查函数的**源仓库**。

`_mk_v122_smoke_checks.py` 会把本文件里的 `check_v122_phaseN` 函数
逐个抽出来插进 `smoke_test.py`（已存在的用本文件版本替换）。

函数体在 smoke_test 的命名空间里执行，所以可以直接用 `mod` / `HERE` /
`sys` / `Path`。签名统一为 `check_v122_phaseN(SRC=None)`：
- `SRC=None`（smoke 内部调用）→ 用 smoke 已经加载好的 `mod`；
- 传 `SRC`（任务书里的独立冒烟写法）→ 自己按路径加载模块。

★ 每个判据都必须带**负对照**：只锁「该判红的判红」不够，还要锁
  「不该判红的别判红」，否则把阈值改坏也能通过。
"""
from __future__ import annotations


def _v122_mod(SRC):
    """取被测模块：优先 smoke 命名空间里已加载的 mod，其次按 SRC 现加载。"""
    import importlib.util
    import sys as _sys
    base = globals().get("mod")
    if SRC is None and base is not None:
        return base
    if SRC is None:
        raise RuntimeError("既没传 SRC，命名空间里也没有 mod")
    spec = importlib.util.spec_from_file_location("dgtf_v122check", SRC)
    m = importlib.util.module_from_spec(spec)
    _sys.modules["dgtf_v122check"] = m
    spec.loader.exec_module(m)
    return m


def _v122_src_text(SRC):
    from pathlib import Path as _P
    if SRC is not None:
        return _P(SRC).read_text(encoding="utf-8")
    base = globals().get("mod")
    f = getattr(base, "__file__", None)
    if f:
        return _P(f).read_text(encoding="utf-8")
    return ""


def check_v122_phase1(SRC=None):
    """[v122 阶段1] 四层 objective / 覆盖率只对研究层 / 未生分类 / 头部四行。"""
    print("  · v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类 / 头部四行")
    try:
        m = _v122_mod(SRC)

        # ① Phase.objective 四层各就各位
        want = {"0": "manifest", "1": "truth",
                "both": "collision", "all": "closure"}
        for k, v in want.items():
            got = getattr(m.PHASES.get(k), "objective", None)
            assert got == v, f"PHASES[{k!r}].objective={got!r} ≠ {v!r}"

        # ② 覆盖率只对研究层：entry≠"1" → None
        #   ★ 池子必须**非空**：空池分母为 0，coverage 本来就是 None，
        #     那样「entry=1 不是 None」会误报成过度收窄。
        p = m.Pool()
        p.sub_questions = [{"id": "s1", "decidability": "decidable",
                            "status": "answered", "weight": 1.0,
                            "depth": 1.0}]
        assert m.coverage_of(p, {}, entry="0") is None, "entry=0 必须 None"
        assert m.coverage_of(p, {}, entry="both") is None, "entry=both 必须 None"
        assert m.coverage_of(p, {}, entry="all") is None, "entry=all 必须 None"
        # 负对照：研究层不许被一起挡掉（挡住了就是过度收窄）
        assert m.coverage_of(p, {}, entry="1") is not None, \
            "entry=1 不该是 None"
        # 向下兼容：不传 entry 的旧调用点行为必须与 entry=1 逐字一致
        assert m.coverage_of(p, {}) == m.coverage_of(p, {}, entry="1"), \
            "不传 entry 时旧行为应逐字不变"
        assert m.coverage_parts(p, {}, entry="0") == (0, 0, None), \
            "coverage_parts(entry=0) 必须是 (0,0,None)"

        # ③ 未生分类：两种入参形态都要吃
        #    · 任务书口径 = View 对象
        assert m._classify_unsaid(m.View(entry="0", collision="")) == "lazy"
        assert m._classify_unsaid(m.View(
            entry="0", collision="一、让两端各自把话说完\n二、各推到极端",
            probes=[{"question": "Q", "covers": ["T1"]}])) == "real"
        # 负对照：说了「此处未生」，即使 probes 带 covers，也必须判 lazy
        assert m._classify_unsaid(m.View(
            entry="0", collision="（此处未生）",
            probes=[{"question": "Q", "covers": ["T1"]}])) == "lazy"
        # 负对照：空 covers 必须 lazy，否则这个判据永远亮
        assert m._classify_unsaid(m.View(
            entry="0", collision="一、让两端各自把话说完",
            probes=[{"question": "Q", "covers": []}])) == "lazy"
        #    · 旧 dict 形态继续可用
        assert m._classify_unsaid({}) == "lazy"
        assert m._classify_unsaid({"covers": ["T1"]}) == "real"
        assert m._classify_unsaid({"covers": []}) == "lazy"
        assert m._classify_unsaid(None) == "lazy"
        assert m._classify_unsaid({"covers": "T1"}) == "real"

        # ④ 头部四行：计数口径，且每层名 + objective 都在
        _res = {
            "views": {
                "0": {"amps": [1, 2], "threads": [1], "suspensions": [],
                      "probes": [1, 2, 3]},
                "1": {"settlement": {"coverage": 0.5},
                      "decidable_product": {"distance": 0.4}},
                "both": {"ing_structured": {"third": True,
                                            "tensions": ["a", "b"]}},
                "all": {"meta_closure": {"clean": True, "unsettled": 0}},
            },
            "pools": {},
        }
        lines = m._layer_objective_lines(_res)
        assert len(lines) == 4, f"分层目标应为 4 行，得到 {len(lines)}"
        joined = "".join(lines)
        for n in ("修行层", "研究层", "对撞层", "元层"):
            assert n in joined, f"分层目标缺 {n}"
        for kw in ("& 2", "线头 1", "悬置 0", "探针 3", "覆盖率 50%",
                   "third ✓", "张力 2", "clean True", "未交代 0 类"):
            assert kw in joined, f"分层目标缺计数 {kw!r}"
        # 负对照：objective 图例形态仍在（不传 result）
        lg = m._layer_objective_lines()
        assert len(lg) == 4 and "objective=" in "".join(lg)

        # ⑤ 元层不评价修行层
        import inspect as _ins
        body = _ins.getsource(m.MetaDGTF._settle_meta)
        assert 'pools["0"]' not in body and "pools['0']" not in body, \
            "_settle_meta 仍在读修行池"

        # ⑥ 修行层停止理由含「未生质量」（源码级）
        src = _v122_src_text(SRC)
        assert "未生质量" in src, "stop_reason 改写没落进源码"
        assert "修行层不追求收敛" in src, "缺红线注释"
        assert "分层目标" in src, "头部渲染没落进源码"

        # ⑦ route 分层：boundary 保留全四层；decision 允许砍层
        inst = object.__new__(m.MetaDGTF)
        inst.config = {}
        inst.vp = lambda *a, **k: None
        r = inst._route_by_decidability("q", ["0", "1", "both", "all"],
                                        orientation="boundary")
        assert r == ["0", "1", "both", "all"], f"boundary 应保留全四层，得到 {r}"
        r2 = inst._route_by_decidability("q", ["0", "1"], orientation="boundary")
        assert r2 == ["0", "1"], f"两层的 route 不该被动，得到 {r2}"

        print("  ✓ v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类(双形态) / "
              "头部四行计数 / 元层不读修行池 / route 分层")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段1 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v122_phase2(SRC=None):
    """[v122 阶段2] 三态多票 / 冻结条 / 校准队列。"""
    print("  · v1.22 阶段2：三票互异 / 冻结签名 / 校准 export-import")
    try:
        import json as _json
        import subprocess as _sp
        import tempfile
        from pathlib import Path as _P

        m = _v122_mod(SRC)
        HERE_ = _P(getattr(globals().get("mod"), "__file__", ".")).resolve().parent \
            if SRC is None else _P(SRC).resolve().parent

        tv = m._TRI_VOTE_PROMPTS
        assert len(tv) == 3, f"三票 prompt 应为 3，得到 {len(tv)}"
        assert len(set(tv)) == 3, "三票 prompt 有重复 —— 重复的三票等于没投票"
        assert hasattr(m.MetaDGTF, "_adjudicate_sub_tristate_multi")
        assert hasattr(m.MetaDGTF, "_adjudicate_sub_tristate")

        def _pool(labs):
            pp = m.Pool()
            pp.sub_questions = [
                {"id": f"s{i}", "decidability": l, "question": f"Q{i}"}
                for i, l in enumerate(labs, 1)]
            pp.deferrals = []
            return pp

        p = _pool(["decidable", "undecidable"])
        fz = m.DecidabilityFreeze()
        sig = fz.freeze(p, layer=1)
        assert len(sig) == 64, f"sha256 应为 64 位，得到 {len(sig)}"
        assert all("_frozen_answerable" in s for s in p.sub_questions)
        assert fz.verify(p) is True, "未篡改却判红"
        # 负对照①：decidable→partial —— 分母没变、判定变了，只签布尔会漏
        p.sub_questions[0]["decidability"] = "partial"
        try:
            fz.verify(p)
            raise AssertionError("decidable→partial 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照②：真翻转分母也要判红
        p.sub_questions[0]["decidability"] = "undecidable"
        try:
            fz.verify(p)
            raise AssertionError("decidable→undecidable 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照③：条数变了（换了个池）也不许静默通过
        try:
            fz.verify(_pool(["decidable"]))
            raise AssertionError("池条数变了仍判通过")
        except RuntimeError:
            pass
        # 负对照④：**只翻 `_frozen_answerable`、不动标签** —— 任务书
        #   Step 3.3 的冒烟标的正是这一刀。实测早先漏了（_canon 当时
        #   由当前标签现推可答性，被冻结的布尔根本没进签名）。
        #   这条是探针发现的，收进冒烟钉死。
        p_b = _pool(["decidable", "undecidable"])
        fz_b = m.DecidabilityFreeze()
        fz_b.freeze(p_b, layer=1)
        p_b.sub_questions[0]["_frozen_answerable"] = \
            not p_b.sub_questions[0]["_frozen_answerable"]
        try:
            fz_b.verify(p_b)
            raise AssertionError("只翻 _frozen_answerable 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照⑤：只改 `_frozen_decidability` 也要判红
        p_c = _pool(["decidable", "undecidable"])
        fz_c = m.DecidabilityFreeze()
        fz_c.freeze(p_c, layer=1)
        p_c.sub_questions[0]["_frozen_decidability"] = "undecidable"
        try:
            fz_c.verify(p_c)
            raise AssertionError("只改 _frozen_decidability 未被判为篡改")
        except RuntimeError:
            pass

        # 冻结后分母不变
        p3 = _pool(["decidable", "undecidable"])
        m.DecidabilityFreeze().freeze(p3, layer=1)
        d1 = m.coverage_parts(p3, {}, entry="1")[1]
        p3.sub_questions[0]["decidability"] = "undecidable"
        d2 = m.coverage_parts(p3, {}, entry="1")[1]
        assert d1 == d2 == 1, f"冻结后分母不该变：{d1} → {d2}"
        # 负对照：不冻结时改判**会**改变分母（否则上面那条没判别力）
        p4 = _pool(["decidable", "undecidable"])
        d3 = m.coverage_parts(p4, {}, entry="1")[1]
        p4.sub_questions[0]["decidability"] = "undecidable"
        d4 = m.coverage_parts(p4, {}, entry="1")[1]
        assert d3 == 1 and d4 == 0, f"不冻结时应随改判变：{d3} → {d4}"

        # 校准 export → 填表 → import
        td = _P(tempfile.mkdtemp())
        (td / "result.json").write_text(_json.dumps({
            "calibration_queue": [
                {"sub_id": "s1",
                 "final": "partial",
                 "votes": [{"voter": 0, "label": "decidable"},
                           {"voter": 1, "label": "partial"},
                           {"voter": 2, "label": "decidable"}]}],
            "freeze": {"signature": sig},
            "pools": {"1": {"sub_questions": [
                {"id": "s1", "question": "甲"}]}},
        }, ensure_ascii=False), encoding="utf-8")
        cal = HERE_ / "bench" / "bench_calibrate.py"
        r = _sp.run([__import__("sys").executable, str(cal), "export", str(td),
                     str(td / "b.md")], capture_output=True, text=True)
        assert r.returncode == 0, f"export 失败 {r.stderr[-200:]}"
        tbl = (td / "b.md").read_text(encoding="utf-8")
        assert tbl.count("| ") >= 4, "导出表没有数据行"
        (td / "b.md").write_text(
            tbl.replace("|  |  |", "| partial | 人工核过 |"), encoding="utf-8")
        r2 = _sp.run([__import__("sys").executable, str(cal), "import",
                      str(td / "b.md"), str(td)],
                     capture_output=True, text=True)
        assert r2.returncode == 0, f"import 失败 {r2.stderr[-200:]}"
        v = _json.loads((td / "verdicts.json").read_text(encoding="utf-8"))
        assert v["n"] == 1, f"回填条数 {v['n']} ≠ 1"

        src = _v122_src_text(SRC)
        assert "三态多票" in src and "**冻结**" in src, "头部渲染字面串缺失"
        print("  ✓ v1.22 阶段2：三票互异 / 签名 64 位 / 三类篡改都判红 / "
              "分母冻结(含反向负对照) / 校准 export→import")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段2 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v122_phase3(SRC=None):
    """[v122 阶段3] decision 行动闭环 / 分流壳 / 硬约束 / rubric。"""
    print("  · v1.22 阶段3：行动抽取 / 分流壳 / 硬约束 / rubric")
    try:
        m = _v122_mod(SRC)
        src = _v122_src_text(SRC)

        # ① 开关 + 两个 render 都在
        assert "landing_decision" in src, "缺开关字面串"
        assert hasattr(m, "_render_landing_decision"), "缺新模板"
        assert hasattr(m, "_render_landing_boundary"), "缺老模板（改名后必须仍在）"

        # ② 抽取：任务书口径的 View 入参
        v = m.View(entry="1")
        v.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
        acts = m._extract_actions(v)
        assert len(acts) >= 1, f"抽出 {len(acts)} 条"
        for k in ("verb", "object", "owner_role", "deadline_hint",
                  "acceptance", "fallback"):
            assert all(k in a and a[k] for a in acts), f"缺字段 {k}"
        # 负对照：空结论必须 0 条（否则 action_incomplete 永不亮）
        v2 = m.View(entry="1")
        v2.decidable_product = {"answer": ""}
        assert m._extract_actions(v2) == [], "空 answer 不该抽出 action"
        # dict 形态也要吃（落地层拿到的是 packed 里的 dict）
        assert len(m._extract_actions(
            {"decidable_product": {"answer": "先指派区防汛办核查。"}})) >= 1

        # ③ 硬约束字面串
        assert "action_incomplete" in src and "not_do_missing" in src

        # ③b 硬约束 flag 必须能在 quality_flags **重算**后存活。
        #   ★ 实测踩过（读真跑的 packed 才发现）：flag 追加后 19 行有
        #     `_keep_selfcheck_flags(view, _dg._quality_check(...))` ——
        #     整体重算，两条 flag 当场消失（errors 里还在、flags 里没了）。
        class _VQ:
            def __init__(self):
                self.quality_flags = ["action_incomplete", "not_do_missing",
                                      "unsaid_overused", "无关的线索"]
        _kept = m._keep_selfcheck_flags(_VQ(), ["probe_return_empty"])
        assert "action_incomplete" in _kept and "not_do_missing" in _kept, \
            f"硬约束 flag 被重算冲掉：{_kept}"
        # 负对照：不在保留集合里的线索该被丢掉（否则等于「全都保留」）
        assert "无关的线索" not in _kept, f"保留集合过宽：{_kept}"

        # ④ 分流壳：boundary 走老模板、decision 走新模板、关掉开关回老模板
        _b = m.render_landing({"orientation": "boundary",
                              "_config": {"actions": {}}, "views": {},
                              "decidability": {}})
        _d = m.render_landing({
            "orientation": "decision",
            "_config": {"actions": {"landing_decision": True}},
            "views": {"1": {"decidable_product": {
                "answer": "指派 排水公司 核查 内涝点位，汛期前完成，"
                          "否则回退人工排查。"}}},
            "decidability": {}})
        _off = m.render_landing({
            "orientation": "decision",
            "_config": {"actions": {"landing_decision": False}},
            "views": {}, "decidability": {}})
        assert "落地层（decision 模式）" not in _b, "boundary 不该走新模板"
        assert "落地层（decision 模式）" in _d, "decision 应走新模板"
        assert "落地层（decision 模式）" not in _off, "关开关应回老模板"
        assert "### 二、行动清单" in _d, "新模板缺行动清单段"

        print("  ✓ v1.22 阶段3：抽取(双形态+负对照) / 分流三分支 / 硬约束字面串 / "
              "行动清单段")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段3 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_v122_dup_dict_keys(SRC=None):
    """[v122 结构] 全文件 AST 扫描：任何 dict 字面量的常量键重复都判红。

    ★ 为什么要有这条：阶段 4 往 `DEFAULT_CONFIG["external_anchor"]` 加
      `as_evidence`，而那个键**已经存在** —— Python 的 dict 字面量后者胜，
      新值被静默丢掉，直到验收报 `as_evidence=False ∈ 五档` 才暴露。
      「同一个键写两遍」在 20k 行的配置块里靠人眼是查不出来的。
    """
    print("  · v1.22 结构：dict 字面量无重复常量键")
    try:
        import ast as _ast
        m = _v122_mod(SRC)
        f = getattr(m, "__file__", None) or SRC
        tree = _ast.parse(Path(f).read_text(encoding="utf-8"))
        dups = []
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Dict):
                continue
            seen = {}
            for k in node.keys:
                if k is None:
                    continue
                try:
                    kk = _ast.literal_eval(k)
                except Exception:
                    continue
                if not isinstance(kk, (str, int, float, bool, tuple)):
                    continue
                if kk in seen:
                    dups.append(f"line {getattr(k, 'lineno', '?')}: {kk!r}")
                seen[kk] = True
        assert not dups, "dict 重复键 " + str(len(dups)) + " 处：" + "；".join(dups[:6])
        print("  ✓ v1.22 结构：dict 字面量无重复常量键")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 结构 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
