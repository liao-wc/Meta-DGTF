#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P5 + P6] 补丁脚本。

改前 `元DGTF-V1.22.1-rc2.py` → 改后 `元DGTF-V1.22.1-rc3.py`（本脚本就地改 rc3）。

P5（auto 取向回填）：
  ① `auto_plan` 单调用分支：prompt 里一并要 `orientation`，并在三处 return 带出；
  ② `save_result`：渲染「取向判定（plan_orientation）」+ 「取向错配」告警；
  ③ `_pack_result`：挂 `_auto_plan_used`。

P6（tier 缺省提示）：
  ④ `_load_anchors`：在**原始条目**上数「显式声明 tier」的条数；全缺省 → 警告；
  ⑤ `save_result`：渲染「⚠️ 锚点 tier 警告」；
  ⑥ `_pack_result`：挂 `_anchor_tier_warning`。

★ 两处任务书前提与实现不符（已写进报告）：
  · `auto_plan` 的**单调用**分支（`run()` 走的就是它）不带 `orientation` ——
    `_auto_plan_used` 于是永远没有取向，P5 的头部行一行都印不出来。
  · P6 骨架拿 `out` 去数「谁没声明 tier」，而 `out` 里每条都补了 tier（缺省 3）
    → 计数恒为 0，警告永远不触发。正解是在**原始条目**上判。

幂等：已改过则打印「已应用」并退出 0。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("元DGTF-V1.22.1-rc3.py")
NL = chr(10)
CRLF = chr(13) + chr(10)
SENTINEL = "_anchor_tier_warning"

# ---------------------------------------------------------------- P5 ① prompt
OLD_PROMPT = '''            "严格 JSON：\\n"
            '{"mode":"serial|A|B|C|D|E|F|G|H",'
            '"rounds":{"0":n,"1":n,"both":n,"all":n},'
            '"reason":"≤80字","confidence":0.0-1.0}'
        )
'''
NEW_PROMPT = '''            "【取向】\\n"
            "  decision：要可落地的方案 / 取舍 / 怎么办\\n"
            "  boundary：要边界清单 / 判别标准 / 什么算数什么不算数\\n\\n"
            "严格 JSON：\\n"
            '{"mode":"serial|A|B|C|D|E|F|G|H",'
            '"orientation":"decision|boundary",'
            '"rounds":{"0":n,"1":n,"both":n,"all":n},'
            '"reason":"≤80字","confidence":0.0-1.0}'
        )
'''

# ------------------------------------------------------------- P5 ① 解析取向
OLD_PARSE = '''        conf = float(data.get("confidence", 0.0) or 0.0)
        reason = str(data.get("reason", ""))[:200]
'''
NEW_PARSE = '''        conf = float(data.get("confidence", 0.0) or 0.0)
        reason = str(data.get("reason", ""))[:200]
        # [v1.22.1 P5] 取向一并带出来。★ `run()` 走的是**单调用**这条路，
        #   而它原来只回 mode/rounds —— `_auto_plan_used` 于是**永远**没有
        #   orientation，P5 的头部「取向判定」行一行都印不出来。这里在
        #   **同一次调用**里把取向一起要出来（不加调用次数、不加成本）。
        _ori = str(data.get("orientation", "")).strip().lower()
        if _ori not in ("decision", "boundary"):
            _ori = ""
'''

# -------------------------------------------------------- P5 ① 三处 return
OLD_R_FAIL = '''            return {"mode": "serial", "rounds": {},
                    "reason": "调度失败，退回保守（圈数走配置）",
                    "confidence": 0.0}
'''
NEW_R_FAIL = '''            return {"mode": "serial", "rounds": {},
                    "reason": "调度失败，退回保守（圈数走配置）",
                    "orientation": "", "confidence": 0.0}
'''
OLD_R_LOW = '''            return {"mode": "serial", "rounds": rnd,
                    "reason": f"低置信({conf:.2f})，退回 serial：{reason}",
                    "confidence": conf}
'''
NEW_R_LOW = '''            return {"mode": "serial", "rounds": rnd,
                    "reason": f"低置信({conf:.2f})，退回 serial：{reason}",
                    "orientation": _ori, "confidence": conf}
'''
OLD_R_OK = '''        return {"mode": mode, "rounds": rnd, "reason": reason,
                "confidence": conf}
'''
NEW_R_OK = '''        return {"mode": mode, "rounds": rnd, "reason": reason,
                "orientation": _ori, "confidence": conf}
'''

# ------------------------------------------------- P5 ② / P6 ⑤ save_result
OLD_HEAD = '''                f.write(f"**取向**：{_or_disp}\\n\\n")
'''
NEW_HEAD = '''                f.write(f"**取向**：{_or_disp}\\n\\n")
            # [v1.22.1 P5] 取向**判定**留痕（plan_orientation 的真实结果）。
            #   此前只写「请求了什么取向」，判成了什么无处可查 —— 于是
            #   「auto 判成 boundary 却按 decision 渲染」这种错配没人看得见。
            _ap = result.get("_auto_plan_used") or {}
            if _ap.get("orientation"):
                f.write(f"**取向判定（plan_orientation）**："
                        f"{_ap['orientation']}"
                        f"（{str(_ap.get('_orientation_reason') or '')[:60]}）"
                        f"\\n\\n")
                _actual = str(_ap.get("orientation") or "").strip()
                _declared = str(result.get("orientation") or "auto").strip()
                if _declared == "auto" and _actual != "decision":
                    f.write(f"⚠️ **取向错配**：plan_orientation 判为 "
                            f"`{_actual}`，但 orientation 未指定（按 decision "
                            f"渲染）。如想用 boundary 模板，请显式传 "
                            f"`--orientation boundary`。\\n\\n")
            # [v1.22.1 P6] 锚点 tier 全缺省时的显式提示（不阻断，只告警）：
            #   缺省 3 > tier_floor 2 → 引用表一条都收不到，产物会静默地
            #   「看起来对照过了但没有锚点」。这一行让沉默变成可读。
            if result.get("_anchor_tier_warning"):
                f.write(f"⚠️ **锚点 tier 警告**："
                        f"{result['_anchor_tier_warning']}\\n\\n")
'''

# ------------------------------------------------------------- P5 ③ / P6 ⑥
OLD_PACK = '''            "orientation": str(getattr(self, "_orientation", "auto")),
'''
NEW_PACK = '''            "orientation": str(getattr(self, "_orientation", "auto")),
            # [v1.22.1 P5/P6] 自动调度的真实决策 + 锚点 tier 告警（留痕）。
            "_auto_plan_used": dict(getattr(self, "_auto_plan_used", None) or {}),
            "_anchor_tier_warning": str(
                getattr(self, "_anchor_tier_warning", "") or ""),
'''

# ------------------------------------------------------------ P6 ④ 检测
OLD_LOOP = '''        out: List[dict] = []
        for i, a in enumerate(raw[:max_items], 1):
'''
NEW_LOOP = '''        out: List[dict] = []
        _n_explicit_tier = 0     # [v1.22.1 P6] 显式声明 tier 的条数
        for i, a in enumerate(raw[:max_items], 1):
'''
OLD_TIER = '''            try:
                _t = int(a.get("tier", 3) or 3)
            except (TypeError, ValueError):
                _t = 3
'''
NEW_TIER = '''            try:
                _t = int(a.get("tier", 3) or 3)
            except (TypeError, ValueError):
                _t = 3
            # [v1.22.1 P6] 在**原始条目**上数「显式声明」。
            #   ★ 任务书骨架写的是 `"tier" in a and a["tier"] is not None`
            #     并且对 `out` 用 —— 但 `out` 里每条都补了 tier（缺省 3），
            #     于是计数恒为 0、警告永远不触发。必须在补默认值之前判。
            if str(a.get("tier") if a.get("tier") is not None else "").strip():
                _n_explicit_tier += 1
'''
OLD_TAIL = '''            logger.warning("锚点 answers 全部缺失：%s",
                           self._anchor_answers_warning)
        if not out:
'''
NEW_TAIL = '''            logger.warning("锚点 answers 全部缺失：%s",
                           self._anchor_answers_warning)
        # [v1.22.1 P6] 全部锚点未显式声明 tier → 缺省 3 > tier_floor 2，
        #   引用表一条都收不到。显式提示，**不阻断**（阻断会把「锚点没写 tier」
        #   变成致命错误，而它只是让对照空转）。
        if out and _n_explicit_tier == 0:
            self._anchor_tier_warning = (
                "全部 " + str(len(out)) + " 条锚点未显式声明 tier（缺省 3 > "
                "tier_floor " + str(_tier_floor(cfg)) + "），引用表将收不到任何"
                "锚点")
            logger.warning("锚点 tier 全部缺省：%s", self._anchor_tier_warning)
        else:
            self._anchor_tier_warning = ""
        if not out:
'''

# ------------------------------------------------------------ 属性初始化
OLD_INI_LOAD = '''        self._anchor_answers_warning = ""
'''
NEW_INI_LOAD = '''        self._anchor_answers_warning = ""
        self._anchor_tier_warning = ""
'''
OLD_INI_CLS = '''        self._anchor_answers_warning: str = ""
'''
NEW_INI_CLS = '''        self._anchor_answers_warning: str = ""
        # [v1.22.1 P6] 锚点 tier 全缺省时的告警（"" = 无告警）。
        self._anchor_tier_warning: str = ""
'''

REPS = [
    ("P5① auto_plan prompt 加取向", OLD_PROMPT, NEW_PROMPT),
    ("P5① 解析 orientation", OLD_PARSE, NEW_PARSE),
    ("P5① 失败早退带 orientation", OLD_R_FAIL, NEW_R_FAIL),
    ("P5① 低置信早退带 orientation", OLD_R_LOW, NEW_R_LOW),
    ("P5① 正常返回带 orientation", OLD_R_OK, NEW_R_OK),
    ("P5②+P6⑤ save_result 两行留痕", OLD_HEAD, NEW_HEAD),
    ("P5③+P6⑥ _pack_result 两个字段", OLD_PACK, NEW_PACK),
    ("P6④ 计数变量", OLD_LOOP, NEW_LOOP),
    ("P6④ 原始条目上判显式 tier", OLD_TIER, NEW_TIER),
    ("P6④ 全缺省告警", OLD_TAIL, NEW_TAIL),
    ("属性初始化（_load_anchors）", OLD_INI_LOAD, NEW_INI_LOAD),
    ("属性初始化（__init__）", OLD_INI_CLS, NEW_INI_CLS),
]


def main() -> int:
    raw = TARGET.read_bytes()
    s = raw.decode("utf-8")
    if SENTINEL in s:
        print("  · 已应用（幂等跳过）")
        return 0
    assert s.count(CRLF) == s.count(NL), "rc3 行尾不纯"
    assert b"\r\r\n" not in raw, "rc3 含 CRCRLF"
    s = s.replace(CRLF, NL)
    for name, old, new in REPS:
        # ★ 不要在这里做「转义还原」：OLD_*/NEW_* 是**普通三引号字符串**，
        #   脚本里写的 `\\n` 已经被 Python 解析成「反斜杠+n」两个字符，
        #   正是目标文件里需要的形态。再做一次 replace 会把它变成真换行，
        #   锚点就永远匹配不上了（本项目踩过一次「多级转义」的坑）。
        got = s.count(old)
        assert got == 1, "[" + name + "] 锚点命中 " + str(got) + " 次，期望 1"
        s = s.replace(old, new, 1)
        print("  ✓ " + name)
    ast.parse(s)
    out = s.replace(NL, CRLF)
    assert out.count(NL) == out.count(CRLF)
    assert "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print("  ✓ 写回 " + TARGET.name + "（纯 CRLF）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
