#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：[本轮铁律] `candidate_yield` 在**真实入口**下是否可达。

## 为什么必须单独探
本轮新增 `candidate_yield()`（候选产出率），判据 ㉜ 只查了：
  · 纯函数方向两向（直接喂构造入参）
  · 源码里 `candidate_yield([getattr(c, "desc", "")` 字面存在
  · 接线位置 `_i_cy < _i_dj`
但本项目已经栽过两次**「纯函数全绿 / 字面存在 ⇒ 实际不可达」**：
  ① v1.23.27 三条信念迁移在真实入口结构性不可达；
  ② 本轮 `_quant_note` 只定义在 `MetaDGTF`、调用点在 `DGTF`（无继承）⇒
     `AttributeError` 被 `except: pass` 静默吞掉，真跑 `quant_readings` 四层全空。
⇒ **凡新能力必须配「真实入口产出」判据**（跑一次真实入口、断言产出）。

## 本探针做什么
复用 smoke_test 的全局 mock（`mod.LLM.call = fake_call`）——
**零 API 花费**，但走的是**真实引擎路径** `MetaDGTF.run(...)`：
  载入引擎 → 装 mock LLM → 跑 route=["0"] / rounds={"0": 3}（≥2 圈才有上一圈可比）
  → 读 `res["views"]["0"]["quant_readings"]`，断言里面有 `candidate_yield` 键。

## 四问（与 `_probe_v12333_quant.py` 同规格）
  Q1 `candidate_yield` 被调了几次？
  Q2 返回值形态对不对（有 n / new_ratio / verdict）？
  Q3 `view.quant_readings` 里有没有这个键（**出口**）？
  Q4 四问的「同一个东西」：读的是不是 `to_dict()` 之后的那份？
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"


def main():
    # ── 复用 smoke_test 的模块级 mock（不跑它的 main）──
    spec = importlib.util.spec_from_file_location("smoke_test_probe", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_test_probe"] = st
    spec.loader.exec_module(st)
    mod = st.mod
    print("[mock] %s 已装载；LLM.call = %s" % (SRC.name, getattr(mod.LLM, "call", None)))

    # ── Q1：给 candidate_yield 打点（猴补丁包一层，不改主文件）──
    _orig_cy = mod.candidate_yield
    _n = {"cy": 0, "ret": []}

    def _spy_cy(cands, prev_texts, thr=0.72):
        r = _orig_cy(cands, prev_texts, thr)
        _n["cy"] += 1
        _n["ret"].append(dict(r or {}))
        return r
    mod.candidate_yield = _spy_cy

    # ── 真实入口：mock run，route=0 / 3 圈（≥2 圈才有「上一圈」可比）──
    cfg = st.build_cfg(False)
    meta = mod.MetaDGTF(cfg)
    print("[run] route=['0'] rounds={'0':3}（mock LLM ⇒ 零花费）")
    res = meta.run("意识能否被还原为信息处理过程？",
                   route=["0"], rounds={"0": 3},
                   parallel_mode="serial")
    mod.candidate_yield = _orig_cy

    # ── Q4：读法与主路径一致（to_dict() 之后）──
    views = res.get("views") or {}
    v0 = views.get("0")
    vd = v0.to_dict() if hasattr(v0, "to_dict") else (v0 or {})
    qr = (vd or {}).get("quant_readings") or {}

    print("\n=== 四问 ===")
    print("Q1 candidate_yield 调用次数 = %d" % _n["cy"])
    for i, r in enumerate(_n["ret"], 1):
        print("     第 %d 次返回：n=%r n_new=%r new_ratio=%r max_sim=%r verdict=%r"
              % (i, r.get("n"), r.get("n_new"), r.get("new_ratio"),
                 r.get("max_sim"), r.get("verdict")))
    print("Q3 quant_readings 键 = %r" % (sorted(qr.keys()),))
    print("     candidate_yield 值 = %r" % (qr.get("candidate_yield"),))
    # ── Q5：内部暂存量**不许污染产物**（`_prev_cand_descs` 是过程状态）──
    #   `Pool.to_dict()` 是**手工白名单** ⇒ 本该不带出；但白名单的失效模式
    #   正是「新增字段静默漏掉」的反面 —— 这次要证的是「动态属性不被吞进去」。
    import json as _json
    _blob = _json.dumps(res, ensure_ascii=False, default=str)
    _dirty = "_prev_cand_descs" in _blob
    print("Q5 产物 JSON %d 字符；含 `_prev_cand_descs` = %r（应为 False）"
          % (len(_blob), _dirty))
    print("     quant_readings 在产物里 = %r" % ("quant_readings" in _blob,))

    ok = True
    if _dirty:
        print("\n[X] Q5 失败：内部暂存量污染了产物")
        ok = False
    if _n["cy"] <= 0:
        print("\n[X] Q1 失败：真实入口下一次都没调到 —— **能力不可达**")
        ok = False
    if "candidate_yield" not in qr:
        print("\n[X] Q3 失败：调到了但没落进 `quant_readings`（写入口/出口断了）")
        ok = False
    else:
        _v = qr.get("candidate_yield") or {}
        if isinstance(_v, dict) and "value" in _v and len(_v) == 1:
            _v = _v["value"]
        if not isinstance(_v, dict) or "verdict" not in _v:
            print("\n[X] Q3.b 失败：落盘值形态不对（应为含 verdict 的 dict）：%r" % (_v,))
            ok = False
    print("\n%s" % ("[OK] 真实入口可达" if ok else "[FAIL] 真实入口**不可达**"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
