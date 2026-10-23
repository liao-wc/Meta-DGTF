# -*- coding: utf-8 -*-
"""v1.23.56 开发期构造性验证：快照记账**跨窗口累计**。

判据：
  A 不续跑：`window_calls == llm_calls`（与旧版逐字相同，基线为 0）
  B 续跑：第二个窗口的快照里 `llm_calls` **≥ 第一个窗口的**（累计），
    且 `window_calls` **严格小于** `llm_calls`（证明它记的是"本窗口"而不是"累计"）
  C 旧版对照：同一条链路跑 v1.23.55 ⇒ 第二个窗口 `llm_calls` 归零到本窗口值
    （即"累计"不成立）—— 证明本版确实改了行为

★ LLM 打桩（否则真花钱）。
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

Q = "冒烟题面：这件事的边界在哪里（v12356 记账累计判据）"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("e56_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.LLM._real_call = m.LLM.call
    m.LLM.call = st.fake_call
    assert getattr(m.LLM.call, "__name__", "") == "fake_call", "LLM 桩没装上"
    return m


def mkcfg(mod, mem):
    c = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="v56out_")))
    c["playbook"] = {"mode": "off", "dir": str(mem)}   # 记账判据不关心 EML
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    c.setdefault("runtime", {})
    c["runtime"]["live_checkpoint"] = True
    c["runtime"]["ckpt_interval"] = 0.05
    c["all_on"] = False
    return c


def run_chain(mod, tag):
    """跑两个窗口（都极小预算 ⇒ 都 paused），返回两个快照的读数。"""
    ckdir = pathlib.Path(tempfile.mkdtemp(prefix="v56ck_%s_" % tag))
    mem = pathlib.Path(tempfile.mkdtemp(prefix="v56mem_%s_" % tag))
    orig = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: ckdir
    rid = "CK56%s" % tag
    out = []
    try:
        # 窗口 1
        mod.MetaDGTF(mkcfg(mod, mem)).run(
            Q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=rid, max_minutes=1e-6)
        p = ckdir / ("%s.json" % rid)
        d1 = json.loads(p.read_text(encoding="utf-8"))
        out.append(d1)
        # 窗口 2：从快照续跑（截断层会被摘掉重跑，仍会到点）
        mod.MetaDGTF(mkcfg(mod, mem)).run(
            Q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=rid, resume_ckpt=str(p), max_minutes=1e-6)
        d2 = json.loads(p.read_text(encoding="utf-8"))
        out.append(d2)
    finally:
        mod.run_ckpt_dir = orig
    return out


new = load(HERE / "元DGTF-V1.23.56.py")
old = load(HERE / "元DGTF-V1.23.55.py")

print("=" * 62)
print("【A】不续跑：window_calls == llm_calls（基线 0，与旧版一致）")
memA = pathlib.Path(tempfile.mkdtemp(prefix="v56A_"))
ckA = pathlib.Path(tempfile.mkdtemp(prefix="v56Ack_"))
_orig = new.run_ckpt_dir
new.run_ckpt_dir = lambda base=None: ckA
new.MetaDGTF(mkcfg(new, memA)).run(
    Q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
    run_id="CK56A", max_minutes=1e-6)
dA = json.loads((ckA / "CK56A.json").read_text(encoding="utf-8"))
new.run_ckpt_dir = _orig
ck(int(dA.get("window_calls") or -1) == int(dA.get("llm_calls") or -2),
   "window=%r == llm_calls=%r" % (dA.get("window_calls"), dA.get("llm_calls")))
ck(int(dA.get("llm_calls") or 0) > 0, "第一窗口确实花了调用：%r" % (dA.get("llm_calls"),))

print("\n【B】续跑：第二个窗口的快照必须是**累计**")
d1, d2 = run_chain(new, "B")
c1, c2 = int(d1.get("llm_calls") or 0), int(d2.get("llm_calls") or 0)
w2 = int(d2.get("window_calls") or 0)
ck(c1 > 0 and w2 > 0, "两窗口都有读数（c1=%d, window2=%d）" % (c1, w2))
ck(c2 >= c1, "第二窗口 llm_calls(%d) ≥ 第一窗口(%d) —— 累计没有被抹掉" % (c2, c1))
ck(c2 == c1 + w2, "且恰好等于 基线(%d) + 本窗口(%d) = %d" % (c1, w2, c1 + w2))
ck(w2 < c2, "window_calls(%d) < llm_calls(%d)（两个口径分得开）" % (w2, c2))

print("\n【C】旧版对照：同链路跑 v1.23.55 ⇒ 第二窗口归零")
e1, e2 = run_chain(old, "C")
o1, o2 = int(e1.get("llm_calls") or 0), int(e2.get("llm_calls") or 0)
ck(o2 < int(e1.get("llm_calls") or 0) + int(e2.get("llm_calls") or 0),
   "旧版第二窗口 llm_calls=%d（≈本窗口），没把第一窗口的 %d 算进去" % (o2, o1))
ck("window_calls" not in e2, "旧版没有 window_calls 字段（口径没分开）")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
