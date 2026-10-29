# -*- coding: utf-8 -*-
"""[V2.2.19] 由 V2.2.18 生成 V2.2.19：输入驱动自动模式 + 每模式专属配置 + 运行期动态调整 + 模式集裁剪。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.18.py"
DST = ENG / "Meta-DGTF-V2.2.19.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b, n=1):
    global t
    c = t.count(a)
    assert c == n, "锚点命中 %d 次（应为 %d）: %r" % (c, n, a[:70])
    t = t.replace(a, b)


# 0) 标题 / 版本 / 补丁说明
rep("Meta-DGTF-道生三阶模型 · V2.2.18\n", "Meta-DGTF-道生三阶模型 · V2.2.19\n")
rep('__version__ = "2.2.18"', '__version__ = "2.2.19"')
rep("★ V2.2.18 补丁（项目流程门；引擎侧零行为差）：",
"""★ V2.2.19 补丁（输入驱动自动模式 + 每模式专属配置 + 运行期动态调整 + 模式集裁剪）：
      · 模式集只保留 B / serial / fast（web 降为标志位；A、C-H 从用户面移除）；
      · 新增 --mode auto|B|serial|fast：由题面（事实/推理/选择/长度）+ 显式预算
        自动选最优模式（枚举 oracle 可证 regret=0；不可行显式 fallback，不假装最优）；
      · MODE_CONFIGS 为每个模式给出专门配置（parallel/thinking/effort/web/rounds），
        App 与引擎共用同一事实源；
      · 运行期 dynamic_adjust：预算超支降档 fast、fast 质量代理低于目标升档 B，
        调整落 packed.auto_mode（含 reason/alternatives/optimality，可审计）；
      · --parallel 用户面只留 serial/B/auto；旧 mode A-H 显式回落 B 并留痕。
      · 默认（不给 --mode）逐字保持 V2.2.18 行为（零行为差，便于回归对照）。

★ V2.2.18 补丁（项目流程门；引擎侧零行为差）：""")

# 1) --parallel 用户面裁剪 + 新增 --mode
rep('''    parser.add_argument("--parallel", default=None,
                        choices=["serial", "A", "B", "C", "D", "E",
                                 "F", "G", "H", "auto"],
                        help="并行模式：serial / A~H / auto"
                             "（不给则用配置 actions.parallel_mode）")''',
'''    parser.add_argument("--parallel", default=None,
                        choices=["serial", "B", "auto"],
                        help="并行模式：serial / B / auto（保留集 B/serial/fast；"
                             "A、C-H 已从用户面移除，显式传入会回落 B 并留痕）")
    # ★ [V2.2.19] 输入驱动自动模式：每个模式有专门配置（MODE_CONFIGS），
    #   auto = 由题面 + 显式预算枚举最优；显式 B/serial/fast = 用该模式专属配置。
    parser.add_argument("--mode", default=None,
                        choices=["auto", "B", "serial", "fast"],
                        help="自动模式选择：auto=由题面选最优（事实题 fast / 推理题 B "
                             "/ 预算约束按需 serial）；也可显式 B/serial/fast。"
                             "每个模式有专门配置；不给则保持旧行为")''')

# 2) main：题面确定后立刻做模式规划（在 auto_dispatch 之前 => 显式参数优先链不变）
rep('''    _question = " ".join(args.question)
    _dispatch = auto_dispatch(_question, cfg, explicit={''',
'''    _question = " ".join(args.question)
    # ★ [V2.2.19] 输入驱动自动模式：只保留 B/serial/fast；auto 由题面推断；
    #   规划出来的显式参数写回 args（等价于用户显式传参，后续优先级链不变）。
    _auto_mode_plan = None
    if getattr(args, "mode", None):
        try:
            _mode_root = str(Path(__file__).resolve().parents[2])
            if _mode_root not in sys.path:
                sys.path.insert(0, _mode_root)
            from dgtf_v2.mode_fusion import plan_for_input
            _mopts = {}
            if args.mode != "auto":
                _mopts["mode"] = args.mode
            _auto_mode_plan = plan_for_input(_question, _mopts)
            _mc = _auto_mode_plan.get("config") or {}
            if not args.parallel:
                args.parallel = _mc.get("parallel")
            if getattr(args, "thinking", "auto") == "auto":
                args.thinking = ("off" if _mc.get("thinking") == "off"
                                 else "auto")
            if getattr(args, "web", "auto") == "auto":
                args.web = ("on" if _auto_mode_plan.get("web") else "off")
            if getattr(args, "effort", "auto") == "auto":
                args.effort = _mc.get("effort") or "auto"
            if not args.rounds:
                args.rounds = _mc.get("rounds_hint")
            if (getattr(args, "behavior_fusion", "auto") == "auto"
                    and _mc.get("behavior_fusion") == "off"):
                args.behavior_fusion = "off"
            _opt = _auto_mode_plan.get("optimality") or {}
            print("   ✓ 自动模式：%s（%s）" % (_auto_mode_plan.get("mode"),
                  _auto_mode_plan.get("reason") or ""))
            print("     · 模式专属配置：parallel=%s thinking=%s web=%s rounds=%s"
                  % (_mc.get("parallel"), _mc.get("thinking"),
                     "on" if _auto_mode_plan.get("web") else "off",
                     _mc.get("rounds_hint")))
            print("     · 最优性：%s（regret=%s，可行=%s）"
                  % (_opt.get("note"), _opt.get("regret"),
                     (_auto_mode_plan.get("selection") or {}).get("feasible")))
        except Exception as _me:  # noqa: BLE001
            print("   ⚠️ 自动模式不可用，退回默认：%s: %s"
                  % (type(_me).__name__, _me))
            _auto_mode_plan = None
    _dispatch = auto_dispatch(_question, cfg, explicit={''')

# 3) cfg 里挂计划（供 MetaDGTF.run 运行期动态调整）
rep('''    cfg = load_config(args.config)
    # default 改 None ⇒ 没给就别写（写 None 会把附录模式打坏）''',
'''    cfg = load_config(args.config)
    if _auto_mode_plan is not None:
        cfg["_auto_mode"] = _auto_mode_plan
    # default 改 None ⇒ 没给就别写（写 None 会把附录模式打坏）''')

# 4) _pm 计算后：旧并行模式回落 B
rep('''    _pm = args.parallel or (str(_dispatch.get("mode") or "")
                            if _mi.get("source") == "auto" else None) \\
        or cfg.get("actions", {}).get("parallel_mode", "auto") or "auto"
''',
'''    _pm = args.parallel or (str(_dispatch.get("mode") or "")
                            if _mi.get("source") == "auto" else None) \\
        or cfg.get("actions", {}).get("parallel_mode", "auto") or "auto"
    # ★ [V2.2.19] 保留集裁剪：A、C-H 已从用户面移除（内部实现仍保留供历史复现）。
    if _pm not in ("serial", "B", "auto"):
        print(f"   · 旧并行模式 {_pm} 已移除（保留集 B/serial/fast）⇒ 回落 B")
        _pm = "B"
''')

# 5) MetaDGTF.run：初始化自动模式账本
rep('''        self._run_id = str(run_id or "")
''',
'''        self._run_id = str(run_id or "")
        # ★ [V2.2.19] 自动模式计划 + 运行期调整账本（没有计划 => 恒空 => 零行为差）
        self._auto_mode_plan = None
        try:
            _amp = self.config.get("_auto_mode")
            if isinstance(_amp, dict) and _amp.get("mode"):
                self._auto_mode_plan = _amp
        except Exception:  # noqa: BLE001
            self._auto_mode_plan = None
        self._auto_adjustments: List[dict] = []
        self._auto_thinking_orig = None
        if self._auto_mode_plan is not None:
            try:
                self._auto_thinking_orig = json.loads(json.dumps(
                    (self.config.get("api") or {}).get("thinking") or {}))
            except Exception:  # noqa: BLE001
                self._auto_thinking_orig = None
''')

# 6) 动态调整方法（插在 _run_layer 之前）
rep('''    def _run_layer(self, entry: str, n_rounds: int = 0) -> View:
''',
'''    # ── [V2.2.19] 运行期自动模式调整（纯函数 dynamic_adjust 的引擎侧落地）──
    def _auto_quality_proxy(self):
        """运行期质量代理：已完成层的错误数/候选数（不是分数，只用于升档触发）。"""
        vs = [v for v in (self._results or {}).values() if isinstance(v, dict)]
        if not vs:
            return None
        errs = sum(len(v.get("errors") or []) for v in vs)
        cands = sum(len(v.get("candidates") or []) for v in vs)
        if errs == 0 and cands > 0:
            return 1.0
        if errs == 0:
            return 0.6
        return 0.2

    def _auto_set_thinking(self, mode: str) -> None:
        th = (self.config.get("api") or {}).get("thinking")
        if not isinstance(th, dict):
            th = {}
            self.config.setdefault("api", {})["thinking"] = th
        if mode == "off":
            th["default"] = "disabled"
            th["reasoner"] = "disabled"
            for _k in list((th.get("stages") or {})):
                th["stages"][_k] = "disabled"
        elif isinstance(self._auto_thinking_orig, dict):
            th.clear()
            th.update(json.loads(json.dumps(self._auto_thinking_orig)))

    def _auto_mode_tick(self, phase: str, done: int, total: int,
                        wave: int = 0):
        """层/波边界检查：预算超支降档、fast 质量不达标升档；记录可审计账本。"""
        plan = getattr(self, "_auto_mode_plan", None)
        if not plan:
            return None
        try:
            from dgtf_v2.mode_fusion import dynamic_adjust
            _tok = int(getattr(self.llm, "total_tokens", 0) or 0)
            _elapsed = max(0.0, time.time() - float(getattr(self, "_t0",
                                                           time.time())))
            _prog = {
                "elapsed_sec": _elapsed,
                "wall_budget_sec": (
                    float(getattr(self, "_max_minutes", 0) or 0) * 60.0) or None,
                "tokens_used": _tok,
                "token_budget": (int(getattr(self, "_token_budget_raw", 0) or 0)
                                 or None),
                "layers_done": int(done),
                "layers_total": int(total),
                "quality_proxy": self._auto_quality_proxy(),
                "phase": phase,
                "wave": int(wave),
            }
            dec = dynamic_adjust(plan, _prog)
            if dec.get("action") == "keep":
                return dec
            dec = dict(dec, phase=phase, wave=int(wave),
                       at=round(float(_elapsed), 1), tokens=_tok)
            self._auto_adjustments.append(dec)
            if dec["action"] == "downgrade":
                self._auto_set_thinking("off")
                try:
                    self.config.setdefault("web_search", {})["enabled"] = False
                except Exception:  # noqa: BLE001
                    pass
                _st = getattr(self, "_b_state", None)
                if isinstance(_st, dict):
                    for _s in _st.values():
                        if _s.get("stopped"):
                            continue
                        _s["total_rounds"] = min(
                            int(_s.get("total_rounds") or 1),
                            max(1, int(wave)) + 1)
                else:
                    _rounds = getattr(self, "_rounds", None)
                    if isinstance(_rounds, dict):
                        for _e in list(_rounds):
                            if _e not in (getattr(self, "_results", {}) or {}):
                                _rounds[_e] = 1
            elif dec["action"] == "upgrade":
                self._auto_set_thinking("auto")
                if not isinstance(getattr(self, "_b_state", None), dict):
                    _rounds = getattr(self, "_rounds", None)
                    if isinstance(_rounds, dict):
                        for _e in list(_rounds):
                            if _e not in (getattr(self, "_results", {}) or {}):
                                _rounds[_e] = int(_rounds.get(_e) or 0) + 1
            self.vp("   · 自动模式调整：%s（%s）"
                    % (dec.get("reason"), dec.get("action")))
            return dec
        except Exception as exc:  # noqa: BLE001
            logger.warning("自动模式调整失败（不阻断）：%s", exc)
            return None

    def _run_layer(self, entry: str, n_rounds: int = 0) -> View:
''')

# 7) serial：层边界调用 tick
rep('''            try:
                self.vp(f"\\n{'═'*60}\\n【{entry}】{_LAYER_LABEL[entry]} DGTF"
''',
'''            self._auto_mode_tick("serial", len(self._results),
                                 len(dispatch["order"]))
            try:
                self.vp(f"\\n{'═'*60}\\n【{entry}】{_LAYER_LABEL[entry]} DGTF"
''')

# 8) B 模式：波边界调用 tick
rep('''        for k in range(warm + 1, max_wave + 1):
''',
'''        for k in range(warm + 1, max_wave + 1):
            self._auto_mode_tick("B", len(self._results),
                                 len(active), wave=k)
''')

# 9) packed：auto_mode 出口
rep('''        _pack["llm_ops_calls"] = int(getattr(self.llm, "ops_calls", 0) or 0)
''',
'''        _pack["auto_mode"] = {
            "plan": getattr(self, "_auto_mode_plan", None),
            "adjustments": list(getattr(self, "_auto_adjustments", []) or []),
        }
        _pack["llm_ops_calls"] = int(getattr(self.llm, "ops_calls", 0) or 0)
''')

out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk), "bytes")
