#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前置量化探针 · v1.21.71（F1 ~ F11 共 11 项）

用法：
    python _probe_v71.py 元DGTF-V1.21.70.py > _probe_v71_before.txt
    python _probe_v71.py 元DGTF-V1.21.71.py > _probe_v71_after.txt

★ 全部离线：LLM 一律走 smoke_test 的 fake_call 桩（按 system 关键字返回
  罐头 JSON），绝不联网。
★ 每项尽量走**生产入口**（MetaDGTF.run / smoke_test.run_mode /
  MetaDGTF._b_finalize_layer / DGTF._quality_check / load_config / main）。
  少数只能定点的地方（F7 兜底分支）直接喂**真产物格式**的数据。
★ 本探针**只读**：不改任何源文件；唯一的写是诊断文件计数用的临时目录。
"""
import contextlib
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

TARGET = Path(sys.argv[1]).resolve()
HERE = TARGET.parent


def _load_harness():
    """加载 smoke_test，并把它的 SRC 换成 TARGET。

    ★ 为什么这么做：F1/F6/F11 要走「一次真实跑圈」的生产入口，而
      smoke_test 已经准备好全套桩（fake_call + build_cfg + run_mode）。
      复制一份 harness 会立刻分叉（本项目最贵的坑），所以这里**读它的
      源码**、只替换 SRC 那一行，并断言替换**恰好命中一次**。
    """
    src = (HERE / "smoke_test.py").read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
    hits = pat.findall(src)
    assert len(hits) == 1, f"smoke_test.py 里 SRC 行不是 1 行而是 {len(hits)} 行"
    src = pat.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), src)
    hm = types.ModuleType("probe_harness")
    hm.__file__ = str(HERE / "smoke_test.py")
    sys.modules["probe_harness"] = hm
    exec(compile(src, str(HERE / "smoke_test.py"), "exec"), hm.__dict__)
    return hm


HM = _load_harness()
mod = HM.mod
CFG = HM.build_cfg(False)
REPORT = {}
Q = "探针题：这套结构的边界到底在哪，哪些部分原则上判不出"


def _sec(name):
    print("\n" + "=" * 66)
    print(f"## {name}")
    print("=" * 66)


def _packed_run(mode="serial", rounds=None, question=Q):
    """走生产入口 MetaDGTF.run（LLM 已被 harness 换成桩，离线）。

    ★ 不用 run_mode：它返回的是**汇总行**（views 被换成 key 列表），
      拿不到 packed 里的 view 字段。
    """
    HM.CALLS["n"] = 0
    _cfg = HM.build_cfg(False)
    _meta = mod.MetaDGTF(_cfg)
    return _meta.run(question, route=["0", "1", "both", "all"],
                     rounds=rounds or {"0": 2, "1": 2, "both": 2, "all": 2},
                     parallel_mode=mode)


# ======================================================================
# [A] F1 · 单圈层是否跳过整段收尾
# ======================================================================
_sec("[A] F1 · 四层各请求 1 圈时，收尾字段在不在")
_A = {}
try:
    _res = _packed_run(rounds={"0": 1, "1": 1, "both": 1, "all": 1})
    for _e in ("0", "1", "both", "all"):
        _v = _res["views"].get(_e) or {}
        _A[f"layer_{_e}"] = {
            "roles_run": len(_v.get("roles_run") or []),
            "rounds_cap": _v.get("rounds_cap"),
            "round_log": len(_v.get("round_log") or []),
            "stop_reason": (str(_v.get("stop_reason") or ""))[:34],
        }
        print(f"   层 {_e:5s} roles_run={_A[f'layer_{_e}']['roles_run']} "
              f"rounds_cap={_A[f'layer_{_e}']['rounds_cap']} "
              f"round_log={_A[f'layer_{_e}']['round_log']} "
              f"stop_reason={_A[f'layer_{_e}']['stop_reason']!r}")
except Exception as _e:
    _A["run_exc"] = f"{type(_e).__name__}: {_e}"
    print(f"   ✗ 单圈跑崩：{_A['run_exc']}")

# 定点：_b_finalize_layer 的 total_rounds<=1 门
_A["b_finalize_gate"] = {}
try:
    _m = mod.MetaDGTF(CFG)
    _mv = mod.View(entry="0")
    _sp0 = mod._spiral_for(CFG, "0")
    _m._b_state = {"0": {
        "view": _mv, "total_rounds": 1, "roles_hist": ["摊开"],
        "all_candidates": [], "all_amps": [], "all_threads": [],
        "all_rehashed": [], "all_expanded_descs": [], "all_amp_cands": 0,
        "all_dec_products": [], "all_und_products": [], "all_view_errors": [],
        "round_log": [{"round": 1}], "deferred_notes": [],
        "r": 1, "rounds_n": 1, "sp": _sp0}}
    _m._results = {}
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        _m._b_finalize_layer("0")
    _A["b_finalize_gate"] = {
        "roles_run": list(_mv.roles_run), "rounds_cap": _mv.rounds_cap,
        "round_log": len(_mv.round_log),
        "stop_reason": (str(_mv.stop_reason or ""))[:34]}
except Exception as _e:
    _A["b_finalize_gate"] = f"EXC {type(_e).__name__}: {_e}"
print(f"   _b_finalize_layer(total_rounds=1) → "
      f"roles_run={_A['b_finalize_gate'].get('roles_run') if isinstance(_A['b_finalize_gate'], dict) else _A['b_finalize_gate']} "
      f"rounds_cap={_A['b_finalize_gate'].get('rounds_cap') if isinstance(_A['b_finalize_gate'], dict) else ''} "
      f"round_log={_A['b_finalize_gate'].get('round_log') if isinstance(_A['b_finalize_gate'], dict) else ''}")
REPORT["A"] = _A


# ======================================================================
# [B] F2 · main() 里 save_result 失败会怎样
# ======================================================================
_sec("[B] F2 · main() 保存失败时的兜底")
_B = {}
_FAKE_RESULT = {"llm_calls": 0, "llm_tokens": 0, "views": {},
                "dispatch": {"order": ["0"], "missing": [], "skipped": []},
                "question": Q}


def _drive_main(save_impl):
    _orig_run = mod.MetaDGTF.run
    _orig_save = mod.save_result
    mod.MetaDGTF.run = lambda self, *a, **k: dict(_FAKE_RESULT)
    mod.save_result = save_impl
    _argv = sys.argv
    sys.argv = ["dgtf", Q, "--route", "0", "--rounds", "0:1",
                "--parallel", "serial", "--quiet"]
    code, exc, buf = None, None, io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            mod.main()
    except SystemExit as _e:
        code = _e.code
    except BaseException as _e:                      # noqa: BLE001
        exc = f"{type(_e).__name__}: {_e}"
    finally:
        sys.argv = _argv
        mod.MetaDGTF.run = _orig_run
        mod.save_result = _orig_save
    return code, exc, buf.getvalue()


def _bad_save(*a, **k):
    raise OSError("探针：模拟磁盘写失败")


_code, _exc, _out = _drive_main(_bad_save)
_B["fail_exit_code"] = _code
_B["fail_uncaught"] = _exc
_B["fail_mentions_save"] = ("保存失败" in _out) or ("保存" in _out)
print(f"   假保存失败 → SystemExit.code={_code!r} 未捕获异常={_exc!r} "
      f"打印里提到保存失败={_B['fail_mentions_save']}")

_code2, _exc2, _out2 = _drive_main(
    lambda *a, **k: Path(tempfile.gettempdir()) / "probe_never_used.md")
_B["ok_exit_code"] = _code2
_B["ok_uncaught"] = _exc2
print(f"   保存成功（打桩成 no-op）→ SystemExit.code={_code2!r} "
      f"未捕获异常={_exc2!r}")
REPORT["B"] = _B


# ======================================================================
# [C] F3 · _build_inp_meta 遇到非法 entry 的上游 view
# ======================================================================
_sec("[C] F3 · 上游 view 的 entry 非法（'9'）时")
_C = {}
try:
    _m = mod.MetaDGTF(CFG)
    _m._upstream_provider = lambda e: [mod.View(entry="9", manifest="上游形状正文")]
    _inp = _m._build_inp_meta([])
    _C["meta"] = {"exc": None,
                  "upstream_views": [getattr(v, "entry", None)
                                     for v in _inp.upstream_views],
                  "upstream_pools": len(_inp.upstream_pools)}
except Exception as _e:
    _C["meta"] = {"exc": f"{type(_e).__name__}: {_e}"}
print(f"   _build_inp_meta  → {_C['meta']}")

try:
    _m2 = mod.MetaDGTF(CFG)
    _m2._upstream_provider = lambda e: [mod.View(entry="9", manifest="上游形状正文")]
    _inp2 = _m2._build_inp_duel([])
    _C["duel"] = {"exc": None,
                  "upstream_views": [getattr(v, "entry", None)
                                     for v in _inp2.upstream_views]}
except Exception as _e:
    _C["duel"] = {"exc": f"{type(_e).__name__}: {_e}"}
print(f"   _build_inp_duel  → {_C['duel']}"
      f"   （对照：duel 用的是固定 [0,1] 池，本来就没有这个风险）")
REPORT["C"] = _C


# ======================================================================
# [D] F4 · load_config("") 会不会误报
# ======================================================================
_sec("[D] F4 · load_config 的空路径 / 坏 yaml")
_D = {}


def _cfg_noise(path):
    _b = io.StringIO()
    with contextlib.redirect_stdout(_b):
        mod.load_config(path)
    t = _b.getvalue()
    return {"warn": ("⚠️" in t), "head": t.strip()[:56]}


_D["empty_path"] = _cfg_noise("")
_td = Path(tempfile.mkdtemp(prefix="probe71_"))
_bad = _td / "bad.yaml"
_bad.write_text("output:\n  save_dir: a\n   verbose: b\n", encoding="utf-8")
_good = _td / "good.yaml"
_good.write_text("output:\n  verbose: true\n", encoding="utf-8")
_missing = _td / "nope.yaml"
_D["bad_yaml"] = _cfg_noise(str(_bad))
_D["good_yaml"] = _cfg_noise(str(_good))
_D["missing_yaml"] = _cfg_noise(str(_missing))
shutil.rmtree(_td, ignore_errors=True)
for _k, _v in _D.items():
    print(f"   {_k:14s} 警告={_v['warn']}  head={_v['head']!r}")
REPORT["D"] = _D


# ======================================================================
# [E] F5 · route 里没有合法层时，C / D-H 的 dispatch
# ======================================================================
_sec("[E] F5 · active 为空时的 packed['dispatch']")
_E = {}
for _fn in ("_run_parallel_C", "_run_parallel_stage"):
    try:
        _m = mod.MetaDGTF(CFG)
        _m._dispatch_plan = _m._plan_dispatch(["x"])
        _m._failed_layers = {}
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            if _fn == "_run_parallel_C":
                _pk = _m._run_parallel_C(Q, ["x"], {}, {"0": 1}, None)
            else:
                _pk = _m._run_parallel_stage("G", Q, ["x"], {}, {"0": 1}, None)
        _d = _pk.get("dispatch") or {}
        _E[_fn] = {"keys": sorted(_d.keys()),
                   "mode_value": _d.get("_parallel_mode"),
                   "has_guard_keys": all(
                       k in _d for k in ("ran", "missing", "failed", "skipped"))}
    except Exception as _e:
        _E[_fn] = {"exc": f"{type(_e).__name__}: {_e}"}
    print(f"   {_fn:20s} → {_E[_fn]}")
REPORT["E"] = _E


# ======================================================================
# [F] F6 · 一次 run 里外部可判定性评估跑几次
# ======================================================================
_sec("[F] F6 · 外部 _assess_decidability 的调用次数（同一次 run）")
_F = {}
_SITE = {"route_by_decidability": 0, "assess_dynamic": 0, "other": 0}
_TAG = {"where": "other"}
_cnt = {"n": 0}
_orig_assess = mod.DGTF._assess_decidability
_orig_route = mod.MetaDGTF._route_by_decidability
_orig_dyn = mod.MetaDGTF._assess_decidability_dynamic


def _counting_assess(self, q):
    _cnt["n"] += 1
    _SITE[_TAG["where"]] += 1
    return _orig_assess(self, q)


def _tag_route(self, *a, **k):
    _TAG["where"] = "route_by_decidability"
    try:
        return _orig_route(self, *a, **k)
    finally:
        _TAG["where"] = "other"


def _tag_dyn(self, *a, **k):
    _TAG["where"] = "assess_dynamic"
    try:
        return _orig_dyn(self, *a, **k)
    finally:
        _TAG["where"] = "other"


mod.DGTF._assess_decidability = _counting_assess
mod.MetaDGTF._route_by_decidability = _tag_route
mod.MetaDGTF._assess_decidability_dynamic = _tag_dyn
try:
    _res6 = _packed_run()
    _F["ext_assess_calls"] = _cnt["n"]
    _F["site_breakdown"] = dict(_SITE)
    _F["dec_source"] = (_res6.get("decidability") or {}).get("_source")
except Exception as _e:
    _F["exc"] = f"{type(_e).__name__}: {_e}"
finally:
    mod.DGTF._assess_decidability = _orig_assess
    mod.MetaDGTF._route_by_decidability = _orig_route
    mod.MetaDGTF._assess_decidability_dynamic = _orig_dyn
print(f"   外部评估调用次数 = {_F.get('ext_assess_calls')} "
      f"（按站点 {_F.get('site_breakdown')}；判定源 {_F.get('dec_source')!r}）"
      f"{_F.get('exc', '')}")

_CACHE_KEY = "_ext_assess_cache"
_F["has_cache_attr_source"] = (
    _CACHE_KEY in inspect.getsource(mod.MetaDGTF.__init__)
    or hasattr(mod.MetaDGTF(CFG), _CACHE_KEY))
print(f"   MetaDGTF 实例上有 {_CACHE_KEY}：{_F['has_cache_attr_source']}")
REPORT["F"] = _F


# ======================================================================
# [G] F7 · 合并兜底分支与缓存分支的口径
# ======================================================================
_sec("[G] F7 · evidence 长 9 条时，缓存 / 兜底两条路的 _und_untraced")
_G = {}
_Aspect = "清分规则未定，断面客流与线路客流不可互证"
_FULL_EV = [{"aspect": f"毫不相干的噪音条目第{i}条"} for i in range(8)] \
    + [{"aspect": _Aspect}]
_CACHED = mod._untraced_undecidable([_Aspect], _FULL_EV)
_ext7 = {"decidability": "undecidable", "decidable_aspects": [],
         "undecidable_aspects": [], "reason": "", "features": []}
_pool7 = {"decidability": "undecidable",
          "undecidable_aspects": [_Aspect],
          "evidence": _FULL_EV[:8],
          "_evidence_full": _FULL_EV}
_m7 = mod.MetaDGTF(CFG)
_r_cached = _m7._merge_decidability(dict(_pool7, _und_untraced=_CACHED),
                                    dict(_ext7))
_r_fb = _m7._merge_decidability(dict(_pool7), dict(_ext7))
_G = {"cached_path_untraced": _r_cached.get("_und_untraced"),
      "fallback_path_untraced": _r_fb.get("_und_untraced"),
      "consistent": _r_cached.get("_und_untraced")
      == _r_fb.get("_und_untraced"),
      "pool_assess_full_untraced": _CACHED,
      "pool_assess_emits_evidence_full":
          "_evidence_full" in inspect.getsource(
              mod.MetaDGTF._assess_decidability_from_pool_view)}
for _k, _v in _G.items():
    print(f"   {_k} = {_v!r}")
REPORT["G"] = _G


# ======================================================================
# [H] F9 · 分词停用词
# ======================================================================
_sec("[H] F9 · _tokenize 的停用词过滤")
_H = {}
_sent = "如果我们通过一种方式进行整理的话，螺旋结构就浮现出来了"
_toks = mod._tokenize(_sent)
_H["n_tokens"] = len(_toks)
_H["has_stop_multi"] = {w: (w in _toks) for w in
                        ("的话", "一种", "进行", "我们", "通过", "这个")}
_H["keeps_content"] = {w: (w in _toks) for w in ("螺旋", "结构", "整理")}
_H["stopwords_is_chars"] = (
    all(len(x) == 1 for x in mod._STOPWORDS)
    if isinstance(mod._STOPWORDS, set) else "非 set")
for _k, _v in _H.items():
    print(f"   {_k} = {_v!r}")
print(f"   分词结果：{_toks}")
REPORT["H"] = _H


# ======================================================================
# [I] F10 · coverage_parts 的 cfg 参数
# ======================================================================
_sec("[I] F10 · coverage_parts 的 cfg 参数是否可选")
_I = {}
try:
    mod.coverage_parts(mod.Pool(), None)
    _I["pass_none"] = "ok"
except Exception as _e:
    _I["pass_none"] = f"EXC {type(_e).__name__}: {_e}"
try:
    mod.coverage_parts(mod.Pool())
    _I["omit_cfg"] = "ok"
except Exception as _e:
    _I["omit_cfg"] = f"EXC {type(_e).__name__}: {_e}"
_I["sig"] = str(inspect.signature(mod.coverage_parts))
_I["refresh_passes_config"] = \
    'coverage_parts(self.pools["1"], self.config)' in inspect.getsource(
        mod.MetaDGTF._refresh_settlement)
_I["refresh_passes_empty"] = \
    'coverage_parts(self.pools["1"], {})' in inspect.getsource(
        mod.MetaDGTF._refresh_settlement)
for _k, _v in _I.items():
    print(f"   {_k} = {_v!r}")
REPORT["I"] = _I


# ======================================================================
# [J] F11 · 收尾二次 _quality_check 会不会多写一份诊断
# ======================================================================
_sec("[J] F11 · 收尾二次 _quality_check 会不会多写一份诊断")
_J = {}
_ATT = {"in_round": 0, "in_finalize": 0, "qc_calls": 0, "qc_wdiag_false": 0,
        "in_finalize_flag": False}
_orig_fin = mod.MetaDGTF._finalize_layer_common
_orig_dump = mod.DGTF._dump_position_diagnostic
_orig_qc11 = mod.DGTF._quality_check


def _fin_wrap(self, entry, view, state):
    _ATT["in_finalize_flag"] = True
    try:
        return _orig_fin(self, entry, view, state)
    finally:
        _ATT["in_finalize_flag"] = False


def _dump_wrap(self, *a, **k):
    _ATT["in_finalize" if _ATT["in_finalize_flag"] else "in_round"] += 1
    return _orig_dump(self, *a, **k)


def _qc_wrap(self, *a, **k):
    _ATT["qc_calls"] += 1
    if k.get("write_diag") is False:
        _ATT["qc_wdiag_false"] += 1
    return _orig_qc11(self, *a, **k)


mod.MetaDGTF._finalize_layer_common = _fin_wrap
mod.DGTF._dump_position_diagnostic = _dump_wrap
mod.DGTF._quality_check = _qc_wrap
try:
    _osd = os.environ.get("SMOKE_SAVE_DIR")
    # ★ 用**每次唯一**的目录：沙箱里 shutil.rmtree 会被拒（safe-delete），
    #   固定目录会跨进程累积，把上一轮的旧文件算进来。
    _drun = Path(tempfile.mkdtemp(prefix="probe71_run_"))
    os.environ["SMOKE_SAVE_DIR"] = str(_drun)
    _packed_run()
    _J["run_dump_attempts"] = dict(_ATT)
    _J["run_diag_files"] = len(list(_drun.glob("diagnostic_position_*.log")))
    if _osd is None:
        os.environ.pop("SMOKE_SAVE_DIR", None)
    else:
        os.environ["SMOKE_SAVE_DIR"] = _osd
except Exception as _e:
    _J["run_exc"] = f"{type(_e).__name__}: {_e}"
finally:
    mod.MetaDGTF._finalize_layer_common = _orig_fin
    mod.DGTF._dump_position_diagnostic = _orig_dump
    mod.DGTF._quality_check = _orig_qc11
_J["finalize_passes_write_diag_false"] = \
    "write_diag=False" in inspect.getsource(mod.MetaDGTF._finalize_layer_common)
for _k, _v in _J.items():
    print(f"   {_k} = {_v!r}")
print("   ↑ 文件数会被**秒级时间戳撞名**吃掉，所以判据取 dump **尝试次数**："
      "in_finalize 必须为 0")
REPORT["J"] = _J


# ======================================================================
# [K] F8 · 模块级 auto_plan 与方法级 _auto_plan 的一致性
# ======================================================================
_sec("[K] F8 · 两份调度实现在同一输入下的 mode / rounds")
_K = {}


class _StubLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, *a, **k):
        self.calls += 1
        return json.dumps(self.payload, ensure_ascii=False)

    def parse_json(self, raw):
        return json.loads(raw)


def _compare(rounds_in, mode_in="G", conf=0.8, meta_cls=None):
    _cls = meta_cls or mod.MetaDGTF
    _m = _cls(CFG)
    _m.llm = _StubLLM({"mode": mode_in, "rounds": dict(rounds_in),
                       "reason": "probe", "confidence": conf})
    _p1 = _m._auto_plan("探针题：该怎么跑")
    _stub2 = _StubLLM({"route": "full", "mode": mode_in,
                       "rounds": dict(rounds_in), "max_calls": 0,
                       "reason": "probe", "confidence": conf})
    _orig_LLM = mod.LLM
    mod.LLM = lambda cfg: _stub2
    try:
        _p2 = mod.plan_resources("探针题：该怎么跑", "decision", CFG)
    finally:
        mod.LLM = _orig_LLM
    _route = _p2["route"]
    _r2 = {k: v for k, v in _p2["rounds"].items() if k in _route}
    return {"method_mode": _p1["mode"], "method_rounds": _p1["rounds"],
            "module_mode": _p2["mode"], "module_rounds": _r2,
            "agree": (_p1["mode"] == _p2["mode"]
                      and _p1["rounds"] == _r2)}


for _tag, _rin in (("full_4keys", {"0": 3, "1": 7, "both": 4, "all": 6}),
                   ("partial_2keys", {"0": 5, "1": 5}),
                   ("out_of_range", {"0": 1, "1": 99, "both": 2, "all": 2})):
    _K[_tag] = _compare(_rin)
    print(f"   {_tag:14s} 方法 {_K[_tag]['method_mode']}/{_K[_tag]['method_rounds']}"
          f"  模块 {_K[_tag]['module_mode']}/{_K[_tag]['module_rounds']}"
          f"  一致={_K[_tag]['agree']}")


class _DriftMeta(mod.MetaDGTF):
    """负对照：模拟「两份实现漂移」—— 方法级那份的钳制被人改坏。"""

    def _auto_plan(self, question):
        _r = super()._auto_plan(question)
        _r = dict(_r)
        _r["rounds"] = {k: v + 1 for k, v in (_r.get("rounds") or {}).items()}
        return _r


_K["drift_negative_control"] = _compare({"0": 3, "1": 7, "both": 4, "all": 6},
                                        meta_cls=_DriftMeta)
print(f"   负对照（人为把方法级的圈数改坏）一致="
      f"{_K['drift_negative_control']['agree']}"
      f"  ← 必须为 False，否则这条判据没有判别力")
REPORT["K"] = _K


print("\n" + "=" * 66)
print("## 摘要（机器可读）")
print("=" * 66)
print(json.dumps(REPORT, ensure_ascii=False, indent=1, default=str))
