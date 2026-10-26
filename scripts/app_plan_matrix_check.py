# -*- coding: utf-8 -*-
"""App plan 不变量检查（Round 71，零 API）：不同场景/预算下的动态最优约束。

覆盖：事实题 web 强制、fast 档可用、预算降级、route 恒四层、m4/场景字段、
本地 metrics、dual_judge 合法值、display/cache 策略等。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_app"))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))

import daosheng_mode as dm  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def _plan(q, requested="daosheng", balance=999.0):
    return dm.build_plan(q, {}, requested=requested, is_mock=True,
                         balance_cny=balance)


def main() -> int:
    q_fact = "HTTP 404状态码表示什么？"
    q_reason = "为什么在高原上煮饭更容易夹生？"
    q_choice = "企业建设数据中心，应该优先选择哪个方案？A. 自建机房 B. 公有云 C. 混合云"

    p1 = _plan(q_fact)
    def _kind(plan):
        return (plan.get("scenario") or {}).get("kind")

    ck("① 事实题 scenario=fact", _kind(p1) == "fact", p1.get("scenario"))
    ck("② 事实题 web 强制 on", str(p1.get("web")) == "on", p1.get("web"))
    ck("③ route 恒为四层 0,1,both,all", str(p1.get("route")) == "0,1,both,all",
       p1.get("route"))
    ck("④ 含 m4 与 local_llm.metrics",
       isinstance(p1.get("m4"), dict)
       and isinstance((p1.get("local_llm") or {}).get("metrics"), dict))

    p2 = _plan(q_reason)
    ck("⑤ 推理题 scenario=reasoning", _kind(p2) == "reasoning",
       p2.get("scenario"))
    ck("⑥ 推理题 web 不强制 on（非事实）", str(p2.get("web")) in ("on", "off", "auto"),
       p2.get("web"))

    p3 = _plan(q_choice)
    # ★ [Round 91] 选项题（A./B./C./D. ≥2）→ choice 且 web on（引擎事实门需证据）
    _q_opt = ("以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气")
    _p_opt = _plan(_q_opt)
    ck("⑦b 选项题 scenario=choice 且 web on",
       _kind(_p_opt) == "choice" and str(_p_opt.get("web")) == "on",
       (_kind(_p_opt), _p_opt.get("web")))
    ck("⑦ 选择题 scenario=choice", _kind(p3) == "choice",
       p3.get("scenario"))

    p4 = _plan(q_fact, balance=0.1)
    ck("⑧ 低预算事实题：fast 且 web on",
       str(p4.get("tier")) == "fast" and str(p4.get("web")) == "on",
       (p4.get("tier"), p4.get("web")))

    for p in (p1, p2, p3, p4):
        ck("⑨ dual_judge_mode 合法（llm/cache/auto/None）",
           str(p.get("dual_judge_mode")) in ("llm", "cache", "auto", "None"),
           p.get("dual_judge_mode"))
        ck("⑩ self_check_mode 合法（llm/cache/auto/None）",
           str(p.get("self_check_mode")) in ("llm", "cache", "auto", "None"),
           p.get("self_check_mode"))

    ck("⑪ 预算守卫字段存在", isinstance(p1.get("budget_guard"), dict))
    ck("⑫ 模式可审计（mode_id/requested）",
       bool(p1.get("mode_id")) and p1.get("requested") is not None)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
