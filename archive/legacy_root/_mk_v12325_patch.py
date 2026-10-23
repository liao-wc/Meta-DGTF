# -*- coding: utf-8 -*-
"""v1.23.25 打补丁脚本（方案：结构覆盖率 = 结构被研究出自己触及的概率）。

【本版主题】把「结构覆盖率」按它**本来的视角（结构侧）**重新设计并加回去。

【三轮诊断（为什么旧算式救不回来）】
  六个候选凭据全部**实测排除**（见 v12325_报告.md §2）：
    ① structural_amps 撞 und_aspects  → overlap ≤ 0.17，从不命中
    ② aligned_amps    撞 und_aspects  → 命中，但已被「对齐覆盖率」占用
    ③ covered_aspects 撞 und_aspects  → 命中，但真数据里是 aligned 的子集
    ④ struct_trace[].newly            → 依赖①，全空
    ⑤ amp.polarity                    → 100% 填充，零判别力
    ⑥ A# 引用（_citation_table）      → 实测引用数 0（模型只引 C#）

【新算式（本版落地）—— 自触及】
  结构覆盖率 = |后续圈自己的产物（线头 / 探针 / 自报触及）里
                再次呼应到的 structural_amps| / |structural_amps|
  · 「自触及」：这条结构写完之后，**研究过程自己还碰它吗**。
  · 分母 = 结构数（与独立度**同分母**）
  · 视角正交：独立度数「有多**新**」（不与评估阶段的疑问重合），
    结构覆盖率数「有多**活**」（后续圈还碰它）。
    实测 Pearson r = 0.130（近独立）⇒ 两读数真区分。
  · 阈值 `_overlap_coef >= 0.3`（全局判「重合」口径）。

【实测信号（真产物 7 份）】
  自触及率范围 0.143 ~ 1.000（有跨度、有区分力），
  旧值恒 0.000 ⇒ 新旧口径必不同。

【旧键一字不动】last_struct_coverage / struct_coverage_history /
  last_struct_hit / struct_trace。

用法： python _mk_v12325_patch.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.25.py"
APP = "元DGTF-V1.23.25.py"
OLD_VER = "v1.23.24"
NEW_VER = "v1.23.25"
OV = OLD_VER.split("v")[1]
NV = NEW_VER.split("v")[1]

if not SRC.exists():
    sys.exit(f"缺主文件：{SRC}")


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    crlf, lf, crcrlf = b.count(b"\r\n"), b.count(b"\n"), b.count(b"\r\r\n")
    assert crcrlf == 0, f"{p.name} 已有 \\r\\r\\n：{crcrlf}"
    assert crlf == lf, f"{p.name} 不是纯 CRLF：CRLF={crlf} LF={lf}"
    return b.decode("utf-8").replace("\r\n", "\n")


def write_crlf(p: Path, txt: str) -> None:
    assert "\r" not in txt, "待写文本里残留 \\r"
    b = txt.replace("\n", "\r\n").encode("utf-8")
    p.write_bytes(b)
    chk = p.read_bytes()
    assert chk.count(b"\r\r\n") == 0, "写回后出现 \\r\\r\\n"
    assert chk.count(b"\r\n") == chk.count(b"\n"), "写回后不是纯 CRLF"


TXT = read_crlf(SRC)
_n = 0


def rep(anchor: str, new: str, *, expect: int = 1, tag: str = "") -> None:
    global TXT, _n
    cnt = TXT.count(anchor)
    assert cnt == expect, (
        f"[{tag}] 锚点命中 {cnt} 次（期望 {expect}）：\n{anchor[:300]}")
    TXT = TXT.replace(anchor, new, expect)
    _n += 1
    print(f"  ok [{tag}]")


print("=" * 78)
print(f"{NEW_VER} 打补丁 · 结构覆盖率 = 结构被研究出自己触及的概率")
print("=" * 78)

# ------------------------------------------------ ① 版本号
rep(f"元 DGTF · {OLD_VER}\n", f"元 DGTF · {NEW_VER}\n", tag="版本号·标题")
rep(f'__version__ = "{OV}"', f'__version__ = "{NV}"', tag="版本号·__version__")

# ------------------------------------------------ ② 新键初始化
rep(
    '                "last_indep_ratio": None, "last_indep_pool": 0,\n'
    '                "last_indep_free": 0, "indep_history": [],\n',
    '                "last_indep_ratio": None, "last_indep_pool": 0,\n'
    '                "last_indep_free": 0, "indep_history": [],\n'
    '                "last_sc_ratio": None, "last_sc_pool": 0,\n'
    '                "last_sc_touched": 0, "sc_history": [],\n'
    '                "sc_touched_amps": [],\n',
    tag="初始化·结构覆盖率新键",
)

# ------------------------------------------------ ③ 自触及计算
rep(
    '        self.undecidable_channel["last_indep_ratio"] = indep_ratio\n'
    '        self.undecidable_channel["last_indep_pool"] = len(_amps_pool)\n'
    '        self.undecidable_channel["last_indep_free"] = len(_free_amps)\n'
    '        self.undecidable_channel.setdefault("indep_history", []).append(\n'
    '            indep_ratio)\n',
    '        self.undecidable_channel["last_indep_ratio"] = indep_ratio\n'
    '        self.undecidable_channel["last_indep_pool"] = len(_amps_pool)\n'
    '        self.undecidable_channel["last_indep_free"] = len(_free_amps)\n'
    '        self.undecidable_channel.setdefault("indep_history", []).append(\n'
    '            indep_ratio)\n'
    '\n'
    '        #  ★ 结构覆盖率（重设计）＝**自触及**：一条结构性 & 写完之后，\n'
    '        #    研究过程**自己还碰不碰它**。分子 = 被「后续圈自己的产物」\n'
    '        #    再次呼应的结构条数，分母 = 结构总条数。\n'
    '        #    ★ 凭据只取**研究层自己产出的文本**（线头 / 探针 / 自报触及），\n'
    '        #      不取评估阶段的 und_aspects，也不取 evidence 引用——\n'
    '        #      后者实测 A# 引用为 0（模型只引 C#），前者方向相反。\n'
    '        #    ★ 与「独立度」同分母、不同视角：独立度数「有多新」，\n'
    '        #      本读数数「有多活」。实测两者 Pearson r ≈ 0.13（正交）。\n'
    '        _downstream = self._und_self_touch_texts()\n'
    '        _touched = [sa for sa in _amps_pool\n'
    '                    if any(t and _overlap_coef(sa, t) >= 0.3\n'
    '                           for t in _downstream)]\n'
    '        sc_ratio = (len(_touched) / len(_amps_pool)\n'
    '                    if _amps_pool else None)\n'
    '        self.undecidable_channel["last_sc_ratio"] = sc_ratio\n'
    '        self.undecidable_channel["last_sc_pool"] = len(_amps_pool)\n'
    '        self.undecidable_channel["last_sc_touched"] = len(_touched)\n'
    '        self.undecidable_channel["sc_touched_amps"] = [\n'
    '            s[:120] for s in _touched]\n'
    '        self.undecidable_channel.setdefault("sc_history", []).append(\n'
    '            sc_ratio)\n',
    tag="计算·结构覆盖率（自触及）",
)

# ------------------------------------------------ ④ _und_self_touch_texts 方法
rep(
    '    def to_dict(self) -> dict:\n'
    '        d = {"amps": self.amps, "threads": self.threads,\n',
    '    def _und_self_touch_texts(self) -> List[str]:\n'
    '        """「研究层自己产出的下游文本」——用来判结构 amp 有没有被再次触及。\n'
    '\n'
    '        ★ 为什么是这几类、且**只能是**这几类：\n'
    '          · `threads`（悬空线头）：研究层自己产出的待追线索 ——\n'
    '            一条结构若被后续圈追成线头，就是「还活着」。\n'
    '          · `probes`（探针）：研究层自己设计的验证动作。\n'
    '          · `sc_probe_texts`（各圈自报触及）：模型每圈写\n'
    '            covered/uncovered_aspects 时实际在描述自己碰到的东西。\n'
    '        ★ **刻意不取**：\n'
    '          · `und_aspects`（那是评估阶段的疑问，不是研究层的产物）——\n'
    '            拿了就和「独立度」用同一参照，两读数会互为函数。\n'
    '          · `evidence[].cite` 的 A# —— 实测模型只引 C#，A# 引用为 0，\n'
    '            拿了等于恒 0。\n'
    '        ★ 空池返回空表（调用点据此记 None，不印 0.00 冒充读数）。\n'
    '        """\n'
    '        out: List[str] = []\n'
    '        for t in (self.threads or []):\n'
    '            s = str(t.get("desc", "")).strip()\n'
    '            if s:\n'
    '                out.append(s)\n'
    '            w = str(t.get("polarity_why", "")).strip()\n'
    '            if w:\n'
    '                out.append(w)\n'
    '        for p in (self.probes or []):\n'
    '            s = str(p.get("question", "")).strip()\n'
    '            if s:\n'
    '                out.append(s)\n'
    '        for _seg in (self.covered_unders or []):\n'
    '            s = str(_seg).strip()\n'
    '            if s:\n'
    '                out.append(s)\n'
    '        return out\n'
    '\n'
    '    def to_dict(self) -> dict:\n'
    '        d = {"amps": self.amps, "threads": self.threads,\n',
    tag="新增·_und_self_touch_texts",
)

# ------------------------------------------------ ⑤ Pool 增加 covered_unders 字段
rep(
    '            }\n'
    '        if und_aspects and not self.undecidable_channel.get("und_aspects"):\n',
    '            }\n'
    '        #  ★ 研究层各圈自报的「已触及方面」——结构覆盖率的自触及凭据\n'
    '        #    之一（另一个是 threads/probes）。与 structural_amps 分属\n'
    '        #    两层：一个是结构名，一个是方面名。\n'
    '        if covered_aspects is not None:\n'
    '            _bs = self.covered_unders or []\n'
    '            for _ca in covered_aspects:\n'
    '                _s = str(_ca).strip()\n'
    '                if _s and not any(_similar(_s, _x, _DUP_SIM)\n'
    '                                  for _x in _bs):\n'
    '                    _bs.append(_s[:200])\n'
    '            self.covered_unders = _bs\n'
    '        if und_aspects and not self.undecidable_channel.get("und_aspects"):\n',
    tag="累积·研究层自报触及（Pool 级）",
)

# ------------------------------------------------ ⑥ add_undecidable 签名
rep(
    '    def add_undecidable(self, product: dict,\n'
    '                        und_aspects: Optional[List[str]] = None,\n'
    '                        layer: int = 0):\n',
    '    def add_undecidable(self, product: dict,\n'
    '                        und_aspects: Optional[List[str]] = None,\n'
    '                        layer: int = 0,\n'
    '                        covered_aspects: Optional[List[str]] = None):\n',
    tag="签名·covered_aspects",
)

# ------------------------------------------------ ⑦ 渲染（产物第七节）
rep(
    '        if ac_hist:\n'
    '            aspects = list(ch.get("und_aspects") or [])\n'
    '            ahit = int(ch.get("last_aligned_hit", 0) or 0)\n'
    '            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"\n'
    '                      if aspects else "")\n'
    '            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"\n'
    '                         f"（代码实算{_hard2}）")\n'
    '        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"\n',
    '        if ac_hist:\n'
    '            aspects = list(ch.get("und_aspects") or [])\n'
    '            ahit = int(ch.get("last_aligned_hit", 0) or 0)\n'
    '            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"\n'
    '                      if aspects else "")\n'
    '            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"\n'
    '                         f"（代码实算{_hard2}）")\n'
    '        #  ★ 结构覆盖率（重设计）＝自触及：结构写完之后，研究过程\n'
    '        #    自己还碰不碰它。分母 = 结构条数（与独立度同），\n'
    '        #    视角正交（独立度＝有多新；本读数＝有多活）。\n'
    '        if "sc_history" in ch and ch.get("last_sc_ratio") is not None:\n'
    '            _scv = ch.get("last_sc_ratio")\n'
    '            _nsc_t = int(ch.get("last_sc_touched", 0) or 0)\n'
    '            _nsc_p = int(ch.get("last_sc_pool", 0) or 0)\n'
    '            parts.append(\n'
    '                f"结构覆盖率 {_scv:.2f}"\n'
    '                f"（代码实算：{_nsc_t}/{_nsc_p} 条结构被后续圈"\n'
    '                f"再次触及；量的是「结构有多活」，不是方面被覆盖几成）")\n'
    '        elif "sc_history" in ch:\n'
    '            parts.append("结构覆盖率 —（无结构，不可计算）")\n'
    '        return "研究层不可判定通道：" + "｜".join(parts) + "\\n"\n',
    tag="渲染·产物第七节（三读数并列）",
)

# ------------------------------------------------ ⑧ 终端
rep(
    '            _acov = ch.get("last_aligned_coverage")\n'
    '            if _acov is not None:\n'
    '                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"\n'
    '                        f"（{int(ch.get(\'last_aligned_hit\', 0) or 0)}"\n'
    '                        f"/{n_aspects} und_aspects 命中）")\n',
    '            _acov = ch.get("last_aligned_coverage")\n'
    '            if _acov is not None:\n'
    '                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"\n'
    '                        f"（{int(ch.get(\'last_aligned_hit\', 0) or 0)}"\n'
    '                        f"/{n_aspects} und_aspects 命中）")\n'
    '            _scv = ch.get("last_sc_ratio")\n'
    '            if "sc_history" in ch:\n'
    '                if _scv is None:\n'
    '                    self.vp("   📘 不可判定结构覆盖率 "\n'
    '                            "—（无结构，不可计算）")\n'
    '                else:\n'
    '                    self.vp(f"   📘 不可判定结构覆盖率 {_scv:.0%}"\n'
    '                            f"（{int(ch.get(\'last_sc_touched\', 0) or 0)}"\n'
    '                            f"/{int(ch.get(\'last_sc_pool\', 0) or 0)}"\n'
    '                            f" 条结构被后续圈再次触及）")\n',
    tag="终端·结构覆盖率并列",
)

# ------------------------------------------------ ⑨ 调用点传参
rep(
    '            pool.add_undecidable(view.undecidable_product,\n'
    '                                 und_aspects=und_aspects, layer=layer)\n',
    '            pool.add_undecidable(\n'
    '                view.undecidable_product,\n'
    '                und_aspects=und_aspects, layer=layer,\n'
    '                covered_aspects=list(\n'
    '                    getattr(view, "covered_aspects", None) or []))\n',
    tag="调用点·传 covered_aspects",
)

# ------------------------------------------------ ⑩ Pool 初始化 covered_unders
rep(
    '    undecidable_channel: dict = field(default_factory=dict)\n',
    '    undecidable_channel: dict = field(default_factory=dict)\n'
    '    #  ★ 研究层各圈自报的「已触及方面」——结构覆盖率（自触及）的\n'
    '    #    凭据之一（另一个是 threads / probes）。\n'
    '    covered_unders: List[str] = field(default_factory=list)\n',
    tag="初始化·covered_unders",
)

write_crlf(SRC, TXT)
print("-" * 78)
print(f"共 {_n} 处编辑；已写回 {APP}")


# ================================================================ 自检
print("=" * 78)
print("自检")
print("=" * 78)

_t = read_crlf(SRC)
print(f"  行数 {_t.count(chr(10))}")

assert f"元 DGTF · {NEW_VER}" in _t
assert f'__version__ = "{NV}"' in _t
assert NV in _t[:4000]
print("  [1] 版本号两处 + 前 4000 字符内 ✓")

for k in ('"last_sc_ratio"', '"last_sc_pool"', '"last_sc_touched"',
          '"sc_history"', '"sc_touched_amps"'):
    assert k in _t, f"缺新键 {k}"
print("  [2] 五个新键齐 ✓")

assert "def _und_self_touch_texts(self)" in _t
assert "covered_unders: List[str] = field(default_factory=list)" in _t
print("  [3] 自触及方法 + covered_unders 字段 ✓")

assert ("layer: int = 0,\n"
        "                        covered_aspects: Optional[List[str]] = None") in _t
assert "covered_aspects=list(" in _t
print("  [4] 签名 + 调用点 ✓")

for k in ('"last_struct_coverage": 0.0', '"struct_coverage_history": []',
          '"last_struct_hit": 0'):
    assert k in _t, f"旧键被动了：{k}"
print("  [5] 旧键一字未动 ✓")

assert "结构覆盖率 {_scv:.2f}" in _t and "对齐覆盖率 {ac_hist[-1]:.2f}" in _t
print("  [6] 产物渲染含 结构覆盖率 + 对齐覆盖率 ✓")

import ast
ast.parse(_t)
print("  [7] AST 解析通过 ✓")

# ---- 真调用自检 ----
sys.path.insert(0, str(HERE))
import importlib.util
spec = importlib.util.spec_from_file_location("dg25", str(SRC))
mod = importlib.util.module_from_spec(spec)
sys.modules["dg25"] = mod
spec.loader.exec_module(mod)
assert mod.__version__ == NV, mod.__version__
print(f"  [8] import 通过，__version__ = {mod.__version__} ✓")

_S = ["结构甲：前台按钮与后台提示不可同时满足",
      "结构乙：时间差两端不可折中",
      "结构丙：两域可改性不同，合问为假"]
p = mod.Pool()
p.add_undecidable(
    {"clarity": 0.7, "structural_amps": _S, "aligned_amps": []},
    und_aspects=["世界本身是否虚拟"], layer=1, covered_aspects=[])
ch = p.undecidable_channel
print(f"  [9] 首圈（无线头/探针）：sc={ch['last_sc_ratio']} "
      f"touched={ch['last_sc_touched']}/{ch['last_sc_pool']}")
assert ch["last_sc_ratio"] == 0.0, ch["last_sc_ratio"]
print("      首圈 0.00（还没有下游文本）✓")

# 造下游：一条线头呼应结构乙
p.threads.append({"desc": "时间差两端不可折中的实例仍未取到，悬空",
                  "kind": "thread", "polarity": "0"})
p.probes.append({"question": "同一栏两次取值是否不同？"})
p.add_undecidable(
    {"clarity": 0.8, "structural_amps": _S, "aligned_amps": []},
    und_aspects=[], layer=2, covered_aspects=[])
ch = p.undecidable_channel
print(f"  [10] 二圈（1 条线头呼应结构乙）：sc={ch['last_sc_ratio']} "
      f"touched={ch['last_sc_touched']}/{ch['last_sc_pool']}")
assert ch["last_sc_ratio"] == 1 / 3, ch["last_sc_ratio"]
assert ch["last_sc_touched"] == 1, ch["last_sc_touched"]
print("      1/3 —— 三结构只有乙被后续触及 ✓")
assert ch["sc_history"] == [0.0, 1 / 3], ch["sc_history"]
print("      sc_history 逐圈累积 ✓")

# 独立度必须**不受** touched 影响（正交）
assert ch["last_indep_ratio"] == 1.0, ch["last_indep_ratio"]
print("  [11] 独立度仍 1.000（无线头影响，两读数正交）✓")

# 空池 → None
p2 = mod.Pool()
p2.add_undecidable({"clarity": 0.5, "structural_amps": [], "aligned_amps": []},
                   und_aspects=[], layer=1, covered_aspects=[])
assert p2.undecidable_channel["last_sc_ratio"] is None
print("  [12] 无结构时记 None（不可计算 ≠ 0）✓")

# 负对照：线头跟所有结构都不搭 → 必须掉回 0
p3 = mod.Pool()
p3.add_undecidable({"clarity": 0.5, "structural_amps": _S, "aligned_amps": []},
                   und_aspects=[], layer=1, covered_aspects=[])
p3.threads.append({"desc": "量子引力中的时间箭头问题仍未解", "kind": "thread"})
p3.add_undecidable({"clarity": 0.5, "structural_amps": _S, "aligned_amps": []},
                   und_aspects=[], layer=2, covered_aspects=[])
_ch3 = p3.undecidable_channel
print(f"  [13] 负对照（线头不搭）：sc={_ch3['last_sc_ratio']} "
      f"touched={_ch3['last_sc_touched']}")
assert _ch3["last_sc_touched"] == 0, _ch3["last_sc_touched"]
assert _ch3["last_sc_ratio"] == 0.0, _ch3["last_sc_ratio"]
print("      负对照判红：不搭就是 0.00 ✓")

print("  [14] 全部自检通过 ✓")
print("=" * 78)
