# -*- coding: utf-8 -*-
"""v1.23.34 判据：两个新接线的 stage（并入 ㉞/㉟ 已有的那次 mock run）。

## 为什么并入
本项目的冒烟对时长敏感（每次 mock run ≈ 10 秒）。㉞/㉟ 已经跑了一次
`MetaDGTF.run` ⇒ **顺便**挂上 Gate spy 就能验证「默认关 ⇒ 走到 Gate 且被拦」，
**零额外成本**。

## 判据内容（两向）
  · **源码级**：两 stage 各有真实调用点、挂在统一实现上、豁免已取消、
    枚举已登记、`used_as` 正确；
  · **真实入口**：默认配置（`web_search.enabled` 默认关）下，两个 stage
    都**走到了 Gate**（证明接线可达）且**都被拦**（证明红线未破）。
★ 「打开就做」由 `_probe_v12334_web2stage.py` 覆盖（它是两层观测、跑两次配置）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

# ── A：在 ㉞/㉟ 的 mock run 上挂 Gate spy ──
OLD_RUN = '''            mod.DGTF._render = _spy_render
            try:
                _res_cy = _mt_cy.run("意识能否被还原为信息处理过程？",
                                     route=["0"], rounds={"0": 3},
                                     parallel_mode="serial")
            finally:
                mod.DGTF._render = _orig_render'''
NEW_RUN = '''            mod.DGTF._render = _spy_render
            # ★ [修行层/停止判据联网] 顺便观测两条新接线：默认关时
            #   「走到 Gate + 被拦」= 接线可达 且 红线未破（零真检索）。
            _w2s_allow = []
            _orig_wallow = mod.WebSearchGate.allow

            def _spy_wallow(self, stage, round_no):
                _r = _orig_wallow(self, stage, round_no)
                _w2s_allow.append(
                    (str(stage), bool(_r[0]) if isinstance(_r, tuple)
                     else bool(_r)))
                return _r
            mod.WebSearchGate.allow = _spy_wallow
            try:
                _res_cy = _mt_cy.run("意识能否被还原为信息处理过程？",
                                     route=["0"], rounds={"0": 3},
                                     parallel_mode="serial")
            finally:
                mod.DGTF._render = _orig_render
                mod.WebSearchGate.allow = _orig_wallow'''
ANCHOR_RUN = OLD_RUN

# ── B：在 ㉟ 的量化/可读性断言之后加两 stage 的断言 ──
OLD_ASSERT = '''            # ★ [v1.23.34 · view 输出结构] 正文最前面要有「本层速览」。
            #   与上面的量化断言**共用同一次 mock run**（不重复起引擎）。
            if "本层速览" not in _body_md:
                bad.append("[提示词] `_render` 正文缺「本层速览」"
                           "（view 输出结构没生效）")'''
NEW_ASSERT = '''            # ★ [v1.23.34 · view 输出结构] 正文最前面要有「本层速览」。
            #   与上面的量化断言**共用同一次 mock run**（不重复起引擎）。
            if "本层速览" not in _body_md:
                bad.append("[提示词] `_render` 正文缺「本层速览」"
                           "（view 输出结构没生效）")
            # ★ [修行层/停止判据联网] 默认关 ⇒ 两 stage 都**走到 Gate 且被拦**。
            #   「走到了」证接线可达；「被拦」证红线未破（零真检索）。
            _w2s = dict(_w2s_allow)
            for _st in ("practice_term_calibration", "stop_criteria"):
                if _st not in _w2s:
                    bad.append("[联网] `%s` 默认配置下**没走到 Gate**"
                               "（接线不可达）" % _st)
                elif _w2s[_st]:
                    bad.append("[联网] `%s` 默认关却**被 Gate 放行**"
                               "（红线破了）" % _st)'''

# ── C：源码级断言（加进 check_v12334_prompt）──
OLD_SRC = '''    if "===ING-STRUCT===" not in src or "ing_structured" not in src:
        bad.append("[提示词] ing 结构化尾块契约被动了（机器解析依赖它）")'''
NEW_SRC = '''    if "===ING-STRUCT===" not in src or "ing_structured" not in src:
        bad.append("[提示词] ing 结构化尾块契约被动了（机器解析依赖它）")

    # ── ⑦ [修行层/停止判据联网] 两个「默认不做、显式打开就做」的 stage ──
    #   ★ 从前它们是「配了不做」（登记在 `_AUDIT_CONFIG_EXEMPT`）——
    #     用户口径改为「开关要能作用」⇒ 必须有**真实调用点**。
    _flat2 = " ".join(src.replace("\\r\\n", "\\n").split())
    for _st in ("practice_term_calibration", "stop_criteria"):
        if ('_web_search("%s"' % _st) not in src:
            bad.append("[联网] `%s` **没有真实调用点**（配了不做）" % _st)
    if "_AUDIT_CONFIG_EXEMPT = ()" not in src:
        bad.append("[联网] `_AUDIT_CONFIG_EXEMPT` 未清空（两 stage 仍在「声明不做」里）")
    for _u in ("term_calibration", "stop_criteria"):
        if ('"%s"' % _u) not in src[src.find("_WEB_USED_AS"):
                                    src.find("_WEB_USED_AS") + 400]:
            bad.append("[联网] `_WEB_USED_AS` 未登记枚举值 %r（有判据钉封闭集合）" % _u)
    # 接线必须挂在**两条通道共用的统一实现**上（不许在通道里各写一份）
    _i_br = src.find("self._practice_term_calibration_prep()")
    _i_br_fn = src.find("def _before_round")
    if _i_br < 0 or _i_br_fn < 0 or _i_br < _i_br_fn:
        bad.append("[联网] 术语校准没挂在 `_before_round`（圈前统一实现）上")
    _i_sc = src.find("self._stop_criteria_check(entry, view)")
    _i_sc_fn = src.find("def _finalize_layer_common")
    if _i_sc < 0 or _i_sc_fn < 0 or _i_sc < _i_sc_fn:
        bad.append("[联网] 判据复核没挂在 `_finalize_layer_common`（共用的层收尾）上")'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((ANCHOR_RUN, NEW_RUN, "A mock run 挂 Gate spy"),
                          (OLD_ASSERT, NEW_ASSERT, "B 两 stage 断言"),
                          (OLD_SRC, NEW_SRC, "C 源码级断言")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 两 stage 判据已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()
