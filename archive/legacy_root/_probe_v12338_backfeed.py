# -*- coding: utf-8 -*-
"""[v1.23.38 探针] 量「池复用式回喂」改前/改后行为。

用法：python _probe_v12338_backfeed.py 元DGTF-V1.23.38.py
输出：_probe_v12338_backfeed_<ver>.txt

量法说明（v1.23.36 通则 #1：观测打在被测逻辑真正执行的那一层）：
  不整体替换 _web_augment —— 直接**驱动它本身**，只看它的**返回值**。
  桩只打在**更下层**：
    · LLM._web_augment 的 _searcher 回调（_llm_ctx_set(web_searcher=...)）
    · 池的 web_results（直接构造）
  ⇒ 观测的是「_web_augment 到底注入了什么」，不是「谁调了它」。
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.38.py"
VER = re.search(r"V(1\.\d+\.\d+)", TARGET.name).group(1)
OUT = HERE / ("_probe_v12338_backfeed_%s.txt" % VER.replace(".", "_"))

_lines = []


def p(*a):
    t = " ".join(str(x) for x in a)
    _lines.append(t)
    print(t)


# ── 加载主文件模块（dataclass 注解需要放进 sys.modules）────────────────
spec = importlib.util.spec_from_file_location("tgt_mod", TARGET)
mod = importlib.util.module_from_spec(spec)
sys.modules["tgt_mod"] = mod
spec.loader.exec_module(mod)

p("=== 探针 v12338 · 目标 %s ===" % TARGET.name)

# ── 构造：一个 LLM 实例 + 一个池（带 record 条目）─────────────────────
# LLM 的 _web_augment 是实例方法；它读线程上下文里的 web_searcher / question /
# round。我们用 _llm_ctx_set 注入桩。
try:
    inst = mod.LLM.__new__(mod.LLM)          # 不走 __init__（避免依赖 API）
except Exception as e:
    p("[FATAL] LLM.__new__ 失败：%r" % e)
    OUT.write_bytes(("\n".join(_lines) + "\n").encode("utf-8"))
    sys.exit(1)

# 填 _web_augment 会用到的属性
inst.thinking_stages = getattr(inst, "thinking_stages", {}) or {}
inst.thinking_default = getattr(inst, "thinking_default", None)
inst.default_model = getattr(inst, "default_model", "deepseek-flash")

p("")
p("--- 静态：_web_augment 是否引用了池的 web_results ---")
try:
    import inspect
    body = inspect.getsource(mod.LLM._web_augment)
    p("_web_augment 引用 web_results :", "web_results" in body)
    p("_web_augment 引用 used_as     :", "used_as" in body)
    p("_web_augment 引用 record      :", '"record"' in body or "'record'" in body)
except Exception as e:
    p("[WARN] getsource 失败：%r" % e)

# ── 场景 A：池里有 record 条目（按需声明的结果已进池）───────────────
#   期望（改后）：_web_augment 直接复用池里这条 → 返回注入文本，且**不调** searcher
#   期望（改前）：_web_augment 看不到池 → 会去调 searcher（或返回 None）
p("")
p("--- 场景 A：池里有 used_as=record 的条目 ---")


def _mk_pool(records):
    """构造一个带 web_results 的最小池对象。"""
    try:
        pool = mod.Pool()
    except Exception:
        pool = type("P", (), {})()
        pool.web_results = []
    pool.web_results = list(records)
    return pool


REC = [{"id": "W7", "stage": "research_evidence", "query": "q",
        "claim": "回喂来的事实：X 是 Y", "url": "http://e/x",
        "source": "a", "tier": 2, "used_as": "record", "round": 1,
        "round_kind": "in", "pre_seq": 0}]

POOL_A = _mk_pool(REC)

_calls = {"n": 0}


def _searcher_a(stage, queries, rn, used_as):
    _calls["n"] += 1
    return [{"claim": "新检索结果", "url": "http://new", "source": "b", "tier": 2}]


# ★ 关键：池必须经**真实通道**递进去（= 线程上下文 backfeed_pool），
#   不是挂在实例上 —— 这正是 v1.23.36 通则 #1「观测要打在被测逻辑真正
#   执行的那一层」的翻版（第一版探针就把池挂错了地方 ⇒ 观测恒空）。
mod._llm_ctx_set(web_searcher=_searcher_a, question="测试问题",
                 round=2, entry="1", backfeed_pool=POOL_A)

_aug_sig = None
try:
    _aug_sig = str(inspect.signature(mod.LLM._web_augment))
except Exception:
    pass
p("_web_augment 签名 :", _aug_sig)

try:
    r = inst._web_augment("research_evidence", "原始 user 文本")
    p("场景A 返回类型 :", type(r).__name__)
    p("场景A 返回非空 :", bool(r))
    p("场景A searcher 调用次数 :", _calls["n"])
    if r:
        p("场景A 含回喂声明原文 :", "回喂来的事实" in str(r))
        p("场景A 含新检索结果   :", "新检索结果" in str(r))
except Exception as e:
    p("[ERR] 场景A 驱动失败：%r" % e)

# ── 场景 B：池里**没有** record 条目（负对照）────────────────────────
p("")
p("--- 场景 B：池里没有 record 条目（负对照）---")
POOL_B = _mk_pool([])
_calls["n"] = 0


def _searcher_b(stage, queries, rn, used_as):
    _calls["n"] += 1
    return [{"claim": "B 检索结果", "url": "http://b", "source": "b", "tier": 2}]


mod._llm_ctx_set(web_searcher=_searcher_b, question="测试问题",
                 round=2, entry="1", backfeed_pool=POOL_B)
try:
    r2 = inst._web_augment("research_evidence", "原始 user 文本")
    p("场景B 返回非空 :", bool(r2))
    p("场景B searcher 调用次数 :", _calls["n"])
except Exception as e:
    p("[ERR] 场景B 驱动失败：%r" % e)

# ── 场景 C：没有注入器（独立调用 LLM）⇒ 必须 None ────────────────────
p("")
p("--- 场景 C：无 web_searcher 注入器 ---")
mod._llm_ctx_set(web_searcher=None, question="测试问题", round=2, entry="1",
                 backfeed_pool=POOL_A)
try:
    r3 = inst._web_augment("research_evidence", "原始 user 文本")
    p("场景C 返回 is None :", r3 is None)
except Exception as e:
    p("[ERR] 场景C 驱动失败：%r" % e)

OUT.write_bytes(("\n".join(_lines) + "\n").encode("utf-8"))
print("\n[written] %s" % OUT.name)
