#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E：用冒烟的真跑路径（verbose=True）抓 stdout，验 v1.21.70 的新渲染可达。

判据（按「段」统计，不用整串 re.search —— 相邻段会互相污染计数）：
  [I] 「本段是**本圈**留痕」出现次数 == 「圈全量留痕」段数
  [H] rendered / manifest 只以 `：str N 字（超大覆盖字段…）` 出现，正文不落日志；
      负对照：其它字段的 │ 正文行仍在（证明不是一刀切）
  [F] 产物 md 里两条轨迹行
  [K] 产物 md 里有「## 七、原始问题覆盖率」（route 含 all 时本就有；
      route 不含 all 的关键证据由真跑验收给）
"""
import contextlib
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st          # noqa: E402

Q = "老城区暴雨内涝，重建排水系统还是局部改造加海绵，怎么权衡？"
SAVE = HERE / st.build_cfg(False)["output"]["save_dir"]


def _cap(mode):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = st.run_mode(mode, Q, verbose=True)
    return buf.getvalue(), r


for mode in ("serial", "B"):
    print("=" * 62)
    print(f"## E2E · mode={mode}")
    print("=" * 62)
    txt, res = _cap(mode)
    Path(f"_E2E_v70_{mode}.stdout.txt").write_text(txt, encoding="utf-8")

    n_seg = txt.count("圈全量留痕 · entry=")
    n_note = txt.count("本段是**本圈**留痕")
    ok_i = bool(n_seg) and n_note == n_seg
    print(f"[I] 「圈全量留痕」段 {n_seg} 个｜说明 {n_note} 次｜"
          f"{'✓ 每段一句' if ok_i else '✗ 不匹配'}")

    n_len = len(re.findall(
        r"├ (rendered|manifest)：str \d+ 字（超大覆盖字段，正文见产物 md）",
        txt))
    leaks = []
    for m in re.finditer(
            r"├ (rendered|manifest)：str \d+ 字（超大覆盖字段，正文见产物 md）\n"
            r"((?:   │ [^\n]*\n)*)", txt):
        body = sum(len(x) for x in m.group(2).splitlines())
        if body:
            leaks.append((m.group(1), body))
    print(f"[H] 「只打长度」行 {n_len} 条｜正文泄漏 {len(leaks)} 处 "
          f"{'✓' if not leaks else '✗ ' + str(leaks[:3])}")
    print(f"[H] 负对照 · 仍逐行打正文的行数（`   │ ` 前缀）= "
          f"{txt.count('   │ ')}（>0 ⇒ 没一刀切）")

    p = SAVE / res["md"]
    print(f"    产物：{p}")
    if p.exists():
        md = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        print(f"[F] 产物含「不可判定独立结构覆盖轨迹」："
              f"{'不可判定独立结构覆盖轨迹' in md}")
        print(f"[F] 产物含「不可判定对齐结构覆盖轨迹」："
              f"{'不可判定对齐结构覆盖轨迹' in md}")
        print(f"[K] 产物含「## 七、原始问题覆盖率」："
              f"{'## 七、原始问题覆盖率' in md}")
        print(f"[K] 负对照 · 其它节标题仍在：{'## 一、' in md}")
    print()
