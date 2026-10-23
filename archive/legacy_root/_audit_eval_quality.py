#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[_audit_eval_quality.py] 只读探针：审计「评估阶段」的质量。

目的只有一个 —— 回答：

    这份产物里的**评估结论**（判定值 + 两份清单 + evidence），能不能当真用？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【纪律】（每一条都别破）

  1. 只读。不改主文件、不写 outputs/、不改任何池。
     静态模式把 API key 强制换成假值 —— 不是"顺手"，是**物理上防止**
     探针在离线审计时误联网。
  2. 可复跑。同输入 → 同输出。LLM 采样的随机性只出现在 C 组，
     并且**显式标注**是"这次采样"，不混进结构判据。
  3. 不预设答案。绝不写"这道题应该判成什么"。能自动查的只有两件事：
     结构自洽、有追溯。判定值本身**不是**判据。
  4. 量化优先。每项给数字，不给"看着还行"。
  5. 分档明确。✅ / ⚠️ / ❌ 三档，每档判据线写清楚。
  6. 失败留痕。读不到字段、LLM 挂，都进第 8 节，不静默。

【判据为什么只信这两条】

  上一轮（v1.21.59~v1.21.61）连栽两次：先预设"地铁该 decidable"，
  改完又预设"地铁该 partial"，两次都拿预设当判据，两次都判错。
  能**自动查**的只有：
    · 池判与外判**分不分叉**（`_divergent`）
    · 每条不可判定有没有**池内追溯**（`_untraced_undecidable`）
  本探针只把这两条（加上它们的静态同伴：归一化自洽、evidence 覆盖）
  当成"可用性"的判据。清单质量（D 组）只出数字和分档，
  不出"该不该改 prompt"的建议 —— 那要人看完逐条明细自己判。

【用法】

  # 1) 快速体检（秒级、离线，从已有产物 md 读）
  python _audit_eval_quality.py 元DGTF-V1.21.72.py \
      --from-md "outputs/20261004_053744_现金流紧张的中小制造企业上自动化产线还.md"

  # 2) 稳定度检查（真调用 N 次评估；view 从产物重建，不重跑流程）
  python _audit_eval_quality.py 元DGTF-V1.21.72.py \
      --from-md <同上> --repeat 5

  # 3) 从 packed sidecar 读（verif_*.full.json 之类）
  python _audit_eval_quality.py 元DGTF-V1.21.72.py --from-pool verif_x.full.json

  # 4) 探针自检（三条负对照，证明它抓得住问题）
  python _audit_eval_quality.py 元DGTF-V1.21.72.py --self-test

【输出】

  audits/eval_quality_<ts>.md     人读报告（8 节固定结构）
  audits/eval_quality_<ts>.json   机读侧车（跨次 diff 的锚）

【刻意不做】见 README 的「刻意不做」节 —— 一句话：
  探测和修复必须分家。探针的第一版只出数字，不出结论。
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPENDIX_TITLE = "## 附录 · 全量字段（packed 原文）"

# 分档符号
OK, WARN, BAD, NA = "✅", "⚠️", "❌", "—"

# ============================================================
# 判据线（集中一处，README 引用同一组数）
# ============================================================
TH = {
    "B1_untraced_ratio": (0.0, 0.3),      # ≤0 ✅ / ≤0.3 ⚠️ / >0.3 ❌
    "B3_evidence_cover": (0.5, 0.2),      # ≥0.5 ✅ / ≥0.2 ⚠️ / <0.2 ❌
    "B4_source_resolve": (0.8, 0.5),      # ≥0.8 ✅ / ≥0.5 ⚠️ / <0.5 ❌
    "C1_agree": (0.8, 0.5),               # ≥0.8 ✅ / ≥0.5 ⚠️ / <0.5 ❌
    "C2_span": (2, 4),                    # ≤2 ✅ / ≤4 ⚠️ / >4 ❌（条数极差）
    "C3_semantic": (0.6, 0.3),            # ≥0.6 ✅ / ≥0.3 ⚠️ / <0.3 ❌
    "D1_specific": (0.6, 0.3),            # ≥0.6 ✅ / ≥0.3 ⚠️ / <0.3 ❌
    "D3_near_dup": (0.2, 0.4),            # ≤0.2 ✅ / ≤0.4 ⚠️ / >0.4 ❌
    "D4_fill": (0.4, 0.7),                # ≤0.4 ✅ / ≤0.7 ⚠️ / >0.7 ❌
    "D5_len_ratio": (3.0, 6.0),           # ≤3 ✅ / ≤6 ⚠️ / >6 ❌
    "E2_two_way_jac": (0.4, 0.2),         # ≥0.4 ✅ / ≥0.2 ⚠️ / <0.2 ❌
    "F2_agree_median": (0.6, 0.4),        # ≥0.6 ✅ / ≥0.4 ⚠️ / <0.4 ❌
    "F3_untraced_median": (0.2, 0.4),     # ≤0.2 ✅ / ≤0.4 ⚠️ / >0.4 ❌
}

MIN_SAMPLE = 5      # C 组 / F 组样本红线：低于它不出分档

# 评估调用里出现的"口号式"词（`_BOILERPLATE` 之外的补充）
_SLOGAN_EXTRA = ("本质上", "根本上", "核心诉求", "存在冲突", "归根结底",
                 "不可通约", "辩证", "范式", "维度")

# D1「具体度」：命中即算"可指认"。分三类（任务书列的四类 + 技术名词）。
#   ★ 实测注记：宽口径下 D1 在真实产物上会**接近饱和**（见 README
#     「已知观测」）。它的实际用途是抓**退化产物**（口号式清单），
#     不是区分两份正常产物之间的优劣 —— 别拿它排名。
#   ★ 词边界：中文紧邻英文缩写时不构成 \b（"CAP取舍" 里 CAP 后是中文，
#     `\bCAP\b` 匹配不上）。所以这里**不用 \b**。
_REF_RE = re.compile(          # 引用号类
    r"(?:候选|amp|印记|悬置|线头|探针|债务)\s*\d+"
    r"|[PATSCd]_\d+|[PATC]\d+|(?:^|[^A-Za-z])ing|"
    r"第\s*[0-9一二三四五六七八九十]+\s*[圈条章节项轮]")
_ACTION_RE = re.compile(       # 动作动词类（任务书列的四类之一）
    r"可查|查得|查阅|可谈|访谈|调研|测算|核算|核实|盘点|试跑|试点|试产|"
    r"抽样|实测|稽核|对账|复核|校准|谈判|比价|询价|验证|体检|问卷|测量|比较")
_OBJ_RE = re.compile(          # 具体对象类（数值 / 命名对象 / 技术术语）
    r"\d+(?:\.\d+)?\s*(?:%|％|元|万|亿|天|月|年|次|条|圈|倍|pt|人|台|吨)"
    r"|\d{2,}"
    r"|[A-Z]{2,6}"
    r"|清单|闸门|阈值|公式|指标|表格|字段|接口|协议|标准|条款|期限|账期|报表"
    r"|参数|口径|分母|分子|编号|流程|合同|报价|发票|税|费率|余额"
    r"|时机|扣减|锁|分桶|分片|分库|拓扑|降级|排队|回补|释放|机制|路径"
    r"|方案|模式|规则|矩阵|缓存|队列|事务|索引|副本|节点|集群|工位"
    r"|残值|月供|回收期|成本|产能|付款|回款|到账|维保|备件|换型")


def _is_specific(t: str) -> bool:
    s = str(t)
    return bool(_REF_RE.search(s) or _ACTION_RE.search(s)
                or _OBJ_RE.search(s))


def band_le(v, ok: float, warn: float) -> str:
    """越小越好的分档。"""
    if v is None:
        return NA
    if v <= ok:
        return OK
    if v <= warn:
        return WARN
    return BAD


def band_ge(v, ok: float, warn: float) -> str:
    """越大越好的分档。"""
    if v is None:
        return NA
    if v >= ok:
        return OK
    if v >= warn:
        return WARN
    return BAD


def _item(value, verdict, basis="", value_disp=None):
    return {"value": value, "display": value_disp if value_disp
            is not None else value, "verdict": verdict, "basis": basis}


# ============================================================
# 0. 引擎加载（只读）
# ============================================================
_ENGINE_CACHE: dict = {}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_engine(target_py: Path, offline: bool) -> object:
    """加载目标引擎。offline=True 时把 key 强制置成假值（防误联网）。"""
    key = f"{target_py}|{offline}"
    if key in _ENGINE_CACHE:
        return _ENGINE_CACHE[key]
    if offline:
        os.environ["DGTF_API_KEY"] = "sk-audit-readonly-static"
    else:
        _load_dotenv(HERE / ".env")
        os.environ.setdefault("DGTF_API_KEY", "sk-audit-readonly-static")
    spec = importlib.util.spec_from_file_location("dgtf_audit_target",
                                                 str(target_py))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_audit_target"] = mod
    spec.loader.exec_module(mod)
    _ENGINE_CACHE[key] = mod
    return mod


# ============================================================
# 1. 输入源
# ============================================================
_APP_RE = re.compile(
    re.escape(APPENDIX_TITLE) + r"\s*(.*?)```json\s*(.*?)\s*```", re.S)


def packed_from_md(md_path: Path):
    """从产物 md 抽「附录 · 全量字段」的 packed。返回 (packed|None, text)。"""
    txt = Path(md_path).read_text(encoding="utf-8", errors="replace")
    m = _APP_RE.search(txt)
    if not m:
        return None, txt
    try:
        return json.loads(m.group(2)), txt
    except json.JSONDecodeError:
        return None, txt


def body_decidability(md_text: str) -> dict:
    """正文回退解析：附录缺失时，只能拿到 4 个字段。"""
    out: dict = {}
    m = re.search(r"\*\*可判定性\*\*[:：]\s*(\S+)", md_text)
    if m:
        out["decidability"] = m.group(1).strip()
    m = re.search(r"\*\*理由\*\*[:：]\s*(.+)", md_text)
    if m:
        out["reason"] = m.group(1).strip()
    out["decidable_aspects"] = [
        s.strip() for s in re.findall(r"^- 📗 可判定：(.*)$", md_text, re.M)]
    out["undecidable_aspects"] = [
        s.strip() for s in re.findall(r"^- 📘 不可判定：(.*)$", md_text, re.M)]
    return out


# ============================================================
# 2. 小工具
# ============================================================
def rebuild_view(mod, d: dict):
    """把 packed 里的 view dict 还原成引擎的 View 对象（只填已知字段）。"""
    if not isinstance(d, dict):
        return None
    names = {f.name for f in dataclasses.fields(mod.View)}
    kw = {k: v for k, v in d.items() if k in names}
    if "entry" not in kw:
        return None
    try:
        return mod.View(**kw)
    except Exception:
        return None


def _bare_aspect(t: str) -> str:
    """剥掉来源标注后缀与标点，用于逐字比对。与引擎 _bare 同口径。"""
    t = re.sub(r"[（(\[【]\s*(?:候选|amp|&|印记|悬置|suspension|thread|"
               r"线头|外)?\s*[0-9A-Za-z]*\s*[)）\]】]", "", str(t))
    return re.sub(r"[，。、；：:,\.;\s]+", "", t).strip()


def list_overlap(a, b, mod, thr: float = 0.55) -> float:
    """两个清单的条级重合率（同 _same_batch 口径，双向取平均）。"""
    a = [str(x) for x in (a or []) if str(x).strip()]
    b = [str(x) for x in (b or []) if str(x).strip()]
    if not a or not b:
        return 0.0
    ab = sum(1 for x in a if any(mod._similar(x, y, thr) for y in b)) / \
        max(len(a), len(b))
    ba = sum(1 for x in b if any(mod._similar(x, y, thr) for y in a)) / \
        max(len(a), len(b))
    return (ab + ba) / 2.0


def kw_jaccard(a, b, mod) -> float:
    """关键词集合 Jaccard。"""
    ka = mod._kw(" ".join(str(x) for x in (a or [])), top_n=12)
    kb = mod._kw(" ".join(str(x) for x in (b or [])), top_n=12)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / max(1, len(ka | kb))


def pair_near_dup(items, mod, thr: float = 0.7) -> tuple:
    """清单内两两近义配对数 / 总配对数。"""
    items = [str(x) for x in (items or []) if str(x).strip()]
    n = len(items)
    if n < 2:
        return 0, 0
    hits = 0
    for i in range(n):
        for j in range(i + 1, n):
            if mod._overlap_coef(items[i], items[j]) >= thr:
                hits += 1
    return hits, n * (n - 1) // 2


def cross_near_dup(a, b, mod, thr: float = 0.7) -> int:
    """两个清单之间的近义配对数（dec 与 und 应互斥）。"""
    a = [str(x) for x in (a or []) if str(x).strip()]
    b = [str(x) for x in (b or []) if str(x).strip()]
    return sum(1 for x in a for y in b
               if mod._overlap_coef(x, y) >= thr)


# ============================================================
# 3. A 组 · 结构自洽（静态）
# ============================================================
def check_A(dec: dict, mod, norm_count=None) -> dict:
    out: dict = {}
    status = str(dec.get("decidability", "")).lower()
    decs = [str(x) for x in (dec.get("decidable_aspects") or [])]
    unds = [str(x) for x in (dec.get("undecidable_aspects") or [])]
    untraced = set(dec.get("_und_untraced") or [])
    # 归一化实际采信的 und：非[外] 且不在 untraced
    und_for_norm = [a for a in unds
                    if a.startswith("[外]") or a not in untraced]

    # A1 三态-清单自洽：重放归一化，看是否复现产物里的状态
    try:
        recomputed = mod._normalize_decidability(
            status, decs, und_for_norm, where="")
    except Exception as e:
        out["A1"] = _item(None, NA, f"归一化重放失败：{e}")
        recomputed = None
    if recomputed is not None:
        if recomputed == status:
            out["A1"] = _item(True, OK,
                              f"归一化重放复现 {status}（自洽）")
        else:
            out["A1"] = _item(False, WARN,
                              f"归一化重放得 {recomputed}，产物写的是 "
                              f"{status} —— 三态与清单不自洽")

    # A2 归一化触发次数（需 --log：从跑批日志 grep「可判定性归一化」）
    if norm_count is None:
        out["A2"] = _item(None, NA,
                          "未给 --log（该计数只能从跑批日志数，"
                          "产物 md 里没有）")
    else:
        v = OK if norm_count <= 1 else (WARN if norm_count <= 3 else BAD)
        out["A2"] = _item(norm_count, v,
                          f"日志里「可判定性归一化」出现 {norm_count} 次"
                          f"（注意：日志是整批的，不专属这一份产物）")

    # A3 判定源
    src = str(dec.get("_source", "") or "")
    if not src:
        out["A3"] = _item(src or None, WARN, "无 _source（旧产物）")
    elif src == "pool+external":
        out["A3"] = _item(src, OK, "池判 + 外判都在，分叉可查")
    elif src in ("pool_only", "pool"):
        out["A3"] = _item(src, WARN, "只有池判，无外判对照")
    elif src == "external":
        out["A3"] = _item(src, OK, "池空路径，走外判（正常）")
    else:
        out["A3"] = _item(src, BAD, f"非正常来源：{src}")

    # A4 两路分叉
    dv = dec.get("_divergent")
    if dv is None:
        out["A4"] = _item(None, WARN,
                          "_divergent 缺失（单边判定无从验收）")
    elif dv:
        ps, es = dec.get("_pool_status"), dec.get("_ext_status")
        out["A4"] = _item(True, WARN,
                          f"两路分叉：池判={ps} / 外判={es}")
    else:
        out["A4"] = _item(False, OK, "两路一致")

    # A5 _ext_status 存在性
    has_ext = dec.get("_ext_status") is not None
    if has_ext:
        out["A5"] = _item(True, OK, f"_ext_status={dec.get('_ext_status')}")
    else:
        out["A5"] = _item(False, WARN, "_ext_status 缺失（分叉信息没留下）")
    return out


# ============================================================
# 4. B 组 · 追溯完整度
# ============================================================
def check_B(dec: dict, mod) -> dict:
    out: dict = {}
    unds = [str(x) for x in (dec.get("undecidable_aspects") or [])]
    decs = [str(x) for x in (dec.get("decidable_aspects") or [])]
    ev = dec.get("_evidence_full") or dec.get("evidence") or []
    ev = [e for e in ev if isinstance(e, dict)]
    untraced = list(dec.get("_und_untraced") or [])

    # 池判侧 und（分母）：排除 [外]
    pool_und = [a for a in unds if not a.startswith("[外]")]

    # B1 无追溯比（分母 = 池判侧 und 条目）
    #   ★ 分母为 0 时不出分档 —— 「有池判 und 且全都无追溯」与
    #     「压根没有池判 und 可查」必须分开，否则后者会被读成满分。
    if not pool_und:
        out["B1"] = _item(None, NA,
                          f"池判侧无 und 条目（{len(unds)} 条不可判定全来自"
                          f"外判）—— 无「池内追溯」可言，不适用")
    else:
        r = len(untraced) / len(pool_und)
        out["B1"] = _item(r, band_le(r, *TH["B1_untraced_ratio"]),
                          f"{len(untraced)}/{len(pool_und)} 条池判 und 无追溯")

    # B2 无追溯原文（必列）
    out["B2"] = _item(len(untraced), OK if not untraced else WARN,
                      "；".join(str(x)[:60] for x in untraced) or "（无）")

    # B3 evidence 覆盖
    #   ★ 分母只算**池判侧**条目：外判是独立判断，本来就不产 evidence，
    #     把它算进分母是系统性拉低（实测 5/13 里 8 条全是 [外]）。
    #     同 `_merge_decidability` 的口径。附全清单口径供对照。
    n_pool = len([a for a in decs if not a.startswith("[外]")]) + len(pool_und)
    denom = len(decs) + len(unds)
    if n_pool == 0:
        out["B3"] = _item(None, NA, "无池判侧清单条目，evidence 覆盖不适用")
    else:
        raw_r = len(ev) / n_pool
        # ★ 封顶 1.0：evidence 条数可能超过清单条数（一份清单可有多条
        #   evidence），实测出现过 6/5=1.2。覆盖率不是"人均配比"。
        r = min(raw_r, 1.0)
        out["B3"] = _item(r, band_ge(r, *TH["B3_evidence_cover"]),
                          f"{len(ev)}/{n_pool} 条**池判侧**清单有 evidence"
                          f"（含 [外] 口径 {len(ev)}/{denom}）")

    # B4 evidence.source 可解析为池内对象
    if not ev:
        out["B4"] = _item(0.0, WARN, "无 evidence")
    else:
        ok = 0
        for e in ev:
            s = str(e.get("source", "") or "").strip()
            if s and (_REF_RE.search(s) or _OBJ_RE.search(s)):
                ok += 1
        r = ok / len(ev)
        out["B4"] = _item(r, band_ge(r, *TH["B4_source_resolve"]),
                          f"{ok}/{len(ev)} 条 source 可定位到池内对象")

    # B5 [外] 前缀占比（记录，不分档）
    n_ext = sum(1 for a in (decs + unds) if a.startswith("[外]"))
    tot = len(decs) + len(unds)
    out["B5"] = _item(n_ext / tot if tot else 0.0, NA,
                      f"{n_ext}/{tot} 条来自外判并集（分叉痕迹）")
    return out


# ============================================================
# 5. C 组 · 三态判决稳定度（动态 / 假函数注入）
# ============================================================
def run_stability(assess_fn, question: str, view, n: int, mod) -> dict:
    """拿**固定** view 重复评估 n 次。assess_fn(question, view) -> dict。"""
    samples, errors = [], []
    for i in range(n):
        try:
            r = assess_fn(question, view)
            if not isinstance(r, dict):
                errors.append(f"第{i+1}次返回非 dict：{type(r).__name__}")
                continue
            # ★ 引擎在评估失败时会返回 `_source="pool_failed"` 的兜底
            #   （decidable / "池评估失败"）。把它当样本会让 C1 报出
            #   假的 1.0 —— 失败必须进 errors，不能进 samples。
            if str(r.get("_source", "")) == "pool_failed":
                errors.append(f"第{i+1}次评估失败：{r.get('reason')}")
                continue
            samples.append(r)
        except Exception as e:
            errors.append(f"第{i+1}次评估失败：{e}")

    res: dict = {"_n": len(samples), "_errors": errors, "_raw": samples,
                 "_insufficient": len(samples) < MIN_SAMPLE}
    if not samples:
        for k in ("C1", "C2", "C3", "C4"):
            res[k] = _item(None, NA, "无有效样本")
        res["C5"] = _item(None, NA, "无有效样本")
        return res

    # C1 判定值一致率
    cnt = Counter(str(s.get("decidability", "")) for s in samples)
    top_v, top_n = cnt.most_common(1)[0]
    c1 = top_n / len(samples)
    v1 = NA if res["_insufficient"] else band_ge(c1, *TH["C1_agree"])
    res["C1"] = _item(c1, v1,
                      f"最常见判定 {top_v} 出现 {top_n}/{len(samples)}"
                      f"；分布 {dict(cnt)}")

    # C2 清单条数极差
    sizes = [len(s.get("decidable_aspects") or [])
             + len(s.get("undecidable_aspects") or []) for s in samples]
    span = max(sizes) - min(sizes) if sizes else None
    v2 = NA if res["_insufficient"] else band_le(span, *TH["C2_span"])
    res["C2"] = _item(span, v2, f"条数={sizes}，极差={span}")

    # C3 语义重合度（两两条级重合，取均值）
    pair_vals = []
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            li = (samples[i].get("decidable_aspects") or []) + \
                 (samples[i].get("undecidable_aspects") or [])
            lj = (samples[j].get("decidable_aspects") or []) + \
                 (samples[j].get("undecidable_aspects") or [])
            pair_vals.append(list_overlap(li, lj, mod))
    c3 = sum(pair_vals) / len(pair_vals) if pair_vals else None
    v3 = NA if res["_insufficient"] else band_ge(c3, *TH["C3_semantic"])
    _c3_basis = (f"{len(pair_vals)} 个配对，均值 {c3:.3f}"
                 if c3 is not None else "无配对")
    res["C3"] = _item(c3, v3, _c3_basis)

    # C4 逐字重合率（记录，不分档）：出现 ≥2 次的条 / 全部条
    all_items = []
    for s in samples:
        all_items += [str(x) for x in
                      (s.get("decidable_aspects") or [])
                      + (s.get("undecidable_aspects") or [])]
    bare = [_bare_aspect(x) for x in all_items if _bare_aspect(x)]
    bc = Counter(bare)
    dup = sum(1 for x in bare if bc[x] >= 2)
    c4 = dup / len(bare) if bare else None
    res["C4"] = _item(c4, NA, f"{dup}/{len(bare)} 条逐字重复出现")

    # C5 样本量告警
    if res["_insufficient"]:
        res["C5"] = _item(False, WARN,
                          f"样本 {len(samples)} < {MIN_SAMPLE}，C 组分档不可用")
    else:
        res["C5"] = _item(True, OK, f"样本 {len(samples)} ≥ {MIN_SAMPLE}")
    return res


def stability_verdict(stab: dict) -> str:
    """C 组整体判据：C1/C2/C3 中 ≥2 个 ❌ → 不可当真。"""
    if not stab or stab.get("_insufficient"):
        return NA
    bad = sum(1 for k in ("C1", "C2", "C3")
              if stab.get(k, {}).get("verdict") == BAD)
    return BAD if bad >= 2 else (WARN if bad == 1 else OK)


# ============================================================
# 6. D 组 · 清单质量分项
# ============================================================
def _specificity(items) -> float:
    if not items:
        return 0.0
    return sum(1 for t in items if _is_specific(t)) / len(items)


def _slogan_count(items, mod) -> int:
    n = 0
    for t in items:
        s = str(t)
        if any(bp in s for bp in mod._BOILERPLATE) or \
                any(w in s for w in _SLOGAN_EXTRA):
            n += 1
    return n


def check_D(dec: dict, mod, extra_lists=None) -> dict:
    """extra_lists: C 组多轮采样时，把每轮的清单并起来看填满倾向。"""
    out: dict = {}
    decs = [str(x) for x in (dec.get("decidable_aspects") or [])]
    unds = [str(x) for x in (dec.get("undecidable_aspects") or [])]
    all_items = decs + unds

    # D1 具体度
    s = _specificity(all_items)
    _hit = sum(1 for t in all_items if _is_specific(t))
    out["D1"] = _item(s, band_ge(s, *TH["D1_specific"]),
                      f"{_hit}/{len(all_items)} 条含可指认对象"
                      f"（数值/条款号/引用号/动作动词）")

    # D2 口号式比例
    ns = _slogan_count(all_items, mod)
    if ns == 0:
        v = OK
    elif ns == 1:
        v = WARN
    else:
        v = BAD
    out["D2"] = _item(ns, v, f"{ns} 条命中口号词/BOILERPLATE")

    # D3 近义堆叠
    hits, pairs = pair_near_dup(all_items, mod)
    r = hits / pairs if pairs else 0.0
    out["D3"] = _item(r, band_le(r, *TH["D3_near_dup"]),
                      f"{hits}/{pairs} 对 overlap≥0.7")

    # D4 填满倾向（==5 是上限；只有静态单样本时只能看布尔）
    if extra_lists:
        fills = sum(1 for L in extra_lists
                    if len(L.get("decidable_aspects") or []) >= 5
                    or len(L.get("undecidable_aspects") or []) >= 5)
        r4 = fills / len(extra_lists)
        out["D4"] = _item(r4, band_le(r4, *TH["D4_fill"]),
                          f"{fills}/{len(extra_lists)} 轮有清单顶到上限 5")
    else:
        filled = (len(decs) >= 5) or (len(unds) >= 5)
        out["D4"] = _item(filled, NA,
                          f"静态单样本：dec={len(decs)}/und={len(unds)}"
                          f"（≥5 为顶到上限；填满倾向需 --repeat 才分档）")

    # D5 条长极差
    lens = [len(str(x)) for x in all_items if str(x).strip()]
    if len(lens) >= 2 and min(lens) > 0:
        ratio = max(lens) / min(lens)
        out["D5"] = _item(ratio, band_le(ratio, *TH["D5_len_ratio"]),
                          f"最长 {max(lens)} / 最短 {min(lens)} 字符")
    else:
        out["D5"] = _item(None, NA, "条数不足 2，无法算极差")

    # D6 dec 与 und 互斥性
    cd = cross_near_dup(decs, unds, mod)
    v6 = OK if cd == 0 else (WARN if cd <= 2 else BAD)
    out["D6"] = _item(cd, v6, f"{cd} 对 dec↔und 近义（应互斥）")
    return out


def quality_verdict(dq: dict) -> str:
    bad = sum(1 for k in ("D1", "D3", "D4")
              if dq.get(k, {}).get("verdict") == BAD)
    return WARN if bad >= 2 else OK


# ============================================================
# 7. E 组 · 两路一致性专项
# ============================================================
def check_E(dec: dict, view0, mod) -> dict:
    out: dict = {}
    decs = [str(x) for x in (dec.get("decidable_aspects") or [])]
    unds = [str(x) for x in (dec.get("undecidable_aspects") or [])]
    pool_dec = [a for a in decs if not a.startswith("[外]")]
    ext_dec = [a[len("[外] "):] for a in decs if a.startswith("[外]")]
    pool_und = [a for a in unds if not a.startswith("[外]")]
    ext_und = [a[len("[外] "):] for a in unds if a.startswith("[外]")]

    out["E1"] = _item(f"池判={dec.get('_pool_status')} / "
                      f"外判={dec.get('_ext_status')} / "
                      f"合并={dec.get('decidability')}", NA,
                      f"外判理由：{str(dec.get('_ext_reason', ''))[:80]}")

    if not ext_dec and not ext_und:
        out["E2"] = _item(None, NA, "无外判条目（池判单边或外判为空）")
    else:
        j_dec = kw_jaccard(pool_dec, ext_dec, mod)
        j_und = kw_jaccard(pool_und, ext_und, mod)
        avg = (j_dec + j_und) / 2
        out["E2"] = _item(avg, band_ge(avg, *TH["E2_two_way_jac"]),
                          f"dec Jaccard={j_dec:.2f}；und Jaccard={j_und:.2f}"
                          f"（低 ≠ bug：两路看的东西本就可能不同，"
                          f"但需在明细里核对）")

    # E3 两路无追溯比（与 B1 同口径：分母 0 → 不适用）
    untraced = list(dec.get("_und_untraced") or [])
    if not pool_und:
        out["E3"] = _item(None, NA,
                          "池判侧无 und —— 「无追溯」无从谈起；"
                          "外判侧无池可追溯（不适用）")
    else:
        r_pool = len(untraced) / len(pool_und)
        v3 = band_le(r_pool, *TH["B1_untraced_ratio"])
        out["E3"] = _item(r_pool, v3,
                          f"池判侧 {len(untraced)}/{len(pool_und)}；"
                          f"外判侧无池可追溯（不适用）")

    # E4 池是否空
    if view0 is None:
        out["E4"] = _item(None, NA, "无 view，无法判池空")
    else:
        try:
            has = mod.MetaDGTF._has_pool_content_view(view0)
        except Exception as e:
            out["E4"] = _item(None, NA, f"池空判据调用失败：{e}")
            return out
        out["E4"] = _item("池有内容" if has else "池空", NA,
                          "池有内容" if has else
                          "池空 —— 池判实际是读空池，分叉不算质量问题")
    return out


# ============================================================
# 7b. F 组 · 跨题分布
# ============================================================
_PTYPE_KW = (
    ("tech", ("系统", "架构", "算法", "性能", "并发", "数据", "软件", "接口",
              "超卖", "CAP", "缓存", "分布式", "服务", "平台", "模型")),
    ("biz", ("企业", "市场", "商业", "利润", "投资", "客户", "现金流", "营收",
             "成本", "供应链", "渠道", "定价", "盈利")),
    ("med", ("医疗", "临床", "病人", "患者", "药物", "诊断", "医院", "治疗")),
    ("eng", ("工程", "施工", "排水", "建筑", "设备", "产线", "制造", "市政",
             "管网", "车间", "工艺")),
    ("law", ("法律", "条款", "合规", "合同", "诉讼", "监管", "纠纷")),
    ("org", ("组织", "管理", "团队", "考核", "人事", "编制", "激励")),
)


def classify_ptype(question: str) -> str:
    q = question or ""
    for name, kws in _PTYPE_KW:
        if any(k in q for k in kws):
            return name
    return "other"


def check_F(rows, mod) -> dict:
    """rows = [{"question","type","audit"}] —— 跨题分布。"""
    out: dict = {}
    if not rows:
        for k in ("F1", "F2", "F3"):
            out[k] = _item(None, NA, "无样本")
        out["F4"] = _item([], NA, "无样本")
        return out

    groups: dict = {}
    for r in rows:
        groups.setdefault(r.get("type", "other"), []).append(r)

    # F1 判定分布（某类占比 >0.9 且样本够 → ⚠️，可能被某种题面 dominate）
    dist = {}
    for t, rs in groups.items():
        c = Counter(str((r["audit"].get("_dec") or {}).get("decidability"))
                    for r in rs)
        dist[t] = dict(c)
    _risky = []
    for t, c in dist.items():
        tot = sum(c.values())
        if tot >= 5 and max(c.values()) / tot > 0.9:
            _risky.append(t)
    _disp = "；".join(f"{t}:{v}" for t, v in dist.items())
    if _risky:
        out["F1"] = _item(_disp, WARN,
                          f"{_disp}　被单种判定 dominate 的题型：{_risky}")
    else:
        out["F1"] = _item(_disp, NA,
                          f"{_disp}（样本 <5/类时不做 dominate 判定）")

    def _med(vals, key):
        v = [x for x in vals if x is not None]
        if not v:
            return None
        v.sort()
        return v[len(v) // 2]

    # F2 一致率中位数
    c1s = [(r["audit"].get("stability") or {}).get("C1", {}).get("value")
           for r in rows]
    m2 = _med(c1s, "C1")
    if m2 is None:
        out["F2"] = _item(None, WARN, "未跑 --repeat，无一致率可汇总")
    else:
        out["F2"] = _item(m2, band_ge(m2, *TH["F2_agree_median"]),
                          f"各组 C1 中位 = {m2:.3f}（n={len(c1s)}）")

    # F3 无追溯比中位数
    b1s = [(r["audit"].get("traceability") or {}).get("B1", {}).get("value")
           for r in rows]
    m3 = _med(b1s, "B1")
    if m3 is None:
        out["F3"] = _item(None, NA, "各题池判侧均无 und（不适用）")
    else:
        out["F3"] = _item(m3, band_le(m3, *TH["F3_untraced_median"]),
                          f"各题 B1 中位 = {m3:.3f}")

    # F4 三元组记录（不出分档）
    tri = []
    for r in rows:
        a = r["audit"]
        tri.append({
            "type": r.get("type"),
            "question": (r.get("question") or "")[:24],
            "decidability": (a.get("_dec") or {}).get("decidability"),
            "size_span": (a.get("stability") or {}).get("C2", {}).get("value"),
            "C1": (a.get("stability") or {}).get("C1", {}).get("value"),
            "B1": (a.get("traceability") or {}).get("B1", {}).get("value"),
        })
    out["F4"] = _item(len(tri), NA, "逐题三元组见附录 json 的 distribution.F4")
    out["_rows"] = tri
    return out


# ============================================================
# 8. 汇总
# ============================================================
def summarize(structure, trace, quality, stab, two_way) -> dict:
    a_bad = sum(1 for v in structure.values() if v["verdict"] == BAD)
    b1_bad = trace.get("B1", {}).get("verdict") == BAD
    stab_v = stability_verdict(stab) if stab else NA

    if a_bad or b1_bad or stab_v == BAD:
        usable = "bad"
    elif stab_v == WARN or any(
            v["verdict"] in (WARN, BAD)
            for v in list(structure.values()) + list(trace.values())):
        usable = "warning"
    else:
        usable = "ok"

    issues = []
    for k, v in structure.items():
        if v["verdict"] in (WARN, BAD):
            issues.append(f"{k} {v['basis']}")
    for k, v in trace.items():
        if v["verdict"] in (WARN, BAD):
            issues.append(f"{k} {v['basis']}")
    if stab_v in (WARN, BAD):
        issues.append("C 组稳定度未过")
    main = issues[0] if issues else "无（结构自洽 + 追溯完整）"

    _act = {
        "bad": "结论不可当真：先看第 1/2 节与 C 组，别拿它当判据",
        "warning": "可用但带警示：读逐条明细确认清单质量",
        "ok": "结构面可用；清单质量仍需人读逐条明细",
    }[usable]
    if quality.get("_verdict") == WARN:
        _act += "；D 组清单质量差（⚠️）"
    return {"usable": usable, "main_issue": main, "suggested_action": _act,
            "stability_verdict": stab_v}


# ============================================================
# 9. 渲染 MD
# ============================================================
def _table(d: dict, keys) -> str:
    lines = ["| 检查项 | 值 | 分档 | 依据 |",
             "| --- | --- | --- | --- |"]
    for k in keys:
        it = d.get(k)
        if not it:
            continue
        val = it.get("value")
        if val is None:
            val = "—"
        elif isinstance(val, float):
            val = f"{val:.3f}"
        elif isinstance(val, bool):
            val = "是" if val else "否"
        lines.append(f"| {k} | {val} | {it['verdict']} | {it['basis']} |")
    return "\n".join(lines)


def render_md(meta, summary, structure, trace, stab, quality, two_way,
              dec, errors, distribution=None) -> str:
    L = []
    L.append(f"# 评估质量审计 · {meta['target_version']} · "
             f"{meta['audit_ts']}")
    L.append("")
    L.append("## 0. 结论摘要")
    L.append("")
    _usable_disp = {"ok": "✅ 可用", "warning": "⚠️ 带警示",
                    "bad": "❌ 不可当真"}.get(summary["usable"],
                                              summary["usable"])
    L.append(f"- 判定值：**{dec.get('decidability', '?')}**"
             f"（来源 {dec.get('_source', '?')}）")
    L.append(f"- 是否可用：**{_usable_disp}**")
    L.append(f"- 主要问题：{summary['main_issue']}")
    L.append(f"- 建议动作：{summary['suggested_action']}")
    L.append(f"- 输入：mode={meta['mode']}  repeat={meta['repeat']}  "
             f"sample={meta['sample']}  layer={meta.get('view_layer')}")
    L.append("")

    L.append("## 1. 结构自洽（静态）")
    L.append("")
    L.append(_table(structure, ("A1", "A2", "A3", "A4", "A5")))
    L.append("")

    L.append("## 2. 追溯完整度")
    L.append("")
    L.append(_table(trace, ("B1", "B2", "B3", "B4", "B5")))
    L.append("")

    L.append("## 3. 三态判决稳定度")
    L.append("")
    if not stab:
        L.append("未做。要跑加 `--repeat 5`（视图从产物重建，不重跑流程）。")
    else:
        L.append(_table(stab, ("C1", "C2", "C3", "C4", "C5")))
        if stab.get("_errors"):
            L.append("")
            for e in stab["_errors"]:
                L.append(f"- 采样异常：{e}")
        raw = stab.get("_raw") or []
        if raw:
            L.append("")
            L.append(f"### 各轮原始清单（{len(raw)} 轮，逐字留痕）")
            L.append("")
            for i, s in enumerate(raw, 1):
                L.append(f"- **第 {i} 轮** 判定 `{s.get('decidability')}`"
                         f"　dec={len(s.get('decidable_aspects') or [])} / "
                         f"und={len(s.get('undecidable_aspects') or [])}")
                for a in (s.get("decidable_aspects") or []):
                    L.append(f"  - 📗 {str(a)[:80]}")
                for a in (s.get("undecidable_aspects") or []):
                    L.append(f"  - 📘 {str(a)[:80]}")
    L.append("")

    L.append("## 4. 清单质量分项")
    L.append("")
    L.append("以 1 为上限：0 表示该项无问题。"
             "具体度/语义重合是**越高越好**，其余越低越好。")
    L.append("")
    L.append(_table(quality, ("D1", "D2", "D3", "D4", "D5", "D6")))
    L.append("")

    L.append("## 5. 两路一致性（池判 vs 外判）")
    L.append("")
    L.append(_table(two_way, ("E1", "E2", "E3", "E4")))
    L.append("")

    L.append("## 6. 跨题分布")
    L.append("")
    if not distribution:
        L.append("未做。要跑加 `--sample N --from-dir <产物目录>`"
                 "（静态、推荐）或 `--sample N --questions-file <题面清单>`"
                 "（真跑，成本高）。")
    else:
        L.append(_table(distribution, ("F1", "F2", "F3", "F4")))
        rows = distribution.get("_rows") or []
        if rows:
            L.append("")
            L.append("| 题型 | 题目 | 判定值 | C2 条数极差 | C1 | B1 |")
            L.append("| --- | --- | --- | --- | --- | --- |")
            for r in rows:
                def _f(x):
                    # ★ 别用 `x or "—"`：C2 的正常值就是 0，会被 falsy 吞掉
                    if x is None:
                        return "—"
                    if isinstance(x, float):
                        return f"{x:.3f}"
                    return str(x)
                L.append(f"| {r.get('type')} | {r.get('question')} | "
                         f"{r.get('decidability') or '—'} | "
                         f"{_f(r.get('size_span'))} | "
                         f"{_f(r.get('C1'))} | {_f(r.get('B1'))} |")
    L.append("")

    L.append("## 7. 逐条明细")
    L.append("")
    L.append("### decidable_aspects")
    for i, a in enumerate(dec.get("decidable_aspects") or [], 1):
        L.append(f"{i}. {a}　<sub>具体度 "
                 f"{_specificity([a]):.0f}</sub>")
    L.append("")
    L.append("### undecidable_aspects")
    untraced = set(dec.get("_und_untraced") or [])
    for i, a in enumerate(dec.get("undecidable_aspects") or [], 1):
        tag = "无追溯" if a in untraced else "有追溯/外判"
        L.append(f"{i}. {a}　<sub>{tag}</sub>")
    L.append("")
    L.append("### evidence")
    ev = dec.get("_evidence_full") or dec.get("evidence") or []
    if not ev:
        L.append("（无）")
    else:
        for e in ev:
            if isinstance(e, dict):
                L.append(f"- `{e.get('source', '')}` → {e.get('aspect', '')}")
    L.append("")

    L.append("## 8. 失败记录")
    L.append("")
    if errors:
        for e in errors:
            L.append(f"- {e}")
    else:
        L.append("无。")
    L.append("")
    return "\n".join(L)


# ============================================================
# 10. 主审计流程
# ============================================================
def audit(packed: dict, mod, meta: dict, *, assess_fn=None, repeat: int = 0,
          view_layer: str = "0", norm_count=None,
          distribution=None) -> dict:
    errors: list = list(meta.pop("_input_errors", []))
    dec = packed.get("decidability") or {}
    if not isinstance(dec, dict):
        errors.append("packed.decidability 不是 dict —— 退化为空")
        dec = {}

    structure = check_A(dec, mod, norm_count=norm_count)
    trace = check_B(dec, mod)

    stab = None
    extra_lists = None
    if assess_fn is not None and repeat > 0:
        views = packed.get("views") or {}
        view = rebuild_view(mod, views.get(view_layer))
        if view is None:
            errors.append(f"views['{view_layer}'] 无法重建，C 组跳过")
        else:
            stab = run_stability(assess_fn, packed.get("question", ""),
                                 view, repeat, mod)
            extra_lists = stab.get("_raw") or None

    quality = check_D(dec, mod, extra_lists=extra_lists)
    quality["_verdict"] = quality_verdict(quality)

    view0 = rebuild_view(mod, (packed.get("views") or {}).get(view_layer))
    two_way = check_E(dec, view0, mod)

    summary = summarize(structure, trace, quality, stab, two_way)
    meta["view_layer"] = view_layer

    return {
        "meta": meta,
        "summary": summary,
        "structure": structure,
        "traceability": trace,
        "stability": stab or {},
        "quality": quality,
        "two_way": two_way,
        "distribution": distribution or {},
        "details": {
            "dec_aspects": [
                {"text": a, "specificity": _specificity([a])}
                for a in (dec.get("decidable_aspects") or [])],
            "und_aspects": [
                {"text": a,
                 "traced": a not in set(dec.get("_und_untraced") or [])}
                for a in (dec.get("undecidable_aspects") or [])],
            "evidence": dec.get("_evidence_full") or dec.get("evidence") or [],
        },
        "_dec": dec,
        "errors": errors,
    }


# ============================================================
# 11. 负对照自检（三条，证明探针抓得住问题）
# ============================================================
def _self_test(mod) -> int:
    fails: list = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
        if not cond:
            fails.append(name)

    # --- 负对照 1：结构不自洽必须被抓 ---
    print("负对照 1 · 结构自洽")
    bad_packed = {
        "question": "selftest",
        "decidability": {
            "decidability": "undecidable",
            "decidable_aspects": ["这条明明是可判定的方面"],
            "undecidable_aspects": [],
            "_source": "pool+external",
            "_pool_status": "undecidable",
            "_ext_status": "undecidable",
            "_divergent": False,
            "_und_untraced": [],
        },
        "views": {},
    }
    r1 = check_A(bad_packed["decidability"], mod)
    check("A1 抓住不自洽", r1["A1"]["verdict"] in (WARN, BAD),
          r1["A1"]["basis"])

    # --- 负对照 2：稳定度探针必须区分“每次不同”和“逐字稳定” ---
    print("负对照 2 · 稳定度")
    varying = [
        {"decidability": "decidable",
         "decidable_aspects": ["采购成本可核算"], "undecidable_aspects": []},
        {"decidability": "undecidable",
         "decidable_aspects": [], "undecidable_aspects": ["审美偏好无法量化"]},
        {"decidability": "partial",
         "decidable_aspects": ["交付周期可测算"],
         "undecidable_aspects": ["组织政治不可探"]},
        {"decidability": "decidable",
         "decidable_aspects": ["人员编制可盘点"], "undecidable_aspects": []},
        {"decidability": "undecidable",
         "decidable_aspects": [], "undecidable_aspects": ["品牌溢价不可测"]},
    ]
    it = {"i": 0}

    def fn_varying(q, v):
        r = varying[it["i"] % len(varying)]
        it["i"] += 1
        return r

    sv = run_stability(fn_varying, "q", None, 5, mod)
    check("C1 变化时判低", sv["C1"]["value"] < 0.5,
          f"C1={sv['C1']['value']:.2f}")
    check("C3 变化时判低", sv["C3"]["value"] < 0.5,
          f"C3={sv['C3']['value']:.2f}")
    check("C 组整体非 OK", stability_verdict(sv) in (WARN, BAD),
          stability_verdict(sv))

    same = {"decidability": "partial",
            "decidable_aspects": ["客户回款到账日可查"],
            "undecidable_aspects": ["企业主风险偏好无法量化"]}

    def fn_stable(q, v):
        return dict(same)

    ss = run_stability(fn_stable, "q", None, 5, mod)
    check("C1 稳定时为 1", abs(ss["C1"]["value"] - 1.0) < 1e-9,
          f"C1={ss['C1']['value']:.2f}")
    check("C3 稳定时高", ss["C3"]["value"] >= 0.6,
          f"C3={ss['C3']['value']:.2f}")
    check("C 组整体 OK", stability_verdict(ss) == OK,
          stability_verdict(ss))

    # --- 负对照 3：具体度必须区分口号与具体 ---
    print("负对照 3 · 具体度")
    slogan = {"decidable_aspects": ["核心诉求未定", "存在根本冲突",
                                    "本质上不可判定", "归根结底是哲学问题"],
              "undecidable_aspects": []}
    concrete = {"decidable_aspects": ["第25条规定的付款期限",
                                      "候选3的 position=both 说明两面读不出同一答案",
                                      "T2 探针给出边界判据后即可定夺"],
                "undecidable_aspects": []}
    d_slogan = check_D(slogan, mod)
    d_conc = check_D(concrete, mod)
    check("D1 口号清单判低", d_slogan["D1"]["verdict"] in (WARN, BAD),
          f"D1={d_slogan['D1']['value']:.2f} {d_slogan['D1']['verdict']}")
    check("D1 具体清单判高", d_conc["D1"]["verdict"] == OK,
          f"D1={d_conc['D1']['value']:.2f}")
    check("D2 口号清单命中", d_slogan["D2"]["value"] >= 1,
          f"D2={d_slogan['D2']['value']}")

    print()
    if fails:
        print(f"自检失败 {len(fails)} 条：{fails}")
        return 1
    print("自检全部通过（3 条负对照，探针对应判别力成立）")
    return 0


# ============================================================
# 12. CLI
# ============================================================
def _version_of(target_py: Path) -> str:
    m = re.search(r"V?(\d+\.\d+\.\d+)", target_py.stem)
    return m.group(1) if m else target_py.stem


def _run_sampling(mod, args, target_py: Path) -> int:
    """F 组：跨题分布。

    两个输入源：
      · `--from-dir <目录> --sample N`：扫目录里**最近 N 份**带全量附录的产物
        （推荐 —— 复用已跑过的真实产物，静态、秒级、零调用）。
      · `--questions-file <路径>`：逐题**真跑**一次最小流程（任务书原规格，
        成本高：每题 route 0,1 各 1 圈 ≈ 15~21 min）。
    """
    rows = []

    if getattr(args, "from_dir", None):
        src = Path(args.from_dir)
        if not src.exists():
            src = HERE / args.from_dir
        if not src.is_dir():
            print(f"❌ 目录不存在：{args.from_dir}")
            return 2
        picked = []
        seen_q: set = set()
        # 按 mtime 倒序扫**全部**产物，题目去重后取前 N 个不同题。
        #   ★ 别截断扫描窗口：实测最近 600 份产物里只有 3 个不同题
        #     （跑批会同题反复跑），截断会让"跨题分布"退化成同题分布。
        for p in sorted(src.glob("*.md"),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            if len(picked) >= args.sample:
                break
            packed, _txt = packed_from_md(p)
            if packed is None:
                continue          # 无全量附录的产物跳过
            q = packed.get("question", "") or p.stem
            if q in seen_q:
                continue          # 同题只取最近一份
            seen_q.add(q)
            picked.append((p, packed))
        if not picked:
            print("❌ 目录里没有带全量附录的产物")
            return 2
        print(f"[sample] 从目录取 {len(picked)} 份（静态）")
        _fn = _make_assess_fn(mod, args) if args.repeat > 0 else None
        for i, (p, packed) in enumerate(picked, 1):
            q = packed.get("question", "") or p.stem
            print(f"  [{i}/{len(picked)}] {str(q)[:40]}")
            m = {"target_py": target_py.name,
                 "target_version": _version_of(target_py),
                 "audit_ts": datetime.now().isoformat(timespec="seconds"),
                 "mode": "dynamic" if args.repeat > 0 else "static",
                 "repeat": args.repeat, "sample": args.sample,
                 "question": q, "n_views": len(packed.get("views") or {}),
                 "source": str(p.name),
                 "_input_errors": []}
            r = audit(packed, mod, m, assess_fn=_fn,
                      repeat=args.repeat, view_layer=args.view_layer)
            rows.append({"question": q, "type": classify_ptype(q),
                         "audit": r})
    else:
        qf = Path(args.questions_file)
        if not qf.exists():
            qf = HERE / args.questions_file
        if not qf.exists():
            print(f"❌ 题面文件不存在：{args.questions_file}")
            return 2
        qs = [ln.strip() for ln in
              qf.read_text(encoding="utf-8", errors="replace").splitlines()
              if ln.strip()][:args.sample]
        if not qs:
            print("❌ 题面文件为空")
            return 2
        for i, q in enumerate(qs, 1):
            print(f"[sample {i}/{len(qs)}] 真跑最小流程：{q[:40]}")
            try:
                cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
                engine = mod.MetaDGTF(cfg)
                packed = engine.run(q, route=["0", "1"],
                                    rounds={"0": 1, "1": 1},
                                    parallel_mode="serial")
            except Exception as e:
                print(f"  ⚠️ 跑失败，跳过：{e}")
                continue
            m = {"target_py": target_py.name,
                 "target_version": _version_of(target_py),
                 "audit_ts": datetime.now().isoformat(timespec="seconds"),
                 "mode": "dynamic", "repeat": args.repeat,
                 "sample": args.sample, "question": q,
                 "n_views": len(packed.get("views") or {}),
                 "_input_errors": []}
            r = audit(packed, mod, m,
                      assess_fn=_make_assess_fn(mod, args, engine)
                      if args.repeat > 0 else None,
                      repeat=args.repeat, view_layer=args.view_layer)
            rows.append({"question": q, "type": classify_ptype(q),
                         "audit": r})

    if not rows:
        print("❌ 没有任何一题跑成功")
        return 1

    dist = check_F(rows, mod)
    first = rows[0]["audit"]
    types = Counter(r["type"] for r in rows)
    first["summary"] = dict(first["summary"])
    first["summary"]["main_issue"] = (
        f"跨题采样 {len(rows)} 题，题型分布 {dict(types)}；单题明细见第 6 节")
    first["summary"]["suggested_action"] = (
        "横向看分布：某题型判定分布 >90% 或一致率中位偏低 → "
        "该题型不适合当前评估 prompt")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md = render_md(first["meta"], first["summary"], first["structure"],
                   first["traceability"], first["stability"],
                   first["quality"], first["two_way"], first["_dec"],
                   first["errors"], distribution=dist)
    md = (f"> 本报告为 `--sample {args.sample}` 跨题采样；"
          f"第 1~5 节是**第 1 题**的明细，第 6 节是全部 {len(rows)} 题的分布。\n\n"
          + md)
    md_path = out_dir / f"eval_quality_sample_{ts}.md"
    md_path.write_text(md, encoding="utf-8")
    side = {k: v for k, v in first.items() if k != "_dec"}
    side["distribution"] = {k: v for k, v in dist.items()}
    (out_dir / f"eval_quality_sample_{ts}.json").write_text(
        json.dumps(side, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8")
    print(f"[sample] {len(rows)} 题  -> {md_path}")
    return 0


def _make_assess_fn(mod, args, engine=None):
    """构造 assess_fn：从 packed 重建 view 后重复评估。"""
    if engine is None:
        cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
        engine = mod.MetaDGTF(cfg)

    def _af(q, v):
        return engine._assess_decidability_from_pool_view(q, v)
    return _af


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="评估阶段质量只读审计探针")
    ap.add_argument("target_py", help="目标元DGTF py 文件")
    ap.add_argument("--from-md", dest="from_md", default=None,
                    help="从产物 md 读（抽全量附录里的 packed）")
    ap.add_argument("--from-pool", dest="from_pool", default=None,
                    help="从 packed json 读")
    ap.add_argument("--question", default=None,
                    help="无产物时现跑（动态）—— 本版只用它做 C 组入口")
    ap.add_argument("--repeat", type=int, default=0,
                    help="同 view 重复评估次数（C 组），默认 0")
    ap.add_argument("--view-layer", default="0",
                    help="C 组用哪一层的 view，默认 0")
    ap.add_argument("--sample", type=int, default=0, help="多题采样数")
    ap.add_argument("--questions-file", default=None,
                    help="多题真跑时的题面清单（一行一题）")
    ap.add_argument("--from-dir", dest="from_dir", default=None,
                    help="多题采样的目录源：扫最近 N 份含全量附录的产物"
                         "（静态、推荐，比 --questions-file 便宜得多）")
    ap.add_argument("--out-dir", default=str(HERE / "audits"))
    ap.add_argument("--log", default=None,
                    help="跑批日志路径，用于 A2（数「可判定性归一化」）")
    ap.add_argument("--json", action="store_true", help="只输出 json")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="跑三条负对照，验证探针判别力")
    args = ap.parse_args(argv)

    target_py = Path(args.target_py)
    if not target_py.exists():
        target_py = HERE / args.target_py
    if not target_py.exists():
        print(f"❌ 找不到目标文件：{args.target_py}")
        return 2

    # 离线与否：只有真会打 LLM 的路径才加载真 key
    #   --from-dir 纯静态（不带 --repeat）不该碰 key
    dynamic = bool(args.repeat > 0) or (
        bool(args.sample > 0) and not getattr(args, "from_dir", None))
    mod = load_engine(target_py, offline=not dynamic)

    if args.self_test:
        return _self_test(mod)

    if args.sample > 0:
        return _run_sampling(mod, args, target_py)

    input_errors: list = []
    packed = None
    mode = "static"
    if args.from_pool:
        try:
            packed = json.loads(Path(args.from_pool).read_text(
                encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"❌ 读 packed json 失败：{e}")
            return 2
    elif args.from_md:
        packed, txt = packed_from_md(Path(args.from_md))
        if packed is None:
            packed = {"decidability": body_decidability(txt), "views": {}}
            input_errors.append(
                "附录 packed 未解析到 —— 已退化为正文回退（只有 4 个字段，"
                "A3/A4/A5/B1/B4/E 组不可用）")
    else:
        print("❌ 需要 --from-md 或 --from-pool（本版不做无产物现跑全流程）")
        return 2

    if not packed:
        print("❌ 未取到 packed")
        return 2

    # 动态：准备评估函数（复刻 _assess_decidability_from_pool_view 的调用面）
    assess_fn = None
    if dynamic:
        try:
            cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
            meta_obj = mod.MetaDGTF(cfg)
        except Exception as e:
            print(f"❌ 初始化引擎实例失败：{e}")
            return 2

        def _assess(q, v):
            return meta_obj._assess_decidability_from_pool_view(q, v)
        assess_fn = _assess
        mode = "dynamic"

    views = packed.get("views") or {}
    any_view = next(iter(views.values()), None)
    question = packed.get("question", "") or (args.question or "")

    meta = {
        "target_py": target_py.name,
        "target_version": _version_of(target_py),
        "audit_ts": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "repeat": args.repeat,
        "sample": args.sample,
        "question": question,
        "n_views": len(views) if isinstance(views, dict) else 0,
        "_input_errors": input_errors,
    }
    if any_view is None:
        input_errors.append("packed 无 views —— C/E4 组不可用")

    # A2：归一化触发次数只能从跑批日志数
    norm_count = None
    if args.log:
        lp = Path(args.log)
        if not lp.exists():
            lp = HERE / args.log
        if lp.exists():
            try:
                norm_count = lp.read_text(encoding="utf-8",
                                          errors="replace").count(
                    "可判定性归一化")
            except Exception as e:
                input_errors.append(f"读日志失败：{e}")
        else:
            input_errors.append(f"日志不存在：{args.log}")

    res = audit(packed, mod, meta, assess_fn=assess_fn, repeat=args.repeat,
                view_layer=args.view_layer, norm_count=norm_count)

    if args.json:
        print(json.dumps({k: v for k, v in res.items() if k != "_dec"},
                         ensure_ascii=False, indent=1, default=str))
        return 0 if res["summary"]["usable"] != "bad" else 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"eval_quality_{ts}.md"
    json_path = out_dir / f"eval_quality_{ts}.json"

    md = render_md(res["meta"], res["summary"], res["structure"],
                   res["traceability"], res["stability"], res["quality"],
                   res["two_way"], res["_dec"], res["errors"],
                   distribution=res.get("distribution"))
    md_path.write_text(md, encoding="utf-8")

    sidecar = {k: v for k, v in res.items() if k != "_dec"}
    if sidecar.get("stability"):
        sidecar["stability"].pop("_raw", None)
    json_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=1,
                                    default=str), encoding="utf-8")

    print(f"[audit] {res['meta']['target_version']}  "
          f"usable={res['summary']['usable']}")
    print(f"[audit] 判定值={res['_dec'].get('decidability')}  "
          f"来源={res['_dec'].get('_source')}")
    print(f"[audit] md   -> {md_path}")
    print(f"[audit] json -> {json_path}")
    for e in res["errors"]:
        print(f"[warn] {e}")
    if args.verbose:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
