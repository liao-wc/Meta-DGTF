# -*- coding: utf-8 -*-
"""P1c：**心跳级调度** `_schedule_tick` —— 运行中主动调整（不等失败）。

## 依据
**Heartbeat-Driven Activity Scheduling**（arXiv 2604.14178, 2026）：
用**周期性「心跳」主动**编排认知模块，**不是**等失败才反思（reactive）；
调度策略由**历史日志元学习**改进。

## 在本引擎里的落点（**层级心跳**，务实且可判据化）
`_finalize_layer_common`（两条跑圈通道共用的收尾）**末尾** —— 此刻：
  · `view` 在手上 ⇒ **读数可取**（`_readings_bundle`）；
  · 下一层还没跑 ⇒ **调整来得及**。
⇒ 读**已有读数**（不新增计算）→ 出调整 → 过 `ControlSurface`（唯一收口）
  → 写 trace（可追溯）。

★ 为什么**不做圈级**：圈级要在 `_before_round` 读「上一圈」的读数，而那需要
  跨圈状态传递（`view` 每圈新建）；层级先行、圈级待跨圈状态就位后再做。

## 首批三条规则（都可判据化）
  ① `candidate_yield.verdict == "collapsed"`（复述多）
     ⇒ 放宽**下一层**对撞/探针类环节的联网（`web.allow.<stage>` = True）
  ② 职责 S 低于当前 floor ⇒ 记一条 `carve_first`（**跨跑类**，见 `_EML_RECORD_ONLY`）
  ③ 语义停滞（`sem_stagnation` 非空）⇒ 允许探针环节联网

## 三条纪律
  · **默认零行为差**：读数取不到 ⇒ 什么都不做；调成**同值** ⇒ `write` 判 noop 不落；
  · **全部经控制面**：可追溯（必带 why + trace_ref）+ 可控（白名单 + 边界）；
  · **绝不写配置**（红线：建议与执行分开）——只改本次跑的内存态。

## 配套改动（一处动作、两处同步）
  · `_web_augment` 要**读**控制面的 `web.allow.<stage>` ⇒ 运行中放的宽才真生效；
  · `run` 里把 `control` 也注入线程上下文（与 `web_searcher` 同路）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.36.py"

# ── A：在 `_eml_apply` 之前插入 `_schedule_tick`（同类、相邻，便于阅读）──
ANCHOR_FN = '''    def _eml_apply(self, rounds_plan: dict) -> list:'''

NEW_FN = '''    #: [心跳] 允许被「放宽联网」的环节 —— 只列**最需要外部刺激**的那一类。
    #: ★ 不列全 30 个：放宽是**有代价**的（每次调用都检索），只挑对撞/探针这类
    #:   「卡住时最该问外面」的环节。
    _TICK_WEB_RELAX = ("ing", "probe_research", "probe_duel", "probe_meta")

    def _schedule_tick(self, entry: str, view) -> None:
        """[心跳 · 层级] 层收尾时**主动**检查 ⇒ 调下一层的策略。

        ★ 依据 Heartbeat-Driven Scheduling：**周期性主动**编排，不是等失败才反思。
        ★ 读**已有读数**（`_readings_bundle`，不新增计算）；调整**全过**
          `ControlSurface`（可追溯 + 可控）；**默认零行为差**
          （取不到读数 ⇒ 不动；同值 ⇒ `write` 判 noop 不落）。
        ★ 只改**本次跑的内存态**，绝不写配置（红线：建议与执行分开）。
        """
        try:
            _b = _readings_bundle(view)
        except Exception:
            return
        _q = _b.get("quant") or {}
        # ① 候选产出率 collapsed（复述多）⇒ 放宽下一层的联网
        if str(_q.get("候选") or "") == "collapsed":
            for _st in self._TICK_WEB_RELAX:
                self._control.write(
                    "web.allow.%s" % _st, True,
                    why="心跳：本层候选产出率 collapsed（复述多）⇒ "
                        "放宽该环节联网，让它能问外面",
                    trace_ref="tick:web_relax:%s" % entry)
        # ③ 语义停滞 ⇒ 同样允许探针类环节联网（与 ① 的机制同路，理由不同）
        if str(getattr(view, "sem_stagnation", "") or "").strip():
            for _st in ("probe_research", "probe_meta"):
                self._control.write(
                    "web.allow.%s" % _st, True,
                    why="心跳：本层语义停滞 ⇒ 允许探针环节联网找外部刺激",
                    trace_ref="tick:stag_web:%s" % entry)
        # ② 职责不足 ⇒ 记一条 carve_first（跨跑类，落在 `_EML_RECORD_ONLY`）
        try:
            _d = _b.get("duty")
            _fl = float(getattr(self, "_duty_floor", 0.0) or 0.0)
            if _d is not None and _fl and float(_d) < _fl:
                _trace_note(view, "decide",
                            what="是否把「职责不足」升级为动作",
                            options=[{"opt": "记 carve_first（跨跑优先雕）",
                                      "verdict": "taken",
                                      "why": "S=%s < floor=%s" % (_d, _fl)},
                                     {"opt": "本跑内硬插一次雕",
                                      "verdict": "rejected",
                                      "why": "会打断已定的圈序；且跨跑类动作"
                                             "不属于本跑的执行面"}],
                            chosen="carve_first", conf=0.7)
        except Exception:
            pass
        self._control.write(
            "duty_floor", float(getattr(self, "_duty_floor", 0.0) or 0.0),
            why="心跳：占位（同值 ⇒ noop，不落 applied）",
            trace_ref="tick:noop:%s" % entry)

    def _eml_apply(self, rounds_plan: dict) -> list:'''

# ── B：`_finalize_layer_common` 末尾接线 ──
OLD_WIRE = '''        # ★ [读数全量显示 · 运行中] 本层的全部读数打**一行**（不刷屏、不省略）。
        #   渲染自 `_readings_bundle`（与产物的总表**同源**，不可能漂移）。
        #   ★ 走 `logger`（**不受 verbose 控制**）：读数是事后审计用的，
        #     不是「啰嗦模式」的进度感 —— 用 vp 会被 verbose=False 静默吞掉。
        try:
            logger.info(_readings_line(entry, view))
        except Exception:
            pass'''
NEW_WIRE = '''        # ★ [读数全量显示 · 运行中] 本层的全部读数打**一行**（不刷屏、不省略）。
        #   渲染自 `_readings_bundle`（与产物的总表**同源**，不可能漂移）。
        #   ★ 走 `logger`（**不受 verbose 控制**）：读数是事后审计用的，
        #     不是「啰嗦模式」的进度感 —— 用 vp 会被 verbose=False 静默吞掉。
        try:
            logger.info(_readings_line(entry, view))
        except Exception:
            pass

        # ★ [心跳] 层收尾时**主动**检查 ⇒ 调下一层的策略（不等失败）。
        #   依据 Heartbeat-Driven Scheduling；全部经控制面（可追溯 + 可控）。
        try:
            self._schedule_tick(entry, view)
        except Exception as _e_tk:
            logger.warning("心跳调度失败：%s", _e_tk)'''

# ── C：给 `WebSearchGate` 加**运行时放宽集**（不碰配置）──
OLD_GATE_INIT = '''    def allow(self, stage: str, round_no: int) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        if not bool((self.cfg.get("stages") or {}).get(stage, False)):
            return False, "stage " + repr(stage) + " 未授权"'''
NEW_GATE_INIT = '''    def allow(self, stage: str, round_no: int) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        # ★ [运行中放宽] `_relaxed` 由心跳调度（经控制面）在**本次跑内**填充，
        #   **不改配置**（`cfg` 只读）⇒ 放开的只是「授权」这一道；
        #   配额 / 连续失败降级 / 各 stage 上限**照旧生效**（可控性不降）。
        _relaxed = getattr(self, "_relaxed", None) or ()
        if not bool((self.cfg.get("stages") or {}).get(stage, False)) \\
                and stage not in _relaxed:
            return False, "stage " + repr(stage) + " 未授权"'''
OLD_GATE_CLS = '''class WebSearchGate:'''
NEW_GATE_CLS = '''class WebSearchGate:
    #: [运行中放宽] 由心跳调度填（经控制面）——**只影响本次跑的内存态**。
    _relaxed: set = set()'''

# ── C2：`_web_search` 里把控制面的放宽同步进 Gate ──
OLD_C2 = '''        gate = getattr(self, "_web_gate", None)
        client = getattr(self, "_web_client", None)
        if gate is None or client is None:
            return []'''
NEW_C2 = '''        gate = getattr(self, "_web_gate", None)
        client = getattr(self, "_web_client", None)
        if gate is None or client is None:
            return []
        # ★ [心跳放宽] 把控制面里**本次跑内**放开的环节同步进 Gate 的放宽集
        #   （`_relaxed` 是内存态；配额与降级判定照旧 ⇒ 可控性不降）。
        try:
            _surf = getattr(self, "_control", None)
            if _surf is not None:
                _relaxed = set()
                for _st in (self._TICK_WEB_RELAX or ()):
                    if _surf.read("web.allow.%s" % _st) is True:
                        _relaxed.add(_st)
                gate._relaxed = _relaxed
        except Exception:
            pass'''

# ── D：`run` 注入 control ──
OLD_INJ = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""))'''
NEW_INJ = '''            _llm_ctx_set(web_searcher=self._web_search,
                         question=str(question or ""),
                         control=self._control)'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_FN, NEW_FN, "A 心跳方法"),
                          (OLD_WIRE, NEW_WIRE, "B 层收尾接线"),
                          (OLD_GATE_CLS, NEW_GATE_CLS, "C1 Gate 放宽集"),
                          (OLD_GATE_INIT, NEW_GATE_INIT, "C2 Gate.allow 判放宽"),
                          (OLD_C2, NEW_C2, "C3 同步放宽进 Gate"),
                          (OLD_INJ, NEW_INJ, "D 注入 control")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert s.count("def _schedule_tick") == 1
    assert s.count("self._schedule_tick(entry, view)") == 1
    assert "control=self._control" in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 心跳调度已加；行数 %d" % out.count(b"\n"))


main()
