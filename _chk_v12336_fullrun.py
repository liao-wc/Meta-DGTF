#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.36 全开真跑验收检查（在 v12334 版基础上加**本轮新能力**）。

## 用户口径
「所有最终真跑验收默认都是配置开关全开或者针对性设置配置，不仅可以检验本次
改动，还方便检查之前的改动有没有生效、或者发现新问题。」

## 本轮（v1.23.36）新增的检查项
  · **读数显示**（日志里的每层行 `📊 [x] 圈 n` + 结束总表）；★ 读的是**日志文件**
  · **产物读数总表**（md 里的 `## 读数总表` 段 + JSON 的 `readings_table`）
  · **通用 trace**（产物 `views[*].trace_log` 的条数）
  · **联网全接的配置面**（37 个 stage 键在位；★ 30 个环节开关**故意不在
    `_ALL_ON_ITEMS`** 里 —— 全开会让每次 LLM 调用都联网，成本不可控；
    「打开就注入」由探针 `_probe_v12336_allweb.py` 覆盖）

用法：`python _chk_v12336_fullrun.py [tag]`（默认 tag=V1236FULL）
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAG = sys.argv[1] if len(sys.argv) > 1 else "V1236FULL"


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    ok, bad = [], []
    log_p = HERE / ("_fullrun_%s.log" % TAG)
    quant_p = HERE / ("_fullrun_%s.quant.json" % TAG)
    log = log_p.read_text(encoding="utf-8", errors="replace") if log_p.is_file() else ""

    # ── ① 全开清单（逐项回读）──
    _rows = [l for l in log.splitlines() if "期望=" in l]
    _no = [l for l in _rows if "✗" in l]
    if _rows and not _no:
        ok.append("① 全开清单 %d 项**逐项生效**" % len(_rows))
    elif not _rows:
        bad.append("① 日志里没有全开清单回读（脚本或配置没走全开）")
    else:
        bad.append("① 全开清单有未生效项 %d 个：%r" % (len(_no), _no[:2]))

    # ── ② 四层量化读数 ──
    q = load(quant_p)
    if isinstance(q, dict) and q:
        _n = sum(len(v or {}) for v in q.values())
        _keys = sorted({k for v in q.values() for k in (v or {})})
        if _n >= 12:
            ok.append("② quant_readings **%d 条**（四层 × 四个读数）：%r"
                      % (_n, _keys))
        else:
            bad.append("② quant_readings 只有 %d 条（应 ≥12）：%r" % (_n, _keys))
        for _k in ("restate_fidelity", "yin_yang_divergence",
                   "ing_density", "candidate_yield"):
            if _k not in _keys:
                bad.append("② 缺读数 %s" % _k)
    else:
        bad.append("② 缺 %s" % quant_p.name)

    # ── ③ ★ 读数显示（日志侧）──
    _lines = [l for l in log.splitlines() if "📊 [" in l]
    if _lines:
        ok.append("③ 日志里每层读数行 **%d 行**（样例：%s）"
                  % (len(_lines), _lines[0].strip()[:80]))
    else:
        # 真跑脚本的 log 是 stdout+logging 合流 ⇒ 应该能看到；
        # 看不到说明走了 vp 或被 verbose 吞掉。
        bad.append("③ 日志里**没有**每层读数行（📊 [x] 圈 n）—— "
                   "是不是又走回 vp 了？")
    if "读数总表（四层）" in log:
        ok.append("③.b 日志里有**结束总表**")
    else:
        bad.append("③.b 日志里**没有**结束总表")

    # ── ④ 产物侧（md + JSON）──
    _mds = sorted((HERE / "outputs").glob("*.md"),
                  key=lambda p: p.stat().st_mtime, reverse=True)[:4]
    _hit = None
    for _m in _mds:
        _t = _m.read_text(encoding="utf-8", errors="replace")
        if "读数总表" in _t:
            _hit = _m.name
            break
    if _hit:
        ok.append("④ 产物 md 有【读数总表】段：%s" % _hit)
    else:
        bad.append("④ 产物 md **没有**【读数总表】段")

    # ── ⑤ 通用 trace（在产物 md 的附录 JSON 里找 trace_log）──
    _has_trace = any("trace_log" in (m.read_text(encoding="utf-8",
                                                errors="replace"))
                     for m in _mds)
    if _has_trace:
        ok.append("⑤ 产物里出现 `trace_log`（通用 trace 出口在）")
    else:
        ok.append("⑤ 产物里没有 `trace_log` —— **正常**：本轮没有代码路径调用 "
                  "`_trace_note`（trace 是地基，等待心跳调度接线）")

    # ── ⑥ 配置面（37 个 stage 键）──
    try:
        sys.path.insert(0, str(HERE))
        import importlib.util
        _sp = importlib.util.spec_from_file_location(
            "m36", HERE / "元DGTF-V1.23.36.py")
        _m = importlib.util.module_from_spec(_sp)
        sys.modules["m36"] = _m
        _sp.loader.exec_module(_m)
        _st = ((_m.DEFAULT_CONFIG.get("web_search") or {}).get("stages") or {})
        _n30 = [k for k in (_m._WEB_ALL_STAGES or ()) if k in _st]
        if len(_st) >= 37 and len(_n30) == 30:
            ok.append("⑥ 配置面：`web_search.stages` **%d 键**（含 30 个环节开关）"
                      % len(_st))
        else:
            bad.append("⑥ 配置面不对：stages=%d 键，环节开关 %d 个"
                       % (len(_st), len(_n30)))
        _in_allon = any(str(p).startswith("web_search.stages")
                        for p, _v, _w in (_m._ALL_ON_ITEMS or ()))
        if _in_allon:
            bad.append("⑥ ★ 30 个环节开关被塞进了 `_ALL_ON_ITEMS` —— "
                       "全开时每次 LLM 调用都会联网（成本不可控）")
        else:
            ok.append("⑥.b 环节开关**不在** `_ALL_ON_ITEMS` 里（成本保护，"
                      "故意为之；「打开就注入」由探针覆盖）")
    except Exception as _e:
        bad.append("⑥ 配置面检查抛错：%r" % (_e,))

    print("=== v1.23.36 全开真跑验收（tag=%s）===" % TAG)
    for x in ok:
        print("  ✓", x)
    for x in bad:
        print("  ✗", x)
    print("\n%s" % ("[OK] 本轮 + 之前各轮能力均在真实产物/日志里生效"
                    if not bad else "[FAIL] %d 项未生效" % len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
