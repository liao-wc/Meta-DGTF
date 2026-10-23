# -*- coding: utf-8 -*-
"""「联网全接」B：配置层 —— 30 个环节各一个开关（`web_search.stages.<环节名>`）。

## 用户口径
「联网全接**配置可控开关**」⇒ 每个环节都要有**自己的**开关，且默认关。

## 两处改
 ① `_infer_stage_from_stack` 返回值去掉前导 `_`（`_ing` → `ing`）——
    配置键是给人看/给人写的，带下划线像内部符号；
 ② `DEFAULT_CONFIG["web_search"]["stages"]` 与出厂 yaml **各补 30 键**（默认 false）。

## 零行为差
全部默认 `false` ⇒ Gate 一律拒 ⇒ 与今天逐字相同（总闸 `enabled` 出厂也是 false）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"
Y = Path(__file__).resolve().parent / "dgtf_config.yaml"

#: 30 个环节（AST 实测：含 LLM 调用的函数，已扣 `_call_long` 这个工具）
STAGES = [
    "plan_orientation", "plan_resources", "auto_plan", "assess_decidability",
    "re_anchor", "expand_pair", "expand_pair_merged_once", "dual_judge",
    "ing", "he", "decompose_normal", "decompose_hybrid", "decompose_koan",
    "decompose_from_pool", "probe_research", "probe_duel", "probe_meta",
    "phase_probe", "ask_missing_polarity", "self_check", "manifest",
    "assess_decidability_from_pool_view", "check_structure_saturation",
    "re_evaluate_pool", "settle_research", "decide_parallel_mode",
    "adjudicate_sub_tristate_multi", "adjudicate_sub_tristate",
    "anchor_crosscheck", "check_input_sanity",
]

# ── A：推断时去下划线 ──
OLD_INFER = '''            if _n not in ("call", "_call_long", "_web_augment", "<module>") \\
                    and not _n.startswith("_llm_"):
                return _n'''
NEW_INFER = '''            if _n not in ("call", "_call_long", "_web_augment", "<module>") \\
                    and not _n.startswith("_llm_"):
                # 去掉前导下划线：配置键是给人读写的（`ing` 比 `_ing` 好写），
                # 而 `_infer` 拿到的是函数名（含前缀）⇒ 在这一处统一口径。
                return str(_n).lstrip("_")'''

# ── B：引擎默认配置补 30 键 ──
OLD_CFG = '''_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote",'''
NEW_CFG = '''#: [联网全接] 30 个环节的开关名（与 `_infer_stage_from_stack` 同口径：
#: 函数名去掉前导下划线）。★ 这张表**只用于生成默认配置**，运行时**不查它** ——
#: Gate 直接按键名查 `web_search.stages[...]`，所以**新增环节只需加一行**，
#: 老环节也不会因为表过期而失效（清单与运行时解耦）。
_WEB_ALL_STAGES = (
    "plan_orientation", "plan_resources", "auto_plan", "assess_decidability",
    "re_anchor", "expand_pair", "expand_pair_merged_once", "dual_judge",
    "ing", "he", "decompose_normal", "decompose_hybrid", "decompose_koan",
    "decompose_from_pool", "probe_research", "probe_duel", "probe_meta",
    "phase_probe", "ask_missing_polarity", "self_check", "manifest",
    "assess_decidability_from_pool_view", "check_structure_saturation",
    "re_evaluate_pool", "settle_research", "decide_parallel_mode",
    "adjudicate_sub_tristate_multi", "adjudicate_sub_tristate",
    "anchor_crosscheck", "check_input_sanity",
)

_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote",'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD_INFER, NEW_INFER, "A 推断去下划线"),
                          (OLD_CFG, NEW_CFG, "B 环节表")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)

    # ── C：把 30 键挂进 DEFAULT_CONFIG（用**推导式**，不手抄 30 行）──
    #   位置：`"stages": {` 之后的第一个键之前
    _i = s.find('"stages": {', s.find('"web_search"'))
    assert _i > 0, "找不到 web_search.stages"
    _ins = _i + len('"stages": {')
    s = (s[:_ins]
         + '\n'
           '            # ★ [联网全接] 30 个环节各自的开关（默认 false ⇒ 零行为差）。\n'
           '            #   名字与 `_infer_stage_from_stack` 同口径（函数名去下划线）。\n'
           '            #   现有 7 个「语义名」的 stage（research_* 等）走**显式接线**，\n'
           '            #   与这张表并存、互不干扰。\n'
           '            **{_k: False for _k in _WEB_ALL_STAGES},'
         + s[_ins:])

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 引擎侧 30 键已挂（推导式）；行数 %d" % out.count(b"\n"))

    # ── D：出厂 yaml 补 30 键（显式列出：给人看，不用推导式）──
    yraw = Y.read_bytes()
    assert yraw.count(b"\n") == yraw.count(b"\r\n"), "yaml 应为纯 CRLF"
    ys = yraw.decode("utf-8").replace("\r\n", "\n")
    _anchor = "    stop_criteria: false\n"
    assert ys.count(_anchor) == 1, "yaml 锚点命中 %d 次" % ys.count(_anchor)
    _lines = ["", "    # ★ [联网全接] 30 个环节各自的开关（默认 false ⇒ 零行为差）。",
              "    #   名字 = 环节函数名去掉前导下划线（与引擎的 stage 推断同口径）。",
              "    #   打开某个 ⇒ 该环节的 LLM 调用会自动带上「外部参考」段；",
              "    #   全部经 Gate（授权/三层配额/失败降级）⇒ 可控。",
              "    #   ★ 修行层的环节**不注入**（红线：输入是形状不是数据）。"]
    for _k in STAGES:
        _lines.append("    %s: false" % _k)
    ys = ys.replace(_anchor, _anchor + "\n".join(_lines) + "\n", 1)
    yout = ys.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in yout
    Y.write_bytes(yout)
    print("OK yaml 侧 30 键已补；行数 %d" % yout.count(b"\n"))


main()
