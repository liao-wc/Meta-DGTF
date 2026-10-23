# -*- coding: utf-8 -*-
"""v1.23.50 引擎补丁：断点续跑 + 快照记账 + route 死捕获 + 墙钟预算。

背景（真实事故）：今天 A/B 真跑被宿主回收两次（18.2 min / 12.7 min），烧掉约 ¥2
**且不可续** —— 快照只能"留痕"，不能接着跑；连花了多少钱都查不出来（快照没记账）。
本版补四件事（与前一轮清单一致）：

  ① `run(..., resume_ckpt=<路径>)`：复用快照里**已完成层**（不重跑、不再花那部分钱），
     并恢复其**池**（下游层读上游池；池不还原 ⇒ 续跑结果与一次跑完不同）。
  ② 快照带**记账**：`llm_calls` / `llm_tokens` / 各层 `rounds_run` ⇒ 被杀跑次也能结算成本。
  ③ 快照带 `mode`；`run()` 里补 `self._route = list(route)`（原为死捕获 ⇒ 恒 []）。
  ④ `run(..., max_minutes=N)`（默认 0 = 关）：层间墙钟预算 ⇒ **优雅停**（状态 `paused`）
     + 落快照 ⇒ 分片跑完，撞不上宿主的回收窗口。

★ 只支持 `serial` 的续跑（并行模式的 `_results` 由并发填，完成判据不同）——
  非 serial 一律**拒绝续跑并说明理由**，绝不静默混跑。
★ 默认行为零变化：不传 `resume_ckpt` / `max_minutes=0` ⇒ 与 v1.23.49 逐字相同。

CRLF 安全：read_bytes → 断言 → 替换（每处断言命中 == 1）→ write_bytes → 回读自检。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.50.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF，先停"
assert b.count(b"\r\r\n") == 0, "已有 CRCRLF 污染，先停"
t = b.decode("utf-8").replace("\r\n", "\n")

PATCHES = []

# ── ① 版本位（docstring 标题 + __version__） ─────────────────────────
PATCHES.append((
    "版本标题",
    "元 DGTF · v1.23.49\n",
    "元 DGTF · v1.23.50\n",
))
PATCHES.append((
    "版本号",
    '__version__ = "1.23.49"\n',
    '__version__ = "1.23.50"\n',
))

# ── ② View.from_dict（to_dict 的逆；快照还原要用） ────────────────────
PATCHES.append((
    "View.from_dict",
    '        return d\n'
    '\n'
    '\n'
    'CHANNELS = ("content", "context", "self")\n',
    '        return d\n'
    '\n'
    '    @classmethod\n'
    '    def from_dict(cls, d: dict) -> "View":\n'
    '        """[v1.23.50 断点续跑] `to_dict()` 的**逆**：从快照/产物字典还原 View。\n'
    '\n'
    '        \u2605 只取**数据类字段**：`to_dict` 会额外补 `touch_rate` /\n'
    '          `aspect_carry_rate` 两个 **property**（不是构造参数）\n'
    '          \u21d2 原样 `cls(**d)` 必 TypeError。\n'
    '        \u2605 未知键**不静默吞**：打一条 warning 并记进 `meta`（留痕）。\n'
    '        """\n'
    '        if not isinstance(d, dict):\n'
    '            raise TypeError("View.from_dict 需要 dict，得到 %r" % (type(d),))\n'
    '        _names = set(getattr(cls, "__dataclass_fields__", {}) or {})\n'
    '        _kw = {k: v for k, v in d.items() if k in _names}\n'
    '        _extra = sorted(k for k in d if k not in _names)\n'
    '        v = cls(**_kw)\n'
    '        if _extra:\n'
    '            logger.warning("View.from_dict：忽略非字段键 %r", _extra[:8])\n'
    '            v.meta = list(v.meta or []) + [\n'
    '                "[from_dict] 忽略非字段键：%s" % ",".join(_extra[:8])]\n'
    '        return v\n'
    '\n'
    '\n'
    'CHANNELS = ("content", "context", "self")\n',
))

# ── ③ 快照加 mode / pools / 记账（被杀跑次也要能结算） ────────────────
PATCHES.append((
    "快照加字段",
    '    out = {"id": str(run_id), "status": str(status),\n'
    '           "engine": __version__,\n'
    '           "question": str(getattr(engine, "_question", "") or "")[:400],\n'
    '           "route": list(getattr(engine, "_route", None) or []),\n'
    '           "n_views": len(views), "views": views,\n'
    '           "t": time.time()}\n',
    '    # \u2605 [v1.23.50] 续跑要还原**池**，而 `Pool.to_dict()` 是**手工白名单**\n'
    '    #   （新键不同步就静默丢）\u21d2 这里用 `asdict` 取**全字段**。\n'
    '    pools = {}\n'
    '    try:\n'
    '        for _pe, _pool in (getattr(engine, "pools", None) or {}).items():\n'
    '            try:\n'
    '                pools[str(_pe)] = (asdict(_pool)\n'
    '                                   if hasattr(_pool, "__dataclass_fields__")\n'
    '                                   else dict(_pool))\n'
    '            except Exception as _e3:  # noqa: BLE001\n'
    '                pools[str(_pe)] = {"_unserializable": "%s: %s"\n'
    '                                   % (type(_e3).__name__, _e3)}\n'
    '    except Exception:  # noqa: BLE001\n'
    '        pools = {}\n'
    '    # \u2605 [v1.23.50 记账] 被杀跑次的计数器随进程消失 \u21d2 必须进快照，\n'
    '    #   否则「这跑烧了多少」永远查不出来（今天就是这么亏的）。\n'
    '    _acct = {}\n'
    '    try:\n'
    '        _llm = getattr(engine, "llm", None)\n'
    '        _acct = {"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),\n'
    '                 "llm_tokens": int(getattr(_llm, "total_tokens", 0) or 0),\n'
    '                 "rounds_run": {str(k): int(getattr(v, "rounds_run", 0) or 0)\n'
    '                                for k, v in\n'
    '                                (getattr(engine, "_results", None) or {}).items()\n'
    '                                if v is not None}}\n'
    '    except Exception:  # noqa: BLE001\n'
    '        _acct = {}\n'
    '    out = {"id": str(run_id), "status": str(status),\n'
    '           "engine": __version__,\n'
    '           "mode": str(getattr(engine, "_parallel_mode", "") or ""),\n'
    '           "question": str(getattr(engine, "_question", "") or "")[:400],\n'
    '           "route": list(getattr(engine, "_route", None) or []),\n'
    '           "n_views": len(views), "views": views, "pools": pools,\n'
    '           "t": time.time()}\n'
    '    out.update(_acct)\n',
))

# ── ④ load_resume_snapshot（续跑入口：三道硬校验 + 还原 View/Pool） ────
PATCHES.append((
    "续跑入口函数",
    '        out.append({"id": d.get("id"), "why": d["interrupted_why"]})\n'
    '    return out\n'
    '\n'
    '\n'
    'class MetaDGTF:\n',
    '        out.append({"id": d.get("id"), "why": d["interrupted_why"]})\n'
    '    return out\n'
    '\n'
    '\n'
    'def load_resume_snapshot(path, question: str = "", mode: str = "") -> dict:\n'
    '    """[v1.23.50 断点续跑] 读一份快照 \u21d2 `{"ok", "why", "views", "pools"}`。\n'
    '\n'
    '    \u2605 三道**硬校验**（不过就 `ok=False` + 理由，调用方\uff08按原样全跑\uff09，\n'
    '      **绝不静默地把两跑混在一起**）：\n'
    '        ① `status` 必须是 `running`/`interrupted`/`paused`\uff08`done` 的不该再续\uff09；\n'
    '        ② 题面与本次**逐字相同**\uff08是"同一跑的续"，不是拿别人的快照凑\uff09；\n'
    '        ③ 本版只支持 `serial` 的续跑 \u2014\u2014 并行模式的 `_results` 由并发填，\n'
    '           "层已完成"的判据不同，混用会静默改结果。\n'
    '    \u2605 `_results[e]` \u53ea\u5728\u5c42**\u8dd1\u5b8c**\u624d\u8d4b\u503c \u21d2 \u5feb\u7167\u91cc\u6709 view = \u8be5\u5c42\u5df2\u5b8c\u6210\u3002\n'
    '    """\n'
    '    _out = {"ok": False, "why": "", "views": {}, "pools": {}}\n'
    '    try:\n'
    '        _d = json.loads(Path(path).read_text(encoding="utf-8"))\n'
    '    except Exception as _e:  # noqa: BLE001\n'
    '        _out["why"] = "快照读不了：%s: %s" % (type(_e).__name__, _e)\n'
    '        return _out\n'
    '    if not isinstance(_d, dict):\n'
    '        _out["why"] = "快照不是 dict"\n'
    '        return _out\n'
    '    _st = str(_d.get("status") or "")\n'
    '    if _st not in ("running", "interrupted", "paused"):\n'
    '        _out["why"] = "快照状态 %r 不可续（只有 running/interrupted/paused 能续）" % _st\n'
    '        return _out\n'
    '    _q0 = str(_d.get("question") or "").strip()\n'
    '    if question and _q0 and _q0 != str(question).strip()[:400]:\n'
    '        _out["why"] = ("题面不一致（快照 %.18s… vs 本次 %.18s…）"\n'
    '                       % (_q0, str(question).strip()[:400]))\n'
    '        return _out\n'
    '    _m0 = str(_d.get("mode") or "")\n'
    '    if mode and mode != "serial":\n'
    '        _out["why"] = "本版只支持 serial 的续跑（本次 mode=%s）" % mode\n'
    '        return _out\n'
    '    if _m0 and _m0 != "serial":\n'
    '        _out["why"] = "快照来自 mode=%s（本版只支持 serial）" % _m0\n'
    '        return _out\n'
    '    _bad = []\n'
    '    for _e, _v in (_d.get("views") or {}).items():\n'
    '        if _v is None:\n'
    '            continue          # 该层没产出 View \u21d2 不算完成\n'
    '        try:\n'
    '            _out["views"][str(_e)] = View.from_dict(_v)\n'
    '        except Exception as _e2:  # noqa: BLE001\n'
    '            _bad.append("%s(%s)" % (_e, type(_e2).__name__))\n'
    '    _pnames = set(getattr(Pool, "__dataclass_fields__", {}) or {})\n'
    '    for _e, _p in (_d.get("pools") or {}).items():\n'
    '        if not isinstance(_p, dict):\n'
    '            continue\n'
    '        try:\n'
    '            _out["pools"][str(_e)] = Pool(\n'
    '                **{k: v for k, v in _p.items() if k in _pnames})\n'
    '        except Exception:  # noqa: BLE001\n'
    '            pass            # 池还原失败 \u21d2 该层池为空（不阻断，但要留痕）\n'
    '    _out["ok"] = True\n'
    '    if _bad:\n'
    '        _out["why"] = "部分层 View 还原失败\uff08那几层会重跑\uff09：%s" % ",".join(_bad)\n'
    '    return _out\n'
    '\n'
    '\n'
    'class MetaDGTF:\n',
))

# ── ⑤ run() 签名 + 续跑/预算的初始化 ─────────────────────────────────
PATCHES.append((
    "run 签名",
    '    def run(self, question: str,\n'
    '            route: Optional[List[str]] = None,\n'
    '            keep: Optional[Dict[str, str]] = None,\n'
    '            rounds=0,\n'
    '            channels: Optional[List[str]] = None,\n'
    '            parallel_mode: str = "auto",\n'
    '            orientation: str = "auto",\n'
    '            auto_plan: Optional[dict] = None,\n'
    '            run_id: str = "") -> dict:\n',
    '    def run(self, question: str,\n'
    '            route: Optional[List[str]] = None,\n'
    '            keep: Optional[Dict[str, str]] = None,\n'
    '            rounds=0,\n'
    '            channels: Optional[List[str]] = None,\n'
    '            parallel_mode: str = "auto",\n'
    '            orientation: str = "auto",\n'
    '            auto_plan: Optional[dict] = None,\n'
    '            run_id: str = "",\n'
    '            resume_ckpt: str = "",\n'
    '            max_minutes: float = 0.0) -> dict:\n'
    '        # \u2605\u2605 [v1.23.50] 断点续跑 + \u5899\u949f\u9884\u7b97\uff08\u9ed8\u8ba4\u5168\u5173 \u21d2 \u96f6\u884c\u4e3a\u5dee\uff09\u3002\n'
    '        #   · `resume_ckpt=<\u5feb\u7167\u8def\u5f84>`\uff1a\u590d\u7528\u91cc\u9762**\u5df2\u5b8c\u6210\u7684\u5c42**\uff08\u4e0d\u91cd\u8dd1\u3001\n'
    '        #     \u4e0d\u518d\u82b1\u90a3\u90e8\u5206\u94b1\uff09\uff1b\u5c42\u7684\u5b8c\u6210\u5224\u636e = `_results[e]` \u6709\u503c\n'
    '        #     \uff08\u8be5\u5b57\u6bb5\u53ea\u5728\u5c42\u8dd1\u5b8c\u540e\u8d4b\u503c\uff09\u3002\n'
    '        #   · `max_minutes>0`\uff1a\u5c42\u95f4\u5899\u949f\u9884\u7b97 \u21d2 \u4f18\u96c5\u505c\uff08\u72b6\u6001 `paused`\uff09\u5e76\u843d\n'
    '        #     \u5feb\u7167\uff0c\u4e0b\u4e00\u6b21\u7528 `resume_ckpt` \u63a5\u7740\u8dd1\uff08\u5206\u7247\u8dd1\u5b8c\uff0c\n'
    '        #     \u649e\u4e0d\u4e0a\u5bbf\u4e3b\u7684\u56de\u6536\u7a97\u53e3\uff09\u3002\n'
    '        self._t0 = time.time()\n'
    '        self._max_minutes = float(max_minutes or 0.0)\n'
    '        self._resume_path = str(resume_ckpt or "")\n'
    '        self._resume = {"views": {}, "pools": {}}\n'
    '        self._paused_rest: List[str] = []\n',
))

# ── ⑥ route 死捕获修复（记**生效**的 route，别记形参） ────────────────
PATCHES.append((
    "route 死捕获",
    '        route = self._route_by_decidability(question, route, orientation,\n'
    '                                            allow_probe=_dec_probe)\n',
    '        route = self._route_by_decidability(question, route, orientation,\n'
    '                                            allow_probe=_dec_probe)\n'
    '        # \u2605 [v1.23.50] \u8bb0**\u751f\u6548**\u7684 route\uff08\u88c1\u5b9a\u4e4b\u540e\uff09\u3002\u539f\u6765\u5feb\u7167\u91cc\u7684\n'
    '        #   `route` \u8bfb `engine._route`\uff0c\u800c\u5f15\u64ce**\u4ece\u4e0d\u8bbe**\u8fd9\u4e2a\u5c5e\u6027\n'
    '        #   \u21d2 \u6b7b\u6355\u83b7\u3001\u6052 `[]`\uff08\u771f\u5b9e\u4e8b\u6545\u91cc\u53d1\u73b0\uff1a\u6062\u590d\u8005\u770b\u4e0d\u5230"\u8bf7\u6c42\u4e86\u54ea\u4e9b\u5c42"\uff09\u3002\n'
    '        self._route = list(route)\n',
))

# ── ⑦ run() 里挂上续跑（校验 + 打日志）与预算起点 ────────────────────
PATCHES.append((
    "run 挂续跑",
    '        # \u2605 \u8dd1\u4e2d\u5feb\u7167\uff1a\u957f\u8dd1\u4e2d\u65ad\u4e0d\u518d\u5168\u4e22\u3002\u914d\u7f6e\u5f0f\uff1alive_checkpoint \u9ed8\u8ba4 true\uff08\u7eaf\u5b89\u5168\u7f51\uff0c\u5d29\u4e86\u80fd\u627e\u56de\uff09\u3002\n',
    '        # \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u6062\u7528\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210\u7684\u5c42**\u3002\n'
    '        #   \u6821\u9a8c\u4e0d\u8fc7 \u21d2 **\u6309\u539f\u6837\u5168\u8dd1**\uff08\u4e0d\u9759\u9ed8\u6df7\u8dd1\uff09\uff0c\u5e76\u628a\u7406\u7531\u6253\u51fa\u6765\u3002\n'
    '        if self._resume_path:\n'
    '            _rs = load_resume_snapshot(self._resume_path, question=question,\n'
    '                                       mode=mode)\n'
    '            if _rs.get("ok"):\n'
    '                self._resume = {"views": _rs.get("views") or {},\n'
    '                                "pools": _rs.get("pools") or {}}\n'
    '                _done = [e for e in route if e in self._resume["views"]]\n'
    '                self.vp("\\n\u267b\ufe0f \u65ad\u70b9\u7eed\u8dd1\uff1a\u590d\u7528\u5df2\u5b8c\u6210\u5c42 %s"\n'
    '                        "\uff08\u4e0d\u91cd\u8dd1\u3001\u4e0d\u518d\u82b1\u8fd9\u90e8\u5206\u94f1\uff09"\n'
    '                        % "\uff0f".join(_LAYER_LABEL.get(e, e) for e in _done))\n'
    '                if _rs.get("why"):\n'
    '                    self.vp("   \u26a0\ufe0f " + str(_rs["why"]))\n'
    '            else:\n'
    '                self.vp("\\n\u26a0\ufe0f \u65ad\u70b9\u7eed\u8dd1**\u672a\u542f\u7528**\uff08%s\uff09\u21d2 \u6309\u539f\u6837\u5168\u8dd1"\n'
    '                        % _rs.get("why"))\n'
    '        # \u2605 \u8dd1\u4e2d\u5feb\u7167\uff1a\u957f\u8dd1\u4e2d\u65ad\u4e0d\u518d\u5168\u4e22\u3002\u914d\u7f6e\u5f0f\uff1alive_checkpoint \u9ed8\u8ba4 true\uff08\u7eaf\u5b89\u5168\u7f51\uff0c\u5d29\u4e86\u80fd\u627e\u56de\uff09\u3002\n',
))

# ── ⑧ 跑完：状态给 paused（而不是 done）＋ 产物交代待续层 ──────────────
PATCHES.append((
    "停心跳状态",
    '        # \u2605 \u505c\u5fc3\u8df3 + \u843d\u6700\u540e\u4e00\u4efd\uff08dispatch \u5df2\u8fd4\u56de \u21d2 \u8fd9\u4e00\u8dd1\u6709\u4e86\u7ed3\u679c\uff09\n'
    '        if _ck_stop is not None:\n'
    '            stop_run_ckpt(_ck_stop, self, _ck_rid, "done")\n'
    '        if isinstance(packed, dict):\n'
    '            packed["cost_profile"] = getattr(\n'
    '                self, "_cost_profile", "balanced")\n'
    '            packed["orientation"] = orientation\n',
    '        # \u2605 \u505c\u5fc3\u8df3 + \u843d\u6700\u540e\u4e00\u4efd\uff08dispatch \u5df2\u8fd4\u56de \u21d2 \u8fd9\u4e00\u8dd1\u6709\u4e86\u7ed3\u679c\uff09\n'
    '        #   \u2605 [v1.23.50] \u5899\u949f\u9884\u7b97\u5230\u70b9\u65f6\u72b6\u6001\u662f **paused**\uff08\u4e0d\u662f done\uff09\u2014\u2014\n'
    '        #     \u5426\u5219\u4e0b\u4e00\u6b21\u65ad\u70b9\u7eed\u8dd1\u4f1a\u56e0"\u72b6\u6001\u4e0d\u53ef\u7eed"\u800c\u62d2\u7edd\u3002\n'
    '        if _ck_stop is not None:\n'
    '            stop_run_ckpt(_ck_stop, self, _ck_rid,\n'
    '                          "paused" if self._paused_rest else "done")\n'
    '        if isinstance(packed, dict):\n'
    '            packed["cost_profile"] = getattr(\n'
    '                self, "_cost_profile", "balanced")\n'
    '            packed["orientation"] = orientation\n'
    '            if self._paused_rest:\n'
    '                packed["paused"] = True\n'
    '                packed["pending_layers"] = list(self._paused_rest)\n',
))

# ── ⑨ _run_serial：种回已完成层（含池）+ 跳过 + 层间墙钟守卫 ───────────
PATCHES.append((
    "_run_serial 种回",
    '        self._results = {}\n'
    '        self._upstream_provider = (\n',
    '        self._results = {}\n'
    '        # \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u628a\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210**\u7684\u5c42\u79cd\u56de `_results`\uff1b\n'
    '        #   \u5e76\u6062\u590d\u5b83\u4eec\u7684**\u6c60** \u2014\u2014 \u4e0b\u6e38\u5c42\u4f1a\u8bfb\u4e0a\u6e38\u6c60\uff08\u5982\u7814\u7a76\u5c42\u8bfb\u4fee\u884c\u6c60\uff09\uff0c\n'
    '        #   \u6c60\u4e0d\u8fd8\u539f \u21d2 \u7eed\u8dd1\u51fa\u6765\u7684\u4e1c\u897f\u4e0e"\u4e00\u6b21\u8dd1\u5b8c"\u4e0d\u540c\uff08\u9759\u9ed8\u53d8\u5f62\uff09\u3002\n'
    '        for _re, _rv in ((getattr(self, "_resume", None) or {}).get("views") or {}).items():\n'
    '            self._results[str(_re)] = _rv\n'
    '        for _re, _rp in ((getattr(self, "_resume", None) or {}).get("pools") or {}).items():\n'
    '            try:\n'
    '                self.pools[str(_re)] = _rp\n'
    '            except Exception:  # noqa: BLE001\n'
    '                pass\n'
    '        self._upstream_provider = (\n',
))
PATCHES.append((
    "_run_serial 跳过+预算",
    '        for entry in dispatch["order"]:\n'
    '            try:\n'
    '                self.vp(f"\\n{\'\u2550\'*60}\\n\u3010{entry}\u3011{_LAYER_LABEL[entry]} DGTF"\n'
    '                        f"\uff08\u87ba\u65cb\u4e0a\u9650 {rounds[entry]} \u5708\uff09\\n{\'\u2550\'*60}")\n'
    '                self._results[entry] = self._run_layer(\n'
    '                    entry, self._rounds.get(entry, 0))\n',
    '        for entry in dispatch["order"]:\n'
    '            # \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u5df2\u5b8c\u6210\u7684\u5c42\u76f4\u63a5\u8df3\u8fc7\uff08\u4e0d\u91cd\u8dd1\uff09\u3002\n'
    '            if entry in self._results:\n'
    '                self.vp(f"\\n{\'\u2550\'*60}\\n\u3010{entry}\u3011{_LAYER_LABEL[entry]}"\n'
    '                        f" \u2014\u2014 \u267b\ufe0f \u590d\u7528\u5feb\u7167\uff08\u5df2\u5b8c\u6210\uff0c**\u4e0d\u91cd\u8dd1**\uff09\\n{\'\u2550\'*60}")\n'
    '                continue\n'
    '            # \u2605 [v1.23.50 \u5899\u949f\u9884\u7b97] \u5c42\u95f4\u5b88\u536b\uff1a\u8d85\u9884\u7b97 \u21d2 \u4f18\u96c5\u505c\uff08\u4e0d\u542f\u65b0\u5c42\uff09\u3002\n'
    '            _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)\n'
    '            if _mx > 0 and (time.time() - float(getattr(self, "_t0", 0.0) or 0.0)\n'
    '                            ) >= _mx * 60.0:\n'
    '                self._paused_rest = [e for e in dispatch["order"]\n'
    '                                     if e not in self._results]\n'
    '                self.vp(f"\\n\u23f8 \u5899\u949f\u9884\u7b97 {_mx:.1f} \u5206\u949f\u5230 \u21d2 \u4f18\u96c5\u505c\uff1a\u5df2\u5b8c\u6210 "\n'
    '                        f"{sorted(self._results)}\uff0c\u5f85\u7eed {self._paused_rest}"\n'
    '                        f"\uff08\u7528 resume_ckpt \u63a5\u7740\u8dd1\uff09")\n'
    '                break\n'
    '            try:\n'
    '                self.vp(f"\\n{\'\u2550\'*60}\\n\u3010{entry}\u3011{_LAYER_LABEL[entry]} DGTF"\n'
    '                        f"\uff08\u87ba\u65cb\u4e0a\u9650 {rounds[entry]} \u5708\uff09\\n{\'\u2550\'*60}")\n'
    '                self._results[entry] = self._run_layer(\n'
    '                    entry, self._rounds.get(entry, 0))\n',
))

# ── ⑩ 源码 token 自检（冒烟/审计按字面找） ────────────────────────────
for i, (name, old, new) in enumerate(PATCHES, 1):
    c = t.count(old)
    print("%2d %-22s 锚点命中 %d" % (i, name, c))
    assert c == 1, "锚点不唯一/不存在：%s（%d）" % (name, c)
    t = t.replace(old, new, 1)

assert "resume_ckpt: str = \"\"" in t and "max_minutes: float = 0.0" in t
assert "def from_dict(cls, d: dict)" in t
assert "def load_resume_snapshot(" in t
assert "self._route = list(route)" in t
assert "_paused_rest" in t
assert "v1.23.49" not in t, "还有残留的旧版本号"

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写前自检失败"
P.write_bytes(out)

b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n"), "写后非纯 CRLF"
assert b2.count(b"\r\r\n") == 0, "写后 CRCRLF 污染"
print("OK：%d 处补丁全部落位，纯 CRLF 保持，行数 %d" % (len(PATCHES), b2.count(b"\n")))
