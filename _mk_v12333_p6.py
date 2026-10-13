#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P6：给「层读数进产物」加**行为判据**（防回归）。

★ 为什么必须加：本版真跑暴露「主因/三态/anytime 只进了 verbose 转储、
  产物看不到」—— 这类缺口**只有驱动 `save_result` 才测得出来**。
  判据形态：造最小 packed 夹具 → 走真实 `save_result` → 断言产物 md 里
  出现 6 个新读数块。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

ADD = '''        # ★ [层读数进产物] **行为判据**：走真实 `save_result`，断言产物 md
        #   里出现 6 个新读数块（真跑曾暴露「只进 verbose 转储」的缺口）。
        try:
            import tempfile as _tf3
            _d3 = Path(_tf3.mkdtemp(prefix="smk_lay_"))
            _pool3 = {"amps": [], "threads": [], "probes": [], "meta": [],
                      "suspensions": [], "aspect_units": [], "belief_items": [],
                      "anchors": [], "duel_suspensions": [], "aspect_targets": {}}
            _r3 = {"question": "层读数验收题", "route": ["0", "1"],
                   "rounds": {"0": 1, "1": 1},
                   "dispatch": {"order": ["0", "1"], "ran": ["0", "1"],
                                "requested": ["0", "1"], "missing": [],
                                "failed": {}, "skipped": [],
                                "_parallel_mode": "serial"},
                   "keep": {"0": "all", "1": "all"},
                   "_anchor_tier_warning": "", "_anchor_answers_filtered": 0,
                   "views": {},
                   "pools": {k: dict(_pool3) for k in ("0", "1", "both", "all")},
                   "llm_calls": 2, "llm_tokens": 20, "llm_ops_calls": 1,
                   "llm_ops_tokens": 10, "llm_eval_calls": 1,
                   "llm_eval_tokens": 10,
                   "compact": {"inner_share": 0.9, "budget": 0.6, "over": True,
                               "verdict": "内部面超预算 ⇒ 索引化"},
                   "belief_staleness": {"n": 5, "stale_n": 2, "max_age": 4},
                   "diversity": {"layers": 2, "channels": 3, "combos": 6,
                                 "mode": "serial", "note": "x"}}
            _v3 = mod.View(entry="0")
            _v3.stop_primary = "悬置决定稳定，自然安住"
            _v3.divergence = {"state": "发散", "var_first": 1.0,
                              "var_last": 4.0, "ac1": 0.4}
            _v3.best_round = 2
            _v3.anytime = {"n": 6, "lower": 0.44, "delta": 0.05}
            _v3.csd = {"new_amps": {"hint": True}}
            _r3["views"]["0"] = _v3.to_dict()
            _md3 = Path(mod.save_result(_r3, str(_d3))).read_text(encoding="utf-8")
            for _k3 in ("层读数（每层）", "三态=发散", "历史最佳=第2圈",
                        "anytime下界=0.440", "内部面预算", "信念陈旧度"):
                if _k3 not in _md3:
                    bad.append("[层读数] 产物里缺 %r（只进了 verbose 转储？）" % _k3)
            import shutil as _sh3
            _sh3.rmtree(_d3, ignore_errors=True)
        except Exception as _e3:
            bad.append("[层读数] 行为判据异常：%r" % (_e3,))

'''
for _f in ("_smk_v12332_fn.py", "smoke_test.py"):
    p = HERE / _f
    b = p.read_bytes()
    is_crlf = b.count(b"\r\n") > 0 and b.count(b"\r\n") == b.count(b"\n")
    s = b.decode("utf-8").replace("\r\n", "\n")
    anchor = "    # ── 真实入口 + 不变量 ──\n"
    assert s.count(anchor) == 1, (_f, s.count(anchor))
    s = s.replace(anchor, ADD + anchor, 1)
    p.write_bytes((s.replace("\n", "\r\n") if is_crlf else s).encode("utf-8"))
    print("层读数行为判据已补", _f)
