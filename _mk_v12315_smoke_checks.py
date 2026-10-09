# -*- coding: utf-8 -*-
"""把 v1.23.15 的判据注入 smoke_test.py，并把 SRC 指到新版。

新增 `check_v12315_history_calibration`：
  · **分层**：每题型上限（两桶都非空、各自 ≤ limit、大 limit 样本更多）；
  · **时间衰减**：权重数值 + 三点加权偏向新样本（半衰期 0 = 等权，负对照）；
  · **抽取补齐**：「三态一致率」与「联网行」都进读数；**抽不到的字段不写键**
    （`web_fail = 0` 与「没有联网这一行」是两件事）；
  · **三条规则按实测定**：成本档用实测 p10（不是拍脑袋的 0.5）且要 ≥30 份样本；
    截断率要 ≥24 层样本才表态；圈数三级回退 + 实际停圈门槛。
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

NEWFN = '''def check_v12315_history_calibration():
    """[v1.23.15] 分层抽样 + 时间衰减 + 三条规则的**实测**校准。

    ★ 背景：v1.23.14 把历史接上了，但三件事没做：
      ① `limit` 是「总数」⇒ 窗口一缩，事实型会被整体挤掉，「按题型比同类」
         退化成「比全语料」；
      ② 语料跨十几天，旧样本是旧配置下的读数，等权平均会把新读数拉向旧行为；
      ③ 「截断率 / 三态一致率 / 联网」三条规则**没有数据**（抽取器漏了
         「三态一致率」这一行，实测有 254 份），阈值是拍脑袋的 —— 实测
         一致率 p50 = 0.333，而门槛写 0.5 ⇒ 54% 的情况被拦，等于废掉降档。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 半衰期 0 ⇒ 加权分位必须**等于**等权分位；
      · 抽不到的字段**不许写键**（不写 0）；
      · 一致率高于 p10 ⇒ 照降档；低于 p10 且样本够 ⇒ 不降；
      · 截断率层样本不足 ⇒ 不表态（落到题型分支）。
    """
    import time as _t
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "_hist_wquant"):
        print("  \\u2717 [v12315] 命名空间里没有加权分位")
        return False
    cfg0 = m.load_config("")
    _F = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"

    # ── A 分层：每题型上限 ───────────────────────────────────
    h = m._auto_history("outputs", 20, cfg=cfg0)
    if h.get("_limit_per_type") != 20:
        bad.append("没报出「每题型上限」：%r" % h.get("_limit_per_type"))
    _ft = (h["by_type"]["fact"] or {}).get("n", 0)
    _nf = (h["by_type"]["nonfact"] or {}).get("n", 0)
    if _ft <= 0 or _nf <= 0:
        bad.append("分层后某桶为空（fact=%s nonfact=%s）" % (_ft, _nf))
    if _ft > 20 or _nf > 20:
        bad.append("某桶超过上限 20（fact=%s nonfact=%s）" % (_ft, _nf))
    _big = m._auto_history("outputs", 300, cfg=cfg0)
    if _big["n"] <= h["n"]:
        bad.append("上限放大后样本数没增加（%d → %d）" % (h["n"], _big["n"]))

    # ── B 时间衰减 ──────────────────────────────────────────
    _now = _t.time()
    if m._hist_weight(_now, 14, _now) != 1.0:
        bad.append("同刻权重不是 1")
    if abs(m._hist_weight(_now - 14 * 86400, 14, _now) - 0.5) > 1e-6:
        bad.append("一个半衰期后权重不是 0.5")
    if abs(m._hist_weight(_now - 28 * 86400, 14, _now) - 0.25) > 1e-6:
        bad.append("两个半衰期后权重不是 0.25")
    if m._hist_weight(None, 14, _now) != 1.0:
        bad.append("无 mtime 时不该衰减")
    if m._hist_weight(_now - 999 * 86400, 0, _now) != 1.0:
        bad.append("半衰期 0 时不该衰减")
    _old2 = [(100, m._hist_weight(_now - 28 * 86400, 14, _now)),
             (100, m._hist_weight(_now - 28 * 86400, 14, _now)),
             (10, m._hist_weight(_now, 14, _now))]
    _same = [(100, m._hist_weight(_now - 28 * 86400, 0, _now)),
             (100, m._hist_weight(_now - 28 * 86400, 0, _now)),
             (10, m._hist_weight(_now, 0, _now))]
    if not (m._hist_wquant(_old2, .5) < m._hist_quant([100, 100, 10], .5)):
        bad.append("加权后没偏向新样本（衰减没生效）")
    if m._hist_wquant(_same, .5) != m._hist_quant([100, 100, 10], .5):
        bad.append("半衰期 0 时加权分位不等于等权（负对照失效）")
    if m._hist_decay(cfg0) <= 0:
        bad.append("默认半衰期不该是 0（那样等于不衰减）")

    # ── C 抽取补齐：三态一致率 ───────────────────────────────
    _H = ("# 元 DGTF · 测试题\\n\\n**资源**: 10 次 LLM | 1000 tokens\\n\\n"
          "**三态判决一致率**：2/6（33%）　其中 4 条分歧已按 partial 计入\\n")
    _r = m._hist_from_md(_H)
    if abs((_r.get("tri") or -1) - 2 / 6) > 1e-6:
        bad.append("没抽到三态一致率：%r" % (_r.get("tri"),))
    _H0 = ("# 元 DGTF · 测试题\\n\\n**资源**: 10 次 LLM | 1000 tokens\\n\\n"
           "**三态判决一致率**：0/0（—）\\n")
    if "tri" in m._hist_from_md(_H0):
        bad.append("分母为 0 时不该写 tri 键")

    # ── D 抽取补齐：联网行 + 不写缺省键 ──────────────────────
    _H2 = ("# 元 DGTF · 测试题\\n\\n**资源**: 10 次 LLM | 1000 tokens\\n\\n"
           "**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条"
           "（W1、W2；2 个环节；tier 3×6）；失败 1 条\\n")
    _r2 = m._hist_from_md(_H2)
    if _r2.get("web_hit") != 6 or _r2.get("web_fail") != 1:
        bad.append("没抽到联网行：%r" % ({k: _r2.get(k) for k in
                                       ("web_hit", "web_fail")},))
    _H3 = "# 元 DGTF · 测试题\\n\\n**资源**: 10 次 LLM | 1000 tokens\\n"
    _r3 = m._hist_from_md(_H3)
    if ("web_hit" in _r3) or ("web_fail" in _r3):
        bad.append("没有联网行却写了键（0 与「没有这一行」是两件事）")

    # ── E 真实语料读数 ──────────────────────────────────────
    if _big["tri_n"] < 100:
        bad.append("三态一致率样本仍太少（%d）—— 抽取没生效" % _big["tri_n"])
    if _big["tri_p10"] is None:
        bad.append("没报三态一致率的 p10（阈值无法校准）")
    if not all((_big["by_type"][k] or {}).get("n", 0) > 0
               for k in ("fact", "nonfact")):
        bad.append("真实语料分层后某桶为空")

    # ── F 三条规则：按实测定 ─────────────────────────────────
    _base = {"n": 99, "tokens_p75": 1000, "calls_p75": 999999}
    _exp1 = {"n": 30, "tokens_med": 900000, "calls_med": 1}
    _d = m._auto_features(_D)
    _lo = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=40, tri_rate=0.10,
                                              tri_p10=0.167)})
    if m._auto_pick_cost_profile(_d, _lo, cfg0)[0] != "balanced":
        bad.append("一致率远低于 p10 时仍降档（质量保护失效）")
    _ok = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=40, tri_rate=0.30,
                                              tri_p10=0.167)})
    if m._auto_pick_cost_profile(_d, _ok, cfg0)[0] != "economy":
        bad.append("一致率高于 p10 却不降档（门槛把降档废掉了）")
    _few = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=5, tri_rate=0.10,
                                               tri_p10=0.167)})
    if m._auto_pick_cost_profile(_d, _few, cfg0)[0] != "economy":
        bad.append("一致率样本不足时不该表态（应照降）")
    if getattr(m, "_AUTO_TRI_FLOOR", None) != 0.167:
        bad.append("一致率异常线不是实测 p10（%r）"
                   % getattr(m, "_AUTO_TRI_FLOOR", None))
    if getattr(m, "_AUTO_TRI_MIN_N", 0) < 10:
        bad.append("一致率没有样本量门槛")
    if getattr(m, "_AUTO_STOP_MIN_N", 0) < 8:
        bad.append("截断率没有样本量门槛")

    _f = m._auto_features(_F)
    _fewstop = {"n": 50, "cut_rate": 0.9, "stop_n": 6}
    if m._auto_pick_route(_f, _fewstop, cfg0)[0] != ["0", "1", "both"]:
        bad.append("截断率层样本不足时不该拿它挡住题型分支")
    _manystop = {"n": 50, "cut_rate": 0.9, "stop_n": 40}
    if "被截断率" not in m._auto_pick_route(_f, _manystop, cfg0)[1]:
        bad.append("截断率层样本足够时应保留全四层")

    if bad:
        for _x in bad:
            print("  \\u2717 [v12315] %s" % _x)
        return False
    print("  \\u2713 [v12315] 分层（每题型 %s 条）· 时间衰减（半衰期 %s 天）· "
          "三态一致率 n=%d p10=%s · 联网行 · 三条规则按实测定"
          % (h.get("_limit_per_type"), h.get("_half_life_days"),
             _big["tri_n"], _big["tri_p10"]))
    return True


'''
ANCHOR = "def check_v12310_render_ops():"
assert s.count(ANCHOR) == 1, "check_v12310_render_ops 命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, NEWFN + ANCHOR, 1)

OLD_REG = '''    if not check_v12314_history_corpus():
        return 1
'''
NEW_REG = OLD_REG + '''    if not check_v12315_history_calibration():
        return 1
'''
assert s.count(OLD_REG) == 1, "runner 注册点命中 %d 次" % s.count(OLD_REG)
s = s.replace(OLD_REG, NEW_REG, 1)

pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(pat.findall(s)) == 1, "SRC 行不是 1 行"
s = pat.sub('SRC = HERE / "元DGTF-V1.23.15.py"', s, count=1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
ast.parse(out.decode("utf-8"))
SK.write_bytes(out)
print("smoke_test.py 已更新：新增 check_v12315_history_calibration；SRC ->",
      re.findall(r"SRC = HERE / .*", out.decode("utf-8"))[:1])
