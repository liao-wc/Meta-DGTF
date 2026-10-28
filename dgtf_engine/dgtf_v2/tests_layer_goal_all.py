# -*- coding: utf-8 -*-
"""四层目标读数的四层契约判据（V2.2.14，静态 + 动态变异体 + 真实产物回验）。

与 tests_layer_goal.py 的分工
----------------------------
tests_layer_goal.py 钉的是「修行层 2pt 口径 + 未测出原因 + 落盘出口」这一批
V2.2.12 修复点。本文件钉的是**四层都要有 verdict 出口**这件事本身：

  A. 四层读数出口：_LG_KEYS / _LG_LABELS 四层齐；layer_goal_readings 对完整
     夹具四层都出主读数，且数值可由物理量复算（0: Heaps 2pt / 1: answered/total /
     both: 新层面/上游层 / all: 四件事留痕）。
  B. 四层方向/阈值：用引擎自己的 layer_goal_stop_signal 验证读数方向
     （excavate 越小越接近挖尽；settle/fuse/crystallize 越大越好）。
  C. _lg_unmeasured_why 四层分支覆盖：每层给**层专属**的可指认原因（非空、
     非「未知」、四层互不相同）。
  D. verdict 渲染出口：从引擎源码抽取「目标读数收尾刷新」块，包成函数后对四层
     夹具渲染：非空 / 含中文层标签 / 含主读数键 / 有值给值 / 未测出给原因 /
     四层输出互不相同。**不改引擎源码，只读抽取**。
  E. 落盘出口：view.to_dict 里 goal_verdict / goal_now 两个出口点名存在；
     _layer_goal_now 写 goal_now 并 append goal_trace。
  F. 变异体（动态，在内存里改函数体后 exec，不落盘）：
     F1 删 layer_goal_readings 的某一层分支 => 该层读数契约必红（四层各一次）；
     F2 删 _LG_KEYS 的某一层 key => 该层 verdict 丢掉主读数键（四层各一次）；
     F3 删 _LG_LABELS 的某一层标签 => 该层 verdict 丢中文层名（四层各一次）；
     F4 把 _lg_unmeasured_why 的某一层分支改死 => 该层原因退化成兜底（四层各一次）；
     F5 把 _lg_unmeasured_why 改成 return "" => 渲染出「未测出（）」契约必红。
  G. 真实产物回验（V2.2.12+）：跑过的层 verdict 恒非空、goal_now 落盘、
     goal_now 与离线复算一致、未测出原因非空。
  H. 有牙自检：被测函数/源码块抽不出来 => 直接判红（判据没在测东西不许假绿）。

本文件不写任何文件、不起子进程、零 API 零 GPU。退出码 0 = 全绿；1 = 有判红。
"""
from __future__ import annotations

import copy
import glob
import importlib.util
import json
import pathlib
import re
import sys
from types import SimpleNamespace

V2 = pathlib.Path(__file__).resolve().parent
ROOT = V2.parent.parent
ENG = V2 / "engine"
sys.path.insert(0, str(ENG.parent))

PASS: list[str] = []
FAIL: list[str] = []


def ck(n, ok, info=""):
    (PASS if ok else FAIL).append(n)
    print(("✓ " if ok else "✗ ") + n + (("  — " + str(info)) if info else ""))


def _deep_same(a, b, tol: float = 1e-9) -> bool:
    """读数一致性比较：float 容差；None/缺失严格区分（未测不等于 0）。"""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(_deep_same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_deep_same(x, y, tol)
                                        for x, y in zip(a, b))
    fa = _mod._lg_num(a) if "_mod" in globals() else None
    fb = _mod._lg_num(b) if "_mod" in globals() else None
    if fa is not None and fb is not None:
        return abs(fa - fb) <= tol
    return a == b


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
VT = tuple(int(x) for x in re.search(r"V(\d+)\.(\d+)\.(\d+)", PATH.name).groups())
print("   被测引擎：%s" % PATH.name)

_spec = importlib.util.spec_from_file_location("_eng_layer_goal_all", PATH)
_mod = importlib.util.module_from_spec(_spec)
# dataclass/typing 内省需要模块先注册（同 tests_layer_goal.py 的既有做法）。
sys.modules["_eng_layer_goal_all"] = _mod
try:
    _spec.loader.exec_module(_mod)
except Exception as e:  # noqa: BLE001
    raise SystemExit("❌ 引擎导入失败（判据无法运行）：%s: %s"
                     % (type(e).__name__, e))
SRC_TEXT = PATH.read_text(encoding="utf-8", errors="replace")
SRC_LINES = SRC_TEXT.splitlines()

LAYERS = ("0", "1", "both", "all")
LG_KEYS = getattr(_mod, "_LG_KEYS", {})
LG_LABELS = getattr(_mod, "_LG_LABELS", {})
_readings = getattr(_mod, "layer_goal_readings", None)
_margin = getattr(_mod, "_lg_aspect_margin", None)
_why = getattr(_mod, "_lg_unmeasured_why", None)
_stop = getattr(_mod, "layer_goal_stop_signal", None)

ck("T0 有牙自检：四层读数/未测出/停因判据四个函数都能从引擎抠出来",
   _readings is not None and _margin is not None and _why is not None
   and _stop is not None,
   "readings=%s margin=%s why=%s stop=%s"
   % (_readings is not None, _margin is not None, _why is not None,
      _stop is not None))

# ============================ 夹具（四层各一份） ============================
FIXTURE = {
    "0": {"aspect_hist": [10, 12], "aspect_units": [{"id": "A%d" % i}
                                                     for i in range(1, 13)],
          "rounds_run": 2, "divergence": {"state": "收敛"}},
    "1": {"settlement": {"answered": 3, "total": 4}, "rounds_run": 2,
          "divergence": {"state": "收敛"}},
    "both": {"duel_suspensions": [{"target": "t1"}, {"target": "t2"}],
             "belief_items": [{"target": "t3"}], "upstream_layers": 5,
             "upstream_texts": ["完全无关的上游文本甲", "乙"],
             "rounds_run": 2},
    "all": {"meta_closure": {"clean": True, "total": 2},
            "engagements": [{"e": 1}], "suspensions": [{"s": 1}],
            "rounds_run": 2},
}
EXPECT = {"0": 0.2, "1": 0.75, "both": 0.6, "all": 1.0}
UNMEAS = {
    "0": {"aspect_hist": [0, 0], "aspect_units": [], "rounds_run": 2},
    "1": {"settlement": {"answered": 0, "total": 0}, "rounds_run": 2},
    "both": {"upstream_layers": 0, "rounds_run": 2},
}
WHY_TOKEN = {"0": "累计", "1": "子问题", "both": "上游层面", "all": "结晶"}


def readings_violations(r: dict, L: str) -> list:
    """四层读数出口契约：该层必须有主读数键且数值可由夹具复算。"""
    out = []
    if L not in (r or {}):
        return ["缺该层读数出口"]
    d = r.get(L) or {}
    k = LG_KEYS.get(L)
    if not k:
        return ["_LG_KEYS 缺该层主读数键"]
    if k not in d:
        return ["读数明细缺主读数键 %s" % k]
    v = d.get(k)
    if v is None:
        return ["主读数 %s 为 None（完整夹具应可测）" % k]
    if abs(float(v) - EXPECT[L]) > 1e-9:
        out.append("主读数 %s=%s 与复算期望 %s 不符" % (k, v, EXPECT[L]))
    req = {"0": ["excavate_basis", "n_hist", "n_aspects"],
           "1": ["settle", "non_degenerate"],
           "both": ["n_new", "n_upstream"],
           "all": ["crystallize", "n_hits", "crystallize_detail"]}[L]
    miss = [x for x in req if x not in d]
    if miss:
        out.append("缺依据字段：%s" % miss)
    return out


# ========================= A. 四层读数出口 =========================
ck("A1 _LG_KEYS 四层齐且键名与用户战略指令一致",
   set(LG_KEYS) == set(LAYERS)
   and LG_KEYS.get("0") == "excavate" and LG_KEYS.get("1") == "settle"
   and LG_KEYS.get("both") == "fuse"
   and LG_KEYS.get("all") == "crystallize",
   str(LG_KEYS))
ck("A2 _LG_LABELS 四层齐且标签非空、互不相同",
   set(LG_LABELS) == set(LAYERS)
   and all(str(LG_LABELS.get(L) or "").strip() for L in LAYERS)
   and len(set(LG_LABELS.values())) == 4,
   str(LG_LABELS))
if _readings:
    _r = _readings(FIXTURE)
    for L in LAYERS:
        vs = readings_violations(_r, L)
        ck("A3.%s 四层读数出口：%s 层主读数可复算（%s=%s）"
           % (L, L, LG_KEYS.get(L), EXPECT[L]), not vs, vs)
else:
    ck("A3 四层读数出口", False, "layer_goal_readings 缺失")

# ========================= B. 四层方向/阈值 =========================
if _stop:
    hit, _ = _stop("0", {"excavate": 0.05, "n_aspects": 3})
    ck("B1 修行层方向：excavate=0.05 < 0.10 ⇒ 判「挖尽」", hit,
       "hit=%s" % hit)
    hit, _ = _stop("0", {"excavate": 0.50, "n_aspects": 3})
    ck("B2 修行层方向：excavate=0.50 >= 0.10 ⇒ 不判挖尽", not hit,
       "hit=%s" % hit)
    flat3 = [{"settle": 0.8}, {"settle": 0.8}, {"settle": 0.8}]
    hit, _ = _stop("1", {"settle": 0.8}, flat3)
    ck("B3 研究层方向：settle 连续 2 圈不涨 ⇒ 判「收敛」", hit, "hit=%s" % hit)
    hit, _ = _stop("1", {"settle": 0.9},
                   [{"settle": 0.8}, {"settle": 0.8}, {"settle": 0.9}])
    ck("B4 研究层方向：settle 仍在涨 ⇒ 不判收敛", not hit, "hit=%s" % hit)
    hit, _ = _stop("both", {"fuse": 0.5},
                   [{"fuse": 0.5}, {"fuse": 0.5}, {"fuse": 0.5}])
    ck("B5 对撞层方向：fuse 连续 2 圈不涨 ⇒ 判融合收敛", hit, "hit=%s" % hit)
    hit, why = _stop("both", {"fuse": 0.9, "sem_stagnation": 0.9})
    ck("B6 对撞层停因受阻：sem_stagnation>=0.8 ⇒ 判「受阻」而非达成",
       hit and "受阻" in str(why), str(why)[:80])
    hit, _ = _stop("all", {"crystallize": 1.0})
    ck("B7 元层方向：crystallize=1.0（四件齐）⇒ 判「结晶完成」", hit,
       "hit=%s" % hit)
    hit, _ = _stop("all", {"crystallize": 0.5})
    ck("B8 元层方向：crystallize=0.5 ⇒ 不判完成", not hit, "hit=%s" % hit)
else:
    ck("B 四层方向/阈值", False, "layer_goal_stop_signal 缺失")

# =================== C. _lg_unmeasured_why 四层分支覆盖 ===================
WHY_FEEDS = {
    "0": {"n_hist": 2, "n_aspects": 0},
    "1": {"non_degenerate": False},
    "both": {"n_upstream": 0, "n_new": 0},
    "all": {"n_hits": 2},
}
if _why:
    _whys = {}
    for L in LAYERS:
        got = str(_why(L, WHY_FEEDS[L]) or "").strip()
        _whys[L] = got
        ck("C.%s 未测出原因覆盖 %s 层分支（含层专属词「%s」）"
           % (L, L, WHY_TOKEN[L]),
           bool(got) and WHY_TOKEN[L] in got and "未知" not in got, got)
    ck("C5 四层原因是**层专属**的（不是同一句兜底）",
       len(set(_whys.values())) == 4, str(_whys))
    ck("C6 未测出原因不含占位式空括号/未知",
       all("（）" not in v and "未知" not in v for v in _whys.values()),
       str(_whys))
    ck("C7 元层两种未测出原因可区分（四件缺几件 vs 全无产物）",
       "2/4" in str(_why("all", {"n_hits": 2}))
       and "均无产物" in str(_why("all", {"n_hits": 0})),
       "%s | %s" % (_why("all", {"n_hits": 2}), _why("all", {"n_hits": 0})))
else:
    ck("C 未测出原因四层覆盖", False, "_lg_unmeasured_why 缺失")

# ============== D. verdict 渲染出口（源码抽取，不改引擎文件） ==============
def _render_block_text(src_lines: list):
    """把「目标读数收尾刷新」try 块抽成 def _lg_render(view, entry): 源码。"""
    idx = next((i for i, ln in enumerate(src_lines)
                if "_vd_f = view.to_dict()" in ln), None)
    if idx is None:
        return None
    start = next((j for j in range(idx, -1, -1)
                  if src_lines[j].strip() == "try:"), None)
    if start is None:
        return None
    k = next((i for i in range(idx, len(src_lines))
              if "_lg_unmeasured_why(str(entry), _fresh))" in src_lines[i]),
             None)
    if k is None:
        return None
    end = next((j for j in range(k, len(src_lines))
                if src_lines[j].strip() == "except Exception:"), None)
    if end is None or end + 1 >= len(src_lines) \
            or src_lines[end + 1].strip() != "pass":
        return None
    block = [(ln[4:] if ln.startswith("    ") else ln)
             for ln in src_lines[start:end + 2]]
    return "def _lg_render(view, entry):\n" + "\n".join(block) + "\n"


def _extract_render(src_lines: list):
    """抽取渲染块并在**引擎模块命名空间**里编译成函数（不改引擎文件）。"""
    text = _render_block_text(src_lines)
    if text is None:
        return None
    ns = dict(vars(_mod))
    try:
        exec(compile(text, "<extracted_render>", "exec"), ns)  # noqa: S102
    except Exception as e:  # noqa: BLE001
        print("   抽取块编译失败：%s: %s" % (type(e).__name__, e))
        return None
    return ns.get("_lg_render")


_render = _extract_render(SRC_LINES)
ck("D0 有牙自检：能从引擎源码抽出 verdict 收尾渲染块并包成函数",
   _render is not None)


def render_violations(render_fn, L: str, view_dict: dict) -> list:
    """verdict 渲染契约：非空 / 含层标签 / 含主读数键 / 值或原因合法。"""
    out = []
    fake = SimpleNamespace(to_dict=lambda: view_dict)
    try:
        render_fn(fake, L)
    except Exception as e:  # noqa: BLE001
        return ["渲染异常：%s: %s" % (type(e).__name__, e)]
    gv = str(getattr(fake, "goal_verdict", "") or "")
    gn = getattr(fake, "goal_now", None) or {}
    k = LG_KEYS.get(L)
    label = LG_LABELS.get(L)
    if not gv.strip():
        out.append("verdict 空（跑了必有说法）")
        return out
    if not gv.startswith("本层目标（"):
        out.append("verdict 前缀不合契约")
    if label and label not in gv:
        out.append("verdict 缺中文层标签 %s" % label)
    if k and ("%s=" % k) not in gv:
        out.append("verdict 缺主读数键 %s=" % k)
    if k and not isinstance(gn, dict):
        out.append("goal_now 未落盘")
    elif k and k not in gn:
        out.append("goal_now 缺主读数键")
    main = _mod._lg_num(gn.get(k)) if isinstance(gn, dict) else None
    if "=未测出（" in gv:
        why = gv.split("=未测出（", 1)[1]
        why = why[:-1] if why.endswith("）") else why
        if not why.strip() or why.strip() in ("未知", "依据不足"):
            out.append("未测出原因不可指认：%r" % why)
        if main is not None:
            out.append("verdict 说未测出但 goal_now 有数值 %s" % main)
    else:
        m = re.search(r"=(-?\d+(?:\.\d+)?)", gv)
        if not m:
            out.append("有值形态缺数值")
        elif main is None or abs(float(m.group(1)) - main) > 5e-4:
            out.append("verdict 数值 %s 与 goal_now %s 不同源"
                       % (m.group(1) if m else None, main))
    return out


if _render:
    _gvs = {}
    for L in LAYERS:
        vs = render_violations(_render, L, FIXTURE[L])
        ck("D1.%s verdict 有值形态渲染契约（%s 层）" % (L, L), not vs, vs)
        fake = SimpleNamespace(to_dict=lambda: FIXTURE[L])
        _render(fake, L)
        _gvs[L] = str(getattr(fake, "goal_verdict", ""))
    ck("D2 四层 verdict 文本互不相同（层语义未被抹平）",
       len(set(_gvs.values())) == 4, str(_gvs))
    for L in ("0", "1", "both"):
        vs = render_violations(_render, L, UNMEAS[L])
        ck("D3.%s verdict 未测出形态渲染契约（%s 层，原因可指认）"
           % (L, L), not vs, vs)
    # 元层 crystallize 恒可算（0.0 也是「测出来是 0」）——未测出分支在
    # verdict 通道不可达；这里钉住「0.0 必须走有值形态而不是伪装未测出」。
    vs = render_violations(_render, "all",
                           {"engagements": [], "suspensions": []})
    ck("D4 元层零留痕 ⇒ crystallize=0.000（测出来是 0，不冒充未测出）",
       not vs, vs)
else:
    ck("D1 四层 verdict 渲染", False, "渲染块抽取失败")

# ================== E. 落盘出口 / goal_trace 出口点名 ==================
ck("E1 ★ view.to_dict 有 goal_verdict 落盘出口",
   'd["goal_verdict"] = str(self.goal_verdict)' in SRC_TEXT)
ck("E2 ★ view.to_dict 有 goal_now 落盘出口",
   'd["goal_now"] = dict(self.goal_now)' in SRC_TEXT)
ck("E3 ★ _layer_goal_now 写 goal_now 并 append goal_trace"
   "（逐圈留痕的唯一写入点）",
   "view.goal_now = dict(_d)" in SRC_TEXT
   and "_h.append(_rec)" in SRC_TEXT
   and "view.goal_trace = list(_h)" in SRC_TEXT)
ck("E4 ★ goal_verdict 有值/未测出两个出口都点名存在（不是只写有值）",
   "本层目标（%s）：%s=%.3f%s" in SRC_TEXT
   and "_lg_unmeasured_why(str(entry), _fresh)" in SRC_TEXT)


# ===================== F. 变异体（动态，必红证明） =====================
def _extract_func(name: str):
    start = None
    for i, ln in enumerate(SRC_LINES):
        if ln.startswith("def %s(" % name):
            start = i
            break
    if start is None:
        return None
    end = len(SRC_LINES)
    for j in range(start + 1, len(SRC_LINES)):
        if SRC_LINES[j].strip() and not SRC_LINES[j][0].isspace():
            end = j
            break
    return "\n".join(SRC_LINES[start:end])


def _exec_in(name: str, text: str, ns: dict):
    loc: dict = {}
    exec(compile(text, "<mutant:%s>" % name, "exec"), ns, loc)  # noqa: S102
    return loc.get(name)


_ns_base = dict(vars(_mod))
_src_readings = _extract_func("layer_goal_readings")
_src_why = _extract_func("_lg_unmeasured_why")
ck("F0 有牙自检：待变异函数源码抽取成功",
   bool(_src_readings) and bool(_src_why))

if _src_readings and _readings:
    for L in LAYERS:
        marker = '%s L == "%s":' % ("if" if L == "0" else "elif", L)
        if marker not in _src_readings:
            ck("F1.%s 变异体可定位 %s 层读数分支" % (L, L), False, marker)
            continue
        mut_src = _src_readings.replace(marker, marker.replace(L, "__dead__"), 1)
        ns = dict(_ns_base)
        mut = _exec_in("layer_goal_readings", mut_src, ns)
        if mut is None:
            ck("F1.%s 变异体编译" % L, False)
            continue
        try:
            r_mut = mut(FIXTURE)
        except Exception as e:  # noqa: BLE001
            ck("F1.%s 删 %s 层读数分支 ⇒ 真判据必红" % (L, L), True,
               "变异体已炸（%s）—— 说明该分支承重" % type(e).__name__)
            continue
        vs = readings_violations(r_mut, L)
        ck("F1.%s ★ 删 %s 层读数分支 ⇒ 四层读数契约必红（该层读数消失）"
           % (L, L), bool(vs), str(vs)[:120])

if _render:
    for L in LAYERS:
        # F2：删 _LG_KEYS 的某一层 key ⇒ 该层 verdict 丢掉主读数键。
        ns = dict(_ns_base)
        ns["_LG_KEYS"] = {k: v for k, v in LG_KEYS.items() if k != L}
        mut_render = _exec_in("_lg_render", _render_block_text(SRC_LINES), ns)
        if mut_render is None:
            ck("F2.%s 渲染变异体编译" % L, False)
        else:
            vs = render_violations(mut_render, L, FIXTURE[L])
            ck("F2.%s ★ 删 _LG_KEYS 的 %s 层出口 ⇒ verdict 契约必红"
               "（缺主读数键）" % (L, L),
               bool(vs) and any("主读数键" in x for x in vs), str(vs)[:120])
        # F3：删 _LG_LABELS 的某一层标签 ⇒ 该层 verdict 丢掉中文层名。
        ns = dict(_ns_base)
        ns["_LG_LABELS"] = {k: v for k, v in LG_LABELS.items() if k != L}
        mut_render = _exec_in("_lg_render", _render_block_text(SRC_LINES), ns)
        if mut_render is None:
            ck("F3.%s 渲染变异体编译" % L, False)
        else:
            vs = render_violations(mut_render, L, FIXTURE[L])
            ck("F3.%s ★ 删 _LG_LABELS 的 %s 层标签 ⇒ verdict 契约必红"
               "（缺中文层标签）" % (L, L),
               bool(vs) and any("中文层标签" in x for x in vs), str(vs)[:120])

if _src_why and _why:
    for L in LAYERS:
        marker = 'if _e == "%s":' % L
        if marker not in _src_why:
            ck("F4.%s 变异体可定位 %s 层原因分支" % (L, L), False, marker)
            continue
        mut_src = _src_why.replace(marker,
                                   'if _e == "__dead_%s__":' % L, 1)
        ns = dict(_ns_base)
        mut = _exec_in("_lg_unmeasured_why", mut_src, ns)
        if mut is None:
            ck("F4.%s 变异体编译" % L, False)
            continue
        got = str(mut(L, WHY_FEEDS[L]) or "").strip()
        bad = (not got) or WHY_TOKEN[L] not in got or "未知" in got
        ck("F4.%s ★ 把 %s 层未测出原因分支改死 ⇒ 层专属原因契约必红"
           % (L, L), bad, repr(got))
    # F5：整体 return ""（任务要求「让某层 return 空串 ⇒ 必红」的极端形态）
    ns = dict(_ns_base)
    mut_empty = _exec_in(
        "_lg_unmeasured_why",
        "def _lg_unmeasured_why(entry, d):\n    return \"\"\n", ns)
    render_text = _render_block_text(SRC_LINES)
    render_broken = None
    if mut_empty is not None and render_text is not None:
        ns2 = dict(_ns_base)
        ns2["_lg_unmeasured_why"] = mut_empty
        try:
            render_broken = _exec_in("_lg_render", render_text, ns2)
        except Exception as e:  # noqa: BLE001
            print("   F5 变异体编译失败：%s: %s" % (type(e).__name__, e))
    bad = False
    detail = "构造失败（why 变异体或渲染块缺失）"
    if mut_empty is not None and render_broken is not None:
        fake = SimpleNamespace(to_dict=lambda: UNMEAS["0"])
        try:
            render_broken(fake, "0")
            gv = str(getattr(fake, "goal_verdict", ""))
            bad = ("未测出（）" in gv) or not gv.strip()
            detail = gv[:80]
        except Exception as e:  # noqa: BLE001
            bad, detail = True, "%s: %s" % (type(e).__name__, e)
    ck("F5 ★ 把未测出原因函数改成 return 空串 ⇒ 渲染契约必红"
       "（出「未测出（）」）", bad, detail)

# ===================== G. 真实产物回验（V2.2.12+） =====================
V_GOALNOW = (2, 2, 12)
_pack_dirs = [str(ROOT / "outputs"), str(ROOT / "outputs" / "_e2e_local")]
_new, _bad, _recent = [], [], []
_zero_packs = []
for pat in _pack_dirs:
    for f in glob.glob(str(pathlib.Path(pat) / "*.packed.json")):
        try:
            d = json.loads(pathlib.Path(f).read_text(encoding="utf-8",
                                                     errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", pv)
        if not m or tuple(int(x) for x in m.groups()) < V_GOALNOW:
            continue
        _recent.append(d)
        if d.get("llm_calls") == 0 and any(
                isinstance(v, dict) and v.get("rounds_run")
                for v in (d.get("views") or {}).values()):
            _zero_packs.append(d)
        name = pathlib.Path(f).name
        for L, v in (d.get("views") or {}).items():
            if not isinstance(v, dict) or not v.get("rounds_run"):
                continue
            _new.append("%s::%s" % (name[:34], L))
            if not str(v.get("goal_verdict") or "").strip():
                _bad.append("%s::%s verdict 空" % (name[:34], L))
            gn = v.get("goal_now")
            if not isinstance(gn, dict) or not gn:
                _bad.append("%s::%s goal_now 缺" % (name[:34], L))
                continue
            gv = str(v.get("goal_verdict") or "")
            if "=未测出（" in gv and "未测出（）" in gv:
                _bad.append("%s::%s 未测出原因为空" % (name[:34], L))
            if _readings:
                try:
                    fresh = (_readings({L: v}).get(L) or {})
                except Exception:  # noqa: BLE001
                    fresh = None
                if fresh is not None and not _deep_same(gn, fresh):
                    _bad.append("%s::%s goal_now 与离线复算不一致"
                                % (name[:34], L))
if _new:
    ck("G1 有牙自检：存在 V2.2.12+ 跑过层的产物（否则 G2 恒绿 = 没判据）",
       len(_new) >= 1, "%d 个层实例" % len(_new))
    ck("G2 ★ 真实产物：V2.2.12+ 跑过的层 verdict 恒非空、goal_now 恒落盘、"
       "未测出恒有原因、读数可离线复算", not _bad, _bad[:6])
else:
    print("· SKIP G 真实产物回验：没有 V2.2.12+ 的 packed（干净 checkout）")


def zero_llm_violations(d: dict) -> list:
    """零 LLM 产物判据：跑过的层不许判达成、未测出必须有可指认原因。

    12:55 shim 死掉那类跑次必须能被读成「没跑通」，不能被读成
    「模型能力不足 / 挖尽」。返回违规列表（空 = 合规）。
    """
    bad = []
    if d.get("llm_calls") != 0:
        return bad
    for L, v in (d.get("views") or {}).items():
        if not isinstance(v, dict) or not v.get("rounds_run"):
            continue
        gv = str(v.get("goal_verdict") or "").strip()
        if not gv:
            bad.append("%s 层 verdict 空（零 LLM 也必须有说法）" % L)
            continue
        if "=未测出（" in gv:
            why = gv.split("=未测出（", 1)[1]
            why = why[:-1] if why.endswith("）") else why
            if not why.strip() or "未知" in why:
                bad.append("%s 层未测出原因不可指认：%r" % (L, why[:40]))
        if _stop:
            try:
                hit, _ = _stop(L, dict(v.get("goal_now") or {}),
                               list(v.get("goal_trace") or []))
            except Exception:  # noqa: BLE001
                hit = False
            if hit:
                bad.append("%s 层零 LLM 却判「达成」（没调用就没证据）" % L)
    return bad


if _zero_packs:
    _zv = [b for d in _zero_packs for b in zero_llm_violations(d)]
    ck("G3 ★ 零 LLM 产物判据（真实产物）：%d 个零 LLM 跑次里，跑过的层"
       "verdict 有说法、未测出有原因、无「达成」" % len(_zero_packs),
       not _zv, _zv[:5])
    # G4 有牙：把零 LLM 产物伪造成「修行层挖尽」⇒ 判据必须报违规。
    _zm = copy.deepcopy(_zero_packs[0])
    _found = False
    for L, v in ((_zm.get("views") or {})).items():
        if L != "0" or not isinstance(v, dict) or not v.get("rounds_run"):
            continue
        gn = v.setdefault("goal_now", {})
        if not isinstance(gn, dict):
            gn = {}
            v["goal_now"] = gn
        gn.update({"excavate": 0.0, "excavate_closed": 1.0,
                   "excavate_basis": "2pt", "n_aspects": 3, "n_hist": 2})
        v["goal_verdict"] = ("本层目标（修行·挖尽）：excavate=0.000"
                             "（边际新增率·趋零即挖尽）")
        _found = True
        break
    ck("G4 ★ 零 LLM 判据有牙：伪造成「修行层挖尽」⇒ 必红",
       _found and bool(zero_llm_violations(_zm)),
       zero_llm_violations(_zm)[:3] if _found else "没有可伪造的零 LLM layer0")
else:
    print("· SKIP G3/G4 零 LLM 产物判据：没有 V2.2.12+ 的零 LLM packed")

# =============================== 汇总 ===============================
print("─" * 60)
print("%d/%d 通过" % (len(PASS), len(PASS) + len(FAIL))
      + ("，%d 项判红" % len(FAIL) if FAIL else ""))
if FAIL:
    print("失败：", FAIL[:12])
    raise SystemExit(1)
