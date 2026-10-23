#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.21.71 · smoke_test.py 打补丁（SRC 换版 + 新增 11 条 check_v71_*）

用法：
    python _mk_v71_smoke_patch.py

★ smoke_test.py 同样是**纯 CRLF**，所以走同一套 CRLF 往返 + 命中唯一断言。
"""
import sys
from pathlib import Path

F = Path(__file__).resolve().parent / "smoke_test.py"
raw = F.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "smoke_test.py 不是纯 CRLF"
assert raw.count("\r") == raw.count("\r\n"), "smoke_test.py 有裸 CR"
s = raw.replace("\r\n", "\n")

REPL = []


def add(tag, old, new):
    REPL.append((tag, old, new))


# ---------------------------------------------------------------- SRC
add("SRC换版",
    'SRC = HERE / "元DGTF-V1.21.70.py"',
    'SRC = HERE / "元DGTF-V1.21.71.py"')

# ---------------------------------------------------------------- 新检查
CHECKS = '''# ======================================================================
# [v1.21.71 F1~F11] 十一项缺陷修复的判据
#   每条都配**反方向**（不该被放过的仍被放过）或**负对照**（把改坏的
#   行为模拟出来，断言必须判失败）。
# ======================================================================
_V71_Q = "探针题：这套结构的边界在哪，哪些部分原则上判不出"


def _v71_packed_run(rounds=None, mode="serial"):
    """走生产入口 MetaDGTF.run（LLM 已被桩换掉）拿 packed 本体。

    ★ 不用 run_mode：它返回的是**汇总行**（views 被换成 key 列表），
      拿不到 packed 里的 view 字段。
    """
    CALLS["n"] = 0
    cfg = build_cfg(False)
    meta = mod.MetaDGTF(cfg)
    return meta.run(_V71_Q, route=["0", "1", "both", "all"],
                    rounds=rounds or {"0": 2, "1": 2, "both": 2, "all": 2},
                    parallel_mode=mode)


def _v71_b_state(view, rounds_hist):
    """造一个 total_rounds=1 的层状态（定点测 _b_finalize_layer）。"""
    cfg = build_cfg(False)
    return {
        "view": view, "total_rounds": 1,
        "roles_hist": list(rounds_hist),
        "all_candidates": [], "all_amps": [], "all_threads": [],
        "all_rehashed": [], "all_expanded_descs": [], "all_amp_cands": 0,
        "all_dec_products": [], "all_und_products": [], "all_view_errors": [],
        "round_log": [{"round": 1}], "deferred_notes": [],
        "r": 1, "rounds_n": 1, "sp": mod._spiral_for(cfg, "0")}


def check_v71_single_round_finalize():
    """[v1.21.71 F1] 单圈层必须走完整收尾。

    两方向 + 负对照：
      · 四层各 1 圈 → roles_run / rounds_cap / round_log / stop_reason
        四件套都在，且 rounds_cap == len(round_log)（自洽）；
      · 负对照：把旧的 `total_rounds <= 1` 门用子类装回去，**同一场景**
        必须退化成空 —— 否则这条判据压根不是在被改的那行上生效；
      · 源码反向断言：两处旧写法都不许再出现。
    """
    import inspect as _ins
    bad = []
    res = _v71_packed_run(rounds={"0": 1, "1": 1, "both": 1, "all": 1})
    for e in _ALL_LAYERS:
        v = res["views"].get(e) or {}
        cap = int(v.get("rounds_cap") or 0)
        rl = len(v.get("round_log") or [])
        rr = len(v.get("roles_run") or [])
        if rr <= 0 or cap <= 0 or rl <= 0:
            bad.append(f"[F1] 层 {e} 单圈收尾字段缺：roles_run={rr} "
                       f"rounds_cap={cap} round_log={rl}")
        elif cap != rl:
            bad.append(f"[F1] 层 {e} 不自洽：rounds_cap={cap} "
                       f"但 round_log={rl} 条")
        if not str(v.get("stop_reason") or "").strip():
            bad.append(f"[F1] 层 {e} 单圈没有 stop_reason")
    # 走满预算的交代必须是这句（别把单圈写成"未触发判据"以外的东西）
    _sr = str((res["views"].get("0") or {}).get("stop_reason") or "")
    if "体力耗尽" not in _sr:
        bad.append(f"[F1] 层 0 的单圈 stop_reason 不是「体力耗尽」交代：{_sr!r}")

    # ---- 定点 A/B：同一场景，一个带新代码、一个装回旧门 ----
    cfg = build_cfg(False)

    def _run_unit(meta):
        v = mod.View(entry="0")
        meta._b_state = {"0": _v71_b_state(v, ["摊开"])}
        meta._results = {}
        with contextlib.redirect_stdout(io.StringIO()):
            meta._b_finalize_layer("0")
        return list(v.roles_run), int(v.rounds_cap), len(v.round_log)

    _new = mod.MetaDGTF(cfg)
    _rr, _cap, _rl = _run_unit(_new)
    if not (_rr and _cap and _rl):
        bad.append(f"[F1] 定点：新代码下单圈层仍未收尾 "
                   f"roles_run={_rr} cap={_cap} log={_rl}")

    class _OldGate(mod.MetaDGTF):
        def _b_finalize_layer(self, entry):
            _st = self._b_state.get(entry)
            if _st and _st["view"] is not None and _st["total_rounds"] <= 1:
                return
            return super()._b_finalize_layer(entry)

    _old = _OldGate(cfg)
    _rr2, _cap2, _rl2 = _run_unit(_old)
    if _rr2 or _cap2 or _rl2:
        bad.append("[F1] 负对照失效：旧门装回去居然还写了收尾 "
                   f"roles_run={_rr2} cap={_cap2} log={_rl2}")

    if 'state["total_rounds"] <= 1' in _ins.getsource(
            mod.MetaDGTF._b_finalize_layer):
        bad.append("[F1] _b_finalize_layer 里旧门又回来了")
    if "if view is not None and rounds_n > 1:" in _ins.getsource(
            mod.MetaDGTF._run_layer):
        bad.append("[F1] _run_layer 里旧门又回来了")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F1] {m}")
        return False
    print("  \\u2713 [v71 F1] 单圈四层四件套齐全且自洽；旧门子类不写收尾"
          "（负对照有判别力）；两处旧写法都不在")
    return True


def check_v71_main_save_guard():
    """[v1.21.71 F2] main() 里 save_result 失败必须有兜底 + 非零退出码。

    两方向：
      · save_result 抛 OSError → SystemExit.code == 1 且打印「保存失败」；
      · save_result 正常 → 不抛、不打印（成功路径不许被 try 改变语义）。
    负对照：**改前的真实行为**已由 `_probe_v71_before.txt` [B] 记录
      （异常冲出 main()、无任何提示）—— 这里再用源码形态锁一次，
      防止有人把 try 拆掉而判据仍然通过。
    """
    import inspect as _ins
    bad = []
    _fake_res = {"llm_calls": 0, "llm_tokens": 0, "views": {},
                 "dispatch": {"order": ["0"], "missing": [], "skipped": []},
                 "question": _V71_Q}

    def _drive(save_impl):
        _orun, _osave = mod.MetaDGTF.run, mod.save_result
        mod.MetaDGTF.run = lambda self, *a, **k: dict(_fake_res)
        mod.save_result = save_impl
        _argv = sys.argv
        sys.argv = ["dgtf", _V71_Q, "--route", "0", "--rounds", "0:1",
                    "--parallel", "serial", "--quiet"]
        code, exc, buf = None, None, io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                mod.main()
        except SystemExit as _e:
            code = _e.code
        except BaseException as _e:                      # noqa: BLE001
            exc = f"{type(_e).__name__}: {_e}"
        finally:
            sys.argv = _argv
            mod.MetaDGTF.run, mod.save_result = _orun, _osave
        return code, exc, buf.getvalue()

    def _bad(*a, **k):
        raise OSError("冒烟：模拟磁盘写失败")

    code, exc, out = _drive(_bad)
    if exc:
        bad.append(f"[F2] 保存失败仍冲出 main()：{exc}")
    if code != 1:
        bad.append(f"[F2] 保存失败的退出码是 {code!r}，应为 1")
    if "保存失败" not in out:
        bad.append("[F2] 没有打印「保存失败」——失败不静默这一条没做到")
    code2, exc2, out2 = _drive(
        lambda *a, **k: Path(tempfile.gettempdir()) / "smoke71_never.md")
    if exc2 or code2 is not None:
        bad.append(f"[F2] 成功路径被 try 改变了行为：code={code2!r} "
                   f"exc={exc2!r}")
    if "保存失败" in out2:
        bad.append("[F2] 成功路径印了「保存失败」")
    _src = _ins.getsource(mod.main)
    _needle = ('    try:\\n        save_result(result, '
               'cfg["output"]["save_dir"])')
    if _needle not in _src:
        bad.append("[F2] main() 里的 save_result 不在 try 块内（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F2] {m}")
        return False
    print("  \\u2713 [v71 F2] 保存失败 → SystemExit(1) + 打印；成功路径不变；"
          "try 接线在")
    return True


def check_v71_build_inp_meta_filter():
    """[v1.21.71 F3] `_build_inp_meta` 的非法 entry 必须被**配对过滤**。

    两方向：
      · entry="9"（不存在）→ 不抛 KeyError、被剔除、且留痕两处；
      · entry=0/1（合法）→ **一条都不许丢**（否则"全丢掉"也能通过上面）。
    """
    import inspect as _ins
    bad = []
    cfg = build_cfg(False)
    m = mod.MetaDGTF(cfg)
    m._upstream_provider = lambda e: [mod.View(entry="9", manifest="上游形状正文")]
    try:
        inp = m._build_inp_meta([])
        if inp.upstream_views or inp.upstream_pools:
            bad.append("[F3] 非法 entry 的上游 view 没被剔除")
        if not str(getattr(m, "_build_inp_dropped", "")).strip():
            bad.append("[F3] 剔除了却没留痕（_build_inp_dropped 为空）")
    except Exception as e:
        bad.append(f"[F3] 非法 entry 仍打崩元层：{type(e).__name__}: {e}")

    m2 = mod.MetaDGTF(cfg)
    m2._upstream_provider = lambda e: [mod.View(entry="0", manifest="甲"),
                                       mod.View(entry="1", manifest="乙")]
    try:
        inp2 = m2._build_inp_meta([])
        if len(inp2.upstream_views) != 2 or len(inp2.upstream_pools) != 2:
            bad.append("[F3] 合法 entry 被误删：views="
                       + str([getattr(v, "entry", None)
                              for v in inp2.upstream_views])
                       + " pools=" + str(len(inp2.upstream_pools)))
        if str(getattr(m2, "_build_inp_dropped", "")).strip():
            bad.append("[F3] 合法 entry 也被报了剔除留痕")
    except Exception as e:
        bad.append(f"[F3] 合法 entry 路径崩了：{type(e).__name__}: {e}")
    if "_build_inp_dropped" not in _ins.getsource(mod.MetaDGTF._build_inp_meta):
        bad.append("[F3] 过滤逻辑没接线")
    # 连带把「上游是非法的」这条留痕也验一遍：它必须能被读出来
    if not _ins.getsource(mod.MetaDGTF._build_inp_meta).count("_pairs"):
        bad.append("[F3] 配对过滤的 _pairs 不在实现里")
    if bad:
        for m_ in bad:
            print(f"  \\u2717 [v71 F3] {m_}")
        return False
    print("  \\u2713 [v71 F3] 非法 entry 被剔除 + 留痕；合法 entry 一条不丢；"
          "接线在")
    return True


def check_v71_load_config_empty():
    """[v1.21.71 F4] `load_config("")` 不许报「读取  失败」。

    两方向：空路径 → 无警告；**真坏的 yaml** → 仍必须报「解析失败」
    （修过头会把这条判据变成"只要不报警就通过"）。
    """
    bad = []
    if not mod.HAS_YAML:
        print("  \\u26a0 [v71 F4] 环境无 pyyaml，本条无判别力 → 跳过")
        return True
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.load_config("")
    if "\\u26a0" in buf.getvalue():
        bad.append("[F4] load_config('') 仍在报错："
                   + repr(buf.getvalue().strip()[:70]))
    td = Path(tempfile.mkdtemp(prefix="smoke71_"))
    _badf = td / "bad.yaml"
    _badf.write_text("output:\\n  save_dir: a\\n   verbose: b\\n",
                     encoding="utf-8")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        mod.load_config(str(_badf))
    if "\\u26a0" not in buf2.getvalue():
        bad.append("[F4] 坏 yaml 不再报「解析失败」—— 修过头了")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F4] {m}")
        return False
    print("  \\u2713 [v71 F4] 空路径静默回落；坏 yaml 仍报解析失败")
    return True


def check_v71_early_dispatch():
    """[v1.21.71 F5] C / D-H 早退时 dispatch 不许为空。

    两方向：
      · route 里没有合法层 → dispatch 仍带 ran/missing/failed/skipped，
        且模式名是实际变量（C / 传入的 mode）；
      · 守卫**活着**的证明：dispatch 非空 + 计划里的层没产出 →
        `_layer_guard` 必须记 `layer_gap`；空 dispatch 则什么都记不到
        （这就是"守卫短路"本身，两个方向一起锁）。
    """
    bad = []
    cfg = build_cfg(False)
    for fn, want in (("_run_parallel_C", "C"), ("_run_parallel_stage", "G")):
        m = mod.MetaDGTF(cfg)
        m._dispatch_plan = m._plan_dispatch(["x"])
        m._failed_layers = {}
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                if fn == "_run_parallel_C":
                    pk = m._run_parallel_C(_V71_Q, ["x"], {}, {"0": 1}, None)
                else:
                    pk = m._run_parallel_stage("G", _V71_Q, ["x"], {},
                                               {"0": 1}, None)
        except Exception as e:
            bad.append(f"[F5] {fn} 早退崩了：{type(e).__name__}: {e}")
            continue
        d = pk.get("dispatch") or {}
        if not all(k in d for k in ("ran", "missing", "failed", "skipped")):
            bad.append(f"[F5] {fn} 早退的 dispatch 缺守卫键：{sorted(d)}")
        if d.get("_parallel_mode") != want:
            bad.append(f"[F5] {fn} 的 _parallel_mode={d.get('_parallel_mode')!r}"
                       f"，应为 {want!r}（模式名不许硬编码）")
    # 守卫的判别力（两个方向）
    m3 = mod.MetaDGTF(cfg)
    m3._results = {}
    m3._dispatch_plan = m3._plan_dispatch(["0"])
    _p_live = {"views": {}, "dispatch": m3._dispatch_for_pack("C")}
    with contextlib.redirect_stdout(io.StringIO()):
        m3._layer_guard(_p_live)
    if "layer_gap" not in _p_live:
        bad.append("[F5] dispatch 非空时守卫仍不报缺层（接线断了）")
    _p_dead = {"views": {}, "dispatch": {}}
    m3._layer_guard(_p_dead)
    if "layer_gap" in _p_dead:
        bad.append("[F5] 空 dispatch 居然也能报缺层 —— 判据前提不成立")
    if bad:
        for m_ in bad:
            print(f"  \\u2717 [v71 F5] {m_}")
        return False
    print("  \\u2713 [v71 F5] 两条早退路径的 dispatch 齐全（C / G 模式名）；"
          "守卫在非空 dispatch 下真会记 layer_gap")
    return True


def check_v71_ext_assess_cached():
    """[v1.21.71 F6] 同题的外部可判定性评估，一次 run 只跑一次。

    两方向 + 负对照：
      · 一次 run → `DGTF._assess_decidability` 恰好 1 次（改前 2 次）；
      · 缓存**可被清掉**：手动清空后同一题会再打一次（证明计数不是被
        别的东西压住的）；
      · 跨 run 不许复用：同一实例跑两次 → 各 1 次（共 2 次）。
    """
    bad = []
    cnt = {"n": 0}
    _orig = mod.DGTF._assess_decidability

    def _wrap(self, q):
        cnt["n"] += 1
        return _orig(self, q)

    mod.DGTF._assess_decidability = _wrap
    try:
        cfg = build_cfg(False)
        meta = mod.MetaDGTF(cfg)
        cnt["n"] = 0
        meta.run(_V71_Q, route=["0", "1", "both", "all"],
                 rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                 parallel_mode="serial")
        if cnt["n"] != 1:
            bad.append(f"[F6] 一次 run 打了 {cnt['n']} 次外部评估，应为 1")
        # ★ 缓存单测必须换一个**没跑过**的题：上面那次 run 已经把
        #   _V71_Q 填进缓存了，同题再调是缓存命中、不会增加计数。
        _q2 = _V71_Q + "（缓存单测）"
        meta._ext_assess_cache = {}
        meta._cached_ext_assess(_q2)
        _c1 = cnt["n"]
        meta._cached_ext_assess(_q2)
        _c2 = cnt["n"]
        if _c1 != 2 or _c2 != 2:
            bad.append(f"[F6] 缓存没生效：第一次调用后累计 {_c1} 次、"
                       f"重复调用后 {_c2} 次（应停在 2）")
        meta._ext_assess_cache = {}
        meta._cached_ext_assess(_q2)
        if cnt["n"] != 3:
            bad.append(f"[F6] 清掉缓存后仍只有 {cnt['n']} 次 —— 计数被压住了，"
                       f"上面那条判据没判别力")
        meta.run(_V71_Q, route=["0", "1", "both", "all"],
                 rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                 parallel_mode="serial")
        if cnt["n"] != 4:
            bad.append(f"[F6] 第二次 run 之后累计 {cnt['n']} 次，"
                       f"应为 4（每 run 一次）")
    finally:
        mod.DGTF._assess_decidability = _orig
    import inspect as _ins
    if "_ext_assess_cache" not in _ins.getsource(mod.MetaDGTF.run):
        bad.append("[F6] run() 里没有重置缓存（跨 run 会复用）")
    if "_cached_ext_assess" not in _ins.getsource(
            mod.MetaDGTF._assess_decidability_dynamic):
        bad.append("[F6] 动态评估那条没走缓存（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F6] {m}")
        return False
    print("  \\u2713 [v71 F6] 一次 run 只打 1 次外部评估；缓存可清（有判别力）；"
          "跨 run 各自一次")
    return True


def check_v71_evidence_full():
    """[v1.21.71 F7] 兜底重算与缓存同口径（用完整 evidence）。

    两方向 + 负对照：
      · 同一份 pool_res，缓存路与兜底路的 `_und_untraced` 必须相等；
      · 无 `_evidence_full` 的老数据 → 退回 `evidence`，不许崩；
      · 负对照：直接用**截断**的 evidence 重算必须与完整 evidence 不等
        —— 否则说明这个样例本身造不出口径差，判据没有判别力。
    """
    bad = []
    _asp = "清分规则未定，断面客流与线路客流不可互证"
    _full = [{"aspect": f"毫不相干的噪音条目第{i}条"} for i in range(8)] + \\
        [{"aspect": _asp}]
    _cached = mod._untraced_undecidable([_asp], _full)
    cfg = build_cfg(False)
    mt = mod.MetaDGTF(cfg)
    _ext = {"decidability": "undecidable", "decidable_aspects": [],
            "undecidable_aspects": [], "reason": "", "features": []}
    _pool = {"decidability": "undecidable", "undecidable_aspects": [_asp],
             "evidence": _full[:8], "_evidence_full": _full}
    _r1 = mt._merge_decidability(dict(_pool, _und_untraced=_cached), dict(_ext))
    _r2 = mt._merge_decidability(dict(_pool), dict(_ext))
    if _r1.get("_und_untraced") != _r2.get("_und_untraced"):
        bad.append(f"[F7] 两路口径仍不一致：缓存 {_r1.get('_und_untraced')!r} "
                   f"vs 兜底 {_r2.get('_und_untraced')!r}")
    if _r2.get("_und_untraced"):
        bad.append(f"[F7] 兜底仍把第 9 条的追溯判成无追溯："
                   f"{_r2.get('_und_untraced')!r}")
    # 老数据（没有 _evidence_full）必须仍能算，且等于用 evidence 重算
    _oldpool = {"decidability": "undecidable", "undecidable_aspects": [_asp],
                "evidence": _full[:8]}
    _r3 = mt._merge_decidability(dict(_oldpool), dict(_ext))
    _exp = sorted(mod._untraced_undecidable([_asp], _full[:8]))
    if _r3.get("_und_untraced") != _exp:
        bad.append(f"[F7] 老数据兜底值不对：{_r3.get('_und_untraced')!r} "
                   f"≠ {_exp!r}")
    # 负对照：截断口径必须与完整口径不等，否则样例没判别力
    if mod._untraced_undecidable([_asp], _full[:8]) == _cached:
        bad.append("[F7] 负对照失效：截断与完整的追溯判定相同，"
                   "这条判据验不出口径差")
    import inspect as _ins
    if "_evidence_full" not in _ins.getsource(
            mod.MetaDGTF._assess_decidability_from_pool_view):
        bad.append("[F7] 池评估没带出 _evidence_full（没接线）")
    if "_evidence_full" not in _ins.getsource(mod.MetaDGTF._merge_decidability):
        bad.append("[F7] 兜底分支没读 _evidence_full（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F7] {m}")
        return False
    print("  \\u2713 [v71 F7] 缓存 / 兜底同口径；老数据仍可算；"
          "截断口径确有差异（负对照有判别力）")
    return True


def check_v71_tokenize_stopwords():
    """[v1.21.71 F9] 停用词按**词**匹配。

    两方向：
      · 多字停用词被挡（的话 / 一种 / 进行 …）；
      · **内容词一个都不许丢**（螺旋 / 结构 / 整理），否则"全挡掉"也能过。
    负对照：`_STOPWORDS` 必须全是多字词 —— 退化成单字集合立刻失败。
    """
    bad = []
    _toks = mod._tokenize("如果我们通过一种方式进行整理的话，螺旋结构就浮现出来了")
    for w in ("的话", "一种", "进行", "我们", "通过"):
        if w in _toks:
            bad.append(f"[F9] 停用词「{w}」没被挡：{_toks}")
    for w in ("螺旋", "结构", "整理"):
        if w not in _toks:
            bad.append(f"[F9] 内容词「{w}」被误挡：{_toks}")
    if not all(len(w) >= 2 for w in mod._STOPWORDS):
        bad.append(f"[F9] _STOPWORDS 里还有单字："
                   f"{sorted(w for w in mod._STOPWORDS if len(w) < 2)}")
    if not all(len(c) == 1 for c in mod._STOPCHARS):
        bad.append("[F9] _STOPCHARS 不是单字集合（原名语义被改坏了）")
    if not mod._STOPCHARS:
        bad.append("[F9] _STOPCHARS 丢了 —— 原来挡了什么就无从查起")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F9] {m}")
        return False
    print(f"  \\u2713 [v71 F9] 停用词按词生效、内容词保留；"
          f"_STOPWORDS 全为多字（{len(mod._STOPWORDS)} 个）")
    return True


def check_v71_coverage_cfg_optional():
    """[v1.21.71 F10] `coverage_parts` 的 cfg 可选 + 调用点传真配置。

    两方向：
      · 省略 cfg 也能调（签名可选的直接证据）；
      · 传 cfg / 传 None 的结果必须**逐值相同**（当前实现不读 cfg，
        这条同时是"没有偷偷把 cfg 用起来"的反向锁）。
    """
    bad = []
    import inspect as _ins
    p = mod.Pool()
    try:
        _a = mod.coverage_parts(p)
    except Exception as e:
        bad.append(f"[F10] 省略 cfg 仍报错：{type(e).__name__}: {e}")
        _a = None
    _b = mod.coverage_parts(p, None)
    _c = mod.coverage_parts(p, {})
    _d = mod.coverage_parts(p, build_cfg(False))
    if _a is not None and not (_a == _b == _c == _d):
        bad.append(f"[F10] 四种传法的结果不一致：{_a} / {_b} / {_c} / {_d}")
    _src = _ins.getsource(mod.MetaDGTF._refresh_settlement)
    if 'coverage_parts(self.pools["1"], self.config)' not in _src:
        bad.append("[F10] _refresh_settlement 没传真配置（没接线）")
    if 'coverage_parts(self.pools["1"], {})' in _src:
        bad.append("[F10] _refresh_settlement 还在传空 dict")
    _sig = _ins.signature(mod.coverage_parts)
    if _sig.parameters["cfg"].default is _ins.Parameter.empty:
        bad.append("[F10] cfg 仍无默认值")
    elif _sig.parameters["cfg"].default is not None:
        bad.append(f"[F10] cfg 的默认值不是 None 而是 "
                   f"{_sig.parameters['cfg'].default!r}")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F10] {m}")
        return False
    print("  \\u2713 [v71 F10] cfg 可选（默认 None）且四种传法结果一致；"
          "调用点已传真配置")
    return True


def check_v71_no_dup_position_diag():
    """[v1.21.71 F11] 收尾复核不许重复写 position 诊断。

    两方向（这条最容易修过头 —— 一刀全关也能让"变少"成立）：
      · 收尾复核（`_finalize_layer_common` 那条）→ dump 尝试次数为 0；
      · **圈内那条仍必须写**：同一个全同 position 的 view 直接调
        `_quality_check`（默认 write_diag=True）→ 必须落盘一个文件；
        传 `write_diag=False` → 不落盘。
      · 真跑侧：一次四层跑里 `write_diag=False` 的调用数 == 层数（4）。
    """
    bad = []
    import inspect as _ins
    _att = {"in_finalize": 0, "in_round": 0, "wfalse": 0, "qc": 0,
            "flag": False}
    _ofin = mod.MetaDGTF._finalize_layer_common
    _odump = mod.DGTF._dump_position_diagnostic
    _oqc = mod.DGTF._quality_check

    def _fin(self, entry, view, state):
        _att["flag"] = True
        try:
            return _ofin(self, entry, view, state)
        finally:
            _att["flag"] = False

    def _dmp(self, *a, **k):
        _att["in_finalize" if _att["flag"] else "in_round"] += 1
        return _odump(self, *a, **k)

    def _qc(self, *a, **k):
        _att["qc"] += 1
        if k.get("write_diag") is False:
            _att["wfalse"] += 1
        return _oqc(self, *a, **k)

    mod.MetaDGTF._finalize_layer_common = _fin
    mod.DGTF._dump_position_diagnostic = _dmp
    mod.DGTF._quality_check = _qc
    try:
        _v71_packed_run()
    finally:
        mod.MetaDGTF._finalize_layer_common = _ofin
        mod.DGTF._dump_position_diagnostic = _odump
        mod.DGTF._quality_check = _oqc
    if _att["in_finalize"] != 0:
        bad.append(f"[F11] 收尾复核仍写了 {_att['in_finalize']} 次诊断")
    if _att["wfalse"] != len(_ALL_LAYERS):
        bad.append(f"[F11] write_diag=False 的调用数是 {_att['wfalse']}，"
                   f"应为 {len(_ALL_LAYERS)}（每层一次收尾复核）")

    # ---- 圈内那条必须仍然写（反向锁）----
    _td = Path(tempfile.mkdtemp(prefix="smoke71_diag_"))
    _cfg = build_cfg(False)
    _cfg["output"]["save_dir"] = str(_td)
    _dg = mod.DGTF("0", mod.LLM(_cfg), _cfg)
    _dg.verbose = False
    _v = mod.View(entry="0", anchor="锚")
    _v.candidates = [{"desc": "候选甲", "attribute": "0", "position": "0"},
                     {"desc": "候选乙", "attribute": "3", "position": "0"}]
    _pool = mod.Pool()
    _f_before = len(list(_td.glob("diagnostic_position_*.log")))
    _dg._quality_check(_v, _pool, 1)                      # 默认 True = 圈内
    _n_after_true = len(list(_td.glob("diagnostic_position_*.log")))
    if _n_after_true <= _f_before:
        bad.append("[F11] 圈内调用（默认 write_diag=True）居然不写诊断了 —— "
                   "修成了一刀全关")
    _dg._quality_check(_v, _pool, 1, write_diag=False)
    _n_after_false = len(list(_td.glob("diagnostic_position_*.log")))
    if _n_after_false != _n_after_true:
        bad.append("[F11] write_diag=False 仍写了文件")
    if "write_diag=False" not in _ins.getsource(
            mod.MetaDGTF._finalize_layer_common):
        bad.append("[F11] 收尾调用没传 write_diag=False（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F11] {m}")
        return False
    print(f"  \\u2713 [v71 F11] 收尾 0 次写入 / {_att['wfalse']} 次抑制；"
          f"圈内那条仍写（反向锁成立）")
    return True


def check_v71_auto_plan_agreement():
    """[v1.21.71 F8] 模块级 `auto_plan` 与方法级 `_auto_plan` 的一致性检测器。

    这是**给未来漂移用的报警器**，不是"修好了"：
      · 同一份 mock 输入（模式 + 逐层圈数）分别喂两实现 → mode 与
        （按 route 裁剪后的）rounds 必须逐字相同；
      · 负对照：子类把方法级那份的圈数改坏 → 必须判**不一致**
        （否则检测器没有判别力）。
    """
    bad = []

    class _Stub:
        def __init__(self, payload):
            self.payload = payload

        def call(self, *a, **k):
            return json.dumps(self.payload, ensure_ascii=False)

        def parse_json(self, raw):
            return json.loads(raw)

    def _cmp(rounds_in, mode_in="G", conf=0.8, cls=None):
        _cls = cls or mod.MetaDGTF
        _m = _cls(build_cfg(False))
        _m.llm = _Stub({"mode": mode_in, "rounds": dict(rounds_in),
                        "reason": "smoke", "confidence": conf})
        _p1 = _m._auto_plan("探针题：该怎么跑")
        _s2 = _Stub({"route": "full", "mode": mode_in,
                     "rounds": dict(rounds_in), "max_calls": 0,
                     "reason": "smoke", "confidence": conf})
        _oL = mod.LLM
        mod.LLM = lambda cfg: _s2
        try:
            _p2 = mod.plan_resources("探针题：该怎么跑", "decision",
                                     build_cfg(False))
        finally:
            mod.LLM = _oL
        _r2 = {k: v for k, v in _p2["rounds"].items() if k in _p2["route"]}
        return _p1["mode"], dict(_p1["rounds"]), _p2["mode"], _r2

    _cases = {"四层齐": {"0": 3, "1": 7, "both": 4, "all": 6},
              "只给两层": {"0": 5, "1": 5},
              "越界值": {"0": 1, "1": 99, "both": 2, "all": 2}}
    for tag, _rin in _cases.items():
        m1, r1, m2, r2 = _cmp(_rin)
        if m1 != m2 or r1 != r2:
            bad.append(f"[F8] {tag}：方法 {m1}/{r1} vs 模块 {m2}/{r2}")

    class _Drift(mod.MetaDGTF):
        def _auto_plan(self, question):
            _r = dict(super()._auto_plan(question))
            _r["rounds"] = {k: v + 1 for k, v in (_r.get("rounds") or {}).items()}
            return _r

    m1, r1, m2, r2 = _cmp({"0": 3, "1": 7, "both": 4, "all": 6}, cls=_Drift)
    if (m1, r1) == (m2, r2):
        bad.append("[F8] 负对照失效：把一份改坏了居然还判一致 —— "
                   "检测器没有判别力")
    import inspect as _ins
    _ds = mod.MetaDGTF._auto_plan.__doc__ or ""
    if "auto_plan" not in _ds or "plan_resources" not in _ds:
        bad.append("[F8] _auto_plan 的 docstring 没标注与模块级 auto_plan 的关系")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v71 F8] {m}")
        return False
    print("  \\u2713 [v71 F8] 三组输入两实现逐字一致；改坏一份立刻判不一致；"
          "关系已标注")
    return True


'''

add("插入11条检查",
    "def check_config_parses():",
    CHECKS + "def check_config_parses():")

# ---------------------------------------------------------------- 接线
_WIRE_OLD = """    if not check_v70_j_reuse():
        return 1
"""
_WIRE_NEW = """    if not check_v70_j_reuse():
        return 1
    if not check_v71_single_round_finalize():
        return 1
    if not check_v71_main_save_guard():
        return 1
    if not check_v71_build_inp_meta_filter():
        return 1
    if not check_v71_load_config_empty():
        return 1
    if not check_v71_early_dispatch():
        return 1
    if not check_v71_ext_assess_cached():
        return 1
    if not check_v71_evidence_full():
        return 1
    if not check_v71_tokenize_stopwords():
        return 1
    if not check_v71_coverage_cfg_optional():
        return 1
    if not check_v71_no_dup_position_diag():
        return 1
    if not check_v71_auto_plan_agreement():
        return 1
"""
add("main接线", _WIRE_OLD, _WIRE_NEW)

# ------------------------------------------------------------- 执行
print(f"打补丁：{F.name}（{len(REPL)} 处）")
fail = []
for tag, old, new in REPL:
    n = s.count(old)
    if n != 1:
        fail.append(f"{tag}: 命中 {n} 次（必须恰好 1 次）")
        continue
    s = s.replace(old, new, 1)
    print(f"   ✓ {tag}")
if fail:
    print("\n✗ 中止，未写文件：")
    for f in fail:
        print("   -", f)
    sys.exit(1)

import re as _re
_names = _re.findall(r"^def (check_v71_\w+)\(", s, _re.M)
assert len(_names) == 11, f"新增检查函数数 = {len(_names)}，应为 11"
assert len(set(_names)) == 11, "检查函数名有重复（重复插入）"
print(f"\n新增 check_v71_* 共 {len(_names)} 条：")
for _n in _names:
    print(f"   · {_n}")
assert 'SRC = HERE / "元DGTF-V1.21.71.py"' in s, "SRC 没换成 v71"

out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "回写后有裸 LF"
assert out.count("\r") == out.count("\r\n"), "回写后有裸 CR"
F.write_bytes(out.encode("utf-8"))
print(f"\n✓ 已写出 {F.name}（{out.count(chr(10))} 行按 LF 计）")
