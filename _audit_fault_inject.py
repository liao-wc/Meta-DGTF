# -*- coding: utf-8 -*-
"""故障注入探针：真实跑一定会遇到的 5 种 LLM 故障，引擎会怎么表现。

不是"应该怎样"的清单，而是**实测矩阵**：
  · 崩（抛异常穿透到调用方）—— 最坏；
  · 静默成功（产物看起来正常，但其实是空壳）—— 次坏（比崩更难发现）；
  · 降级 + 留痕（有 errors 记录，读数如实为 None）—— 可接受。

5 种故障：
  1) 每次调用都抛 RuntimeError（网络挂）
  2) 返回空字符串（模型返回空）
  3) 返回非 JSON 文本（模型乱答）
  4) 返回 JSON null
  5) 返回类型不对（该是 list 给了 str）

输出：每种故障下 run() 是否抛异常、views 是否产出、errors 是否留痕。
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

spec = importlib.util.spec_from_file_location("f62", str(HERE / "元DGTF-V1.23.62.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
mod.LLM._real_call = mod.LLM.call

Q = "常识是怎么形成的，它靠不靠得住"


def mkcfg():
    c = mod.load_config(str(HERE / "__none__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="f62o_")))
    m = pathlib.Path(tempfile.mkdtemp(prefix="f62m_"))
    c["playbook"] = {"mode": "off", "dir": str(m)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(m)
    c.setdefault("runtime", {})["live_checkpoint"] = False
    c["all_on"] = False
    return c


def _raise(*a, **kw):
    raise RuntimeError("simulated network down")


FAULTS = [
    ("1 抛异常", _raise),
    ("2 空字符串", lambda *a, **kw: ""),
    ("3 非JSON", lambda *a, **kw: "我觉得这个问题的答案是……（一段散文）"),
    ("4 JSON null", lambda *a, **kw: "null"),
    ("5 类型不对", lambda *a, **kw: json.dumps(
        {"candidates": "本该是列表", "threads": 42}, ensure_ascii=False)),
]

print("%-12s %-8s %-8s %-8s %s" % ("故障", "抛异常", "views", "errors", "备注"))
print("-" * 74)
rows = []
for name, fn in FAULTS:
    mod.LLM.call = fn
    try:
        r = mod.MetaDGTF(mkcfg()).run(
            Q, route=["0"], rounds={"0": 1}, parallel_mode="serial")
        views = r.get("views") or {}
        raised = False
        v0 = views.get("0") or {}
        errs = v0.get("errors") if isinstance(v0, dict) else None
        n_err = len(errs or []) if isinstance(errs, (list, dict)) else 0
        note = ""
        if isinstance(v0, dict):
            note = ("候选=%d" % len(v0.get("candidates") or []))
        print("%-12s %-8s %-8s %-8s %s"
              % (name, "否", len(views), n_err, note))
        rows.append((name, False, len(views), n_err, note))
    except Exception as e:  # noqa: BLE001
        print("%-12s %-8s %-8s %-8s %s"
              % (name, "**是**", "-", "-", "%s: %s" % (type(e).__name__, str(e)[:40])))
        traceback.print_exc()
        rows.append((name, True, "-", "-", type(e).__name__))
    finally:
        mod.LLM.call = mod.LLM._real_call

print("-" * 74)
_nraise = sum(1 for r in rows if r[1])
print("抛异常的故障：%d / %d" % (_nraise, len(rows)))
