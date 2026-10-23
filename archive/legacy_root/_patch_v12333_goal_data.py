# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮 patch-5：把「层目标读数」所需的**逐圈原料**接进产物。

缺什么（本轮核查结论 —— 「字段有值 ≠ 有出口」的反面：**出口要有原料**）：
  ① `aspect_hist`：修行层「边际新增趋零」需要**逐圈累计层面数**；
     现在只有终值 `len(aspect_units)` ⇒ `excavate` 只能走 fallback。
  ② `upstream_layers` / `upstream_texts`：对撞层「融合率」的分母与
     「复读罚」的比对语料。
  ③ `sem_stagnation`：若对撞层自己已经算了语义停滞（`distance_to_question`
     同族的量），直接出口；没有则由 `_lg_stag_ratio` 现算。

落点：
  · Pool 增 `aspect_hist` 字段 + `merge` 末尾记一次累计数（逐圈 = 逐 merge）。
  · View.to_dict 增三个出口（白名单，手工加）。
  · 逐圈循环体统一回填 `view.aspect_hist`（真实层别名 → 数字索引对齐）。
"""
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    t = p.read_bytes().decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), "非纯 CRLF"
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", "")
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0
    p.write_bytes(out.encode("utf-8"))
    chk = p.read_bytes().decode("utf-8")
    assert chk.count("\n") == chk.count("\r\n")


def sub1(t, a, r):
    n = t.count(a)
    assert n == 1, "锚点命中 %d 次（必须 1）：%r" % (n, a[:100])
    return t.replace(a, r, 1)


t = load_crlf(SRC)

# ── ① Pool 增 aspect_hist 字段 ────────────────────────────────────────
A1 = '''    aspect_units: List[dict] = field(default_factory=list)
    anchors: List[dict] = field(default_factory=list)
'''
R1 = '''    aspect_units: List[dict] = field(default_factory=list)
    #: [层目标 / Heaps 饱和] 逐圈**累计层面数**：`[V1, V2, …]`。
    #:   ★ 修行层「挖到不能再挖」= 边际新增趋零 ⇒ 必须留**逐圈序列**，
    #:     只留终值就只能退回单点估计（真跑读不到判别力）。
    aspect_hist: List[int] = field(default_factory=list)
    anchors: List[dict] = field(default_factory=list)
'''
t = sub1(t, A1, R1)

# ── ② merge 末尾记一次累计数 ──────────────────────────────────────────
A2 = '''        for _u in (aspect_units or []):
            if not isinstance(_u, dict):
                continue
            _uid = str(_u.get("id") or "").strip()
            if not _uid:
                continue
            if not any(str(x.get("id") or "") == _uid
                       for x in self.aspect_units):
                self.aspect_units.append(_u)
'''
R2 = '''        for _u in (aspect_units or []):
            if not isinstance(_u, dict):
                continue
            _uid = str(_u.get("id") or "").strip()
            if not _uid:
                continue
            if not any(str(x.get("id") or "") == _uid
                       for x in self.aspect_units):
                self.aspect_units.append(_u)
        # ★ [层目标] 本圈结束时记一次**累计层面数**（merge 每圈调一次
        #   ⇒ 本列表天然是「逐圈序列」）。同值也记：**平稳本身就是读数**
        #   （Heaps 饱和 = 后续增量恒 0，序列会连续重复）。
        self.aspect_hist.append(len(self.aspect_units))
'''
t = sub1(t, A2, R2)

# ── ③ View.to_dict 增三个出口 ─────────────────────────────────────────
A3 = '''        # [A1 方面单元] 池级镜像出口（A1~An 编号可在产物里审计）。
        if self.aspect_units:
            d["aspect_units"] = self.aspect_units
'''
R3 = '''        # [A1 方面单元] 池级镜像出口（A1~An 编号可在产物里审计）。
        if self.aspect_units:
            d["aspect_units"] = self.aspect_units
        # ★ [层目标] 四层目标读数所需的原料必须**出口**（否则 AutoTune
        #   的 `layer_goal_summary` 在真跑里永远读不到 ⇒ 只能走 fallback）。
        if getattr(self, "aspect_hist", None):
            d["aspect_hist"] = list(self.aspect_hist)
        if getattr(self, "upstream_layers", 0):
            d["upstream_layers"] = int(self.upstream_layers)
        if getattr(self, "upstream_texts", None):
            d["upstream_texts"] = list(self.upstream_texts)
        if getattr(self, "sem_stagnation", None) is not None:
            d["sem_stagnation"] = float(self.sem_stagnation)
'''
t = sub1(t, A3, R3)

save_crlf(SRC, t)
print("OK: patch-5 逐圈原料与出口")
