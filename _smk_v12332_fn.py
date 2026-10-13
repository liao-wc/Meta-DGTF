def check_v12332_discipline():
    """[v1.23.32] 学科吸收六项：口径（α/κ）· 测量尺度 · 停因级联 · 成本两分 ·
    CSD 早期预警 · 判词阈值。

    判据四层（源码 / 纯函数 / 不变量 / 真实入口），每条带负对照。
    判别力由 `_mut_v12332.py` 背书（M1~M9）。
    """
    import tempfile as _tf
    src = SRC.read_bytes().decode("utf-8")
    bad = []

    # ── 源码级 ──
    for _n, _w in (("def krippendorff_alpha_ordinal(", "ordinal α"),
                   ("def weighted_kappa_pair(", "加权 κ"),
                   ("def rare_class_agreement(", "少数类一致"),
                   ("def alpha_verdict(", "α 判词"),
                   ("def reading_scale(", "尺度登记"),
                   ("def scale_word_violations(", "尺度禁词"),
                   ("def stop_priority(", "停因优先级"),
                   ("def stop_cascade(", "停因级联"),
                   ("def csd_indicators(", "CSD 指标"),
                   ("def _layer_csd_now(self, entry: str, view)", "CSD 接线"),
                   ("机会校正一致（ordinal）", "产物渲染"),
                   ("成本两分", "成本渲染")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    if "_LLM_EVAL_STAGES" not in src:
        bad.append("[源码] 成本两分的 stage 名单缺失")

    # ── 纯函数级（含负对照）──
    _perf = [["decidable"] * 3, ["partial"] * 3, ["undecidable"] * 3]
    _a = mod.krippendorff_alpha_ordinal(_perf)
    if not _a or abs(_a["alpha"] - 1.0) > 1e-9:
        bad.append("[α] 完美一致未得 1（%r）" % (_a,))
    if mod.krippendorff_alpha_ordinal([["decidable", "decidable"]]) is not None:
        bad.append("[α] 样本不足未返回 None（会印 0 冒充读数）")
    _skew = [["decidable"] * 3] * 9 + [["decidable", "partial", "undecidable"]]
    _ask = mod.krippendorff_alpha_ordinal(_skew)
    if not (_ask and _ask["alpha"] < 0.75):
        bad.append("[α] 偏斜夹具下 α 未被机会校正拉低（%r）" % (_ask,))
    if "可靠" not in mod.alpha_verdict(0.85) or \
            "不可靠" not in mod.alpha_verdict(0.40):
        bad.append("[α] 判词未按 Krippendorff 阈值分级")
    _rc = mod.rare_class_agreement(
        [["undecidable"] * 3, ["undecidable", "partial", "decidable"],
         ["decidable"] * 3], "undecidable")
    if not (_rc and _rc["units"] == 2 and abs(_rc["rate"] - 0.5) < 1e-9):
        bad.append("[少数类] 未筛类或一致率算错（%r）" % (_rc,))
    if mod.reading_scale("tri_state_agreement") != "ordinal":
        bad.append("[尺度] 三态一致率未登记为定序")
    if mod.reading_scale("绝不存在的读数") != "unknown":
        bad.append("[尺度] 未登记读数未返回 unknown（会默认当 interval）")
    if mod.scale_word_violations("一致率均值 0.5", "ordinal") != ["均值"]:
        bad.append("[尺度] 定序禁词未命中")
    if mod.scale_word_violations("一致率均值 0.5", "ratio") != []:
        bad.append("[尺度·负] 比例读数被误禁")
    _cas = mod.stop_cascade(["体力耗尽（4 圈走满）", "悬置决定稳定，自然安住"])
    if _cas["primary"] != "悬置决定稳定，自然安住":
        bad.append("[级联] 优先级未生效（主因=%r）" % _cas["primary"])
    if _cas["primary"] not in _cas["all"]:
        bad.append("[级联] ★主因不在全部触发里（报告即实际被破坏）")
    if mod.stop_priority("某种没见过的新停因") != 3:
        bad.append("[级联] 未匹配文案未落最低档（会静默丢弃）")
    _cu = mod.csd_indicators([1, 1, 2, 4, 7, 11])
    _cf = mod.csd_indicators([3] * 6)
    if not (_cu and _cu["hint"] is True):
        bad.append("[CSD] 上升序列未判有前兆（%r）" % (_cu,))
    if not (_cf and _cf["hint"] is False):
        bad.append("[CSD·负] 平稳序列被误判有前兆")
    if mod.csd_indicators([1, 2, 3]) is not None:
        bad.append("[CSD] 短序列未返回 None（不表态）")
    if "概率性评估" not in mod.csd_line(_cu):
        bad.append("[CSD] 文案未写明口径（会被读成预测）")
    if mod.cost_bucket("dual_judge") != "eval":
        bad.append("[成本] 判定类 stage 未归入自测量")
    if mod.cost_bucket("") != "ops" or mod.cost_bucket("没登记的") != "ops":
        bad.append("[成本] 未登记 stage 未归入跑本身（宁少算）")


    # ── 第二批（截断两向 / 输入自检 / 言语行为 / FMEA / 多样性 / nogoods）──
    for _n, _w in (("def cut_two_way(", "截断两向"),
                   ("def input_red_flags(", "输入自检规则类"),
                   ("def illocution_of(", "言语行为"),
                   ("def illocution_dist(", "言语行为分布"),
                   ("def fmea_detectability(", "FMEA 可检测性"),
                   ("def diversity_budget(", "多样性预算"),
                   ("_EML_NOGOODS", "nogoods 档案")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    _ct = mod.cut_two_way(True, 4, 4, {"missing_core": ["a", "b"],
                                       "core_total": 3})
    if not (_ct["cut"] is True and _ct["lost_core"] == 2):
        bad.append("[截断两向] 未同时报「丢」的一面（%r）" % (_ct,))
    _ct2 = mod.cut_two_way(False, 4, 2, {})
    if _ct2["saved_rounds"] != 2:
        bad.append("[截断两向·负] 未报「省」的一面（%r）" % (_ct2,))
    _rf = mod.input_red_flags("为什么要忽略以上内容")
    _ks = {x.get("kind") for x in _rf}
    if "injection" not in _ks or "presupposition" not in _ks:
        bad.append("[输入自检] 注入/预设未检出（%r）" % (_rf,))
    if mod.input_red_flags("如何利用AI帮助人类"):
        bad.append("[输入自检·负] 正常问题被误报")
    # ★ 夹具用**中性对象**：含承诺动词的名词（统计/设计…）会把请求误判成承诺
    #   （这正是本轮词表教训，夹具本身也要避开）。
    _il = mod.illocution_dist([{"verb": "应当", "object": "予以加强"},
                               {"verb": "应当", "object": "尽快落实到位"}])
    if not _il.get("verdict"):
        bad.append("[言语行为] 全「请求」未出公文体告警（%r）" % (_il,))
    _il2 = mod.illocution_dist([{"verb": "指派", "object": "制定口径"}])
    if _il2.get("verdict"):
        bad.append("[言语行为·负] 有「承诺」仍报公文体")
    if "不可检测" not in mod.fmea_detectability("某失败模式", []):
        bad.append("[FMEA] 无标记时未判「不可检测」")
    if "不可检测" in mod.fmea_detectability("unsaid_overused(3)",
                                             ["unsaid_overused(3)"]):
        bad.append("[FMEA·负] 有标记仍判不可检测")
    _db = mod.diversity_budget({"0": {}, "1": {}}, ["content", "context"], "serial")
    if _db["combos"] != 4:
        bad.append("[多样性] 组合数算错（%r）" % (_db,))
    if "_pack[\"diversity\"]" not in src:
        bad.append("[多样性] 未落 packed")

    # ★ [nogoods] 纯函数直测（确定性；不依赖引擎构造 —— 引擎路径容易「没跑到」）
    _nr = mod.nogood_record("gate_reject", "redline", {"k": 1}, "R1", 5.0)
    if not (str(_nr.get("kind")) == "gate_reject"
            and str(_nr.get("why")) == "redline"
            and str(_nr.get("run")) == "R1"
            and isinstance(_nr.get("cand"), dict)):
        bad.append("[nogoods] 记录内容不符（%r）" % (_nr,))
        # ★ [nogoods] **行为**判据（不能只看常量在不在）：
        #   猴补丁让候选必被闸拒（红线类）⇒ `nogoods.jsonl` 必须落一行。
        try:
            _ngdir = Path(_tf.mkdtemp(prefix="smk_ng_"))
            _cfg2 = dict(mod.DEFAULT_CONFIG)
            _cfg2["playbook"] = {"mode": "on", "dir": str(_ngdir)}
            _e2 = mod.MetaDGTF(_cfg2)
            _orig_c = mod.eml_candidates_from_result

            def _fake_cands(_r, ep=None):
                return [{"kind": "schedule", "cond": {"issue": "x"},
                         "action": {"key": "inject_answer"},
                         "readings": {"before": {"a": 1}},
                         "evidence": ["R1"], "source": "test"}]

            mod.eml_candidates_from_result = _fake_cands
            try:
                _e2._eml_finish({"id": "NG1", "question": "x", "views": {},
                                 "pools": {}, "dispatch": {}, "rounds": {}})
            finally:
                mod.eml_candidates_from_result = _orig_c
            _ngf = _ngdir / "nogoods.jsonl"
            _ngrows = mod.eml_read_jsonl(_ngf) if _ngf.is_file() else []
            if len(_ngrows) < 1:
                bad.append("[nogoods] ★ 被闸拒的候选未写进矛盾档案（append-only）")
            elif not (str(_ngrows[0].get("why")) == "redline"
                      and str(_ngrows[0].get("kind")) == "gate_reject"):
                bad.append("[nogoods] 档案内容不对（kind/why）=%r" % (_ngrows[0],))
            import shutil as _sh2
            _sh2.rmtree(_ngdir, ignore_errors=True)
        except Exception as _en:
            bad.append("[nogoods] 行为判据异常：%r" % (_en,))


    # ── 第三批（机制级：anytime / 发散+指针 / bandit / compact / 锚点 / 裁决 / 陈旧）──
    for _n, _w in (("def stitched_hoeffding_lower(", "anytime 置信序列"),
                   ("def anytime_majority_decided(", "anytime 判据"),
                   ("def divergence_state(", "发散三态"),
                   ("def best_round_index(", "回滚指针"),
                   ("class BudgetBandit:", "预算 bandit"),
                   ("def compact_plan(", "compact 预算"),
                   ("def anchor_offline_check(", "锚点离线验证"),
                   ("def anchor_interest_hint(", "锚点内部批判"),
                   ("def anchor_evidence_standard(", "分级证明标准"),
                   ("def adjudication_aspect(", "裁决维度"),
                   ("def belief_staleness(", "信念陈旧度"),
                   ("anytime_ok=_any_ok", "anytime 接线")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    # anytime：12 个 1 ⇒ 下界 > 0.5 判「已确立」；3 个 1 ⇒ 样本不足不判（负对照）
    _lb = mod.stitched_hoeffding_lower([1] * 12)
    if not (_lb and _lb["lower"] > 0.5):
        bad.append("[anytime] 全 1 序列下界未 > 0.5（%r）" % (_lb,))
    if mod.anytime_majority_decided([1, 1, 1])[0]:
        bad.append("[anytime·负] 3 个样本就判「已确立」（过早）")
    if mod.stitched_hoeffding_lower([1]) is not None:
        bad.append("[anytime] n<2 未返回 None")
    # 发散/停滞/指针
    _dv = mod.divergence_state([1, 1, 2, 4, 8, 16])
    if not (_dv and _dv["state"] == "发散"):
        bad.append("[发散] 方差上升序列未判发散（%r）" % (_dv,))
    if mod.divergence_state([3] * 6)["state"] != "停滞":
        bad.append("[发散·负] 平稳序列未判停滞")
    if mod.best_round_index([1, 3, 2, 0]) != 2:
        bad.append("[指针] 历史最佳圈指针算错")
    # bandit：未试过的臂优先（确定性探索）；更新后仍可选
    _bb = mod.BudgetBandit([{"rounds": 3}, {"rounds": 4}, {"rounds": 6}])
    _p0 = _bb.pick()
    if not (_p0["explore"] is True and _p0["index"] == 0):
        bad.append("[bandit] 首挑未走确定性探索（%r）" % (_p0,))
    _bb.update(0, 0.9, 1.0)
    if _bb.n[0] != 1 or abs(_bb.mean[0] - 0.9) > 1e-9:
        bad.append("[bandit] 更新未生效（%r/%r）" % (_bb.n, _bb.mean))
    # compact（率失真口径）
    if not mod.compact_plan(900, 1000)["over"]:
        bad.append("[compact] 超预算未判 over")
    if mod.compact_plan(300, 1000)["over"]:
        bad.append("[compact·负] 预算内被误判超")
    # 锚点三项
    if not mod.anchor_offline_check("https://www.gov.cn/a")["ok"]:
        bad.append("[锚点] 合法 URL 未过离线检查")
    if mod.anchor_offline_check("htp:/x")["ok"]:
        bad.append("[锚点·负] 畸形 URL 竟通过")
    if "媒体" not in mod.anchor_interest_hint("https://blog.medium.com/x"):
        bad.append("[锚点·内部批判] 自媒体域名未识别")
    if mod.anchor_evidence_standard("causal")["standard"] != "beyond_reasonable_doubt":
        bad.append("[法学] 因果 claim 未用最高证明标准")
    # 裁决维度 + 陈旧度
    if not mod.adjudication_aspect("口径矛盾", "按实测数据").strip():
        bad.append("[裁决维度] 未判出维度")
    _st = mod.belief_staleness({"id": "B", "status": "active",
                                "last_confirmed_round": 1}, 5)
    if not (_st["age"] == 4 and _st["stale_hint"] is True):
        bad.append("[陈旧度] 读数不对（%r）" % (_st,))

        # ★ [层读数进产物] **行为判据**：走真实 `save_result`，断言产物 md
        #   里出现 6 个新读数块（真跑曾暴露「只进 verbose 转储」的缺口）。
        try:
            import tempfile as _tf3
            _d3 = Path(_tf3.mkdtemp(prefix="smk_lay_"))
            _pool3 = {"amps": [], "threads": [], "probes": [], "meta": [],
                      "suspensions": [], "aspect_units": [], "belief_items": [],
                      "anchors": [], "duel_suspensions": [], "aspect_targets": {}}
            _r3 = {"question": "层读数验收题", "route": ["0", "1"],
                   "rounds": {"0": 1, "1": 1},
                   "dispatch": {"order": ["0", "1"], "ran": ["0", "1"],
                                "requested": ["0", "1"], "missing": [],
                                "failed": {}, "skipped": [],
                                "_parallel_mode": "serial"},
                   "keep": {"0": "all", "1": "all"},
                   "_anchor_tier_warning": "", "_anchor_answers_filtered": 0,
                   "views": {},
                   "pools": {k: dict(_pool3) for k in ("0", "1", "both", "all")},
                   "llm_calls": 2, "llm_tokens": 20, "llm_ops_calls": 1,
                   "llm_ops_tokens": 10, "llm_eval_calls": 1,
                   "llm_eval_tokens": 10,
                   "compact": {"inner_share": 0.9, "budget": 0.6, "over": True,
                               "verdict": "内部面超预算 ⇒ 索引化"},
                   "belief_staleness": {"n": 5, "stale_n": 2, "max_age": 4},
                   "diversity": {"layers": 2, "channels": 3, "combos": 6,
                                 "mode": "serial", "note": "x"}}
            _v3 = mod.View(entry="0")
            _v3.stop_primary = "悬置决定稳定，自然安住"
            _v3.divergence = {"state": "发散", "var_first": 1.0,
                              "var_last": 4.0, "ac1": 0.4}
            _v3.best_round = 2
            _v3.anytime = {"n": 6, "lower": 0.44, "delta": 0.05}
            _v3.csd = {"new_amps": {"hint": True}}
            _r3["views"]["0"] = _v3.to_dict()
            _md3 = Path(mod.save_result(_r3, str(_d3))).read_text(encoding="utf-8")
            for _k3 in ("层读数（每层）", "三态=发散", "历史最佳=第2圈",
                        "anytime下界=0.440", "内部面预算", "信念陈旧度"):
                if _k3 not in _md3:
                    bad.append("[层读数] 产物里缺 %r（只进了 verbose 转储？）" % _k3)
            import shutil as _sh3
            _sh3.rmtree(_d3, ignore_errors=True)
        except Exception as _e3:
            bad.append("[层读数] 行为判据异常：%r" % (_e3,))

    # ── 真实入口 + 不变量 ──
    _tmp = Path(_tf.mkdtemp(prefix="smk_v1232_"))
    try:
        cfg = dict(mod.DEFAULT_CONFIG)
        cfg["playbook"] = {"mode": "shadow", "dir": str(_tmp)}
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["save_dir"] = str(_tmp)
        eng = mod.MetaDGTF(cfg)
        v = mod.View(entry="1")
        v.round_log = [{"round": i + 1, "new_amps": x, "idle_stall": 0}
                       for i, x in enumerate([1, 1, 2, 4, 7])]
        d = eng._layer_csd_now("1", v)
        if not (v.csd and v.csd.get("new_amps")):
            bad.append("[入口] CSD 未写回 view.csd（%r）" % (d,))
        # LLM 计数不变量：ops + eval == total（两向）
        _l = eng.llm
        for _attr in ("ops_calls", "ops_tokens", "eval_calls", "eval_tokens"):
            if not hasattr(_l, _attr):
                bad.append("[入口] LLM 缺计数属性 %s" % _attr)
        if hasattr(_l, "ops_calls") and \
                (_l.ops_calls + _l.eval_calls) != _l.total_calls:
            bad.append("[入口] 成本两分之和 != 总调用（%d+%d vs %d）"
                       % (_l.ops_calls, _l.eval_calls, _l.total_calls))
        # 停因级联：主因必须出现在最终 stop_reason 里
        v2 = mod.View(entry="1")
        v2.stop_reason = "体力耗尽（4 圈走满，未触发任何停止判据）"
        v2.stop_primary = ""
        _cas2 = mod.stop_cascade([v2.stop_reason, "悬置决定稳定，自然安住"])
        v2.stop_primary = _cas2["primary"]
        v2.stop_reason = " + ".join(_cas2["ordered"]) + "，螺旋停止"
        if v2.stop_primary not in v2.stop_reason:
            bad.append("[入口] ★主因不在 stop_reason 里（报告即实际被破坏）")
        # 渲染可达性（**两向**：出口在 + 渲染点真的读到它）。
        # ★ 口径说明：这里走源码级而**不是**驱动 `save_result` —— 后者需要
        #   一份完整 packed 夹具（视图/池全字段），而冒烟其它判据已端到端跑过
        #   它（真 mock 跑 + 落盘）。两向断言足以钉住「出口与渲染点成对存在」：
        #   删任一方向都会判红。
        for _k, _what in (("tri_alpha", "机会校正一致"),
                          ("llm_ops_calls", "成本两分（跑本身）"),
                          ("llm_eval_calls", "成本两分（自测量）")):
            if ('_pack["%s"]' % _k) not in src:
                bad.append("[渲染] 出口缺失：%s" % _k)
        for _s, _what in (("机会校正一致（ordinal）", "机会校正一致行"),
                          ("成本两分", "成本两分行"),
                          ("三态判决一致率（原始）", "原始一致率标注")):
            if _s not in src:
                bad.append("[渲染] 渲染点缺失：%s" % _what)
    except Exception as _e:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  OK v1.23.32 学科吸收（α/κ · 尺度 · 级联 · 成本两分 · CSD）全过")
    return True


