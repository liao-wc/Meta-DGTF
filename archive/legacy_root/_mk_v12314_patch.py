# -*- coding: utf-8 -*-
"""v1.23.14 补丁：用**真实历史语料**校准自适应调度。

改动：
  A 版本号
  B 重写 `_auto_history`（三类来源 + 分位 + 按题型分桶）+ 新增 `_hist_*` 助手
    与 `_hist_for`；★ 修字段名 bug（`rounds` → `rounds_run`，实际停圈原先永远取不到）
  C `_auto_pick_cost_profile`：拍脑袋的「40 万 token」→ **相对判据**
    （同类题成本中位 ≥ 全语料 p75 才降档）
  D `_auto_pick_rounds`：三级回退（实际停圈 → 种子上限 → 按层实测默认）
  E `auto_dispatch` 的 history 调用改成 cfg 驱动（三个开关）
  F DEFAULT_CONFIG：`auto.history_limit` 20→200，新增 `history_md` / `history_batch`
  G 产物新增「**实际停圈**」一行（`rounds_run`）—— 让语料能积累
  H `_auto_dispatch_lines` 的历史行报出来源数与 p75
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.14.py"
BLOCK = (HERE / "_v12314_block_hist.py").read_text(
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
repl("元 DGTF · v1.23.13", "元 DGTF · v1.23.14", "标题版本")
repl('__version__ = "1.23.13"', '__version__ = "1.23.14"', "版本常量")

# ══════════════════════════════════════════════ B 重写 _auto_history
i_h = find_row(lambda l: l.startswith("def _auto_history(save_dir"),
               "_auto_history 定义")
j = i_h + 1
while j < len(lines) and not lines[j].startswith("def "):
    j += 1
k = j
while k - 1 > i_h and lines[k - 1] == "":
    k -= 1
assert k - i_h > 50, "被替换的 _auto_history 太短（%d 行）" % (k - i_h)
lines[i_h:k] = BLOCK.rstrip("\n").split("\n") + ["", ""]

# ══════════════════════════════════════════════ C 成本档校准
repl('''def _auto_pick_cost_profile(feat, hist, cfg):
    """成本档：先按题型定基线，再按历史成本与质量读数微调。"""
    if feat["fact"] and feat["short"]:
        base, why = "economy", "事实型短题（无决策语境）"
    elif feat["meta"] or feat["choice"]:
        base, why = "balanced", "含元层/选择，需要摊开"
    else:
        base, why = "balanced", "决策型题面，用 token 精简档"
    _tm = int(hist.get("tokens_med") or 0)
    _tr = hist.get("tri_rate")
    if _tm >= 400000 and base == "balanced":
        base, why = "economy", why + "；历史 token 中位 %d 偏高，降一档" % _tm
    if _tr is not None and _tr < 0.5 and base == "economy" and not feat["fact"]:
        base, why = "balanced", "历史三态一致率 %.2f 偏低，不降到 economy" % _tr
    return base, why''',
     '''def _auto_pick_cost_profile(feat, hist, cfg):
    """成本档：先按题型定基线，再按**同题型历史**相对全语料基准微调。

    ★ 校准依据（真实语料 384 条）：阈值不再写死「40 万 token」这种拍脑袋数，
      改成**相对判据** —— 该类题的成本中位是否 ≥ 全语料 p75
      （实测 tokens_p75 = 1_050_814、calls_p75 = 171）。
      相对判据会随语料自动更新，不会因样本规模变化而失效。
    """
    if feat["fact"] and feat["short"]:
        base, why = "economy", "事实型短题（无决策语境）"
    elif feat["meta"] or feat["choice"]:
        base, why = "balanced", "含元层/选择，需要摊开"
    else:
        base, why = "balanced", "决策型题面，用 token 精简档"
    _all = hist or {}
    _h = _hist_for(feat, hist)
    _tk75 = int(_all.get("tokens_p75") or 0)
    _cl75 = int(_all.get("calls_p75") or 0)
    _tk = int(_h.get("tokens_med") or 0)
    _cl = int(_h.get("calls_med") or 0)
    _exp = ((_tk75 and _tk >= _tk75) or (_cl75 and _cl >= _cl75))
    if _exp and base == "balanced":
        base, why = "economy", (why + "；同类题历史成本中位 %d token / %d 次"
                                "调用 ≥ 全语料 p75（%d / %d），降一档"
                                % (_tk, _cl, _tk75, _cl75))
    _tr = _h.get("tri_rate")
    _trn = int(_h.get("tri_n") or 0)
    if (_tr is not None and _tr < 0.5 and base == "economy"
            and not feat["fact"]):
        base, why = "balanced", ("同类题历史三态一致率 %.2f 偏低（n=%d），"
                                 "不降到 economy" % (_tr, _trn))
    return base, why''',
     "成本档校准")

# ══════════════════════════════════════════════ D 圈数校准
repl('''def _auto_pick_rounds(feat, hist, cfg):
    """圈数：有历史就按「各层实际停在第几圈」+1，无历史按题型给基线。"""
    hard = int(((cfg or {}).get("spiral") or {}).get("hard_max", 12) or 12)
    soft = int(((cfg or {}).get("spiral") or {}).get("soft_max", 3) or 3)
    _lr = hist.get("layer_rounds") or {}
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    out = {}
    for e in _ENTRIES:
        _h = int(_lr.get(e) or 0)
        if _h > 0:
            _v = _h + 1
        elif feat["fact"] and feat["short"]:
            _v = _floor
        else:
            _v = max(soft, _floor) + 1
        out[e] = min(max(_v, _layer_floor(e, hard, _floor)),
                     _layer_ceil(e, hard, _floor))
    _src = ("历史各层停圈中位 %s +1" % _lr) if _lr else "无历史，按题型给基线"
    return out, _src''',
     '''def _auto_pick_rounds(feat, hist, cfg):
    """圈数：**实际停圈 → 种子上限 → 按层实测默认** 三级回退。

    ★ 校准依据（真实语料 384 条）：各层**种子圈数上限**实测 p50 =
      修行 4 / 研究 4 / 对撞 5 / 元 6。所以「无历史时统一给 soft_max+2=5」
      对前两层偏高、对元层偏低；改成按层给实测中位（`_AUTO_ROUNDS_BASE`）。
    ★ 实际停圈（`views.*.rounds_run`）优先 —— 它才是真信号；但当前语料里
      只有落 packed 的那几次有，所以必须有回退链，而不是「取不到就当 0」。
    """
    hard = int(((cfg or {}).get("spiral") or {}).get("hard_max", 12) or 12)
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    _act = (hist.get("layer_rounds") or {})
    _act_n = (hist.get("layer_rounds_n") or {})
    _cap = (hist.get("cap_rounds") or {})
    _cap_n = (hist.get("cap_rounds_n") or {})
    out, _src_layers = {}, []
    for e in _ENTRIES:
        _a = int(_act.get(e) or 0)
        _c = int(_cap.get(e) or 0)
        # ★ 实际停圈优先，但要够样本（`_AUTO_ACT_MIN`）—— 见该常量注释。
        if _a > 0 and int(_act_n.get(e) or 0) >= _AUTO_ACT_MIN:
            _v, _k = _a + 1, "实际停圈(n=%d)" % int(_act_n.get(e) or 0)
        elif _c > 0:
            _v, _k = _c, "种子上限(n=%d)" % int(_cap_n.get(e) or 0)
        elif feat["fact"] and feat["short"]:
            _v, _k = _floor, "题型基线"
        else:
            _v, _k = int(_AUTO_ROUNDS_BASE.get(e, max(3, _floor))), "实测默认"
        _v2 = min(max(_v, _layer_floor(e, hard, _floor)),
                  _layer_ceil(e, hard, _floor))
        # ★ 报**钳制后**的值：报钳制前的原始值会与产物「取值」列不一致。
        _src_layers.append("%s=%d(%s%s)"
                           % (_LAYER_LABEL.get(e, e), _v2,
                              _k, "，原始 %d 被钳" % _v if _v2 != _v else ""))
        out[e] = _v2
    _src = "按层：%s（实际停圈需 ≥%d 份样本才采用）" % (
        "、".join(_src_layers), _AUTO_ACT_MIN)
    return out, _src''',
     "圈数校准")

# ══════════════════════════════════════════════ E history 调用
repl('''    hist = history if history is not None else _auto_history(
        save_dir or _auto_save_dir(cfg),
        int(((cfg or {}).get("auto") or {}).get("history_limit", 20) or 20))''',
     '''    _acfg = (cfg or {}).get("auto") or {}
    if history is not None:
        hist = history
    else:
        hist = _auto_history(
            save_dir or _auto_save_dir(cfg),
            int(_acfg.get("history_limit", 200) or 200), cfg=cfg,
            want_md=bool(_acfg.get("history_md", True)),
            want_batch=bool(_acfg.get("history_batch", True)))''',
     "history 调用")

# ══════════════════════════════════════════════ F 配置默认值
repl('''    "auto": {
        "enabled": True,
        "allow_route_trim": True,
        "history_limit": 20,
    },''',
     '''    "auto": {
        "enabled": True,
        "allow_route_trim": True,
        # ★ 语料实测：`outputs/` 里有 368 份产物 md + 16 条跑批记录，
        #   默认只扫 20 份等于把历史样本丢了 95%。200 够覆盖现有语料。
        "history_limit": 200,
        "history_md": True,
        "history_batch": True,
    },''',
     "配置默认值")

# ══════════════════════════════════════════════ G 实测默认圈数常量
repl('''_AUTO_META_MARKS = ("本身", "自身", "递归", "元", "整体", "到底")''',
     '''_AUTO_META_MARKS = ("本身", "自身", "递归", "元", "整体", "到底")

#: 各层圈数的**实测默认**（384 条真实语料里「种子上限」的中位数）。
#: 用途：历史里既没有实际停圈、也没有种子上限时的最后回退。
_AUTO_ROUNDS_BASE = {"0": 4, "1": 4, "both": 5, "all": 6}

#: 「实际停圈」要多少份样本才值得信。低于它退回「种子上限」——
#: 实测：真实语料里落 packed 的只有 1 份；若只按「有没有」判断，
#: 单条噪声（`{'1': 1}`）会盖掉 200 份的种子上限分布。
_AUTO_ACT_MIN = 3''',
     "实测默认圈数")

# ══════════════════════════════════════════════ G2 「实际停圈」渲染
repl('''def _stop_kind_summary(views) -> str:''',
     '''def _rounds_run_line(views) -> str:
    """各层**实际跑了几圈**（`rounds_run`）+ 种子上限（`rounds_cap`）一行。

    ★ 为什么要有这一行：调度器的「历史实际停圈」读数此前**取不到** ——
      `_auto_history` 把字段名读成了 `rounds`，真实字段是 `rounds_run`
      （静默：`dict.get` 不报错，只是恒 None）。而且产物里根本没有任何渲染点
      把它写出来。于是「实际停圈」这条信号**既没被读、也没被记**。
      本行把它落进产物 ⇒ 后续语料才积累得起来（数据收集闭环）。
    """
    if not isinstance(views, dict) or not views:
        return ""
    _parts = []
    for _e in _ENTRIES:
        _v = views.get(_e)
        if not isinstance(_v, dict):
            continue
        _r = _v.get("rounds_run")
        if not isinstance(_r, int) or _r <= 0:
            continue
        _c = _v.get("rounds_cap")
        _parts.append("%s %d 圈%s"
                      % (_LAYER_LABEL.get(_e, _e), _r,
                         ("（上限 %d）" % _c
                          if isinstance(_c, int) and _c else "")))
    if not _parts:
        return ""
    return "**实际停圈**：" + " / ".join(_parts) + "\\n\\n"


def _stop_kind_summary(views) -> str:''',
     "实际停圈渲染函数")

repl('''            _stop_line = _stop_kind_summary(_views0)
            if _stop_line:
                f.write(_stop_line)''',
     '''            _stop_line = _stop_kind_summary(_views0)
            if _stop_line:
                f.write(_stop_line)
            _rr_line = _rounds_run_line(_views0)
            if _rr_line:
                f.write(_rr_line)''',
     "实际停圈接线")

# ══════════════════════════════════════════════ H 历史行报告来源
repl('''    out.append("- 历史读数：%d 份 · tokens 中位 %s · 三态一致率 %s · "
               "被截断率 %s · 联网 收%s/失败%s · 取向错配 %s\\n"
               % (int(_hist.get("n") or 0), _hist.get("tokens_med") or "—",
                  ("%.2f" % _hist["tri_rate"]) if _hist.get("tri_rate")
                  is not None else "—",
                  ("%.2f" % _hist["cut_rate"]) if _hist.get("cut_rate")
                  is not None else "—",
                  _hist.get("web_hit", 0), _hist.get("web_fail", 0),
                  _hist.get("mismatch", 0)))''',
     '''    _srcs = _hist.get("sources") or {}
    _bt = _hist.get("by_type") or {}
    out.append("- 历史读数：**%d 份**（%s）· token 中位 %s / p75 %s · "
               "calls 中位 %s / p75 %s · 三态一致率 %s（n=%s）· "
               "被截断率 %s（n=%s 层）· 联网 收%s/失败%s（%s 跑有入池）· "
               "取向错配 %s\\n"
               % (int(_hist.get("n") or 0),
                  "、".join("%s %s" % (a, b) for a, b in sorted(_srcs.items()))
                  or "无",
                  _hist.get("tokens_med") or "—", _hist.get("tokens_p75") or "—",
                  _hist.get("calls_med") or "—", _hist.get("calls_p75") or "—",
                  ("%.2f" % _hist["tri_rate"]) if _hist.get("tri_rate")
                  is not None else "—", _hist.get("tri_n") or 0,
                  ("%.2f" % _hist["cut_rate"]) if _hist.get("cut_rate")
                  is not None else "—", _hist.get("stop_n") or 0,
                  _hist.get("web_hit", 0), _hist.get("web_fail", 0),
                  _hist.get("web_runs", 0),
                  _hist.get("mismatch", 0)))
    if _bt:
        out.append("- 分题型：事实型 %s 份（token 中位 %s）/ 决策型 %s 份"
                   "（token 中位 %s）\\n"
                   % ((_bt.get("fact") or {}).get("n", 0),
                      (_bt.get("fact") or {}).get("tokens_med") or "—",
                      (_bt.get("nonfact") or {}).get("n", 0),
                      (_bt.get("nonfact") or {}).get("tokens_med") or "—"))''',
     "历史行报来源")

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
for _k in ("def _hist_from_packed(", "def _hist_from_md(",
           "def _hist_from_batch(", "def _hist_for(",
           "def _rounds_run_line(", "_AUTO_ROUNDS_BASE =",
           'get("rounds_run")', '"history_md"', '"history_limit": 200'):
    print("  %-34s ×%d" % (_k, txt.count(_k)))
print("旧字段名残留（应为 0）：", txt.count('_v.get("rounds")'))

import importlib.util as _ilu
import sys as _sys
_spec = _ilu.spec_from_file_location("m_v12314_chk", MAIN)
_m = _ilu.module_from_spec(_spec)
_sys.modules["m_v12314_chk"] = _m
_spec.loader.exec_module(_m)
assert _m.__version__ == "1.23.14", _m.__version__
_h = _m._auto_history("outputs", 200, cfg=_m.DEFAULT_CONFIG)
print("历史读数自检：n=%s sources=%s tokens_p75=%s cap_rounds=%s"
      % (_h["n"], _h["sources"], _h["tokens_p75"], _h["cap_rounds"]))
assert _h["n"] > 100, "历史样本仍太少：%s（md/跑批源没接上）" % _h["n"]
print("结构自检 OK ✓")
