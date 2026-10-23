# -*- coding: utf-8 -*-
"""v1.23.54 开发期构造性验证：并行跑次能被墙钟截住 + 续跑按 serial 跑剩余层。

判据：
  A 真入口：A 模式 + 极小预算 ⇒ `paused` + `pending_layers` + EML 零写入
  B 标记：截断层的 `stop_reason` 必须带「墙钟预算」——否则续跑认不出来（假修）
  C 续跑：用 A 的快照、仍传 mode="A" ⇒ 产物记 `resumed_serial`；
    已完成的层**不重跑**、截断层**重跑**（用 spy 数实际跑了哪些层）
  D 负对照：预算关的 A 模式 ⇒ 不 paused、`resumed_serial` 不出现

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

Q = "冒烟题面：这件事的边界在哪里（v12354 并行墙钟判据）"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("e54_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.LLM._real_call = m.LLM.call
    m.LLM.call = st.fake_call
    assert getattr(m.LLM.call, "__name__", "") == "fake_call", "LLM 桩没装上"
    return m


new = load(HERE / "元DGTF-V1.23.54.py")

_ck = pathlib.Path(tempfile.mkdtemp(prefix="v54ck_"))
_mem = pathlib.Path(tempfile.mkdtemp(prefix="v54mem_"))
_orig_dir = new.run_ckpt_dir
new.run_ckpt_dir = lambda base=None: _ck


def mkcfg():
    c = new.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="v54out_")))
    c["playbook"] = {"mode": "on", "dir": str(_mem)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
    c.setdefault("runtime", {})
    c["runtime"]["live_checkpoint"] = True
    c["runtime"]["ckpt_interval"] = 0.05
    c["all_on"] = False
    return c


def n_eps():
    p = _mem / "episodes.jsonl"
    return len(new.eml_read_jsonl(p) or []) if p.is_file() else 0


print("=" * 62)
print("【A】A 模式 + 极小预算 ⇒ paused，且 EML 零写入")
r1 = new.MetaDGTF(mkcfg()).run(
    Q, route=["0", "1"], rounds={"0": 1, "1": 2}, parallel_mode="A",
    run_id="PA1", max_minutes=1e-6)
ck(r1.get("paused") is True, "产物标了 paused")
ck(bool(r1.get("pending_layers")), "产物交代了 pending_layers：%r"
   % (r1.get("pending_layers"),))
ck(n_eps() == 0, "episodes 一条都没写（实测 %d）" % n_eps())

print("\n【B】截断层的 stop_reason 必须带标记（否则续跑认不出来）")
_views = r1.get("views") or {}
_trunc = [e for e, v in _views.items()
          if "墙钟预算" in str((v or {}).get("stop_reason") or "")]
ck(bool(_trunc), "有层带「墙钟预算」标记：%r" % (_trunc,))
ck(sorted(_trunc) == sorted(r1.get("pending_layers") or []),
   "带标记的层 == pending_layers（%r vs %r）"
   % (sorted(_trunc), sorted(r1.get("pending_layers") or [])))
ck("0" not in _trunc, "只跑 1 圈的层 0 没被误标（%r）" % (_trunc,))

print("\n【C】续跑：仍传 mode=A ⇒ 降级 serial，完成的层不重跑、截断层重跑")
_snap = _ck / ("%s.json" % "PA1")
ck(_snap.is_file(), "暂停快照已落盘：%s" % _snap.name)
if _snap.is_file():
    _d = json.loads(_snap.read_text(encoding="utf-8"))
    ck(_d.get("status") == "paused", "快照状态是 paused（%r）" % (_d.get("status"),))
    _ran = []
    _orig_layer = new.MetaDGTF._run_layer

    def _spy(self, entry, n):
        _ran.append(entry)
        return _orig_layer(self, entry, n)

    new.MetaDGTF._run_layer = _spy
    try:
        r2 = new.MetaDGTF(mkcfg()).run(
            Q, route=["0", "1"], rounds={"0": 1, "1": 2}, parallel_mode="A",
            run_id="PA2", resume_ckpt=str(_snap))
    finally:
        new.MetaDGTF._run_layer = _orig_layer
    ck(r2.get("resumed_serial") == "A",
       "产物记了 resumed_serial=A（实测 %r）" % (r2.get("resumed_serial"),))
    ck("0" not in _ran, "已完成的层 0 **没重跑**（跑了 %r）" % (_ran,))
    ck("1" in _ran, "截断层 1 **重跑了**（跑了 %r）" % (_ran,))
    _v0a = json.dumps((r1.get("views") or {}).get("0"), sort_keys=True,
                      ensure_ascii=False, default=str)
    _v0b = json.dumps((r2.get("views") or {}).get("0"), sort_keys=True,
                      ensure_ascii=False, default=str)
    ck(_v0a == _v0b, "层 0 的产物与快照那份逐字相同（真复用）")
    ck(not r2.get("paused"), "这次跑完了（没再 paused）")

print("\n【D】负对照：预算关的 A 模式 ⇒ 不 paused、不降级")
r3 = new.MetaDGTF(mkcfg()).run(
    Q, route=["0", "1"], rounds={"0": 1, "1": 1}, parallel_mode="A",
    run_id="PA3")
ck(not r3.get("paused"), "没被标 paused")
ck("resumed_serial" not in r3, "没有 resumed_serial（没续跑）")
ck(set((r3.get("views") or {})) >= {"0", "1"}, "两层都有产物")

new.run_ckpt_dir = _orig_dir
print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
