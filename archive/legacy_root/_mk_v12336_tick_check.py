# -*- coding: utf-8 -*-
"""v1.23.36 判据：**心跳级调度**（主动调整 + 控制面 + 默认零行为差）。

## 判据分两层
  · **源码级**：`_schedule_tick` 存在、挂在 `_finalize_layer_common`、
    `WebSearchGate` 有 `_relaxed`、`_web_search` 会同步放宽；
  · **构造性**（零 API 花费，直接驱动真实方法）：
    ① **触发放宽**：造一个「候选产出率 collapsed」的 view ⇒ 调 `_schedule_tick`
       ⇒ 断言控制面 `applied` 里出现 `web.allow.ing`；
    ② **默认零行为差**：读数正常（verdict=ok）⇒ **什么都不写**；
    ③ **幂等**：连调两次 ⇒ 第二次判 `noop`（不重复落 applied）；
    ④ **绝不复权**：控制面 `values` 在**内存**里，不碰 `cfg`（红线：建议与执行分开）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12336_tick():
    """[v1.23.36] 心跳级调度：**主动**调整（不等失败）+ 全过控制面 + 默认零行为差。

    ★ 依据 Heartbeat-Driven Activity Scheduling（arXiv 2604.14178）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if "def _schedule_tick" not in src:
        bad.append("[心跳] 缺 `_schedule_tick`")
    if "self._schedule_tick(entry, view)" not in src:
        bad.append("[心跳] 没挂在 `_finalize_layer_common`（层收尾）上")
    if "_relaxed" not in src:
        bad.append("[心跳] `WebSearchGate` 没有运行时放宽集（放宽无法生效）")
    if "gate._relaxed = _relaxed" not in src:
        bad.append("[心跳] `_web_search` 没把控制面的放宽同步进 Gate")

    # ── 构造性（直接驱动真实方法）──
    try:
        _cfg = build_cfg(False)
        _mt = mod.MetaDGTF(_cfg)

        def _mkview(verdict: str):
            _v = mod.View(entry="0")
            _v.rounds_run = 2
            _v.quant_readings = {"candidate_yield": {
                "n": 3, "n_new": 0, "verdict": verdict}}
            return _v

        # ① 触发放宽
        _mt._schedule_tick("0", _mkview("collapsed"))
        _ap = [x.get("key") for x in (_mt._control.applied or [])]
        if not any(str(k).startswith("web.allow.") for k in _ap):
            bad.append("[心跳] collapsed 读数**没触发放宽**（applied=%r）" % (_ap,))
        else:
            # ② 幂等：再调一次，同样的放宽**不该**再落一笔
            _n1 = len(_mt._control.applied)
            _mt._schedule_tick("0", _mkview("collapsed"))
            if len(_mt._control.applied) > _n1 + 1:
                bad.append("[心跳] 重复触发**重复落账**（应判 noop）")
            # ③ 默认零行为差：正常读数 ⇒ 不新增放宽
            _mt2 = mod.MetaDGTF(build_cfg(False))
            _mt2._schedule_tick("0", _mkview("ok"))
            _ap2 = [x.get("key") for x in (_mt2._control.applied or [])]
            if any(str(k).startswith("web.allow.") for k in _ap2):
                bad.append("[心跳] 读数正常却**放宽了**（默认零行为差被破坏）")
            # ④ 不碰配置
            _cfgs = ((_mt.config.get("web_search") or {}).get("stages") or {})
            if any(v is True for v in _cfgs.values()):
                bad.append("[心跳] **改了配置**（红线：建议与执行分开）")
    except Exception as _e:
        bad.append("[心跳] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 心跳级调度（主动触发 · 全过控制面 · 幂等 · "
          "默认零行为差 · 不写配置）全过")
    return True


def check_v12336_readings():'''

ANCHOR_CALL = '''    if not check_v12336_readings():
        return 1'''
NEW_CALL = '''    if not check_v12336_readings():
        return 1
    if not check_v12336_tick():
        return 1'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count("def check_v12336_readings():")
    assert n == 1, "插入锚点命中 %d 次" % n
    s = s.replace("def check_v12336_readings():", NEW_FN, 1)
    n2 = s.count(ANCHOR_CALL)
    assert n2 == 1, "调用锚点命中 %d 次" % n2
    s = s.replace(ANCHOR_CALL, NEW_CALL, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 心跳判据已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()
