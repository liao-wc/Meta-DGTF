# -*- coding: utf-8 -*-
"""v1.23.15 补丁：把「未做 / 边界」四条做完。

  A 版本号
  B 重写历史块：三大来源 + **按题型分层（每题型上限）** + **时间衰减加权分位**
    + 抽取器补齐「三态一致率」「联网行」；抽不到的字段**不写键**
  C 成本档的「质量保护」阈值改**实测 p10**（原 0.5 落在中位数之上，
    实测会拦掉 54% 的情况 ⇒ 等于废掉降档）；并要求 ≥30 份样本才启用
  D 截断率规则加**样本量门槛**（`_AUTO_STOP_MIN_N`）
  E 圈数默认基线按真跑对照实验重校准（见 `_AUTO_ROUNDS_BASE`）
  F DEFAULT_CONFIG：新增 `auto.history_halflife_days`
  G 历史行报出半衰期与每题型上限
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.15.py"
BLOCK = (HERE / "_v12315_block_hist.py").read_text(
    encoding="utf-8").replace("\r\n", "\n")

raw = MAIN.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "主文件不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
N0 = len(lines) - 1


def find_row(pred, what):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, "%s：命中 %d 次 %r" % (what, len(hits), hits)
    return hits[0]


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1)
            if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：块命中 %d 次（要求 %d）" % (what, len(hits),
                                                             expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n


# ══════════════════════════════════════════════ A 版本号
repl("元 DGTF · v1.23.14", "元 DGTF · v1.23.15", "标题版本")
repl('__version__ = "1.23.14"', '__version__ = "1.23.15"', "版本常量")

# ══════════════════════════════════════════════ B 重写历史块
i0 = find_row(lambda l: l.startswith("def _hist_quant("), "_hist_quant 起始")
i_cp = find_row(lambda l: l.startswith("def _auto_pick_cost_profile("),
                "成本档策略定义")
i1 = i_cp
while i1 - 1 > i0 and lines[i1 - 1] == "":
    i1 -= 1
assert i1 - i0 > 200, "被替换的历史块太短（%d 行）" % (i1 - i0)
# ★ 顺手补回 ③ 段头：上一版替换时按「下一个 def」切片，把这段头**一起删掉了**
#   （没有判据守着它，所以静默）。本次显式补回。
THREE_HDR = [
    "# ------------------------------------------------------------",
    "# ③ 十二项策略（各自适应条件）",
    "#   返回 (值, 理由)。返回 None = **auto 不表态**（按配置/默认）。",
    "# ------------------------------------------------------------",
]
lines[i0:i1] = (BLOCK.rstrip("\n").split("\n") + ["", ""]
                + THREE_HDR + ["", ""])

# ══════════════════════════════════════════════ C 成本档质量保护阈值
repl('''    _tr = _h.get("tri_rate")
    _trn = int(_h.get("tri_n") or 0)
    if (_tr is not None and _tr < 0.5 and base == "economy"
            and not feat["fact"]):
        base, why = "balanced", ("同类题历史三态一致率 %.2f 偏低（n=%d），"
                                 "不降到 economy" % (_tr, _trn))
    return base, why''',
     '''    # ★ 校准（真实语料 254 份）：三态一致率 p10 = 0.167、p50 = 0.333。
    #   原门槛 0.5 落在**中位数之上** ⇒ 实测会拦掉 54% 的情况，
    #   这条「质量优先保护」实际等于把降档功能废掉。改用**实测 p10** 作异常线，
    #   并要求 ≥30 份样本才启用（样本不足时不表态）。
    _tr = _h.get("tri_rate")
    _trn = int(_h.get("tri_n") or 0)
    _tri_floor = _h.get("tri_p10")
    if _tri_floor is None:
        _tri_floor = _AUTO_TRI_FLOOR
    if (_trn >= _AUTO_TRI_MIN_N and _tr is not None and _tr < _tri_floor
            and base == "economy" and not feat["fact"]):
        base, why = "balanced", ("同类题历史三态一致率 %.3f 低于实测 p10 %.3f"
                                 "（n=%d），不降到 economy"
                                 % (_tr, _tri_floor, _trn))
    return base, why''',
     "成本档质量保护阈值")

# ══════════════════════════════════════════════ D 截断率样本门槛
repl('''    if not bool(((cfg or {}).get("auto") or {}).get("allow_route_trim", True)):
        return list(_ENTRIES), "auto.allow_route_trim=false：不砍层"
    _cr = hist.get("cut_rate")
    if _cr is not None and _cr >= 0.5:
        return list(_ENTRIES), ("历史被截断率 %.2f 偏高，样本不足，"
                                "保留全四层" % _cr)''',
     '''    if not bool(((cfg or {}).get("auto") or {}).get("allow_route_trim", True)):
        return list(_ENTRIES), "auto.allow_route_trim=false：不砍层"
    # ★ 截断率要**够层样本**才信：实测语料里只有 5 层（产物里的「停止」行是后来才加的），
    #   5 层的比率不足以决定「要不要砍层」。门槛以下不表态。
    _cr = hist.get("cut_rate")
    _sn = int(hist.get("stop_n") or 0)
    if _cr is not None and _sn >= _AUTO_STOP_MIN_N and _cr >= 0.5:
        return list(_ENTRIES), ("历史被截断率 %.2f 偏高（n=%d 层），保留全四层"
                                % (_cr, _sn))''',
     "截断率样本门槛")

# ══════════════════════════════════════════════ E 常量
repl('''#: 「实际停圈」要多少份样本才值得信。低于它退回「种子上限」——
#: 实测：真实语料里落 packed 的只有 1 份；若只按「有没有」判断，
#: 单条噪声（`{'1': 1}`）会盖掉 200 份的种子上限分布。
_AUTO_ACT_MIN = 3''',
     '''#: 「实际停圈」要多少份样本才值得信。低于它退回「种子上限」——
#: 实测：真实语料里落 packed 的只有 1 份；若只按「有没有」判断，
#: 单条噪声（`{'1': 1}`）会盖掉 200 份的种子上限分布。
_AUTO_ACT_MIN = 3

#: 三态一致率的**异常线**。真实语料 254 份实测 p10 = 0.167
#: （p50 = 0.333 —— 旧门槛 0.5 在中位数之上，会拦掉 54%，等于废掉降档）。
_AUTO_TRI_FLOOR = 0.167

#: 三态一致率要多少份样本才够用来判「异常」。低于它不表态。
_AUTO_TRI_MIN_N = 30

#: 截断率要多少**层**样本才够。实测语料只有 5 层 —— 不足以下结论。
_AUTO_STOP_MIN_N = 24''',
     "阈值常量")

# ══════════════════════════════════════════════ F 配置
repl('''        "history_limit": 200,
        "history_md": True,
        "history_batch": True,
    },''',
     '''        "history_limit": 200,
        "history_md": True,
        "history_batch": True,
        # 历史加权的时间半衰期（天）。0 = 不衰减（等权）。
        # 旧样本是旧配置下的读数，不加权会把新读数系统性地拉向旧行为。
        "history_halflife_days": 14,
    },''',
     "配置半衰期")

# ══════════════════════════════════════════════ G 历史行报半衰期与每桶上限
repl('''    _hist = plan.get("_history") or {}''',
     '''    _hist = plan.get("_history") or {}
    _hl = _hist.get("_half_life_days")
    _plt = _hist.get("_limit_per_type")''',
     "历史行变量")
repl('''    out.append("\\n- 题型特征：%s\\n"''',
     '''    if _hl is not None:
        out.append("- 取样口径：每题型上限 %s 条 · 时间半衰期 %s 天"
                   "（0=不衰减）\\n" % (_plt or "—", _hl))
    out.append("- 题型特征：%s\\n"''',
     "历史行口径")

# ══════════════════════════════════════════════ 落盘
out = "\n".join(lines)
ast.parse(out)
data = out.replace("\n", "\r\n").encode("utf-8")
assert data.count(b"\r\r\n") == 0 and data.count(b"\r\n") == data.count(b"\n")
MAIN.write_bytes(data)

txt = data.decode("utf-8")
N1 = txt.count("\n")
print("行数：%d → %d（%+d）" % (N0, N1, N1 - N0))
print("CRLF %d | CRCRLF %d" % (data.count(b"\r\n"), data.count(b"\r\r\n")))
print("版本：", [l for l in txt.split("\n") if l.startswith("__version__")])
for _k in ("def _hist_wquant(", "def _hist_weight(", "def _hist_decay(",
           "_AUTO_TRI_FLOOR =", "_AUTO_TRI_MIN_N =", "_AUTO_STOP_MIN_N =",
           "_HIST_RE_TRI", "_HIST_RE_WEB", '"history_halflife_days"',
           "_limit_per_type"):
    print("  %-32s ×%d" % (_k, txt.count(_k)))

import importlib.util as _ilu
import sys as _sys
_spec = _ilu.spec_from_file_location("m_v12315_chk", MAIN)
_m = _ilu.module_from_spec(_spec)
_sys.modules["m_v12315_chk"] = _m
_spec.loader.exec_module(_m)
assert _m.__version__ == "1.23.15", _m.__version__
_h = _m._auto_history("outputs", 200, cfg=_m.DEFAULT_CONFIG)
print("历史自检：n=%s sources=%s 每桶上限=%s 半衰期=%s"
      % (_h["n"], _h["sources"], _h.get("_limit_per_type"),
         _h.get("_half_life_days")))
print("  tri: n=%s p10=%s med=%s | 分题型 n=%s"
      % (_h["tri_n"], _h["tri_p10"], _h["tri_rate"],
         {k: v["n"] for k, v in (_h["by_type"] or {}).items()}))
print("  cut_rate=%s (stop_n=%s) | web 收%s/失败%s/%s跑"
      % (_h["cut_rate"], _h["stop_n"], _h["web_hit"], _h["web_fail"],
         _h["web_runs"]))
assert _h["tri_n"] > 50, "三态一致率抽取没生效（n=%s）" % _h["tri_n"]
print("结构自检 OK ✓")
