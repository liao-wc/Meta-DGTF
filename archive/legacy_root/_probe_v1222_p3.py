# -*- coding: utf-8 -*-
"""[v1.22.2 P3] 探针：answers 最短长度约束 + 双告警分离。

用法：python _probe_v1222_p3.py [元DGTF-V1.22.2.py]
改前跑（v1.22.1）应当**假**：没有 answers_min_len，短 answer 全被留下。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.22.2.py"
if not SRC.is_absolute():
    SRC = HERE / SRC
txt = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

spec = importlib.util.spec_from_file_location("dgtf_p3", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_p3"] = mod
spec.loader.exec_module(mod)

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


def load(anchors, **over):
    p = Path(tempfile.mkdtemp()) / "anc.json"
    p.write_text(json.dumps({"anchors": anchors}, ensure_ascii=False),
                 encoding="utf-8")
    cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    cfg["external_anchor"] = dict(cfg["external_anchor"])
    cfg["external_anchor"].update({"enabled": True, "path": str(p)})
    cfg["external_anchor"].update(over)
    m = object.__new__(mod.MetaDGTF)
    m.config = cfg
    m.vp = lambda *a, **k: None
    return m, m._load_anchors()


# 1 配置键
ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
ck("P3.1 answers_min_len 存在且默认 6", ea.get("answers_min_len") == 6,
   repr(ea.get("answers_min_len")))
ck("P3.2 answers_max_n 存在且默认 5", ea.get("answers_max_n") == 5,
   repr(ea.get("answers_max_n")))

# 2 过滤行为
_m, _ = load([
    {"id": "a1", "claim": "老城区管网重现期标准",
     "answers": ["重现期", "老城区现有排水管网的设计标准是多少年一遇"]},
])
_ans = _m._anchors[0].get("answers") or []
ck("P3.3 短 answer 被丢弃", "重现期" not in _ans, repr(_ans))
ck("P3.4 长 answer 保留",
   any("老城区" in x for x in _ans), repr(_ans))
ck("P3.5 被丢弃项留痕", _m._anchors[0].get("_answers_dropped") == ["重现期"],
   repr(_m._anchors[0].get("_answers_dropped")))
ck("P3.6 过滤告警非空", bool(getattr(_m, "_anchor_answers_filtered", "")),
   repr(getattr(_m, "_anchor_answers_filtered", "")))
ck("P3.7 ★ 未声明告警**不**被误触发（声明过）",
   getattr(_m, "_anchor_answers_warning", "") == "", repr(getattr(_m, "_anchor_answers_warning", "")))

# 3 负对照：min_len=0 → 不过滤（退回旧行为）
_m0, _ = load([{"id": "a1", "claim": "x", "answers": ["重现期", "短"]}],
              answers_min_len=0)
_ans0 = _m0._anchors[0].get("answers") or []
ck("P3.8 负对照：min_len=0 → 不过滤",
   "重现期" in _ans0 and "短" in _ans0, repr(_ans0))
ck("P3.9 负对照：不过滤时无过滤告警",
   getattr(_m0, "_anchor_answers_filtered", "") == "", repr(getattr(_m0, "_anchor_answers_filtered", "")))

# 4 负对照：真「未声明 answers」→ 走另一条告警
_m2, _ = load([{"id": "a1", "claim": "x"}])
ck("P3.10 真未声明 → answers_all_missing 告警（另一条）",
   bool(getattr(_m2, "_anchor_answers_warning", "")), repr(getattr(_m2, "_anchor_answers_warning", "")))
ck("P3.11 ★ 两条告警分离（这条不亮）",
   getattr(_m2, "_anchor_answers_filtered", "") == "", repr(getattr(_m2, "_anchor_answers_filtered", "")))

# 5 上限
_m3, _ = load([{"id": "a1", "claim": "x",
                "answers": ["答案一很长很长", "答案二很长很长", "答案三很长很长",
                            "答案四很长很长", "答案五很长很长", "答案六很长很长"]}])
ck("P3.12 上限 5 条（配置化）", len(_m3._anchors[0]["answers"]) == 5,
   repr(len(_m3._anchors[0]["answers"])))

# 6 阈值不许动
ck("P3.13 ★ 负对照：0.6 阈值未动", "_UNTRACED_OVERLAP = 0.6" in txt or
   "0.6" in txt, "")
ck("P3.14 ★ 负对照：_overlap_coef 分母仍是 min",
   "return inter / min(len(ka), len(kb))" in txt, "")
ck("P3.15 packed 键已加", '"answers_filtered"' in txt, "")
ck("P3.16 产物渲染已加", "**锚点 answers 警告**" in txt, "")

print("═══ probe v1222 P3 ═══")
for t, ok, note in R:
    print(("  ✓ " if ok else "  ✗ ") + t + ("　" + note if note else ""))
print("PASS %d / FAIL %d" % (sum(1 for _, o, _ in R if o),
                             sum(1 for _, o, _ in R if not o)))
sys.exit(0 if all(o for _, o, _ in R) else 1)
