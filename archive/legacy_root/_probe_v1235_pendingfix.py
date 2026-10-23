# -*- coding: utf-8 -*-
"""v1.23.5 前置量化探针：清挂账（pending_fix #1 / #3）的改前/改后对表。

用法：
    python _probe_v1235_pendingfix.py 元DGTF-V1.23.4.py before
    python _probe_v1235_pendingfix.py 元DGTF-V1.23.5.py after

输出 `_probe_v1235_pendingfix_<tag>.txt`（脚本自己 write_bytes，不用 shell 重定向）。

量法纪律：
  · 每一项都走**生产入口**（MetaDGTF._decide_parallel_mode / 模块级 plan_resources /
    MetaDGTF._auto_plan），不手造中间结构 —— 手造会绕过归一化本身。
  · 三处归一化喂**同一份 mock payload**，输出才可比。
  · 形态计数一律**先抠掉模块 docstring**（changelog 里会提到这些串）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(src_path):
    spec = importlib.util.spec_from_file_location("dgtf_probe", str(src_path))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_probe"] = m
    spec.loader.exec_module(m)
    return m


class Stub:
    """只记调用、返回固定 payload 的 LLM 桩（走生产入口，不绕过归一化）。"""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, *a, **k):
        self.calls.append((a, k))
        return json.dumps(self.payload, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def strip_doc(src_text):
    s = src_text.replace("\r\n", "\n")
    i = s.index('"""')
    j = s.index('"""', i + 3)
    return s[j + 3:]


def counts(src_text):
    body = strip_doc(src_text)
    pats = {
        "模式白名单(_up = mode.upper())": "_up = mode.upper()",
        "圈数补漏(if rnd and len(rnd) < 4:)": "if rnd and len(rnd) < 4:",
        "圈数钳制(_layer_floor(k, hard, _floor))": "_layer_floor(k, hard, _floor)",
        "conf 解析(conf = float(data.get()": 'conf = float(data.get(',
        "低置信退serial(conf < _PARALLEL_CONF_MIN)": "conf < _PARALLEL_CONF_MIN",
    }
    return {k: body.count(v) for k, v in pats.items()}


def main():
    src = Path(sys.argv[1])
    tag = sys.argv[2] if len(sys.argv) > 2 else "x"
    mod = load(src)
    raw = src.read_bytes().decode("utf-8")
    out = []

    out.append("=" * 70)
    out.append("v1.23.5 挂账探针 [%s]  src=%s" % (tag, src.name))
    out.append("=" * 70)

    # ---------- A. 归一化形态计数（抠 docstring 后）----------
    out.append("")
    out.append("[A] 归一化规则形态计数（抠掉模块 docstring 后）")
    for k, v in counts(raw).items():
        out.append("    %-42s %d" % (k, v))

    # ---------- B. 三处归一化喂同一份 payload ----------
    cfg = mod.load_config("")
    hard = int((cfg.get("spiral") or {}).get("hard_max", 12) or 12)
    out.append("")
    out.append("[B] 同一份 mock payload 喂三处归一化（hard_max=%d）" % hard)

    cases = {
        "四层齐": {"0": 3, "1": 7, "both": 4, "all": 6},
        "只给两层": {"0": 5, "1": 5},
        "越界值": {"0": 1, "1": 99, "both": 2, "all": 2},
        "空圈数": {},
    }
    modes = ["G", "Z", "h", "serial"]

    for m_in in modes:
        for tag_c, r_in in cases.items():
            payload = {"route": "full", "mode": m_in, "rounds": dict(r_in),
                       "max_calls": 0, "reason": "probe",
                       "confidence": 0.8, "orientation": "decision"}
            row = {}

            # (1) _decide_parallel_mode：只定 mode，不产 rounds
            try:
                m = mod.MetaDGTF(cfg)
                m.llm = Stub(dict(payload))
                r1 = m._decide_parallel_mode("探针题：该怎么跑")
                row["单目标决策"] = (r1.get("mode"), None,
                                     r1.get("confidence"), r1.get("reason"))
            except Exception as e:
                row["单目标决策"] = ("EXC:%s" % type(e).__name__, None, None, None)

            # (2) plan_resources：两段式路径（走模块级，需要 patch LLM）
            try:
                s2 = Stub(dict(payload))
                _oL = mod.LLM
                mod.LLM = lambda c: s2
                try:
                    r2 = mod.plan_resources("探针题：该怎么跑", "decision", cfg)
                finally:
                    mod.LLM = _oL
                row["两段式"] = (r2.get("mode"),
                                {k: v for k, v in (r2.get("rounds") or {}).items()
                                 if k in (r2.get("route") or [])},
                                r2.get("confidence"), r2.get("reason"))
            except Exception as e:
                row["两段式"] = ("EXC:%s" % type(e).__name__, None, None, None)

            # (3) auto_plan 单调用分支（run() 走的就是这条）
            try:
                m3 = mod.MetaDGTF(cfg)
                m3.llm = Stub(dict(payload))
                r3 = m3._auto_plan("探针题：该怎么跑")
                row["单调用"] = (r3.get("mode"), dict(r3.get("rounds") or {}),
                                r3.get("confidence"), r3.get("reason"))
            except Exception as e:
                row["单调用"] = ("EXC:%s" % type(e).__name__, None, None, None)

            out.append("  -- mode=%-6s %s" % (m_in, tag_c))
            for k, v in row.items():
                out.append("       %-12s %s" % (k, v))

    # ---------- C. 低置信退 serial（conf=0.1）----------
    out.append("")
    out.append("[C] 低置信（conf=0.1，阈值 %s）三处处置" % getattr(
        mod, "_PARALLEL_CONF_MIN", "?"))
    lo = {"route": "full", "mode": "G", "rounds": {"0": 3, "1": 5,
                                                   "both": 4, "all": 6},
          "max_calls": 0, "reason": "probe", "confidence": 0.1,
          "orientation": "decision"}
    try:
        m = mod.MetaDGTF(cfg)
        m.llm = Stub(dict(lo))
        r1 = m._decide_parallel_mode("探针题")
        out.append("    单目标决策 %s" % (r1,))
    except Exception as e:
        out.append("    单目标决策 EXC:%s" % type(e).__name__)
    try:
        s2 = Stub(dict(lo))
        _oL = mod.LLM
        mod.LLM = lambda c: s2
        try:
            r2 = mod.plan_resources("探针题", "decision", cfg)
        finally:
            mod.LLM = _oL
        out.append("    两段式     %s" % ({k: r2.get(k) for k in
                                          ("route", "mode", "rounds",
                                           "confidence", "reason")},))
    except Exception as e:
        out.append("    两段式     EXC:%s" % type(e).__name__)
    try:
        m3 = mod.MetaDGTF(cfg)
        m3.llm = Stub(dict(lo))
        r3 = m3._auto_plan("探针题")
        out.append("    单调用     %s" % ({k: r3.get(k) for k in
                                          ("mode", "rounds", "confidence",
                                           "reason", "orientation")},))
    except Exception as e:
        out.append("    单调用     EXC:%s" % type(e).__name__)

    # ---------- D. pending_fix #3：as_evidence 布尔兼容 ----------
    out.append("")
    out.append("[D] pending_fix #3 · _anchor_tier 布尔兼容（当前是否有留痕）")
    for name, val in [("True", True), ("False", False), ('"off"', "off"),
                      ('"evidence"', "evidence"), ('"crosscheck"', "crosscheck"),
                      ("垃圾值", "nonsense"), ("None", None)]:
        try:
            tier = mod._anchor_tier({"as_evidence": val})
        except Exception as e:
            tier = "EXC:%s" % type(e).__name__
        out.append("    as_evidence=%-12s -> %r" % (name, tier))

    # ---------- E. 布尔兼容是否被走（仓库内调用点）----------
    out.append("")
    out.append("[E] DEFAULT_CONFIG 里 as_evidence 的取值（应为字符串档）")
    dc = getattr(mod, "DEFAULT_CONFIG", {}) or {}
    for path in ("external_anchor", "web_search"):
        seg = dc.get(path) or {}
        if "as_evidence" in seg:
            out.append("    %-18s %r" % (path, seg["as_evidence"]))

    txt = "\n".join(out) + "\n"
    dst = HERE / ("_probe_v1235_pendingfix_%s.txt" % tag)
    dst.write_bytes(txt.encode("utf-8"))
    print(txt)
    print("落盘:", dst)


if __name__ == "__main__":
    main()
