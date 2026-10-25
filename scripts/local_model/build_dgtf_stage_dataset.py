# -*- coding: utf-8 -*-
"""构建 Meta-DGTF-道生三阶模型专属 stage 数据集（dual_judge / self_check）。

数据源：outputs/*.packed.json 历史产物（177 份，580 个 view，17,394 条候选标签，
576 份 self_check 自省标签）。全部离线，不做任何真实 API 调用。

设计要点
--------
1. **prompt 与引擎同构**：不手抄模板 —— 用 AST 从
   dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py 只读提取
   PHASE_*.dual_spec / view_focus / NO_FILL_JUDGE_RULE / AMP_TYPES，
   再按 `_dual_judge` / `_self_check` 的拼装顺序重建。
   与引擎的两处**有意偏差**（均已在下文注释说明）：
     · dual_judge schema 精简为 {idx,position,why_position} 三字段（任务契约），
       why_0/why_1 在引擎侧缺失时按空串处理；
     · 省略 `_self_block`（线上无 self_memory 时本来就为空）与
       `_carry_block_text`（carry 是引擎运行期输入，产物里没有原值）。
2. **标签还原**：dual_judge 的 target 由 candidates[].position / why_position
   还原；self_check 的 target 就是 views.*.self_check 原 JSON（按引擎输出的
   11 个键重新排序，保证与线上解析一致）。
3. **防泄漏**：按「问题」分组切 train/val，同一问题的所有 run/所有 view/
   所有分片只进同一侧。
4. **截断策略**：max_len 受 6GB 卡限制（训练 max_len=2048），所有块都有
   字符上限；每个样本都会统计 token 长度，超限样本数写进 dataset_stats.json。
5. **dual_judge 分片**：一个 view 的候选 p50=27 / max=60，整包喂不进 2048。
   引擎自身在「命中率低」时也会把候选减半重判（`_dual_judge` 降级重试），
   说明该任务是逐候选独立的，因此按顺序切成 ≤shard 条的小批：
   N 条候选 → ceil(N/shard) 个样本，idx 在每个样本内从 1 重新编号。

用法：
  # 小样本 demo（验证字段可还原）
  python scripts/local_model/build_dgtf_stage_dataset.py \
      --outdir llm_sft/dgtf_stage_demo --limit-files 3 --tokenizer-stats
  # 全量
  python scripts/local_model/build_dgtf_stage_dataset.py \
      --outdir llm_sft/dgtf_stage --shard 8 --val-ratio 0.18 --tokenizer-stats
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V2.2.2.py"
OUTPUTS = ROOT / "outputs"
DEFAULT_TOKENIZER = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"

# ---------------- 截断上限（字符） ----------------
# dual_judge
DJ_ANCHOR_CAP = 300          # 锚点
DJ_QUESTION_CAP = 300        # 原始问题 / 透传问题
DJ_UPSTREAM_CAP = 320        # 每个上游 view 的 shape
DJ_UPSTREAM_MAX = 2          # 最多列几个上游 view
DJ_DESC_CAP = 120            # 候选描述
DJ_DECID_CAP = 220           # 可判定性块
DJ_WHY_CAP = 60              # target why_position
# self_check（引擎原文：ing≤1500、manifest 全文、候选全列）
SC_ANCHOR_CAP = 300
SC_COLLISION_CAP = 700
SC_MANIFEST_CAP = 600
SC_CAND_MAX = 20
SC_CAND_DESC_CAP = 80
SC_AMP_MAX = 10
SC_AMP_DESC_CAP = 80
SC_FLAGS_MAX = 10
SC_VERDICT_CAP = 120

_UNSAID_MARK = "此处未生"
_ENTRIES = ("0", "1", "both", "all")
PHASE_BY_ENTRY = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}

# dual_judge schema —— 任务契约三字段（见模块 docstring 的「有意偏差」）
DJ_SCHEMA = ('{"judgments":[{"idx":1,"position":"0|1|both",'
             '"why_position":"≤30字"}]}')
# anchored=True 时的 how 块（引擎 line 12256-12259）
DJ_HOW = (
    "本层【属性】已由这条候选是从哪一面被看出来而确定，你不用判、也别猜。\n"
    "你只判【位置】这一维。\n"
)

# self_check system 模板（引擎 line 15175-15209 逐字，__VIEW_FOCUS__ 为占位）
SELF_CHECK_SYSTEM_TMPL = (
    "你是【自我回看者】。\n"
    "回看这次运行，如实回答：\n"
    "1. 有没有哪条候选，是后面补的，不是从展开里长出来的？\n"
    "2. 有没有哪条 &，是为了凑数？\n"
    "3. ing 输出里，是否有**超过一半**的句子与**上游 view** 的"
    "manifest/collision 逐字或近义重复？\n"
    "   - 逐字重复：完全相同的句子；\n"
    "   - 近义重复：换了个说法但说的是同一件事。\n"
    "   - 若超过一半 → ing_rephrased=true；\n"
    "   - 若不到一半 → false。\n"
    "   ★ 不要因为'有几句原话'就填 true；要看**比例**。\n"
    "   ★ 本层候选不是上游：ing 本来就是吃候选的，\n"
    "     ing 提到候选不算复述——只有复述**上游 view 的话**才算。\n"
    "4. 如果撞不出新东西，我有没有诚实说'未生'？\n"
    "5. 这次 DGTF 整体流程走得好不好？\n"
    "6. 本层 view 的标准是：__VIEW_FOCUS__\n"
    "7. 本圈有几处说了「此处未生」？自己数一遍，填进 unsaid_count。\n"
    "   ★ 「此处未生」是允许的诚实姿态，但如果一处圈里出现超过 3 处，\n"
    "     说明这一圈的探针没有真的往里推——它成了收尾的套路。\n"
    "     这种情况下 unsaid_is_escape 填 true，\n"
    "     并说明是哪一步该推没推。\n"
    "严格 JSON：\n"
    '{"suspicious_candidates":[1,2],'
    '"suspicious_amps":[1],'
    '"ing_rephrased":false,'
    '"honest_about_empty":true,'
    '"unsaid_count":0,'
    '"unsaid_is_escape":false,'
    '"unsaid_where":"≤60字（超过 3 处时填：哪一步该推没推）",'
    '"flow_verdict":"≤60字",'
    '"view_verdict":"≤60字",'
    '"amp_ratio_verdict":"≤40字",'
    '"notes":"≤80字"}'
)

SC_KEYS = ("suspicious_candidates", "suspicious_amps", "ing_rephrased",
           "honest_about_empty", "unsaid_count", "unsaid_is_escape",
           "unsaid_where", "flow_verdict", "view_verdict",
           "amp_ratio_verdict", "notes")
# P0 变体：只输出决策字段的最小 JSON（压低本地 decode 延迟 + 训练成本）。
# 字段与引擎 self_check 同义，只是砍掉解释性字段，不是自创格式。
SC_MIN_KEYS = ("suspicious_candidates", "ing_rephrased", "unsaid_is_escape")
_SC_MIN_SCHEMA = (
    '{"suspicious_candidates":[1,2],"ing_rephrased":false,'
    '"unsaid_is_escape":false}')
_SC_MIN_TAIL = (
    "严格 JSON：只输出下面这三个决策字段，不要输出 verdict/notes 等解释性字段，"
    "不要任何多余文字：\n" + _SC_MIN_SCHEMA
)


def self_check_system(phase: dict, variant: str = "full") -> str:
    base = SELF_CHECK_SYSTEM_TMPL.replace("__VIEW_FOCUS__",
                                          phase["view_focus"])
    if variant == "min":
        head = base.partition("严格 JSON：")[0]
        return head + _SC_MIN_TAIL
    return base


# ============================================================
# 引擎模板提取（只读，AST）
# ============================================================
def _const_str(node) -> str:
    try:
        val = ast.literal_eval(node)
    except Exception:
        return ""
    return val if isinstance(val, str) else ""


def load_engine_templates(path: Path = ENGINE) -> dict:
    """从引擎源码提取 Phase 模板 / 规则常量。只读，不 import 执行。"""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    phases: dict[str, dict] = {}
    consts: dict[str, object] = {}
    phase_names = {"PHASE_PRACTICE", "PHASE_RESEARCH", "PHASE_DUEL",
                   "PHASE_META"}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        name = tgt.id
        if name in phase_names and isinstance(node.value, ast.Call):
            kw = {}
            for k in node.value.keywords:
                if k.arg is None:
                    continue
                s = _const_str(k.value)
                if s:
                    kw[k.arg] = s
            if kw.get("name"):
                _name2entry = {"修行": "0", "研究": "1", "对撞": "both",
                               "元": "all"}
                if kw["name"] in _name2entry:
                    phases[_name2entry[kw["name"]]] = kw
        elif name in ("NO_FILL_JUDGE_RULE", "AMP_TYPES",
                      "UNSAID_ESCAPE_LIMIT"):
            try:
                consts[name] = ast.literal_eval(node.value)
            except Exception:
                pass
    missing = [e for e in _ENTRIES if e not in phases]
    if missing:
        raise SystemExit(f"引擎模板提取失败，缺 phase: {missing} —— 检查 {path}")
    if "NO_FILL_JUDGE_RULE" not in consts:
        raise SystemExit("引擎模板提取失败：NO_FILL_JUDGE_RULE 未找到")
    return {
        "phases": phases,
        "no_fill": consts["NO_FILL_JUDGE_RULE"],
        "amp_types": consts.get("AMP_TYPES") or {},
        "unsaid_limit": int(consts.get("UNSAID_ESCAPE_LIMIT") or 3),
        "source": str(path),
    }


# ============================================================
# 文本拼装（对齐引擎）
# ============================================================
def _clip(s, n: int) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "…"


def shape_of(v: dict, limit_chars: int = 0,
             amp_types: dict | None = None) -> str:
    """View.shape_of 的只读复刻（引擎 line 8608-8693，limit=0 分支）。

    末尾按 limit_chars 硬截断（引擎侧是 [:1200]）。
    """
    amp_types = amp_types or {}
    lines = [f"【view｜entry={v.get('entry')}】", f"锚点：{v.get('anchor', '')}"]
    if v.get("manifest"):
        lines.append(f"它显形为：{v['manifest']}")
    if v.get("candidates"):
        lines.append(f"候选：")
        for c in v["candidates"]:
            lines.append(f"  - {c.get('desc', '')}")
    if v.get("amps"):
        lines.append("& 印记：")
        for a in v["amps"]:
            lines.append(
                f"  - [{amp_types.get(a.get('type', ''), '?')}] "
                f"{a.get('desc', '')}")
    if v.get("threads"):
        lines.append("悬空线头：")
        for t in v["threads"]:
            lines.append(f"  - {t.get('desc', '')}")
    if v.get("probes"):
        lines.append("还没带走的自问：")
        for p in v["probes"]:
            lines.append(f"  - {p.get('question', '')}"
                         f"（回来：{p.get('link', '')}）")
    if v.get("meta"):
        lines.append("元反思：")
        for m in v["meta"]:
            lines.append(f"  - {m}")
    if v.get("untouched"):
        lines.append("尚未触及的方面：")
        for u in v["untouched"]:
            _aid = str(u.get("id", "") or "")
            _pfx = (_aid + ". ") if _aid else ""
            lines.append(f"  - {_pfx}{u.get('desc', '')}")
    if v.get("engagements"):
        lines.append("本层碰了的：")
        for e in v["engagements"]:
            lines.append(f"  - {e.get('target', '')}（{e.get('how', '')}）")
    if v.get("suspensions"):
        lines.append("主动悬置（判断过、决定不碰）：")
        for s in v["suspensions"]:
            lines.append(f"  - {s.get('target', '')}（{s.get('reason', '')}）"
                         f"[{s.get('status', '')}]")
    if v.get("deferrals"):
        lines.append("延迟债务（暂缓，非悬置）：")
        for d in v["deferrals"]:
            lines.append(f"  - {d.get('sub_question', '')}"
                         f"（回访：{d.get('revisit_condition', '')}）"
                         f"[{d.get('status', '')}]")
    if v.get("adjudications"):
        lines.append("裁决的张力（极性，回溯）：")
        for a in v["adjudications"]:
            lines.append(f"  - {a.get('tension', '')} → "
                         f"{a.get('polarity', '')}")
    if v.get("duel_suspensions"):
        lines.append("悬置的张力（不解决什么分歧）：")
        for s in v["duel_suspensions"]:
            lines.append(f"  - {s.get('target', '')}"
                         f"（{s.get('quadrant', '')}）"
                         f"[{s.get('status', '')}]")
    if (v.get("decidable_product") or {}).get("answer"):
        lines.append("【可判定通道产物】")
        lines.append("  - answer: "
                     + str(v["decidable_product"]["answer"])[:200])
    if (v.get("undecidable_product") or {}).get("structural_amps"):
        lines.append("【不可判定通道产物】")
        lines.append("  - 结构清晰度: "
                     f"{(v['undecidable_product'] or {}).get('clarity', 0)}")
        for sa in (v["undecidable_product"].get("structural_amps") or [])[:3]:
            lines.append(f"  - {sa}")
    out = "\n".join(lines)
    return _clip(out, limit_chars) if limit_chars else out


def _decidability_block(dec: dict | None) -> str:
    """引擎 _decidability_block 复刻（line 10804-10832）。"""
    dr = dec or {}
    status = str(dr.get("decidability", "")).strip()
    reason = str(dr.get("reason", "")).strip()
    if not status and not reason:
        return ""
    lines = ["", "【全局可判定性评估（前置）】", f"  状态：{status or '（未标）'}"]
    if reason:
        lines.append(f"  理由：{reason[:120]}")
    dec_aspects = (dr.get("decidable_aspects") or [])[:3]
    if dec_aspects:
        lines.append("  可判定方向：")
        for a in dec_aspects:
            lines.append(f"    - {str(a)[:80]}")
    und_aspects = (dr.get("undecidable_aspects") or [])[:3]
    if und_aspects:
        lines.append("  不可判定方向：")
        for a in und_aspects:
            lines.append(f"    - {str(a)[:80]}")
    lines.append(
        "  这是本层展开/判断的前置信息，供你参考：\n"
        "  不可判定方向上的候选，允许更多悬置、更多 both、更多未生；\n"
        "  可判定方向上的候选，尽量给出明确的 0/1 判断。")
    return _clip("\n".join(lines), DJ_DECID_CAP)


def judge_context(packed: dict, entry: str, anchor: str,
                  amp_types: dict) -> str:
    """引擎 _judge_context 复刻（line 12193-12205）。"""
    question = str(packed.get("question") or "")
    if entry in ("0", "1"):
        return f"{_clip(anchor, DJ_ANCHOR_CAP)}\n\n【原始问题】\n" \
               f"{_clip(question, DJ_QUESTION_CAP)}"
    parts = [f"【问题（透传）】\n{_clip(anchor, DJ_ANCHOR_CAP)}"]
    views = packed.get("views") or {}
    ups = [e for e in _ENTRIES[:_ENTRIES.index(entry)] if e in views]
    for e in ups[-DJ_UPSTREAM_MAX:]:
        parts.append(
            f"【view-{e} 形状】\n"
            f"{shape_of(views[e], DJ_UPSTREAM_CAP, amp_types)}")
    return "\n\n".join(parts)


def dual_judge_system(phase: dict, no_fill: str) -> str:
    """引擎 _dual_judge system 复刻（line 12270-12280，anchored=True）。"""
    return (
        "你是【对偶判断者】。\n"
        + phase["dual_spec"] + DJ_HOW
        + "both 只在真的看不出偏向时才用；\n"
        "不要为了省事把两端都填 both，那是逃避判断。\n"
        + no_fill
        + "严格 JSON：\n" + DJ_SCHEMA
    )


def _norm_desc(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


# ============================================================
# dual_judge 样本
# ============================================================
def build_dual_judge(packed: dict, src: str, tpl: dict,
                     shard: int) -> tuple[list[dict], dict]:
    """一个 packed 产物 → 若干 dual_judge 样本。"""
    stats = Counter()
    question = str(packed.get("question") or "").strip()
    views = packed.get("views") or {}
    dec = packed.get("decidability") or {}
    amp_types = tpl["amp_types"]
    out: list[dict] = []
    for entry in _ENTRIES:
        v = views.get(entry)
        if not isinstance(v, dict):
            continue
        anchor = str(v.get("anchor") or "").strip()
        if not anchor:
            stats["skip_no_anchor"] += 1
            continue
        phase = tpl["phases"][entry]
        system = dual_judge_system(phase, tpl["no_fill"])
        ctx = judge_context(packed, entry, anchor, amp_types)
        dec_block = _decidability_block(dec)
        # ---- 候选清洗：未判（why_position 空）视为默认 0 噪声，丢弃 ----
        seen = set()
        cands = []
        for c in v.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            desc = _norm_desc(c.get("desc"))
            pos = str(c.get("position", "")).lower()
            why = _norm_desc(c.get("why_position"))
            if not desc or len(desc) < 5:
                stats["drop_short_desc"] += 1
                continue
            if not why:
                stats["drop_unjudged"] += 1
                continue
            if pos not in ("0", "1", "both"):
                stats["drop_bad_pos"] += 1
                continue
            key = desc
            if key in seen:
                stats["drop_dup_in_view"] += 1
                continue
            seen.add(key)
            cands.append({"desc": _clip(desc, DJ_DESC_CAP),
                          "kind": str(c.get("kind") or "concept"),
                          "position": pos,
                          "why_position": _clip(why, DJ_WHY_CAP)})
        if not cands:
            stats["skip_no_cands"] += 1
            continue
        stats["views"] += 1
        stats["judged_candidates"] += len(cands)
        for si in range(0, len(cands), shard):
            chunk = cands[si:si + shard]
            cand_text = "\n".join(
                f"{i + 1}. [{c['kind']}] {c['desc']}"
                for i, c in enumerate(chunk))
            user = (f"【处境】\n{ctx}"
                    f"\n{dec_block}\n"
                    f"\n【候选列表】\n{cand_text}")
            target = json.dumps(
                {"judgments": [{"idx": i + 1, "position": c["position"],
                                "why_position": c["why_position"]}
                               for i, c in enumerate(chunk)]},
                ensure_ascii=False, separators=(",", ":"))
            out.append({
                "id": f"dj::{_qid(question)}::{Path(src).stem}::{entry}"
                      f"::{si // shard}",
                "stage": "dual_judge",
                "question": question,
                "packed": src,
                "entry": entry,
                "phase": phase["name"],
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user},
                             {"role": "assistant", "content": target}],
                "meta": {"n_candidates": len(chunk),
                         "shard_index": si // shard,
                         "view_candidates": len(cands)},
            })
            stats["shards"] += 1
    return out, dict(stats)


# ============================================================
# self_check 样本
# ============================================================
def _count_unsaid(view: dict) -> tuple[int, str]:
    """_count_unsaid 复刻（引擎 line 1824-1854）。"""
    buckets = [
        ("ing", str(view.get("collision") or "")),
        ("view", str(view.get("manifest") or "")),
        ("线头", "\n".join(str(t.get("desc", ""))
                           for t in (view.get("threads") or [])
                           if isinstance(t, dict))),
        ("&", "\n".join(str(a.get("desc", ""))
                        for a in (view.get("amps") or [])
                        if isinstance(a, dict))),
        ("不可判定通道", str(
            (view.get("undecidable_product") or {}).get(
                "why_undecidable", "") or "")),
    ]
    total, where = 0, []
    for name, text in buckets:
        if not text:
            continue
        n = text.count(_UNSAID_MARK)
        if n:
            total += n
            where.append(f"{name}×{n}")
    return total, "、".join(where)


def build_self_check(packed: dict, src: str, tpl: dict,
                     unsaid_limit: int,
                     variant: str = "full") -> tuple[list[dict], dict]:
    """variant='full' → 引擎原 11 键 JSON；'min' → 3 个决策字段的最小 JSON。"""
    stats = Counter()
    question = str(packed.get("question") or "").strip()
    views = packed.get("views") or {}
    out: list[dict] = []
    keys = SC_MIN_KEYS if variant == "min" else SC_KEYS
    for entry in _ENTRIES:
        v = views.get(entry)
        if not isinstance(v, dict):
            continue
        sc = v.get("self_check")
        cands = [c for c in (v.get("candidates") or [])
                 if isinstance(c, dict)]
        amps = [a for a in (v.get("amps") or []) if isinstance(a, dict)]
        if not isinstance(sc, dict) or not sc:
            stats["skip_no_self_check"] += 1
            continue
        if not cands and not amps:
            # 引擎在无候选无 & 时早退，不发 LLM 调用 —— 没有监督信号
            stats["skip_blank_view"] += 1
            continue
        anchor = str(v.get("anchor") or "").strip()
        if not anchor:
            stats["skip_no_anchor"] += 1
            continue
        phase = tpl["phases"][entry]
        system = self_check_system(phase, variant)
        # ★ 引擎的 assistant 历史（本圈 view）已经包含在 user 的【view】块里，
        #   这里折叠成单轮（推理侧同样单轮），不重复塞 manifest。
        cand_lines = "\n".join(
            f"{i + 1}. [{c.get('attribute', '0')}×{c.get('position', '0')}] "
            f"{_clip(_norm_desc(c.get('desc')), SC_CAND_DESC_CAP)}"
            for i, c in enumerate(cands[:SC_CAND_MAX]))
        amp_lines = "\n".join(
            f"{i + 1}. [{a.get('type', '?')}] "
            f"{_clip(_norm_desc(a.get('desc')), SC_AMP_DESC_CAP)}"
            for i, a in enumerate(amps[:SC_AMP_MAX]))
        flags = [str(f) for f in (v.get("quality_flags") or [])][:SC_FLAGS_MAX]
        user = (
            f"【锚点】\n{_clip(anchor, SC_ANCHOR_CAP)}\n\n"
            f"【候选】\n{cand_lines or '（无）'}\n\n"
            f"【& 印记】\n{amp_lines or '（无）'}\n\n"
            f"【ing 输出】\n{_clip(v.get('collision') or '', SC_COLLISION_CAP)}\n\n"
            f"【view】\n{_clip(v.get('manifest') or '（未生）', SC_MANIFEST_CAP)}\n\n"
            f"【代码已发现的质量线索】\n{', '.join(flags) or '（无）'}\n"
        )
        if any("too_many_amp_candidates" in f for f in flags):
            user += (
                "\n\n【★ 深究请求】本轮 amp 候选占比偏高。请专门判断：\n"
                "  这是结构性一致（& 候选从不同角度指向同一结构），\n"
                "  还是判断塌缩（属性与位置机械全反）？\n"
                "  把结论写进 amp_ratio_verdict（≤40字）。\n")
        counted, where = _count_unsaid(v)
        if counted:
            user += (f"\n\n【★ 代码统计】本圈产物里出现「{_UNSAID_MARK}」"
                     f"{counted} 处，分布在：{where or '（未定位）'}。\n"
                     f"  你自己数的 unsaid_count 应与此接近；差太多请说明。\n")
            if unsaid_limit > 0:
                user += (f"  超过 {unsaid_limit} 处 → 这一圈的探针没真的往里推，"
                         f"unsaid_is_escape 填 true。\n")
        target = json.dumps(
            OrderedDict((k, sc.get(k)) for k in keys),
            ensure_ascii=False, separators=(",", ":"))
        out.append({
            "id": f"{'scmin' if variant == 'min' else 'sc'}::"
                  f"{_qid(question)}::{Path(src).stem}::{entry}",
            "stage": "self_check",
            "variant": variant,
            "question": question,
            "packed": src,
            "entry": entry,
            "phase": phase["name"],
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": target}],
            "meta": {"n_candidates": min(len(cands), SC_CAND_MAX),
                     "n_amps": min(len(amps), SC_AMP_MAX),
                     "candidates_total": len(cands),
                     "amps_total": len(amps),
                     "unsaid_counted": counted},
        })
        stats["views"] += 1
    return out, dict(stats)


# ============================================================
# 划分 / 统计
# ============================================================
def _qid(question: str) -> str:
    return hashlib.md5(question.encode("utf-8")).hexdigest()[:8]


def _dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    seen, out = set(), []
    for r in rows:
        h = hashlib.md5(json.dumps(
            [r["stage"], r["messages"]], ensure_ascii=False,
            sort_keys=True).encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(r)
    return out, len(rows) - len(out)


def split_by_question(rows: list[dict], val_ratio: float,
                      seed: int) -> tuple[list[dict], list[dict], dict]:
    """按问题分组切分：同一问题的全部样本只进同一侧。

    53 个唯一问题、run 数极不均衡（1~33），单纯贪心会让 val 只剩 1 个大问题。
    这里按问题样本量分位分桶，每桶各抽 ~val_ratio 的问题，兼顾
    「问题多样性（topic 覆盖）」与「样本比例可控」。
    """
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    qs = list(by_q)
    total = len(rows)
    target = max(1, int(round(total * val_ratio)))
    rng = random.Random(seed)
    order = list(qs)
    rng.shuffle(order)
    order.sort(key=lambda q: len(by_q[q]))
    nb = 4
    buckets: list[list[str]] = [[] for _ in range(nb)]
    for rank, q in enumerate(order):
        buckets[min(nb - 1, rank * nb // max(1, len(order)))].append(q)
    val_q: list[str] = []
    for b in buckets:
        k = max(1, int(round(len(b) * val_ratio))) if b else 0
        val_q.extend(b[:k])
    keep_train_guard = 2
    vset = set(val_q)

    def _n_val() -> int:
        return sum(len(by_q[q]) for q in vset)

    # 比例过高：把最大的 val 问题踢回 train
    while _n_val() > target * 1.35 and len(vset) > 1:
        q_big = max(vset, key=lambda q: len(by_q[q]))
        vset.discard(q_big)
    # 比例过低：从剩余问题里继续抽（小问题优先，避免一次顶满）
    rest = [q for q in order if q not in vset]
    for q in rest:
        if _n_val() >= target * 0.85:
            break
        if len(rest) - len(vset) <= keep_train_guard:
            break
        if _n_val() + len(by_q[q]) > target * 1.35 and _n_val() > target * 0.5:
            continue
        vset.add(q)
    val_q = [q for q in qs if q in vset]
    train = [r for r in rows if r["question"] not in vset]
    val = [r for r in rows if r["question"] in vset]
    info = {
        "questions_total": len(qs),
        "val_questions": [{"question": q, "n": len(by_q[q])} for q in val_q],
        "train_questions": len(qs) - len(val_q),
        "val_share": round(len(val) / max(1, total), 3),
    }
    return train, val, info


def _len_stats(xs: list[int]) -> dict:
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return {"n": 0}
    def p(q):
        return xs[min(n - 1, int(n * q))]
    return {"n": n, "min": xs[0], "p50": p(0.50), "p90": p(0.90),
            "p95": p(0.95), "p99": p(0.99), "max": xs[-1],
            "mean": round(sum(xs) / n, 1)}


def token_stats(rows: list[dict], tokenizer_path: Path,
                max_len: int) -> tuple[dict, dict]:
    """用真实 tokenizer 统计 prompt/target token 长度（训练口径）。"""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(
        str(tokenizer_path), trust_remote_code=True, local_files_only=True)
    plens, tlens, tot = [], [], []
    over = 0
    for r in rows:
        try:
            prompt = tok.apply_chat_template(
                r["messages"][:-1], tokenize=False,
                add_generation_prompt=True)
            p = len(tok(prompt, add_special_tokens=False)["input_ids"])
            t = len(tok(r["messages"][-1]["content"],
                        add_special_tokens=False)["input_ids"])
        except Exception:
            continue
        plens.append(p)
        tlens.append(t)
        tot.append(p + t)
        if p + t > max_len:
            over += 1
    return ({
        "prompt_tokens": _len_stats(plens),
        "target_tokens": _len_stats(tlens),
        "total_tokens": _len_stats(tot),
        "over_max_len": over,
        "over_max_len_ratio": round(over / max(1, len(tot)), 4),
        "max_len": max_len,
    }, {"prompt": plens, "target": tlens, "total": tot})


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _interleave_by_question(rows: list[dict], cap: int, seed: int) -> list[dict]:
    """按问题轮转截取前 cap 条，保证问题多样性（训练预算控制用）。"""
    if cap <= 0 or len(rows) <= cap:
        return rows
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    rng = random.Random(seed)
    qs = list(by_q)
    rng.shuffle(qs)
    for q in qs:
        rng.shuffle(by_q[q])
    out, i = [], 0
    while len(out) < cap:
        added = False
        for q in qs:
            if i < len(by_q[q]):
                out.append(by_q[q][i])
                added = True
                if len(out) >= cap:
                    break
        if not added:
            break
        i += 1
    return out


def main() -> int:
    global SC_CAND_MAX, SC_COLLISION_CAP, SC_MANIFEST_CAP, SC_AMP_MAX
    global DJ_DESC_CAP, DJ_UPSTREAM_CAP, DJ_UPSTREAM_MAX, DJ_ANCHOR_CAP
    global DJ_QUESTION_CAP, DJ_WHY_CAP
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="llm_sft/dgtf_stage")
    ap.add_argument("--shard", type=int, default=8, help="dual_judge 每样本候选数")
    ap.add_argument("--val-ratio", type=float, default=0.18)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-files", type=int, default=0,
                    help=">0 时只取前 N 份 packed（demo 验证）")
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--tokenizer-stats", action="store_true",
                    help="用真实 tokenizer 统计长度（慢一些但准）")
    ap.add_argument("--tokenizer", default=str(DEFAULT_TOKENIZER))
    ap.add_argument("--self-check-variant", default="both",
                    choices=("full", "min", "both"))
    ap.add_argument("--train-sample-cap", type=int, default=0,
                    help=">0 时训练集按问题轮转截断到 N 条（训练预算控）")
    ap.add_argument("--aligned-dj-cap", type=int, default=0,
                    help=">0 时 dual_judge 训练集截断到 N 条")
    # ---- 截断上限旋钮（调 token 预算用）----
    ap.add_argument("--sc-cand-max", type=int, default=SC_CAND_MAX)
    ap.add_argument("--sc-collision-cap", type=int, default=SC_COLLISION_CAP)
    ap.add_argument("--sc-manifest-cap", type=int, default=SC_MANIFEST_CAP)
    ap.add_argument("--sc-amp-max", type=int, default=SC_AMP_MAX)
    ap.add_argument("--dj-desc-cap", type=int, default=DJ_DESC_CAP)
    ap.add_argument("--dj-upstream-cap", type=int, default=DJ_UPSTREAM_CAP)
    ap.add_argument("--dj-anchor-cap", type=int, default=DJ_ANCHOR_CAP)
    ap.add_argument("--dj-question-cap", type=int, default=DJ_QUESTION_CAP)
    ap.add_argument("--dj-why-cap", type=int, default=DJ_WHY_CAP)
    args = ap.parse_args()

    SC_CAND_MAX = args.sc_cand_max
    SC_COLLISION_CAP = args.sc_collision_cap
    SC_MANIFEST_CAP = args.sc_manifest_cap
    SC_AMP_MAX = args.sc_amp_max
    DJ_DESC_CAP = args.dj_desc_cap
    DJ_UPSTREAM_CAP = args.dj_upstream_cap
    DJ_ANCHOR_CAP = args.dj_anchor_cap
    DJ_QUESTION_CAP = args.dj_question_cap
    DJ_WHY_CAP = args.dj_why_cap

    outdir = (ROOT / args.outdir) if not Path(args.outdir).is_absolute() \
        else Path(args.outdir)
    tpl = load_engine_templates()
    files = sorted(OUTPUTS.glob("*.packed.json"))
    if args.limit_files:
        files = files[:args.limit_files]
    print(f"[build] engine={tpl['source']}", flush=True)
    print(f"[build] packed files={len(files)} shard={args.shard} "
          f"outdir={outdir}", flush=True)

    dj_rows, sc_rows, scmin_rows = [], [], []
    dj_stats = Counter()
    sc_stats = Counter()
    n_bad = 0
    for i, fpath in enumerate(files):
        try:
            packed = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            n_bad += 1
            print(f"[warn] {fpath.name}: {e}", flush=True)
            continue
        src = str(fpath.relative_to(ROOT))
        rows, st = build_dual_judge(packed, src, tpl, args.shard)
        dj_rows.extend(rows)
        dj_stats.update(st)
        if args.self_check_variant in ("full", "both"):
            rows, st = build_self_check(packed, src, tpl,
                                        int(tpl["unsaid_limit"]), "full")
            sc_rows.extend(rows)
            sc_stats.update(st)
        if args.self_check_variant in ("min", "both"):
            rows, st = build_self_check(packed, src, tpl,
                                        int(tpl["unsaid_limit"]), "min")
            scmin_rows.extend(rows)
            sc_stats.update(st)
        if (i + 1) % 40 == 0:
            print(f"[build] {i + 1}/{len(files)} dj={len(dj_rows)} "
                  f"sc={len(sc_rows)} scmin={len(scmin_rows)}", flush=True)

    # 去重（全量精确去重，跨 run）
    dj_rows, dj_dup = _dedupe(dj_rows)
    sc_rows, sc_dup = _dedupe(sc_rows)
    scmin_rows, scmin_dup = _dedupe(scmin_rows)
    # 按问题分组划分（所有 stage 用同一套 holdout 问题，避免任何问题泄漏）
    all_rows = dj_rows + sc_rows + scmin_rows
    _, _, split_info = split_by_question(all_rows, args.val_ratio, args.seed)
    val_qs = {x["question"] for x in split_info["val_questions"]}

    def _split(rows):
        return ([r for r in rows if r["question"] not in val_qs],
                [r for r in rows if r["question"] in val_qs])

    dj_train, dj_val = _split(dj_rows)
    sc_train, sc_val = _split(sc_rows)
    scmin_train, scmin_val = _split(scmin_rows)
    # 训练预算截断（只动 train，val 保持全量）
    if args.train_sample_cap and len(sc_train) > args.train_sample_cap:
        sc_train = _interleave_by_question(sc_train, args.train_sample_cap,
                                           args.seed)
    if args.train_sample_cap and len(scmin_train) > args.train_sample_cap:
        scmin_train = _interleave_by_question(scmin_train,
                                              args.train_sample_cap, args.seed)
    if args.aligned_dj_cap and len(dj_train) > args.aligned_dj_cap:
        dj_train = _interleave_by_question(dj_train, args.aligned_dj_cap,
                                           args.seed)

    write_jsonl(outdir / "dual_judge_train.jsonl", dj_train)
    write_jsonl(outdir / "dual_judge_val.jsonl", dj_val)
    if sc_rows:
        write_jsonl(outdir / "self_check_train.jsonl", sc_train)
        write_jsonl(outdir / "self_check_val.jsonl", sc_val)
    if scmin_rows:
        write_jsonl(outdir / "self_check_min_train.jsonl", scmin_train)
        write_jsonl(outdir / "self_check_min_val.jsonl", scmin_val)

    # ---------- 统计 ----------
    def _dist(rows, key):
        return dict(Counter(str(r.get(key)) for r in rows).most_common())

    def _block(rows, train, val, dup, build_stats):
        return {
            "samples_total": len(rows),
            "train": len(train), "val": len(val),
            "dedupe_removed": dup,
            "build_stats": build_stats,
            "by_phase": _dist(rows, "phase"),
            "by_entry": _dist(rows, "entry"),
            "avg_candidates": round(
                sum(r["meta"]["n_candidates"] for r in rows)
                / max(1, len(rows)), 2),
        }

    stats = {
        "built_at": __import__("datetime").datetime.now().isoformat(
            timespec="seconds"),
        "engine_templates": tpl["source"],
        "inputs": {"packed_files": len(files), "bad_files": n_bad,
                   "outputs_dir": "outputs/*.packed.json",
                   "lead_judge_labels": "outputs/_lead_audit/judge_labels.jsonl"
                                        "（未用：packed 已含 desc/kind/source/"
                                        "position/why_position + 完整上下文）"},
        "caps": {
            "dual_judge": {"shard": args.shard, "anchor": DJ_ANCHOR_CAP,
                           "question": DJ_QUESTION_CAP,
                           "upstream_per_view": DJ_UPSTREAM_CAP,
                           "upstream_max": DJ_UPSTREAM_MAX,
                           "desc": DJ_DESC_CAP, "why_position": DJ_WHY_CAP},
            "self_check": {"collision": SC_COLLISION_CAP,
                           "manifest": SC_MANIFEST_CAP,
                           "cand_max": SC_CAND_MAX,
                           "amp_max": SC_AMP_MAX},
            "max_len": args.max_len,
            "train_sample_cap": args.train_sample_cap,
            "aligned_dj_cap": args.aligned_dj_cap,
        },
        "dual_judge": _block(dj_rows, dj_train, dj_val, dj_dup, dj_stats),
        "leakage_guard": {
            "by": "question（问题字符串全等分组）",
            "val_questions_used_for_all_stages": True,
            "note": "同一问题的所有 run / view / 分片只会出现在同一侧",
        },
        "target_schema": {
            "dual_judge": '{"judgments":[{"idx","position","why_position"}]}',
            "self_check": list(SC_KEYS),
            "self_check_min": list(SC_MIN_KEYS),
        },
    }
    if sc_rows:
        stats["self_check"] = _block(sc_rows, sc_train, sc_val, sc_dup,
                                     sc_stats)
        stats["self_check"]["variant"] = "full"
        stats["self_check"]["avg_amps"] = round(
            sum(r["meta"]["n_amps"] for r in sc_rows)
            / max(1, len(sc_rows)), 2)
    if scmin_rows:
        stats["self_check_min"] = _block(scmin_rows, scmin_train, scmin_val,
                                         scmin_dup, sc_stats)
        stats["self_check_min"]["variant"] = "min(decision-only)"
        stats["self_check_min"]["note"] = (
            "与 full 共用同一 prompt 模板，仅严格 JSON schema 换成 3 个决策字段；"
            "用于压低本地 decode 延迟")
    stats["split"] = split_info
    stats["note_dual_judge"] = (
        "is_amp_candidate 是 position 的派生量（标签泄漏），未作为输入特征；"
        "why_position 为空的候选是未判/默认 0，作为噪声丢弃")
    if args.tokenizer_stats:
        def _tok(rows):
            return token_stats(rows, Path(args.tokenizer), args.max_len)[0]
        if dj_train:
            stats["dual_judge"]["tokens"] = _tok(dj_train)
        if sc_train:
            stats["self_check"]["tokens"] = _tok(sc_train)
        if scmin_train:
            stats["self_check_min"]["tokens"] = _tok(scmin_train)
        print("[build] token stats done", flush=True)
    (outdir / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "outdir": str(outdir.relative_to(ROOT)),
        "dual_judge": {"total": len(dj_rows), "train": len(dj_train),
                       "val": len(dj_val), "dedupe": dj_dup},
        "questions": {"total": split_info["questions_total"],
                      "val": len(split_info["val_questions"])},
        "tokens": {},
    }
    if sc_rows:
        summary["self_check"] = {"total": len(sc_rows),
                                 "train": len(sc_train),
                                 "val": len(sc_val), "dedupe": sc_dup}
    if scmin_rows:
        summary["self_check_min"] = {"total": len(scmin_rows),
                                     "train": len(scmin_train),
                                     "val": len(scmin_val),
                                     "dedupe": scmin_dup}
    for k in ("dual_judge", "self_check", "self_check_min"):
        if k in stats and "tokens" in stats[k]:
            summary["tokens"][k] = stats[k]["tokens"]["total_tokens"]
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)

    # ---------- demo 模式：字段还原自检 ----------
    if args.limit_files:
        ok = True
        probe = (dj_rows[:2]
                 + (sc_rows[:1] if sc_rows else [])
                 + (scmin_rows[:1] if scmin_rows else []))
        for r in probe:
            msgs = r["messages"]
            tgt = json.loads(msgs[-1]["content"])
            print("=" * 70, flush=True)
            print("ID", r["id"], "| stage", r["stage"],
                  "| variant", r.get("variant", "-"), "| phase", r["phase"],
                  "| entry", r["entry"], flush=True)
            print("SYSTEM(head 200):",
                  msgs[0]["content"][:200].replace("\n", " ⏎ "), flush=True)
            print("USER(head 350):",
                  msgs[1]["content"][:350].replace("\n", " ⏎ "), flush=True)
            print("TARGET:", json.dumps(tgt, ensure_ascii=False)[:400],
                  flush=True)
            if r["stage"] == "dual_judge":
                js = tgt.get("judgments") or []
                if len(js) != r["meta"]["n_candidates"] or not all(
                        j.get("position") in ("0", "1", "both") for j in js):
                    ok = False
                if not all(str(j.get("why_position") or "") for j in js):
                    ok = False
            else:
                want = SC_MIN_KEYS if r.get("variant") == "min" else SC_KEYS
                if list(tgt) != list(want):
                    ok = False
        print("DEMO_FIELD_RECON_OK", ok, flush=True)
        return 0 if ok else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
