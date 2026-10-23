#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.21.69 前置探针] 先把 A/B/C/D/E 五项「改之前」的实测值量出来。

目的：本项目最贵的一课是「断言会假通过」「凭想象断言」。所以任何一项改动
落地之前，先用**生产入口**（不是手造对象）量出改前基线；改完再量一次，
用同一支探针做前后对照。没有对照的"修好了"不算数。

五项的量法：
  A `_b_merge` 缩进 —— 用 MetaDGTF._b_merge 真跑一遍，看 amps=3 条时
    `all_amp_cands` 被加了几次（旧=15，新=5）。
  B 不可判定覆盖率 —— 用 V68 真产物里的 und_aspects / structural_amps /
    aligned_amps，分别算两个口径（旧只算头一个，恒 0）。
  C `object_desc` —— 用 DGTF._ing 真跑一遍，把喂给模型的
    「对撞的对象是：…」原样截下来（不看代码分支，看模型真收到什么）。
  D `_untraced_undecidable` —— 用 V68 真产物里的 und_aspects + evidence
    真跑一遍，看几条被判「无池内追溯」（实为误报）。
  E 日志累积字段 —— 用 verif_V68.log 真数一遍：每段留痕里
    round_log / roles_run / carry_checks 到底几项。

用法：python _probe_v69_abcde.py [目标py]   （默认指向 V1.21.68）
"""
import copy
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE / "元DGTF-V1.21.68.py")
V68JSON = HERE / "verif_V68.full.json"
V68LOG = HERE / "verif_V68.log"

os.environ.setdefault("DGTF_API_KEY", "sk-probe-key")

_spec = importlib.util.spec_from_file_location("dgtf_probe", str(SRC))
mod = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_probe"] = mod
_spec.loader.exec_module(mod)

print("== 目标 ==")
print("  SRC =", SRC.name, "| __version__ =", getattr(mod, "__version__", "?"))


def _cfg():
    return copy.deepcopy(mod.DEFAULT_CONFIG)


# ---------------------------------------------------------------- A
def probe_A():
    print("\n== A · _b_merge 的 all_amp_cands 累加次数 ==")
    cfg = _cfg()
    md = mod.MetaDGTF(cfg)

    def _run(amps, cand):
        v = mod.View(entry="0")
        v.amps = [{"desc": d} for d in amps]
        v._amp_cand_count = cand
        st = {"all_candidates": [], "all_amps": [], "all_amp_cands": 0,
              "all_threads": [], "all_dec_products": [],
              "all_und_products": []}
        md._b_merge("0", v, st)
        return st["all_amp_cands"]

    got1 = _run(["a1", "a2", "a3"], 5)
    got2 = _run([], 7)
    print(f"  amps=3 条且 _amp_cand_count=5 → all_amp_cands={got1} "
          f"（正确=5，重复累加则=15）")
    print(f"  amps=0 条且 _amp_cand_count=7 → all_amp_cands={got2} "
          f"（正确=7，漏累加则=0）")
    return got1, got2


# ---------------------------------------------------------------- B
def probe_B():
    print("\n== B · 不可判定覆盖率用错输入 ==")
    if not V68JSON.exists():
        print("  （没有 verif_V68.full.json，跳过）")
        return None
    d = json.loads(V68JSON.read_text(encoding="utf-8"))
    ch = d["pools"]["1"]["undecidable_channel"]
    aspects = ch["und_aspects"]
    struct = ch["structural_amps"]
    aligned = ch.get("aligned_amps") or []

    def hits(pool, thr=0.3):
        if not aspects or not pool:
            return []
        return [a for a in aspects
                if any(mod._overlap_coef(a, s) >= thr for s in pool)]

    hs, ha = hits(struct), hits(aligned)
    print(f"  und_aspects={len(aspects)} 条 / structural_amps={len(struct)} 条"
          f" / aligned_amps={len(aligned)} 条")
    print(f"  旧口径 struct_cov = {len(hs)}/{len(aspects)}"
          f" = {len(hs) / len(aspects):.3f}   （产物里记的是 "
          f"{ch.get('last_struct_coverage')}）")
    print(f"  新口径 aligned_cov = {len(ha)}/{len(aspects)}"
          f" = {len(ha) / len(aspects):.3f}")
    for a in ha:
        print(f"      · 命中：{a[:48]}")

    # 走**生产入口**再量一次：Pool.add_undecidable 真跑，看通道里落了什么键
    p = mod.Pool()
    p.add_undecidable({"structural_amps": struct, "aligned_amps": aligned,
                       "clarity": 0.78}, aspects, layer=1)
    print(f"  生产入口 add_undecidable → "
          f"last_struct_coverage={p.undecidable_channel.get('last_struct_coverage')}"
          f" / last_struct_hit={p.undecidable_channel.get('last_struct_hit')}")
    if "last_aligned_coverage" in p.undecidable_channel:
        print(f"                          → "
              f"last_aligned_coverage="
              f"{p.undecidable_channel.get('last_aligned_coverage')}"
              f" / last_aligned_hit="
              f"{p.undecidable_channel.get('last_aligned_hit')}")
    else:
        print("                          → （该版本没有 last_aligned_coverage"
              " 这个键 ⇒ aligned 口径无出口）")
    return len(hs), len(ha), len(aspects)


# ---------------------------------------------------------------- C
def probe_C():
    print("\n== C · ing 收到的「对撞的对象」= ==")
    cfg = _cfg()
    out = {}
    for entry in ("0", "1", "both", "all"):
        dg = mod.DGTF(entry, mod.LLM(cfg), cfg)
        dg.verbose = False
        cap = {}

        def _fake_long(system, user, *a, **k):
            cap["system"] = system
            cap["user"] = user
            return "对撞正文占位", False
        dg._call_long = _fake_long
        for is_base in (True, False):
            inp = mod.Input(question="原始问题" if is_base else None,
                            round_role="转向", round_no=2)
            if not is_base:
                up = []
                for i in range(2 if entry in ("both",) else 3):
                    uv = mod.View(entry="0")
                    uv.manifest = f"上游{i}的 manifest"
                    uv.collision = f"上游{i}的 ing"
                    up.append(uv)
                inp.upstream_views = up
            inp.pool = mod.Pool()
            cands = [mod.Candidate(desc="候选甲"), mod.Candidate(desc="候选乙")]
            try:
                dg._ing(cands, inp, "锚点原文", mod.View(entry=entry))
            except Exception as e:
                print(f"  entry={entry} is_base={is_base} → 抛异常 "
                      f"{type(e).__name__}: {e}")
                continue
            sys_p = cap.get("system", "")
            usr_p = cap.get("user", "")
            m = re.search(r"对撞的对象是：(.+)", sys_p)
            obj = m.group(1).strip() if m else "（没有这一行）"
            m2 = re.search(r"以下是(.+?)说过的话", usr_p)
            intro = m2.group(1).strip() if m2 else "（无上游 speech 段）"
            out[(entry, is_base)] = (obj, intro)
            print(f"  entry={entry:4s} is_base={str(is_base):5s} → "
                  f"对象=「{obj}」  上游引入语=「{intro}」")
    return out


# ---------------------------------------------------------------- D
def probe_D():
    print("\n== D · _untraced_undecidable 的误报 ==")
    if not V68JSON.exists():
        print("  （没有 verif_V68.full.json，跳过）")
        return None
    d = json.loads(V68JSON.read_text(encoding="utf-8"))
    dec = d["decidability"]
    und = dec["undecidable_aspects"]
    ev = dec["evidence"]
    old = mod._untraced_undecidable(und, ev)
    print(f"  旧判据（_similar 0.55 + 子串）：{len(old)}/{len(und)} 条被判无追溯")
    for x in old:
        print(f"      ✗ {x[:52]}")

    # 加一层「包含度」判据（分母取 min），local 复刻，不动源码
    def _bare(t):
        t = re.sub(r"[（(\[【]\s*(?:候选|amp|&|印记|悬置|suspension|thread|"
                   r"线头|外)?\s*[0-9A-Za-z]*\s*[)）\]】]", "", str(t))
        return re.sub(r"[，。、；：:,\.;\s]+", "", t).strip()

    srcs = [_bare(e.get("aspect", "")) for e in ev
            if isinstance(e, dict)]
    srcs = [s for s in srcs if s]

    def _new(und_aspects, evidences, thr=0.55, ov_thr=0.6):
        out = []
        for a in und_aspects:
            s = str(a).strip()
            if not s:
                continue
            bs = _bare(s)
            if not any(mod._similar(bs, x, thr) or mod._similar(x, bs, thr)
                       or (bs and x and (bs in x or x in bs))
                       or mod._overlap_coef(bs, x) >= ov_thr
                       for x in srcs):
                out.append(s)
        return out

    new = _new(und, ev)
    print(f"  新判据（+_overlap_coef≥0.6）  ：{len(new)}/{len(und)} 条被判无追溯")
    for x in new:
        print(f"      ✗ {x[:52]}")
    # 逐条给出救回来的那条的系数，证明判据有判别力而不是随手放宽
    for a in old:
        bs = _bare(a)
        best = max(((round(mod._overlap_coef(bs, x), 3), x) for x in srcs),
                   default=(0.0, ""))
        print(f"      救回：{a[:34]}… → 最高包含度 {best[0]} "
              f"vs「{best[1][:22]}」")
    return len(old), len(new)


# ---------------------------------------------------------------- E
def probe_E():
    print("\n== E · 日志里的累积型字段 ==")
    if not V68LOG.exists():
        print("  （没有 verif_V68.log，跳过）")
        return None
    s = V68LOG.read_text(encoding="utf-8", errors="replace")
    lines = s.split("\n")
    idx = [i for i, l in enumerate(lines) if "圈全量留痕 ·" in l]
    print(f"  日志 {len(s)} 字符 / {len(lines)} 行；留痕段 {len(idx)} 段")
    rows = []
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(lines)
        blk = lines[i:j]
        head = re.search(r"entry=(\S+) · 第 (\d+) 圈", blk[0])
        row = {"seg": n + 1,
               "entry": head.group(1) if head else "?",
               "round": head.group(2) if head else "?",
               "chars": sum(len(x) for x in blk)}
        for f in ("round_log", "roles_run", "carry_checks",
                  "carry_dropped_all", "rehashed"):
            m = re.search(r"[├└] " + f + r"：\w+ (\d+) 项", "\n".join(blk))
            row[f] = int(m.group(1)) if m else None
        rows.append(row)
    hdr = ("seg", "entry", "round", "chars", "round_log", "roles_run")
    print("  " + " | ".join(hdr))
    for r in rows:
        print("  " + " | ".join(str(r[k]).rjust(len(h)) for k, h in
                                zip(hdr, hdr)))
    print("  → 累积型字段在各段留痕里的项数如上；全 0 表示**从未被 dump**"
          "（不是重复）。")
    print("  → 各段体积主要由 candidates / rendered / untouched 撑起"
          "（逐圈内容，非累积）。")
    biggest = sorted(rows, key=lambda r: -r["chars"])[:1]
    if biggest:
        print(f"  → 最大一段 {biggest[0]['chars']} 字符"
              f"（entry={biggest[0]['entry']} 第 {biggest[0]['round']} 圈）")
    return rows


if __name__ == "__main__":
    a = probe_A()
    b = probe_B()
    c = probe_C()
    d = probe_D()
    e = probe_E()
    print("\n== 汇总 ==")
    print(f"  A: {a}   （期望 新={5, 7} / 旧={15, 0}）")
    print(f"  B: {b}   （旧 hit/新 hit/总数）")
    print(f"  C: {len(c)} 个组合")
    print(f"  D: {d}   （旧误报条数 / 新误报条数）")
    print(f"  E: {len(e) if e else 0} 段留痕")
