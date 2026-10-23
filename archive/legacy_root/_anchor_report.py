# -*- coding: utf-8 -*-
"""[v1.21.73 外部锚点对照] 两臂对表 —— 按 `_anchor_prereg.json` 事前写死的判据出数。

★ 本脚本只读两臂的 full.json + 产物 md，**不重新评估、不再调 LLM**。
  所有门槛都在预注册里写死，这里只负责算和判，不负责挑好看的数字。

用法：
  python _anchor_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREG = HERE / "_anchor_prereg.json"

# 空闲价 ¥/M token（官网 2026-10-04，deepseek-flash）：未命中输入 1 / 输出 4
PRICE_IN, PRICE_OUT = 1.0, 4.0
OUT_SHARE = 0.575  # 探针实测输出占 token 57.5%


PFX = None


def load(tag: str) -> dict | None:
    p = HERE / f"{PFX}_{tag}.full.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def money(tok: int) -> float:
    return (tok * OUT_SHARE * PRICE_OUT
            + tok * (1 - OUT_SHARE) * PRICE_IN) / 1_000_000


def bar(n: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "─" * width
    f = max(0, min(width, round(n / total * width)))
    return "█" * f + "·" * (width - f)


def main() -> int:
    global PFX
    PFX = sys.argv[1] if len(sys.argv) > 1 else "v73arm"
    print(f"（读数前缀 {PFX}）\n")
    on, off = load("ON"), load("OFF")
    if on is None or off is None:
        miss = [t for t, d in (("ON", on), ("OFF", off)) if d is None]
        print(f"❌ 缺侧车：{miss} —— 先跑完两臂")
        return 1

    ea = on.get("external_anchor")
    dec_on = on.get("decidability") or {}
    dec_off = off.get("decidability") or {}
    sm = (ea or {}).get("summary") or {}

    L: list[str] = []
    add = L.append

    add("=" * 60)
    add("v1.21.73 外部锚点对照 · 两臂对表")
    add("=" * 60)
    add("")

    # ── 先查「差异项只有一个」这条前置 ────────────────────────────
    k_on, k_off = set(on.keys()), set(off.keys())
    only_on, only_off = sorted(k_on - k_off), sorted(k_off - k_on)
    add("[前置] packed 键差")
    add(f"  ON  独有键：{only_on or '（无）'}")
    add(f"  OFF 独有键：{only_off or '（无）'}")
    if only_on == ["external_anchor"] and not only_off:
        add("  ✅ 差异项恰为 external_anchor 一个键，对照成立")
    else:
        add("  ❌ 差异项不止锚点一个键 —— 按预注册，对照作废，需点名解释")
    add("")

    # ── M1 / M2 / M3 ────────────────────────────────────────────
    claims = int(sm.get("claims") or 0)
    sup = int(sm.get("supported") or 0)
    con = int(sm.get("conflicted") or 0)
    unm = int(sm.get("unmatched") or 0)
    used = int(sm.get("anchor_used") or 0)
    anchors_n = int((ea or {}).get("anchors") or 0)

    add("─" * 60)
    add("[M1] 结论条目数 claims")
    add(f"  claims = {claims}")
    if claims == 0:
        add("  ⚠️ 踩零触发线：本次零触发。★ 不得解读为「没有冲突」"
            " —— 判据缺失与判据为 0 是两回事")
    else:
        add(f"  ✅ 有 {claims} 条结论进入对照")

    add("")
    add("[M2] 锚点使用数")
    add(f"  anchor_used = {used} / anchors = {anchors_n}"
        + (f"  {bar(used, anchors_n)}" if anchors_n else ""))
    if used == 0:
        add("  ❌ 踩接入失败线：锚点未真正接入，整套对照判为无效")
    else:
        add(f"  ✅ 12 条锚点里 {used} 条被真正引用到判定理由中")

    add("")
    add("[M3] 三态分布（主结论，不合成单一分数）")
    for name, n, mk in (("印证 supported", sup, "✅"),
                        ("冲突 conflicted", con, "❌"),
                        ("无对应 unmatched", unm, "➖")):
        add(f"  {mk} {name:<16} {n:>3} / {claims:<3} {bar(n, claims)}")
    if claims > 0:
        ratio = con / claims
        add(f"  conflicted ÷ claims = {ratio:.3f}")
        if ratio >= 0.20:
            add(f"  ✅ 过冲突张力线（≥0.20）：结论与外部事实存在实质张力")
        elif ratio < 0.05:
            add("  ⚠️ 低于 0.05：本次未检出张力（不等于不存在，见已知边界）")
        else:
            add("  ～ 落在 0.05~0.20 之间：有张力但不到「实质」门槛")

    add("")
    add("[M4] 外判有没有真引用锚点")
    refs = dec_on.get("anchor_refs")
    given = dec_on.get("_anchors_given")
    add(f"  anchor_refs     = {refs}")
    add(f"  _anchors_given  = {given}")
    if refs:
        add(f"  ✅ 外判这一路确实引用了锚点编号 {refs}")
    else:
        add("  ➖ 外判未引用编号（只说明没引用，不说明没看到 —— prompt 里确实附了）")
    add(f"  对照：OFF 臂 decidability 键里是否有 anchor_refs = "
        f"{'anchor_refs' in dec_off}")

    add("")
    add("[M5] 两臂运行形态差")
    rows = [("llm_calls", on.get("llm_calls"), off.get("llm_calls")),
            ("llm_tokens", on.get("llm_tokens"), off.get("llm_tokens"))]
    for k, a, b in rows:
        d = (a or 0) - (b or 0)
        pct = (d / b * 100) if b else 0.0
        add(f"  {k:<12} ON={a:<8} OFF={b:<8} 差={d:+d}  ({pct:+.1f}%)")
    cd = (on.get("llm_calls") or 0) - (off.get("llm_calls") or 0)
    td = (on.get("llm_tokens") or 0) - (off.get("llm_tokens") or 0)
    tpct = td / off.get("llm_tokens", 1) * 100
    if abs(cd) <= 2 and abs(tpct) <= 15:
        add("  ✅ 过形态线：锚点没改变运行形态（calls 差 ≤2 且 token 差 ≤15%）")
    else:
        add(f"  ⚠️ 超形态线：多出来的 {cd} 次调用 / {td:+d} token 要解释花在哪")
    for k in ("decidability", "_source", "_divergent", "_pool_status",
              "_ext_status"):
        add(f"  decidability.{k:<14} ON={dec_on.get(k)!r:<22} "
            f"OFF={dec_off.get(k)!r}")
    lc_on = on.get("layer_contribution")
    lc_off = off.get("layer_contribution")
    add(f"  layer_contribution ON ={json.dumps(lc_on, ensure_ascii=False)}")
    add(f"  layer_contribution OFF={json.dumps(lc_off, ensure_ascii=False)}")
    add(f"  层停点 ON ={on.get('dispatch', {}).get('ran')} "
        f"OFF={off.get('dispatch', {}).get('ran')}")

    add("")
    add("[M6] 成本增量")
    add(f"  ON  估 ¥{money(on.get('llm_tokens') or 0):.3f}"
        f"  OFF 估 ¥{money(off.get('llm_tokens') or 0):.3f}"
        f"  差 ¥{money(td):.3f}")
    add(f"  （按空闲价 输入¥{PRICE_IN}/M · 输出¥{PRICE_OUT}/M · "
        f"输出占比 {OUT_SHARE} 折算，仅供量级参考）")

    # ── 逐条对照明细 ────────────────────────────────────────────
    add("")
    add("─" * 60)
    add("[逐条] 对照明细（计数比逐条 note 可信，note 只作线索）")
    for it in (ea or {}).get("items") or []:
        mk = {"印证": "✅", "冲突": "❌", "无对应": "➖"}.get(it.get("verdict"), "?")
        add(f"  {mk} {it.get('verdict')} | {it.get('claim', '')}")
        add(f"      锚点 {it.get('anchor_ids')} | {it.get('note', '')}")
    if (ea or {}).get("error"):
        add(f"  error: {ea['error']}")
    add(f"  source_file={ (ea or {}).get('source_file') } "
        f"retrieved_at={(ea or {}).get('retrieved_at')} "
        f"retriever={(ea or {}).get('retriever')}")

    # ── 产物 md 差异 ────────────────────────────────────────────
    add("")
    add("─" * 60)
    add("[产物] md 侧")
    # packed 里没有产物路径（v1.21.73 的 packed 仍是 17 键 + 可选 external_anchor），
    # 从跑臂日志尾部的「产物=」行取 —— 那是 save_result 的返回值。
    def md_of(tag: str) -> Path:
        lp = HERE / f"{PFX}_{tag}.log"
        if not lp.exists():
            return Path("")
        for line in lp.read_text(encoding="utf-8").splitlines():
            if line.startswith("产物="):
                return Path(line[len("产物="):].strip())
        return Path("")

    md_on, md_off = md_of("ON"), md_of("OFF")
    if md_on.exists() and md_off.exists():
        t_on = md_on.read_text(encoding="utf-8")
        t_off = md_off.read_text(encoding="utf-8")
        add(f"  ON  {md_on.name}  {len(t_on)} 字符")
        add(f"  OFF {md_off.name}  {len(t_off)} 字符")
        for key in ("外部锚点", "逐条对照", "印证", "冲突"):
            add(f"  「{key}」出现次数 ON={t_on.count(key)} OFF={t_off.count(key)}")
    else:
        add(f"  产物路径未落 packed：ON={md_on} OFF={md_off}")

    add("")
    add("=" * 60)
    txt = "\n".join(L)
    out = HERE / f"_anchor_report_{PFX}.txt"
    out.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    print(f"\n已写入 {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
