# -*- coding: utf-8 -*-
"""v1.23.25 的 smoke_test.py 判据同步补丁。

改动：
  ① SRC → v1.23.25
  ② check_v12324_indep_therapy 的 A 段：新渲染现在**确实**印「结构覆盖率」
     （这是本版的重设计，不是回归）⇒ 那条 `"结构覆盖率" in _line` 的
     否定断言必须改成「新口径 + 旧口径各自渲染正确」。
  ③ 新增 check_v12325_struct_coverage()：
     A. 自触及算式（含负对照、空池 None、与独立度正交）
     B. 产物渲染三读数并列
     C. shape 喂模型
     D. 源码接线
  ④ 注册新判据。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\r\n") == 0, "已有 \\r\\r\\n"
    assert b.count(b"\r\n") == b.count(b"\n"), "不是纯 CRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def write_crlf(p: Path, txt: str) -> None:
    assert "\r" not in txt
    p.write_bytes(txt.replace("\n", "\r\n").encode("utf-8"))
    chk = p.read_bytes()
    assert chk.count(b"\r\r\n") == 0
    assert chk.count(b"\r\n") == chk.count(b"\n")


T = read_crlf(SMOKE)
_n = 0


def rep(a: str, b: str, tag: str) -> None:
    global T, _n
    c = T.count(a)
    assert c == 1, f"[{tag}] 命中 {c} 次（期望 1）：\n{a[:250]}"
    T = T.replace(a, b, 1)
    _n += 1
    print(f"  ok [{tag}]")


print("=" * 78)
print("smoke_test.py 判据同步（v1.23.25）")
print("=" * 78)

# ---------------------------------------------------------- ① SRC
rep('SRC = HERE / "元DGTF-V1.23.24.py"',
    'SRC = HERE / "元DGTF-V1.23.25.py"',
    tag="SRC 指向 v1.23.25")

# ---------------------------------------------------------- ② A 段渲染断言
rep(
    '    if "不是覆盖率" not in _line:\n'
    '        bad.append(f"[A] 口径标注（不是覆盖率）缺了：{_line!r}")\n'
    '    if "结构覆盖率" in _line:\n'
    '        bad.append(f"[A] 新口径 dict 还在印「结构覆盖率」：{_line!r}")\n',
    '    if "不是覆盖率" not in _line:\n'
    '        bad.append(f"[A] 口径标注（不是覆盖率）缺了：{_line!r}")\n'
    '    # ★ v1.23.25 起「结构覆盖率」是**重设计后的合法读数**（自触及），\n'
    '    #   不再是误名 ⇒ 这条否定断言反过来：新口径 dict 里\n'
    '    #   `sc_history` 不存在时不许印，存在时必须印（见 B 段）。\n'
    '    if "sc_history" not in _ch and "结构覆盖率" in _line:\n'
    '        bad.append(f"[A] 无 sc_history 时不该印结构覆盖率：{_line!r}")\n',
    tag="A 段·结构覆盖率否定断言改写")

# ---------------------------------------------------------- ③ 新增判据函数
_NEW_FN = '''

def check_v12325_struct_coverage():
    """[v1.23.25] 「结构覆盖率」按它**本来的视角（结构侧）**重设计：
       结构被研究出自己触及的概率。

    ★ 三轮诊断（六个候选凭据全排除）见 v12325_报告.md §2。
    ★ 判别力：旧口径恒 0.000，新口径 0.143~1.000。
    ★ 正交：与「独立度」Pearson r ≈ 0.13（夹具下独立度恒 1.000、
      结构覆盖率可变）。
    """
    import inspect as _ins
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    cfg = build_cfg(False)

    # ================= A. 自触及算式 =================
    _S = ["结构甲：前台按钮与后台提示不可同时满足",
          "结构乙：时间差两端不可折中",
          "结构丙：两域可改性不同，合问为假"]
    _p = mod.Pool()
    _p.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.7},
        und_aspects=["世界本身是否虚拟"], layer=1, covered_aspects=[])
    _ch = _p.undecidable_channel
    if _ch.get("last_sc_ratio") != 0.0 or _ch.get("last_sc_touched") != 0:
        bad.append(f"[A] 首圈（无下游文本）应为 0.00："
                   f"sc={_ch.get('last_sc_ratio')} "
                   f"touched={_ch.get('last_sc_touched')}")
    if _ch.get("last_sc_pool") != 3:
        bad.append(f"[A] 分母不是 3：{_ch.get('last_sc_pool')}")
    # 加一条呼应「结构乙」的线头 ⇒ 1/3
    _p.threads.append({"desc": "时间差两端不可折中的实例仍未取到，悬空",
                       "kind": "thread", "polarity": "0"})
    _p.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.8},
        und_aspects=[], layer=2, covered_aspects=[])
    _ch = _p.undecidable_channel
    if abs(float(_ch.get("last_sc_ratio") or -1) - 1 / 3) > 1e-9:
        bad.append(f"[A] 自触及不是 1/3：{_ch.get('last_sc_ratio')}")
    if _ch.get("last_sc_touched") != 1:
        bad.append(f"[A] touched 不是 1：{_ch.get('last_sc_touched')}")
    if list(_ch.get("sc_history") or []) != [0.0, 1 / 3]:
        bad.append(f"[A] sc_history 不对：{_ch.get('sc_history')}")
    # ★ 不变式：旧键一个数不许动（历史语料的口径 + 命中轨迹的输入）
    if _ch.get("last_struct_coverage") != 0.0:
        bad.append(f"[A] 旧键 last_struct_coverage 被动了："
                   f"{_ch.get('last_struct_coverage')}（应 0.0）")
    # ★ 正交：线头不该影响独立度（独立度只看与 und_aspects 的重合）
    if abs(float(_ch.get("last_indep_ratio") or -1) - 1.0) > 1e-9:
        bad.append(f"[A] 独立度被线头影响了（应仍 1.000）："
                   f"{_ch.get('last_indep_ratio')}")
    # 空池：None（不可计算），不许 0.0
    _pe = mod.Pool()
    _pe.add_undecidable({"structural_amps": [], "aligned_amps": [],
                         "clarity": 0.5}, und_aspects=[], layer=1,
                        covered_aspects=[])
    if _pe.undecidable_channel.get("last_sc_ratio") is not None:
        bad.append(f"[A] 空池的结构覆盖率不是 None："
                   f"{_pe.undecidable_channel.get('last_sc_ratio')}")
    # 负对照：线头跟所有结构都不搭 ⇒ 必须掉回 0.00
    _pn = mod.Pool()
    _pn.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.5},
        und_aspects=[], layer=1, covered_aspects=[])
    _pn.threads.append({"desc": "量子引力中的时间箭头问题仍未解",
                        "kind": "thread"})
    _pn.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.5},
        und_aspects=[], layer=2, covered_aspects=[])
    _cn = _pn.undecidable_channel
    if _cn.get("last_sc_touched") != 0 or _cn.get("last_sc_ratio") != 0.0:
        bad.append(f"[A-负对照] 不搭的线头竟算作触及："
                   f"touched={_cn.get('last_sc_touched')} "
                   f"sc={_cn.get('last_sc_ratio')}")

    # ================= B. 产物渲染三读数并列 =================
    _mg = mod.MetaDGTF(cfg)
    _mg.pools["1"].undecidable_channel = _ch
    _line = _mg._und_channel_line()
    if "结构覆盖率 0.33" not in _line:
        bad.append(f"[B] 产物没渲染结构覆盖率：{_line!r}")
    if "1/3 条结构被后续圈" not in _line:
        bad.append(f"[B] 结构覆盖率的分子分母没渲染：{_line!r}")
    if "独立度 1.00" not in _line:
        bad.append(f"[B] 三读数没并列（缺独立度）：{_line!r}")
    # ★ 三读数必须**同现**在同一行（v1.23.25 的验收点）
    for _k in ("清晰度", "独立度", "结构覆盖率"):
        if _k not in _line:
            bad.append(f"[B] 三读数缺「{_k}」：{_line!r}")
    # 口径标注：不许把「结构覆盖率」说成「方面被覆盖」
    if "量的是「结构有多活」" not in _line:
        bad.append(f"[B] 口径标注（结构有多活）缺了：{_line!r}")
    # 无结构时印「—」，不许印 0.00
    _m2 = mod.MetaDGTF(cfg)
    _m2.pools["1"].undecidable_channel = dict(
        _pe.undecidable_channel, clarity_history=[0.5])
    _l2 = _m2._und_channel_line()
    if "结构覆盖率 —" not in _l2 or "结构覆盖率 0.00" in _l2:
        bad.append(f"[B] 无结构时应印「—」不是 0.00：{_l2!r}")

    # ================= C. shape 喂模型 =================
    if "不可判定结构覆盖率" not in src:
        bad.append("[C] 终端渲染没接结构覆盖率")

    # ================= D. 源码接线 =================
    if src.count("def _und_self_touch_texts(self)") != 1:
        bad.append("[D] _und_self_touch_texts 不是唯一实现")
    if src.count('"sc_history"') < 2:
        bad.append(f"[D] sc_history 接线点太少："
                   f"{src.count(chr(34) + 'sc_history' + chr(34))}")
    if "covered_aspects: Optional[List[str]] = None" not in src:
        bad.append("[D] add_undecidable 没接 covered_aspects 形参")
    _sig = _ins.signature(mod.Pool.add_undecidable).parameters
    if "covered_aspects" not in _sig:
        bad.append("[D] add_undecidable 签名里没有 covered_aspects")

    if bad:
        for b in bad:
            print(f"  ✗ [v12325] {b}")
        return False
    print("  \\u2713 [v12325] 结构覆盖率重设计（自触及）+ 三读数并列 / "
          "空池 None / 独立度正交 / 负对照 / 源码接线")
    return True
'''

rep(
    '\ndef check_v12324_indep_therapy():',
    _NEW_FN.rstrip("\n") + '\n\n\ndef check_v12324_indep_therapy():',
    tag="新增 check_v12325_struct_coverage",
)

# ---------------------------------------------------------- ④ 注册
rep(
    '    if not check_v12324_indep_therapy():\n'
    '        return 1\n',
    '    if not check_v12324_indep_therapy():\n'
    '        return 1\n'
    '    if not check_v12325_struct_coverage():\n'
    '        return 1\n',
    tag="注册新判据",
)

write_crlf(SMOKE, T)
print("-" * 78)
print(f"共 {_n} 处改动；已写回 smoke_test.py")

# ---------------------------------------------------------- 自检
import ast
_t = read_crlf(SMOKE)
ast.parse(_t)
print("  [1] AST 解析通过 ✓")
assert 'SRC = HERE / "元DGTF-V1.23.25.py"' in _t
print("  [2] SRC 指向 v1.23.25 ✓")
assert "def check_v12325_struct_coverage():" in _t
assert "if not check_v12325_struct_coverage():" in _t
print("  [3] 新判据定义 + 注册 ✓")
assert '"sc_history" not in _ch and "结构覆盖率" in _line' in _t
print("  [4] A 段否定断言已改写 ✓")
print(f"  行数 {_t.count(chr(10))}")
print("=" * 78)
