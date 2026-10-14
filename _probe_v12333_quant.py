# -*- coding: utf-8 -*-
"""[第六期] 探针：`quant_readings` 真跑恒空 —— 分清「没触发」与「坏了」。

★ 本项目通则：**判据要能区分「没触发」与「坏了」** —— 分不开就会把
  **正确行为**当缺陷反复"修"。⇒ 打点（猴补丁包一层方法、进出各读一次、
  **不改主文件**），而不是加一条更细的判据。

四问：
  Q1 `_quant_note` 到底被调用了几次？（0 次 ⇒ 接线不可达；>0 次 ⇒ 写了但没出）
  Q2 `restate_fidelity` / `semantic_density` 返回了什么？（verdict 是否空）
  Q3 `view.quant_readings` 在 to_dict 前是否有值？（有值 ⇒ 出口丢；空 ⇒ 写没发生）
  Q4 真跑的 view 对象从哪来（是 View 还是 dict）？
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import importlib.util
_sp = importlib.util.spec_from_file_location("dgtf_m", HERE / "元DGTF-V1.23.33.py")
m = importlib.util.module_from_spec(_sp)
sys.modules["dgtf_m"] = m
_sp.loader.exec_module(m)

log = []

# ── Q1/Q3：包 `_quant_note`（进出各读一次）──
# ★★ 关键：接线点在 **`DGTF._quant_note`**（`DGTF.run` L8749-9053），
#    而 `MetaDGTF` **不继承** `DGTF`（每次跑一层**新建 DGTF 实例**）。
#    ⇒ 第一版探针只补了 `MetaDGTF._quant_note` ⇒ 一次都没记到 ⇒ **探针假阴性**。
#    ★ 通则：**打点要打在接线点真正所属的那个类上** —— 补错类 = 「没触发」的假象。
_orig_note = m.DGTF._quant_note
_calls = {"n": 0, "by_key": {}}


def _spy_note(self, view, key, val):
    _calls["n"] += 1
    _calls["by_key"][key] = _calls["by_key"].get(key, 0) + 1
    log.append("[note] #%d key=%s val=%r" % (_calls["n"], key, val))
    r = _orig_note(self, view, key, val)
    try:
        _d = getattr(view, "quant_readings", None) or {}
        log.append("       after write: view.quant_readings=%r" % (dict(_d),))
    except Exception as e:
        log.append("       after write EXC %r" % (e,))
    return r


m.DGTF._quant_note = _spy_note

# ── Q2：包三个纯函数 ──
_orig_rf = m.restate_fidelity
_rf_all = []


def _spy_rf(q, a):
    r = _orig_rf(q, a)
    _rf_all.append((repr(q)[:60], repr(a)[:60], r))
    log.append("[restate_fidelity] q=%r a=%r => %r" % (repr(q)[:40], repr(a)[:40], r))
    return r


m.restate_fidelity = _spy_rf

_orig_sd = m.semantic_density
_sd_all = []


def _spy_sd(t):
    r = _orig_sd(t)
    _sd_all.append(r)
    log.append("[semantic_density] len=%r => %r" % (
        len(str(t or "")), r))
    return r


m.semantic_density = _spy_sd

_orig_yy = m.yin_yang_divergence
_yy_all = []


def _spy_yy(a, b):
    r = _orig_yy(a, b)
    _yy_all.append(r)
    log.append("[yin_yang_divergence] |a|=%d |b|=%d => %r" % (
        len(a or []), len(b or []), r))
    return r


m.yin_yang_divergence = _spy_yy

# ── Q4：看真跑怎么造 view ──
_cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
meta = m.MetaDGTF(_cfg)
res = meta.run("只用被动观测能否排除外部驱动或测量滤波制造的伪收敛？"
               "若不能，判据需包含干预。请给出可检验的判据并说明其边界条件。",
               parallel_mode="serial", rounds={"0": 1, "1": 1, "both": 1, "all": 1},
               route=["0"], orientation="auto", run_id="QPROBE")

print("=" * 70)
print("[Q1] _quant_note 调用次数 =", _calls["n"], " by_key =", _calls["by_key"])
print("[Q2] restate_fidelity 调用 %d 次" % len(_rf_all))
for q, a, r in _rf_all[:6]:
    print("     q=%s a=%s => %r" % (q, a, r))
print("[Q2] semantic_density 调用 %d 次；非 None 值 = %r"
      % (len(_sd_all), [x for x in _sd_all if x is not None][:6]))
print("[Q2] yin_yang_divergence 调用 %d 次" % len(_yy_all))
for r in _yy_all[:4]:
    print("     => %r" % (r,))
print("[Q4] views 类型 =", {k: type(v).__name__
                          for k, v in (res.get("views") or {}).items()})
print("=" * 70)
print("\n".join(log[:40]))
