#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.25 变异体：证明 `check_v12325_struct_coverage` 真的有判别力。

做法（沿用 v1.23.24 的可复用套路）：把 `smoke_test.py` 的 `SRC` 行换成
畸形体路径，把 smoke 源码 exec 成独立 module —— 每个畸形体一个 module，
互不污染；然后让**原样的判据函数**去跑，必须判红（正对照跑真文件判绿）。

★ 变异体一律打在「判据读的那个东西」上，不是改判据的文案：
  ① 自触及算式（阈值 0.3 → 0.99 = 永不命中）
  ② 自触及分子（换成「与 und_aspects 重合」= 退回旧语义）
  ③ 空池哨兵（None → 0.0 冒充读数）
  ④ 分母（结构数 → 方面数 = 退回旧分母）
  ⑤ 下游文本池（拿掉 threads = 凭据缺一）
  ⑥ 渲染（结构覆盖率整行不印）
  ⑦ 旧键不变式（把 last_struct_coverage 也跟着改成新值）
  ⑧ 正交性（让线头影响独立度）
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "元DGTF-V1.23.25.py"
SMOKE = HERE / "smoke_test.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 变异体定义
_TOUCH_CALC = (
    '        _downstream = self._und_self_touch_texts()\n'
    '        _touched = [sa for sa in _amps_pool\n'
    '                    if any(t and _overlap_coef(sa, t) >= 0.3\n'
    '                           for t in _downstream)]\n'
    '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
    '                    if _amps_pool else None)\n'
)

MUTANTS = {

    # ① 阈值抬到 0.99 ⇒ 永不命中 ⇒ 恒 0
    "M1_阈值0.99": (
        '                    if any(t and _overlap_coef(sa, t) >= 0.3\n',
        '                    if any(t and _overlap_coef(sa, t) >= 0.99\n',
    ),

    # ② 分子换成「与 und_aspects 重合」⇒ 退回旧语义（方向相反）
    "M2_分子退回方面重合": (
        _TOUCH_CALC,
        '        _downstream = self._und_self_touch_texts()\n'
        '        _touched = [sa for sa in _amps_pool\n'
        '                    if any(_overlap_coef(asp, sa) >= 0.3\n'
        '                           for asp in aspects)]\n'
        '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
        '                    if _amps_pool else None)\n',
    ),

    # ③ 空池哨兵 None → 0.0（冒充读数）
    "M3_空池记0": (
        '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
        '                    if _amps_pool else None)\n',
        '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
        '                    if _amps_pool else 0.0)\n',
    ),

    # ④ 分母换成方面数（退回旧分母）
    "M4_分母换成方面数": (
        '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
        '                    if _amps_pool else None)\n',
        '        sc_ratio = (len(_touched) / len(aspects)\n'
        '                    if aspects else None)\n',
    ),

    # ⑤ 下游文本池拿掉 threads（凭据缺一）
    "M5_凭据缺threads": (
        '        for t in (self.threads or []):\n'
        '            s = str(t.get("desc", "")).strip()\n'
        '            if s:\n'
        '                out.append(s)\n'
        '            w = str(t.get("polarity_why", "")).strip()\n'
        '            if w:\n'
        '                out.append(w)\n',
        '        for t in (self.threads or []):\n'
        '            pass\n',
    ),

    # ⑥ 渲染整行不印
    "M6_不渲染": (
        '        if "sc_history" in ch and ch.get("last_sc_ratio") is not None:\n',
        '        if False and "sc_history" in ch:\n',
    ),

    # ⑦ 旧键不变式：让 last_struct_coverage 也跟着变
    "M7_旧键被改": (
        '        self.undecidable_channel["last_sc_ratio"] = sc_ratio\n',
        '        self.undecidable_channel["last_sc_ratio"] = sc_ratio\n'
        '        self.undecidable_channel["last_struct_coverage"] = sc_ratio\n',
    ),

    # ⑧ 正交性破坏：让线头也影响独立度
    "M8_线头影响独立度": (
        '        indep_ratio = (len(_free_amps) / len(_amps_pool)\n'
        '                       if _amps_pool else None)\n',
        '        indep_ratio = (len(_free_amps) / max(1, len(_amps_pool)\n'
        '                       + len(self._und_self_touch_texts()))\n'
        '                       if _amps_pool else None)\n',
    ),
}


def _load_smoke_with(src_path: Path, tag: str):
    """把 smoke 源码的 SRC 指到 src_path，exec 成独立 module。

    ★ SRC 必须换成**绝对路径**：畸形体写在 `_audit_tmp/` 下，而 smoke 里的
      `HERE` 是仓库根 ⇒ `HERE / "<畸形体名>"` 指不到，会 FileNotFoundError
      ——那是「路径错」冒充的判红，等于没跑。v1.23.25 第一版就栽在这。
    """
    txt = SMOKE.read_text(encoding="utf-8")
    _abs = src_path.resolve().as_posix()
    _old_line = re.search(r'^SRC = .*$', txt, flags=re.M).group(0)
    txt = re.sub(r'^SRC = .*$', f'SRC = Path(r"{_abs}")',
                 txt, count=1, flags=re.M)
    assert _abs in txt, "SRC 替换失败"
    if src_path.exists() is False:
        raise FileNotFoundError(f"变异体文件不存在：{src_path}")
    assert _old_line, "SRC 原行没取到"
    mod_name = f"_smoke_{tag}"
    m = types.ModuleType(mod_name)
    m.__file__ = str(SMOKE)
    sys.modules[mod_name] = m
    code = compile(txt, str(SMOKE), "exec")
    exec(code, m.__dict__)
    return m


def _run_check(m):
    """跑新判据 + v1.23.24 那条（旧断言改写后也要一起成立）。"""
    r25 = m.check_v12325_struct_coverage()
    r24 = m.check_v12324_indep_therapy()
    return r25, r24


print("=" * 82)
print("v1.23.25 变异体（打自触及算式 / 凭据 / 渲染 / 不变式）")
print("=" * 82)

# ---- 正对照：真文件必须判绿 ----
print("\n[正对照] 真文件（无变异）")
_m = _load_smoke_with(BASE, "ctrl")
_r25, _r24 = _run_check(_m)
assert _r25, "★ 正对照失败：真文件下 check_v12325_struct_coverage 没判绿"
assert _r24, "★ 正对照失败：真文件下 check_v12324_indep_therapy 没判绿"
print("  ✓ 两条判据都判绿（正对照成立 → 后面的判红才是变异体造成的）")

# ---- 各变异体 ----
passed = 0
failed = []
for tag, (old, new) in MUTANTS.items():
    src = BASE.read_text(encoding="utf-8").replace("\r\n", "\n")
    cnt = src.count(old)
    if cnt != 1:
        failed.append(f"{tag}: 锚点命中 {cnt} 次（期望 1）")
        print(f"  ✗ {tag}: 锚点命中 {cnt} 次")
        continue
    src = src.replace(old, new, 1)
    out = TMP / f"_mut_v12325_{tag}.py"
    out.write_text(src, encoding="utf-8")

    print(f"\n[{tag}]")
    try:
        _mm = _load_smoke_with(out, tag)
        _a, _b = _run_check(_mm)
    except Exception as e:  # noqa: BLE001
        # ★ 抛错**不算判红**：那只说明畸形体没被加载起来（多半是锚点/路径问题），
        #   判据根本没执行 ⇒ 得不到「有判别力」的结论。必须当失败。
        failed.append(f"{tag}: 加载/执行抛错（不是判红）：{type(e).__name__}: {e}")
        print(f"  ✗ 加载/执行抛错 ⇒ 判据没跑，不能算判红：{type(e).__name__}: {e}")
        continue
    if _a and _b:
        failed.append(f"{tag}: 两条判据都判绿 ⇒ 变异体没被发现")
        print("  ✗ 没被发现（两条判据都判绿）")
    else:
        which = []
        if not _a:
            which.append("v12325")
        if not _b:
            which.append("v12324")
        print(f"  ✓ 判红（{'/'.join(which)}）")
        passed += 1

print()
print("=" * 82)
print(f"变异体判红：{passed} / {len(MUTANTS)}")
if failed:
    for f in failed:
        print(f"  ✗ {f}")
    sys.exit(1)
print("★ 全部变异体判红 + 正对照判绿 ⇒ 判据有判别力")
print("=" * 82)
