# -*- coding: utf-8 -*-
"""四层目标读数的**可达性**判据（V2.2.12）。

缺陷（实测 213 个产物包普查）
----------------------------
层          跑了     verdict空   值分布
修行(0)     213      211        0.000/0.000/0.000, n=2
研究(1)     211      19         0.333/1.000/1.000, n=192
对撞(both)  198      2          0.036/0.622/0.940, n=196
元(all)     198      0          0.500/1.000/1.000 → 195 个 1.000

根因（修行层为主）：
  · `_lg_aspect_margin` 要求 ≥3 个逐圈点，默认 soft_max=2 圈只给 2 点
    ⇒ 读数**结构性**为 None ⇒ verdict 空。
  · docstring 承诺的 `1/(1+total)` 单点估计从未实现（total 被忽略）。
  · verdict 空时无法区分「算不出」与「没算」（goal_now 无落盘出口）。
  · 元层「四件事非空即满分」⇒ 195/198=1.000，零区分度。

本判据要钉住的五件事
--------------------
A. 纯函数 `_lg_aspect_margin`：2pt 口径（恰 2 点）+ 诚实 None（0/1 点、V1=0）
B. `layer_goal_readings`：修行层带 `excavate_basis`/`n_hist`；元层带量
C. `_lg_unmeasured_why`：每层给**可指认**的未测出原因（非空、含具体数字）
D. 静态：verdict 未测出分支 + goal_now 落盘出口**点名存在**（+ 变异体）
E. 真实产物回验：V2.2.12+ 的包里，跑过的层 verdict 恒非空（有值或未测出）
"""
from __future__ import annotations

import glob
import importlib.util
import json
import pathlib
import re
import sys

V2 = pathlib.Path(__file__).resolve().parent
ROOT = V2.parent.parent          # dgtf_v2 -> dgtf_engine -> 仓库根
ENG = V2 / "engine"
sys.path.insert(0, str(ENG.parent))

PASS: list[str] = []
FAIL: list[str] = []


def ck(n, ok, info=""):
    (PASS if ok else FAIL).append(n)
    print(("✓ " if ok else "✗ ") + n + (("  — " + str(info)) if info else ""))


def _latest():
    vs = []
    for p in ENG.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            vs.append((tuple(int(x) for x in m.groups()), p))
    if not vs:
        raise SystemExit("❌ 找不到引擎文件")
    return sorted(vs)[-1][1]


PATH = _latest()
VER = tuple(int(x) for x in re.search(r"V(\d+)\.(\d+)\.(\d+)", PATH.name).groups())
print(f"   被测引擎：{PATH.name}")

# 整模块导入拿纯函数（系统 python 有 openai；fast_gate 的 audit 探针
# 已经这么导过引擎文件，无重副作用）。★ 不走手工 exec 抠函数 ——
# `layer_goal_readings` 依赖 `_AT_LAYERS`/`_LG_KEYS` 等一堆模块级常量，
# 手工挑依赖必漏（第一次就漏了 `_AT_LAYERS`）。
_spec = importlib.util.spec_from_file_location("_eng_under_test", PATH)
_mod = importlib.util.module_from_spec(_spec)
# ★ 必须先注册进 sys.modules 再 exec：dataclass/typing 的内省要靠
#   `sys.modules[__module__]` 找到模块字典，不注册就会炸
#   "'NoneType' object has no attribute '__dict__'"（_probe_v1232_audit
#   的既有做法，第一次没抄全）。
sys.modules["_eng_under_test"] = _mod
try:
    _spec.loader.exec_module(_mod)
except Exception as _e:  # noqa: BLE001
    raise SystemExit("❌ 引擎导入失败（判据无法运行）：%s" % _e)
_src = PATH.read_text(encoding="utf-8", errors="replace")

_marg = getattr(_mod, "_lg_aspect_margin", None)
_readings = getattr(_mod, "layer_goal_readings", None)
_why = getattr(_mod, "_lg_unmeasured_why", None)
ck("T0 有牙自检：三个被测函数都能从引擎里抠出来（否则本判据没在测东西）",
   _marg is not None and _readings is not None and _why is not None,
   "marg=%s readings=%s why=%s" % (_marg, _readings, _why))

# ───────────────── A. _lg_aspect_margin：2pt + 诚实 None ─────────────────
if _marg:
    ck("A1 [] ⇒ None（没测 ≠ 测出 0）", _marg([]) is None, repr(_marg([])))
    ck("A2 [5] ⇒ None（1 点无增益信息）", _marg([5]) is None, repr(_marg([5])))
    ck("A3 ★ [0,0] ⇒ None（没东西可挖 ≠ 已挖尽 —— 不冒充）",
       _marg([0, 0]) is None, repr(_marg([0, 0])))
    ck("A4 [0,5] ⇒ None（V1=0 相对边际无定义）",
       _marg([0, 5]) is None, repr(_marg([0, 5])))
    ck("A5 ★ [13,16] ⇒ 3/13≈0.2308（2pt 口径：ΔV/V）",
       abs((_marg([13, 16]) or -1) - 3.0 / 13.0) < 1e-9, repr(_marg([13, 16])))
    ck("A6 ★ [10,10] ⇒ 0.0（2pt 口径下「挖尽」可判 —— 此前结构性不可达）",
       _marg([10, 10]) == 0.0, repr(_marg([10, 10])))
    ck("A7 [10,12,12,12] ⇒ 0.0（halves 口径不回归）",
       _marg([10, 12, 12, 12]) == 0.0, repr(_marg([10, 12, 12, 12])))
    ck("A8 [10,20,30] ⇒ 1.0（halves 口径不回归）",
       _marg([10, 20, 30]) == 1.0, repr(_marg([10, 20, 30])))

# ───────────────── B. layer_goal_readings：basis / 带量 ─────────────────
if _readings:
    # 修行层 2 点
    r = _readings({"0": {"aspect_hist": [13, 16], "aspect_units": [1] * 16,
                         "rounds_run": 2}})
    d0 = r.get("0") or {}
    ck("B1 ★ 修行层 2 点读得出：excavate≈0.231",
       abs((d0.get("excavate") or -1) - 3.0 / 13.0) < 1e-9,
       str(d0.get("excavate")))
    ck("B2 ★ 带口径标注 excavate_basis='2pt'（消费方不与 halves 混比）",
       d0.get("excavate_basis") == "2pt", str(d0.get("excavate_basis")))
    ck("B3 带 n_hist（依据点数可见）", d0.get("n_hist") == 2, str(d0.get("n_hist")))
    # 修行层 3 点 → halves
    r3 = _readings({"0": {"aspect_hist": [10, 20, 30], "aspect_units": [1] * 30,
                          "rounds_run": 3}})
    ck("B4 3 点 ⇒ basis='halves'（老口径不回归）",
       (r3.get("0") or {}).get("excavate_basis") == "halves",
       str((r3.get("0") or {}).get("excavate_basis")))
    # 修行层 0 点 → None + basis=None
    r0 = _readings({"0": {"aspect_hist": [], "aspect_units": [1] * 5}})
    d00 = r0.get("0") or {}
    ck("B5 0 点 ⇒ excavate=None 且 basis=None（不冒充）",
       d00.get("excavate") is None and d00.get("excavate_basis") is None,
       str((d00.get("excavate"), d00.get("excavate_basis"))))
    # 元层带量
    rm = _readings({"all": {"meta_closure": {"clean": True, "total": 7},
                            "engagements": [{"t": 1}, {"t": 2}, {"t": 3}],
                            "suspensions": [{"s": 1}]}})
    dm = rm.get("all") or {}
    det = dm.get("crystallize_detail") or {}
    ck("B6 ★ 元层 crystallize_detail 带量（天花板效应下保留区分度）",
       det.get("lookback_items") == 7 and det.get("engagements") == 3
       and det.get("suspensions") == 1 and det.get("closure") is True,
       str(det))
    ck("B7 crystallize 主读数语义不变（四件全齐 ⇒ 1.0）",
       abs((dm.get("crystallize") or -1) - 1.0) < 1e-9, str(dm.get("crystallize")))
    rm2 = _readings({"all": {"meta_closure": {"clean": True, "total": 3},
                             "engagements": [{"t": 1}],
                             "suspensions": []}})
    ck("B7b crystallize 缺一件（无悬置）⇒ 3/4=0.75（不因带量子读数改变口径）",
       abs(((rm2.get("all") or {}).get("crystallize") or -1) - 0.75) < 1e-9,
       str((rm2.get("all") or {}).get("crystallize")))

# ───────────────── C. _lg_unmeasured_why：可指认原因 ─────────────────
if _why:
    cases = [
        ("0", {"n_hist": 1}, "1 点"),
        ("0", {"n_hist": 2, "n_aspects": 0}, "存量为 0"),
        ("1", {"non_degenerate": False}, "全部子问题未答"),
        ("1", {}, "无可判定子问题"),
        ("both", {"n_upstream": 0, "n_new": 5}, "上游层面=0"),
        ("all", {"n_hits": 0}, "均无产物"),
    ]
    for ent, feed, want in cases:
        got = _why(ent, feed)
        ck("C ★ %s 层未测出原因可指认（含「%s」且非空）"
           % ({"0": "修行", "1": "研究", "both": "对撞", "all": "元"}[ent], want),
           bool(got) and want in str(got), repr(got))
    ck("C7 所有层的原因都**不是空串、不是「未知」",
       all((_why(e, {}) or "").strip() and "未知" not in _why(e, {})
           for e in ("0", "1", "both", "all")),
       repr([_why(e, {}) for e in ("0", "1", "both", "all")]))

# ───────────────── D. 静态点名 + 变异体 ─────────────────
ck("D1 ★ verdict 未测出分支点名存在（`_lg_unmeasured_why(str(entry), _fresh)`）",
   _src.count("_lg_unmeasured_why(str(entry), _fresh)") == 1,
   str(_src.count("_lg_unmeasured_why(str(entry), _fresh)")))
ck("D2 ★ goal_now 落盘出口点名存在（`d[\"goal_now\"] = dict(self.goal_now)`）",
   'd["goal_now"] = dict(self.goal_now)' in _src, "")
_mut = _src.replace("                        _lg_unmeasured_why(str(entry), _fresh))\n",
                    "", 1)
ck("D3 变异体真的插进去了（删的是那一行，不是别的）",
   _mut != _src and _mut.count("_lg_unmeasured_why(str(entry), _fresh)") == 0)
ck("D4 ★ 删掉未测出分支后 D1 必须判红（证明 D1 有牙）",
   _mut.count("_lg_unmeasured_why(str(entry), _fresh)") != 1)

# ───────────────── E. 真实产物回验 ─────────────────
pack_dirs = [str(ROOT / "outputs" / "*.packed.json"),
             str(ROOT / "outputs" / "_e2e_local" / "*.packed.json")]
_new, _bad = [], []
for pat in pack_dirs:
    for f in glob.glob(pat):
        try:
            d = json.loads(pathlib.Path(f).read_text(encoding="utf-8",
                                                     errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", pv)
        if not m or tuple(int(x) for x in m.groups()) < VER:
            continue
        _new.append(pathlib.Path(f).name)
        for L, v in ((d.get("views") or {}).items()):
            if isinstance(v, dict) and v.get("rounds_run"):
                gv = str(v.get("goal_verdict") or "").strip()
                if not gv:
                    _bad.append("%s::%s" % (pathlib.Path(f).name[:30], L))
ck("E1 有牙自检：存在 V%d.%d.%d+ 产出的产物包（否则 E2 恒绿 = 没判据）"
   % VER, len(_new) >= 1, f"{len(_new)} 个：{_new[:2]}")
ck("E2 ★ 真实产物：跑过的层 goal_verdict 恒非空（有值或「未测出(原因)」）",
   not _bad, f"空 verdict：{_bad[:4]}")
# E2 的「未测出」形态必须带原因，不是光秃秃的「未测出」
_bare = []
for pat in pack_dirs:
    for f in glob.glob(pat):
        try:
            d = json.loads(pathlib.Path(f).read_text(encoding="utf-8",
                                                     errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", pv)
        if not m or tuple(int(x) for x in m.groups()) < VER:
            continue
        for L, v in ((d.get("views") or {}).items()):
            if isinstance(v, dict):
                gv = str(v.get("goal_verdict") or "")
                if "未测出（" in gv and gv.count("（") - gv.count("（未") < 0:
                    pass
                if gv.startswith("本层目标") and "=未测出" in gv \
                        and ("未测出（）" in gv or "未测出(原因)" in gv):
                    _bare.append(gv[:50])
ck("E3 「未测出」形态必须带具体原因（不是空括号占位）", not _bare,
   str(_bare[:3]))

print("─" * 60)
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} 通过"
      + (f"，{len(FAIL)} 项判红" if FAIL else ""))
if FAIL:
    print("失败：", FAIL)
    raise SystemExit(1)
