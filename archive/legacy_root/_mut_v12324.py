#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 变异体：证明 `check_v12324_indep_therapy` 真的有判别力。

做法（可复用）：把 `smoke_test.py` 的 `SRC` 那一行换成畸形体路径，
再把 smoke 源码 exec 成独立 module —— 每个畸形体一个 module，互不污染；
然后让**原样的判据函数**去跑，必须判红。

★ 变异体一律打在「判据读的那个东西」上（不是改判据的文案）：
  独立度算式 / 空池哨兵 / 条件 3 支路 / 条件 1 措辞 / 收尾门 /
  红线句 / 旧键不变式 / 口径标注。
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "元DGTF-V1.23.24.py"
SMOKE = HERE / "smoke_test.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

FREE = ('        _free_amps = [sa for sa in _amps_pool\n'
        '                      if not any(_overlap_coef(asp, sa) >= 0.3\n'
        '                                 for asp in aspects)]\n'
        '        indep_ratio = (len(_free_amps) / len(_amps_pool)\n'
        '                       if _amps_pool else None)')

MUTANTS = {
    # M1 · 独立度退回旧口径（命中方面数 / 方面数）
    "M1_caliber_back": [(
        FREE,
        '        _free_amps = [asp for asp in aspects\n'
        '                      if any(_overlap_coef(asp, sa) >= 0.3\n'
        '                             for sa in _amps_pool)]\n'
        '        indep_ratio = (len(_free_amps) / len(aspects)\n'
        '                       if aspects else None)',
    )],
    # M2 · 空池哨兵退成 0.0（用假读数冒充「不可计算」）
    "M2_empty_zero": [(
        '        indep_ratio = (len(_free_amps) / len(_amps_pool)\n'
        '                       if _amps_pool else None)',
        '        indep_ratio = (len(_free_amps) / len(_amps_pool)\n'
        '                       if _amps_pool else 0.0)',
    )],
    # M3 · 条件 3 砍掉 sat 支路（空括号回来）
    "M3_no_sat_branch": [(
        '            if stall_is_sat:\n'
        '                # sat 判「无新维度」时把 idle_stall 顶到门槛上 —— 那\n'
        '                # 不是「有新增但无推进」，照搬老模板会把空串印成\n'
        '                # `…无推进（）`。这一支有自己的说法。\n'
        '                reasons.append(\n'
        '                    f"连续 {idle_stall} 轮无新结构维度"\n'
        '                    f"（结构饱和度判定，不是新增停滞）")\n'
        '            else:\n'
        '                reasons.append(\n'
        '                    f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")',
        '            reasons.append(\n'
        '                f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")',
    )],
    # M4 · 条件 1 措辞退回「ing」（借对撞层的词）
    "M4_ing_back": [(
        '            _src.append(f"{_lyr}层连续 {rephrase_streak} 圈复述"\n'
        '                        f"（层内空转）")',
        '            _src.append(f"ing 连续 {rephrase_streak} 圈复述"\n'
        '                        f"（层内空转）")',
    )],
    # M5 · 收尾门退回「只认体力耗尽」
    "M5_finish_gate_back": [(
        '        if entry == "0" and (view.stop_reason or "").strip() \\\n'
        '                and "未生质量" not in (view.stop_reason or ""):',
        '        if entry == "0" and (view.stop_reason or "").startswith("体力耗尽") \\\n'
        '                and "未生质量" not in (view.stop_reason or ""):',
    )],
    # M6 · 新旧红线句互换
    "M6_redline_back": [(
        '        # ★ 修行层本来就能停 —— 要的不是「不许停」，是「停得合理」。',
        '        # ★ 修行层不追求收敛：不设停止判据。',
    )],
    # M7 · 旧键不变式被写坏
    "M7_old_key_broken": [(
        '        self.undecidable_channel["last_struct_coverage"] = struct_cov',
        '        self.undecidable_channel["last_struct_coverage"] = 0.99',
    )],
    # M8 · 渲染不再标口径（读者会把它当覆盖率）
    "M8_no_caliber_note": [(
        '                parts.append(f"独立度 {_iv:.2f}"\n'
        '                             f"（代码实算：独立结构 {_nfree}/{_npool} 条"\n'
        '                             f"不与评估阶段方面重合；这是「独立比例」，"\n'
        '                             f"不是覆盖率）")',
        '                parts.append(f"独立度 {_iv:.2f}"\n'
        '                             f"（代码实算：独立结构 {_nfree}/{_npool} 条）")',
    )],
}


def make_mutant(name, reps):
    txt = BASE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for old, new in reps:
        n = txt.count(old)
        assert n == 1, "%s：锚点命中 %d 次（不是 1）—— 变异体失效！" % (name, n)
        txt = txt.replace(old, new)
    p = TMP / ("mut_v12324_%s.py" % name)
    p.write_bytes(txt.replace("\n", "\r\n").encode("utf-8"))
    return p


def run_check(name, path):
    src = SMOKE.read_text(encoding="utf-8")
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
    assert len(pat.findall(src)) == 1, "smoke SRC 行不是 1 行"
    src = pat.sub(lambda m: 'SRC = Path(r"%s")' % str(path), src, count=1)
    hm = types.ModuleType("harness_" + name)
    hm.__file__ = str(SMOKE)
    sys.modules[hm.__name__] = hm
    exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
    try:
        return hm.check_v12324_indep_therapy()
    except Exception as e:  # noqa: BLE001
        return "EXC:%s: %s" % (type(e).__name__, e)


def main():
    print("=" * 66)
    print("正对照 · 原版 v1.23.24 必须判绿")
    print("=" * 66)
    ok = run_check("clean", BASE)
    print("  clean ⇒ %r" % (ok,))
    assert ok is True, "正对照失败：原版都判红，判据没意义"

    print("")
    print("=" * 66)
    print("变异体 · 每个都必须判红")
    print("=" * 66)
    red = 0
    for name, reps in MUTANTS.items():
        p = make_mutant(name, reps)
        r = run_check(name, p)
        if r is True:
            print("  ✗ %-22s 判绿 —— 判据没测到它！" % name)
        else:
            red += 1
            print("  ✓ %-22s 判红 (%s)" % (name, r))
    print("")
    print("MUTANTS: %d/%d 判红" % (red, len(MUTANTS)))
    return 0 if red == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
