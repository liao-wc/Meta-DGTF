# -*- coding: utf-8 -*-
from pathlib import Path

p = Path("元DGTF-V1.23.66.py")
t = p.read_text(encoding="utf-8")

def rep(old, new, n=1):
    global t
    assert old in t, "NOT FOUND: " + old[:80]
    t = t.replace(old, new, n)

# 1) anytime: growth sequence is inverted before judging stagnation
rep('''                    _any_ok = bool(anytime_decided(
                        [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5,
                        mode=str(getattr(self, "_anytime_mode", "hoeffding"))
                    )[0])''',
'''                    _any_ok = bool(anytime_stagnant_decided(
                        [int(r.get("new_amps", 0) or 0)
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5,
                        mode=str(getattr(self, "_anytime_mode", "hoeffding"))
                    )[0])''')
rep('''                _any_ok = bool(anytime_decided(
                    [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                     for r in (view.round_log or [])], delta=_aa, thr=0.5,
                    mode=str(getattr(self, "_anytime_mode", "hoeffding")))[0])''',
'''                _any_ok = bool(anytime_stagnant_decided(
                    [int(r.get("new_amps", 0) or 0)
                     for r in (view.round_log or [])], delta=_aa, thr=0.5,
                    mode=str(getattr(self, "_anytime_mode", "hoeffding")))[0])''')

rep('''            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。''',
'''            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。
            #   判的是「不再长」：生长序列取反后，多数圈没新增结构才停。
            #   此前直接用生长序列判「多数在长 ⇒ 停」，会把仍在产出的层提前停掉。''')

rep('''                    "结构增长已 anytime-valid 地判停（「仍在长」下界 < 0.5，"
                    "对任意停时有效）")''',
'''                    "结构增长已 anytime-valid 地判停（「不再长」下界 > 0.5，"
                    "对任意停时有效）")''')

rep('''# ── F2 保形预测 ──────────────────────────────────────────────''',
'''def anytime_stagnant_decided(seq, delta: float = 0.05, thr: float = 0.5,
                             mode: str = "hoeffding"):
    """「多数圈不再长」的 anytime-valid 停止判据（生长序列取反）。

    输入 seq 是每圈的新增结构数（new_amps）。把「有新增」映射为 0、
    「无新增」映射为 1，再走 anytime_decided：下界 > 0.5 ⇒ 多数圈确实
    没再长。这样停的是停滞层，不会把仍在产出的层提前停掉。
    """
    growth = [0 if int(x or 0) > 0 else 1 for x in (seq or [])]
    ok, info = anytime_decided(growth, delta=delta, thr=thr, mode=mode)
    info = dict(info or {})
    info["basis"] = "stagnant"
    info["mode"] = str(mode or "hoeffding")
    return bool(ok), info


# ── F2 保形预测 ──────────────────────────────────────────────''')

# 2) pool window honors spiral.shape_limit
rep('''    def _pool_text(self, pool: Pool) -> str:
        if not self.use_content:
            return "（内容通道未开：本次不读历史）"
        lines = []''',
'''    def _pool_text(self, pool: Pool) -> str:
        if not self.use_content:
            return "（内容通道未开：本次不读历史）"
        # ★ 池窗口与 view 窗口同源：spiral.shape_limit 设为 N 时，池也只列
        #   最近 N 条。此前这里硬编码 8，配置调到 6/4 对池不生效（成本没降）。
        _lim = 8
        try:
            _sl = int((self.config.get("spiral") or {}).get(
                "shape_limit", 0) or 0)
            if _sl > 0:
                _lim = _sl
        except Exception:
            _lim = 8
        lines = []''')

_a = t.index("    def _pool_text(self, pool: Pool) -> str:")
_b = t.index("    # ---------- 候选行解析 ----------", _a)
_seg = t[_a:_b]
assert _seg.count("[-8:]") == 4, _seg.count("[-8:]")
t = t[:_a] + _seg.replace("[-8:]", "[-_lim:]") + t[_b:]

# 3) LLM: json repair + per-stage stats
rep('''        self.eval_calls = 0
        self.eval_tokens = 0
        # [fix-98] 上一次调用的 finish_reason''',
'''        self.eval_calls = 0
        self.eval_tokens = 0
        # ★ JSON 自修复：json_mode 解析失败时，用一次低温修复调用把
        #   「答了但答不成结构」救回来；默认关，配置 api.json_repair=true 开。
        self.json_repair = bool(api_cfg.get("json_repair", False))
        self.json_repaired = 0
        self.json_repair_failed = 0
        # ★ 分环节成本：只做读数，不改控制流。键 = stage，值 = calls/tokens/ms。
        self.stage_calls: Dict[str, int] = {}
        self.stage_tokens: Dict[str, int] = {}
        self.stage_ms: Dict[str, int] = {}
        # [fix-98] 上一次调用的 finish_reason''')

rep('''        last_err = None
        # ★ [脚枪]''',
'''        last_err = None
        _t0 = time.monotonic()
        # ★ [脚枪]''')

rep('''                    else:
                        self.ops_calls += 1
                        self.ops_tokens += _tk
                    _tok_calls, _tok_total = (
                        self.total_calls, self.total_tokens)''',
'''                    else:
                        self.ops_calls += 1
                        self.ops_tokens += _tk
                    _sn = str(stage or "unknown")
                    self.stage_calls[_sn] = self.stage_calls.get(_sn, 0) + 1
                    self.stage_tokens[_sn] = self.stage_tokens.get(_sn, 0) + _tk
                    self.stage_ms[_sn] = self.stage_ms.get(_sn, 0) + int(
                        (time.monotonic() - _t0) * 1000)
                    _tok_calls, _tok_total = (
                        self.total_calls, self.total_tokens)''')

rep('''                            logger.warning(
                                "json_mode 但解析失败（累计 %d 次，stage=%s）：%r",
                                self.bad_json, stage, content[:80])
                    return content''',
'''                            logger.warning(
                                "json_mode 但解析失败（累计 %d 次，stage=%s）：%r",
                                self.bad_json, stage, content[:80])
                        if not _ok_json and self.json_repair:
                            _fixed = self._repair_json(content, stage)
                            if _fixed is not None:
                                with self._lock:
                                    self.json_repaired += 1
                                logger.info("json 自修复成功（stage=%s）", stage)
                                return _fixed
                            with self._lock:
                                self.json_repair_failed += 1
                    return content''')

rep('''    @staticmethod
    def parse_json(raw: str) -> Optional[dict]:''',
'''    def _repair_json(self, raw: str, stage=None) -> Optional[str]:
        """把解析失败的 json_mode 输出修成严格 JSON；失败返回 None。

        只修格式（引号/逗号/括号/尾注），不改语义；一次调用，无重试。
        成本计入 ops（自测量），不混进跑本身。
        """
        if not raw or not str(raw).strip():
            return None
        _sys = ("你是 JSON 修复器。只修格式：补引号、逗号、括号，去掉解释与"
                " markdown 围栏；**不改语义**。只输出一个合法 JSON 对象。")
        _user = "把下面内容修成严格 JSON：\\n\\n" + str(raw)[:12000]
        _mx = min(4000, max(512, len(str(raw)) // 2))
        try:
            resp = self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "system", "content": _sys},
                          {"role": "user", "content": _user}],
                temperature=0.0,
                max_tokens=_mx,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content or self.parse_json(content) is None:
                return None
            _tk = 0
            try:
                _tk = int(getattr(getattr(resp, "usage", None),
                                 "total_tokens", 0) or 0)
            except Exception:
                _tk = 0
            with self._lock:
                self.total_calls += 1
                self.total_tokens += _tk
                self.ops_calls += 1
                self.ops_tokens += _tk
                _sn = "json_repair"
                self.stage_calls[_sn] = self.stage_calls.get(_sn, 0) + 1
                self.stage_tokens[_sn] = self.stage_tokens.get(_sn, 0) + _tk
                self.stage_ms[_sn] = self.stage_ms.get(_sn, 0)
                logger.info("[tok] calls=%d tokens=%d",
                            self.total_calls, self.total_tokens)
            return content
        except Exception as e:
            logger.warning("json 自修复调用失败: %s", e)
            return None

    def stage_stats(self) -> List[dict]:
        """分环节成本读数（按 tokens 降序）。"""
        with self._lock:
            rows = []
            for k in set(self.stage_calls) | set(self.stage_tokens):
                rows.append({
                    "stage": k,
                    "calls": int(self.stage_calls.get(k, 0)),
                    "tokens": int(self.stage_tokens.get(k, 0)),
                    "ms": int(self.stage_ms.get(k, 0)),
                })
        return sorted(rows, key=lambda r: (-r["tokens"], r["stage"]))

    @staticmethod
    def parse_json(raw: str) -> Optional[dict]:''')

# 4) quality report + packed + md
rep('''    def _pack_result(self, question, route, keep, rounds, results):''',
'''    def _quality_report(self, results) -> dict:
        """质量闭环读数：覆盖率 / 三态 / 决策完整度 / 各层质量线索。

        只做读数，不改输出。它把「这跑到底哪几项质量指标达标」从散落的
        日志收成 packed 的一个块，并同步进 md。
        """
        answered = total = 0
        cov = None
        try:
            answered, total, cov = coverage_parts(
                self.pools.get("1"), self.config, "1")
        except Exception:
            pass
        tri_agree = int(getattr(self, "_tri_agree", 0) or 0)
        tri_total = int(getattr(self, "_tri_total", 0) or 0)
        actions = []
        not_do = []
        try:
            _v1 = results.get("1")
            if _v1 is not None:
                actions = _extract_actions(_v1) or []
                not_do = _extract_not_do(_v1) or []
        except Exception:
            pass
        flags = []
        layers = []
        for _e in ("0", "1", "both", "all"):
            _v = results.get(_e)
            if _v is None:
                continue
            _fl = list(getattr(_v, "quality_flags", None) or [])
            flags.extend(_fl)
            _dv = getattr(_v, "divergence", None) or {}
            layers.append({
                "entry": _e,
                "rounds": int(getattr(_v, "rounds_run", 0) or 0),
                "stop": str(getattr(_v, "stop_primary", "") or "")[:40],
                "flags": _fl,
                "quality": str(getattr(_v, "quality_verdict", "") or ""),
                "divergence": str((_dv or {}).get("state", "") or ""),
            })
        return {
            "coverage": (round(float(cov), 4) if cov is not None else None),
            "answered": answered,
            "answerable_total": total,
            "tri_state": [tri_agree, tri_total],
            "tri_ratio": (round(tri_agree / tri_total, 4)
                          if tri_total else None),
            "decision_actions": len(actions),
            "not_do": len(not_do),
            "flags": sorted(set(flags)),
            "layers": layers,
        }

    def _pack_result(self, question, route, keep, rounds, results):''')

rep('''        _pack["llm_eval_tokens"] = int(getattr(self.llm, "eval_tokens", 0) or 0)''',
'''        _pack["llm_eval_tokens"] = int(getattr(self.llm, "eval_tokens", 0) or 0)
        _pack["llm_by_stage"] = self.llm.stage_stats()
        _pack["llm_json_repaired"] = int(
            getattr(self.llm, "json_repaired", 0) or 0)
        _pack["llm_json_repair_failed"] = int(
            getattr(self.llm, "json_repair_failed", 0) or 0)
        _pack["quality"] = self._quality_report(results)''')

rep('''        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\\n")''',
'''        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\\n")
        _q = result.get("quality") or {}
        if _q:
            _cov = _q.get("coverage")
            _cov_s = ("—" if _cov is None else f"{_cov * 100:.1f}%")
            _tri = _q.get("tri_state") or [0, 0]
            f.write(f"**质量闭环**: 覆盖 {_cov_s}"
                    f"（{_q.get('answered', 0)}/{_q.get('answerable_total', 0)}）"
                    f" | 三态 {_tri[0]}/{_tri[1]}"
                    f" | 决策 {_q.get('decision_actions', 0)} 条"
                    f" / 不做 {_q.get('not_do', 0)} 条\\n")
            if _q.get("flags"):
                f.write(f"**质量线索**: {'、'.join(_q['flags'][:8])}\\n")
        _bs = result.get("llm_by_stage") or []
        if _bs:
            _top = "、".join(f"{r['stage']} {r['calls']}次/{r['tokens']}t"
                            for r in _bs[:4])
            f.write(f"**分环节成本（Top4）**: {_top}\\n")''')

# 5) default config
rep('''        "timeout": 240,
        "max_retries": 3,
        "retry_backoff": 1.8,''',
'''        "timeout": 240,
        "max_retries": 3,
        "retry_backoff": 1.8,
        # ★ JSON 自修复：默认关（零行为差）；打开后只在解析失败时多一次
        #   低温修复调用，把「答了但答不成结构」救回来。
        "json_repair": False,''')

p.write_bytes(t.encode("utf-8"))
print("patched", len(t), "crlf", t.count("\\r\\n"))
