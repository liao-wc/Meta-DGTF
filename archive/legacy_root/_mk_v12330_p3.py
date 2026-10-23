#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 3 阶段：LDG 渲染与注入。

· 头部新增「层职责（LDG）」块 —— 每层 S/C/R + 缺核心项 + 交付比。
· 落地层新增「未答的核心问项」节（点名，而不是让读者以为都答了）。
· `distance_to_question` 渲染条件 `<1.0` → `is not None`（缺省不印）。
· `_duty_carry` 注入后续层的 carry 约束（core 问项喂回）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    # 1) 头部「层职责（LDG）」块
    old_h = '''        f.write("**分层目标**：\\n")
        for _ol in _layer_objective_lines(result):
            f.write(f"{_ol}\\n")
        f.write("\\n")'''
    new_h = '''        f.write("**分层目标**：\\n")
        for _ol in _layer_objective_lines(result):
            f.write(f"{_ol}\\n")
        f.write("\\n")
        # ★ [LDG] 每层「到底替原始问题干了什么」—— 在**停止/收敛处**算的
        #   读数（C 覆盖 / R 相关 / S 调和平均）。★ 它是读数不是分数：
        #   低于门槛只做两件事 —— 改署名（不许说自然安住）+ 点名缺的 core。
        _duty_lines = []
        for _e in ("0", "1", "both", "all"):
            _vv = (result.get("views") or {}).get(_e) or {}
            _dd = _vv.get("duty") or {}
            if not _dd:
                continue
            _mark = "⚠ " if _dd.get("short") else ""
            _duty_lines.append(
                f"  - {_LAYER_LABEL.get(_e, _e)}层：{_mark}{duty_short_line(_dd)}")
            _tr = _vv.get("duty_trace") or []
            if len(_tr) >= 2:
                _duty_lines.append(
                    "      ↳ 逐圈 S：" + " → ".join(
                        f"{float(t.get('S', 0)):.2f}" for t in _tr))
        if _duty_lines:
            f.write("**层职责（LDG · 停止处实算）**：\\n")
            for _dl in _duty_lines:
                f.write(f"{_dl}\\n")
            f.write("\\n")'''
    s = rep(s, old_h, new_h, "头部 LDG 块")

    # 2) distance 渲染：缺省不印（两处）
    old_d = '''        if view.distance_to_question < 1.0:
            parts.append(f"【综合距离】distance_to_question={view.distance_to_question:.2f}")'''
    new_d = '''        # ★ [LDG 修真] 只有**真拿到**读数才印（缺省 None = 模型没报，
        #   不许印 1.00 冒充「离得最远」）。
        if view.distance_to_question is not None:
            parts.append(
                f"【综合距离】distance_to_question="
                f"{float(view.distance_to_question):.2f}")'''
    s = rep(s, old_d, new_d, "distance 渲染（manifest）")

    old_d2 = '''        if view.distance_to_question < 1.0:
            lines += ["", f"【综合距离】{view.distance_to_question:.2f}"]'''
    new_d2 = '''        # ★ [LDG 修真] 同上：缺省不印。
        if view.distance_to_question is not None:
            lines += ["", f"【综合距离】"
                          f"{float(view.distance_to_question):.2f}"]'''
    s = rep(s, old_d2, new_d2, "distance 渲染（lines）")

    # 3) 落地层「未答的核心问项」节（插在「六、如果只能做一件事」之前）
    old_l = '''    out.append("\\n### 六、如果只能做一件事\\n")'''
    new_l = '''    # ★ [LDG] 未答的核心问项 —— **点名**，而不是让读者以为都答了。
    #   来源：各层职责读数里 `missing_core` 的并集（去重保序）。
    try:
        _miss_all = []
        for _e in ("0", "1", "both", "all"):
            _dd = ((result.get("views") or {}).get(_e) or {}).get("duty") or {}
            for _m in (_dd.get("missing_core") or []):
                if _m and _m not in _miss_all:
                    _miss_all.append(_m)
        if _miss_all:
            out.append("\\n### ★ 未答的核心问项（守卫实算·点名）\\n")
            out.append("> 这些是问项的 **core 档**（主问，不含附加目标）"
                       "在四层交付面里**没有被正面回答**的部分。\\n")
            out.append("> 列在这里不是「失败了」，是不许假装答过 —— "
                       "按红线「悬置不打分」。\\n")
            for _m in _miss_all[:8]:
                out.append(f"- ⚠ {_m}")
    except Exception:
        pass
    out.append("\\n### 六、如果只能做一件事\\n")'''
    s = rep(s, old_l, new_l, "落地层未答问项节")

    # 4) duty carry 注入后续层
    old_c = '''    def _build_inp_base(self, s, role="", rno=0, entry="0", carry=None):
        return Input(
            question=self._question,
            seed_probes=s,
            carry_constraints=list(carry or []),'''
    new_c = '''    def _build_inp_base(self, s, role="", rno=0, entry="0", carry=None):
        # ★ [LDG 补救] 前面某层判定「职责未尽」时，其缺失的 core 问项
        #   在这里并入 carry 约束 ⇒ 后续层被**定向**提醒「这几项还没答」。
        #   对应 NAACL'25「core 子问题喂回生成器」（实测胜率 74%）；
        #   本仓库不重跑本层（不浪费预算、不掩盖），只让下游带着它走。
        _carry_all = list(carry or [])
        try:
            for _q in (getattr(self, "_duty_carry", None) or []):
                _carry_all.append({"question": str(_q)[:80],
                                   "kind": "duty_missing_core",
                                   "banned": []})
        except Exception:
            pass
        return Input(
            question=self._question,
            seed_probes=s,
            carry_constraints=_carry_all,'''
    s = rep(s, old_c, new_c, "duty carry 注入")

    _save(s)
    print("OK 第 3 阶段（LDG 渲染与注入）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "**层职责（LDG · 停止处实算）**" in s2
    assert "未答的核心问项（守卫实算·点名）" in s2
    assert s2.count("distance_to_question is not None") == 2
    assert 'kind": "duty_missing_core"' in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
