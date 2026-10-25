# -*- coding: utf-8 -*-
"""Round 12 判据：uncovered 片段级覆盖 + 整体量语义加权（零 API）。

真实依据：黄河长度真跑 aq=needs_evidence，gaps=['uncovered:黄河的长度']
（原文是「黄河…全长约5464公里」），且答案取了官方「河段长3472千米」而非
多源「全长约5464公里」。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import (Evidence, _overall_quantity_bonus,  # noqa: E402
                              _short_answer, _term_covered,
                              answer_from_evidence, detect_gaps)
from dgtf_v2.fact_flow import _compact_numeric_answer  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def ev(eid, snippet, official=False):
    return Evidence(evidence_id=eid, query="q", title="", url="u/" + eid,
                    snippet=snippet, domain="d" + eid, official=official,
                    fingerprint="fp_" + eid, rank=0)


def main():
    # ── A：片段级覆盖 ─────────────────────────────
    ck("A1 整短语命中仍算覆盖",
       _term_covered("黄河的长度", "黄河的长度为5464千米") is True)
    ck("A2 片段全命中算覆盖（黄河 + 长度）",
       _term_covered("黄河的长度", "黄河全长约5464公里，长度居全国第二") is True)
    ck("A3 缺片段不算覆盖（只有黄河、无长度近义）",
       _term_covered("黄河的长度", "黄河流域面积广阔") is False)
    ck("A4 缺片段不算覆盖（只有长度没有黄河）",
       _term_covered("黄河的长度", "河流长度排名") is False)
    ck("A5 空词项视为覆盖", _term_covered("", "x") is True)

    gaps = detect_gaps("黄河的长度是多少千米",
                       [ev("E1", "黄河全长约5464公里，中国第二长河"),
                        ev("E2", "黄河全长约5464公里", True)])
    ck("A6 detect_gaps 不再误报 uncovered（长度←全长近义覆盖）",
       not any(str(g).startswith("uncovered:") for g in gaps), gaps)

    gaps2 = detect_gaps("黄河的面积是多少平方千米",
                        [ev("E1", "黄河全长约5464公里，中国第二长河")])
    ck("A7 真缺目标项仍报 uncovered",
       any(str(g).startswith("uncovered:") for g in gaps2), gaps2)

    # ── A2：口语量词数值句（Round 15）────────────────
    ck("A8 「5400多公里」句子被识别为数值句",
       "5400" in _short_answer("黄河，我国第二大河。全长5400多公里。",
                               "黄河的长度是多少千米"))
    ck("A9 「约5464公里」句子被识别为数值句",
       "5464" in _short_answer("说明一段话。它全长约5464公里。",
                               "黄河有多长"))
    ck("A10 「5400余公里」句子被识别为数值句",
       "5400" in _short_answer("一些背景。全长5400余公里。",
                               "黄河的长度是多少千米"))

    # ── A3：展示紧凑的弱量词过滤（Round 15）──────────
    d1 = _compact_numeric_answer("黄河的长度是多少千米",
                                 "黄河流经9个省（区），全长5400多公里")
    ck("A11 展示不取弱量词「9个」（不得只给 9个）",
       d1 != "9个" and ("5400" in d1 or "公里" in d1), d1)
    d2 = _compact_numeric_answer("长江的长度是多少千米", "长江总长6280千米。")
    ck("A12 展示取强单位「6280千米」", "6280千米" in d2, d2)

    # ── B：整体量语义加权 ────────────────────────
    ck("B1 问长度 + 全长标记 → 加分",
       _overall_quantity_bonus("黄河全长约5464公里", "黄河的长度是多少千米") > 0)
    ck("B2 非整体量题 → 不加分",
       _overall_quantity_bonus("黄河全长约5464公里", "中国GDP增长多少") == 0
       and _overall_quantity_bonus("黄河全长约5464公里", "如何提高GDP") == 0)
    ck("B3 河段长文本（含「长」但无整体量标记）→ 不加分",
       _overall_quantity_bonus("河段长3472千米", "黄河的长度是多少千米") == 0)

    off_wrong = ev("E3", "黄河上游河段长3472千米", official=True)
    uno_right = ev("E1", "黄河全长约5464公里")
    ans = answer_from_evidence([off_wrong, uno_right],
                               "黄河的长度是多少千米")
    ck("B4 官方分段值 vs 非官方全长值 → 取全长 5464（语义加权反超官方 0.15）",
       "5464" in ans, ans)
    ans2 = answer_from_evidence([off_wrong, uno_right], "黄河有多长")
    ck("B5 同义问法也生效", "5464" in ans2, ans2)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
