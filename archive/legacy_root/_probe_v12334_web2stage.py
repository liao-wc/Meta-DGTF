#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：两个新接线的 stage 是否真的「默认不做、打开就做」。

## 怎么证（构造性，不真联网）
猴补丁 `MetaDGTF._web_search` 本身（拦截**在它内部**，所以不会走网络）：
  · 默认配置（`web_search.stages.{practice_term_calibration,stop_criteria}=false`）
    ⇒ 两个 stage **一次都不能被调到**（零调用可验证）；
  · 把两个 stage 打开（`web_search.enabled=True` + stage=True）
    ⇒ 两个 stage **各至少调到一次**，且 `used_as` 正确。
★ 这样既不花钱，又真的走过了**接线点**（`_before_round` / `_finalize_layer_common`）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_case(st, mod, tc: bool, sc: bool):
    cfg = st.build_cfg(False)
    cfg.setdefault("web_search", {})
    cfg["web_search"]["enabled"] = True
    _st = cfg["web_search"].setdefault("stages", {})
    _st["practice_term_calibration"] = tc
    _st["stop_criteria"] = sc
    # 其余 stage 全关（把变量收窄到这两个，免得被别的 stage 干扰读数）
    for _k in ("research_decompose", "research_evidence", "research_precedent",
               "duel_arbitration", "meta_clean_check"):
        _st[_k] = False
    calls = []
    allows = []
    https = []
    orig_allow = mod.WebSearchGate.allow
    orig_http = mod.WebSearchClient._http

    def _spy_allow(self, stage, round_no):
        r = orig_allow(self, stage, round_no)
        allows.append((str(stage), bool(r[0]) if isinstance(r, tuple) else bool(r)))
        return r

    def _spy_http(self, query, max_n):
        # ★ 官方打桩缝（该方法自己的注释：「探针 / 冒烟覆写它就能离线测」）。
        #   返回 ([], "empty") = 「外部确实没有」，是**终态**、不降级。
        https.append((str(query)[:60], int(max_n)))
        return [], "empty"
    mod.WebSearchGate.allow = _spy_allow
    mod.WebSearchClient._http = _spy_http
    # ★ **不**替换 `_web_search`：让它真跑内部逻辑，否则 Gate 观测不到
    #   （第一次就是这么错的：把整个方法换成 spy ⇒ allow 一次都没被调到）。
    try:
        mod.MetaDGTF(cfg).run("术语校准与停止判据的复核该怎么做？",
                              route=["0"], rounds={"0": 2},
                              parallel_mode="serial", run_id="")
    finally:
        mod.WebSearchGate.allow = orig_allow
        mod.WebSearchClient._http = orig_http
    return allows, https


def main():
    spec = importlib.util.spec_from_file_location("smoke_w2s", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_w2s"] = st
    spec.loader.exec_module(st)
    mod = st.mod

    bad = []
    # ── 默认关 ──
    a_off, h_off = run_case(st, mod, False, False)
    _tc_off = [a for a in a_off if a[0] == "practice_term_calibration"]
    _sc_off = [a for a in a_off if a[0] == "stop_criteria"]
    print("【默认关】Gate.allow 结果=%r" % (a_off,))
    print("            真检索次数=%d（应 0）" % len(h_off))
    if not (_tc_off and _sc_off):
        bad.append("默认关时**没走到 Gate**（接线不可达：应走到 allow 并被拦）")
    elif any(v for _s, v in _tc_off + _sc_off):
        bad.append("默认关时 Gate 竟放行：%r" % (_tc_off + _sc_off,))
    elif h_off:
        bad.append("默认关时竟发生了真检索：%r" % (h_off,))
    else:
        print("  ✓ 两 stage 都走到 Gate 且**被拦**；零真检索（红线未破）")

    # ── 打开 ──
    a_on, h_on = run_case(st, mod, True, True)
    _tc_on = [a for a in a_on if a[0] == "practice_term_calibration"]
    _sc_on = [a for a in a_on if a[0] == "stop_criteria"]
    print("【打开】Gate.allow 结果=%r" % (a_on,))
    print("        真检索次数=%d（应 ≥2：两个 stage 各一次）" % len(h_on))
    if not (_tc_on and all(v for _s, v in _tc_on)):
        bad.append("打开后 `practice_term_calibration` 的 Gate 未放行：%r" % (_tc_on,))
    if not (_sc_on and all(v for _s, v in _sc_on)):
        bad.append("打开后 `stop_criteria` 的 Gate 未放行：%r" % (_sc_on,))
    if len(h_on) < 2:
        bad.append("打开后真检索次数 <2（接线没真走到检索）：%r" % (h_on,))

    if not bad:
        print("\n[OK] 默认不做（Gate 拦 + 零检索）/ 打开就做（Gate 放行 + 真检索）"
              "—— 两条接线均可达")
    else:
        print("\n[FAIL] " + "；".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
