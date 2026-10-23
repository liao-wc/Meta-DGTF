# -*- coding: utf-8 -*-
"""[v1.23.39 判据] 按需联网**四层一致**：声明即查（声明不再被逐环节开关挡）。

三层验证（本项目铁律：源码级只能证「接线写了」）：
  ① 构造性·正：修行层环节（`stages` 默认 false）声明 `===WEB-NEED===`
     ⇒ Gate **放行**、`_web_search` 真被调用（v1.23.38 这里会被拒）。
  ② 构造性·负一：**总闸关** ⇒ 即便声明也拒（成本闸门不因按需而失效）。
  ③ 构造性·负二：**配额用尽** ⇒ 按需路径同样拒（防「按需=无限检索」）。
  ④ 静态：`on_demand` 只从 `used_as == "record"` 一处产生（不扩散）。
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.38.py"


def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main():
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    mod = load(SRC, "tgt39")

    # ── ④ 静态：on_demand 的产生点唯一 ──
    n_prod = len(re.findall(r'on_demand\s*=\s*\(str\(used_as\)\s*==\s*"record"\)', src))
    if n_prod != 1:
        bad.append("[按需四层] `on_demand` 的产生点 %d 处（要求 1：只从 "
                   "used_as=record 来）" % n_prod)
    if "on_demand: bool = False" not in src:
        bad.append("[按需四层] `allow` 缺 `on_demand` 形参")

    # ── 构造性：直接驱动 WebSearchGate（真对象，不打桩）──
    def _cfg(enabled=True):
        return {"web_search": {"enabled": enabled,
                               "stages": {"research_evidence": True}}}

    # ① 正：修行层环节（未授权）**按需**放行；非按需仍拒
    try:
        g = mod.WebSearchGate(_cfg(True), run_id="probe")
        ok_demand, why_demand = g.allow("ing", 1, on_demand=True)
        if not ok_demand:
            bad.append("[按需四层] 修行层环节按需仍被拒：%s（声明了也查不到 ⇒ "
                       "四层不一致的老问题没修好）" % why_demand)
        ok_plain, why_plain = g.allow("ing", 1)
        if ok_plain:
            bad.append("[按需四层] 非按需路径被放行了（逐环节静态开关失效了！）")
        # 已授权 stage 的两条路径都该放行
        if not g.allow("research_evidence", 1, on_demand=True)[0]:
            bad.append("[按需四层] 已授权 stage 的按需路径反被拒")
        if not g.allow("research_evidence", 1)[0]:
            bad.append("[按需四层] 已授权 stage 的常规路径被拒（回归）")
    except Exception as e:
        bad.append("[按需四层] Gate 驱动抛错：%r" % (e,))

    # ② 负一：总闸关 ⇒ 按需也拒
    try:
        g2 = mod.WebSearchGate(_cfg(False), run_id="probe")
        ok2, why2 = g2.allow("ing", 1, on_demand=True)
        if ok2:
            bad.append("[按需四层] **总闸关**时按需仍放行（成本闸门失效！）")
    except Exception as e:
        bad.append("[按需四层] 总闸负对照抛错：%r" % (e,))

    # ③ 负二：配额用尽 ⇒ 按需拒（本跑总配额 3，故意打满）
    try:
        cfg3 = _cfg(True)
        cfg3["web_search"]["quota"] = {"per_run_total": 2,
                                       "per_stage_total": 8,
                                       "per_stage_round": 2}
        g3 = mod.WebSearchGate(cfg3, run_id="probe")
        for i in range(2):
            g3.note_call("ing", 1)
        ok3, why3 = g3.allow("ing", 1, on_demand=True)
        if ok3:
            bad.append("[按需四层] 配额打满后按需仍放行（按需=无限检索！）")
        elif "配额" not in why3:
            bad.append("[按需四层] 配额拒绝原因不含「配额」：%s" % why3)
    except Exception as e:
        bad.append("[按需四层] 配额负对照抛错：%r" % (e,))

    # ── 端到端：`_web_search` 收到 used_as="record" 时真的过 Gate ──
    try:
        seen = []

        class _Gate:
            def __init__(self):
                self._relaxed = set()

            def allow(self, stage, round_no, on_demand=False):
                seen.append((stage, bool(on_demand)))
                return True, ""

            def note_call(self, stage, round_no):
                pass

            def note_failure(self, kind=""):
                return False

            def note_success(self):
                pass

        class _Client:
            def search(self, q):
                return ([{"claim": "命中", "url": "http://x", "tier": 3}], "")

        class _Pool:
            web_results = []
            web_errors = []
            meta = []
            _web_cfg = None
            web_as_evidence = False

        class _Owner:
            config = {"web_search": {"enabled": True, "stages": {}}}
            pools = {"1": _Pool()}
            _control = None
            _TICK_WEB_RELAX = ()

        o = _Owner()
        o._web_gate, o._web_client = _Gate(), _Client()
        fn = mod.MetaDGTF._web_search
        r = fn(o, "ing", ["测试查询"], 1, "record", 0)
        if not seen:
            bad.append("[按需四层] `_web_search` 没调 Gate（接线不可达）")
        elif not seen[0][1]:
            bad.append("[按需四层] `_web_search` 未把按需标记传给 Gate：%r"
                       % (seen[0],))
        if not r:
            bad.append("[按需四层] 按需检索返回空（声明后仍查不到）")
    except Exception as e:
        bad.append("[按需四层] 端到端驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.39 按需联网四层一致（修行层声明即查 · 非按需仍受环节开关 · "
          "总闸/配额照旧压得住 · on_demand 单一来源）全过")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)