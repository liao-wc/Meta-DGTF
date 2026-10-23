#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前置量化探针 · v1.21.72（#13 注释 / #20 文档卫生 / #22 唯一实现点 / #24 长度异常）

用法：
    python _probe_v72.py 元DGTF-V1.21.71.py > _probe_v72_before.txt
    python _probe_v72.py 元DGTF-V1.21.72.py > _probe_v72_after.txt

★ 三项都是**只读**观测：
  [A] B 模式预算耗尽时，是不是**所有层一起停**（barrier 语义，#13）；
  [B] 一次 mock 跑里每个 View 字段的渲染长度（#24 的告警阈值要靠它标定）；
  [C] docstring 的卫生指标：重复「收束摘要」段数、版本段序（#20）。
★ LLM 全部走 smoke_test 的桩，不联网。
"""
import ast
import contextlib
import inspect
import io
import re
import sys
import types
from pathlib import Path

TARGET = Path(sys.argv[1]).resolve()
HERE = TARGET.parent

src_raw = TARGET.read_bytes().decode("utf-8").replace("\r\n", "\n")
_src = (HERE / "smoke_test.py").read_text(encoding="utf-8")
_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
assert len(_pat.findall(_src)) == 1, "smoke_test.py 里 SRC 行不是 1 行"
_src = _pat.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), _src)
_hm = types.ModuleType("probe72_harness")
_hm.__file__ = str(HERE / "smoke_test.py")
sys.modules["probe72_harness"] = _hm
exec(compile(_src, str(HERE / "smoke_test.py"), "exec"), _hm.__dict__)
mod = _hm.mod
Q = "v72 探针题：这套结构的边界在哪，哪些部分原则上判不出"


def _sec(n):
    print("\n" + "=" * 66)
    print(f"## {n}")
    print("=" * 66)


# ======================================================================
# [A] #13 · B 模式预算耗尽：全部层一起停 vs 只停一层
# ======================================================================
_sec("[A] #13 · B 模式预算耗尽时停了哪些层")
_A = {}
for _budget, _tag in ((0, "不限预算"), (30, "预算 30")):
    _cfg = _hm.build_cfg(False)
    _cfg["max_calls"] = _budget
    meta = mod.MetaDGTF(_cfg)
    _buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(_buf):
            packed = meta.run(Q, route=["0", "1", "both", "all"],
                              rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                              parallel_mode="B")
        _stopped = [e for e, v in (packed.get("views") or {}).items()
                    if "预算用尽" in str(v.get("stop_reason") or "")]
        _A[_tag] = {"active": len(packed.get("views") or {}),
                    "budget_stopped": sorted(_stopped),
                    "calls": packed.get("llm_calls")}
    except Exception as e:                                  # noqa: BLE001
        _A[_tag] = {"exc": f"{type(e).__name__}: {e}"}
    print(f"   {_tag:8s} → {_A[_tag]}")
print("   ⇒ 判据：预算触发时 `budget_stopped` 要么为空（没触发），要么等于"
      "全部 active 层（barrier）。出现 1..n-1 就是语义被改坏。")


# ======================================================================
# [B] #24 · View 各字段的渲染长度（告警阈值标定）
# ======================================================================
_sec("[B] #24 · 一次 mock 跑里的字段长度谱")
# ★ `_OVERSIZED` 是 `dump_view_fields` 的**局部**变量，不是模块级常量 ——
#   第一版探针用 getattr(mod, "_OVERSIZED") 拿到空集，把"不在名单里"误判成 0 个。
_dvf = inspect.getsource(mod.dump_view_fields)
_ov = set(re.findall(r'_OVERSIZED = \{([^}]*)\}', _dvf))
_ov = {x.strip().strip('"').strip("'") for x in (list(_ov)[0].split(",") if _ov else [])}
_ov.discard("")
print(f"   _OVERSIZED（从 dump_view_fields 源码里取）= {sorted(_ov)}")
_cfg = _hm.build_cfg(True)
meta = mod.MetaDGTF(_cfg)
with contextlib.redirect_stdout(io.StringIO()):
    _pk = meta.run(Q, route=["0", "1", "both", "all"],
                   rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                   parallel_mode="serial")
_lens = {}
for _e, _v in (_pk.get("views") or {}).items():
    if not isinstance(_v, dict):
        continue
    for _k, _val in _v.items():
        if isinstance(_val, str):
            _lens.setdefault(_k, 0)
            _lens[_k] = max(_lens[_k], len(_val))
_big = sorted((v, k) for k, v in _lens.items() if v >= 2000)
print(f"   字符串字段 ≥2000 字的（字段, 最大长度）：")
for _v, _k in reversed(_big):
    print(f"      {_k:<22} {_v:>7}  {'（在 _OVERSIZED）' if _k in _ov else '★ 不在 _OVERSIZED'}")
print(f"   字段总数 {len(_lens)}；≥2000 字 {len(_big)} 个")


# ======================================================================
# [C] #20 · docstring 卫生
# ======================================================================
_sec("[C] #20 · docstring 卫生（重复段 / 版本段序）")
_i = src_raw.index('"""')
_j = src_raw.index('"""', _i + 3)
doc = src_raw[_i:_j + 3]
_lines = doc.split("\n")
_sums = [_l.strip() for _l in _lines if "★ v1.21." in _l and "收束摘要" in _l]
_dup = {t: _sums.count(t) for t in set(_sums) if _sums.count(t) > 1}
_secs = re.findall(r"^v(1\.21\.\d+) 相对", doc, re.M)
_ver = [tuple(int(x) for x in v.split(".")) for v in _secs]
_C = {"summary_headers": len(_sums), "duplicated": _dup,
      "section_order": _secs,
      "order_ok": all(_ver[k] > _ver[k + 1] for k in range(len(_ver) - 1)),
      "n_sections": len(_secs)}
for _k, _v in _C.items():
    print(f"   {_k} = {str(_v)[:120]}")
print("   ⇒ 判据：`duplicated` 必须为空；`order_ok` 必须为 True")


# ======================================================================
# [D] #22 · 机制 → 唯一实现点
# ======================================================================
_sec("[D] #22 · 关键机制的定义点数 / 第二实现点")
# ★ 必须在**抠掉 docstring 的源码**上数：changelog 里也会出现这些函数名
#   与旧写法（第一版在全文上数，`old_finalize_gate_serial` 数出 1 —— 那
#   是 v1.21.71 changelog 里的引用，不是代码）。
exec_src = '"""X"""' + src_raw[_j + 3:]
_D = {}
for _fn in ("_normalize_decidability", "_untraced_undecidable", "_stop_reasons",
            "_finalize_layer_common", "_cached_ext_assess",
            "_dispatch_for_pack", "_layer_guard", "_quality_check",
            "_merge_decidability", "_assess_decidability_dynamic"):
    _D[_fn] = len(re.findall(r"^\s*def " + _fn + r"\b", exec_src, re.M))
_D["_assess_decidability_def"] = len(
    re.findall(r"def _assess_decidability\(", exec_src))
_D["_assess_decidability_call_sites"] = len(
    re.findall(r"_assess_decidability\(", exec_src)) \
    - _D["_assess_decidability_def"]
_D["finalize_call_sites"] = len(re.findall(r"self\._finalize_layer_common\(",
                                           exec_src))
_D["stop_reasons_call_sites"] = len(re.findall(r"self\._stop_reasons\(", exec_src))
_D["old_finalize_gate_serial"] = exec_src.count(
    "if view is not None and rounds_n > 1:")
_D["old_finalize_gate_B"] = exec_src.count('state["total_rounds"] <= 1')
_D["b_barrier_comment"] = "barrier" in exec_src
# ★ 判据要用**带标签的标记串**：`barrier` 这个词在 v1.21.71 之前就有别处
#   （`_run_parallel_B` 里"每波 barrier 对齐"），拿它当判据没有判别力。
_D["v72_13_tag"] = exec_src.count("[v1.21.72 #13]")
for _k, _v in _D.items():
    print(f"   {_k:<34} = {_v}")
print("   ⇒ 判据：各机制定义点 == 1；`_assess_decidability` 的调用点 == 1"
      "（F6 的唯一入口）；finalize / stop_reasons 各 2 个调用点但只有 1 份实现；"
      "两处旧门 == 0。")

# ---- 零语义改动的机器证明：AST 逐节点相同（docstring 归一化后）----
_sec("[E] AST 逐节点比对（docstring 归一化后）")
_ast = ast.dump(ast.parse('"""X"""\n' + src_raw[_j + 3:]))
print(f"   本版 AST 指纹 {hash(_ast) & 0xffffffff:08x}  节点数 {len(_ast)}")
print(f"   与上一版比：见 _probe_v72_astcmp.txt（由 _cmp_v72_ast.py 生成）")

print("\n" + "=" * 66)
print("## 摘要（机器可读）")
print("=" * 66)
import json
print(json.dumps({"A": _A, "B": {"big_fields": _big, "oversized": sorted(_ov)},
                  "C": _C, "D": _D}, ensure_ascii=False, indent=1, default=str))
