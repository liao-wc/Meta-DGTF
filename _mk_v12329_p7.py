#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 7 阶段：B1 规则层统一接线（整体自洽修复）。

问题（冒烟 v1235 [1d]/[1e] 抓出）：规则层只接在 `_decide_parallel_mode`
上，而 `plan_resources` / `auto_plan(llm=...)` 两处分派仍直接吃 LLM 结果
⇒ 同一问题三处模式决策**分叉**。

修法：规则逻辑提为模块级唯一实现 `mode_rule(q)`；三处分派点统一先走
规则，命中即定案（省一次 LLM 调用），拿不准才回落；rounds 走 {}。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def repl_text(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


NEW_METHOD = '''    def _mode_rule(self, question: str):
        """规则优先的模式判断（薄壳）：唯一实现在模块级 `mode_rule`。

        ★ 下沉原因（本版冒烟 v1235 [1d] 抓出的真分叉）：规则层只接在
          本方法上时，`plan_resources` / `auto_plan(llm=...)` 两处分派
          不走规则 ⇒ 同一问题三处模式决策不一致。规则逻辑必须**一份
          实现、三处接线**（本项目「同一条逻辑两条通道各写一份」老坑）。
        """
        return mode_rule(question)

'''

MODULE_RULE = '''#: [B1 规则优先] 模块级唯一实现（v1.23.29 下沉）。★ 规则只判到
#:   serial/B/C（与 `MetaDGTF._AUTO_REACHABLE_MODES` 对应）——
#:   6 个 stage 模式不参与自动分派，显式传参才可达。
_MODE_RULE_OR = ("或", "还是", "或者", "抑或")
_MODE_RULE_AND = ("和", "与", "以及", "同时", "并")
_MODE_RULE_PIPE = ("流水", "接力", "时序", "尽快", "尽量快")


def mode_rule(question: str):
    """规则优先的模式判断。返回 (mode, reason) 或 (None, why_not)。

    ★ 为什么要有规则层：出厂把模式**全权**交给一次 LLM 调用，而
      实测该调用几乎总返回 `serial`（含 `_PARALLEL_CONF_MIN` 门槛
      的兜底）——花一次调用换一句『退回保守』。
      规则层能覆盖的情形就地定案，**不再花调用**；拿不准才回落 LLM。
    ★ 三处接线：`_decide_parallel_mode` / `plan_resources` /
      `auto_plan(llm=...)` —— 同一问题必须同案（冒烟 v1235 [1d]）。
    """
    q = question or ""
    _n = len(q)
    _or = any(t in q for t in _MODE_RULE_OR)
    _and = any(t in q for t in _MODE_RULE_AND)
    _pipe = any(t in q for t in _MODE_RULE_PIPE)
    _how = ("如何" in q) or ("怎样" in q) or ("怎么" in q)
    _clauses = (q.count("，") + q.count(",")) >= 2
    # 1) 含「或/还是」⇒ 开放震荡 ⇒ B（与 `_auto_pick_mode` 的
    #    `choice` 判据同源）。
    if _or and _n >= 8:
        return "B", "规则：含选择/开放词（或/还是），走轮次并行"
    # 2) 讲过程 + 显式要压缩时长 ⇒ C（层界可接力）。
    if _pipe and (_clauses or _how):
        return "C", "规则：显式要求压缩时长且讲过程，走流水线并行"
    # 3) 单一短问句 ⇒ serial（与 `_auto_pick_mode` 的
    #    `fact and short` 一致：层间依赖强，无并行收益）。
    if _n <= 16 and not _or and not _and and not _clauses:
        return "serial", "规则：单一短问句，无并列无选择，走严格串行"
    # 4) 多分句且含并列 ⇒ B（层次不分明、需震荡）。
    if _clauses and _and:
        return "B", "规则：多分句且含并列，层次不分明，走轮次并行"
    return None, "规则拿不准"


def plan_resources(question: str, orientation: str,'''


def main():
    s = _load()

    # ── 1. 类方法退薄壳（区间替换，含规则元组一并下沉）──
    start = s.index("    def _mode_rule(self, question: str):")
    end = s.index("    def _decide_parallel_mode(self, question: str) -> dict:")
    region = s[start:end]
    for marker in ("_MODE_RULE_OR", "规则拿不准", "走严格串行"):
        assert marker in region, "方法区间缺 %r" % marker
    s = s[:start] + NEW_METHOD + s[end:]

    # ── 2. 删类级规则元组（已在区间外，单独删）─────────
    old_t = '''    #: 规则优先判据的**并列连接词/选择词**（决定 A/B 分岔）。
    _MODE_RULE_OR = ("或", "还是", "或者", "抑或")
    _MODE_RULE_AND = ("和", "与", "以及", "同时", "并")
    _MODE_RULE_PIPE = ("流水", "接力", "时序", "尽快", "尽量快")

'''
    assert s.count(old_t) == 1, "类级元组命中 %d 次" % s.count(old_t)
    s = s.replace(old_t, "")

    # ── 3. 模块级唯一实现：插在 plan_resources 之前 ──────
    old_pr = 'def plan_resources(question: str, orientation: str,'
    s = repl_text(s, old_pr, MODULE_RULE, "B1 模块级 mode_rule")

    # ── 4. plan_resources 规则优先（省一次调用）─────────
    old_pr2 = '''    q = question or ""
    _o = _normalize_orientation(orientation, "decision")
'''
    new_pr2 = '''    q = question or ""
    _o = _normalize_orientation(orientation, "decision")

    # ★ [B1 规则优先] 命中即定案，**不花这次 LLM 调用**；拿不准才
    #   走下面的真调用。rounds 走 {}（各层由停止判据自定，不猜）。
    _rm, _rr = mode_rule(q)
    if _rm:
        return {"route": list(_ROUTE_PRESETS[_route_default]),
                "mode": _rm, "rounds": {},
                "max_calls": 0,
                "reason": _rr, "confidence": 0.9}
'''
    s = repl_text(s, old_pr2, new_pr2, "B1 plan_resources 规则优先")

    # ── 5. auto_plan 单调用路径规则优先 ─────────────────
    old_ap = '''        q = question or ""
        spiral = config.get("spiral", {}) or {}
        hard = int(spiral.get("hard_max", 12) or 12)
        soft = int(spiral.get("soft_max", 2) or 2)'''
    new_ap = '''        q = question or ""
        spiral = config.get("spiral", {}) or {}
        hard = int(spiral.get("hard_max", 12) or 12)
        soft = int(spiral.get("soft_max", 2) or 2)
        # ★ [B1 规则优先] 与 `_decide_parallel_mode` / `plan_resources`
        #   同一规则、同一接线 —— 命中即定案，不花这次调用。
        _rm, _rr = mode_rule(q)
        if _rm:
            return _assemble_plan(
                _rm, {}, cfg, confidence=0.9,
                reason=_rr + "（规则命中，未花调度调用）")'''
    s = repl_text(s, old_ap, new_ap, "B1 auto_plan 规则优先")

    _save(s)
    print("OK 第 7 阶段（B1 统一接线）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("return mode_rule(question)") == 1
    assert s2.count("def mode_rule(question: str):") == 1
    assert s2.count("self._MODE_RULE_OR") == 0
    print("复读校验通过")


if __name__ == "__main__":
    main()
