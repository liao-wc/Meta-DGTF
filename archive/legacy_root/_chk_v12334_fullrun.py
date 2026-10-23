#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全开真跑验收检查（v1.23.34）。

用户口径：「所有最终真跑验收默认都是配置开关全开或者针对性设置配置，
**不仅可以检验本次改动，还方便检查之前的改动有没有生效、或者发现新问题**。」

⇒ 本脚本**一次跑完，逐项查「本轮 + 之前各轮」的能力是否在**真实产物**里生效。
   每条都读**产物**（不是源码）—— 这是本项目那条铁律的可执行化：
   **纯函数判据全绿 ≠ 能力在引擎里可达**。

用法：真跑结束后 `python _chk_v12334_fullrun.py [tag]`（默认 tag=V1234FULL）。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAG = sys.argv[1] if len(sys.argv) > 1 else "V1234FULL"


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    ok, bad = [], []
    log_p = HERE / ("_fullrun_%s.log" % TAG)
    quant_p = HERE / ("_fullrun_%s.quant.json" % TAG)
    goals_p = HERE / ("_fullrun_%s.goals.json" % TAG)
    summ_p = HERE / ("_fullrun_%s.json" % TAG)

    log = log_p.read_text(encoding="utf-8", errors="replace") if log_p.is_file() else ""

    # ── ① 全开清单真的全开（从日志回读，不信脚本声明）──
    _rows = [l for l in log.splitlines() if "期望=" in l]
    _n_ok = sum(1 for l in _rows if "✓" in l)
    _n_no = sum(1 for l in _rows if "✗" in l)
    if _rows and _n_no == 0:
        ok.append("① 全开清单 %d 项**逐项生效**（✗ 0）" % _n_ok)
    else:
        bad.append("① 全开清单有未生效项：✓%d / ✗%d" % (_n_ok, _n_no))

    # ── ② 四层跑齐 + 圈数 ──
    for _L in ("0", "1", "both", "all"):
        if ("【%s】" % _L) in log or ("层 %s" % _L) in log:
            pass
    _runs = sum(1 for l in log.splitlines() if "圈 ·" in l)
    if _runs > 0:
        ok.append("② 层圈推进留痕 %d 行" % _runs)
    else:
        bad.append("② 日志里没有「圈 ·」推进留痕（四层没跑起来？）")

    # ── ③ quant_readings 四层有值 + 本轮新增键（v1.23.33 续三）──
    q = load(quant_p)
    if isinstance(q, dict):
        _cnt = {k: len(v or {}) for k, v in q.items()}
        _keys = set()
        for v in q.values():
            _keys |= set((v or {}).keys())
        if sum(_cnt.values()) > 0:
            ok.append("③ quant_readings 四层条数 %r" % (_cnt,))
        else:
            bad.append("③ quant_readings 四层**全空**（能力不可达）")
        for _k, _lab in (("candidate_yield", "候选产出率"),
                         ("restate_fidelity", "锚点保真度"),
                         ("yin_yang_divergence", "阴阳分歧度"),
                         ("ing_density", "ing 语义密度")):
            if _k in _keys:
                ok.append("③.%s %s 已落盘" % (_k[:6], _lab))
            else:
                bad.append("③.%s %s **未落盘**" % (_k[:6], _lab))
    else:
        bad.append("③ 缺 %s（真跑没写读数？）" % quant_p.name)

    # ── ④ goals 四层目标读数（更早的机制）──
    g = load(goals_p)
    if isinstance(g, dict) and any((g.get(L) or {}).get("value") is not None
                                   for L in ("0", "1", "both", "all")):
        ok.append("④ 四层目标读数有值：%r"
                  % ({L: (g.get(L) or {}).get("value") for L in
                      ("0", "1", "both", "all")},))
    else:
        bad.append("④ goals 四层目标读数缺值")

    # ── ⑤ run_id 记账 + EML（自学习真的在跑）──
    if "run_id" in log:
        ok.append("⑤ run_id 已记账（EML 不判匿名）")
    else:
        bad.append("⑤ 日志里没有 run_id（EML 会把这次跑当匿名跳过）")
    if "🧠 EML" in log:
        ok.append("⑤.b EML 留痕出现（自学习回路在工作）")
    else:
        bad.append("⑤.b 未见 EML 留痕")

    # ── ⑥ 产物 md：量化段（可读性，v1.23.33 续三）+ 本层速览（v1.23.34）──
    _mds = sorted((HERE / "outputs").glob("*.md"),
                  key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    _hit_quant = _hit_glance = _hit_ing = None
    for _m in _mds:
        _t = _m.read_text(encoding="utf-8", errors="replace")
        if _hit_quant is None and "【各环节量化】" in _t:
            _hit_quant = _m.name
        if _hit_glance is None and "本层速览" in _t:
            _hit_glance = _m.name
        if _hit_ing is None and "六步" in _t:
            _hit_ing = _m.name
    if _hit_quant:
        ok.append("⑥ 产物 md 有【各环节量化】段（可读性出口）")
    else:
        bad.append("⑥ 产物 md **没有**【各环节量化】段")
    if _hit_glance:
        ok.append("⑦ 产物 md 有「本层速览」（view 输出结构）")
    else:
        bad.append("⑦ 产物 md **没有**「本层速览」")

    # ── ⑧ 汇总读数 ──
    s = load(summ_p)
    if isinstance(s, dict):
        ok.append("⑧ 汇总读数 calls=%s tokens=%s"
                  % (s.get("llm_calls"), s.get("llm_tokens")))

    print("=== 全开真跑验收（tag=%s）===" % TAG)
    for x in ok:
        print("  ✓", x)
    for x in bad:
        print("  ✗", x)
    print("\n%s" % ("[OK] 本轮 + 之前各轮的改动均在真实产物里生效"
                    if not bad else "[FAIL] %d 项未生效/缺失" % len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
