#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 前置量化探针：①「独立度」口径 ②修行层停止判据/文案。

改前 / 改后同一支探针跑两次对表：

    python _probe_v12324_indep_therapy.py 元DGTF-V1.23.23.py _probe_v12324.before.txt
    python _probe_v12324_indep_therapy.py 元DGTF-V1.23.24.py _probe_v12324.after.txt

★ 走生产入口（Pool.add_undecidable / _und_channel_line / _pool_shape /
  _stop_reasons / _finalize_layer_common），不手造 Input。
★ 输出自带 write_bytes 落盘 —— 本机 shell `>` 偶发写空/写旧。
"""
from __future__ import annotations

import importlib.util
import inspect
import io
import contextlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

OUT: list = []


def say(line=""):
    OUT.append(str(line))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("dgtf_probe", str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_probe"] = m
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- fixtures
ASPECTS = [
    "本体论地位需要先确定登记位置",
    "自指结构导致时刻错开",
    "判决实验缺少可操作标准",
]
AMPS_MIX = [
    # ① 与 aspect[0] 逐字相同 —— 按提示词「不得直接复述」，这条**不独立**
    "本体论地位需要先确定登记位置",
    # ② 与 aspect[0] 高重叠 —— 长句包含短句，_overlap_coef 分母 min
    "任何判定都要求对象在登记前已有边界，本体论地位因此没有登记位置",
    # ③ 与前三条都无关 —— 真独立
    "与上述各项均无关的一条独立结构观察结论",
    # ④ 也无关 —— 真独立
    "关于尺度效应的一条独立观察，与判定标准无关",
]
# ★ 样例判别力：旧口径（命中方面数/方面数）与新口径（自由结构数/结构数）
#   必须**给出不同的数**，否则两种实现在这条样例上不可区分（= 没判别力）。
#   本夹具：旧 = 1/3 = 0.333，新 = 2/4 = 0.500。


def sec(title):
    say("")
    say("=" * 70)
    say(title)
    say("=" * 70)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.23.py"
    outp = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    mod = _load(src)

    say(f"被验文件：{src.name}")
    say(f"__version__ = {getattr(mod, '__version__', '?')}")

    cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    cfg["api"]["key"] = "sk-probe-key"
    cfg["output"]["verbose"] = False
    cfg["output"]["save_dir"] = tempfile.mkdtemp(prefix="probe12324_")

    # ---------------------------------------------------------- S1 口径
    sec("S1 · 不可判定结构通道口径（走生产入口 Pool.add_undecidable）")
    say(f"und_aspects = {ASPECTS}")
    for i, a in enumerate(AMPS_MIX):
        _mx = max((mod._overlap_coef(a, asp) for asp in ASPECTS), default=0.0)
        say(f"  structural_amps[{i}] max_overlap={_mx:.3f}  {a[:32]}…")

    pool = mod.Pool()
    pool.add_undecidable(
        {"structural_amps": list(AMPS_MIX), "aligned_amps": [],
         "clarity": 0.7}, list(ASPECTS), layer=1)
    ch = pool.undecidable_channel

    say("")
    say("[旧键 · 不变式] 这些必须逐个数字不变（它们喂模型 + 历史语料）")
    for k in ("last_struct_hit", "last_struct_coverage",
              "last_aligned_hit", "last_aligned_coverage"):
        say(f"  {k} = {ch.get(k)!r}")
    say(f"  struct_coverage_history = {ch.get('struct_coverage_history')!r}")

    say("")
    say("[新键 · 独立度] 改前应全部缺失")
    _has_new = all(k in ch for k in
                   ("last_indep_ratio", "last_indep_pool",
                    "last_indep_free", "indep_history"))
    say(f"  四个新键齐全 = {_has_new}")
    for k in ("last_indep_ratio", "last_indep_pool",
              "last_indep_free", "indep_history"):
        say(f"  {k} = {ch.get(k)!r}")

    # 探针侧独立复算（参照实现）—— 与实现比对，防「实现自己算错了」
    _free = [a for a in AMPS_MIX
             if not any(mod._overlap_coef(asp, a) >= 0.3 for asp in ASPECTS)]
    say(f"  [参照] 独立条数 = {len(_free)}/{len(AMPS_MIX)} "
        f"⇒ 独立度 = {len(_free) / len(AMPS_MIX):.4f}")

    # 空池：不许把「没东西」印成 0.00
    pool_e = mod.Pool()
    pool_e.add_undecidable({"structural_amps": [], "aligned_amps": [],
                            "clarity": 0.5}, list(ASPECTS), layer=1)
    che = pool_e.undecidable_channel
    say(f"  [空池负对照] last_indep_ratio = {che.get('last_indep_ratio')!r}"
        f"（None = 不可计算，0.0 = 假读数）")

    # ------------------------------------------------- S2 产物渲染
    sec("S2 · _und_channel_line 渲染串（产物 md「七、原始问题覆盖率」）")
    mg = mod.MetaDGTF(cfg)
    mg.pools["1"].undecidable_channel = ch
    with contextlib.redirect_stdout(io.StringIO()):
        line_new = mg._und_channel_line()
    say("[新口径 dict]")
    say(line_new.rstrip("\n") or "（空串）")

    legacy = {
        "clarity_history": [0.6, 0.75],
        "struct_coverage_history": [0.4, 0.6],
        "und_aspects": [f"面{i}" for i in range(10)],
        "last_struct_hit": 6,
        "structural_amps": ["a", "b"], "aligned_amps": [],
    }
    mg2 = mod.MetaDGTF(cfg)
    mg2.pools["1"].undecidable_channel = dict(legacy)
    with contextlib.redirect_stdout(io.StringIO()):
        line_leg = mg2._und_channel_line()
    say("[历史 packed / 旧键 dict]（必须仍渲染得出来，不许静默丢信息）")
    say(line_leg.rstrip("\n") or "（空串）")

    # ------------------------------------------------- S3 模型输入
    sec("S3 · _pool_shape 串（★ 这是喂给模型的输入，改它 = 运行期可见变化）")
    # ★ _pool_shape 挂在 DGTF 上（不是 MetaDGTF）—— 名字先 grep 再用
    def _shape(_pool, _label):
        _dg = mod.DGTF("1", mod.LLM(cfg), cfg)
        _dg.verbose = False
        with contextlib.redirect_stdout(io.StringIO()):
            return _dg._pool_shape(_pool, _label)

    shape1 = _shape(pool, "【修行层池】")
    shape2 = _shape(pool_e, "【研究层池】")
    say("[有独立度数据的池]")
    for ln in shape1.splitlines():
        if "不可判定" in ln or "可判定覆盖" in ln:
            say("   " + ln)
    say("[空池]")
    for ln in shape2.splitlines():
        if "不可判定" in ln or "可判定覆盖" in ln:
            say("   " + ln)

    # ------------------------------------------------- S4 停止理由
    sec("S4 · _stop_reasons 的**签名**（有无 stall_is_sat）")
    sig = inspect.signature(mod.MetaDGTF._stop_reasons)
    _has_flag = "stall_is_sat" in sig.parameters
    say(f"  stall_is_sat 参数存在 = {_has_flag}")
    say(f"  参数表 = {list(sig.parameters)}")

    sec("S5 · sat 推计数后的停因文案（空括号复现）")
    mr = mod.MetaDGTF(cfg)
    _sp = dict(mod.DEFAULT_CONFIG["spiral"])
    kw = dict(entry="0", layer_no=3, rounds_n=3, total_rounds=3, sp=_sp,
              soft_max=3, sim_thr=0.8, stable_need=2, idle_limit=2,
              r_idle_limit=2, r_stall_limit=2, rephrase_streak=0,
              carry_streak=0, idle_new_amp=0, idle_new_thread=0,
              idle_stall=2, stall_why="", sat_override=False,
              prev_product="", view=mod.View(entry="0"), idles=0)
    if _has_flag:
        kw["stall_is_sat"] = True
    with contextlib.redirect_stdout(io.StringIO()):
        r0, _ = mr._stop_reasons(**kw)
    _txt = " | ".join(str(x) for x in r0)
    say(f"  entry=0 / idle_stall=2 / stall_why='' / stall_is_sat="
        f"{kw.get('stall_is_sat')}")
    say(f"  ⇒ {_txt}")
    say(f"  含空括号「（）」= {'（）' in _txt}")

    kw2 = dict(kw)
    kw2.update(idle_stall=0, idle_new_amp=2, sat_override=True)
    kw2.pop("stall_is_sat", None)
    with contextlib.redirect_stdout(io.StringIO()):
        r1, _ = mr._stop_reasons(**kw2)
    say(f"  entry=0 / sat_override=True / idle_new_amp=2 ⇒ "
        f"{' | '.join(str(x) for x in r1)}")

    sec("S6 · 条件 1 文案的层用词（'ing' 是否还在）")
    for e in ("0", "1", "both", "all"):
        with contextlib.redirect_stdout(io.StringIO()):
            rr, _ = mr._stop_reasons(
                entry=e, layer_no=2, rounds_n=3, total_rounds=3, sp=_sp,
                soft_max=2, sim_thr=0.8, stable_need=2, idle_limit=2,
                r_idle_limit=2, r_stall_limit=2, rephrase_streak=2,
                carry_streak=0, idle_new_amp=0, idle_new_thread=0,
                idle_stall=0, stall_why="", sat_override=False,
                prev_product="", view=mod.View(entry=e), idles=0)
        t = " | ".join(str(x) for x in rr)
        say(f"  entry={e:>4} ⇒ {t}")
    say("  （判据：'ing' 只该出现在对撞层；修行/研究/元层用「X层」）")

    # ------------------------------------------------- S7 收尾体检
    sec("S7 · _finalize_layer_common：修行层停因是否附「本轮显形 / 未生质量」")
    for _why in ("连续 2 轮有新增但无推进（修行层无新增或无推进），螺旋停止",
                 "体力耗尽（4 圈走满，未触发任何停止判据，是被截断不是自然停止）"):
        vv = mod.View(entry="0")
        vv.stop_reason = _why
        stt = {"roles_hist": ["摊开"], "total_rounds": 4, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 4, "rounds_n": 4, "sp": mod._spiral_for(cfg, "0")}
        mm = mod.MetaDGTF(cfg)
        with contextlib.redirect_stdout(io.StringIO()):
            mm._finalize_layer_common("0", vv, stt)
        _has = "未生质量" in (vv.stop_reason or "")
        say(f"  入口停因 = {_why[:24]}… ⇒ 附体检 = {_has}")
        if _has:
            say(f"     {vv.stop_reason.splitlines()[-1][:60]}")

    # 非修行层不许被附加（负对照）
    vv1 = mod.View(entry="1")
    vv1.stop_reason = "研究层双通道均收敛，螺旋停止"
    stt1 = {"roles_hist": ["摊开"], "total_rounds": 4, "round_log": [],
            "all_rehashed": [], "all_candidates": [], "all_amps": [],
            "all_threads": [], "all_expanded_descs": [],
            "all_dec_products": [], "all_und_products": [],
            "r": 4, "rounds_n": 4, "sp": mod._spiral_for(cfg, "1")}
    mm1 = mod.MetaDGTF(cfg)
    with contextlib.redirect_stdout(io.StringIO()):
        mm1._finalize_layer_common("1", vv1, stt1)
    say(f"  [负对照] entry=1 附体检 = {'未生质量' in (vv1.stop_reason or '')}"
        f"（必须为 False）")

    say("")
    say("=" * 70)
    say("结束")
    text = "\n".join(OUT) + "\n"
    sys.stdout.write(text)
    if outp is not None:
        outp.write_bytes(text.encode("utf-8"))
        sys.stdout.write(f"[probe] 已落盘 {outp} ({outp.stat().st_size} bytes)\n")


if __name__ == "__main__":
    main()
