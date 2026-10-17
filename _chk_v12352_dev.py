# -*- coding: utf-8 -*-
"""v1.23.52 开发期构造性验证：`paused` 跑次不写 EML 库。

判据：
  A 真入口：`run(max_minutes=极小)` ⇒ `paused` + `pending_layers` +
    `playbook.skipped_paused` + **episodes 一条都没有**
  B 旧版对照：同样场景跑 v1.23.51 ⇒ episodes **有 1 条**（证明判据有牙）
  C 负对照：正常跑（预算关）⇒ 照写 1 条（不是「一律不写」）
  D 方法级两臂：同一份 result，加 `pending_layers` ⇒ 不写；去掉 ⇒ 写

★ LLM 必须打桩：本脚本给两个版本的模块都装上 smoke 的 `fake_call`，
  否则这里就是真 API 调用（**会花钱**）。
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

Q = "冒烟题面：这件事的边界在哪里（v12352 暂停不写库判据）"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("e52_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    # ★ 打桩：不打这个桩 = 真花钱
    m.LLM._real_call = m.LLM.call
    m.LLM.call = st.fake_call
    assert getattr(m.LLM.call, "__name__", "") == "fake_call", "LLM 桩没装上"
    return m


def mkcfg(mod, mem):
    c = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="v52out_")))
    c.setdefault("playbook", {})
    c["playbook"]["mode"] = "on"
    c["playbook"]["dir"] = str(mem)
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    c["all_on"] = False
    return c


def n_eps(mod, mem):
    p = mem / "episodes.jsonl"
    if not p.is_file():
        return 0
    return len(mod.eml_read_jsonl(p) or [])


new = load(HERE / "元DGTF-V1.23.52.py")
old = load(HERE / "元DGTF-V1.23.51.py")

print("=" * 62)
print("【A】新版真入口：预算到点 ⇒ paused 且不写库")
memA = pathlib.Path(tempfile.mkdtemp(prefix="v52A_"))
rA = new.MetaDGTF(mkcfg(new, memA)).run(
    Q, route=["0", "1"], rounds={"0": 1, "1": 1},
    parallel_mode="serial", run_id="PZ1", max_minutes=1e-6)
ck(rA.get("paused") is True, "产物标了 paused")
ck(bool(rA.get("pending_layers")), "产物交代了 pending_layers：%r"
   % (rA.get("pending_layers"),))
ck((rA.get("playbook") or {}).get("skipped_paused") is True,
   "playbook 块标了 skipped_paused")
ck(n_eps(new, memA) == 0, "episodes 一条都没写（实测 %d）" % n_eps(new, memA))
ck(not (memA / "playbook.jsonl").is_file(),
   "playbook 也没落盘（连库都不建）")

print("\n【B】旧版对照：同场景 ⇒ 写了 1 条（判据有牙）")
memB = pathlib.Path(tempfile.mkdtemp(prefix="v52B_"))
rB = old.MetaDGTF(mkcfg(old, memB)).run(
    Q, route=["0", "1"], rounds={"0": 1, "1": 1},
    parallel_mode="serial", run_id="PZ1", max_minutes=1e-6)
ck(rB.get("paused") is True, "旧版同样 paused（前提一致）")
ck(n_eps(old, memB) == 1, "旧版写了 1 条半程样本（证明本版确实改了行为，实测 %d）"
   % n_eps(old, memB))

print("\n【C】负对照：正常跑 ⇒ 照写（不是「一律不写」）")
rC = new.MetaDGTF(mkcfg(new, memA)).run(
    Q, route=["0"], rounds={"0": 1},
    parallel_mode="serial", run_id="PZ2")
ck(not rC.get("paused"), "正常跑没被标 paused")
ck((rC.get("playbook") or {}).get("skipped_paused") is not True,
   "正常跑没被当暂停跳过")
ck(n_eps(new, memA) == 1, "正常跑写了 1 条（实测 %d）" % n_eps(new, memA))

print("\n【D】方法级两臂：只差 pending_layers 这一个键")
memD = pathlib.Path(tempfile.mkdtemp(prefix="v52D_"))
eng = new.MetaDGTF(mkcfg(new, memD))


def _res(rid, extra=None):
    d = {"id": rid, "question": Q, "route": ["0"], "rounds": {"0": 1},
         "dispatch": {"_parallel_mode": "serial"},
         "views": {"0": {"stop_reason": "自然安住", "duty": {"S": 0.5}}},
         "pools": {"0": {"anchors": [], "web_results": []}},
         "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
         "_auto_dispatch": {"_history": {}}}
    if extra:
        d.update(extra)
    return d


b1 = eng._eml_finish(_res("D1", {"paused": True,
                                 "pending_layers": ["1", "both", "all"]}))
ck(b1.get("skipped_paused") is True and n_eps(new, memD) == 0,
   "带 pending_layers ⇒ 跳过（episodes %d）" % n_eps(new, memD))
b2 = eng._eml_finish(_res("D1"))
ck(b2.get("skipped_paused") is not True and n_eps(new, memD) == 1,
   "去掉 pending_layers ⇒ 照写（同 run_id、同读数 ⇒ episodes %d）"
   % n_eps(new, memD))
b3 = eng._eml_finish(_res("D1", {"paused": True,
                                 "pending_layers": ["1", "both", "all"]}))
ck(b3.get("skipped_paused") is True, "补一次暂停收尾仍被挡住")
ck(n_eps(new, memD) == 1, "补那次没写第二条（实测 %d）" % n_eps(new, memD))

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
