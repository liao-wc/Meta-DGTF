#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实产物上的「旧口径 vs 独立度」对照（零 LLM 调用）。

做法：读 `outputs/` 下最近的产物 packed，取 `pools.<entry>.undecidable_channel`
的**累计** structural_amps × und_aspects，离线复算两种口径。

★ 取产物一律按 st_mtime 取**最新**（产物名带时间戳，`sorted()[0]` 会读到最旧的）。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.24.py"
OUT = HERE / "_probe_v12324_realdata.txt"


def load_mod():
    spec = importlib.util.spec_from_file_location("dgtf_rd", str(TGT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_rd"] = m
    spec.loader.exec_module(m)
    return m


def main():
    m = load_mod()
    packs = sorted((HERE / "outputs").glob("*.packed.json"),
                   key=lambda p: p.stat().st_mtime)
    lines = []
    lines.append("真实产物「旧口径 vs 独立度」对照（离线，零 LLM）")
    lines.append("被验引擎：%s" % TGT.name)
    lines.append("候选 packed 共 %d 份（按 mtime 排序，最新在后）" % len(packs))
    lines.append("")
    hdr = ("%-46s %-5s %8s %6s %6s %6s %6s %8s"
           % ("产物（截断）", "层", "旧口径", "命中", "分母", "结构数", "独立数", "独立度"))
    lines.append(hdr)
    lines.append("-" * len(hdr))

    rows = 0
    for p in packs:
        try:
            d = json.loads(p.read_bytes().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            lines.append("  [跳过] %s：%s" % (p.name[:40], e))
            continue
        pools = d.get("pools") or {}
        for entry, pool in sorted(pools.items()):
            uc = (pool or {}).get("undecidable_channel") or {}
            amps = [str(x) for x in (uc.get("structural_amps") or [])]
            asps = [str(x) for x in (uc.get("und_aspects") or [])]
            if not amps and not asps:
                continue
            free = [a for a in amps
                    if not any(m._overlap_coef(x, a) >= 0.3 for x in asps)]
            indep = (len(free) / len(amps)) if amps else None
            old = uc.get("last_struct_coverage")
            rows += 1
            lines.append("%-46s %-5s %8s %6s %6s %6s %6s %8s" % (
                p.name[:44], entry,
                ("%.3f" % old) if isinstance(old, (int, float)) else "-",
                uc.get("last_struct_hit", "-"), len(asps),
                len(amps), len(free),
                ("%.3f" % indep) if indep is not None else "-"))

    lines.append("")
    lines.append("共 %d 行（层 × 产物）" % rows)

    # 汇总：旧口径为 0 的行数 vs 独立度为 1.0 的行数
    _0 = sum(1 for L in lines if L.strip() and L.split()[-1] != "-"
             and L.count("0.000 ") == 1)
    lines.append("")
    lines.append("读法：旧口径把「独立提炼成功」读成覆盖率 0（读者会当成不及格）；")
    lines.append("      独立度把同一件事读成 1.00（= 结构与评估阶段方面完全不重合）。")

    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    OUT.write_bytes(text.encode("utf-8"))
    sys.stdout.write("[out] %s (%d bytes)\n" % (OUT.name, OUT.stat().st_size))


if __name__ == "__main__":
    main()
