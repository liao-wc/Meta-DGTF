# -*- coding: utf-8 -*-
"""v1.23.64 开发期判据：内核接线 + 工程加固（EML 原子性 / 锁 / 重试）。"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.64.py"
os.environ.setdefault("DGTF_API_KEY", "sk-dev-check")

_spec = importlib.util.spec_from_file_location("dgtf_dev", SRC)
mod = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_dev"] = mod
_spec.loader.exec_module(mod)

P, F = 0, []


def ck(name, cond, note=""):
    global P
    if cond:
        P += 1
        print("  OK  %s" % name)
    else:
        F.append(name)
        print("  RED %s  %s" % (name, note))


# ── A. 内核已进主文件，且行为与独立内核一致 ─────────────────
ck("A1 版本号 1.23.64", mod.__version__ == "1.23.64", mod.__version__)
ck("A2 e-process 存在且可判定",
   mod.anytime_decided([1] * 40, 0.05, 0.5, mode="evalue")[0] is True, "")
ck("A3 e-process 对半半序列不误判",
   mod.anytime_decided([0, 1] * 30, 0.05, 0.5, mode="evalue")[0] is False, "")
ck("A4 保形分位数有限样本修正（n=10, α=0.2 ⇒ 第 9 小）",
   mod.conformal_quantile([i / 10 for i in range(10)], 0.2) == 0.8,
   mod.conformal_quantile([i / 10 for i in range(10)], 0.2))
_rng = random.Random(1)
_seq = [_rng.gauss(0, 1) for _ in range(40)] + [_rng.gauss(5, 1) for _ in range(40)]
ck("A5b BOCPD 检出 1 次", len(mod.bocpd_run(_seq)["detected"]) >= 1,
   repr(mod.bocpd_run(_seq)["detected"])[:120])
ck("A6 论证类可用", mod.ArgumentationFramework(["A", "B"], [("A", "B")])
   .grounded_extension() == ["A"], "")

# ── B. EML 原子写 / 只增不删 ────────────────────────────────
td = Path(tempfile.mkdtemp())
p = td / "playbook.jsonl"
rows = [{"id": "L1", "status": "active"}, {"id": "L2", "status": "shadow"}]
p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
             encoding="utf-8")
ck("B1 原子重写（同形）成功", mod.eml_rewrite_jsonl(p, rows) is True, "")
ck("B2 写入是完整行（无半截）",
   len([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]) == 2,
   p.read_text(encoding="utf-8"))
ck("B3 只增：追加一行允许",
   mod.eml_rewrite_jsonl(p, rows + [{"id": "L3", "status": "shadow"}],
                         allow_grow=True) is True, "")
ck("B4 只增：缩行被拒",
   mod.eml_rewrite_jsonl(p, rows[:1], allow_grow=True) is False, "")
ck("B5 只增：换 id 被拒（旧 id 不能丢）",
   mod.eml_rewrite_jsonl(p, rows + [{"id": "X9"}], allow_grow=True) is False, "")
ck("B6 默认模式仍要求行数/id 集合不变",
   mod.eml_rewrite_jsonl(p, rows + [{"id": "L4"}]) is False, "")

# ── C. eml_read_jsonl：坏行计数 + 告警（不静默）─────────────
p2 = td / "bad.jsonl"
p2.write_text('{"id":"A"}\nnot-json\n{"id":"B"}\n', encoding="utf-8")
st = {}
got = mod.eml_read_jsonl(p2, stats=st)
ck("C1 坏行跳过但好行保留", [x["id"] for x in got] == ["A", "B"], repr(got))
ck("C2 坏行有计数（stats.bad=1）", st.get("bad") == 1, repr(st))
ck("C3 不传 stats 时返回形状不变", isinstance(mod.eml_read_jsonl(p2), list), "")

# ── D. 锁：陈旧回收 / 活进程不抢 / 令牌释放 ─────────────────
ld = Path(tempfile.mkdtemp())
lp = ld / ".eml.lock"
with mod.eml_lock(dirpath=ld, timeout=2.0) as got:
    ck("D1 锁可获取", got is True, "")
    ck("D2 持锁期间锁文件存在", lp.is_file(), "")
ck("D3 释放后锁文件消失", not lp.is_file(), "")
lp.write_text("999999:0", encoding="utf-8")
os.utime(lp, (time.time() - 9999, time.time() - 9999))
with mod.eml_lock(dirpath=ld, timeout=2.0, stale=1.0) as got:
    ck("D4 死进程的陈旧锁可回收", got is True, "")
lp.write_text("%d:0" % os.getpid(), encoding="utf-8")
os.utime(lp, (time.time() - 9999, time.time() - 9999))
with mod.eml_lock(dirpath=ld, timeout=0.4, stale=1.0) as got:
    ck("D5 活进程持有的锁不被抢（负对照）", got is False, "")
lp.unlink(missing_ok=True)

# ── E. 重试策略：错误分类 + 抖动 ────────────────────────────
NS = types.SimpleNamespace
ck("E1 400 不重试", mod.LLM._retryable(NS(status_code=400)) is False, "")
ck("E2 401 不重试", mod.LLM._retryable(NS(status_code=401)) is False, "")
ck("E3 429 重试", mod.LLM._retryable(NS(status_code=429)) is True, "")
ck("E4 500 重试", mod.LLM._retryable(NS(status_code=500)) is True, "")
ck("E5 未知异常保守重试", mod.LLM._retryable(RuntimeError("x")) is True, "")
_dummy = NS(backoff=1.8)
_ds = [mod.LLM._retry_delay(_dummy, 1) for _ in range(200)]
ck("E6 抖动在 [0.5,1.0]×base 内",
   all(0.9 - 1e-9 <= d <= 1.8 + 1e-9 for d in _ds) and len(set(_ds)) > 50,
   "min=%.3f max=%.3f" % (min(_ds), max(_ds)))

# ── F. 召回：被论证裁定为败方时默认仍召回、开关打开才排除 ────
pb = [
    {"id": "A", "kind": "schedule", "status": "active",
     "action": {"key": "k"}, "arg_status": "defeated"},
    {"id": "B", "kind": "schedule", "status": "active",
     "action": {"key": "k"}},
]
r1 = mod.eml_recall(pb, "schedule", time.time(), top_k=5)
r2 = mod.eml_recall(pb, "schedule", time.time(), top_k=5, exclude_defeated=True)
ck("F1 默认召回含败方（零行为差）", {x["id"] for x in r1} == {"A", "B"}, repr(r1))
ck("F2 显式排除后不含败方", {x["id"] for x in r2} == {"B"}, repr(r2))

# ── G. 配置：新键存在且默认保守 ─────────────────────────────
ck("G1 stop.anytime_mode 默认 hoeffding",
   mod.DEFAULT_CONFIG["stop"]["anytime_mode"] == "hoeffding", "")
ck("G2 playbook.argumentation 默认关",
   mod.DEFAULT_CONFIG["playbook"]["argumentation"]["enabled"] is False, "")
ck("G3 _AUDIT_CONFIG_EXEMPT 存在", hasattr(mod, "_AUDIT_CONFIG_EXEMPT"), "")

# ── H. 真实 playbook 上的只读冲突裁决（不写盘）──────────────
pbr = mod.eml_read_jsonl(HERE / "dgtf_memory" / "playbook.jsonl")
res = mod.resolve_playbook_conflicts([dict(x) for x in pbr], apply=False)
ck("H1 真实库只读裁决不抛错", isinstance(res, dict), repr(res)[:100])
ck("H2 裁决结果自洽（winner/defeated 不相交）",
   not (set(res["winners"]) & set(res["defeated"])), "")

print("\nDEV PASS %d / FAIL %d" % (P, len(F)))
sys.exit(1 if F else 0)
