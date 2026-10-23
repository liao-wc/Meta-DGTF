#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变异测试探针 · v1.21.72（给新增的 4 条判据做**负对照**）

用法：
    python _probe_v72_mutants.py > _probe_v72_mutants.txt

为什么需要它：`check_v72_*` 里有几条是**前向守卫**（结构不变式），在
v1.21.72 自己身上必然通过 —— 「通过」不能证明它有判别力。这里把 5 种
**真实的畸形改法**分别注入引擎，再让对应的判据去跑，**每一条都必须判红**。

★ 手法：把 smoke_test.py 的**源码**读进来、只替换 `SRC = HERE / "…"`
那一行（断言恰好 1 处），再 `exec` 成独立 module —— 这样 `mod` 就是那份
**畸形引擎**，而判据函数是原样的。每个变异体一个独立 module，互不污染。
"""
import contextlib
import io
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
V72 = HERE / "元DGTF-V1.21.72.py"
V71 = HERE / "元DGTF-V1.21.71.py"
SMOKE = HERE / "smoke_test.py"
TMP = Path(tempfile.mkdtemp(prefix="probe72_mut_"))

src72 = V72.read_bytes().decode("utf-8").replace("\r\n", "\n")
smoke_txt = SMOKE.read_text(encoding="utf-8")
assert len(re.findall(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"', smoke_txt)) == 1


def _load(engine_path, tag):
    """把 smoke_test 的源码 + 指定引擎路径装成一个 module。"""
    txt = re.sub(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"',
                 'SRC = Path(r"%s")' % str(engine_path).replace("\\", "\\\\"),
                 smoke_txt, count=1)
    m = types.ModuleType("mut_" + tag)
    m.__file__ = str(SMOKE)
    sys.modules["mut_" + tag] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    return m


def _mutant(name, old, new):
    assert src72.count(old) == 1, f"{name}: 变异锚点命中 {src72.count(old)} 次"
    p = TMP / f"_mutant_{name}.py"
    p.write_bytes(src72.replace(old, new, 1).encode("utf-8"))
    return p


print("=" * 66)
print("## 变异测试（每条判据都必须对它的畸形体判红）")
print("=" * 66)

CASES = []

# ---- M1 · 把 B 模式「一起停」改成「只停第一层」 (#13) ----
M1 = _mutant("m1_truncate",
             """                for e in active:
                    st = self._b_state.get(e) or {}
                    if st.get("stopped"):
                        continue
                    st["stopped"] = True""",
             """                for e in active[:1]:
                    st = self._b_state.get(e) or {}
                    if st.get("stopped"):
                        continue
                    st["stopped"] = True""")
CASES.append(("M1 #13 一起停 → 只停一层", M1, "check_v72_bbarrier_semantics"))

# ---- M2 · 删掉 #13 那条注释 ----
M2 = _mutant("m2_nocomment", "                # [v1.21.72 #13] ★ 这里",
             "                # (注释被删) ★ 这里")
CASES.append(("M2 #13 注释被删", M2, "check_v72_bbarrier_semantics"))

# ---- M3 · 让关键机制出现第二份实现 (#22) ----
M3 = _mutant("m3_dupdef",
             "def _normalize_decidability(status, dec_aspects, und_aspects,",
             "_NORMALIZE_DUP = None\n\n\n"
             "def _normalize_decidability(status, dec_aspects,\n"
             "                            und_aspects: list = None,\n"
             "                            where: str = \"\"):\n"
             "    return status                 # ← 第二份实现（畸形体）\n\n\n"
             "def _normalize_decidability(status, dec_aspects, und_aspects,")
CASES.append(("M3 #22 机制出现第二份实现", M3,
              "check_v72_mechanism_single_source"))

# ---- M4 · 绕过 _cached_ext_assess 再直调一次 (#22 / F6 的唯一入口) ----
M4 = _mutant("m4_direct",
             """        try:
            # [v1.21.71 F6] 走运行内缓存：研究层拆解那一步会再要一次同题的
            #   外部评估，改前这一跑会打两遍（probe 站点计数 1 + 1）。
            ext = self._cached_ext_assess(question)""",
             """        try:
            _d_direct = DGTF("1", self.llm, self.config)
            ext = _d_direct._assess_decidability(question)""")
CASES.append(("M4 #22/F6 再直调一次外部评估", M4,
              "check_v72_mechanism_single_source"))

# ---- M5 · 复活旧门 (#22) ----
M5 = _mutant("m5_oldgate",
             "        if view is not None:\n"
             "            self._finalize_layer_common(entry, view, {",
             "        if view is not None and rounds_n > 1:\n"
             "            self._finalize_layer_common(entry, view, {")
CASES.append(("M5 #22 复活 serial 侧旧门", M5,
              "check_v72_mechanism_single_source"))

# ---- M6 · 把 changelog 段序改回颠倒（用真实的 v1.21.71）----
CASES.append(("M6 #20 指向 v1.21.71（段序颠倒 + 63 段重复）", V71,
              "check_v72_changelog_hygiene"))

ok = True
for tag, engine, fn in CASES:
    try:
        st = _load(engine, tag.split()[0].lower())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = getattr(st, fn)()
        verdict = "判红（对）" if r is False else "**判绿（错！）**"
        if r is not False:
            ok = False
        print(f"\n   {tag}")
        print(f"      → {fn}() = {r}   {verdict}")
        for ln in buf.getvalue().strip().splitlines():
            print(f"        {ln}")
    except Exception as e:                                   # noqa: BLE001
        ok = False
        print(f"\n   {tag}\n      → 判据抛异常（也应视为判红失败）："
              f"{type(e).__name__}: {e}")

print("\n" + "=" * 66)
print(f"## 结论：{'全部判红 —— 4 条判据都有判别力' if ok else '有判据没判红，需修'}")
print("=" * 66)
sys.exit(0 if ok else 1)
