# -*- coding: utf-8 -*-
"""v1.23.57 开发期构造性验证：`goal_trace` 跨圈携带 ⇒ 早停单标量判据**走得到**。

★ 为什么拆两段证：
  只跑真入口不够 —— mock 的产物是**固定文本**，修行层第 2 圈就被「复述/空转」自然停了，
  根本走不到第 3 圈（早停单标量要求 ≥3 条历史）⇒ 会误判成"判据不灵"。
  所以：
    段一（真入口）：历史确实**跨圈接上**（`goal_trace` 条数 == 圈数）；
    段二（纯函数）：喂 3 条历史给它，**必须真触发** —— 证明判据本体是活的。
  两段合起来才是"链通了"。

判据：
  D 旧版对照：同条件跑 v1.23.56 ⇒ `goal_trace` 恒 1 条（缺陷重现）
  A 真入口：`goal_trace` 条数 == `rounds_run` 且 ≥2
  B 纯函数：3 条「增益低于阈值」的历史 ⇒ `layer_gain_stop_signal` 返回 True
  C 负对照：只给 1 条历史 ⇒ 返回 False（门就是那道 `len < N+1`）；`gain_floor=0` ⇒ 也 False

★ LLM 打桩。
"""
import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

Q = "冒烟题面：这件事的边界在哪里（v12357 跨圈携带判据）"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("e57_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.LLM._real_call = m.LLM.call
    m.LLM.call = st.fake_call
    assert getattr(m.LLM.call, "__name__", "") == "fake_call", "LLM 桩没装上"
    return m


def mkcfg(mod, gain_floor=0.0):
    c = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="v57out_")))
    c["playbook"] = {"mode": "off",
                     "dir": str(pathlib.Path(tempfile.mkdtemp(prefix="v57mem_")))}
    c.setdefault("stop", {})["gain_floor"] = float(gain_floor)
    c.setdefault("runtime", {})["live_checkpoint"] = False
    c["all_on"] = False
    return c


def run_one(mod):
    r = mod.MetaDGTF(mkcfg(mod, 0.0)).run(
        Q, route=["0"], rounds={"0": 5}, parallel_mode="serial")
    v = (r.get("views") or {}).get("0") or {}
    return (int(v.get("rounds_run") or 0), len(v.get("goal_trace") or []),
            str(v.get("stop_reason") or ""))


new = load(HERE / "元DGTF-V1.23.57.py")
old = load(HERE / "元DGTF-V1.23.56.py")

print("=" * 62)
print("【D】旧版对照：goal_trace 恒 1 条（缺陷重现）")
r_old, t_old, _ = run_one(old)
ck(t_old == 1, "旧版：跑了 %d 圈但 goal_trace 只有 %d 条" % (r_old, t_old))

print("\n【A】新版真入口：历史跨圈接上")
r_n, t_n, s_n = run_one(new)
ck(t_n == r_n, "goal_trace=%d == rounds_run=%d" % (t_n, r_n))
ck(t_n >= 2, "至少 2 条历史（不再是恒 1 条）")

print("\n【B】纯函数：3 条低增益历史 ⇒ 判据**必须触发**")
_prev = [{"round": 1, "excavate": 0.90},
         {"round": 2, "excavate": 0.90},
         {"round": 3, "excavate": 0.90}]
_hit, _why = new.layer_gain_stop_signal(
    "0", _prev[-1], _prev, 0.5)
ck(_hit is True, "返回 True（%s）" % (_why[:50] or "无理由"))
ck("增益趋零" in str(_why), "理由里点名「增益趋零」")

print("\n【C】负对照：历史不够 / 键关闭 ⇒ 都不触发")
_h1, _ = new.layer_gain_stop_signal("0", _prev[-1], _prev[-1:], 0.5)
ck(_h1 is False, "只给 1 条历史 ⇒ False（那道 len<3 门还在）")
_h0, _ = new.layer_gain_stop_signal("0", _prev[-1], _prev, 0.0)
ck(_h0 is False, "gain_floor=0（默认关）⇒ False（零行为差）")
_hn, _ = new.layer_gain_stop_signal(
    "0", {"round": 3, "excavate": 0.10},
    [{"round": 1, "excavate": 0.90}, {"round": 2, "excavate": 0.20},
     {"round": 3, "excavate": 0.10}], 0.5)
ck(_hn is False, "增益有起伏（第 2 圈 0.90→0.20 增益 0.70 ≥ 阈值）⇒ 不停")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
