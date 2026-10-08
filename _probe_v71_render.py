#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E 渲染探针 · v1.21.71（F1 的**产物/日志出口**）

用法：
    python _probe_v71_render.py 元DGTF-V1.21.70.py > _probe_v71_render_before.txt
    python _probe_v71_render.py 元DGTF-V1.21.71.py > _probe_v71_render_after.txt

★ 回答的是 F1 的第二个问题：「收尾字段回填了，**出口有没有**？」
  · 日志侧：`dump_final` 的「收尾留痕 · entry=… · 共 N 圈」段；
  · 产物侧：md 头部每层的 `(N圈)` 与明细里的 `【螺旋停止】`。
★ 全部离线（LLM 走 smoke 的桩），只用 mock 跑，不花 token。
"""
import contextlib
import io
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import types
from pathlib import Path

TARGET = Path(sys.argv[1]).resolve()
HERE = TARGET.parent

_src = (HERE / "smoke_test.py").read_text(encoding="utf-8")
_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
assert len(_pat.findall(_src)) == 1, "smoke_test.py 里 SRC 行不是 1 行"
_src = _pat.sub('SRC = Path(r"%s")' % str(TARGET).replace("\\", "\\\\"), _src)
_hm = types.ModuleType("render_harness")
_hm.__file__ = str(HERE / "smoke_test.py")
sys.modules["render_harness"] = _hm
exec(compile(_src, str(HERE / "smoke_test.py"), "exec"), _hm.__dict__)

mod = _hm.mod
Q = "渲染探针题：这套结构的边界在哪，哪些部分原则上判不出"
OUT = {}


def _run(mode, rounds):
    _cfg = _hm.build_cfg(True)          # verbose=True：dump_final 才打
    _cfg["output"]["save_dir"] = str(_d)
    meta = mod.MetaDGTF(_cfg)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        packed = meta.run(Q, route=["0", "1", "both", "all"],
                          rounds=rounds, parallel_mode=mode)
        mdp = mod.save_result(packed, _cfg["output"]["save_dir"])
    return packed, buf.getvalue(), Path(mdp).read_text(encoding="utf-8")


_d = Path(tempfile.mkdtemp(prefix="probe71_render_"))

for _mode in ("serial", "B"):
    print("\n" + "=" * 62)
    print(f"## 模式 {_mode} · 四层各 1 圈")
    print("=" * 62)
    packed, out, mdtxt = _run(_mode, {"0": 1, "1": 1, "both": 1, "all": 1})
    # ---- 收尾字段 ----
    for e in ("0", "1", "both", "all"):
        v = packed["views"].get(e) or {}
        print(f"   层 {e:5s} roles_run={len(v.get('roles_run') or [])} "
              f"rounds_cap={v.get('rounds_cap')} "
              f"round_log={len(v.get('round_log') or [])} "
              f"| stop={str(v.get('stop_reason') or '')[:20]!r}")
    # ---- 日志出口：收尾留痕段 ----
    segs = re.findall(r"收尾留痕 · entry=(\S+?) · 共 (\d+) 圈 · ([^\n]*)", out)
    print(f"   日志「收尾留痕」段：{len(segs)} 段 → {segs}")
    # ---- 日志出口：每层的停止交代 ----
    stops = re.findall(r"⏹ ([^\n]*)", out)
    print(f"   日志「⏹」行：{len(stops)} 条")
    for s in stops[:8]:
        print(f"      · {s[:70]}")
    # ---- 产物出口 ----
    #   ★ 产物里**没有**【螺旋停止】那种带方括号的写法（那是日志侧
    #     `_view_block_lines` 的），md 自己写的是 `**螺旋停止**：…`。
    #     第一版探针照日志的写法数 md，数出 0 却当成"出口没通"——记下来。
    n_stop = mdtxt.count("**螺旋停止**")
    n_rounds = mdtxt.count("**实际走了")
    n_table = mdtxt.count("| 圈 | 角色 |")
    _head = re.search(r"\*\*调度\*\*：([^\n]*)", mdtxt)
    print(f"   产物：**螺旋停止** {n_stop} 处 / **实际走了** {n_rounds} 处 / "
          f"round_log 表 {n_table} 张")
    print(f"   产物头部调度 = {(_head.group(1) if _head else '（无）')}")
    OUT[_mode] = {"final_segs": len(segs), "stop_marks": n_stop,
                  "rounds_lines": n_rounds, "round_log_tables": n_table,
                  "head": (_head.group(1) if _head else None),
                  "calls": packed.get("llm_calls")}

print("\n" + "=" * 62)
print("## 汇总")
print("=" * 62)
for k, v in OUT.items():
    print(f"   {k:6s} 收尾留痕 {v['final_segs']} 段 / md 螺旋停止 "
          f"{v['stop_marks']} 处 / 实际走了 {v['rounds_lines']} 处 / "
          f"round_log 表 {v['round_log_tables']} 张")
print("\n   预期（v1.21.71）：两种模式都应「收尾留痕 4 段 + md 螺旋停止 4 处"
      "+ 实际走了 4 处 + round_log 表 4 张」；"
      "\n   v1.21.70：单圈层被 `> 1` 门挡掉 → 后三项全少（serial 侧为 0）。")

shutil.rmtree(_d, ignore_errors=True)
