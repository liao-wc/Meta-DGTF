# -*- coding: utf-8 -*-
"""v1.23.61 开发期验证：空题守卫（拒绝 + 零调用 + 非空题不受影响）。

判据：
  A `run("")` ⇒ `refused.reason == "empty_question"`，`views` 为空
  B **零 LLM 调用**（这是"不花钱"的硬证据：打桩计数器必须为 0）
  C 纯空白（"   \\n\\t "）同样拒绝
  D 负对照：`run("熵")` 不被拒绝、正常产出（守卫没变成"见谁都拒"）
  E 旧版对照：v1.23.60 的 `run("")` **会跑**（缺陷重现）
"""
import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

bad, ok = [], []
CALLS = {"n": 0}


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def counting_call(*a, **kw):
    CALLS["n"] += 1
    return st.fake_call(*a, **kw)


def load(py):
    spec = importlib.util.spec_from_file_location("q61_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.LLM._real_call = m.LLM.call
    m.LLM.call = counting_call
    return m


def mkcfg(mod):
    c = mod.load_config(str(HERE / "__none__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="q61o_")))
    mem = pathlib.Path(tempfile.mkdtemp(prefix="q61m_"))
    c["playbook"] = {"mode": "off", "dir": str(mem)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    c.setdefault("runtime", {})["live_checkpoint"] = False
    c["all_on"] = False
    return c


new = load(HERE / "元DGTF-V1.23.61.py")

print("=" * 62)
print("【A】空题被拒绝")
CALLS["n"] = 0
r = new.MetaDGTF(mkcfg(new)).run(
    "", route=["0"], rounds={"0": 1}, parallel_mode="serial")
ck((r.get("refused") or {}).get("reason") == "empty_question",
   "refused=%r" % (r.get("refused"),))
ck(not (r.get("views") or {}), "views 为空：%r" % (list(r.get("views") or {}),))

print("\n【B】零 LLM 调用（拒绝是免费的）")
ck(CALLS["n"] == 0, "打桩计数=%d（必须 0）" % CALLS["n"])
ck(r.get("llm_calls") == 0, "产物 llm_calls=%r" % (r.get("llm_calls"),))

print("\n【C】纯空白同样拒绝")
CALLS["n"] = 0
r2 = new.MetaDGTF(mkcfg(new)).run(
    "   \n\t  ", route=["0"], rounds={"0": 1}, parallel_mode="serial")
ck((r2.get("refused") or {}).get("reason") == "empty_question",
   "refused=%r" % (r2.get("refused"),))
ck(CALLS["n"] == 0, "打桩计数=%d" % CALLS["n"])

print("\n【D】负对照：单字题不被拒绝")
CALLS["n"] = 0
r3 = new.MetaDGTF(mkcfg(new)).run(
    "熵", route=["0"], rounds={"0": 1}, parallel_mode="serial")
ck(not r3.get("refused"), "没被拒绝（refused=%r）" % (r3.get("refused"),))
ck(bool(r3.get("views")), "正常产出视图：%r" % (list(r3.get("views") or {}),))
ck(CALLS["n"] > 0, "确实跑了（打桩计数=%d）" % CALLS["n"])

print("\n【E】旧版对照：v1.23.60 空题会跑")
old = load(HERE / "元DGTF-V1.23.60.py")
CALLS["n"] = 0
ro = old.MetaDGTF(mkcfg(old)).run(
    "", route=["0"], rounds={"0": 1}, parallel_mode="serial")
ck(not ro.get("refused"), "旧版没有 refused 字段（%r）" % (ro.get("refused"),))
ck(bool(ro.get("views")) or CALLS["n"] > 0,
   "旧版照样跑了（视图=%r / 调用=%d）" % (list(ro.get("views") or {}), CALLS["n"]))

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
