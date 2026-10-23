#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1b] 按**完整版**任务书回正阶段 1 的三处偏差。

对照任务书：
- Step 1.5 修行层 stop_reason 改写（含「未生质量」）—— 上一轮漏了。
- `_classify_unsaid` 要能吃 **View 对象**（任务书探针/冒烟传的是
  `View(entry="0", collision=..., probes=[...])`），不能只吃 dict。
- Step 1.6 头部四行是**计数**（& N / 线头 N / 覆盖率 x% / third ✓ / clean），
  不是 objective 图例；objective 仍要可见 → 折进每层的括号里。

纪律：断言锚点出现次数 → 归一化 LF → 替换 → 切回 CRLF → write_bytes。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

# ---------------------------------------------------------------- 1. classify
OLD_CLS = """    if not isinstance(block, dict):
        return "lazy"
    cov = block.get("covers")
"""

NEW_CLS = """    # ★ 两种入参形态都要吃（任务书 Step 1.5 的探针传的是 View 对象）：
    #   · View 形态：看 view.collision 与 view.probes[*].covers；
    #   · dict 形态：直接看 block["covers"]（早期调用点用它）。
    #   判据只有一条：说「此处未生」之前，有没有声明碰过「未触及项」清单。
    if not isinstance(block, dict):
        ing = str(getattr(block, "collision", "") or "")
        prb = list(getattr(block, "probes", None) or [])
        if not ing or ing.strip() == "（此处未生）":
            return "lazy"
        return "real" if any(
            (p.get("covers") or []) for p in prb if isinstance(p, dict)
        ) else "lazy"
    if "collision" in block or "probes" in block:
        ing = str(block.get("collision") or "")
        if not ing or ing.strip() == "（此处未生）":
            return "lazy"
        return "real" if any(
            (p.get("covers") or [])
            for p in (block.get("probes") or []) if isinstance(p, dict)
        ) else "lazy"
    cov = block.get("covers")
"""

# ------------------------------------------------------------ 2. stop_reason
OLD_STOP = """            self.vp(f"   ⏹ {view.stop_reason}")

        # ---- 1. 把跨圈累积回填到 view ----
"""

NEW_STOP = """            self.vp(f"   ⏹ {view.stop_reason}")

        # [v122 阶段1 G1.5] 修行层不追求收敛：走到了「体力耗尽」不等于
        #   什么都没产出。以前 stop_reason 只写「走满 N 圈」，读者分不清
        #   「没东西可说」和「东西说完了但没收」。这里把本轮的显形量与
        #   「未生质量」如实带上。
        #   ★ 子句只在 stop_reason 以「体力耗尽」开头时追加，且**只追加一次**
        #     —— 防止两条通道各调一次收尾时重复叠加。
        if entry == "0" and (view.stop_reason or "").startswith("体力耗尽") \\
                and "未生质量" not in (view.stop_reason or ""):
            n_amp = len(view.amps or [])
            n_thr = len(view.threads or [])
            n_sus = len(view.suspensions or [])
            n_prb = len(view.probes or [])
            quality = _classify_unsaid(view)
            view.stop_reason = (
                f"{view.stop_reason}\\n"
                f"  本轮显形：& {n_amp} / 线头 {n_thr} / "
                f"悬置 {n_sus} / 探针 {n_prb}\\n"
                f"  未生质量：{quality}"
            )
            self.vp(f"   ⏹ {view.stop_reason}")

        # ---- 1. 把跨圈累积回填到 view ----
"""

# --------------------------------------------------------------- 3. header
OLD_HDR = "        for _ol in _layer_objective_lines():"
NEW_HDR = "        for _ol in _layer_objective_lines(result):"

# ------------------------------------------------------- 4. objective lines
OLD_SIG = "def _layer_objective_lines() -> List[str]:"
NEW_SIG = "def _layer_objective_lines(result=None) -> List[str]:"

OLD_BODY = """    out: List[str] = []
    for e in ("0", "1", "both", "all"):
        o = getattr(PHASES.get(e), "objective", "?")
"""

NEW_BODY = '''    if result is not None:
        # [v122 阶段1 G1.6] 完整版口径：四行是**计数**，objective 折进括号。
        #   任务书 Step 1.6 原文给的就是这四行；objective 单独列会让读者
        #   看不到「这一层这轮到底产出了什么」，所以两件事并进一行。
        _views = result.get("views") or {}
        _pools = result.get("pools") or {}

        def _g(k):
            return _views.get(k) or {}

        _p0, _p1 = _g("0"), _g("1")
        _pb, _pa = _g("both"), _g("all")
        out_c: List[str] = []
        out_c.append(
            f"  - 修行层（显形过程 · objective=manifest）："
            f"& {len(_p0.get('amps') or [])} / "
            f"线头 {len(_p0.get('threads') or [])} / "
            f"悬置 {len(_p0.get('suspensions') or [])} / "
            f"探针 {len(_p0.get('probes') or [])}")
        _st = _p1.get("settlement") or {}
        _cov = _st.get("coverage")
        _cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
        _dist = (_p1.get("decidable_product") or {}).get("distance", "?")
        out_c.append(
            f"  - 研究层（逼近真理 · objective=truth）："
            f"覆盖率 {_cov_s} · distance {_dist}")
        _pbi = _pb.get("ing_structured") or {}
        out_c.append(
            f"  - 对撞层（第三者 · objective=collision）："
            f"third {'\\u2713' if _pbi.get('third') else '\\u2717'} · "
            f"张力 {len(_pbi.get('tensions') or [])}")
        _clo = _pa.get("meta_closure") or {}
        out_c.append(
            f"  - 元层（闭环清算 · objective=closure）："
            f"clean {_clo.get('clean')} · "
            f"未交代 {_clo.get('unsettled', 0)} 类")
        return out_c

    out: List[str] = []
    for e in ("0", "1", "both", "all"):
        o = getattr(PHASES.get(e), "objective", "?")
'''

REPS = [
    ("classify", OLD_CLS, NEW_CLS, 1),
    ("stop_reason", OLD_STOP, NEW_STOP, 1),
    ("header_call", OLD_HDR, NEW_HDR, 1),
    ("obj_sig", OLD_SIG, NEW_SIG, 1),
    ("obj_body", OLD_BODY, NEW_BODY, 1),
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "主文件不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "主文件有 \\r\\r\\n"
    s = s.replace("\r\n", "\n")

    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点出现 {got} 次，期望 {want} 次"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    assert "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"✓ 阶段1b 补丁完成；行数 {len(b.decode('utf-8').splitlines())} → "
          f"{len(out.splitlines())}")

    import ast
    ast.parse(out.replace("\r\n", "\n"))
    print("  ✓ ast.parse OK")
    for must in ("修行层不追求收敛", "未生质量", "objective=manifest"):
        assert must in out, f"缺字面串 {must}"
    print("  ✓ 关键字面串齐备")
    return 0


if __name__ == "__main__":
    sys.exit(main())
