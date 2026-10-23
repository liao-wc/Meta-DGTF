# -*- coding: utf-8 -*-
"""元DGTF 配置体检（v1.21.61）

用法：
    python _config_lint.py configs/方案B-标准.yaml
    python _config_lint.py configs/*.yaml

它做四件事：
  1) 检查 12 条已知陷阱组合（§8）
  2) 检查未知 / 拼错的键 —— _deep_merge 会默默接受任何键，写错了不报错
  3) 估算调用数 / token / 墙钟（模型见文档 §10，只有两个实测锚点，外推需谨慎）
  4) 打印「实际生效值」—— 尤其是被 cost_profile 改写过的那些
     （shape_* 被缩放、every_n 被 +1），这是最容易报错数的地方

依赖：PyYAML（没有的话会提示，不会崩）
"""
import io
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML：pip install pyyaml")
    sys.exit(2)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

# ---- 配置白名单（从 DEFAULT_CONFIG 提取 + 隐式键）----
KNOWN = {
    "cost_profile", "max_calls",
    "api", "output", "actions", "probe", "memory", "spiral",
}
SUB = {
    "api": {"key", "base_url", "default_model", "reasoner_model",
            "timeout", "max_retries", "retry_backoff"},
    "output": {"save_dir", "verbose", "show_dual_judge", "show_ing",
               "show_manifest", "self_check", "show_probe_diag"},
    "actions": {"assess_decidability", "decompose_question",
                "decidability_source", "decompose_source", "parallel_mode",
                "parallel_warmup_rounds", "pipeline_gate_timeout",
                "parallel_expand", "input_sanity", "re_anchor", "expand_yin",
                "expand_yang", "dual_judge", "ing", "he", "phase_probe",
                "manifest", "self_check", "re_evaluate_pool",
                "settle_research"},
    "probe": {"min_gain", "select_n"},
    "memory": {"channels", "self_layers", "self_layers_per_entry",
               "carry_feedback", "shape_items", "shape_chars"},
    "spiral": {
        "soft_max", "hard_max", "stop_similarity", "stable_need",
        "stable_layers", "batch_similarity", "meta_cover_similarity",
        "idle_limit", "round_idle_limit", "new_item_similarity",
        "new_item_overlap", "thread_new_similarity", "thread_new_overlap",
        "structure_saturation_enabled", "structure_saturation_every_n",
        "round_window", "round_stall_limit", "rehash_similarity",
        "stall_streak_limit", "min_distance_improvement",
        "unsaid_escape_limit", "convergence_window", "all_extra_rounds",
        "both_quota", "both_tighten_ratio", "alignment_similarity",
        "alignment_containment", "dedup_candidate_overlap",
        "dedup_candidate_similarity", "dedup_amp_overlap",
        "dedup_amp_similarity", "qc_rephrase_ratio", "qc_both_ratio",
        "all_drift_threshold", "all_selfref_threshold", "re_eval_every_n",
        "re_eval_recent_k", "min_rounds", "max_uncovered_pushes",
        "per_entry",
    },
}
BOTH_QUOTA_KEYS = {"enabled", "max_ratio", "min_items"}
ENTRIES = ("0", "1", "both", "all")
MODES = {"serial", "A", "B", "C", "D", "E", "F", "G", "H", "auto"}

PROFILE_SHAPE_SCALE = {"quality": 1.0, "balanced": 0.72, "economy": 0.55}
PROFILE_CAND_LIMIT = {"quality": 0, "balanced": 8, "economy": 6}
PROFILE_CALL_ETA = {"quality": 1.00, "balanced": 1.00, "economy": 0.86}
CALLS_PER_LAYER_ROUND = 9.6      # 两个实测锚点一致：125/13 ≈ 220/23 ≈ 9.6
TOKENS_PER_CALL = 4800
SEC_PER_CALL = 8.7               # serial 实测锚点


def load(path):
    try:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"[FATAL] YAML 解析失败：{path}\n  {e}")
        return None
    if not isinstance(cfg, dict):
        print(f"[FATAL] 顶层不是 mapping：{path}")
        return None
    return cfg


def lint(path):
    cfg = load(path)
    if cfg is None:
        return
    print("=" * 68)
    print(f"体检：{path}")
    print("=" * 68)
    warnings, errors = [], []

    # ---------- 1. 未知键 ----------
    for k in cfg:
        if k not in KNOWN:
            warnings.append(f"顶层键 `{k}` 不在白名单：拼错会被静默忽略")
    for seg, allowed in SUB.items():
        body = cfg.get(seg)
        if not isinstance(body, dict):
            continue
        for k in body:
            if k not in allowed:
                warnings.append(
                    f"{seg}.{k} 不是已知键 —— `sp.get()` 会拿默认值，"
                    f"你以为配了，实际没配")
    pe = ((cfg.get("spiral") or {}).get("per_entry") or {})
    for layer, body in pe.items():
        if str(layer) not in ENTRIES:
            errors.append(f"spiral.per_entry.{layer} 不是合法层名 "
                          f"（只能是 {ENTRIES}）")
        elif isinstance(body, dict):
            for k in body:
                if k not in SUB["spiral"] or k == "per_entry":
                    warnings.append(
                        f"spiral.per_entry.{layer}.{k} 不生效：per_entry 只对 "
                        f"spiral 段内、走 _spiral_for 的键生效")

    prof = str(cfg.get("cost_profile", "balanced")).strip().lower()
    if prof not in PROFILE_SHAPE_SCALE:
        warnings.append(f"cost_profile `{prof}` 非法，会回落 balanced")
        prof = "balanced"
    lazy = prof != "quality"

    sp = cfg.get("spiral") or {}
    ghard = int(sp.get("hard_max", 12) or 12)
    gsoft = int(sp.get("soft_max", 3) or 3)
    extra = int(sp.get("all_extra_rounds", 1) or 1)

    # ---------- 2. 逐层预算与软参 ----------
    plan, total = {}, 0
    for e in ENTRIES:
        body = pe.get(e) or pe.get(str(e)) or {}
        hd = int(body.get("hard_max", ghard) or ghard)
        sf = int(body.get("soft_max", gsoft) or gsoft)
        r = hd + (extra if e == "all" else 0)
        plan[e] = (hd, sf, r)
        total += r
        if sf >= hd:
            errors.append(
                f"[陷阱1] {e} 层 soft_max {sf} >= hard_max {hd} → "
                f"「自然安住」判据永远不可能触发")
        if e not in pe and str(e) not in pe:
            warnings.append(
                f"[陷阱6] {e} 层没写 per_entry → 落到全局 hard_max {ghard}；"
                f"实测漏层会把整轮从 9.7min 拉到 20.7min")

    # ---------- 3. 其它陷阱 ----------
    acts = cfg.get("actions") or {}
    mem = cfg.get("memory") or {}

    if prof != "quality" and ("shape_items" in mem or "shape_chars" in mem):
        sc = PROFILE_SHAPE_SCALE[prof]
        warnings.append(
            f"[陷阱2] cost_profile={prof} 会在 __init__ 就地缩放 shape_* "
            f"（×{sc}），你写的 shape_chars/shape_items 会被覆盖。\n"
            f"          要真的生效请用 cost_profile: quality")

    if bool(acts.get("expand_yin", True)) != bool(acts.get("expand_yang", True)):
        warnings.append(
            "[陷阱3] expand_yin / expand_yang 只开一侧 → len(jobs)==1，"
            "economy 的合并展开不触发：只省内容不省调用。要么都开要么都关")

    if int(mem.get("self_layers", 4)) < 4:
        warnings.append(
            "memory.self_layers < 4：超出 cap 的自我记忆会被 blocks[-cap:] "
            "永久丢掉，这不是成本优化（v1.21.56 踩过）")

    if str(acts.get("parallel_mode", "serial")) not in MODES:
        warnings.append("actions.parallel_mode 取值非法，会回落 serial")
    if not acts.get("self_check", True):
        warnings.append(
            "[陷阱10] self_check 关了 → carry_feedback 没了源头，"
            "自省回流约束全线失效")
    for k in ("decidability_source", "decompose_source"):
        if acts.get(k, "pool") != "pool":
            warnings.append(
                f"[陷阱8] actions.{k} != pool → "
                f"「研究层读 0 层产物」这条路径永不生效")
    bq = sp.get("both_quota") or {}
    if isinstance(bq, dict):
        for k in bq:
            if k not in BOTH_QUOTA_KEYS:
                warnings.append(f"spiral.both_quota.{k} 未知")
    tight = float(sp.get("both_tighten_ratio", 0.3))
    quota = float((bq or {}).get("max_ratio", 0.7))
    if bq.get("enabled", True) and tight < quota:
        warnings.append(
            f"[陷阱12] both_tighten_ratio {tight} < both_quota.max_ratio "
            f"{quota}：both 占比在到 {quota} 前已被 {tight} 的改判压下去，"
            f"both_quota 几乎不可能触发（待验证，见 §5.2）")

    if int(sp.get("idle_limit", 2)) >= 3:
        warnings.append(
            "spiral.idle_limit >= 3：5 份真跑日志里没有样本到过 3，"
            "等于基本关闭这条判据")

    mc = int(cfg.get("max_calls", 0) or 0)
    if mc == 0:
        warnings.append(
            "[P0-1] 没设 max_calls：hard_max 用满时和「自然停止」长得一模一样，"
            "无从分辨。max_calls 是唯一会诚实留痕的提前停止")
    elif 0 < mc < 20:
        warnings.append("max_calls < 20 会被代码当成 0（不设限）")

    # ---------- 4. 实际生效值 ----------
    sat = int(sp.get("structure_saturation_every_n", 3) or 3)
    rev = int(sp.get("re_eval_every_n", 1) or 1)
    si = int(mem.get("shape_items", 6))
    sc = int(mem.get("shape_chars", 900))
    k = PROFILE_SHAPE_SCALE[prof]
    eff_si = si if prof == "quality" else max(2, int(si * k))
    eff_sc = sc if prof == "quality" else max(200, int(sc * k))

    calls = total * CALLS_PER_LAYER_ROUND * PROFILE_CALL_ETA[prof]

    print(f"\n成本档        : {prof}")
    print(f"  候选截断     : {PROFILE_CAND_LIMIT[prof]}（0=不截断）")
    print(f"  shape 实际值 : items {si}→{eff_si}  chars {sc}→{eff_sc}"
          + ("（未被缩放）" if prof == "quality" else f"（×{k}）"))
    print(f"  every_n 实际 : 结构饱和度 {sat}→{sat + 1 if lazy else sat}"
          f"   池重估 {rev}→{rev + 1 if lazy else rev}"
          + ("" if lazy else "（quality 下无 +1 偏移）"))
    print(f"\n每层预算      :")
    for e in ENTRIES:
        hd, sf, r = plan[e]
        print(f"  {e:5s} hard {hd:2d}  soft {sf:2d}  实跑上限 {r:2d}"
              + ("  ← 含 all_extra_rounds" if e == "all" else ""))
    print(f"  合计 {total} 圈")

    print(f"\n预计（估算，非实测）:")
    print(f"  调用  ≈ {calls:.0f} 次")
    print(f"  token ≈ {calls * TOKENS_PER_CALL / 1e6:.2f} M")
    _pm = str(acts.get("parallel_mode", "serial"))
    print(f"  墙钟  ≈ {calls * SEC_PER_CALL / 60:.0f} min（serial 口径）")
    if _pm not in ("serial", "auto"):
        print(f"         {_pm} 模式下预期降到 50-60% 左右（省墙钟不省调用）")
    if mc:
        ratio = calls / mc if mc else 0
        flag = "  ⚠️ 估算跑不满预算上限，会被 max_calls 截断" if ratio > 1 else ""
        print(f"  max_calls = {mc}（估算占 {ratio:.0%}）{flag}")

    print(f"\n诊断:")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
    for w in warnings:
        print(f"  ⚠ {w}")
    if not errors and not warnings:
        print("  ✓ 未发现已知陷阱")
    print()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    for a in args:
        p = Path(a)
        if p.exists():
            lint(a)
        else:
            print(f"[FATAL] 文件不存在：{a}")


if __name__ == "__main__":
    main()
