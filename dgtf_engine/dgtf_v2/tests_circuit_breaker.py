# -*- coding: utf-8 -*-
"""失败熔断判据（opt-in）。

要钉住的三件事（少一件就会假绿）
--------------------------------
1. **默认关 = 零行为差**：`enabled=False` 时尝试次数、返回值、熔断状态都不变。
   这是「只允许更好不能后退」的前提 —— 不打开的人不该感到任何差别。
2. **打开后真的不再发 HTTP**：不是「日志里写了熔断」，而是底层 client
   的调用计数**停在原地**。
3. **省下的墙钟真发生**（成本判据）：同一个慢桩下，熔断臂的总耗时必须
   显著低于不熔断臂 —— 否则「熔断」只是换了个错误消息。

另加：冷却后必须**放行试探**（否则一次抖动会把整跑永久锁死），
试探成功必须**复位**（否则熔断不会退出）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import time
from types import SimpleNamespace

V2 = pathlib.Path(__file__).resolve().parent
ENG = V2 / "engine"
sys.path.insert(0, str(V2.parent))

PASS, FAIL = [], []


def ck(n, ok, info=""):
    (PASS if ok else FAIL).append(n)
    print(("  OK  " if ok else "  FAIL") + " " + n + (("  — " + str(info)) if info else ""))


def _latest():
    vs = []
    for p in ENG.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            vs.append((tuple(int(x) for x in m.groups()), p))
    return sorted(vs)[-1][1]


def _load(path, tag):
    spec = importlib.util.spec_from_file_location(tag, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[tag] = mod
    spec.loader.exec_module(mod)
    return mod


class _Stub:
    """底层 client 桩：可配置「前 N 次失败」「每次耗时」「成功返回」。"""

    def __init__(self, fail_times=None, delay=0.0):
        self.calls = 0
        self.fail_times = fail_times
        self.delay = delay
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kw):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail_times is None or self.calls <= self.fail_times:
            raise RuntimeError("503 Service Unavailable")
        return SimpleNamespace(
            model=str(kw.get("model") or "stub"),
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="OK-CONTENT"),
                finish_reason="stop")],
            usage=SimpleNamespace(total_tokens=10))


def _cfg(cb=None, retries=3):
    api = {"key": "t", "default_model": "stub", "base_url": "http://x/v1",
           "timeout": 2, "max_retries": retries,
           # 退避压到近似 0：判据要测熔断，不要测退避
           "retry_backoff": 0.01}
    if cb is not None:
        api["circuit_breaker"] = cb
    return {"api": api}


def _make(mod, stub, cfg):
    llm = mod.LLM(cfg)
    llm.client = stub
    return llm


def main():
    path = _latest()
    print("  引擎：%s" % path.name)
    mod = _load(path, "_eng_cb")

    # ── 1. 默认关：零行为差 ────────────────────────────
    ck("配置缺省时 cb_enabled=False（默认关）",
       mod.LLM(_cfg()).cb_enabled is False)
    stub0 = _Stub(fail_times=None)
    llm0 = _make(mod, stub0, _cfg())
    t0 = time.monotonic()
    try:
        llm0.call("s", "u", 0.0, 10, stage="probe")
        raised = False
    except Exception:
        raised = True
    ck("关闭时仍按 max_retries 逐次尝试（3 次）", stub0.calls == 3, stub0.calls)
    ck("关闭时最终抛错（不是静默返回空）", raised)
    ck("★ 关闭时不写熔断状态（零行为差）",
       llm0.cb_open_until == 0.0 and llm0.cb_opened_times == 0
       and llm0.cb_skipped_calls == 0,
       (llm0.cb_open_until, llm0.cb_opened_times, llm0.cb_skipped_calls))

    # ── 2. 打开后熔断：底层 client 调用数停在原地 ─────────
    cb = {"enabled": True, "fail_threshold": 3, "cooldown_sec": 60}
    stub1 = _Stub(fail_times=None)
    llm1 = _make(mod, stub1, _cfg(cb))
    try:
        llm1.call("s", "u", 0.0, 10, stage="probe")
    except Exception:
        pass
    ck("首次 call 用满 3 次尝试后熔断", stub1.calls == 3, stub1.calls)
    ck("熔断被记一次", llm1.cb_opened_times == 1, llm1.cb_opened_times)

    calls_before = stub1.calls
    skipped_ok = True
    for _ in range(4):
        try:
            llm1.call("s", "u", 0.0, 10, stage="probe")
            skipped_ok = False
        except Exception as e:
            if "circuit_open" not in str(e):
                skipped_ok = False
    ck("★ 熔断中 4 次调用全部快速失败且错误可识别",
       skipped_ok)
    ck("★ 熔断中底层 client 一次都没被调用（真的没发 HTTP）",
       stub1.calls == calls_before, "%d -> %d" % (calls_before, stub1.calls))
    ck("跳过次数被记账", llm1.cb_skipped_calls == 4, llm1.cb_skipped_calls)

    # ── 3. 冷却后半开：放行试探；成功即复位 ───────────────
    cb2 = {"enabled": True, "fail_threshold": 2, "cooldown_sec": 0.15}
    stub2 = _Stub(fail_times=2)     # 前 2 次失败 ⇒ 触发熔断，之后成功
    llm2 = _make(mod, stub2, _cfg(cb2))
    try:
        llm2.call("s", "u", 0.0, 10, stage="probe")
    except Exception:
        pass
    ck("阈值 2：两次失败后熔断", llm2.cb_open_until > 0, llm2.cb_open_until)
    n_after_trip = stub2.calls
    time.sleep(0.25)                # 过冷却期
    out = llm2.call("s", "u", 0.0, 10, stage="probe")
    ck("★ 冷却后放行试探（不是永久锁死）", stub2.calls == n_after_trip + 1,
       "%d -> %d" % (n_after_trip, stub2.calls))
    ck("试探成功 ⇒ 返回内容", out == "OK-CONTENT", out)
    ck("★ 试探成功 ⇒ 连续失败计数复位（熔断会退出）",
       llm2.cb_consec_fail == 0, llm2.cb_consec_fail)

    # ── 4. 成本判据：省下的墙钟真发生 ────────────────────
    DELAY, N_CALLS = 0.08, 6
    slow_off = _Stub(fail_times=None, delay=DELAY)
    llm_off = _make(mod, slow_off, _cfg(None))
    t = time.monotonic()
    for _ in range(N_CALLS):
        try:
            llm_off.call("s", "u", 0.0, 10, stage="probe")
        except Exception:
            pass
    t_off = time.monotonic() - t

    slow_on = _Stub(fail_times=None, delay=DELAY)
    llm_on = _make(mod, slow_on, _cfg(cb))
    t = time.monotonic()
    for _ in range(N_CALLS):
        try:
            llm_on.call("s", "u", 0.0, 10, stage="probe")
        except Exception:
            pass
    t_on = time.monotonic() - t

    ck("★ 成本判据：熔断臂墙钟显著更短（省时间真发生）",
       t_on < t_off * 0.5, "off=%.2fs on=%.2fs" % (t_off, t_on))
    ck("★ 成本判据：熔断臂 HTTP 次数显著更少",
       slow_on.calls < slow_off.calls,
       "off=%d on=%d" % (slow_off.calls, slow_on.calls))
    ck("省下的次数与记账一致",
       llm_on.cb_skipped_calls == N_CALLS - 1, llm_on.cb_skipped_calls)

    # ── 5. 产物出口（静态：两个键真的写进 packed）──────────
    src = path.read_text(encoding="utf-8")
    ck("产物出口含 llm_cb_opened", '_pack["llm_cb_opened"]' in src)
    ck("产物出口含 llm_cb_skipped", '_pack["llm_cb_skipped"]' in src)
    ck("默认配置登记 circuit_breaker（不是只读不声明）",
       '"circuit_breaker"' in src and '"fail_threshold"' in src)

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  - " + f)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
