# -*- coding: utf-8 -*-
"""v1.23.5 真模型单点探针（成本：1 次 LLM 调用）。

目的不是「跑一遍看效果」，而是回答：
    **真实模型产出的 payload，喂给改前 / 改后两版，归一化结果是否逐字相同？**

做法（反事实对照，不是跑两遍比数）：
  1. 用**真** LLM 打一次 `_auto_plan`（单调用分支，run() 走的就是它），
     把模型返回的**原始 payload** 录下来；
  2. 把这同一份 payload 分别喂 v1.23.4 与 v1.23.5 的三处归一化
     （单目标决策 / 两段式 / 单调用），逐字比对；
  3. 顺带真打一次 `plan_resources` 与 `_decide_parallel_mode` 也各录一份。

★ 为什么不是「两版各真跑一次再比数」：模型采样有抖动，组间差会被组内
  噪声盖掉（本项目 v1.22.2 §6 的结论）。固定**同一份真实输入**才是反事实。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.23.4.py"
NEW = HERE / "元DGTF-V1.23.5.py"
OUT = HERE / "_probe_v1235_real.txt"

QUESTION = "AI 在数字 IC 设计里，哪些环节已经能真正落地，哪些还停在实验室？"


def load(name, p):
    spec = importlib.util.spec_from_file_location(name, str(p))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class Record:
    """包住 parse_json，把模型返回的原始 payload 录下来。"""

    def __init__(self, inner):
        self.inner = inner
        self.payloads = []

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def parse_json(self, raw):
        d = self.inner.parse_json(raw)
        self.payloads.append(dict(d or {}))
        return d


class Stub:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, *a, **k):
        self.calls.append(k.get("stage"))
        return json.dumps(self.payload, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def three_ways(mod, payload, cfg):
    """同一份 payload 喂三处归一化，返回可比的三元组。"""
    m1 = mod.MetaDGTF(cfg)
    m1.llm = Stub(dict(payload))
    r1 = m1._decide_parallel_mode(QUESTION)
    s2 = Stub(dict(payload))
    _oL = mod.LLM
    mod.LLM = lambda c: s2
    try:
        r2 = mod.plan_resources(QUESTION, "decision", cfg)
    finally:
        mod.LLM = _oL
    m3 = mod.MetaDGTF(cfg)
    m3.llm = Stub(dict(payload))
    r3 = m3._auto_plan(QUESTION)
    return ({"mode": r1.get("mode"), "confidence": r1.get("confidence"),
             "reason": r1.get("reason")},
            {"mode": r2.get("mode"),
             "rounds": {k: v for k, v in (r2.get("rounds") or {}).items()
                        if k in (r2.get("route") or [])},
             "confidence": r2.get("confidence"), "reason": r2.get("reason")},
            {"mode": r3.get("mode"), "rounds": dict(r3.get("rounds") or {}),
             "confidence": r3.get("confidence"), "reason": r3.get("reason"),
             "orientation": r3.get("orientation")})


def main():
    lines = []
    new = load("dgtf_new", NEW)
    cfg = new.load_config("")

    lines.append("=" * 70)
    lines.append("v1.23.5 真模型单点探针（同一份真实 payload 喂两版）")
    lines.append("题面：" + QUESTION)
    lines.append("=" * 70)

    # ---- 1) 真打一次单调用分支，录 payload ----
    meta = new.MetaDGTF(cfg)
    rec = Record(meta.llm)
    meta.llm = rec
    try:
        real = meta._auto_plan(QUESTION)
    except Exception as e:
        lines.append("★ 真调用失败：%s: %s" % (type(e).__name__, e))
        OUT.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        print("\n".join(lines))
        return 1
    if not rec.payloads:
        lines.append("★ 没录到 payload（模型没按 JSON 返回？）")
        OUT.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        print("\n".join(lines))
        return 1
    payload = rec.payloads[0]
    lines.append("")
    lines.append("[1] 真模型返回的原始 payload（%d 键）" % len(payload))
    lines.append("    " + json.dumps(payload, ensure_ascii=False)[:400])
    lines.append("")
    lines.append("[2] v1.23.5 真跑出来的结果")
    lines.append("    mode=%r rounds=%r confidence=%r orientation=%r"
                 % (real.get("mode"), real.get("rounds"),
                    real.get("confidence"), real.get("orientation")))

    # ---- 2) 同一份 payload 喂两版 ----
    old = load("dgtf_old", OLD)
    cfg_old = old.load_config("")
    a = three_ways(old, payload, cfg_old)
    b = three_ways(new, payload, cfg)
    lines.append("")
    lines.append("[3] 同一份真实 payload 喂两版的三处归一化")
    tags = ["单目标决策", "两段式", "单调用"]
    same = True
    for t, x, y in zip(tags, a, b):
        ok = x == y
        same = same and ok
        lines.append("    %s  %s" % (t, "逐字相同" if ok else "★ 不同"))
        if not ok:
            lines.append("        改前 %s" % (x,))
            lines.append("        改后 %s" % (y,))
        else:
            lines.append("        %s" % (x,))

    # ---- 3) 低置信反事实：把 payload 的 confidence 压到阈值下 ----
    lo = dict(payload)
    lo["confidence"] = 0.1
    a2 = three_ways(old, lo, cfg_old)
    b2 = three_ways(new, lo, cfg)
    lines.append("")
    lines.append("[4] 反事实：把真实 payload 的 confidence 压到 0.1（阈值 %s）"
                 % getattr(new, "_PARALLEL_CONF_MIN", "?"))
    for t, x, y in zip(tags, a2, b2):
        ok = x == y
        same = same and ok
        lines.append("    %s  %s" % (t, "逐字相同" if ok else "★ 不同"))
        if not ok:
            lines.append("        改前 %s" % (x,))
            lines.append("        改后 %s" % (y,))
        else:
            lines.append("        %s" % (x,))

    lines.append("")
    lines.append("=" * 70)
    lines.append("结论：真实模型 payload 在两版上%s"
                 % ("逐字相同 —— 行为零变化成立" if same
                    else "★ 出现差异 —— 必须查"))
    lines.append("=" * 70)
    txt = "\n".join(lines) + "\n"
    OUT.write_bytes(txt.encode("utf-8"))
    print(txt)
    print("落盘:", OUT)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
