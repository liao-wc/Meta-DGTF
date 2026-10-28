# -*- coding: utf-8 -*-
"""产物落盘的健壮性判据：单层渲染异常不许拖死整份产物。

背景（实测缺陷）
----------------
本地链路第一次跑完时出现：

    ⚠️  保存失败：KeyError: 'anchor'
       本次结果**没有落盘**，上面的终端输出是唯一记录。

根因：修行层（`"0"`）的 view 由 `zero_generation` 产出，是**另一套结构**
（键 = aspect_map / claim_gaps / duty / fact_contract / manifest /
zero_generation …），**没有 anchor / candidates / collision / amps / threads**；
而 `save_result()` 的逐层明细循环**假设四层同构**，直接 `v['anchor']`
⇒ KeyError ⇒ 一整跑（13 次调用 / 21323 tokens）的读数全部丢失。

★ 这个 bug 一直被「本地跑根本跑不完」盖着（单次调用 110s 超时）：
  **修好一个锁会让被它挡住的 bug 显形**。

判据结构
--------
A. 静态：裸下标 `v['anchor']` 不再存在（改成 `.get()` 兜底）
B. 构造性证明：真喂一份「0 层非标准结构」的 result 给 `save_result()`
   ⇒ 必须**落盘成功**，且 1 层照常渲染、0 层有失败留痕
C. 变异体：让 0 层**无论如何都会崩**（candidates 塞成不可迭代对象）
   ⇒ 仍然要落盘，且留痕写明原因
D. 应急落盘：`_emergency_dump()` 真能写出文件（含不可序列化字段）
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

V2 = Path(__file__).resolve().parent
ROOT = V2.parent.parent
ENG = V2 / "engine"

FAILS: list[str] = []
N = [0]


def check(name: str, cond: bool, detail: str = "") -> None:
    N[0] += 1
    if not cond:
        FAILS.append(f"✗ {name}" + (f" — {detail}" if detail else ""))
        print(f"✗ {name}" + (f" — {detail}" if detail else ""))
    else:
        print(f"✓ {name}")


def _latest_engine() -> Path:
    """引擎版本从**文件名**推导（不能钉死版本号，钉了下次升版就假红）。"""
    cands = sorted(ENG.glob("Meta-DGTF-V*.py"))
    if not cands:
        raise SystemExit("❌ 找不到引擎文件")
    return cands[-1]


ENGINE = _latest_engine()
SRC = ENGINE.read_text(encoding="utf-8", errors="replace")
print(f"   被测引擎：{ENGINE.name}")

# ───────────────────────── A. 静态 ─────────────────────────
check("A1 逐层明细不再裸读 `v['anchor']`（改 .get 兜底）",
      "v['anchor']" not in SRC)
check("A2 逐层明细整块包了 try/except（一层崩只降级该层）",
      "except Exception as _lde:" in SRC)
check("A3 降级时**写明原因 + 原始字段留痕**（不是静默吞掉）",
      "本层明细渲染失败" in SRC and "原始字段留痕" in SRC)
check("A4 落盘失败会打印 traceback（原来只有一行 KeyError，定位不了）",
      "_tb.format_exc()" in SRC)
check("A5 有应急落盘函数 `_emergency_dump`（跑完的读数不许白丢）",
      "def _emergency_dump(" in SRC)
check("A6 两个保存点都接了应急落盘",
      SRC.count("_emergency_dump(result,") >= 2,
      f"实际 {SRC.count('_emergency_dump(result,')} 处")

# ─────────────────── B. 构造性证明：真跑 save_result ───────────────────
spec = importlib.util.spec_from_file_location("_eng_save", str(ENGINE))
mod = importlib.util.module_from_spec(spec)
sys.modules["_eng_save"] = mod
spec.loader.exec_module(mod)

# 用一份**真实产物**做底稿（结构最全，避免因缺字段而假红）
_reals = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                key=os.path.getmtime)
BASE = None
for p in reversed(_reals):
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    if isinstance(d.get("views"), dict) and d["views"].get("1"):
        BASE = d
        break
if BASE is None:
    print("⚠ 找不到可用的真实产物做底稿，B/C 组无法执行（不是判红，是没底稿）")
    sys.exit(1 if FAILS else 0)

#: 实测抓到的「0 层非标准结构」（zero_generation 产出，没有 anchor 等键）
ZERO_VIEW = {
    "aspect_map": {"a": 1}, "claim_gaps": [], "deferred": [],
    "duty": {}, "external_evidence_ids": [], "fact_contract": {},
    "manifest": "（非标准结构样本）", "novelty_curve": [],
    "probes": [], "quality_flags": [], "suspensions": [],
    "zero_generation": {"ok": True},
}


def _run_save(result: dict) -> tuple[bool, list[Path], str, str]:
    """调真 `save_result()` 到临时目录。

    ★ md/packed 的**内容必须在临时目录还活着时读出来**：原来是在 `with` 退出后
      才回读文件 ⇒ FileNotFoundError（判据自己崩，不是被测代码有问题）。
    """
    md_txt = ""
    with tempfile.TemporaryDirectory() as td:
        try:
            mod.save_result(json.loads(json.dumps(result)), td)
        except Exception as e:  # noqa: BLE001
            print(f"      save_result 抛错：{type(e).__name__}: {e}")
            return False, [], "", ""
        files = [Path(x) for x in glob.glob(os.path.join(td, "*"))]
        for f in files:
            if f.suffix == ".md":
                try:
                    md_txt = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
                break
        return True, files, md_txt, td


r1 = dict(BASE)
r1["views"] = dict(BASE.get("views") or {})
r1["views"]["0"] = dict(ZERO_VIEW)
ok1, files1, txt1, _td1 = _run_save(r1)
check("B1 ★ 0 层是非标准结构时，**产物仍然落盘**（V2.2.7 在此处整份丢失）",
      ok1 and bool(files1), f"落了 {len(files1)} 个文件")
check("B2 落盘产物含 packed（不只是 md）",
      any(f.suffix == ".json" for f in files1),
      str([f.name for f in files1][:4]))

if txt1:
    check("B3 ★ 研究层（1 层）照常渲染（一层崩不许连坐其他层）",
          "研究层" in txt1 or "`1`" in txt1)
    check("B4 修行层缺 anchor 时按 .get 兜底渲染（不再整层崩掉）",
          "本层未产出锚点" in txt1 or "本层明细渲染失败" in txt1,
          "既没有兜底文案也没有失败留痕 ⇒ 0 层被静默吞了")
    check("B5 0 层的原始字段有留痕（读产物的人看得见数据没丢）",
          "zero_generation" in txt1 or "本层未产出锚点" in txt1)

# ─────────── C. 变异体：让 0 层无论如何都崩 ───────────────────
r2 = dict(BASE)
r2["views"] = dict(BASE.get("views") or {})
r2["views"]["0"] = {"candidates": 12345, "anchor": "x"}   # 迭代必炸
ok2, files2, txt2, _td2 = _run_save(r2)
check("C1 ★ 变异体：0 层渲染必崩时**仍然落盘**", ok2 and bool(files2))
if txt2:
    check("C2 崩掉的那层写明失败原因（不是静默消失）",
          "本层明细渲染失败" in txt2)
    check("C3 崩掉那层的原始字段被列出来留痕",
          "candidates" in txt2)

# ─────────────────── D. 应急落盘 ───────────────────
with tempfile.TemporaryDirectory() as td:
    class _Weird:
        def __repr__(self):
            return "<不可序列化样本>"
    fp = mod._emergency_dump({"views": {"0": {"x": _Weird()}},
                              "n": 1}, td)
    check("D1 ★ 应急落盘真能写出文件（含不可序列化字段也不失败）",
          bool(fp) and Path(fp).is_file(), fp)
    if fp and Path(fp).is_file():
        body = Path(fp).read_text(encoding="utf-8", errors="replace")
        check("D2 应急文件里原始字段还在（不是空壳）",
              "不可序列化样本" in body or "views" in body)
        check("D3 应急文件落在 `_crash/` 子目录（与正式产物分开）",
              "_crash" in fp.replace("\\", "/"))

print("─" * 60)
print(f"{N[0] - len(FAILS)}/{N[0]} 通过" + (f"，{len(FAILS)} 项判红" if FAILS else ""))
sys.exit(1 if FAILS else 0)
