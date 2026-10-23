# -*- coding: utf-8 -*-
"""健壮性探针：退化输入能不能把引擎打挂（mock LLM，零成本）。

不是"应该支持"清单，而是"会不会崩 / 会不会静默产出垃圾"：
  · 空题、纯空白、单字、纯标点
  · 超长（10k 字）
  · 含换行 / 引号 / 反斜杠 / emoji
  · 只有问号（无实义）
判据：不抛异常；产物里有 question 字段；不出现 0 长度主体。
"""
import importlib.util
import pathlib
import sys
import tempfile
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

CASES = [
    ("空字符串", ""),
    ("纯空白", "   \n\t  "),
    ("单字", "熵"),
    ("纯标点", "？？？！！！……"),
    ("只有问号", "?????"),
    ("含引号反斜杠", '什么算"常识"？\\n 反斜杠 \\ 也算？'),
    ("含换行", "第一行\n第二行\n第三行"),
    ("emoji", "🌱 常识 🌱 是怎么来的？"),
    ("超长 10k", "常识的形成机制与可靠性" * 500),
]

spec = importlib.util.spec_from_file_location("e60", str(HERE / "元DGTF-V1.23.60.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
mod.LLM._real_call = mod.LLM.call
mod.LLM.call = st.fake_call


def mkcfg():
    c = mod.load_config(str(HERE / "__none__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="rob_")))
    mem = pathlib.Path(tempfile.mkdtemp(prefix="robm_"))
    c["playbook"] = {"mode": "off", "dir": str(mem)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    c.setdefault("runtime", {})["live_checkpoint"] = False
    c["all_on"] = False
    return c


bad = []
for name, q in CASES:
    try:
        r = mod.MetaDGTF(mkcfg()).run(
            q, route=["0"], rounds={"0": 1}, parallel_mode="serial")
        views = r.get("views") or {}
        nq = len(str(r.get("question") or ""))
        _v = views.get("0") or {}
        n_cand = len(_v.get("candidates") or []) if isinstance(_v, dict) else 0
        ok = nq == len(q) and bool(views)
        print("  %-14s len=%-6d views=%d 候选=%-2d question回填=%s"
              % (name, len(q), len(views), n_cand, "OK" if nq == len(q) else "✗%d" % nq))
        if not ok:
            bad.append("%s：views=%r / question 长度 %d≠%d" % (name, list(views), nq, len(q)))
    except Exception as e:  # noqa: BLE001
        print("  %-14s ✗ 抛异常 %s: %s" % (name, type(e).__name__, e))
        traceback.print_exc()
        bad.append("%s：抛 %s" % (name, type(e).__name__))

print("\n判红 %d / %d" % (len(bad), len(CASES)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
