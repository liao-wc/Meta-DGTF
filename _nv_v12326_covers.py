#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step5 负对照：直接驱动 MetaDGTF._quality_check。

目标：证明 covers 的**数字编号分支**现在会校验语义。

  负对照 A：covers=["T1"] 但探针问题与未触及项**语义无关** ⇒ 必须报红
  正对照 B：covers=["T1"] 且探针问题与未触及项**语义相关** ⇒ 不报

用法：python _nv_v12326_covers.py <引擎.py>
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (Path(sys.argv[1]) if len(sys.argv) > 1
       else HERE / "元DGTF-V1.23.26.py").resolve()
assert SRC.exists()

txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
mod = types.ModuleType("dg")
mod.__file__ = str(SRC)
sys.modules["dg"] = mod
_sv = sys.argv
sys.argv = [str(SRC)]
exec(compile(txt, str(SRC), "exec"), mod.__dict__)
sys.argv = _sv

print(f"引擎 {mod.__version__}  {SRC.name}")

# 类名是 DGTF（不是 MetaDGTF —— 全文件里 MetaDGTF 只出现在文档/别名处）
CLS = None
for cand in ("DGTF", "MetaDGTF"):
    if hasattr(mod, cand) and hasattr(getattr(mod, cand), "_quality_check"):
        CLS = getattr(mod, cand)
        print(f"用类 {cand}")
        break
assert CLS is not None, "没找到含 _quality_check 的类"

View = mod.View
Pool = mod.Pool

# 找 _quality_check 需要的 View 字段
import inspect
sig = inspect.signature(CLS._quality_check)
print("_quality_check 签名:", sig)

# 用一个最省的方式构造实例：绕过 __init__
obj = CLS.__new__(CLS)
obj.entry = "1"
obj.config = dict(mod.DEFAULT_CONFIG)
obj.vp = lambda *a, **k: None
for attr, val in [("_diag_dir", None), ("diag_dir", None)]:
    if hasattr(obj, attr):
        setattr(obj, attr, val)


def _mk_view(untouched_texts, probes):
    v = View.__new__(View)
    for name, default in [
        ("candidates", []), ("amps", []), ("threads", []), ("probes", []),
        ("errors", []), ("self_check", {}), ("collision", ""),
        ("engagements", []), ("deferrals", []), ("reconfirmations", []),
        ("resolutions", []), ("escalations", []), ("reclassifications", []),
        ("covers", []), ("meta", []), ("refinements", []),
        ("probe_skipped", False), ("notes", []), ("suspicious", []),
    ]:
        try:
            setattr(v, name, default)
        except Exception:
            pass
    v.untouched = [{"desc": t} for t in untouched_texts]
    v.probes = probes
    return v


UT = [
    "材料在极低温下的超导相变临界温度测量方法",
    "实验装置的电磁屏蔽对测量信噪比的影响",
    "样品制备过程中杂质浓度对结果的可重复性",
]

CASES = [
    # (名字, probes, 期望报红)
    ("A 负对照：covers=[T1] 但问题与 T1 语义无关",
     [{"question": "披萨需要烤制多长时间才能外脆内软",
       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}], True),
    ("B 正对照：covers=[T1] 且问题与 T1 语义相关",
     [{"question": "超导相变临界温度在极低温下如何测量",
       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}], False),
    ("C 负对照：covers=[T5] 越界编号",
     [{"question": "披萨需要烤制多长时间才能外脆内软",
       "covers": ["T5"], "expected_gain": 0.6, "link": "x"}], True),
    ("D 负对照：covers 空 + 问题与所有未触及项都无关",
     [{"question": "披萨需要烤制多长时间才能外脆内软",
       "covers": [], "expected_gain": 0.6, "link": "x"}], True),
    ("E 正对照：covers 空 + 问题与 T1 相关（走 fallback）",
     [{"question": "超导相变临界温度在极低温下如何测量",
       "covers": [], "expected_gain": 0.6, "link": "x"}], False),
]

print()
ok = True
for name, probes, expect_flag in CASES:
    v = _mk_view(UT, probes)
    p = Pool()
    try:
        flags = obj._quality_check(v, p, 1, write_diag=False)
    except TypeError:
        flags = obj._quality_check(v, p, 1)
    except Exception as e:
        print(f"  {name}\n    !! 驱动失败: {type(e).__name__}: {e}")
        ok = False
        continue
    got = "probe_no_target_covered" in flags
    mark = "OK " if got == expect_flag else "★ 不符"
    if got != expect_flag:
        ok = False
    print(f"  [{mark}] {name}")
    print(f"          报红={got} 期望={expect_flag}  全部 flags={flags}")

print()
print("结论:", "全部符合" if ok else "★ 有不符合项")
sys.exit(0 if ok else 1)
