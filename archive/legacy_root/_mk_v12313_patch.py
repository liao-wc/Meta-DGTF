# -*- coding: utf-8 -*-
"""v1.23.13 补丁：把十二项收进**统一自适应调度器**，并处理 auto_plan 双实现技术债。

★ 本脚本**只改一处真相源**：所有编辑都在 `lines`（LF 行表）上做，最后
  join 一次、转一次 CRLF、写一次盘。
  ★★ 为什么必须这样：上一版（v1.23.12）混合了「文本级 `s.replace`」与
  「行级 `lines[..] = ..`」，中间一次 `s = "\\n".join(lines)` 把前面的文本级
  替换**静默丢掉**（版本号没升、`_assemble_plan` 的 4 处调用全丢），
  而 `ast.parse` 照样通过。同一种错（状态漂移），第二次机制。

改动清单：
  A 版本号（标题 + `__version__`）
  B 插入调度器块（`_v12313_block_auto.py`）
  C 插 `_normalize_orientation`（取向归一化唯一实现）+ `_assemble_plan`（唯一装配器）
  D `plan_orientation` 用 `_normalize_orientation`
  E `plan_resources` 用 `_normalize_orientation`
  F 单调用路径：`_normalize_orientation` + `_assemble_plan`
  G 两段式出口：也过 `_assemble_plan`（⇒ 两条路径**同一 schema**）
  H CLI：`--route/--rounds/--appendix` 默认改 None；新增 `--landing/--decidability`
  I main：一次调度 → 逐项写配置 → 再 `_apply_runtime`
  J run()：接收 plan，逐项取用；可判定性判定可关
  K `_route_by_decidability` 加 `allow_probe`
  L `_pack_result` 挂 `_auto_dispatch`
  M `save_result` 渲染「自动调度 · 逐项来源」表
  N `render_landing` 认 plan 的 landing（取向与模板**解耦**）
  O DEFAULT_CONFIG 新增 `auto` 段
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.13.py"
BLOCK = (HERE / "_v12313_block_auto.py").read_text(
    encoding="utf-8").replace("\r\n", "\n")

raw = MAIN.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "主文件不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
N0 = len(lines) - 1


def find_row(pred, what):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, "%s：命中 %d 次 %r" % (what, len(hits), hits)
    return hits[0]


def repl(old, new, what, expect=1):
    """整块替换（按行比对）。old/new 的第一/末行都算实内容。"""
    o = old.split("\n")
    n = new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1)
            if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：块命中 %d 次（要求 %d）%r" % (
        what, len(hits), expect, hits[:5])
    for i in reversed(hits):
        lines[i:i + len(o)] = n


def insert_at(idx, block, what):
    lines[idx:idx] = block.split("\n")


# ═══════════════════════════════════════════════ A 版本号
repl("元 DGTF · v1.23.12", "元 DGTF · v1.23.13", "标题版本")
repl('__version__ = "1.23.12"', '__version__ = "1.23.13"', "版本常量")

# ═══════════════════════════════════════════════ B 调度器块
insert_at(find_row(lambda l: l == "def plan_orientation(question: str,",
                   "plan_orientation 定义"), BLOCK, "调度器块")

# ═══════════════════════════════════════════════ C 两个唯一实现
UNIQ = '''def _normalize_orientation(v, fallback: str = "") -> str:
    """取向归一化的**唯一实现**（v1.23.13 合并前有三份，且 fallback 语义不同）。

    ★ 合并前的三处：`plan_orientation`（非法 → decision，保守）、
      `plan_resources`（非法 → decision）、单调用路径（非法 → ""，表示未知）。
      三份代码各自 normalize 同一个字段，是「同一条逻辑三条实现」。
      fallback 是**调用方语义**（外部 API 要保守值、热路径要「未知」），
      所以做成显式参数，而不是让实现分叉。
    """
    s = str(v or "").strip().lower()
    if s in ("boundary", "decision"):
        return s
    return fallback if fallback in ("boundary", "decision") else ""


def _assemble_plan(mode, rounds, cfg, route=None, orientation="", max_calls=0,
                   reason="", confidence=0.0, extra=None) -> dict:
    """**唯一装配器**：所有调度出口都过这里 ⇒ `auto_plan()` 只有一种 schema。

    ★ 技术债（v1.21.71 F8 起挂账）：单调用路径返回 `{mode, rounds, reason,
      orientation, confidence}`，两段式路径返回 `{route, mode, rounds,
      cost_profile, max_calls, orientation, reason, confidence, _auto}` ——
      同一个函数名按参数返回**两种形状**，`plan.get("route")` 在单调用路径下
      是 None。装到一处之后形状差异消失，`check_v71_auto_plan_agreement`
      从「漂移检测器」升格为「同一实现的构造性证明」。
    """
    prof = str((cfg or {}).get("cost_profile", "balanced")).strip().lower()
    if prof not in _COST_PROFILES:
        prof = "balanced"
    out = {
        "route": [str(x) for x in (route or list(_ROUTE_PRESETS["full"]))],
        "mode": str(mode or "serial"),
        "rounds": dict(rounds or {}),
        "cost_profile": prof,
        "max_calls": int(max_calls or 0),
        "orientation": _normalize_orientation(orientation, ""),
        # ★ 这个键单调用路径本来没有 ⇒ 两条路径 schema 差一个键。
        #   放进基数里（默认空串），谁有理由谁在 `extra` 里覆盖它。
        "_orientation_reason": "",
        "reason": str(reason or "")[:200],
        "confidence": float(confidence or 0.0),
        "_auto": True,
    }
    if extra:
        out.update(extra)
    return out
'''
insert_at(find_row(lambda l: l == "def _normalize_plan_mode(data) -> str:",
                   "_normalize_plan_mode 定义"), UNIQ, "唯一实现")

# ═══════════════════════════════════════════════ D plan_orientation
repl('''    _o = str(data.get("orientation", "decision")).strip().lower()
    if _o not in ("boundary", "decision"):
        _o = "decision"''',
     '''    _o = _normalize_orientation(data.get("orientation"), "decision")''',
     "plan_orientation 归一化")

# ═══════════════════════════════════════════════ E plan_resources
repl('''    _o = (orientation or "decision").strip().lower()
    if _o not in ("boundary", "decision"):
        _o = "decision"''',
     '''    _o = _normalize_orientation(orientation, "decision")''',
     "plan_resources 归一化")

# ═══════════════════════════════════════════════ F 单调用路径
repl('''        _ori = str(data.get("orientation", "")).strip().lower()
        if _ori not in ("decision", "boundary"):
            _ori = ""''',
     '''        _ori = _normalize_orientation(data.get("orientation"), "")''',
     "单调用取向归一化")

repl('''        if mode != "serial" and conf < _PARALLEL_CONF_MIN:
            return {"mode": "serial", "rounds": rnd,
                    "reason": f"低置信({conf:.2f})，退回 serial：{reason}",
                    "orientation": _ori, "confidence": conf}
        return {"mode": mode, "rounds": rnd, "reason": reason,
                "orientation": _ori, "confidence": conf}''',
     '''        if mode != "serial" and conf < _PARALLEL_CONF_MIN:
            return _assemble_plan(
                "serial", rnd, cfg, orientation=_ori, confidence=conf,
                reason=f"低置信({conf:.2f})，退回 serial：{reason}")
        return _assemble_plan(mode, rnd, cfg, orientation=_ori,
                              reason=reason, confidence=conf)''',
     "单调用返回装配")

repl('''            return {"mode": "serial", "rounds": {},
                    "reason": "调度失败，退回保守（圈数走配置）",
                    "orientation": "", "confidence": 0.0}''',
     '''            return _assemble_plan(
                "serial", {}, cfg, confidence=0.0,
                reason="调度失败，退回保守（圈数走配置）")''',
     "单调用失败出口")

# ═══════════════════════════════════════════════ G 两段式出口
repl('''    return {
        "route": r.get("route", list(_ROUTE_PRESETS["full"])),
        "mode": r.get("mode", "serial"),
        "rounds": r.get("rounds", {}),
        "cost_profile": prof,
        "max_calls": r.get("max_calls", 0),
        "orientation": o["orientation"],
        "_orientation_reason": o.get("reason", ""),
        "reason": _reason,
        "confidence": r.get("confidence", 0.0),
        "_auto": True,
    }''',
     '''    return _assemble_plan(
        r.get("mode", "serial"), r.get("rounds", {}), cfg,
        route=r.get("route", list(_ROUTE_PRESETS["full"])),
        orientation=o["orientation"], max_calls=r.get("max_calls", 0),
        reason=_reason, confidence=r.get("confidence", 0.0),
        extra={"_orientation_reason": o.get("reason", ""),
               "cost_profile": prof})''',
     "两段式出口装配")

# ═══════════════════════════════════════════════ H CLI
repl('''    parser.add_argument("--route", default="0,1,both,all")''',
     '''    # default 改 None：**区分「没给」与「显式给了」**，
    #   否则 route 永远无法交给 auto（旧默认值把「没给」伪装成「给了全四层」）。
    parser.add_argument("--route", default=None)''',
     "--route 默认")
repl('''    parser.add_argument("--rounds", default="0")''',
     '''    parser.add_argument("--rounds", default=None)''',
     "--rounds 默认")
repl('''    parser.add_argument("--appendix", default="file",
                        choices=["file", "inline"],''',
     '''    parser.add_argument("--appendix", default=None,
                        choices=["file", "inline"],''',
     "--appendix 默认")
repl('''    parser.add_argument("--orientation", default="auto",
                        choices=["auto", "boundary", "decision"],''',
     '''    parser.add_argument("--landing", default="auto",
                        choices=["auto", "boundary", "decision"],
                        help="落地层模板：与取向**解耦**（取向管砍层，"
                             "本项管产物形态）；auto = 按题面分流")
    parser.add_argument("--decidability", default="auto",
                        choices=["auto", "on", "off"],
                        help="可判定性判定：auto = 事实型短题跳过那次外部评估")
    parser.add_argument("--orientation", default="auto",
                        choices=["auto", "boundary", "decision"],''',
     "--landing/--decidability 新增")

# ═══════════════════════════════════════════ I0 --appendix 守卫
repl('''    cfg.setdefault("actions", {})["appendix_mode"] = args.appendix''',
     '''    # default 改 None ⇒ 没给就别写（写 None 会把附录模式打坏）
    if args.appendix:
        cfg.setdefault("actions", {})["appendix_mode"] = args.appendix''',
     "--appendix 守卫")

# ═══════════════════════════════════════════════ I main
repl('''    if args.profile:
        _pf = args.profile
        if _pf == "auto":
            _pf = _auto_profile(" ".join(args.question))
            print(f"   ✓ 成本档位：auto → {_pf}（按题面规则选定）")
        else:
            print(f"   ✓ 成本档位：{_pf}")
        cfg["cost_profile"] = _pf
    if args.no_self_check:''',
     '''    # ★ **十二项一次性调度**（显式 ＞ 配置 ＞ auto ＞ 默认）。
    #   命令行「没给」保持 None，调度器才分得清「没给」与「给了」。
    _question = " ".join(args.question)
    _dispatch = auto_dispatch(_question, cfg, explicit={
        "route": args.route, "cost_profile": args.profile,
        "mode": args.parallel, "rounds": args.rounds,
        "orientation": args.orientation, "web": args.web,
        "thinking": args.thinking, "effort": args.effort,
        "landing": args.landing, "decidability": args.decidability,
    })
    for _n in _apply_auto_dispatch(cfg, _dispatch):
        print(f"   ✓ 自动调度：{_n}")
    if args.no_self_check:''',
     "main 调度段")

repl('''    _web = args.web
    if _web == "auto" and _web_auto_for_facts(" ".join(args.question)):
        _web = "on"
        print("   · 事实型询问 + --web auto ⇒ 自动接入外部校验（要关：--web off）")
    cfg, _rt_notes = _apply_runtime(cfg, {
        "web": _web, "thinking": args.thinking,
        "effort": args.effort})''',
     '''    # 运行期三项总控由调度器写进 `cfg["runtime"]`，`_apply_runtime` 是
    # `web_search.enabled` / `api.thinking.*` 的**唯一写入者**（不两处各写）。
    cfg, _rt_notes = _apply_runtime(cfg)''',
     "main 运行期段")

repl('''    route = [x.strip() for x in args.route.split(",") if x.strip()]''',
     '''    _ri = (_dispatch.get("_items") or {}).get("route") or {}
    if args.route:
        route = [x.strip() for x in _normalize_punct(args.route).split(",")
                 if x.strip()]
    elif _ri.get("source") == "auto":
        route = list(_dispatch.get("route") or [])
        print(f"   · 层集合由 auto 接管：{'、'.join(route)}"
              f"（{_ri.get('reason', '')}）")
    else:
        route = list(_ENTRIES)''',
     "main route 解析")

repl('''    _pm = args.parallel or cfg.get("actions", {}).get(
        "parallel_mode", "auto") or "auto"''',
     '''    _mi = (_dispatch.get("_items") or {}).get("mode") or {}
    _pm = args.parallel or (str(_dispatch.get("mode") or "")
                            if _mi.get("source") == "auto" else None) \\
        or cfg.get("actions", {}).get("parallel_mode", "auto") or "auto"''',
     "main 模式解析")

repl('''    print(f"螺旋上限（每层圈数）：{args.rounds}")''',
     '''    _rp = args.rounds or _dispatch.get("rounds") or "（按各层配置）"
    print(f"螺旋上限（每层圈数）：{_rp}")''',
     "main 圈数打印")

repl('''    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds, channels=channels,
                      parallel_mode=_pm,
                      orientation=args.orientation)''',
     '''    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds or _dispatch.get("rounds") or 0,
                      channels=channels, parallel_mode=_pm,
                      orientation=args.orientation, auto_plan=_dispatch)''',
     "main run 调用")

# ═══════════════════════════════════════════════ J run()
repl('''            parallel_mode: str = "auto",
            orientation: str = "auto") -> dict:''',
     '''            parallel_mode: str = "auto",
            orientation: str = "auto",
            auto_plan: Optional[dict] = None) -> dict:''',
     "run 签名")

repl('''        self._web_prep_seq = 0
        self._orientation = str(orientation or "auto")''',
     '''        self._web_prep_seq = 0
        # ★ 统一调度器给的 plan（逐项来源留痕）；没给则沿用旧路径。
        self._auto_plan_spec = auto_plan if isinstance(auto_plan, dict) else None
        _ai = ((self._auto_plan_spec or {}).get("_items") or {})
        if orientation == "auto" and _ai.get("orientation", {}).get(
                "source") == "auto":
            orientation = str((self._auto_plan_spec or {}).get("orientation")
                              or "auto")
        _dec_probe = True
        if _ai.get("decidability", {}).get("source") == "auto":
            _dec_probe = bool((self._auto_plan_spec or {}).get("decidability"))
        self._orientation = str(orientation or "auto")''',
     "run 取向/可判定性")

repl('''        route = self._route_by_decidability(question, route, orientation)''',
     '''        route = self._route_by_decidability(question, route, orientation,
                                            allow_probe=_dec_probe)''',
     "run 路由调用")

repl('''        self._auto_plan_used = None
        if parallel_mode == "auto" and not rounds:
            plan = self._auto_plan(question)''',
     '''        self._auto_plan_used = None
        if self._auto_plan_spec is not None and _ai.get("mode", {}).get(
                "source") == "auto" and parallel_mode == "auto":
            mode = str((self._auto_plan_spec or {}).get("mode") or "serial")
            if mode == "llm":
                decision = self._decide_parallel_mode(question)
                mode = decision["mode"]
                self.vp(f"\\n🧵 并行模式自动决策：{mode}"
                        f"（{decision['reason']}，"
                        f"置信 {decision['confidence']:.2f}）")
            else:
                self.vp(f"\\n🧭 自动调度：模式 {mode}"
                        f"（{_ai['mode'].get('reason', '')}）")
            self._auto_plan_used = dict(self._auto_plan_spec)
            if not rounds:
                rounds = (self._auto_plan_spec or {}).get("rounds") or 0
        elif parallel_mode == "auto" and not rounds:
            plan = self._auto_plan(question)''',
     "run 模式分支")

# ═══════════════════════════════════════════════ K allow_probe
repl('''    def _route_by_decidability(self, question: str,
                               route: List[str],
                               orientation: str = "auto") -> List[str]:''',
     '''    def _route_by_decidability(self, question: str,
                               route: List[str],
                               orientation: str = "auto",
                               allow_probe: bool = True) -> List[str]:''',
     "路由签名")

repl('''        if _o == "boundary":
            self.vp("\\n📐 取向=boundary（要边界清单）"
                    "→ 保留全四层（边界只有对撞/元层会认真做）")
            return route''',
     '''        if _o == "boundary":
            self.vp("\\n📐 取向=boundary（要边界清单）"
                    "→ 保留全四层（边界只有对撞/元层会认真做）")
            return route

        if not allow_probe:
            self.vp("\\n📐 可判定性判定被 auto 关闭（事实型短题：层集合已按"
                    "题型定，不花那次外部评估）→ 保留当前 route")
            return route''',
     "路由可判定性开关")

# ═══════════════════════════════════════════════ L _pack_result
repl('''            "_auto_plan_used": dict(getattr(self, "_auto_plan_used", None) or {}),''',
     '''            "_auto_plan_used": dict(getattr(self, "_auto_plan_used", None) or {}),
            "_auto_dispatch": dict(
                getattr(self, "_auto_plan_spec", None) or {}),''',
     "pack 挂调度")

# ═══════════════════════════════════════════════ M 产物渲染
repl('''            f.write(f"**并行模式**：{_pm_disp}\\n\\n")''',
     '''            f.write(f"**并行模式**：{_pm_disp}\\n\\n")
            for _al in _auto_dispatch_lines(result):
                f.write(_al)''',
     "产物渲染调度表")

# ═══════════════════════════════════════════════ N render_landing
repl('''    cfg = res.get("_config") or {}
    orientation = str(res.get("orientation") or "auto").strip().lower()
    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):''',
     '''    cfg = res.get("_config") or {}
    orientation = str(res.get("orientation") or "auto").strip().lower()
    # ★ 落地层模板可**单独接管**（与取向解耦）——
    #   取向决定「是否按可判定性砍层」，本项只决定产物形态。
    #   上一版之前 `auto` 在 route 侧按 decision、在模板侧按题面分流，
    #   同一趟里可能自相矛盾（产物要靠「取向错配」告警来自证清白）。
    _li = ((res.get("_auto_dispatch") or {}).get("_items") or {}).get(
        "landing") or {}
    _land = str(_li.get("value") or "") if _li.get("source") in (
        "auto", "explicit", "config") else ""
    if _land in ("boundary", "decision"):
        orientation = _land
    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):''',
     "render_landing 解耦")

# ═══════════════════════════════════════════════ O DEFAULT_CONFIG
repl('''    "runtime": {
        "web": "auto",
        "thinking": "auto",
        "effort": "auto",
    },''',
     '''    # ============================================================
    # 统一自适应调度器
    #   enabled=false ⇒ 十二项一律退回「配置 / 默认」，行为回到上一版。
    #   allow_route_trim=false ⇒ auto 永不砍层（层集合恒为全四层）。
    #   history_limit = 扫多少份 `outputs/*.packed.json` 做历史读数。
    # ============================================================
    "auto": {
        "enabled": True,
        "allow_route_trim": True,
        "history_limit": 20,
    },
    "runtime": {
        "web": "auto",
        "thinking": "auto",
        "effort": "auto",
    },''',
     "DEFAULT_CONFIG auto 段")

# ═══════════════════════════════════════════════ 落盘
out = "\n".join(lines)
ast.parse(out)
data = out.replace("\n", "\r\n").encode("utf-8")
assert data.count(b"\r\r\n") == 0 and data.count(b"\r\n") == data.count(b"\n")
MAIN.write_bytes(data)

txt = data.decode("utf-8")
N1 = txt.count("\n")
print("行数：%d → %d（%+d）" % (N0, N1, N1 - N0))
print("CRLF %d | CRCRLF %d" % (data.count(b"\r\n"), data.count(b"\r\r\n")))
print("版本：", [l for l in txt.split("\n")[:5] if l.strip()][:1],
      [l for l in txt.split("\n") if l.startswith("__version__")])
for _k in ("def auto_dispatch(", "def _auto_dispatch_lines(",
           "def _normalize_orientation(", "def _assemble_plan(",
           "def _auto_pick_stop(", "_apply_auto_dispatch(cfg, _dispatch)",
           "_assemble_plan(", "_normalize_orientation(", '"auto": {',
           'parser.add_argument("--landing"'):
    print("  %-40s ×%d" % (_k, txt.count(_k)))

# 结构性自检：模块必须能加载，且三档 render_landing 都返回 str
import importlib.util as _ilu
import sys as _sys
_spec = _ilu.spec_from_file_location("m_v12313_patchchk", MAIN)
_m = _ilu.module_from_spec(_spec)
_sys.modules["m_v12313_patchchk"] = _m
_spec.loader.exec_module(_m)
assert _m.__version__ == "1.23.13", "版本常量没升：%r" % _m.__version__
for _o in ("boundary", "decision", "auto"):
    _r = _m.render_landing({"orientation": _o,
                            "_config": {"actions": {"landing_decision": True}},
                            "views": {}, "decidability": {},
                            "question": "这份方案怎么落地"})
    assert isinstance(_r, str), "★ render_landing(%s) 返回 %r" % (_o, type(_r))
print("结构自检：模块加载 OK / 版本 1.23.13 / render_landing 三档返回 str ✓")
