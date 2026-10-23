# -*- coding: utf-8 -*-
"""把 v1.23.12 的判据注入 smoke_test.py，并把 SRC 指到新版。

三件事：
  1) `check_v122_phase3`（v1.21.73 那条）里的**关闭态文案**断言随实现更新 ——
     旧断言查单通道文案「**外部锚点**：无（本产物不含外部事实校验；」，
     那条文案正是「联网跑了也看不见」的根源。语义不放宽。
  2) 新增 `check_v12312_anchor_lanes`（两条通道分别写明 + 四处渲染点 + 负对照）。
  3) 把新判据挂进主 runner。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

# ── 1 · 旧文案断言随实现更新 ────────────────────────────────
OLD_CHK = '''        chk("**外部锚点**：无（本产物不含外部事实校验；" in t_off,
            "[A] 关闭时产物文案变了（旧断言会回归）")
        chk("已接入" not in t_off, "[A] 关闭时产物竟出现「已接入」")
'''
NEW_CHK = '''        # [v1.23.12 判据随实现更新，语义不放宽]
        #   旧断言查的是**单通道**文案「**外部锚点**：无（本产物不含外部
        #   事实校验；」—— 那条文案把「联网到底跑没跑」整个吞掉了：
        #   真跑里联网收了 6 条（W1–W6），产物仍只写「外部锚点：无」。
        #   锚点改到新实现里那条**文本通道**的写法，并**新增**一条
        #   「联网通道整条不许丢」。
        chk("**外部锚点 · 文本**（锚点文件 `external_anchor`）：无" in t_off,
            "[A] 关闭时文本通道没写「无」")
        chk("**外部锚点 · 联网**" in t_off,
            "[A] 关闭时联网通道整条丢了（读者又看不到这一路）")
        chk("已接入" not in t_off, "[A] 关闭时产物竟出现「已接入」")
'''
assert s.count(OLD_CHK) == 1, "旧关闭态断言命中 %d 次" % s.count(OLD_CHK)
s = s.replace(OLD_CHK, NEW_CHK, 1)

# ── 2 · 新判据 ──────────────────────────────────────────────
NEWFN = '''def check_v12312_anchor_lanes():
    """[v1.23.12] 外部锚点分「文本 / 联网」两条通道分别写明（单一实现）。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 两条通道都必须出现，且**各自**把「没有」写出来 —— 联网关时写
        「**关**」，产物没写 `_runtime` 时写「未记录」，都不许静默省略。
      · 联网**开**且收了 N 条：必须写出条数、W# 编号、环节数、失败数。
      · 联网开时**不许**再出现「未接入外部校验」那句留痕 —— 旧实现口径
        错位：联网明明跑了 6 条，产物仍写「本次未接入外部校验」。
      · **四处渲染点**（产物头部 / 显化说明 / decision 落地 / boundary
        落地）都要出现两条通道 —— 防「四个点只接了一处」。
      · 真正驱动判据的是**真跑形态**：结果里没有 `external_anchor`、
        但有 6 条 `web_results` —— 这正是原始 bug 的现场。
    """
    import tempfile as _tf
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \\u2717 [v12312] 命名空间里没有 mod")
        return False
    for _fn in ("_anchor_lane_lines", "_web_lane_stats"):
        if not hasattr(m, _fn):
            print("  \\u2717 [v12312] 缺 %s" % _fn)
            return False

    def _pool(**x):
        p = {"amps": [], "threads": [], "probes": [], "suspensions": [],
             "meta": [], "sub_questions": [], "deferrals": [],
             "escalations": [], "decidability_log": [], "duel_suspensions": [],
             "duel_alignment": [], "engagements": [], "refinements": [],
             "decidable_channel": [], "undecidable_channel": []}
        p.update(x)
        return p

    def _res(q, **kw):
        d = {"question": q, "route": ["1"], "keep": {"1": "all"},
             "rounds": {"1": 1},
             "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                          "requested": ["1"], "skipped": []},
             "views": {"1": {}}, "pools": {"1": _pool()},
             "llm_calls": 1, "llm_tokens": 1,
             "decidability": {"decidability": "decidable"},
             "channels": ["content"], "tri_state": [0, 0], "_config": {}}
        d.update(kw)
        return d

    _Q = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"
    _ON = {"_runtime": {"web_enabled": True},
           "pools": {"1": _pool(web_results=[
               {"id": "W%d" % i,
                "stage": ("research_decompose" if i <= 3
                          else "research_evidence"), "tier": 3}
               for i in range(1, 7)])}}

    # ── A · 真跑形态：无锚点文件 + 联网 6 条 ────────────────────
    _r = _res(_Q, **_ON)
    _lanes = m._anchor_lane_lines(_r)
    _j = "\\n".join(_lanes)
    if len(_lanes) != 2:
        bad.append("两条通道没分开（得 %d 条）" % len(_lanes))
    if "**外部锚点 · 文本**" not in _j or "**外部锚点 · 联网**" not in _j:
        bad.append("缺「文本」或「联网」标题")
    if "无 ——" not in _j:
        bad.append("没有锚点文件时，文本通道没写「无」")
    for _need in ("**开**", "收 6 条", "W1", "2 个环节", "失败 0 条"):
        if _need not in _j:
            bad.append("联网通道缺读数：%s" % _need)
    _s = m._web_lane_stats(_r)
    if (_s["ok"] != 6 or len(_s["ids"]) != 6 or len(_s["stages"]) != 2
            or _s["tiers"] != {"3": 6} or _s["errs"]
            or _s["enabled"] is not True):
        bad.append("_web_lane_stats 读数不对：%r" % (_s,))

    # ── B · 三态：关 / 未记录 ─────────────────────────────────
    _off = "\\n".join(m._anchor_lane_lines(
        _res(_Q, **{"_runtime": {"web_enabled": False}})))
    if "**关**" not in _off:
        bad.append("联网关时没写「**关**」")
    _na = "\\n".join(m._anchor_lane_lines(_res(_Q)))
    if "未记录" not in _na:
        bad.append("产物没写 `_runtime` 时没写「未记录」")

    # ── C · 失败条数 / 零条 ───────────────────────────────────
    _er = "\\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "pools": {"1": _pool(web_errors=[{"kind": "rate", "stage": "x"}])}})))
    if "失败 1 条" not in _er or "[W-RATE]" not in _er:
        bad.append("联网失败没写出条数与 kind")
    _z = "\\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "pools": {"1": _pool(web_results=[])}})))
    if "收 0 条" not in _z:
        bad.append("联网开而零条时没写「收 0 条」")
    if "已接入" in _z:
        bad.append("联网零条时文本通道混进了「已接入」")

    # ── D · 锚点文件失败 ─────────────────────────────────────
    _an = "\\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "external_anchor": {"anchors": 0, "error": "FileNotFoundError: x"}})))
    if "锚点异常" not in _an:
        bad.append("锚点文件失败时没写「锚点异常」")

    # ── E · 四处渲染点 ───────────────────────────────────────
    _dec = dict(_r, orientation="decision",
                _config={"actions": {"landing_decision": True}})
    _bnd = dict(_r, orientation="boundary")
    _sites = {"显化说明": m.render_manifestation(_r),
              "落地(decision)": m.render_landing(_dec),
              "落地(boundary)": m.render_landing(_bnd)}
    with _tf.TemporaryDirectory() as td:
        _sites["产物头部"] = Path(
            m.save_result(_r, save_dir=td)).read_text(encoding="utf-8")
    for _k, _v in _sites.items():
        if "**外部锚点 · 文本**" not in _v or "**外部锚点 · 联网**" not in _v:
            bad.append("[%s] 没有同时写出两条通道（渲染点漏接）" % _k)
    for _k in ("落地(decision)", "落地(boundary)"):
        if "### 七、外部锚点（两条通道分开记账）" not in _sites[_k]:
            bad.append("[%s] 缺第七节" % _k)

    # ── F · 口径不许打架（联网开 / 关 两种）────────────────────
    if "未接入外部校验" in _sites["产物头部"]:
        bad.append("联网已经开了，产物仍写「未接入外部校验」——口径错位")
    with _tf.TemporaryDirectory() as td:
        _co = Path(m.save_result(
            _res(_Q, **{"_runtime": {"web_enabled": False}}),
            save_dir=td)).read_text(encoding="utf-8")
    if "未接入外部校验" not in _co or "--web on" not in _co:
        bad.append("联网关 + 事实题时缺留痕 / 指路")
    with _tf.TemporaryDirectory() as td:
        _cd = Path(m.save_result(
            _res(_D, **{"_runtime": {"web_enabled": False}}),
            save_dir=td)).read_text(encoding="utf-8")
    if "未接入外部校验" in _cd:
        bad.append("决策题不该出现「未接入外部校验」留痕")

    if bad:
        for _x in bad:
            print("  \\u2717 [v12312] %s" % _x)
        return False
    print("  \\u2713 [v12312] 外部锚点两条通道（文本/联网）分别写明 / "
          "开·关·未记录三态 / 失败与零条读数 / 四处渲染点 / 口径不打架")
    return True


'''
ANCHOR_DEF = "def check_v12310_render_ops():"
assert s.count(ANCHOR_DEF) == 1, "check_v12310_render_ops 命中 %d 次" % s.count(ANCHOR_DEF)
s = s.replace(ANCHOR_DEF, NEWFN + ANCHOR_DEF, 1)

# ── 3 · 挂进 runner ────────────────────────────────────────
OLD_REG = '''    if not check_v12311_writeback_and_web():
        return 1
'''
NEW_REG = OLD_REG + '''    if not check_v12312_anchor_lanes():
        return 1
'''
assert s.count(OLD_REG) == 1, "runner 注册点命中 %d 次" % s.count(OLD_REG)
s = s.replace(OLD_REG, NEW_REG, 1)

# ── 4 · SRC 指向 v1.23.12 ──────────────────────────────────
pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(pat.findall(s)) == 1, "SRC 行不是 1 行"
s = pat.sub('SRC = HERE / "元DGTF-V1.23.12.py"', s, count=1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
SK.write_bytes(out)
import ast
ast.parse(out.decode("utf-8"))
print("smoke_test.py 已更新：")
print("  旧关闭态断言 → 新两条通道（语义不放宽）")
print("  新增 check_v12312_anchor_lanes 并挂进 runner")
print("  SRC =", re.findall(r"SRC = HERE / .*", out.decode("utf-8"))[:1])
