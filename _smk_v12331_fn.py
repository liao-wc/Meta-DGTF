def check_v12331_memory_loop():
    """[v1.23.31] EML 经验记忆回路：跨跑储存记忆 + 每次跑自我学习与迭代。

    判据四层：源码级 / 纯函数级 / 真实入口级（**构造性证明「会学」**）/ 三态。
    判别力由 `_mut_v12331.py` 背书（M1~M10）。
    """
    import shutil as _sh
    import tempfile as _tf
    import time as _tm
    src = SRC.read_bytes().decode("utf-8")
    bad = []
    # ── 源码级 ──
    for _n, _w in (("def episode_from_result(", "episode"),
                   ("def eml_candidates_from_result(", "micro 候选"),
                   ("def gate_check(", "质量闸"),
                   ("def eml_merge_candidate(", "只增合并"),
                   ("def eml_promote(", "meso 升级"),
                   ("def eml_sweep_forget(", "遗忘清扫"),
                   ("def eml_recall(", "读"),
                   ("def eml_aggregate_macro(", "macro 聚合"),
                   ("def _eml_prepare(self, question: str)", "跑前读"),
                   ("def _eml_finish(self, result: dict)", "跑后写"),
                   ("def _eml_apply(self, rounds_plan: dict)", "生效面"),
                   ("EML 经验回路", "产物块")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    for _q in ("evidence", "contradiction", "verifiable", "redline"):
        if _q not in src:
            bad.append("[源码] 质量闸缺一问：%s" % _q)
    if "blocked_cost_only" not in src:
        bad.append("[源码] F2 双边记账（只省成本不升级）缺失")
    if "行数减少" not in src:
        bad.append("[源码] F5「只增不删」断言缺失")

    # ── 纯函数级 ──
    _good = {"kind": "schedule", "cond": {"issue": "cut"},
             "action": {"key": "rounds_delta", "layer": "1", "delta": 1},
             "readings": {"before": {"a": 1}, "after": {"b": 2}}}
    if not mod.gate_check(_good, [])[0]:
        bad.append("[闸] 正样本被判拒")
    if mod.gate_check({"kind": "s", "cond": {}, "action": {"key": "x"}},
                      [])[1] != "evidence":
        bad.append("[闸] 无读数未拒")
    if mod.gate_check({"kind": "s", "cond": {}, "action": {},
                       "readings": {"before": {"a": 1}}},
                      [])[1] != "verifiable":
        bad.append("[闸] 动作无 key 未拒")
    if mod.gate_check({"kind": "s", "cond": {},
                       "action": {"key": "inject_answer"},
                       "readings": {"before": {"a": 1}}},
                      [])[1] != "redline":
        bad.append("[闸] 触红线未拒（红线失守）")
    _pb = []
    _e1 = mod.eml_merge_candidate(_pb, dict(_good, evidence=["r1"]), 1.0)
    mod.eml_merge_candidate(_pb, dict(_good, evidence=["r1", "r2"]), 1.0)
    if len(_pb) != 1 or _pb[0].get("n_evidence") != 2:
        bad.append("[合并] 同键未累证据（行数=%d n_ev=%r）"
                   % (len(_pb), _pb[0].get("n_evidence")))
    if _e1.get("status") != "shadow":
        bad.append("[F1] 新条目不是 shadow")
    _a = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=0.0,
               cost_delta=-1.0, contra=0)]
    mod.eml_promote(_a, promote_n=3)
    if _a[0]["status"] != "shadow":
        bad.append("[F2] 只省成本的条目竟升级了（学坏）")
    _b = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=0.2,
               cost_delta=0.0, contra=0)]
    mod.eml_promote(_b, promote_n=3)
    if _b[0]["status"] != "active":
        bad.append("[meso] 正向证据够却未升级")
    _now = _tm.time()
    _c = [dict(_pb[0], status="active", t_last=_now - 400 * 86400,
               t_used=[], n_evidence=1)]
    mod.eml_sweep_forget(_c, _now, promote_n=3)
    if _c[0]["status"] != "retired" or len(_c) != 1:
        bad.append("[F4] 陈旧低证据未退休（或行被删）")
    _d = [dict(_pb[0], status="active", t_last=_now, t_used=[], n_evidence=1)]
    mod.eml_sweep_forget(_d, _now, promote_n=3)
    if _d[0]["status"] != "active":
        bad.append("[F4-负] 新条目被误清")
    _e = [{"id": "A1", "kind": "schedule", "status": "active", "t_last": _now,
           "n_evidence": 3, "weight": 1.0, "t_used": [],
           "action": {"key": "k1"}},
          {"id": "A2", "kind": "schedule", "status": "active", "t_last": _now,
           "n_evidence": 3, "weight": 1.0, "t_used": ["a", "b"],
           "action": {"key": "k2"}},
          {"id": "S1", "kind": "schedule", "status": "shadow", "t_last": _now,
           "n_evidence": 9, "weight": 1.0, "t_used": [],
           "action": {"key": "k3"}}]
    _ids = [x["id"] for x in mod.eml_recall(_e, "schedule", _now, top_k=5)]
    if "S1" in _ids:
        bad.append("[F1] shadow 竟进了 recall")
    if not _ids or _ids[0] != "A2":
        bad.append("[RRIF] 频率维失效（顺序 %r）" % _ids)
    _f = [{"id": "M1", "kind": "schedule", "status": "active",
           "cond": {"i": "cut"}, "action": {"key": "rounds_delta"}},
          {"id": "M2", "kind": "schedule", "status": "active",
           "cond": {"i": "cut"}, "action": {"key": "rounds_delta"}}]
    _snap = json.dumps(_f, ensure_ascii=False, sort_keys=True)
    if not mod.eml_aggregate_macro(_f, _now):
        bad.append("[macro] 未生成父条目")
    if json.dumps(_f, ensure_ascii=False, sort_keys=True) != _snap:
        bad.append("[macro] 子条目原文被改（ACE：不许重写/压缩）")

    # ── 真实入口：构造性证明「会学」──────────────────────
    _tmp = Path(_tf.mkdtemp(prefix="smk_eml_"))
    try:
        def _mkres(rid, cut=("1",)):
            return {"id": rid,
                    "question": "如何利用AI来帮助人类实现财富自由",
                    "route": ["0", "1", "both", "all"],
                    "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
                    "dispatch": {"_parallel_mode": "serial"},
                    "views": {e: {"stop_reason": (
                        "体力耗尽（3 圈走满）" if e in cut else "自然安住"),
                        "duty": {"S": 0.1 if e in ("0", "1") else 0.5}}
                        for e in ("0", "1", "both", "all")},
                    "pools": {"1": {"anchors": [], "web_results": []}},
                    "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
                    "_auto_dispatch": {"_history": {}}}
        _cfg = dict(mod.DEFAULT_CONFIG)
        _cfg["playbook"] = {"mode": "on", "dir": str(_tmp), "top_k": 3,
                            "promote_n": 3, "halflife_days": 14.0}
        _eng = mod.MetaDGTF(_cfg)
        for _i in range(1, 5):
            _eng._eml_finish(_mkres("RUN%d" % _i))
        if not (_tmp / "playbook.jsonl").is_file():
            bad.append("[入口] playbook 未落盘")
        if len(mod.eml_read_jsonl(_tmp / "episodes.jsonl")) < 4:
            bad.append("[入口] episodes 未逐跑落盘")
        _act = [e for e in mod.eml_read_jsonl(_tmp / "playbook.jsonl")
                if e.get("status") == "active"]
        if not _act:
            bad.append("[入口] 4 跑同向证据未升级（学不会）")
        else:
            _pre = _eng._eml_prepare("如何利用AI来帮助人类实现财富自由")
            if not (_pre.get("used_ids") or []):
                bad.append("[入口] 第 5 跑未读到 active")
            _rp = {"0": 3, "1": 3, "both": 3, "all": 4}
            _ap = _eng._eml_apply(_rp)
            if not _ap:
                bad.append("[入口] 第 5 跑未生效（on 模式下应改写生效面）")
            _blk = _eng._eml_finish(_mkres("RUN5"))
            if not (_blk.get("used") or []):
                bad.append("[入口] 使用未留痕进产物块")
            if "strengthen" not in _blk:
                bad.append("[入口] 访问加强/执行留痕缺失")
        if not (_tmp / "MEMORY.md").is_file():
            bad.append("[入口] MEMORY.md 未生成")
        _c2 = dict(mod.DEFAULT_CONFIG)
        _c2["playbook"] = {"mode": "off", "dir": str(_tmp)}
        _e2 = mod.MetaDGTF(_c2)
        _e2._eml_prepare("x")
        if _e2._eml_finish(_mkres("RX")).get("merged"):
            bad.append("[三态] off 竟写库")
        _c3 = dict(mod.DEFAULT_CONFIG)
        _c3["playbook"] = {"mode": "shadow", "dir": str(_tmp)}
        _e3 = mod.MetaDGTF(_c3)
        _e3._eml_prepare("如何利用AI来帮助人类实现财富自由")
        if _e3._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4}):
            bad.append("[三态] shadow 竟生效（F1 失守）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (_ex,))
    finally:
        _sh.rmtree(_tmp, ignore_errors=True)

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  OK v1.23.31 经验记忆回路（闸门/只增/双边/遗忘/RRIF/构造性证明会学）全过")
    return True


