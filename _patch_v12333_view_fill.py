# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮 patch-6：View 增三个字段并**真正填充**。

★ 「有出口 ≠ 有值」的对称面：出口我在 patch-5 加了，但若没人填，
  `layer_goal_summary` 还是读不到 ⇒ 对撞层读数恒 None。
  故这里补字段定义 + 填充点。
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

# ── ① View 增三字段（放在 aspect_units 之后）──────────────────────────
A1 = '''    aspect_units: List[dict] = field(default_factory=list)
    # [D1 信念条目] 信念条目（带状态/证据/熵），与 structural_amps 双写。
'''
R1 = '''    aspect_units: List[dict] = field(default_factory=list)
    #: [层目标 / Heaps 饱和] 逐圈**累计层面数**（逐圈序列，不是终值）。
    aspect_hist: List[int] = field(default_factory=list)
    #: [层目标 / 对撞] 本层的**上游层数**（融合率的分母）。0 = 未记。
    upstream_layers: int = 0
    #: [层目标 / CORE 停滞罚] 上游 view 的 manifest/collision 文本（比对语料）。
    upstream_texts: List[str] = field(default_factory=list)
    #: [层目标 / CORE] 语义停滞率 0-1（1 = 全复读上游）。None = 未算。
    sem_stagnation: Optional[float] = None
    # [D1 信念条目] 信念条目（带状态/证据/熵），与 structural_amps 双写。
'''
t = sub1(t, A1, R1)

# ── ② 逐圈循环体回填 view.aspect_hist（真实层别名 → 池）───────────────
A2 = '''            if _action_on(self.config, "re_evaluate_pool"):
                re_eval_n = self._lazy_every_n(int(sp.get("re_eval_every_n", 1)))
                if re_eval_n > 0 and layer_no % re_eval_n == 0:
                    result = self._re_evaluate_pool(entry, pool, layer_no)
'''
R2 = '''            # ★ [层目标] 逐圈把池的累计层面序列回填到 view（出口见 to_dict）。
            #   在 `re_evaluate_pool` **之前**：那一步可能改池，回填要贴本圈终态。
            try:
                _p0 = self.pools.get(entry)
                if _p0 is not None and getattr(_p0, "aspect_hist", None):
                    view.aspect_hist = list(_p0.aspect_hist)
            except Exception:
                pass

            if _action_on(self.config, "re_evaluate_pool"):
                re_eval_n = self._lazy_every_n(int(sp.get("re_eval_every_n", 1)))
                if re_eval_n > 0 and layer_no % re_eval_n == 0:
                    result = self._re_evaluate_pool(entry, pool, layer_no)
'''
t = sub1(t, A2, R2)

# ── ③ 对撞层填充 upstream_layers / upstream_texts / sem_stagnation ─────
A3 = '''                _upstream_texts: List[str] = []
                for _v in (inp.upstream_views or []):
                    _m = getattr(_v, "manifest", "") or ""
                    _c = getattr(_v, "collision", "") or ""
                    if _m:
                        _upstream_texts.append(_m)
                    if _c:
                        _upstream_texts.append(_c)
                if _upstream_texts:
'''
R3 = '''                _upstream_texts: List[str] = []
                for _v in (inp.upstream_views or []):
                    _m = getattr(_v, "manifest", "") or ""
                    _c = getattr(_v, "collision", "") or ""
                    if _m:
                        _upstream_texts.append(_m)
                    if _c:
                        _upstream_texts.append(_c)
                # ★ [层目标 / 对撞] 融合率的分母 + CORE 停滞罚的比对语料
                #   必须**从真跑填**（否则读数恒 None ⇒ 对撞层无判别力）。
                #   ★ 放在 `if _upstream_texts:` **之外**：没有上游文本时
                #     也要留 `upstream_layers`（分母），否则「没有上游」
                #     与「没测」又混成一种。
                try:
                    view.upstream_layers = len(inp.upstream_views or [])
                    if _upstream_texts:
                        view.upstream_texts = list(_upstream_texts)
                except Exception:
                    pass
                if _upstream_texts:
'''
t = sub1(t, A3, R3)

save_crlf(SRC, t)
print("OK: patch-6 View 字段与填充")

# ── ④ sem_stagnation：与 rephrase_ratio 同源填（复用同一份上游文本）──
A4 = '''                        view.rephrase_ratio = float(_rr)
'''
R4 = '''                        view.rephrase_ratio = float(_rr)
                        # ★ [层目标 / CORE] 复述率是「与上游的重合度」，
                        #   正是 CORE 的 semantic stagnation —— 直接出口它，
                        #   对撞层读数就用**引擎已算的这把尺子**，
                        #   而不是让 `_lg_stag_ratio` 另算一把（两把尺子会漂）。
                        try:
                            view.sem_stagnation = float(_rr)
                        except Exception:
                            pass
'''
t2 = load_crlf(SRC)
t2 = sub1(t2, A4, R4)
save_crlf(SRC, t2)
print("OK: patch-6b sem_stagnation 同源填充")
