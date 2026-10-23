# -*- coding: utf-8 -*-
"""v1.23.28 真跑核对后的修复补丁（F1 + F3）。

真跑核对产物（outputs/20261013_144044_*.packed.json）抓到的两项：

F1 — D3 `semantic_entropy` **结构性恒 1.0**（读数零信息量）
    根因：`refresh_belief_entropy` 把「本条目 text + **全池** structural_amps」
          拼成一个列表。全池 structural_amps 是 6 条**不同主张**，彼此
          sim < 0.70 ⇒ 每条 belief 都得到 6 个单元素簇 ⇒ h_norm ≡ ln6/ln6 = 1.0。
    修法：改为**按条目自身的历次独立出现**口径 —— 每次 `upsert_belief`
          把该次的 (来源标签, 该次文本) 记进条目的 `occurrences`；
          refresh 只对本条目自己的 occurrences 算发散度。
          n<2 ⇒ None（诚实缺省：单次出现谈「发散」无意义，0.0 会被读成「很稳」）。

F3 — `View.belief_items` **声明了、也出口了、但从不被赋值**
    （`View.to_dict = asdict(self)` ⇒ 该键恒 []），是 v1.23.27 那批
    「有出口无值」的同型体。修法：在 `_apply_view_to_pool_locked`
    里把本轮**由该 view 产出的**信念条目（活跃 + 本轮迁移）回填给 view。

★ 未修（已核实**不是**缺陷）：
  `Pool.to_dict` 的 `belief_transitions` 出口**存在**（L5038-5039）；
  真跑产物里键缺席是因为本次 6 条全 active、无迁移，被
  `if self.belief_transitions:` 守卫正确抑制 —— 这是设计行为，不是丢产物。

★ 本仓库铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → 转回 CRLF
  → **write_bytes**（write_text 会产出 \r\r\n 且不报错）。锚点断言命中 == 1。
"""
SRC = "元DGTF-V1.23.28.py"


def _load(path=SRC):
    """读入 → 断言纯 CRLF → **返回 LF 归一化文本**（锚点全按 LF 写）。"""
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0, "主文件必须是 CRLF"
    assert lf == 0, "主文件不是纯 CRLF（混入裸 LF %d 处）" % lf
    assert b.count(b"\r\r\n") == 0, "已存在 \\r\\r\\n"
    return b.decode("utf-8").replace("\r\n", "\n"), crlf, lf


def _save(txt, path=SRC):
    """LF 文本 → 转回 CRLF → **write_bytes**（write_text 会产出 \\r\\r\\n）。"""
    out = txt.replace("\r\n", "\n").replace("\n", "\r\n")
    data = out.encode("utf-8")
    assert data.count(b"\r\r\n") == 0, "写出前 \\r\\r\\n 非 0"
    open(path, "wb").write(data)


def patch(txt, name, old, new, count=1):
    n = txt.count(old)
    assert n == count, "[%s] 锚点命中 %d 次（期望 %d）" % (name, n, count)
    return txt.replace(old, new)


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    # ── F1a: 信念条目结构加 occurrences 字段 ──
    txt = patch(
        txt, "F1a-make-belief",
        '''        "semantic_entropy": semantic_entropy,
''',
        '''        "semantic_entropy": semantic_entropy,
        #: [D3 修正] 该条目**自身**的历次独立出现：(来源标签, 该次文本)。
        #: 语义熵只对**同一主张的历次出现**有意义 —— 不是「本条目 + 全池
        #: 其他条目」（那会把异质文本混进来，簇全异 ⇒ 熵恒为上界，读数无
        #: 信息量）。登记与去重解耦：同一 (源, 文本) 只记一次。
        "occurrences": [],
''',
    )

    # ── F1b: upsert_belief 记录本次出现 ──
    txt = patch(
        txt, "F1b-upsert-occ",
        '''        _tgt["rounds_seen"] = _rnd
        if ground and not _tgt.get("ground"):
            _tgt["ground"] = str(ground)
        _tgt["status"] = _new
''',
        '''        _tgt["rounds_seen"] = _rnd
        if ground and not _tgt.get("ground"):
            _tgt["ground"] = str(ground)
        # [D3 修正] 记本次出现：(来源标签, 本次文本)。
        #   ★ 来源标签取 `sources` 第一个（= 层名），无来源时用 "unknown"。
        #   ★ 同一 (源, 文本) 已记过则不重复 —— 「同一层同一次说完又说一遍」
        #     不是「两次独立出现」（本项目「重复面」老坑）。
        _occ = list(_tgt.get("occurrences") or [])
        _src_lab = "unknown"
        for _s0 in (sources or []):
            _s0 = str(_s0).strip()
            if _s0:
                _src_lab = _s0
                break
        _occ_keys = set()
        for _x in _occ:
            if isinstance(_x, (list, tuple)) and len(_x) >= 2:
                _occ_keys.add((str(_x[0]), str(_x[1])))
            else:
                _occ_keys.add(("unknown", str(_x)))
        if (_src_lab, _key) not in _occ_keys:
            _occ.append([_src_lab, _key])
        _tgt["occurrences"] = _occ
        _tgt["status"] = _new
''',
    )

    # ── F1c: refresh_belief_entropy 改为按 occurrences 算 ──
    txt = patch(
        txt, "F1c-refresh",
        '''        ★ 出现文本从哪来：`structural_amps`（历次独立提炼的原话）+ 条目
          自身的 `text`。**去重后**再算 —— 同一句话重复登记两次不是
          「两次独立出现」（那是本项目的「重复面」老坑）。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """
        _out = {}
        for _it in self.belief_items:
            _txt = [str(_it.get("text", "")).strip()]
            for _sa in (self.undecidable_channel.get("structural_amps") or []):
                _sa = str(_sa).strip()
                if _sa:
                    _txt.append(_sa)
            # 去重（保序）
            _seen = set()
            _uniq = []
            for _s in _txt:
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _uniq.append(_s)
            _hn, _h, _cl = semantic_entropy_of(_uniq, corpus=corpus,
                                               thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out
''',
        '''        ★ 出现文本从哪来（**修正后**）：该条目**自身**的 `occurrences`
          —— 每次 `upsert_belief` 记下的 (来源标签, 该次文本)。
          **不是**「本条目 text + 全池 structural_amps」：那样任何条目都会
          摊上一批**其他主张**的文本，簇必然全异 ⇒ `h_norm` 恒 = 1.0，
          读数**零信息量**（真跑核对抓到的退化，v1.23.28 修复）。
        ★ 去重口径：按 (源, 文本) —— 同一层同一句重说、或同一 (源,文本)
          重复登记，都不算「两次独立出现」。
        ★ `n < 2 ⇒ None`（诚实缺省）：只出现一次的条目**没有**发散度可言，
          返回 0.0 会被下游读成「很稳」—— 那是自欺。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """
        _out = {}
        for _it in self.belief_items:
            _txt = []
            _seen = set()
            _occs = list(_it.get("occurrences") or [])
            if not _occs:
                # 兼容：手工构造 / 老产物条目没有 occurrences ⇒ 退到
                # 「本条自己的 text」一条（n=1 ⇒ 熵 None，诚实缺省）。
                _occs = [["unknown", str(_it.get("text", "")).strip()]]
            for _oc in _occs:
                if isinstance(_oc, (list, tuple)):
                    _s = str(_oc[1]).strip() if len(_oc) > 1 else ""
                else:
                    _s = str(_oc).strip()
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _txt.append(_s)
            _hn, _h, _cl = semantic_entropy_of(_txt, corpus=corpus, thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _out[_it.get("id", "")] = _hn
        return _out
''',
    )

    # ── F3: 回填 view.belief_items（声明了却从不赋值的死字段）──
    txt = patch(
        txt, "F3-view-fill",
        '''        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM),
                   aspect_units=list(getattr(view, "aspect_units", None) or []))
''',
        '''        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM),
                   aspect_units=list(getattr(view, "aspect_units", None) or []))
        # [D1 回填] `View.belief_items` 之前是**声明了、也出口了、但从不
        #   被赋值**的死字段（`View.to_dict = asdict(self)` ⇒ 该键恒 []）。
        #   这里把该层**本轮产出**的信念条目回填给 view：
        #   ★ 只回填**与本次 view 相关**的条目（按 text 精确命中），
        #     不是把全池倒给每个 view —— view 是「这一圈看到了什么」。
        #   ★ 命中不到就保持 []（不猜、不兜底）。
        try:
            _seen_keys = set()
            for _a in (view.amps or []):
                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()
                if _t0:
                    _seen_keys.add(_t0)
            for _t0 in (view.anchor_touched or []):
                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()
                if _t0:
                    _seen_keys.add(_t0)
            if _seen_keys:
                _bind = []
                for _it in (pool.belief_items or []):
                    if str(_it.get("text", "")).strip() in _seen_keys:
                        _bind.append(_it)
                if _bind:
                    view.belief_items = _bind
        except Exception:
            pass
''',
    )

    _save(txt)
    txt2, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] F1a/F1b/F1c/F3 applied")


if __name__ == "__main__":
    main()
