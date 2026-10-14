# -*- coding: utf-8 -*-
"""P1a：通用行为 trace 地基（`View.trace` 三层 + 决策链含被否选项 + 参数全记）。

## 前沿依据（见 `_方案_v12336_调度学习一体.md`）
  · **三层模型**（agent observability）：L1 决策（why）/ L2 动作（what）/
    L3 归因（matter）；
  · **`decision.chain` span kind + Decision Log Format**：**必须记「考虑过的
    全部选项」** —— 审计要看得见**「没走的路」**；
  · **Observing ≠ Auditability**：观测平台会采样/截断，**审计级不许采样**；
  · **95% 盲点**：不到 5% 的 agent 记了 temperature/top-k/seed ⇒ 本次把它们
    变成**可追溯属性**。

## 设计纪律（四条）
  1. **记被否选项**（不只记选了什么）；
  2. **LLM 调用记全参数**（model / temperature / max_tokens / thinking / trunc）；
  3. **不采样、不截断**；
  4. **空值不写**（缺读数 ≠ 读数是空 —— 与 `quant_readings` 同纪律）。

## 零行为差
  新字段默认空列表 ⇒ **不出键**（同 `quant_readings` 的「有才出」）；
  不调 `trace()` 就与今天逐字相同。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A：View 字段 ──
ANCHOR_FIELD = '''    quant_readings: Dict[str, dict] = field(default_factory=dict)'''
NEW_FIELD = '''    quant_readings: Dict[str, dict] = field(default_factory=dict)
    #: [通用行为 trace] 三层：`decide`（决策，含**被否选项**）/ 动作（llm/web/
    #: judge/pool/stop）/ `outcome`（归因：动作前后的读数）。
    #: ★ 与两条专用 trace（`goal_trace` / `duty_trace`）**并存**，不合并 ——
    #:   那两条各自被判据读；本字段是**追加**的通用层。
    #: ★ 不采样、不截断（审计级：观测平台可以采样，审计不行）。
    #: ★ 空 ⇒ **不出键**（与 `quant_readings` 同纪律）。
    trace_log: List[dict] = field(default_factory=list)'''

# ── B：to_dict 出口 ──
ANCHOR_EXPORT = '''        if getattr(self, "quant_readings", None):
            d["quant_readings"] = {
                str(k): dict(v) for k, v in (self.quant_readings or {}).items()
                if isinstance(v, dict) and v
            }'''
NEW_EXPORT = '''        if getattr(self, "quant_readings", None):
            d["quant_readings"] = {
                str(k): dict(v) for k, v in (self.quant_readings or {}).items()
                if isinstance(v, dict) and v
            }
        # ★ [通用行为 trace] **有才出**（空 ⇒ 不出键，与上面同纪律）。
        #   全量导出、**不截断**：审计级 trace 不许采样（依据见方案 P1a）。
        if getattr(self, "trace_log", None):
            d["trace_log"] = [dict(x) for x in self.trace_log
                              if isinstance(x, dict) and x]'''

# ── C：方法（插在 `_quant_note` 之前 —— 同一批「写入口」放一起）──
ANCHOR_FN = '''def _quant_note(view, key: str, val) -> None:'''
NEW_FN = '''def _trace_note(view, kind: str, **kw) -> None:
    """[通用行为 trace] 把一条行为记录写进 `view.trace_log`（**唯一写入口**）。

    ★ 为什么是**模块级函数**而不是 `View` 的方法：与 `_quant_note` 同因 ——
      调用点分布在 `DGTF` 与 `MetaDGTF`（两类**无继承关系**），做成方法会让
      另一侧解析不到 ⇒ `AttributeError` 被静默吞掉（本项目栽过）。
    ★ 只依赖 `view`，不碰 self。
    ★ **空值不写**：`None` / `""` / `[]` / `{}` 一律跳过 —— 缺读数 ≠ 读数是空。
    ★ **不截断**：调用方给多少写多少（审计级）。
    """
    if view is None or not kind:
        return
    try:
        _log = getattr(view, "trace_log", None)
        if _log is None:
            view.trace_log = []
            _log = view.trace_log
        _rec = {"kind": str(kind), "seq": len(_log) + 1}
        for _k, _v in (kw or {}).items():
            if _v is None or _v == "" or _v == [] or _v == {}:
                continue
            _rec[str(_k)] = _v
        _log.append(_rec)
    except Exception:
        pass


def trace_decide(view, what, options, chosen, why, conf=None) -> None:
    """[L1 决策] 记一条决策 —— **必须带上「考虑过的全部选项」**。

    ★ 依据 `decision.chain` span kind 与 Decision Log Format：审计要能看见
      **「没走的路」**。`options` 每项形如
      `{"opt": "放宽联网", "verdict": "taken", "why": "候选产出率 0.0"}`。
    ★ 只传 `chosen` 不传 `options` = **不合规**（本函数要求 options 非空才写）。
    """
    _opts = [o for o in (options or []) if o]
    if not _opts:
        return                    # 没有备选就不算决策（不许写空壳）
    _trace_note(view, "decide", what=what, options=_opts,
                chosen=chosen, why=why, conf=conf)


def trace_outcome(view, ref, **kw) -> None:
    """[L3 归因] 记一条动作的**效果**（动作前后读数对比）。

    ★ 为什么需要：L1/L2 只说「做了什么」，L3 才回答「有没有用」——
      而这正是 slow path（EML）学习**唯一**能依赖的信号。
    """
    if ref is None or ref == "":
        return
    _trace_note(view, "outcome", ref=ref, **kw)


def _quant_note(view, key: str, val) -> None:'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_FIELD, NEW_FIELD, "A 字段"),
                          (ANCHOR_EXPORT, NEW_EXPORT, "B 出口"),
                          (ANCHOR_FN, NEW_FN, "C 写入口函数")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    # ★ 1 定义 + 2 处内部调用（trace_decide / trace_outcome）= **3**。
    #   第一次我把断言写成 2 ⇒ 当场判红（断言算错不是缺陷，但要一次算对）。
    assert s.count("_trace_note") == 3, \
        "应为 1 定义 + 2 调用（实得 %d）" % s.count("_trace_note")
    assert s.count("def trace_decide") == 1 and s.count("def trace_outcome") == 1
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK P1a trace 地基已加；行数 %d" % out.count(b"\n"))


main()
