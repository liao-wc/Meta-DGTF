#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 前置量化探针：建立「改前基线」。

用法：python _probe_v12326_sim.py <引擎.py>
同一支探针在改前(v1.23.25) / 改后(v1.23.26) 各跑一次，逐项对表。

零 LLM。用引擎本体尺子（exec 主文件成 module）。
"""
from __future__ import annotations

import sys
import types
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.26.py"
SRC = SRC.resolve()
assert SRC.exists(), f"找不到 {SRC}"

# ---- 把主文件 exec 成 module（不触发 main）----
txt = SRC.read_text(encoding="utf-8")
mod = types.ModuleType("dgtf_mod")
mod.__file__ = str(SRC)
sys.modules["dgtf_mod"] = mod
code = compile(txt, str(SRC), "exec")
# 屏蔽 main 入口
_saved = sys.argv
sys.argv = [str(SRC)]
try:
    exec(code, mod.__dict__)
finally:
    sys.argv = _saved

VERSION = getattr(mod, "__version__", "?")
print("=" * 68)
print(f"引擎版本 {VERSION}  文件 {SRC.name}")
print("=" * 68)

out = {"version": VERSION, "file": SRC.name}

# ==========================================================
# B1. _overlap_coef 短句高估（阶段二根因）
# ==========================================================
print("\n[B1] _overlap_coef 短句高估（分母 min + _kw 实取 16 词）")
_kw = mod._kw
_oc = mod._overlap_coef
_sim = mod._similar
_sr = mod._sim_ratio

# 验证 _kw 实取数
probe_long = "这是一个关于人工智能模型部署管线与推理优化的长句子用来测试关键词抽取数量"
kws = _kw(probe_long, 8)
print(f"  _kw(长句, top_n=8) 实取 {len(kws)} 个词  -> {'确认 top_n*2' if len(kws) > 8 else '实取 8 或更少'}")

cases = [
    ("人工智能 模型 部署", "人工智能 模型 训练"),      # 共享 2/3
    ("神经网络 优化", "神经网络 训练"),                 # 共享 1/2
    ("模型 部署", "模型 训练"),                         # 共享 1/2
    ("人工智能 模型 部署 管线 优化 推理 加速 量化", "人工智能 模型 部署 管线 优化"),
    ("人工智能模型部署管线优化推理加速量化压缩蒸馏", "人工智能模型部署管线优化推理加速"),  # 无空格
]
print(f"  {'A':<34} {'B':<28} {'ovl':>6} {'sim':>6} {'sr':>6}")
b1 = []
for a, b in cases:
    v1, v2, v3 = _oc(a, b), (_sim(a, b, 0.75) * 1.0), _sr(a, b)
    b1.append({"a": a, "b": b, "overlap": round(v1, 4),
               "similar": v2, "sim_ratio": round(v3, 4)})
    print(f"  {a[:32]:<34} {b[:26]:<28} {v1:>6.3f} {v2:>6.0f} {v3:>6.3f}")
out["B1_overlap_short"] = b1

# ==========================================================
# B2. 池内去重阈值：字面量数
# ==========================================================
print("\n[B2] Pool.merge 去重阈值字面量（红线「参数按层可覆盖」违规数）")
m = re.search(
    r"    def merge\(self, amps, threads, meta, probes=None, suspensions=None\):"
    r"(.*?)\n    def ", txt, re.S)
if m:
    _merge_src = m.group(1)
    # _similar(...) 的第三个位置参数（阈值）
    lits = re.findall(r"_similar\(\s*[^()]*(?:\([^()]*\)[^()]*)*,\s*(0\.\d+)\s*\)",
                      _merge_src)
    print(f"  merge 体内 _similar 阈值字面量：{lits}  (共 {len(lits)} 处)")
    out["B2_merge_literals"] = lits
    reads_cfg = ("config" in _merge_src or "cfg" in _merge_src)
    print(f"  merge 是否读配置：{reads_cfg}")
    out["B2_merge_reads_config"] = reads_cfg
else:
    print("  !! 未匹配到 merge 函数体")
    out["B2_merge_literals"] = None

# 全文件字面量 0.9 / 0.85 出现在 _similar 里的次数
all_lits = re.findall(r"_similar\([^)]*?,\s*(0\.\d+)\s*\)", txt)
from collections import Counter
print(f"  全文件 _similar(...) 阈值字面量分布：{dict(Counter(all_lits))}")
out["B2_all_similar_literals"] = dict(Counter(all_lits))

# ==========================================================
# B3. select_probe_focus 是否「必然塞满 n」
# ==========================================================
print("\n[B3] select_probe_focus：候选全不相干时，是否仍塞满 n 个")
sel = mod.select_probe_focus


class _Pool:
    def __init__(self):
        self.amps = [{"desc": "关于量子纠缠的实验设计", "polarity": "0"}]
        self.threads = [{"desc": "材料纯度的测量误差"}]
        self.probes = []


# 3 个**完全不相干**的候选
irrelevant = [
    {"question": "唐宋八大家都是谁"},
    {"question": "披萨要烤多久"},
    {"question": "如何给猫剪指甲"},
]
# 4 个候选，n=3
picked = sel(_Pool(), irrelevant + [{"question": "第五个无关问题"}],
             [], ["量子纠缠"], "量子纠缠的实验", {"probe": {"select_n": 3}})
print(f"  输入 4 个全不相干候选 n=3 -> 选出 {len(picked)} 个")
for p in picked:
    print(f"    · {p.get('question')}")
out["B3_fill_unrelated_in"] = 4
out["B3_fill_unrelated_out"] = len(picked)

# 空池 + 无候选
picked0 = sel(_Pool(), [], [], [], "", {"probe": {"select_n": 3}})
print(f"  无候选 -> 选出 {len(picked0)}")
out["B3_empty_out"] = len(picked0)

# ==========================================================
# B4. covers 校验：编号对但语义错，是否报红
# ==========================================================
print("\n[B4] probe_no_target_covered：covers 乱指 T1（编号在范围内、语义无关）")
_cu = mod._classify_unsaid

# 判据是**内嵌**在 _quality_flags 里的（不在模块级）—— 用文本定位
_i = txt.find('if (self.entry == "1" and view.untouched and view.probes):')
_j = txt.find("if not has_touch:", _i)
if _i > 0 and _j > _i:
    body = txt[_i:_j]
    print(f"  判据体行数 {len(body.splitlines())}")
    # 数字分支（只查编号范围）
    num_branch = body.split("if m:", 1)[1].split("else:", 1)[0] if "if m:" in body else ""
    has_sem_num = bool(re.search(r"_similar|_overlap_coef|_sim_ratio|_sim3", num_branch))
    print(f"  【数字编号分支】含语义比较：{has_sem_num}  -> "
          f"{'有' if has_sem_num else '★ 无（只查编号在范围内）'}")
    out["B4_num_branch_semantic"] = has_sem_num
    # 非数字分支
    else_branch = body.split("else:", 1)[1].split("if has_touch:", 1)[0] if "else:" in body else ""
    calls = re.findall(r"(_similar|_overlap_coef|_sim_ratio|_sim3)\(", else_branch)
    print(f"  【非数字分支】相似度调用：{calls or '（无）'}")
    out["B4_else_branch_calls"] = calls
    # 无 covers fallback
    has_fallback = "if not covers_seen" in body
    fb_calls = []
    if has_fallback:
        fbm = body.split("if not covers_seen:", 1)[1]
        fb_calls = re.findall(r"(_similar|_overlap_coef|_sim_ratio|_sim3)\(", fbm)
    print(f"  【无 covers fallback】存在：{has_fallback}；调用：{fb_calls or '（无）'}")
    out["B4_fallback"] = {"present": has_fallback, "calls": fb_calls}
else:
    print("  !! 未找到判据体")
    out["B4_num_branch_semantic"] = None

# ==========================================================
# B5. _classify_unsaid：空 covers -> ?
# ==========================================================
print("\n[B5] _classify_unsaid 三分支")
for blk in [{"covers": ["T1"]}, {"covers": []}, {}, {"collision": "x", "probes": []},
            {"collision": "这里有些内容", "probes": [{"covers": ["T1"]}]}]:
    print(f"  {json.dumps(blk, ensure_ascii=False)[:60]:<62} -> {_cu(blk)}")

# ==========================================================
# B6. 探针过滤门：gain < min_gain 的位置
# ==========================================================
print("\n[B6] 探针过滤门")
for i, line in enumerate(txt.splitlines(), 1):
    if "gain < min_gain" in line or "expected_gain" in line and "min_gain" in line:
        print(f"  L{i}: {line.strip()}")
        out.setdefault("B6_gate_lines", []).append(i)
_gates = [i for i, l in enumerate(txt.splitlines(), 1) if "min_gain" in l]
print(f"  min_gain 出现行：{_gates}")
out["B6_min_gain_lines"] = _gates

# ==========================================================
# B7. 阈值常量表
# ==========================================================
print("\n[B7] 阈值常量")
for name in ["_DUP_SIM", "_REPHRASE_SIM", "_REPHRASE_OVERLAP", "_BAN_SIM",
             "_BAN_OVERLAP", "_KW_TOP_N", "_TAKE_SIM", "_QC_DUP_SIM",
             "_MERGE_SIM", "_SUSP_SAME_SIM", "_UNTRACED_OVERLAP"]:
    if hasattr(mod, name):
        v = getattr(mod, name)
        print(f"  {name:<22} = {v}")
        out.setdefault("B7_consts", {})[name] = v

# ==========================================================
# B8. 是否已有 sim3 / _bm25
# ==========================================================
print("\n[B8] 新函数是否已存在")
for name in ["sim3", "_sim3", "_bm25", "_bm25_sim"]:
    print(f"  {name:<12} : {'存在' if hasattr(mod, name) else '不存在'}")
    out.setdefault("B8_present", {})[name] = hasattr(mod, name)

rpt = HERE / f"_probe_v12326_sim.{VERSION}.json"
rpt.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[写出] {rpt.name}")
