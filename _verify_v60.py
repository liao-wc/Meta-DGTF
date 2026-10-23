# -*- coding: utf-8 -*-
"""[v1.21.60] 真跑验收核对：把 v60_*.log 与产物里的证据抽成一张表。

用法：python _verify_v60.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = sorted(HERE.glob("v60_*.log"))
LOGS = [p for p in LOGS if "selftest" not in p.name]


def tail_meta(text):
    """取 wrapper 追加在末尾的元信息块。"""
    out = {}
    for ln in text.splitlines():
        if "=" in ln and re.match(r"^(tag|mode|rounds|llm_calls|"
                                  r"dispatch\.[a-z]+|decidability|dec_src|"
                                  r"views|产物|耗时)=", ln):
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def pool_counts(text):
    """从产物里抽池计数与分类证据。"""
    d = {}
    m = re.search(r"\*\*可判定性\*\*:\s*(\S+)", text)
    if m:
        d["decidability"] = m.group(1)
    for pat, key in ((r"分解出 .*?（可判定 (\d+)", "拆解_可判定"),
                     (r"（可判定 \d+(?: / 部分 (\d+))? / 不可判定 (\d+)）",
                      "拆解_分布")):
        mm = re.findall(pat, text)
        if mm:
            d[key] = mm[0] if isinstance(mm[0], tuple) else mm[0]
    for key in ("可判定性变更轨迹", "被驳回的可判定性变更", "缺层",
                "迁向不可判定留痕", "复债", "重新挂账",
                "跳过", "自然安住", "体力耗尽"):
        d[key] = text.count(key)
    return d


def main():
    if not LOGS:
        print("还没有 v60_*.log（批次没跑完？）")
        return 2
    print(f"共 {len(LOGS)} 份真跑日志\n")
    rows = []
    for p in LOGS:
        text = p.read_text(encoding="utf-8", errors="replace")
        meta = tail_meta(text)
        prod = ""
        pf = meta.get("产物", "")
        if pf and Path(pf).exists():
            prod = Path(pf).read_text(encoding="utf-8", errors="replace")
        pc = pool_counts(prod) if prod else {}
        rows.append((p.name, meta, pc))

    print(f"{'日志':46} {'模式':>6} {'圈':>3} {'调用':>5}  "
          f"{'缺层':>4} {'跳过':>4} {'分类':<12} {'产物KB':>7}")
    print("-" * 108)
    for name, meta, pc in rows:
        kb = ""
        pf = meta.get("产物", "")
        if pf and Path(pf).exists():
            kb = f"{Path(pf).stat().st_size/1024:.0f}"
        print(f"{name[:46]:46} {meta.get('mode','?'):>6} "
              f"{meta.get('rounds','?'):>3} {meta.get('llm_calls','?'):>5}  "
              f"{(meta.get('dispatch.missing','?') or '?')[:4]:>4} "
              f"{(meta.get('dispatch.skipped','?') or '?')[:4]:>4} "
              f"{pc.get('decidability','?'):<12} {kb:>7}")

    print("\n=== ② 分类分布（本轮最关心的）===")
    dist = {}
    for name, meta, pc in rows:
        k = pc.get("decidability", "?")
        dist[k] = dist.get(k, 0) + 1
        print(f"  {name[:40]:40} 分离判定={pc.get('decidability','?'):<12} "
              f"拆解分布={pc.get('拆解_可判定','?')}")
    print(f"  分布：{dist}")
    print("  ★ 若全为 partial 且拆解里『不可判定 0』→ koan 事实上不再进入；"
          "若出现 undecidable → koan 仍可达。")

    print("\n=== ③ C/E/G/H 是否都跑通且产物完整 ===")
    want = {"modeC": "C", "modeE": "E", "modeG": "G", "modeH": "H"}
    for tag, mode in want.items():
        hit = [r for r in rows if r[0].startswith(f"v60_{tag}_")]
        if not hit:
            print(f"  ✗ {mode} 没有日志")
            continue
        _n, meta, pc = hit[0]
        miss = meta.get("dispatch.missing", "?")
        print(f"  {'✓' if miss in ('[]', '') else '✗'} {mode}: "
              f"missing={miss} views={meta.get('views','?')} "
              f"分类={pc.get('decidability','?')}")

    print("\n=== 本轮 5 处修正的真跑证据 ===")
    for key, label in (("缺层", "① 缺层守卫（应 0，除非真失败）"),
                       ("跳过", "① 跳过留痕（并行模式以前恒为 0）"),
                       ("可判定性变更轨迹", "转态账（新机制）"),
                       ("被驳回的可判定性变更", "驳回留痕"),
                       ("迁向不可判定留痕", "老 escalations 路径"),
                       ("自然安住", "停止判据（收口后仍在）"),
                       ("体力耗尽", "截断（对照）")):
        tot = sum(r[2].get(key, 0) for r in rows)
        print(f"  {label:32} 合计 {tot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
