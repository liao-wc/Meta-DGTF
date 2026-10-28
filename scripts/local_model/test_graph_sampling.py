# -*- coding: utf-8 -*-
"""[V2.2.15] 本地服务 graph 采样/复用的**零 GPU**判据。

为什么需要它
------------
V2.2.15 把 CUDA graph 从「只支持 temp==0 贪心」扩到「temp>0 采样 + 重复惩罚」，
并把 graph 按 key 复用（LoRA stage 各一张 / base 共用一张），还让 base stage
显式禁用适配器。这些改动的**正确性不能只靠「服务在跑」来证明**：
  · 本文件全部零 GPU、零 HTTP、零 torch —— 任何 python 都能跑；
  · 纯函数判据（graph_cache_key）+ 源码结构判据（单一定义/接线/无 temp==0 门）；
  · 每条判据都配**变异体**：把被禁的写法喂给同一个检查函数 ⇒ 必须判红。
    （恒绿的判据等于没有判据，本项目老坑。）

GPU 侧运行判据见 test_graph_decode.py 的 G4–G8（服务在线才跑）。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dgtf_local_llm import gates  # noqa: E402

P, F = [], []


def ck(name: str, cond: bool, info="") -> None:
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" :: " + str(info) if not cond else ""))


SERVICE = ROOT / "dgtf_local_llm" / "service.py"
SRC = SERVICE.read_text(encoding="utf-8-sig")  # service.py 带 BOM
TREE = ast.parse(SRC)
LINES = SRC.splitlines()


# ── A 纯函数：graph 复用 key ─────────────────────────────────
print("── A graph_cache_key（单一定义在 gates）──")
ck("A1 LoRA stage ⇒ 专属图 key",
   gates.graph_cache_key("dual_judge") == "adapter::dual_judge",
   gates.graph_cache_key("dual_judge"))
ck("A2 base stage ⇒ 共用 base 图",
   gates.graph_cache_key("re_anchor") == "base",
   gates.graph_cache_key("re_anchor"))
ck("A3 空/None ⇒ base（不抛异常）",
   gates.graph_cache_key("") == "base" and gates.graph_cache_key(None) == "base")
ck("A4 自定义 lora 表为空 ⇒ 全部 base",
   gates.graph_cache_key("dual_judge", ()) == "base")
ck("A5 LORA_STAGES 全表都映射到专属图（覆盖四件套）",
   all(gates.graph_cache_key(s) == "adapter::" + s for s in gates.LORA_STAGES),
   [gates.graph_cache_key(s) for s in gates.LORA_STAGES])
ck("A6 ★ 未知 base stage 不会撞进 adapter 命名空间",
   not gates.graph_cache_key("expand_pair_merged").startswith("adapter::"))


# ── B 源码结构：service 真的用了单一定义 / 无 temp==0 门 ──────
print("── B service.py 源码结构 ──")


def _func_src(name: str):
    for n in ast.walk(TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return "\n".join(LINES[n.lineno - 1:n.end_lineno]), n
    return "", None


def _calls_name(node, fname: str) -> bool:
    if node is None:
        return False
    for x in ast.walk(node):
        if isinstance(x, ast.Call):
            f = x.func
            if isinstance(f, ast.Name) and f.id == fname:
                return True
            if isinstance(f, ast.Attribute) and f.attr == fname:
                return True
    return False


_gk_src, _gk_node = _func_src("_graph_key")
ck("B1 service 有 _graph_key 方法", _gk_node is not None)
ck("B2 ★ _graph_key 调用 gates.graph_cache_key（不是自己抄一份规则）",
   _calls_name(_gk_node, "graph_cache_key"), _gk_src[:200])
ck("B3 ★ service 源码里没有复制的 adapter:: 字面量（单一定义）",
   "adapter::" not in SRC, [l for l in LINES if "adapter::" in l][:2])
m = re.search(r"from dgtf_local_llm\.gates import \(([^)]*)\)", SRC)
ck("B4 import 里带 graph_cache_key", bool(m) and "graph_cache_key" in m.group(1))
gg_src, gg_node = _func_src("generate_graph")
ck("B5 ★ generate_graph 接受 temperature 参数",
   any(a.arg == "temperature" for a in (gg_node.args.args if gg_node else [])))
ck("B6 ★ generate_graph 接受 rep_pen 参数",
   any(a.arg == "rep_pen" for a in (gg_node.args.args if gg_node else [])))
ck("B7 ★ rep_pen 在 graph 外施加（源码有 where 惩罚分支）",
   "scores / pen_vec" in gg_src and "scores * pen_vec" in gg_src)
_h_src, _h_node = _func_src("_handle")
ck("B8 ★ _handle 不再有 temp == 0 且 graph 的门",
   not re.search(r"if\s+temp\s*==\s*0\s+and", _h_src or ""), (_h_src or "")[:160])
ck("B9 ★ _handle 把 temperature=temp 传给 generate_graph",
   "temperature=temp" in (_h_src or "") and "rep_pen=rep_pen" in (_h_src or ""))
_ac_src, _ac_node = _func_src("_adapter_ctx")
ck("B10 ★ base stage 显式禁用适配器（self.model.disable_adapter()）",
   bool(_ac_node) and "self.model.disable_adapter()" in _ac_src, _ac_src[:160])
ck("B11 适配器隔离有留痕：_graph_capture 记录 graph_capture_keys",
   "graph_capture_keys" in SRC)
ck("B12 回包有 graph / sampled / graph_key 三个留痕字段",
   all(("%s" % k) in SRC and ('"%s":' % k) in SRC for k in ("graph", "sampled", "graph_key")))


# ── C 变异体：同一套检查逻辑必须能判红 ──────────────────────
print("── C 变异体（有牙证明）──")


def _static_checks(src: str) -> dict:
    """对任意 service 源码跑 B2/B3/B8/B10 四条的核心判定（给变异体用）。"""
    tree = ast.parse(src)
    lines = src.splitlines()
    gk_node = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_graph_key":
            gk_node = n
            break
    h = ""
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_handle":
            h = "\n".join(lines[n.lineno - 1:n.end_lineno])
            break
    ac = ""
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_adapter_ctx":
            ac = "\n".join(lines[n.lineno - 1:n.end_lineno])
            break
    return {
        "single_def": "adapter::" not in src,
        "uses_fn": _calls_name(gk_node, "graph_cache_key"),
        "no_temp0_gate": not re.search(r"if\s+temp\s*==\s*0\s+and", h),
        "disable_base": "self.model.disable_adapter()" in ac,
    }


_ok = _static_checks(SRC)
ck("C0 真实源码四项全过（否则 C1–C4 的变异体没有对照）",
   all(_ok.values()), _ok)

_bad1 = SRC.replace("return graph_cache_key(stage, tuple(self.adapter_names or ()))",
                    "if stage in self.adapter_names:\n            return \"adapter::\" + str(stage)\n        return \"base\"")
ck("C1 ★ 变异体：_graph_key 自己抄规则（不调 gates）⇒ 判红",
   _static_checks(_bad1)["uses_fn"] is False)

_bad2 = SRC.replace("        return graph_cache_key(stage, tuple(self.adapter_names or ()))",
                    "        return \"adapter::\" + str(stage)")
ck("C2 ★ 变异体：service 里出现 adapter:: 字面量 ⇒ 单一定义判红",
   _static_checks(_bad2)["single_def"] is False)

_bad3 = SRC.replace("        if int(ids.shape[0]) == 1:",
                    "        if temp == 0 and int(ids.shape[0]) == 1:", 1)
ck("C3 ★ 变异体：把 temp==0 门加回 _handle ⇒ 判红",
   _static_checks(_bad3)["no_temp0_gate"] is False)

_bad4 = SRC.replace("            return self.model.disable_adapter()",
                    "            return _cl.nullcontext()")
ck("C4 ★ 变异体：base stage 不禁用适配器 ⇒ 判红",
   _static_checks(_bad4)["disable_base"] is False)

_bad_key = lambda stage, lora_stages=gates.LORA_STAGES: "base"
ck("C5 ★ 变异体：graph_cache_key 把 LoRA 也映射到 base ⇒ A1 判红",
   _bad_key("dual_judge") != "adapter::dual_judge")
ck("C6 ★ 变异体：把 LORA_STAGES 清空 ⇒ A5 判红",
   gates.graph_cache_key("dual_judge", ()) != "adapter::dual_judge")

print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
