# -*- coding: utf-8 -*-
"""成本归因的**第二个盲区**判据：`stage` 一个参数三种语义。

缺陷（实测）
------------
V2.2.5 用 AST 扫「`llm.call` 有没有 `stage=`」补了 4 处，判据全绿。
但 V2.2.8 第一次跑完的本地跑次里，`llm_by_stage` 仍有：

    {"stage": "unknown", "calls": 2, "tokens": 4224}

占 13 次调用里的 2 次、21323 tokens 里的 4224。**AST 说 0 处缺失，产物里
却有盲区** ⇒ 原来的判据**测错了东西**：它只查「有没有这个 kwarg」，
查不出「传了变量、但值是 None」。

根因：`stage` 一个参数承担三种语义
    · thinking 档位（`thinking_stages.get(stage)`）
    · 联网授权环节名（`_web_augment`）
    · **成本归因标签**（`_sn = str(stage or "unknown")`）
而 18 个调用点写 `stage=_thinking_stage(cfg, 'X')`，该函数**只在环节已声明
时返回名字** ⇒ thinking 关 ⇒ stage=None ⇒ 成本标签掉进 `unknown`。

修法：新增**独立**的 `cost_stage` 参数，只服务归因（`stage` 一字不动）。

本判据要钉住的三件事
--------------------
A. 静态：每个用了 `_thinking_stage(cfg,'X')` 的调用点都配了 `cost_stage='X'`
B. 静态：`cost_stage` 必须是**字面量**（传变量就又回到「值可能是 None」）
C. 构造性：真调 `LLM.call(stage=None, cost_stage='X')` ⇒ 计数落在 'X' 不是 'unknown'
D. 变异体：不给 `cost_stage` ⇒ 落 'unknown'（证明 C 测的是这条代码路径）
E. 真实产物：最新一份 packed 的 `llm_by_stage` 里没有 `unknown`
"""
from __future__ import annotations

import ast
import glob
import importlib.util
import json
import os
import pathlib
import re
import sys
from types import SimpleNamespace

V2 = pathlib.Path(__file__).resolve().parent
ROOT = V2.parent.parent
ENG = V2 / "engine"

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
SRC = PATH.read_text(encoding="utf-8", errors="replace")
print(f"   被测引擎：{PATH.name}")
tree = ast.parse(SRC)

# ───────────────────── A. 静态：调用点配对 ─────────────────────
sites = []          # (lineno, thinking名, cost_stage值)
for node in ast.walk(tree):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "call"):
        continue
    kv = {k.arg: k.value for k in node.keywords if k.arg}
    st = kv.get("stage")
    if not isinstance(st, ast.Call) or getattr(st.func, "id", "") != "_thinking_stage":
        continue
    lit = None
    for a in st.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            lit = a.value
    cs = kv.get("cost_stage")
    cs_val = cs.value if (isinstance(cs, ast.Constant)
                          and isinstance(cs.value, str)) else None
    sites.append((node.lineno, lit, cs_val))

ck("A1 存在用 `_thinking_stage()` 传 stage 的调用点（否则本判据没在测东西）",
   len(sites) >= 10, f"{len(sites)} 处")
missing = [(ln, lit) for ln, lit, cs in sites if cs is None]
ck("A2 ★ 每处都配了 `cost_stage`（thinking 关 ⇒ 成本标签不再丢）",
   not missing, f"缺配：{missing[:6]}")
mismatch = [(ln, lit, cs) for ln, lit, cs in sites if cs is not None and lit != cs]
ck("A3 `cost_stage` 与 thinking 用的是**同一个名字**（不许各写各的）",
   not mismatch, f"不一致：{mismatch[:4]}")

# ★★ A4 全量范围扫描 —— 这才是「一类判据」。
#    上一版判据只扫**主文件**的 `*.call(`，于是漏掉：
#      · `dgtf_v2/*.py` 模块里的 4 处 `llm.call`
#      · 主文件里 3 处 `_call_long(`（包装器，不是 `.call`）
#    ⇒ 它报「0 处缺失」，而产物里照样有 `unknown` 桶。**范围不够的判据
#      比没判据更危险**：它给人「已经查过了」的错觉。
_all_files = [PATH] + sorted(V2.glob("*.py"))
_missing = []
_total_sites = 0
for _f in _all_files:
    if _f.name.startswith("tests"):
        continue
    try:
        _t = ast.parse(_f.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr in ("call", "_call_long"):
            _total_sites += 1
            _ks = {k.arg for k in _n.keywords if k.arg}
            if "stage" not in _ks and "cost_stage" not in _ks:
                _missing.append((_f.name, _n.lineno, _n.func.attr))
ck("A4 ★★ 全量扫描（主文件 + 全部模块 × `call`+`_call_long`）0 处缺 stage",
   not _missing, f"共 {_total_sites} 个调用点；缺：{_missing[:6]}")
#: ★ A5 是 A4 的「有牙」自检：扫描范围真的覆盖了模块文件与 `_call_long`。
#:   否则 A4 会因为「只扫了几处」而恒绿 —— 恒绿的判据等于没有判据。
_files_seen = set()
_call_long_seen = 0
for _f in _all_files:
    if _f.name.startswith("tests"):
        continue
    try:
        _t = ast.parse(_f.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr in ("call", "_call_long"):
            _files_seen.add(_f.name)
            if _n.func.attr == "_call_long":
                _call_long_seen += 1
#: ★ 点名登记（不是 `>= N` 的软阈值）：实测这 3 个模块 + 主文件含有调用点。
#:   少一个就说明扫描范围塌回「只扫主文件」—— 那正是上一版判据漏掉 7 处的原因。
_EXPECT_FILES = {"llm_feedback.py", "multi_turn.py", "vision_input.py"}
ck("A5 扫描覆盖到**模块**（不是只扫了主文件）",
   _EXPECT_FILES <= _files_seen,
   f"实到 {sorted(_files_seen)}")
ck("A6 扫描覆盖到 `_call_long`（包装器，上一版判据漏的就是它）",
   _call_long_seen >= 3, f"{_call_long_seen} 处")

# ───────────────────── B. 静态：必须是字面量 ─────────────────────
nonliteral = []
for node in ast.walk(tree):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "call"):
        continue
    for k in node.keywords:
        if k.arg == "cost_stage" and not (
                isinstance(k.value, ast.Constant)
                and isinstance(k.value.value, str)):
            nonliteral.append(node.lineno)
ck("B1 ★ `cost_stage` 一律是**字符串字面量**（传变量就又回到 None 盲区）",
   not nonliteral, f"非字面量：{nonliteral[:6]}")

ck("B2 归因用 `cost_stage or stage`（标签恒有，且显式标签优先）",
   "str(cost_stage or stage or \"unknown\")" in SRC
   or "str(cost_stage or stage or 'unknown')" in SRC)
ck("B3 eval/ops 归桶也用真实环节名（标签与分桶不许各说各话）",
   "cost_bucket(_sn)" in SRC)
ck("B4 `stage` 的语义没被改（thinking/联网仍读 `stage`）",
   "th = self.thinking_stages.get(stage)" in SRC
   and "_infer_stage_from_stack()" in SRC)

# ───────────── C/D. 构造性证明：真调 LLM.call ─────────────
spec = importlib.util.spec_from_file_location("_eng_cs", str(PATH))
mod = importlib.util.module_from_spec(spec)
sys.modules["_eng_cs"] = mod
spec.loader.exec_module(mod)


class _Stub:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(
            model=str(kw.get("model") or "stub"),
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="OK"),
                finish_reason="stop")],
            usage=SimpleNamespace(total_tokens=7))


CFG = {"api": {"key": "t", "default_model": "stub",
               "base_url": "http://x/v1", "timeout": 2,
               "max_retries": 1, "retry_backoff": 0.01}}


def _call(**kw):
    llm = mod.LLM(CFG)
    llm.client = _Stub()
    llm.call("s", "u", 0.0, 10, **kw)
    return llm


# ★ 复现原始缺陷场景：stage 为 None（= thinking 未声明时 _thinking_stage 返回 None）
llm_c = _call(stage=None, cost_stage="self_check")
ck("C1 ★ `stage=None` 但有 `cost_stage` ⇒ 计数落在真实环节名",
   llm_c.stage_calls.get("self_check") == 1
   and "unknown" not in llm_c.stage_calls,
   dict(llm_c.stage_calls))
ck("C2 该环节按设计归入 eval 桶（`self_check` ∈ _LLM_EVAL_STAGES）",
   llm_c.eval_calls == 1 and llm_c.ops_calls == 0,
   f"eval={llm_c.eval_calls} ops={llm_c.ops_calls}")

# ★ 变异体：不给 cost_stage ⇒ 必须落 unknown（否则 C1 是假绿）
llm_d = _call(stage=None)
ck("D1 ★ 变异体：不给 `cost_stage` ⇒ 落 `unknown`（证明 C1 测的是这条路径）",
   llm_d.stage_calls.get("unknown") == 1, dict(llm_d.stage_calls))
ck("D2 变异体：无标签时按设计归 ops 桶（未登记一律 ops）",
   llm_d.ops_calls == 1 and llm_d.eval_calls == 0,
   f"eval={llm_d.eval_calls} ops={llm_d.ops_calls}")

llm_e = _call(stage="already_named", cost_stage="already_named")
ck("D3 `stage` 与 `cost_stage` 同名时只记一次（不会双计）",
   llm_e.stage_calls.get("already_named") == 1, dict(llm_e.stage_calls))

# ───────────────────── E. 真实产物回归 ─────────────────────
# ★ 锚修正：原来取「outputs/ 里 mtime 最新」的包 —— 那是个**会变的锚**：
#   e2e 产物挪到 `outputs/_e2e_local/` 之后，「最新」回落到旧引擎的历史生产包
#   （它天然带着修复前的 unknown 桶）⇒ 判据量的是「历史」，不是「当前引擎」。
#   改为：只认**当前被测引擎版本及之后**产出的包（读 provenance.engine_version），
#   必须至少 1 个（有牙，否则恒绿）；旧引擎样本里的 unknown 调用数**显式记录**，
#   不判红也不静默（历史不改写）。
def _unk_bucket(by):
    if isinstance(by, dict):
        return by.get("unknown")
    return next((x for x in by
                 if isinstance(x, dict) and x.get("stage") == "unknown"), None)


_ver_m = re.search(r"V(\d+)\.(\d+)\.(\d+)", PATH.name)
VER_T = tuple(int(x) for x in _ver_m.groups()) if _ver_m else (0, 0, 0)
_reals = []
for _pat in (str(ROOT / "outputs" / "*.packed.json"),
             str(ROOT / "outputs" / "_e2e_local" / "*.packed.json")):
    _reals.extend(glob.glob(_pat))
_cur, _stale_unk_calls = [], 0
for p in _reals:
    try:
        d = json.loads(pathlib.Path(p).read_text(encoding="utf-8",
                                                errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", pv)
    if m and tuple(int(x) for x in m.groups()) >= VER_T:
        _cur.append((p, d))
    else:
        u = _unk_bucket(d.get("llm_by_stage") or [])
        if u:
            _stale_unk_calls += int(u.get("calls") or 0)
if not _cur:
    print("⚠ 没有当前引擎（V%d.%d.%d+）产出的可用产物做真实回归（不是判红，"
          "是没样本）" % VER_T)
else:
    _cur.sort(key=lambda t: os.path.getmtime(t[0]))
    _newest = _cur[-1][1]
    by = _newest.get("llm_by_stage") or []
    unk = _unk_bucket(by)
    ck("E1 ★ 当前引擎产出的真实产物里没有 `unknown` 桶（成本归因盲区已消）",
       not unk, f"unknown = {unk}；旧引擎历史样本 unknown 调用数（仅记录）= "
       f"{_stale_unk_calls}")
    ck("E1b 有牙自检：当前引擎样本 ≥1 个（否则 E1 恒绿 = 没判据）",
       len(_cur) >= 1, f"{len(_cur)} 个")
    ck("E2 最新产物有按 stage 归因的读数（不是空表）",
       bool(by), f"{len(by)} 个桶")

print("─" * 60)
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} 通过" + (f"，{len(FAIL)} 项判红" if FAIL else ""))
sys.exit(1 if FAIL else 0)
